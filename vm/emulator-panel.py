#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared browser/desktop panel for the ordinary native QEMU launcher."""
import argparse
import importlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from emulator_ui import Panel, make_server
from local_transport import connect

prime = importlib.import_module('prime-control')


class NativeControls:
    def __init__(self, input_socket, qmp_socket):
        self.input_socket = input_socket
        self.channel = self
        self.held = set()
        self.socket = connect(qmp_socket, timeout=30, io_timeout=2)
        self.file = self.socket.makefile('rwb', buffering=0)
        json.loads(self.file.readline(65536))
        self.execute('qmp_capabilities')

    def command(self, command):
        return prime.send_command(self.input_socket, command, timeout=2)

    def keys(self, names):
        desired = set(names)
        for name in sorted(self.held-desired):
            if self.command(f'KEY {prime.KEYS[name]} 0') != 'OK':
                raise RuntimeError('Key release failed')
            self.held.remove(name)
        for name in sorted(desired-self.held):
            command = ('POWER RESUME' if name == 'onoff' and self.command('POWER STATE') == 'VALUE 1'
                       else f'KEY {prime.KEYS[name]} 1')
            if self.command(command) != 'OK':
                raise RuntimeError('Key press failed')
            self.held.add(name)

    def execute(self, command, arguments=None):
        self.file.write((json.dumps({'execute': command, 'arguments': arguments or {}})+'\n').encode())
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            response = json.loads(self.file.readline(65536))
            if 'event' in response:
                continue
            if 'error' in response:
                raise RuntimeError(str(response['error']))
            return response
        raise TimeoutError('QEMU monitor did not respond')

    def close(self):
        try:
            self.keys([])
            self.command('TOUCH FRAME 0')
        finally:
            self.file.close()
            self.socket.close()


def desktop(url):
    if sys.platform != 'darwin':
        raise RuntimeError('The desktop window currently requires macOS; use --browser on this host')
    source = ROOT / 'vm/emulator-window.swift'
    bundle = ROOT / 'build/emulator-window/Lefony Emulator.app'
    executable = bundle / 'Contents/MacOS/Lefony Emulator'
    executable.parent.mkdir(parents=True, exist_ok=True)
    import plistlib
    (bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleExecutable': 'Lefony Emulator', 'CFBundleIdentifier': 'com.lefony.emulator.preview',
        'CFBundleName': 'Lefony Emulator', 'CFBundlePackageType': 'APPL',
        'NSHighResolutionCapable': True,
    }))
    if not executable.exists() or executable.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(['swiftc', str(source), '-o', str(executable)], check=True, timeout=120)
    return subprocess.Popen([str(executable), url])


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--qmp', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qemu-pid', type=int, required=True)
    parser.add_argument('--desktop', action='store_true')
    args = parser.parse_args()
    window = None
    controls = NativeControls(args.input, args.qmp)
    try:
        deadline = time.monotonic()+30
        while True:
            try:
                if controls.command('PING') == 'PONG':
                    break
            except RuntimeError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('Guest input did not become ready')
            time.sleep(.1)
        panel = Panel(controls, args.output, prime.KEYS)
        with make_server(panel, 'Lefony OS') as server:
            (args.output / 'panel-url.txt').write_text(server.url+'\n')
            print('Lefony Emulator: '+server.url, flush=True)
            if args.desktop:
                window = desktop(server.url)
            else:
                webbrowser.open(server.url)
            while not panel.stopped and (window is None or window.poll() is None):
                try:
                    os.kill(args.qemu_pid, 0)
                except ProcessLookupError:
                    break
                server.handle_request()
                panel.expire()
            if panel.failure:
                raise RuntimeError('Emulator panel disconnected') from panel.failure
    except KeyboardInterrupt:
        pass
    finally:
        try:
            controls.close()
        finally:
            if window is not None and window.poll() is None:
                window.terminate()
                try:
                    window.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    window.kill()
                    window.wait(timeout=3)


if __name__ == '__main__':
    main()

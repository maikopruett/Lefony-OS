#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared desktop panel for the ordinary native QEMU launcher."""
import argparse
import importlib
import json
import os
import signal
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from emulator_ui import Panel
from emulator_desktop import serve_desktop, wait_for_boot_ui
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


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--qmp', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qemu-pid', type=int, required=True)
    args = parser.parse_args()
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
        # Interactive sessions model external power; dismiss its boot status sheet.
        wait_for_boot_ui(controls)
        controls.keys(['back'])
        time.sleep(.25)
        controls.keys([])
        panel = Panel(controls, args.output, prime.KEYS)
        def alive():
            try:
                os.kill(args.qemu_pid, 0)
                return True
            except ProcessLookupError:
                return False
        serve_desktop(panel, 'Lefony OS', alive)
    except KeyboardInterrupt:
        pass
    finally:
        controls.close()


if __name__ == '__main__':
    main()

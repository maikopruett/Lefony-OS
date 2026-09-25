#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded embedded-renderer startup smoke; no browser and no physical device."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
sys.path.insert(0, str(ROOT / 'scripts'))
from PIL import Image
from emulator_ui import Panel, make_server
from emulator_desktop import window_command
from replay import KEYS
from build_emulator_window import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-bundle', type=Path)
    args = parser.parse_args()
    record = verify(args.window_bundle) if args.window_bundle else None
    with tempfile.TemporaryDirectory(prefix='lefony-window-smoke-') as directory:
        folder = Path(directory)
        class Fixture:
            channel = None
            frames = 0
            def keys(self, names):
                pass
            def command(self, value):
                return 'OK'
            def execute(self, command, arguments):
                assert command == 'screendump'
                self.frames += 1
                Image.new('RGB', (320, 240), (70, 100, 65)).save(arguments['filename'])
        fixture = Fixture()
        fixture.channel = fixture
        panel = Panel(fixture, folder, set(KEYS) | {'onoff'})
        with make_server(panel, 'Desktop startup check') as server:
            ready = folder / 'ready'
            if record:
                command = [str((args.window_bundle / record['executable']).resolve()), server.url,
                           '--title', 'Desktop startup check', '--ready-file', str(ready)]
            else:
                command = window_command(server.url, 'Desktop startup check', ready)
            process = subprocess.Popen(command)
            try:
                deadline = time.monotonic() + 30
                while not (ready.is_file() and fixture.frames >= 2):
                    if process.poll() is not None:
                        raise RuntimeError('Window exited before rendering: ' + str(process.returncode))
                    if time.monotonic() > deadline:
                        raise TimeoutError('Window did not render within 30 seconds')
                    server.handle_request()
                print(json.dumps({'system': platform.system(), 'embedded_renderer': 'passed',
                                  'frames': fixture.frames, 'frozen': bool(record)}))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == '__main__':
    main()

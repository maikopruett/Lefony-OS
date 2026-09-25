#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise recovery Settings through the emulated key matrix; no physical device."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import time

recovery = importlib.import_module('test-prime-g2-rom-recovery')
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'build/settings-recovery-validation'
    output.mkdir(exist_ok=True)
    for path in output.glob('*.sock'):
        path.unlink()
    command = [str(recovery.QEMU), '-machine', 'mcimx6ul-evk', '-m', '256M',
               '-global', 'imx6ul-lcdif.prime-g2-panel=on',
               '-global', 'prime-g2-pf1550.external-power=on',
               '-kernel', str(args.elf.resolve()), '-display', 'none',
               '-monitor', 'none', '-serial', f'file:{output}/serial',
               '-S', '-no-reboot', '-qmp', f'unix:{output}/qmp.sock,server=on,wait=off',
               '-qtest', f'unix:{output}/qt.sock,server=on,wait=off',
               '-qtest-log', '/dev/null']
    with (output / 'out').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        keys = monitor = None
        try:
            keys = recovery.QTest(output / 'qt.sock')
            monitor = recovery.QMP(output / 'qmp.sock')
            # Model the capability handed to native by installed U-Boot.
            keys.writel(0x80001000, 0x4255464c)
            keys.writel(0x80001004, 0xbdaab9b3)
            keys.writel(0x80001008, 1)
            monitor.execute('cont')
            time.sleep(10)
            matrix = {'apps': (4, 4), 'down': (4, 5), 'right': (7, 1),
                      'ok': (7, 0), 'back': (4, 6), 'up': (5, 4)}

            def press(name):
                row, col = matrix[name]
                for down in (True, False):
                    keys.writew(0x020b8008, row << 8 | col | (0x8000 if down else 0))
                    time.sleep(.25)

            def capture(name):
                monitor.execute('screendump', {'filename': str(output / f'{name}.ppm')})

            press('back')  # Dismiss the startup USB-power modal.
            press('apps')
            capture('home')
            for _ in range(3):
                press('down')
            for _ in range(2):
                press('right')
            press('ok')
            capture('settings')
            for _ in range(12):
                press('down')
            press('ok')
            capture('about')
            for _ in range(12):
                press('down')
            press('up')  # Recovery is immediately above Contributors.
            capture('recovery-row')
            press('ok')
            capture('confirmation')
            press('ok')  # Cancel is selected by default.
            capture('cancelled')
            assert process.poll() is None
            assert (output / 'confirmation.ppm').read_bytes() != (output / 'cancelled.ppm').read_bytes()
            press('ok')
            press('right')
            # Confirm resets immediately; do not send key-up to the stopped VM.
            keys.writew(0x020b8008, 0x8700)
            process.wait(timeout=10)
            assert process.returncode == 0
            print(json.dumps({'status': 'passed',
                              'scope': 'KPP Settings confirmation, cancel, and automatic reset'}))
        finally:
            if keys:
                keys.close()
            if monitor:
                monitor.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()

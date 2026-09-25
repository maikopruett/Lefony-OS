#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Execute compiled U-Boot twice: requested SDP, then normal NAND after RESET.

Blank model NAND cannot demonstrate a physical native boot. This test checks
consumption/reset routing and USB enumeration, never claims flash qualification.
"""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from prime_usb_host import PrimeUSBHost
r = importlib.import_module('test-prime-g2-rom-recovery')
qmp = importlib.import_module('test-native-uboot-recovery').qmp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uboot', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='lfubreset-', dir='/tmp') as folder:
        root = Path(folder)
        cmd = [str(r.QEMU), '-machine', 'hp-prime-g2', '-global', 'prime-g2-mmdc.preinitialized=on',
               '-device', f'loader,file={args.uboot.resolve()},addr=0x87800000,force-raw=on,cpu-num=0',
               '-display', 'none', '-serial', f'file:{root}/serial', '-monitor', 'none', '-S',
               '-qmp', f'unix:{root}/qmp,server=on,wait=off', '-qtest', f'unix:{root}/qt,server=on,wait=off',
               '-qtest-log', '/dev/null', '-chardev', f'socket,id=usb,path={root}/usb,server=on,wait=off',
               '-global', 'prime-g2-usbotg-device.chardev=usb']
        with (root/'stderr').open('w') as err:
            proc = subprocess.Popen(cmd, stdout=err, stderr=err)
            q = host = conn = stream = None
            try:
                q = r.QTest(root/'qt'); conn, stream, command = qmp(root/'qmp')
                q.writel(0x020cc068, 0x3153464c)
                command('cont')
                def wait_for(text):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        log = (root/'serial').read_text(errors='replace')
                        if text in log: return log
                        time.sleep(.05)
                    raise AssertionError(log)
                wait_for('SDP: initialize')
                assert q.readl(0x020cc068) == 0
                assert q.readl(0x80001000) == 0
                host = PrimeUSBHost(root/'usb')
                dev, _ = host.connect_and_enumerate()
                assert dev[8:12] == bytes.fromhex('feca5350')
                command('system_reset')
                log = wait_for('NAND read: device 0 offset 0x400000')
                assert log.count('consumed one-shot SDP request') == 1
                assert q.readl(0x020cc068) == 0
                assert q.readl(0x80001000) == 0x4255464c
                print(json.dumps({'status':'passed', 'scope':'actual U-Boot SDP then normal NAND path on reset', 'serial':log}))
            finally:
                if host: host.close()
                if q: q.close()
                if stream: stream.close()
                if conn: conn.close()
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


if __name__ == '__main__': main()

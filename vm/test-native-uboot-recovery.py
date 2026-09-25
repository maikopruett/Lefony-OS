#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test native action gates and real compiled U-Boot's one-shot SDP consumption."""
import argparse
import importlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

from prime_usb_host import PrimeUSBHost, ion_crc32, USBError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prime_g2_uboot_recovery import ram_capsule
r = importlib.import_module('test-prime-g2-rom-recovery')


def qmp(path):
    s = socket.socket(socket.AF_UNIX); s.settimeout(10); s.connect(str(path))
    f = s.makefile('rwb', buffering=0); f.readline()
    def command(name):
        f.write(json.dumps({'execute': name}).encode() + b'\n')
        while True:
            reply = json.loads(f.readline())
            if 'return' in reply: return reply['return']
            if 'error' in reply: raise RuntimeError(reply)
    command('qmp_capabilities')
    return s, f, command


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--elf', required=True, type=Path)
    p.add_argument('--uboot', required=True, type=Path)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='lfub-', dir='/tmp') as folder:
        root = Path(folder)
        cmd = [str(r.QEMU), '-machine', 'hp-prime-g2',
               '-global', 'prime-g2-mmdc.preinitialized=on',
               '-kernel', str(args.elf.resolve()), '-display', 'none',
               '-serial', f'file:{root}/serial', '-monitor', 'none',
               '-watchdog-action', 'reset', '-S',
               '-qmp', f'unix:{root}/qmp,server=on,wait=off',
               '-qtest', f'unix:{root}/qt,server=on,wait=off', '-qtest-log', '/dev/null',
               '-chardev', f'socket,id=usb,path={root}/usb,server=on,wait=off',
               '-global', 'prime-g2-usbotg-device.chardev=usb']
        with (root/'stderr').open('w') as err:
            proc = subprocess.Popen(cmd, stdout=err, stderr=err)
            host = q = connection = stream = None
            try:
                q = r.QTest(root/'qt')
                connection, stream, command = qmp(root/'qmp')
                # Actual retained SNVS word; malformed token must survive native init.
                q.writel(0x020cc068, 0x12345678)
                assert q.readl(0x020cc068) == 0x12345678
                command('cont')
                host = PrimeUSBHost(root/'usb')
                device, _ = host.connect_and_enumerate()
                assert device[8:12] == bytes.fromhex('feca5250')
                time.sleep(15) # permit normal app storage initialization to settle
                flags = struct.unpack('<4I', host.control_in(0xc0, 0x4e, length=16))[2]
                assert flags & 8 and not flags & 4
                def rejected(request, crc):
                    try: host.control_out(0x40, request, value=crc & 0xffff, index=crc >> 16)
                    except USBError: pass
                    else: raise AssertionError(f'unsafe request {request:x} accepted')
                    host.control_in(0xc0, 0x4e, length=16) # EP0 recovers after STALL
                rejected(0x5d, 0) # no verified staging
                bad = bytearray(4096)
                struct.pack_into('<I', bad, 0x24, 0x016f2818)
                struct.pack_into('<I', bad, 0x2c, len(bad))
                crc = ion_crc32(bad); host.stage_capsule(bytes(bad), crc)
                rejected(0x5d, crc) # ordinary OS image cannot be RAM-launched
                rejected(0x5c, crc) # old bootloader has no capability
                image = ram_capsule(args.uboot.read_bytes())
                crc = ion_crc32(image); host.stage_capsule(image, crc)
                rejected(0x5d, crc ^ 1)
                rejected(0x53, crc) # RAM wrapper cannot be installed to NAND
                q.writel(0x020cc068, 0x4b4f464c) # pending signed boot confirmation
                rejected(0x5d, crc)
                assert q.readl(0x020cc068) == 0x4b4f464c
                q.writel(0x020cc068, 0)
                before = [q.readl(x) for x in (r.NAND_OVERLAY_PAGES, r.NAND_ECC_WRITES)]
                host.control_out(0x40, 0x5d, value=crc & 0xffff, index=crc >> 16)
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    serial = (root/'serial').read_text(errors='replace')
                    if 'SDP: initialize' in serial: break
                    time.sleep(.1)
                else: raise AssertionError(f'RAM U-Boot never reached SDP:\n{serial}')
                device, _ = host.connect_and_enumerate()
                assert device[8:12] == bytes.fromhex('feca5350'), device.hex()
                assert 'consumed one-shot SDP request' in serial
                assert q.readl(0x020cc068) == 0
                assert q.readl(0x80001000) == 0
                assert [q.readl(x) for x in (r.NAND_OVERLAY_PAGES, r.NAND_ECC_WRITES)] == before
                print(json.dumps({'status':'passed', 'scope':'compiled native CRC gates and RAM U-Boot one-shot consumption', 'serial':serial}))
            finally:
                if host: host.close()
                if q: q.close()
                if stream: stream.close()
                if connection: connection.close()
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


if __name__ == '__main__': main()

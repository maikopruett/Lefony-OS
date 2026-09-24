#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Black-box EP0 protocol-stall and subsequent-SETUP recovery checks.

Uses stopped QEMU, public OCRAM/registers and its cable transaction socket.
No firmware fixture, physical device or synthetic firmware responses.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
from emulator_usb import PrimeUSBHost

recovery = importlib.import_module('test-prime-g2-rom-recovery')
USB = 0x02184000
CONTROL, SETUP, PRIME, COMPLETE = USB+0x1c0, USB+0x1ac, USB+0x1b0, USB+0x1bc
RX_STALL, TX_STALL = 1, 1 << 16
QH, TD, BUFFER = 0x00910000, 0x00910800, 0x00911000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', type=Path, default=recovery.QEMU)
    parser.add_argument('--interpreter', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();args.output.mkdir(parents=True, exist_ok=False)
    report = {'status':'running', 'qemu_sha256':digest(args.qemu),
              'test_sha256':digest(Path(__file__)), 'cases':[], 'physical':'not_tested'}
    if args.interpreter:report['interpreter_sha256'] = digest(args.interpreter)
    def save():
        (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='pg2stall-') as folder:
            folder = Path(folder);qt, us = folder/'qt', folder/'usb'
            command = ([str(args.interpreter)] if args.interpreter else []) + [str(args.qemu),
                '-machine', 'hp-prime-g2', '-S', '-display', 'none', '-serial', 'none', '-monitor', 'none',
                '-qtest', f'unix:{qt},server=on,wait=off', '-qtest-log', '/dev/null',
                '-chardev', f'socket,id=host,path={us},server=on,wait=off',
                '-global', 'prime-g2-usbotg-device.chardev=host']
            with (args.output/'qemu.stderr').open('wb') as stderr:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stderr)
                q = host = None
                try:
                    q = recovery.QTest(qt);q.socket.settimeout(3)
                    host = PrimeUSBHost(us, timeout=3)
                    assert host.command('CONNECT')=='OK'
                    q.writel(USB+0x140, 1);q.writel(USB+0x158, QH)
                    def write(address, data):q.command(f'write 0x{address:x} {len(data)} 0x{data.hex()}')
                    def case(name):
                        report['cases'].append(name);save();print('PASS: '+name, flush=True)
                    assert host.command('IN 0')=='NAK' and host.command('OUT -')=='NAK'
                    q.writel(CONTROL, TX_STALL)
                    assert host.command('IN 0')=='STALL', 'Unprimed IN stall became NAK'
                    assert host.command('OUT -')=='NAK', 'IN stall affected OUT'
                    q.writel(CONTROL, RX_STALL)
                    assert host.command('OUT -')=='STALL', 'Unprimed OUT stall became NAK'
                    assert host.command('IN 0')=='NAK', 'OUT stall affected IN'
                    case('Direction-specific stalls without primed descriptors')
                    for direction, stall in ((0, RX_STALL), (1, TX_STALL)):
                        write(BUFFER, b'abcd')
                        write(QH+64*direction+8, struct.pack('<I', TD))
                        token = (4 << 16) | 0x80
                        write(TD, struct.pack('<8I', 1, token, BUFFER, 0, 0, 0, 0, 0))
                        q.writel(COMPLETE, 0xffffffff);q.writel(PRIME, 1 << (16*direction))
                        q.writel(CONTROL, stall)
                        packet = 'IN 4' if direction else 'OUT 7778797a'
                        assert host.command(packet)=='STALL'
                        assert q.readl(TD+4)==token and q.readl(COMPLETE)==0
                        assert q.readl(BUFFER)==int.from_bytes(b'abcd', 'little')
                        q.writel(CONTROL, 0)
                        assert host.command(packet)==('DATA 61626364' if direction else 'OK')
                        assert not q.readl(TD+4)&0x80
                        assert q.readl(COMPLETE)==1 << (16*direction)
                        assert q.readl(BUFFER)==int.from_bytes(b'abcd' if direction else b'wxyz', 'little')
                    case('Stalled DMA preserves descriptors, bytes and completion; explicit clear resumes')
                    q.writel(CONTROL, RX_STALL|TX_STALL)
                    assert host.command('SETUP 00').startswith('ERR')
                    assert q.readl(CONTROL)&(RX_STALL|TX_STALL)==RX_STALL|TX_STALL
                    setup = struct.pack('<BBHHH', 0xc0, 0x78, 0, 0, 320)
                    assert host.command('SETUP '+setup.hex())=='OK'
                    assert q.readl(SETUP)==1 and not q.readl(CONTROL)&(RX_STALL|TX_STALL)
                    assert q.readl(QH+40)==int.from_bytes(setup[:4], 'little')
                    assert q.readl(QH+44)==int.from_bytes(setup[4:], 'little')
                    q.writel(SETUP, 1)
                    assert host.command('IN 0')=='NAK' and host.command('OUT -')=='NAK'
                    case('Only an accepted new SETUP clears both protocol stalls and captures its packet')
                finally:
                    if host:host.close()
                    if q:q.close()
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed', error=str(error));raise
    finally:save()


if __name__=='__main__':main()

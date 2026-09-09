#!/usr/bin/env python3
"""Rejected DCD must not copy firmware into DDR first; no physical access."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time

boot = importlib.import_module('test-prime-g2-nand-rom-boot')
recovery = importlib.import_module('test-prime-g2-rom-recovery')


def run():
    with tempfile.TemporaryDirectory(prefix='pg2ddrorder-') as temporary:
        folder = Path(temporary)
        image = boot.captured_uboot()
        address = struct.unpack_from('<I', image, 0x414)[0]
        start = address - 0x400
        dcd = struct.unpack_from('<I', image, 0x40c)[0] - start
        image[dcd] = 0  # invalid header; both copies must be rejected
        records = {}
        for page in (512, 1280):
            boot.add_image_records(records, page, image)
        overlay = folder / 'invalid-dcd.overlay'
        boot.write_overlay(overlay, records)
        qt = folder / 'qt'
        log = folder / 'rom.log'
        q = None
        with log.open('wb') as output:
            process = subprocess.Popen(boot.command(overlay) +
                ['-qtest', f'unix:{qt},server=on,wait=off', '-qtest-log', '/dev/null'],
                stdout=output, stderr=output)
            try:
                q = recovery.QTest(qt)
                deadline = time.monotonic() + 10
                while b'entering SDP' not in log.read_bytes():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError(log.read_text(errors='replace'))
                    time.sleep(0.02)
                # Open DDR before inspecting backing bytes: a blocked read
                # returning zero must not conceal a premature firmware copy.
                importlib.import_module('test-prime-g2-mmdc').initialize(q)
                value = q.readl(address)
                return {'actual': value, 'expected': 0,
                        'ivt_address': hex(address),
                        'both_copies_rejected': log.read_bytes().count(b'invalid DCD header') >= 2}
            finally:
                if q:
                    q.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    if args.audit and args.audit.exists():
        parser.error('audit exists')
    result = run()
    result.update({'passed': result['actual'] == result['expected'] and result['both_copies_rejected'],
                   'qemu_sha256': hashlib.sha256(boot.QEMU.read_bytes()).hexdigest(),
                   'physical_access': False, 'full_hardware_parity': False})
    print(result)
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(result, indent=2) + '\n')
    else:
        assert result['passed'], result


if __name__ == '__main__':
    main()

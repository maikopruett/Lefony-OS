#!/usr/bin/env python3
"""Inspect ROM-established BCH_MODE before executing any U-Boot instruction.

Fixtures are re-encoded test pages, not newly acquired physical NAND.
"""
import importlib
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from prime_nand_image import checksum, decode_fcb, encode_fcb

physical = importlib.import_module('test-prime-g2-physical-rom-boot')
boot = physical.boot
recovery = importlib.import_module('test-prime-g2-rom-recovery')


def main():
    original_nand = boot.NAND
    boot.NAND = physical.PHYSICAL
    try:
        with tempfile.TemporaryDirectory(prefix='pg2m-') as folder:
            directory = Path(folder)
            fcb, _ = decode_fcb(physical.read_record(0))

            def configured(value):
                modified = bytearray(fcb)
                struct.pack_into('<I', modified, 0x5c, value)
                struct.pack_into('<I', modified, 0, checksum(modified))
                return encode_fcb(modified)

            def inspect(name, records, expected, selected):
                overlay = physical.overlay(directory / (name + '.overlay'), records)
                sock = directory / (name + '.sock')
                qmp_sock = directory / (name + '.qmp')
                command = boot.command(overlay, qmp_path=qmp_sock)
                command.remove('-no-reboot')
                process = subprocess.Popen(command + [
                    '-S', '-global', 'prime-g2-gpmi-bch.physical-pages=on',
                    '-qtest', f'unix:{sock},server=on,wait=off',
                    '-qtest-log', '/dev/null'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                q = qmp = None
                try:
                    q = recovery.QTest(sock)
                    assert q.readl(0x01808020) == expected, name
                    assert q.readl(0x01808080) == 0x030a0880, name
                    assert q.readl(0x01808090) == 0x08170880, name
                    assert q.readl(0x01808160) == 0x01000000, name
                    qmp = recovery.QMP(qmp_sock)
                    # Deliberately poison live MODE, then reset while still
                    # halted. ROM must reapply the selected FCB on every boot.
                    q.writel(0x01808020, expected ^ 255)
                    qmp.execute('system_reset')
                    deadline = time.monotonic() + 2
                    while q.readl(0x01808020) != expected and time.monotonic() < deadline:
                        time.sleep(.01)
                    assert q.readl(0x01808020) == expected, (name, 'reset')
                finally:
                    if qmp:
                        qmp.close()
                    if q:
                        q.close()
                    output = boot.stop(process)
                assert f'selected FCB copy {selected}'.encode() in output, output
                assert b'loaded 389120 bytes from NAND page 512' in output, output
                assert b'U-Boot 2018.03' not in output, output

            for value in (0, 1, 2, 8, 255, 0x12340002):
                inspect(f'mode-{value}', {0: configured(value)}, value & 255, 0)
            # A valid FCB can fail its DBBT search; the next candidate must
            # install its own threshold rather than inherit the failed one.
            first, _ = decode_fcb(configured(8))
            first = bytearray(first)
            struct.pack_into('<I', first, 0x78, 0x3ffff)
            struct.pack_into('<I', first, 0, checksum(first))
            inspect('fallback', {0: encode_fcb(first), 64: configured(1)}, 1, 1)
            print('PASS FCB ERASE_THRESHOLD handoff, reserved-bit masking and '
                  'candidate fallback before U-Boot executes', flush=True)
    finally:
        boot.NAND = original_nand


if __name__ == '__main__':
    main()

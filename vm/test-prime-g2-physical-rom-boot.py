#!/usr/bin/env python3
"""Boot Lefony using physical codewords, including correction and fallback.

Uses the explicitly re-encoded fixture produced by prime_nand_image.py.
It does not claim that fixture is a physical raw NAND acquisition.
"""
import importlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from prime_bch import BCH
from prime_gpmi_bch import REVERSE
from prime_nand_image import decode_fcb, fcb_layout, PAGE, FCB_PAGES

boot = importlib.import_module('test-prime-g2-nand-rom-boot')
PHYSICAL = Path(os.environ.get('PRIME_G2_PHYSICAL_NAND',
    boot.ROOT / 'build/prime-g2-emulator-qualification/r36-20260907/reencoded-physical-nand.raw'))
MARKER = b'Lefony OS: entering calculator runtime'


def read_record(page):
    with PHYSICAL.open('rb') as source:
        source.seek(page * PAGE)
        data = bytearray(source.read(PAGE))
    assert len(data) == PAGE
    return data


def overlay(path, records):
    with path.open('wb') as target:
        target.write(b'PG2RAW1\n')
        for page, record in records.items():
            target.write(struct.pack('<B3xI', 1, page))
            target.write(record)
    return path


def run(directory):
    clean = overlay(directory / 'clean.overlay', {})
    result = boot.run_until(MARKER, clean, timeout=30)
    assert b'FCB BCH-40/checksum valid; corrected 0 bits' in result
    assert b'FCB configured BCH layout 030a0880/08170880' in result
    assert b'cannot support the NAND' not in result
    boot.test_visible_runtime(directory, clean, 'physical-clean')
    print('PASS complete physical-codeword cold boot and visible Lefony UI', flush=True)

    fcb, _ = decode_fcb(read_record(0))
    layout = fcb_layout(fcb)
    records = {0: read_record(0), 512: read_record(512), 2048: read_record(2048)}
    # Forty errors in the first BCH-40 FCB block, including its checksum and
    # fingerprint. One IVT error in the BCH-2 firmware and one kernel error.
    for byte in range(32, 37):
        records[0][byte] ^= 0xff
    ivt_bit = layout.chunks[2].start_bit
    records[512][ivt_bit // 8] ^= 1 << (ivt_bit % 8)
    records[2048][10] ^= 1
    damaged = overlay(directory / 'correctable.overlay', records)
    result = boot.run_until(MARKER, damaged, timeout=30)
    assert b'FCB BCH-40/checksum valid; corrected 40 bits' in result
    assert b'BCH corrected 1 bits at NAND page 512' in result
    boot.test_visible_runtime(directory, damaged, 'physical-corrected')
    print('PASS correctable FCB/IVT/kernel errors recover to visible UI', flush=True)

    # Valid BCH parity does not excuse a bad FCB checksum.
    bad_checksum = read_record(0)
    bad_checksum[32 + 12] ^= 1
    bch = BCH(13, 40, 0x201b)
    bad_checksum[160:225] = bch.encode(bytes(bad_checksum[32:160]).translate(REVERSE)).translate(REVERSE)
    result = boot.run_until(MARKER, overlay(directory / 'checksum.overlay', {0: bad_checksum}), timeout=30)
    assert b'selected FCB copy 1' in result and b'selected FCB copy 0' not in result
    print('PASS independently rejects bad FCB checksum and selects next copy', flush=True)

    uncorrectable = read_record(512)
    for byte in range(12, 16):
        uncorrectable[byte] ^= 0xff
    assert layout.decode(bytes(uncorrectable)).failed
    result = boot.run_until(MARKER, overlay(directory / 'secondary.overlay', {512: uncorrectable}), timeout=30)
    assert b'firmware 1 rejected: uncorrectable BCH in NAND firmware page 512' in result
    assert b'loaded 389120 bytes from NAND page 1280' in result
    print('PASS uncorrectable primary firmware uses redundant copy', flush=True)

    # Preserve the common reset/UI harness, but supply an empty physical
    # overlay: the base fixture already contains the repaired boot chain.
    saved = boot.bootstream_overlay
    try:
        boot.bootstream_overlay = lambda directory, safe: clean
        boot.test_recovery_exit_boots_nand(directory)
    finally:
        boot.bootstream_overlay = saved
    print('PASS physical-codeword NAND recovery exits and repeated resets', flush=True)

    # All FCB candidates uncorrectable -> ROM SDP, not a decoded-data shortcut.
    records = {}
    for page in FCB_PAGES:
        record = read_record(page)
        for byte in range(32, 48):
            record[byte] ^= 0xff
        try:
            decode_fcb(record)
        except ValueError:
            pass
        else:
            raise AssertionError('selected FCB overload unexpectedly decoded')
        records[page] = record
    bad = overlay(directory / 'all-fcb-bad.overlay', records)
    sock = directory / 'usb.sock'
    process = subprocess.Popen(boot.command(bad, sock), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with boot.PrimeUSBHost(sock) as usb:
            assert usb.command('CONNECT') == 'OK'
            deadline = time.monotonic() + 5
            status = ''
            while time.monotonic() < deadline:
                status = usb.command('STATUS')
                if 'mode=rom-sdp' in status:
                    break
                time.sleep(.01)
            assert 'mode=rom-sdp' in status and 'vid=15a2 pid=0080' in status
            device, _ = usb.connect_and_enumerate()
            assert struct.unpack_from('<HH', device, 8) == (0x15a2, 0x0080)
    finally:
        result = boot.stop(process)
    assert b'no valid i.MX6ULL NAND FCB/DBBT/IVT boot chain' in result
    assert b'U-Boot 2018.03' not in result
    print('PASS all uncorrectable FCBs fall back to enumerated ROM SDP', flush=True)


def main():
    if not PHYSICAL.is_file():
        raise SystemExit(f'Missing re-encoded physical fixture: {PHYSICAL}')
    original_command, original_nand = boot.command, boot.NAND
    boot.NAND = PHYSICAL
    boot.command = lambda *args, **kwargs: original_command(*args, **kwargs) + [
        '-global', 'prime-g2-gpmi-bch.physical-pages=on']
    try:
        with tempfile.TemporaryDirectory(prefix='pg2p-') as folder:
            run(Path(folder))
    finally:
        boot.command, boot.NAND = original_command, original_nand


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Qualify the Prime single-NAND DBBT/BBTN boot format through real QEMU."""
import importlib
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from prime_nand_image import checksum, decode_fcb, encode_fcb, fcb_layout

physical = importlib.import_module('test-prime-g2-physical-rom-boot')
boot = physical.boot


def run(directory):
    fcb, _ = decode_fcb(physical.read_record(0))
    layout = fcb_layout(fcb)

    def encode(payload):
        data, meta = layout.swap_marker(bytes(payload), b'\xff' * 10)
        return layout.encode(data, meta)

    def header(pages, reserved=0):
        payload = bytearray(2048)
        struct.pack_into('<5I', payload, 0, 0, 0x54424244, 0x01000000, reserved, pages)
        return encode(payload)

    def table(blocks, nand=0, count=None):
        payload = bytearray(2048)
        struct.pack_into('<II', payload, 0, nand, len(blocks) if count is None else count)
        for index, block in enumerate(blocks):
            struct.pack_into('<I', payload, 8 + 4 * index, block)
        return encode(payload)

    def tables(blocks):
        records = {}
        for copy in range(4):
            start = 256 + copy * 64
            records[start] = header(int(bool(blocks)))
            if blocks:
                records[start + 4] = table(blocks)
        return records

    def expect(records, name, selected=0, entries=0, skipped=0):
        path = physical.overlay(directory / (name + '.overlay'), records)
        output = boot.run_until(physical.MARKER, path, timeout=30)
        assert f'selected DBBT copy {selected} with {entries} bad-block entries'.encode() in output, output
        assert b'loaded 389120 bytes from NAND page 512' in output, output
        assert f'skipped {skipped} marked block'.encode() in output, output
        assert b'loaded 389120 bytes from NAND page 1280' not in output, output
        return path, output

    # A zero page count makes the list irrelevant. Header numberbb is reserved.
    records = tables([])
    records[256] = header(0, reserved=0xffffffff)
    records[260] = b'\xff' * 2112
    expect(records, 'empty')
    print('PASS empty DBBT ignores reserved count and absent BBTN', flush=True)

    # NXP explicitly permits unsorted lists. Exercise the entire single-page
    # capacity and the final physical block without assuming sorted entries.
    full = list(range(1508, 999, -1)) + [4095]
    assert len(full) == 510
    expect(tables(full), 'full-unsorted', entries=510)
    print('PASS full 510-entry unsorted table and final NAND block', flush=True)

    originals = [physical.read_record(512 + index) for index in range(190)]
    for bad in (8, 9):
        records = tables([bad])
        if bad == 8:
            dbbt_only_fcb = bytearray(fcb)
            struct.pack_into('<I', dbbt_only_fcb, 0xd8, 1)
            struct.pack_into('<I', dbbt_only_fcb, 0, checksum(dbbt_only_fcb))
            records[0] = encode_fcb(dbbt_only_fcb)
        # Place the same firmware stream across good blocks only. Poison the
        # listed block with valid ECC but leave its physical marker erased.
        for page in range(bad * 64, bad * 64 + 64):
            records[page] = encode(bytes(2048))
            assert records[page][2048] == 0xff
        position = 512
        for record in originals:
            if position // 64 == bad:
                position = (bad + 1) * 64
            records[position] = record
            position += 1
        path, _ = expect(records, f'listed-{bad}', entries=1, skipped=1)
        if bad == 9:
            boot.test_visible_runtime(directory, path, 'dbbt')
    print('PASS DBBT-only leading/interior bad blocks are skipped through visible UI', flush=True)

    # The physical marker check must see the overlay, not just the base image.
    records = tables([])
    for index, record in enumerate(originals):
        records[576 + index] = record
    marked = physical.read_record(512)
    marked[2048] = 0
    records[512] = marked
    expect(records, 'physical-marker', skipped=1)
    print('PASS replayed physical marker independently skips a block', flush=True)

    # DISBBSearch bypasses only physical-marker scanning. A marker bit error
    # can then be repaired by BCH; it must not be mistaken for a listed block.
    records = tables([])
    marked = physical.read_record(512)
    assert marked[2048] == 0xff
    marked[2048] ^= 1
    records[512] = marked
    modified_fcb = bytearray(fcb)
    struct.pack_into('<I', modified_fcb, 0xd8, 1)
    struct.pack_into('<I', modified_fcb, 0, checksum(modified_fcb))
    records[0] = encode_fcb(modified_fcb)
    _, result = expect(records, 'dbbt-only')
    assert b'firmware uses DBBT-only bad-block search' in result
    assert b'BCH corrected 1 bits at NAND page 512' in result
    print('PASS FCB DBBT-only mode bypasses marker scanning but retains BCH', flush=True)

    malformed = [
        ('nand', table([8], nand=1)),
        ('count', table([], count=0xffffffff)),
        # The first entry must not leak into the candidate selected later.
        ('range', table([8, 4096])),
    ]
    for name, bbtn in malformed:
        records = tables([])
        records[256], records[260] = header(1), bbtn
        expect(records, name, selected=1)
    records = tables([])
    records[256] = header(2)
    expect(records, 'page-count', selected=1)
    print('PASS malformed NAND/count/range/page-count candidates fall back without stale entries', flush=True)

    # A single BBTN count bit is corrected before the list is consumed.
    records = tables([1000])
    damaged = bytearray(records[260])
    damaged[14] ^= 1
    records[260] = damaged
    _, result = expect(records, 'corrected-table', entries=1)
    assert b'BCH corrected 1 bits at NAND page 260' in result
    records = tables([])
    damaged = bytearray(table([8]))
    for byte in range(14, 18):
        damaged[byte] ^= 0xff
    assert layout.decode(bytes(damaged)).failed
    records[256], records[260] = header(1), damaged
    expect(records, 'uncorrectable-table', selected=1)
    print('PASS BBTN BCH correction and uncorrectable-copy fallback', flush=True)

    # Every header is valid but every required list is absent. Do not treat
    # this as an empty list or boot against an old partially parsed candidate.
    records = tables([8])
    for copy in range(4):
        records[260 + copy * 64] = b'\xff' * 2112
    path = physical.overlay(directory / 'missing.overlay', records)
    sock = directory / 'usb.sock'
    process = subprocess.Popen(boot.command(path, sock), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with boot.PrimeUSBHost(sock) as usb:
            assert usb.command('CONNECT') == 'OK'
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                status = usb.command('STATUS')
                if 'mode=rom-sdp' in status:
                    break
                time.sleep(.01)
            assert 'mode=rom-sdp' in status
            device, _ = usb.connect_and_enumerate()
            assert struct.unpack_from('<HH', device, 8) == (0x15a2, 0x0080)
    finally:
        output = boot.stop(process)
    assert b'has no valid DBBT' in output and b'U-Boot 2018.03' not in output
    print('PASS all required BBTN copies missing -> enumerated ROM recovery', flush=True)


def main():
    saved_command, saved_nand = boot.command, boot.NAND
    boot.NAND = physical.PHYSICAL
    boot.command = lambda *args, **kwargs: saved_command(*args, **kwargs) + [
        '-global', 'prime-g2-gpmi-bch.physical-pages=on']
    try:
        with tempfile.TemporaryDirectory(prefix='pg2d-') as folder:
            run(Path(folder))
    finally:
        boot.command, boot.NAND = saved_command, saved_nand


if __name__ == '__main__':
    main()

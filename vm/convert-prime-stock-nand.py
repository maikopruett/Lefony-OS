#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reconstruct physical codewords from the known Linux BCH-2 raw/OOB capture.

This is an emulator fixture conversion, not a flash image generator. It retains
captured parity; it neither corrects errors nor re-encodes HP firmware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from hp_prime_stock_nand import reconstruct_physical_page, RECORD_BYTES
from prime_gpmi_bch import Layout
from prime_nand_image import checksum

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_hp_prime_compatibility import private_output


def reconstruct(record):
    """Bit-equivalent bulk form of reconstruct_physical_page's fixed geometry."""
    if len(record) != RECORD_BYTES:
        raise ValueError('expected one 2048+64-byte capture record')
    payload = record[:2048]
    oob = int.from_bytes(record[2048:], 'little')
    wire = oob & ((1 << 80) - 1)
    position = oob_position = 80
    for chunk in range(4):
        wire |= int.from_bytes(payload[chunk*512:(chunk+1)*512], 'little') << position
        position += 4096
        wire |= ((oob >> oob_position) & ((1 << 26) - 1)) << position
        position += 26
        oob_position += 26
    wire |= (oob >> oob_position) << position
    result = bytearray(wire.to_bytes(RECORD_BYTES, 'little'))
    result[0], result[2048] = result[2048], result[0]
    return bytes(result)


def convert(source, output):
    if source.stat().st_size != 0x40000 * RECORD_BYTES:
        raise ValueError('expected full 512 MiB NAND with 64-byte OOB per page')
    output = private_output(output)
    manifest = output.with_suffix(output.suffix + '.json')
    if output.exists() or manifest.exists():
        raise ValueError('output and manifest must be new')
    with source.open('rb') as capture:
        for page in (0, 64, 128, 192):
            capture.seek(page * RECORD_BYTES)
            record = capture.read(RECORD_BYTES)
            physical = reconstruct(record)
            if physical != reconstruct_physical_page(record):
                raise ValueError('capture projection self-check failed')
            fcb = Layout(0x0720a020, 0x0840a020).decode(physical)
            if (fcb.status != (0,)*8 or
                struct.unpack_from('<I', fcb.payload)[0] != checksum(fcb.payload) or
                fcb.payload[4:8] != b'FCB '):
                raise ValueError('capture does not match the known HP FCB geometry')
        capture.seek(0)
        source_hash, output_hash = hashlib.sha256(), hashlib.sha256()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as physical:
            while chunk := capture.read(RECORD_BYTES * 1024):
                source_hash.update(chunk)
                converted = b''.join(reconstruct(chunk[i:i+RECORD_BYTES])
                                     for i in range(0, len(chunk), RECORD_BYTES))
                physical.write(converted)
                output_hash.update(converted)
    manifest.write_text(json.dumps({
        'source_sha256': source_hash.hexdigest(),
        'physical_sha256': output_hash.hexdigest(),
        'representation': 'physical interleaved codewords; captured parity retained',
        'capture_geometry': 'Linux raw BCH2, metadata10, 4x512, GF13, marker swap',
        'use': 'private emulator fixture only; not a physical flashing input',
    }, indent=2)+'\n')
    return output_hash.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-linux-bch2', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(convert(args.capture_linux_bch2, args.output))


if __name__ == '__main__':
    main()

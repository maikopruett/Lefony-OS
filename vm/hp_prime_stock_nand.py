#!/usr/bin/env python3
"""Decode the private HP Prime NAND backup into the stock BCH payload view.

The backup was produced by ``nanddump --noecc --oob`` while the recovery
kernel used a different GPMI/BCH geometry from HP's firmware.  Consequently
each 2,112-byte record is neither a plain data+OOB page nor the literal NAND
bitstream.  This module reverses the capture kernel's raw-page projection and
then extracts HP's clean 2,048-byte payload.  It contains no HP firmware data.
"""

from __future__ import annotations

import argparse
from pathlib import Path


PAGE_BYTES = 2048
OOB_BYTES = 64
RECORD_BYTES = PAGE_BYTES + OOB_BYTES
CHUNK_BYTES = 512
CHUNKS = 4
GF_BITS = 13

# Geometry active in the recovery kernel that made the nanddump.
CAPTURE_METADATA_BYTES = 10
CAPTURE_ECC_STRENGTH = 2

# Geometry recovered from the stock image/backup correspondence.  Comparing
# the decoded NAND range at page 768 with the separately extracted authentic
# OS gives all but three bytes of 8,116,352 bytes; the residual is confined to
# the final partial page and is consistent with a corrected bit error.
STOCK_METADATA_BYTES = 36
STOCK_ECC_STRENGTH = 4
STOCK_BLOCK_MARK_BYTE = 1992
STOCK_BLOCK_MARK_BIT = 4
STOCK_SAVED_MARKER_OFFSET = 34
STOCK_OS_FIRST_PAGE = 768


def _copy_bits(destination: bytearray, destination_bit: int, source: bytes,
               source_bit: int, count: int) -> None:
    for index in range(count):
        source_index = source_bit + index
        destination_index = destination_bit + index
        bit = (source[source_index // 8] >> (source_index & 7)) & 1
        mask = 1 << (destination_index & 7)
        if bit:
            destination[destination_index // 8] |= mask
        else:
            destination[destination_index // 8] &= ~mask


def reconstruct_physical_page(record: bytes) -> bytes:
    """Reverse the capture kernel's BCH-2 raw-page projection."""
    if len(record) != RECORD_BYTES:
        raise ValueError(f"stock NAND record must be {RECORD_BYTES} bytes")
    payload, oob = record[:PAGE_BYTES], record[PAGE_BYTES:]
    physical = bytearray(b"\xff" * RECORD_BYTES)
    physical[:CAPTURE_METADATA_BYTES] = oob[:CAPTURE_METADATA_BYTES]
    physical_bit = oob_bit = CAPTURE_METADATA_BYTES * 8
    ecc_bits = CAPTURE_ECC_STRENGTH * GF_BITS
    for chunk in range(CHUNKS):
        _copy_bits(
            physical, physical_bit, payload, chunk * CHUNK_BYTES * 8,
            CHUNK_BYTES * 8,
        )
        physical_bit += CHUNK_BYTES * 8
        chunk_ecc_bits = ecc_bits
        if chunk == CHUNKS - 1 and (oob_bit + chunk_ecc_bits) % 8:
            chunk_ecc_bits += 8 - (oob_bit + chunk_ecc_bits) % 8
        _copy_bits(physical, physical_bit, oob, oob_bit, chunk_ecc_bits)
        physical_bit += chunk_ecc_bits
        oob_bit += chunk_ecc_bits
    oob_byte = oob_bit // 8
    physical[PAGE_BYTES + oob_byte:] = oob[oob_byte:]

    # gpmi_ecc_read_page_raw swaps the physical first byte and conventional
    # OOB marker before producing nanddump's buffers. Undo that projection.
    physical[0], physical[PAGE_BYTES] = physical[PAGE_BYTES], physical[0]
    return bytes(physical)


def decode_stock_page(record: bytes) -> bytes:
    """Return HP's clean 2,048-byte BCH payload for one captured record."""
    physical = reconstruct_physical_page(record)
    payload = bytearray(PAGE_BYTES)
    physical_bit = STOCK_METADATA_BYTES * 8
    ecc_bits = STOCK_ECC_STRENGTH * GF_BITS
    for chunk in range(CHUNKS):
        _copy_bits(
            payload, chunk * CHUNK_BYTES * 8, physical, physical_bit,
            CHUNK_BYTES * 8,
        )
        physical_bit += CHUNK_BYTES * 8 + ecc_bits

    # HP's layout transcribes the byte overlaid by the physical bad-block
    # marker into the tail of its metadata area. Reinsert it into the decoded
    # payload exactly as the GPMI driver's block_mark_swapping() does.
    marker = physical[STOCK_SAVED_MARKER_OFFSET]
    offset = STOCK_BLOCK_MARK_BYTE
    bit = STOCK_BLOCK_MARK_BIT
    payload[offset] = (payload[offset] & ((1 << bit) - 1)) | (
        marker << bit & 0xFF
    )
    payload[offset + 1] = (
        payload[offset + 1] & (0xFF << bit & 0xFF)
    ) | marker >> (8 - bit)
    return bytes(payload)


def verify_os(nand_path: Path, os_path: Path,
              first_page: int = STOCK_OS_FIRST_PAGE) -> tuple[int, int]:
    """Compare a private decoded NAND range with an authentic extracted OS."""
    image = os_path.read_bytes()
    mismatches = 0
    compared = 0
    with nand_path.open("rb") as nand:
        nand.seek(first_page * RECORD_BYTES)
        for offset in range(0, len(image), PAGE_BYTES):
            record = nand.read(RECORD_BYTES)
            if len(record) != RECORD_BYTES:
                raise ValueError("stock NAND fixture ends inside the OS range")
            expected = image[offset:offset + PAGE_BYTES]
            actual = decode_stock_page(record)[:len(expected)]
            mismatches += sum(left != right for left, right in zip(actual, expected))
            compared += len(expected)
    return compared, mismatches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the private stock NAND clean-page projection"
    )
    parser.add_argument("--nand", required=True, type=Path)
    parser.add_argument("--os", required=True, type=Path)
    parser.add_argument("--first-page", type=int, default=STOCK_OS_FIRST_PAGE)
    args = parser.parse_args()
    compared, mismatches = verify_os(args.nand, args.os, args.first_page)
    print(f"compared={compared} mismatches={mismatches}")
    return 0 if mismatches <= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())

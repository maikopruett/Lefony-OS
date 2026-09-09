#!/usr/bin/env python3
"""Construct the stock HP link command that enters maintenance mode.

This module intentionally contains no physical USB transport.  It is an
emulator/research fixture for the normal-mode packet observed in HP's desktop
software.  Sending it to real hardware is deferred until the stock updater's
authorization and complete NAND write set are understood.
"""

from __future__ import annotations

import argparse


RESET_COMMAND = 0xE8
RESET_SOFT_REBOOT = 0
RESET_FACTORY = 1
RESET_FACTORY_CLEAR = 2
RESET_START_UPDATER = 3
RESET_MODES = range(4)
FILE_HEADER_BYTES = 10
HID_REPORT_BYTES = 64


def stock_reset_packet(protocol_version: int, mode: int) -> bytes:
    """Return the 11-byte inner HP file/reset packet.

    The packet layout is the one produced by ``TFilePacket::GetMemoryFor``:
    command, protocol version, a big-endian payload-area size, item/name
    lengths, a zero CRC field, and the one-byte reset mode.  HP's reset path
    deliberately leaves this packet's CRC field zero.
    """
    if not 0 <= protocol_version <= 0xFF:
        raise ValueError("protocol version must fit in one byte")
    if mode not in RESET_MODES:
        raise ValueError("stock reset mode must be in range 0..3")
    # Four bytes of item/name/CRC bookkeeping plus one payload byte.
    body_size = 5
    return bytes((
        RESET_COMMAND,
        protocol_version,
        0,
        0,
        0,
        body_size,
        0,  # item count/type
        0,  # UTF-16 name length
        0,
        0,  # CRC intentionally zero for this command
        mode,
    ))


def stock_reset_hid_report(
    protocol_version: int,
    mode: int = RESET_START_UPDATER,
    sequence: int = 0,
    report_bytes: int = HID_REPORT_BYTES,
) -> bytes:
    """Wrap one reset packet in the normal-mode HID report payload."""
    if not 0 <= sequence <= 0xFE:
        raise ValueError("HID sequence must be in range 0..254")
    packet = stock_reset_packet(protocol_version, mode)
    if report_bytes < len(packet) + 1:
        raise ValueError("HID report is too small for reset packet")
    return bytes((sequence,)) + packet + bytes(report_bytes - len(packet) - 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print an emulator-only HP maintenance-transition report"
    )
    parser.add_argument("--protocol-version", type=int, required=True)
    parser.add_argument("--sequence", type=int, default=0)
    args = parser.parse_args()
    print(stock_reset_hid_report(args.protocol_version, sequence=args.sequence).hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

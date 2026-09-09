#!/usr/bin/env python3
"""Fuzz the native storage record validator through the VM control UART."""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
from pathlib import Path

CONTROL_PATH = Path(__file__).resolve().with_name("prime-control.py")
CONTROL_SPEC = importlib.util.spec_from_file_location("prime_control", CONTROL_PATH)
assert CONTROL_SPEC is not None and CONTROL_SPEC.loader is not None
CONTROL = importlib.util.module_from_spec(CONTROL_SPEC)
CONTROL_SPEC.loader.exec_module(CONTROL)
send_command = CONTROL.send_command


PAYLOAD_SIZE = 64_400
MAX_RECORDS = 1_024
MAX_NAME_LENGTH = 255


def expected_valid(prefix: bytes) -> bool:
    payload = prefix + bytes(PAYLOAD_SIZE - len(prefix))
    offset = 0
    records = 0
    while offset + 2 <= PAYLOAD_SIZE:
        size = int.from_bytes(payload[offset : offset + 2], "little")
        if size == 0:
            return True
        records += 1
        if (
            records > MAX_RECORDS
            or size < 4
            or size > PAYLOAD_SIZE - offset
            or PAYLOAD_SIZE - offset - size < 2
        ):
            return False
        body = payload[offset + 2 : offset + size]
        nul = body.find(0)
        if nul < 0 or nul > MAX_NAME_LENGTH or body[:nul].count(b".") != 1:
            return False
        offset += size
    return False


def record(name: bytes, data: bytes = b"") -> bytes:
    size = 2 + len(name) + 1 + len(data)
    return size.to_bytes(2, "little") + name + b"\0" + data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=512)
    args = parser.parse_args()

    cases = [
        b"",
        b"\0",
        b"\0\0",
        record(b"a.bin") + b"\0\0",
        record(b"a.bin", b"payload") + b"\0\0",
        record(b"a.bin") + record(b"b.py") + b"\0\0",
        record(b"nodot") + b"\0\0",
        record(b"two.dots.bin") + b"\0\0",
        b"\x03\x00a",
        b"\xff\xff",
        b"\x20\x00unterminated-name",
    ]
    rng = random.Random(0x4D414841)
    for _ in range(args.cases):
        size = rng.randrange(0, 33)
        cases.append(bytes(rng.randrange(256) for _ in range(size)))

    for index, candidate in enumerate(cases):
        expected = "VALID" if expected_valid(candidate) else "INVALID"
        actual = send_command(
            args.socket, f"STORAGE VALIDATE {candidate.hex()}", timeout=5.0
        )
        if actual != expected:
            print(
                f"case {index} mismatch: {candidate.hex()} expected {expected}, got {actual}",
                file=sys.stderr,
            )
            return 1
    print(f"PASS: {len(cases)} malformed storage payload cases matched the validator model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

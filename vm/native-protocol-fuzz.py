#!/usr/bin/env python3
"""Deterministically fuzz the native control parser and verify recovery."""

from __future__ import annotations

import argparse
import importlib.util
import random
import string
from pathlib import Path


CONTROL_PATH = Path(__file__).resolve().with_name("prime-control.py")
SPEC = importlib.util.spec_from_file_location("prime_control", CONTROL_PATH)
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=512)
    args = parser.parse_args()
    rng = random.Random(0x50524F544F434F4C)
    alphabet = string.ascii_letters + string.digits + " +-_/.:"
    seeds = [
        "", "V1", "V1 -1 PING", "V1 4294967296 PING", "V1 1", "KEY",
        "KEY 1", "KEY 1 2 trailing", "TEXT", "TEXT 0", "TEXT gg",
        "TIME ADVANCE -1", "TOUCH FAULT 999", "STORAGE PUT", "A" * 512,
    ]
    cases = list(seeds)
    for _ in range(args.cases):
        length = rng.randrange(0, 192)
        value = "".join(rng.choice(alphabet) for _ in range(length))
        if rng.randrange(3) == 0:
            value = f"V1 {rng.randrange(2**32)} {value}"
        cases.append(value)

    for index, candidate in enumerate(cases):
        response = CONTROL.send_command(args.socket, candidate, timeout=2.0)
        if len(response) > 256 or "\x00" in response:
            raise AssertionError(f"case {index} produced invalid response {response!r}")
        if index % 64 == 0:
            if CONTROL.send_command(args.socket, "PING", timeout=2.0) != "PONG":
                raise AssertionError(f"parser did not recover after case {index}")
    if CONTROL.send_command(args.socket, "V1 77 PING") != "V1 77 PONG":
        raise AssertionError("versioned protocol failed after fuzz corpus")
    print(f"PASS: {len(cases)} deterministic control-parser cases remained bounded and recoverable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

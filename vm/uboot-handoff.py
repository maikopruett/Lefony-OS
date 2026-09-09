#!/usr/bin/env python3
"""Interrupt U-Boot autoboot and hand control to the preloaded native ELF."""

from __future__ import annotations

import argparse
import socket
import sys
import time
from pathlib import Path


def connect(path: Path, deadline: float) -> socket.socket:
    while time.monotonic() < deadline:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(str(path))
            client.settimeout(0.25)
            return client
        except OSError:
            client.close()
            time.sleep(0.05)
    raise TimeoutError(f"U-Boot console did not appear at {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path)
    parser.add_argument("--entry", default="82000020")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    client = connect(args.socket, deadline)
    received = bytearray()
    interrupted = False
    handed_off = False
    try:
        while time.monotonic() < deadline:
            try:
                chunk = client.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            received.extend(chunk)
            tail = bytes(received[-8192:])
            if not interrupted and b"Hit any key to stop autoboot" in tail:
                client.sendall(b"\n")
                interrupted = True
            if not handed_off and (tail.endswith(b"=> ") or b"\r\n=> " in tail):
                client.sendall(f"go {args.entry}\n".encode())
                handed_off = True
            if b"Lefony OS: entering calculator runtime" in tail:
                return 0
    finally:
        client.close()

    sys.stderr.buffer.write(received[-4096:])
    if not handed_off:
        raise TimeoutError("U-Boot prompt was not reached")
    raise TimeoutError("native Upsilon did not acknowledge the U-Boot handoff")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TimeoutError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)

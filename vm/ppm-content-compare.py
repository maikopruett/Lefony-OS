#!/usr/bin/env python3
"""Compare P6 screenshots while ignoring explicitly dynamic display rows."""

from __future__ import annotations

import argparse
from pathlib import Path


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    tokens: list[bytes] = []
    offset = 0
    while len(tokens) < 4:
        while offset < len(data) and data[offset] in b" \t\r\n":
            offset += 1
        if offset < len(data) and data[offset] == ord("#"):
            offset = data.find(b"\n", offset) + 1
            if offset == 0:
                raise ValueError(f"unterminated comment in {path}")
            continue
        end = offset
        while end < len(data) and data[end] not in b" \t\r\n":
            end += 1
        tokens.append(data[offset:end])
        offset = end
    if tokens[0] != b"P6" or tokens[3] != b"255":
        raise ValueError(f"unsupported PPM format in {path}")
    width, height = int(tokens[1]), int(tokens[2])
    while offset < len(data) and data[offset] in b" \t\r\n":
        offset += 1
    pixels = data[offset:]
    if len(pixels) != width * height * 3:
        raise ValueError(f"invalid pixel length in {path}")
    return width, height, pixels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--ignore-top", type=int, default=18)
    args = parser.parse_args()
    aw, ah, ap = read_ppm(args.first)
    bw, bh, bp = read_ppm(args.second)
    if (aw, ah) != (bw, bh):
        return 1
    start = max(0, min(ah, args.ignore_top)) * aw * 3
    return 0 if ap[start:] == bp[start:] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate geometry, panel state, and required colors in a PPM screenshot."""

from __future__ import annotations

import argparse
from pathlib import Path


def ppm_tokens(data: bytes):
    offset = 0
    while offset < len(data):
        while offset < len(data) and data[offset] in b" \t\r\n":
            offset += 1
        if offset < len(data) and data[offset] == ord("#"):
            while offset < len(data) and data[offset] not in b"\r\n":
                offset += 1
            continue
        start = offset
        while offset < len(data) and data[offset] not in b" \t\r\n":
            offset += 1
        if start != offset:
            yield data[start:offset], offset


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    tokens = ppm_tokens(data)
    magic, _ = next(tokens)
    width_token, _ = next(tokens)
    height_token, _ = next(tokens)
    maximum_token, header_end = next(tokens)
    if magic != b"P6" or maximum_token != b"255":
        raise ValueError("expected an 8-bit binary P6 PPM")
    pixel_start = header_end
    while pixel_start < len(data) and data[pixel_start] in b" \t\r\n":
        pixel_start += 1
    width = int(width_token)
    height = int(height_token)
    pixels = data[pixel_start:]
    expected = width * height * 3
    if len(pixels) != expected:
        raise ValueError(f"expected {expected} pixel bytes, found {len(pixels)}")
    return width, height, pixels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect", choices=("black", "white", "visible"),
                        required=True)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument(
        "--require-color",
        action="append",
        default=[],
        metavar="RRGGBB:COUNT",
        help="require at least COUNT pixels near the hexadecimal RGB color",
    )
    parser.add_argument(
        "--color-tolerance",
        type=int,
        default=0,
        help="maximum allowed difference per RGB component",
    )
    args = parser.parse_args()

    width, height, pixels = read_ppm(args.path)
    if (width, height) != (args.width, args.height):
        raise SystemExit(
            f"wrong geometry: expected {args.width}x{args.height}, "
            f"found {width}x{height}"
        )
    is_black = not any(pixels)
    is_white = all(component == 0xff for component in pixels)
    if args.expect == "black" and not is_black:
        raise SystemExit("expected a completely black panel, but pixels were visible")
    if args.expect == "white" and not is_white:
        raise SystemExit("expected a completely white panel")
    if args.expect == "visible" and (is_black or is_white):
        raise SystemExit("expected rendered panel pixels, but output was solid")
    if not 0 <= args.color_tolerance <= 255:
        raise SystemExit("color tolerance must be between 0 and 255")
    for requirement in args.require_color:
        try:
            color_text, count_text = requirement.split(":", 1)
            if len(color_text) != 6:
                raise ValueError
            target = tuple(
                int(color_text[index:index + 2], 16) for index in (0, 2, 4)
            )
            minimum = int(count_text)
            if minimum < 1:
                raise ValueError
        except ValueError:
            raise SystemExit(
                f"invalid required color {requirement!r}; expected RRGGBB:COUNT"
            )
        matches = sum(
            1
            for offset in range(0, len(pixels), 3)
            if all(
                abs(pixels[offset + component] - target[component])
                <= args.color_tolerance
                for component in range(3)
            )
        )
        if matches < minimum:
            raise SystemExit(
                f"required at least {minimum} pixels near #{color_text}, "
                f"found {matches}"
            )
    print(f"{width}x{height} {args.expect}: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read app startup timing; never launches an app, sends input or writes NAND."""
import argparse
import json
from pathlib import Path
import struct
from prime_g2_usb_diag import LibUSB


def decode(data):
    if len(data) != 64:
        raise ValueError('Incomplete app runtime report')
    v = struct.unpack('<16I', data)
    if v[:3] != (0x5452464c, 1, 64) or v[3] & ~15 or any(v[13:]):
        raise ValueError('Unsupported app runtime report')
    return dict(zip(('magic', 'version', 'bytes', 'flags', 'started_ms', 'now_ms',
                     'first_pixels_ms', 'startup_ms', 'pixel_frames', 'surface_frames',
                     'heap_setup_ms', 'fault', 'exit_status'), v[:13]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with LibUSB() as device:
        result = decode(device.read(0x57, length=64))
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()

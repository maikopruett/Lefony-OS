#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a non-installable RAM U-Boot wrapper or request one-shot U-Boot SDP."""
from pathlib import Path
import argparse
import json
import struct
import prime_g2_usb_diag as usb


def ram_capsule(payload: bytes) -> bytes:
    if not 0x100 <= len(payload) <= 0xff000 or struct.unpack_from('<I', payload)[0] & 0xff000000 != 0xea000000:
        raise ValueError('expected the pinned Prime U-Boot ARM binary (with DTB), under 1 MiB')
    image = bytearray(0x1000 + len(payload))
    struct.pack_into('<4I', image, 0, 0x3155424c, 1, 0x87800000, len(payload))
    struct.pack_into('<3I', image, 0x24, 0x016f2818, 0, len(image))
    image[0x1000:] = payload
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    make = sub.add_parser('wrap', help='create the RAM-only wrapper; never flash it')
    make.add_argument('uboot', type=Path)
    make.add_argument('output', type=Path)
    ram = sub.add_parser('ram-test', help='stage and execute U-Boot in RAM; no NAND write')
    ram.add_argument('capsule', type=Path)
    sub.add_parser('once', help='request installed U-Boot SDP once; next RESET boots normally')
    sub.add_parser('status')
    args = parser.parse_args()
    if args.action == 'wrap':
        args.output.write_bytes(ram_capsule(args.uboot.read_bytes()))
        return
    with usb.LibUSB() as device:
        device.bulk_upload = None  # macOS EP0 bootstrap also works without bulk claim
        cap = usb.development_capabilities(device)
        if args.action == 'status':
            data = device.read(0x4e, value=3, length=32)
            if len(data) not in (16, 32):
                raise usb.USBError('invalid U-Boot diagnostics length')
            values = struct.unpack('<' + 'I' * (len(data) // 4), data)
            if values[:2] != (0x3142554c, 1):
                raise usb.USBError('unsupported U-Boot diagnostics')
            fields = ('magic', 'version', 'bootloader_version', 'mailbox',
                      'snvs_hplr', 'snvs_lplr', 'snvs_hpcomr', 'snvs_lpsr')
            print(json.dumps({'capabilities': cap, 'bootloader': dict(zip(fields, values))}))
            return
        if args.action == 'ram-test':
            if not cap['flags'] & 8:
                raise usb.USBError('installed firmware has no RAM bootstrap support')
            image = args.capsule.read_bytes()
            if len(image) < 0x1100 or image != ram_capsule(image[0x1000:]):
                raise ValueError('not a canonical RAM-only U-Boot wrapper')
            staged = usb.stage_capsule(device, args.capsule)
            request = 0x5d
        else:
            if not cap['flags'] & 4:
                raise usb.USBError('this boot did not pass through one-shot-capable U-Boot')
            # CRC gate is a deliberate action boundary, not a NAND operation.
            import tempfile
            with tempfile.TemporaryDirectory() as temporary:
                image = bytearray(4096)
                struct.pack_into('<I', image, 0x24, 0x016f2818)
                struct.pack_into('<I', image, 0x2c, len(image))
                path = Path(temporary) / 'request.zImage'
                path.write_bytes(image)
                staged = usb.stage_capsule(device, path)
            request = 0x5c
        print(json.dumps({'staged': staged, 'request': request}), flush=True)
        crc = staged['crc32']
        # Never retry an ambiguous handoff: inspect USB identity instead.
        device.write(request, value=crc & 0xffff, index=crc >> 16)


if __name__ == '__main__':
    main()

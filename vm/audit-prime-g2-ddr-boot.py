#!/usr/bin/env python3
"""Negative control for DDR initialization fidelity, using disposable NAND overlays.

Redirect only DCD MMDC writes into OCRAM scratch storage in BOTH boot copies.
If Lefony still boots, that is a model qualification gap, not evidence that
the physical board can boot without DDR initialization. Never flash this image.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import struct

boot = importlib.import_module('test-prime-g2-nand-rom-boot')
MARKER = b'Lefony OS: entering calculator runtime'


def bypass_mmdc(image):
    image = bytearray(image)
    ivt = 0x400
    if len(image) < ivt + 32 or image[ivt:ivt + 4] != b'\xd1\x00\x20\x40':
        raise ValueError('expected captured i.MX IVT at 0x400')
    self_address = struct.unpack_from('<I', image, ivt + 20)[0]
    dcd_address = struct.unpack_from('<I', image, ivt + 12)[0]
    offset = dcd_address - (self_address - ivt)
    if (offset < 0 or offset + 4 > len(image) or
            image[offset] != 0xd2 or image[offset + 3] != 0x40):
        raise ValueError('invalid DCD pointer/header')
    end = offset + int.from_bytes(image[offset + 1:offset + 3], 'big')
    if end > len(image) or end < offset + 4:
        raise ValueError('DCD bounds')
    cursor = offset + 4
    changes = []
    while cursor < end:
        if end - cursor < 4:
            raise ValueError('truncated DCD command')
        length = int.from_bytes(image[cursor + 1:cursor + 3], 'big')
        if (image[cursor] != 0xcc or image[cursor + 3] != 4 or
                length < 12 or (length - 4) % 8 or cursor + length > end):
            raise ValueError('unsupported DCD command')
        for at in range(cursor + 4, cursor + length, 8):
            address, value = struct.unpack_from('>II', image, at)
            if 0x021b0000 <= address < 0x021c0000:
                # One word of real OCRAM, outside the loaded U-Boot image.
                struct.pack_into('>I', image, at, 0x0093f000)
                changes.append({'offset': at, 'address': hex(address),
                                'value': hex(value), 'redirect': '0x0093f000'})
        cursor += length
    if not changes:
        raise ValueError('no MMDC initialization writes found')
    return image, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path,
                        help='new evidence directory; never a physical device')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    image = boot.captured_uboot()
    boot.patch_manufacturing_command(image, safe=True)
    original_hash = hashlib.sha256(image).hexdigest()
    if original_hash != '935a42e477b37b2988c73843218f021a243466bd9a17d05d25b18ae81fc2826e':
        raise ValueError('baseline does not match archived repaired U-Boot')
    altered, changes = bypass_mmdc(image)
    results = {}
    for name, candidate in [('baseline', image), ('dcd-mmdc-bypassed', altered)]:
        records = {}
        for page in (512, 1280):
            boot.add_image_records(records, page, candidate)
        overlay = boot.capsule_overlay(args.output, records, name + '.overlay')
        # A fixed bounded observation retains no-marker failures as evidence.
        output = boot.run_for(8, overlay)
        (args.output / (name + '.console.log')).write_bytes(output)
        reached = MARKER in output
        visible = False
        if reached:
            boot.test_visible_runtime(args.output, overlay, name)
            visible = True
        results[name] = {
            'uboot_sha256': hashlib.sha256(candidate).hexdigest(),
            'uboot_banner': b'U-Boot 2018.03' in output,
            'kernel_handoff': b'Starting kernel' in output,
            'initialization_rejected': b'MMDC DDR3 initialization incomplete before NAND load' in output,
            'runtime_marker': reached, 'visible_runtime': visible}
        print(name, results[name], flush=True)
    report = {'audit_completed': True, 'full_hardware_parity': False,
              'physical_device_accessed': False,
              'qemu_sha256': hashlib.sha256(boot.QEMU.read_bytes()).hexdigest(),
              'nand_fixture': str(boot.NAND),
              'both_firmware_copies_modified': True,
              'dcd_changes': changes, 'results': results,
              'ddr_initialization_bypass_reproduced':
                  results['baseline']['visible_runtime'] and
                  results['dcd-mmdc-bypassed']['visible_runtime'],
              'interpretation': 'A bypass boot exposes insensitivity to DCD DDR setup. Rejection demonstrates only the modeled boot boundary, not full memory-bus gating. Neither outcome identifies the physical failure or qualifies DDR training, power integrity or retention.'}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    assert results['baseline']['visible_runtime'], 'baseline failed; negative control is inconclusive'


if __name__ == '__main__':
    main()

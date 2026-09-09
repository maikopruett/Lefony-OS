#!/usr/bin/env python3
"""Read-only DCD/MMDC comparison for archived Prime U-Boot images.

A matching sequence excludes a DCD-byte difference, not a power, timing,
retention, later-code, or physical DDR fault. No device access is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

REGISTERS = {0: 'MDCTL', 4: 'MDPDC', 8: 'MDOTC', 12: 'MDCFG0',
             16: 'MDCFG1', 20: 'MDCFG2', 24: 'MDMISC', 28: 'MDSCR',
             32: 'MDREF', 44: 'MDRWD', 48: 'MDOR', 64: 'MDASP',
             0x404: 'MAPSR', 0x800: 'MPZQHWCTRL'}


def inspect(data):
    candidates = [i for i in (0, 0x400)
                  if data[i:i + 4] == b'\xd1\x00\x20\x40']
    if len(candidates) != 1:
        raise ValueError('expected exactly one IVT at offset 0 or 0x400')
    ivt = candidates[0]
    if len(data) < ivt + 32:
        raise ValueError('truncated IVT')
    dcd, boot_data, self_address = struct.unpack_from('<III', data, ivt + 12)
    boot_offset = boot_data - self_address + ivt
    extent = {'boot_data_pointer': f'0x{boot_data:08x}', 'valid_pointer': False}
    if boot_data and 0 <= boot_offset <= len(data) - 12:
        start, size, plugin = struct.unpack_from('<III', data, boot_offset)
        start_offset = start - self_address + ivt
        end_offset = start_offset + size
        extent.update(valid_pointer=True, start=f'0x{start:08x}', size=size,
                      plugin=plugin, start_file_offset=start_offset,
                      end_file_offset=end_offset,
                      bytes_beyond_artifact=max(0, end_offset - len(data)))
    offset = dcd - self_address + ivt
    if (offset < 0 or offset + 4 > len(data) or
            data[offset] != 0xd2 or data[offset + 3] != 0x40):
        raise ValueError('invalid DCD pointer/header')
    end = offset + int.from_bytes(data[offset + 1:offset + 3], 'big')
    if end > len(data) or end < offset + 4:
        raise ValueError('invalid DCD bounds')
    writes, mmdc, sequence = [], [], bytearray()
    cursor = offset + 4
    while cursor < end:
        if cursor + 4 > end:
            raise ValueError('truncated DCD command')
        length = int.from_bytes(data[cursor + 1:cursor + 3], 'big')
        if (data[cursor] != 0xcc or data[cursor + 3] != 4 or
                length < 12 or (length - 4) % 8 or cursor + length > end):
            raise ValueError('unsupported DCD command')
        for at in range(cursor + 4, cursor + length, 8):
            address, value = struct.unpack_from('>II', data, at)
            entry = {'address': f'0x{address:08x}', 'value': f'0x{value:08x}'}
            writes.append(entry)
            if 0x021b0000 <= address < 0x021c0000:
                entry = dict(entry, register=REGISTERS.get(address - 0x021b0000, 'PHY/other'))
                if address == 0x021b001c:
                    entry.update(configuration_request=bool(value & (1 << 15)),
                                 command=(value >> 4) & 7, chip_select=(value >> 3) & 1,
                                 bank=value & 7, mode_data=value >> 16)
                mmdc.append(entry)
                sequence.extend(data[at:at + 8])
        cursor += length
    first_mmdc = next((i for i, entry in enumerate(writes)
                       if 0x021b0000 <= int(entry['address'], 16) < 0x021c0000), len(writes))
    reset_writes = [dict(entry, before_first_mmdc=i < first_mmdc)
                    for i, entry in enumerate(writes)
                    if entry['address'] in ('0x020c4004', '0x020d8000')]
    return {'image_sha256': hashlib.sha256(data).hexdigest(),
            'dcd_sha256': hashlib.sha256(data[offset:end]).hexdigest(),
            'mmdc_sequence_sha256': hashlib.sha256(sequence).hexdigest(),
            'ivt_offset': ivt, 'writes': writes, 'mmdc_writes': mmdc,
            'boot_extent': extent, 'reset_clock_writes': reset_writes,
            'extent_warning': 'Artifact bounds do not establish physical NAND programming or ECC validity.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', nargs='+', type=Path)
    args = parser.parse_args()
    images, groups = {}, {}
    for path in args.images:
        result = inspect(path.read_bytes())
        name = str(path.resolve())
        images[name] = result
        groups.setdefault(result['mmdc_sequence_sha256'], []).append(name)
    print(json.dumps({'physical_access': False, 'images': images,
                      'identical_mmdc_sequence_groups': groups,
                      'warning': 'Equal initialization bytes do not prove equal physical DDR state or reset/power behavior.'}, indent=2))


if __name__ == '__main__':
    main()

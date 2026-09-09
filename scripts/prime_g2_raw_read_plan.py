#!/usr/bin/env python3
"""Build a strictly bounded, emulator-qualified ROM raw-read experiment plan.

No hardware transport is implemented here. A plan changes RAM/controller state,
not NAND contents, and requires backups plus restoration by its executor.
"""
import argparse
import json
from pathlib import Path

from analyze_prime_g2_rom_dma import analyze


def build_plan(capture):
    candidate, = analyze(capture, include_buffers=False)['candidates']
    if candidate['column'] != 0 or candidate['row_3byte'] != 1280:
        raise ValueError('Only the captured secondary boot page 1280 is qualified')
    if candidate['read_command_bytes'] != '00 00 00 00 05 00 00 00':
        raise ValueError('Unexpected NAND command/address sequence')
    registers = capture['dma_registers']
    memory = {int(item['address'], 16): int(item['value'], 16)
              for name, item in registers.items() if name.startswith('OCRAM_')}
    chain = [int(address, 16) for address in candidate['chain']]
    expected = [0x00083096, 0x00011096, 0x000010a4, 0x00000007,
                0x00006094, 0x000030b4, 0x00000048]
    if len(chain) != len(expected):
        raise ValueError('Unexpected descriptor count')
    for index, (address, command) in enumerate(zip(chain, expected)):
        if memory[address + 4] != command:
            raise ValueError('Descriptor command is outside the captured read-only template')
        if memory[address] != (chain[index + 1] if index + 1 < len(chain) else 0):
            raise ValueError('Unexpected descriptor link')
    expected_pio = {0: [0x08830008, 0, 0], 1: [0x08820001],
                    2: [0x03800000], 4: [0x01800817, 0, 0x11ff, 2071],
                    5: [0x03800000, 0, 0]}
    for index, values in expected_pio.items():
        if [memory[chain[index] + 12 + offset * 4] for offset in range(len(values))] != values:
            raise ValueError('Unexpected GPMI PIO words')
    # DMA_SENSE may branch to its BAR instead of NEXT. It must terminate,
    # never follow an unvalidated second chain or issue a flash command.
    branch = memory[chain[3] + 8]
    if [memory.get(branch + offset) for offset in (0, 4, 8)] != [0, 0x48, 1]:
        raise ValueError('Unqualified DMA_SENSE error branch')
    payload = int(candidate['payload_address'], 16)
    if payload & 3 or not 0x00900000 <= payload <= 0x00920000 - 2112:
        raise ValueError('Raw buffer outside bounded OCRAM')
    if any(payload <= address < payload + 2112 for address in memory):
        raise ValueError('Raw buffer overlaps captured descriptor/command memory')
    descriptor = chain[4]
    edits = [(descriptor + 4, 0x08403095), (descriptor + 8, payload),
             (descriptor + 12, 0x01800840), (descriptor + 20, 0)]
    return {
        'page': 1280, 'raw_bytes': 2112, 'hardware_qualified': False,
        'descriptor_edits': [{'address': address, 'before': memory[address], 'after': value}
                             for address, value in edits],
        'ram_backup_ranges': [{'address': payload, 'bytes': 2112}],
        'start_descriptor': chain[0], 'terminal_descriptor': chain[-1],
        'raw_buffer': payload,
        'nand_commands': ['READ0 0x00', 'READSTART 0x30'],
        'required_restoration': 'Restore all descriptor edits and all 2112 overwritten RAM bytes; '
                                'the prior 2048-byte payload capture is not a sufficient backup.',
        'caution': 'Emulator experiment plan only. Does not execute on hardware, program NAND, '
                   'erase NAND, download firmware or reset the calculator.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    print(json.dumps(build_plan(json.loads(args.capture.read_text())), indent=2))


if __name__ == '__main__':
    main()

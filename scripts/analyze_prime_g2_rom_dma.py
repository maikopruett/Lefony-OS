#!/usr/bin/env python3
"""Decode retained NAND read chains from a bounded read-only ROM RAM capture.

This is offline analysis, not a physical NAND reader or execution trace.
"""
import argparse
import json
import hashlib
from pathlib import Path
import struct
import sys


def analyze(capture: dict, *, include_buffers: bool = True) -> dict:
    registers = capture['dma_registers']
    current = int(registers['APBH_CH0_CURCMDAR']['value'], 16)
    if int(registers['APBH_CH0_SEMA']['value'], 16) & 0x00ff0000:
        raise ValueError('DMA channel is active; retained-chain interpretation is unsafe')
    memory = {}
    for name, item in registers.items():
        if name.startswith('OCRAM_'):
            address = int(item['address'], 16)
            if address & 3 or not 0x00900000 <= address <= 0x0091fffc:
                raise ValueError('captured word outside aligned OCRAM')
            if address in memory:
                raise ValueError('duplicate OCRAM address')
            memory[address] = int(item['value'], 16)

    def read(address, count):
        if not 0 <= count <= 4096:
            raise ValueError('unbounded buffer length')
        return bytes((memory[(address + i) & ~3] >> (((address + i) & 3) * 8)) & 255
                     for i in range(count))

    def descriptor(address):
        if address & 3:
            raise ValueError('unaligned DMA descriptor')
        next_address, command, buffer = struct.unpack('<III', read(address, 12))
        pio_count = (command >> 12) & 15
        pio = struct.unpack('<' + 'I' * pio_count, read(address + 12, pio_count * 4))
        return next_address, command, buffer, pio

    candidates = []
    for start in sorted(memory):
        try:
            nxt, command, buffer, pio = descriptor(start)
            # MEM_TO_DEV, CLE with automatic address increment, NAND READ0.
            if command & 3 != 2 or not pio or (pio[0] >> 24) & 3 != 0:
                continue
            if (pio[0] >> 17) & 3 != 1 or not pio[0] & (1 << 16):
                continue
            count = command >> 16
            if not 6 <= count <= 8 or (pio[0] & 0xffff) != count:
                continue
            wire = read(buffer, count)
            if wire[0] != 0:
                continue
            chain, seen, confirm, ecc = [], set(), False, None
            address = start
            while address and address not in seen and len(chain) < 32:
                seen.add(address)
                nxt, flags, ptr, words = descriptor(address)
                chain.append(f'0x{address:08x}')
                if flags & 3 == 2 and flags >> 16 == 1 and words:
                    confirm |= read(ptr, 1) == b'\x30' and (words[0] >> 17) & 3 == 1
                if len(words) >= 6 and (words[0] >> 24) & 3 == 1 and words[2] & 0x1000:
                    ecc = {'transfer_bytes': words[3] & 0xffff,
                           'payload_address': f'0x{words[4]:08x}',
                           'auxiliary_address': f'0x{words[5]:08x}',
                           'ecc_control': f'0x{words[2]:08x}'}
                if address == current:
                    if nxt or flags & 3 or not flags & 0x40:
                        break
                    if confirm and ecc:
                        candidates.append({
                            'start_descriptor': f'0x{start:08x}', 'chain': chain,
                            'read_command_bytes': wire.hex(' '),
                            'column': int.from_bytes(wire[1:3], 'little'),
                            'row_3byte': int.from_bytes(wire[3:6], 'little'),
                            'additional_address_bytes': wire[6:].hex(' '), **ecc})
                    break
                if not flags & 4:
                    break
                address = nxt
        except (KeyError, ValueError, struct.error):
            continue
    result = {'current_descriptor': f'0x{current:08x}',
            'semaphore': registers['APBH_CH0_SEMA']['value'],
            'candidates': candidates,
            'qualification': 'Retained descriptors, not an execution trace. Row uses the '
                             'Prime 2-column/3-row-byte convention; extra address bytes '
                             'are preserved, not silently discarded.'}
    if len(candidates) == 1:
        # Report descriptor topology separately from ECC. A retained terminal
        # is not a time-ordered trace and a zero DMA result is not proof of a
        # successfully decoded NAND page.
        branches = []
        for address_text in candidates[0]['chain']:
            address = int(address_text, 16)
            nxt, flags, ptr, words = descriptor(address)
            if flags & 3 != 3:
                continue
            branch = {'descriptor': address_text, 'normal_next': f'0x{nxt:08x}',
                      'alternate_next': f'0x{ptr:08x}', 'alternate_is_error_terminal': False}
            try:
                alt_next, alt_cmd, alt_result, alt_pio = descriptor(ptr)
                branch['alternate_is_error_terminal'] = (
                    flags == 7 and not words and alt_next == 0 and
                    alt_cmd == 0x48 and alt_result == 1 and not alt_pio)
            except (KeyError, ValueError, struct.error):
                pass
            branches.append(branch)
        nxt, flags, ptr, words = descriptor(current)
        expected = {'APBH_CH0_NXTCMDAR': nxt, 'APBH_CH0_CMD': flags,
                    'APBH_CH0_BAR': ptr}
        missing = [name for name in expected if name not in registers]
        mismatches = [name for name, value in expected.items()
                      if name in registers and int(registers[name]['value'], 16) != value]
        normal = (not missing and not mismatches and nxt == 0 and flags == 0x48
                  and ptr == 0 and not words and bool(branches)
                  and all(b['alternate_is_error_terminal'] for b in branches))
        result['retained_completion'] = {
            'consistent_with_normal_dma_terminal': normal,
            'missing_registers': missing, 'mismatched_registers': mismatches,
            'sense_branches': branches,
            'caution': 'Topology and retained register consistency only, not a trace. '
                       'DMA completion does not establish BCH success or exclude an earlier timeout.'}
    if include_buffers and len(candidates) == 1 and any(name.startswith('PAYLOAD_') for name in registers):
        def buffer(prefix, start, length):
            entries = {int(item['address'], 16): int(item['value'], 16)
                       for name, item in registers.items() if name.startswith(prefix + '_')}
            if set(entries) != set(range(start, start + length, 4)):
                raise ValueError('incomplete or unexpected retained buffer address set')
            return b''.join(struct.pack('<I', entries[address]) for address in sorted(entries))
        payload = buffer('PAYLOAD', int(candidates[0]['payload_address'], 16), 2048)
        auxiliary = buffer('AUX', int(candidates[0]['auxiliary_address'], 16), 64)
        if 'nand_registers' not in capture:
            result['retained_buffers'] = {
                'payload_sha256': hashlib.sha256(payload).hexdigest(),
                'caution': 'No captured BCH layout: chunk statuses cannot be decoded. Buffers are not raw NAND parity.'}
            return result
        layout = int(capture['nand_registers']['BCH_FLASH0LAYOUT0']['value'], 16)
        metadata, chunks = (layout >> 16) & 255, (layout >> 24) + 1
        status_offset = (metadata + 3) & ~3
        if status_offset + chunks > len(auxiliary):
            raise ValueError('status layout exceeds captured auxiliary buffer')
        result['retained_buffers'] = {
            'payload_sha256': hashlib.sha256(payload).hexdigest(),
            'chunk_status': list(auxiliary[status_offset:status_offset + chunks]),
            'caution': 'Decoded buffers may already include ROM marker fixup; not raw NAND parity.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--reference-nand', type=Path,
                        help='Compare retained payload with a physical-codeword-format reference file; this does not establish its provenance')
    args = parser.parse_args()
    result = analyze(json.loads(args.capture.read_text()))
    if args.reference_nand:
        if len(result['candidates']) != 1 or 'retained_buffers' not in result:
            raise SystemExit('Reference comparison requires one chain and complete retained buffers')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vm'))
        from prime_nand_image import decode_fcb, fcb_layout
        page = result['candidates'][0]['row_3byte']
        with args.reference_nand.open('rb') as source:
            fcb, _ = decode_fcb(source.read(2112))
            layout = fcb_layout(fcb)
            source.seek(page * 2112)
            record = source.read(2112)
        decoded = layout.decode(record)
        if decoded.failed:
            raise SystemExit('Reference page is uncorrectable')
        payload, _ = layout.swap_marker(decoded.payload, decoded.metadata)
        digest = hashlib.sha256(payload).hexdigest()
        result['reference_comparison'] = {
            'file': str(args.reference_nand.resolve()), 'page': page,
            'firmware_starts': list(struct.unpack_from('<II', fcb, 0x68)),
            'page_record_sha256': hashlib.sha256(record).hexdigest(),
            'payload_sha256_after_marker_fixup': digest,
            'payload_matches': digest == result['retained_buffers']['payload_sha256'],
            'caution': 'A reference payload match is not a raw NAND/parity match.'}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

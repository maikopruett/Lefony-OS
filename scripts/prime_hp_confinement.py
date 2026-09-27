#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact-input, emulator-first HP V15751 RAM confinement research profile.

No USB, NAND installer, firmware download or release approval. The fixed 256 MiB
split is a disposable experiment. Original images are never modified in place.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import subprocess
import tempfile

from analyze_hp_prime_compatibility import BASE, INPUTS, require, verify_input

PROFILE = 'hp-v15751-research-256-v4'
FIRST_BLOCK, LAST_BLOCK = 392, 2047
BBT_FIRST, BBT_LAST = 4, 7
GEOMETRY = (512 * 1024 * 1024, 128 * 1024, 2048, 64)
# Verified erased padding before ARM entry; outside IVT/DCD and LFUB cookie.
CAVE = 0x80000800
CAVE_BYTES = 0x800
DETAILS = {
    'HPPrime.img': {
        'end': (0x802B1ACC, 'a869401e'),
        'bbt': (0x802B192E, '2de9fc47', 'push.w {r2-r10,lr}', 0x807BDEE4),
        'bbt_callers': (0x802B19B3, 0x802B19D5, 0x802B19E9),
        'disabled': (
            ('official-update', 0x803A2680, '2de9f44f'),
            ('maintenance-reload', 0x802B0B7E, '80b5dff8002a'),
            ('factory-reset', 0x802F5580, '2de9f041'),
        ),
        'guards': (
            ('ecc-program', 0x803A1700, '2de9fe4f', 'push.w {r1-r11,lr}', True),
            ('raw-program', 0x803A185A, '2de9f041', 'push.w {r4-r8,lr}', True),
            ('erase', 0x803A1946, '7cb50400', 'push {r2-r6,lr}\nmovs r4,r0', False),
        ),
    },
    'bootloader.img': {
        'end': (0x80007CF6, '8069401e'),
        'bbt': (0x80007A40, '2de9fc41', 'push.w {r2-r8,lr}', 0x800477CC),
        'bbt_callers': (0x80007AF3, 0x80007B37, 0x80007AC3),
        'disabled': (('official-update', 0x80014A40, '2de9f64f'),),
        'guards': (
            ('ecc-program', 0x80013F24, '2de9fe4f', 'push.w {r1-r11,lr}', True),
            ('raw-program', 0x8001407E, '2de9f041', 'push.w {r4-r8,lr}', True),
            ('erase', 0x8001416A, '7cb50400', 'push {r2-r6,lr}\nmovs r4,r0', False),
        ),
    },
}


@dataclass(frozen=True)
class Patch:
    address: int
    expected: bytes
    replacement: bytes
    purpose: str


def assemble(source: str, address: int) -> bytes:
    """Use the real ARM assembler/linker; no hand-encoded branch immediates."""
    with tempfile.TemporaryDirectory(prefix='hp-profile-') as folder:
        p = Path(folder)
        (p/'patch.S').write_text('.syntax unified\n.arch armv7-a\n.thumb\n.text\n'+source+'\n')
        commands = [
            ['arm-none-eabi-as', '-o', str(p/'patch.o'), str(p/'patch.S')],
            ['arm-none-eabi-ld', '-Ttext', hex(address), '-e', hex(address),
             '-o', str(p/'patch.elf'), str(p/'patch.o')],
            ['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.text',
             str(p/'patch.elf'), str(p/'patch.bin')],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, timeout=15)
        return (p/'patch.bin').read_bytes()


def patches(name: str) -> tuple[Patch, ...]:
    require(name in DETAILS, 'unknown confinement component')
    detail = DETAILS[name]
    address, expected = detail['end']
    result = [Patch(address, bytes.fromhex(expected),
                    assemble(f'movw r0, #{LAST_BLOCK}', address), 'filesystem-inclusive-end')]
    # Both update APIs return Boolean failure (0). Maintenance is a void
    # request-and-reset helper: return before writing the reload request.
    # Filesystem and narrowly owned bad-block metadata writes are permitted;
    # firmware updates are not.
    for label, address, expected in detail['disabled']:
        body = assemble('movs r0, #0\nbx lr', address)
        body += b'\x00\xbf' * ((len(bytes.fromhex(expected))-len(body))//2)
        result.append(Patch(address, bytes.fromhex(expected), body, 'disabled-'+label))
    for index, (label, target, expected, displaced, page) in enumerate(detail['guards']):
        cave = CAVE + index * 0x100
        # Preserve all argument/callee-saved registers and stack on denial.
        # IP is caller-clobbered; original prologue executes on the allowed path.
        # Compare full unsigned page range BEFORE multiplication/truncation.
        lo = FIRST_BLOCK * (64 if page else 1)
        hi = (LAST_BLOCK+1) * (64 if page else 1)
        metadata = ''
        if label == 'ecc-program':
            metadata = f'''
                cmp r0, #{BBT_FIRST*64}
                blo denied
                cmp r0, #{(BBT_LAST+1)*64}
                bhs denied
                and ip, r0, #63
                cmp ip, #0
                beq bbt_first_page
                cmp ip, #4
                bne denied
                ldr ip, =0x{detail['bbt_callers'][1]:x}
                b bbt_caller
            bbt_first_page:
                ldr ip, =0x{detail['bbt_callers'][0]:x}
            bbt_caller:
                cmp lr, ip
                bne denied
                b allowed
            '''
        elif label == 'erase':
            metadata = f'''
                cmp r0, #{BBT_FIRST}
                blo denied
                cmp r0, #{BBT_LAST+1}
                bhs denied
                ldr ip, =0x{detail['bbt_callers'][2]:x}
                cmp lr, ip
                bne denied
                b allowed
            '''
        body = assemble(f'''
            ldr ip, =0x{lo:x}
            cmp r0, ip
            blo metadata
            ldr ip, =0x{hi:x}
            cmp r0, ip
            bhs denied
            b allowed
        metadata:
            {metadata or 'b denied'}
        allowed:
            {displaced}
            b.w 0x{target+4:x}
        denied:
            mvn r0, #1
            bx lr
            .ltorg
        ''', cave)
        require(len(body) <= 0x100, 'guard exceeds private cave slot')
        result += [Patch(cave, b'\xff'*len(body), body, label+'-guard'),
                   Patch(target, bytes.fromhex(expected), assemble(f'b.w 0x{cave:x}', target), label+'-entry')]
    target, expected, displaced, state = detail['bbt']
    cave = CAVE + 0x300
    body = assemble(f'''
        cmp r1, #{FIRST_BLOCK}
        blo denied
        cmp r1, #{LAST_BLOCK+1}
        bhs denied
        ldr ip, =0x{state:x}
        ldr ip, [ip]
        cmp ip, #0
        beq denied
        ldr ip, [ip, #0x78]
        cmp ip, #{BBT_FIRST*64}
        bne denied
        {displaced}
        b.w 0x{target+4:x}
    denied:
        movs r0, #0
        bx lr
        .ltorg
    ''', cave)
    require(len(body) <= 0x100, 'bad-block guard exceeds cave slot')
    result += [Patch(target, bytes.fromhex(expected), assemble(f'b.w 0x{cave:x}', target), 'bad-block-callback-entry'),
               Patch(cave, b'\xff'*len(body), body, 'bad-block-owner-and-metadata-location')]
    if name == 'HPPrime.img':
        # Reset dispatcher returns Boolean status. Ordinary restart remains;
        # both factory-reset modes and maintenance reload return failure.
        # Their direct helpers above are also blocked, covering other callers.
        target, cave = 0x80415AE0, CAVE + 0x400
        body = assemble(f'''
            cmp r0, #1
            blo original
            cmp r0, #3
            bls denied
        original:
            push {{r7,lr}}
            cmp r0, #3
            b.w 0x{target+4:x}
        denied:
            movs r0, #0
            bx lr
        ''', cave)
        result += [Patch(target, bytes.fromhex('80b50328'), assemble(f'b.w 0x{cave:x}',target), 'reset-dispatch-entry'),
                   Patch(cave,b'\xff'*len(body),body,'reset-policy')]
    return tuple(result)


def apply_patches(data: bytes, changes: tuple[Patch, ...]) -> bytes:
    """Validate the entire plan before changing any bytes; reject overlap/resize."""
    ranges = []
    for patch in changes:
        start = patch.address-BASE
        end = start+len(patch.expected)
        require(0 <= start < end <= len(data), 'patch outside image')
        require(len(patch.expected) == len(patch.replacement), 'patch changes image size')
        require(data[start:end] == patch.expected, 'unexpected bytes at patch site')
        require(all(end <= a or start >= b for a,b in ranges), 'overlapping patch sites')
        ranges.append((start,end))
    result = bytearray(data)
    for patch in changes:
        at = patch.address-BASE
        result[at:at+len(patch.expected)] = patch.replacement
    return bytes(result)


def patch_image(name: str, data: bytes, geometry=GEOMETRY):
    verify_input(name, data)
    require(tuple(geometry) == GEOMETRY, 'unsupported confinement geometry')
    require(data[CAVE-BASE:CAVE-BASE+CAVE_BYTES] == b'\xff'*CAVE_BYTES,
            'research code cave is not erased padding')
    changes = patches(name)
    result = apply_patches(data, changes)
    report = {'profile': PROFILE, 'component': name, 'geometry': list(GEOMETRY),
              'filesystem_blocks': [FIRST_BLOCK,LAST_BLOCK],
              'metadata_blocks': [BBT_FIRST,BBT_LAST],
              'source_sha256': INPUTS[name][1],
              'patched_sha256': hashlib.sha256(result).hexdigest(),
              'patches': [{'address': hex(p.address), 'bytes': len(p.expected),
                           'purpose': p.purpose} for p in changes],
              'scope': 'emulator-only research; no update/reload or physical qualification'}
    return result, report

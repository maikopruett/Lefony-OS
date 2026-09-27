#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restartable NAND transaction primitive for dual-layout qualification.

Offline execution is the default. Physical research requires the media
adapter's inspected, transaction-specific permit. A plan binds full before/after block
identities, a verified external recovery backup, and a transaction id. The
journal lives in two dedicated NAND blocks, outside both filesystems. A pending
record is read back before erasing its target; completion follows readback.
Boot-control ordering belongs to the separately validated migration planner.
"""
from dataclasses import dataclass
import hashlib
import json
import struct
import zlib

from prime_dual_boot_contract import (BLOCKS, ERASE, RAW_PAGE, ContractError,
                                      canonical, require, sha, load_layout)

RAW_BLOCK = RAW_PAGE * 64
JOURNAL_BLOCKS = (258, 259)


@dataclass(frozen=True)
class Change:
    block: int
    before: bytes
    after: bytes
    phase: str

    def identity(self):
        return {'block': self.block, 'before': sha(self.before).hex(),
                'after': sha(self.after).hex(), 'phase': self.phase}


class Transaction:
    """Plan storage is on the host; its hash is anchored in each NAND journal."""
    def __init__(self, changes, backup_digest, *, mode='migrate'):
        self.changes = tuple(changes)
        require(mode in ('migrate', 'add-hp', 'restore', 'repair-boot', 'refresh-dual'), 'unknown transaction mode')
        require(len(backup_digest) == 32 and backup_digest != bytes(32), 'backup identity required')
        self.backup_digest, self.mode = backup_digest, mode
        seen = set()
        allowed = {'stage-recovery': 0, 'redirect-rom': 1, 'migrate-data': 2,
                   'stage-images': 3, 'commit-layout': 4}
        restore = {'disable-boot': 0, 'restore-data': 1, 'restore-rom': 2, 'restore-cleanup': 3}
        add_hp = {'stage-recovery':0,'redirect-rom':1,'restore-hp-system':2,
                  'migrate-data':3,'stage-images':4,'commit-layout':5}
        refresh = {'redirect-rom':0, 'stage-recovery':1, 'stage-images':2, 'commit-layout':3}
        phases = (restore if mode == 'restore' else add_hp if mode == 'add-hp'
                  else refresh if mode == 'refresh-dual' else allowed)
        order = -1
        _, regions = load_layout()
        for c in self.changes:
            require(type(c.block) is int and 0 <= c.block < BLOCKS and
                    c.block not in JOURNAL_BLOCKS, 'invalid transaction target')
            require(c.block not in seen, 'block appears twice in transaction')
            seen.add(c.block)
            require(len(c.before) == len(c.after) == RAW_BLOCK, 'full raw block required')
            require(c.before != c.after, 'unchanged transaction target')
            require(c.phase in phases and phases[c.phase] >= order, 'unsafe phase ordering')
            if mode == 'repair-boot':
                require(c.phase == 'stage-recovery', 'boot repair may only replace boot streams')
            if mode == 'refresh-dual':
                permitted = {'redirect-rom': ('rom_control',),
                    'stage-recovery': ('boot_primary','boot_secondary'),
                    'stage-images': ('lefony_image','rescue'),
                    'commit-layout': ('layout_primary','layout_secondary')}[c.phase]
                require(any(regions[n].contains(c.block) for n in permitted),
                        'refresh changes preserved data')
            order = phases[c.phase]
            if mode != 'restore':
                names = {
                    'stage-recovery': ('boot_primary', 'boot_secondary'),
                    'redirect-rom': ('rom_control',),
                    'restore-hp-system': ('hp_bad_blocks','hp_system','hp_system_tail','hp_reserved'),
                    'migrate-data': ('hp_filesystem', 'lefony_apps'),
                    'stage-images': ('hp_image', 'lefony_image', 'lefony_dtb', 'rescue',
                                     'preference_primary', 'preference_secondary'),
                    'commit-layout': ('layout_primary', 'layout_secondary'),
                }[c.phase]
                require(any(regions[n].contains(c.block) for n in names), 'phase writes outside its regions')
            else:
                require((c.phase == 'restore-rom') == (c.block < 4), 'ROM restoration must be last')
                if c.phase == 'restore-cleanup':
                    require(240 <= c.block < 256, 'invalid retired-stream cleanup')
                if c.phase == 'restore-data':
                    require(not 240 <= c.block < 258, 'boot control needs an explicit restore phase')
                if c.phase == 'disable-boot':
                    require(c.block in (256, 257), 'invalid boot-disable record')
        require(self.changes, 'empty transaction')
        self.id = sha(canonical({'schema': 1, 'mode': mode,
                                 'backup': backup_digest.hex(),
                                 'changes': [c.identity() for c in self.changes]}))


def journal_page(transaction, generation, index, pending):
    require(0 < generation < 2**32 and 0 <= index <= len(transaction.changes), 'journal overflow')
    require(not pending or index < len(transaction.changes), 'invalid pending index')
    page = bytearray(b'\xff' * RAW_PAGE)
    # This primitive's backend owns ECC encoding. Only the 2 KiB payload is
    # passed to it; spare bytes are not repurposed as journal data.
    struct.pack_into('<4s4I32s', page, 0, b'LFJ5', 1, generation, index, bool(pending), transaction.id)
    struct.pack_into('<I', page, 2044, zlib.crc32(page[:2044]))
    return bytes(page[:2048])


def decode_journal(data, transaction):
    require(len(data) == 2048, 'short journal page')
    magic, schema, generation, index, pending, txid = struct.unpack_from('<4s4I32s', data)
    require((magic, schema, txid) == (b'LFJ5', 1, transaction.id), 'wrong journal transaction')
    require(0 < generation < 2**32 and 0 <= index <= len(transaction.changes) and pending in (0, 1),
            'invalid journal position')
    require(not pending or index < len(transaction.changes), 'invalid pending journal')
    require(data[52:2044] == b'\xff'*(2044-52) and
            struct.unpack_from('<I', data, 2044)[0] == zlib.crc32(data[:2044]), 'torn journal')
    return generation, index, bool(pending)


def read_transaction_state(backend, transaction):
    states, raw = [], []
    for slot in range(2):
        data = backend.read_journal(slot)
        raw.append(data)
        # A valid foreign transaction is not a torn copy. Never resume
        # against one journal while silently ignoring another owner.
        if (len(data) == 2048 and data[:8] == struct.pack('<4sI', b'LFJ5', 1)
                and struct.unpack_from('<I', data, 2044)[0] == zlib.crc32(data[:2044])):
            require(data[20:52] == transaction.id, 'foreign journal transaction')
        try:
            state = decode_journal(data, transaction)
        except ContractError:
            continue
        states.append((state[0], slot, state))
    require(states, 'no valid transaction journal; recovery backup required')
    if len(states) == 2 and states[0][0] == states[1][0]:
        require(raw[0] == raw[1], 'conflicting journal copies')
    generation, slot, (_, index, pending) = max(states)
    return generation, slot, index, pending


class Engine:
    """Backend operations must persist before returning; no successful-write assumptions.

    Default backend: kind='offline-emulator', read_block, erase_block,
    program_raw_page, read_journal, write_journal, bad_blocks, verify_backup,
    and verify_recovery_barrier. write_journal erases/replaces exactly one copy
    with the proper ECC; its peer remains intact. Each method may raise after
    modifying media, modeling lost acknowledgements as well as torn writes.
    The private physical backend replaces whole blocks through its bounded,
    verified transport; callers cannot enable it by changing a kind string.
    """
    def __init__(self, backend, transaction, *, research_authorization=None):
        if backend.kind != 'offline-emulator':
            from prime_dual_physical import PhysicalMedia
            require(type(backend) is PhysicalMedia and
                    backend.accepts_authorization(transaction, research_authorization),
                    'physical migration is not available without a reviewed research permit')
        self.backend, self.transaction = backend, transaction

    def _read_state(self):
        return read_transaction_state(self.backend, self.transaction)

    def _save(self, index, pending):
        generation, slot, _, _ = self._read_state()
        expected = journal_page(self.transaction, generation+1, index, pending)
        target = 1-slot
        self.backend.write_journal(target, expected)
        require(self.backend.read_journal(target) == expected, 'journal readback mismatch')

    def prepare(self):
        """Only a verified pristine source may initialize a new transaction."""
        self.backend.verify_backup(self.transaction.backup_digest)
        for slot in range(2):
            require(self.backend.read_journal(slot) == b'\xff'*2048, 'journal already provisioned')
        for c in self.transaction.changes:
            require(c.block not in self.backend.bad_blocks, 'plan changes a retired/factory-bad block')
            require(self.backend.read_block(c.block) == c.before, 'source does not match backup plan')
        expected = journal_page(self.transaction, 1, 0, False)
        self.backend.write_journal(0, expected)
        require(self.backend.read_journal(0) == expected, 'initial journal readback mismatch')
        self.backend.write_journal(1, expected)
        require(self.backend.read_journal(1) == expected, 'redundant initial journal readback mismatch')

    def run(self, max_changes=None):
        self.backend.verify_backup(self.transaction.backup_digest)
        _, _, index, pending = self._read_state()
        # Check every previously completed block before accepting progress.
        for c in self.transaction.changes[:index]:
            require(self.backend.read_block(c.block) == c.after, 'completed write no longer verifies')
        require(max_changes is None or type(max_changes) is int and max_changes >= 0,
                'invalid bounded transaction step')
        stop = len(self.transaction.changes) if max_changes is None else min(
            len(self.transaction.changes), index + max_changes)
        for position in range(index, stop):
            c = self.transaction.changes[position]
            require(c.block not in self.backend.bad_blocks, 'target became bad; replan required')
            if c.phase in ('restore-hp-system', 'migrate-data', 'stage-images', 'commit-layout'):
                self.backend.verify_recovery_barrier(self.transaction)
            if c.phase in ('restore-data', 'restore-rom', 'restore-cleanup'):
                self.backend.verify_restore_barrier(self.transaction, c.phase)
            current = self.backend.read_block(c.block)
            if not (position == index and pending):
                require(current == c.before, 'unexpected target mutation')
                self._save(position, True)
            # If the acknowledgement was lost, verify completed bytes and
            # advance without consuming another erase cycle.
            if current != c.after:
                if self.backend.kind == 'physical-research':
                    self.backend.replace_block(c.block,c.after)
                else:
                    self.backend.erase_block(c.block)
                    for page in range(64):
                        data = c.after[page*RAW_PAGE:(page+1)*RAW_PAGE]
                        if data != b'\xff'*RAW_PAGE:
                            self.backend.program_raw_page(c.block*64+page, data)
                require(self.backend.read_block(c.block) == c.after, 'block readback mismatch')
            self._save(position+1, False)
        # Completion is a verified journal state, not merely a returned write.
        require(self._read_state()[2:] == (stop, False), 'incomplete transaction step')
        return self.transaction.id.hex() if stop == len(self.transaction.changes) else None

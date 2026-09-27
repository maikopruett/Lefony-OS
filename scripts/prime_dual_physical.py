#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private Phase 6 NAND media adapter, with explicit transaction authorization.

This is not a public installer or a qualification flag. A retained full backup,
verified loader protocol and exact current-device fingerprint are prerequisites.
The public migration contract remains disabled. No hardware is opened on import.
"""
from pathlib import Path
import sys
import struct
import zlib

from prime_dual_boot_contract import ContractError, require, sha
from prime_hp_raw_restore import GEOMETRY, RAW_BLOCK
from prime_dual_boot_transaction import JOURNAL_BLOCKS, read_transaction_state

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT/'vm') not in sys.path:
    sys.path.insert(0, str(ROOT/'vm'))
import prime_dual_migration as model

ERASED = b'\xff' * RAW_BLOCK


class PhysicalMedia:
    kind = 'physical-research'

    def __init__(self, device, backup, backup_digest, *, event, initial=None, initial_digest=None):
        self.device = device
        self.backup = Path(backup).resolve()
        require(self.backup.is_file() and self.backup.stat().st_size == 4096*RAW_BLOCK,
                'complete external physical backup required')
        require(model.file_hash(self.backup) == backup_digest, 'backup digest mismatch')
        self.backup_digest = backup_digest
        require((initial is None) == (initial_digest is None),'initial snapshot digest required')
        self.initial = self.backup if initial is None else Path(initial).resolve()
        require(self.initial.is_file() and self.initial.stat().st_size == 4096*RAW_BLOCK and
                model.file_hash(self.initial) == (backup_digest if initial is None else initial_digest),
                'initial full snapshot mismatch')
        self.bad_blocks = model.factory_inventory(self.backup)
        self.event = event  # Must fsync before returning; failures stop execution.
        self.native = model.NativeBCH()
        self._token = None
        self._transaction = None
        self._allowed = set()
        self._known = {}
        require(model.factory_inventory(self.initial) == self.bad_blocks,
                'initial snapshot factory inventory differs from recovery backup')
        self._routes = {}
        self._uboot = None
        self._metadata = set()
        self._checked = False
        self._programming = False
        self._barrier = None

    def close(self):
        self._token = None
        self.native.__exit__()

    def _inventory(self):
        geometry, bad = self.device.inventory()
        require(geometry == GEOMETRY and self.bad_blocks <= bad and
                not (bad - self.bad_blocks - self._metadata), 'physical inventory changed')

    def inspect(self, *, transaction=None, resume=False, journal_trial_recovery=False,
                initialize=False, complete=False):
        """Read only. Pin this session to every byte of the external backup."""
        modes=(resume,journal_trial_recovery,initialize,complete)
        require(all(type(v) is bool for v in modes) and sum(modes)<=1,'invalid recovery inspection')
        require(not (resume or initialize or complete) or transaction is not None,
                'retained transaction required for recovery inspection')
        self._checked = False
        self._token = None
        self._transaction = None
        self._allowed = set()
        self._resume_transaction = transaction if resume or initialize or complete else None
        self.device.verify_protocol()
        geometry, actual_bad = self.device.inventory()
        require(geometry == GEOMETRY, 'wrong physical geometry')
        # ROM records can occupy conventional marker bytes. Permit those only
        # when the complete physical block matches the verified backup below.
        self._metadata = actual_bad - self.bad_blocks
        require(self._metadata <= {0,1,2,3,6}, 'unexpected factory bad-block map')
        require(self.bad_blocks <= actual_bad, 'factory marker disappeared')
        completed = {}
        mutable = set()
        if initialize or complete:
            def owner(page):
                if (len(page)==2048 and page[:8]==struct.pack('<4sI',b'LFJ5',1) and
                    struct.unpack_from('<I',page,2044)[0]==zlib.crc32(page[:2044])):
                    return page[20:52]
                return None
            accepted={transaction.id}
            if transaction.mode in ('restore','repair-boot','refresh-dual'):
                for b in JOURNAL_BLOCKS:
                    try:accepted.add(owner(model.payload(model.read_block(self.initial,b)[:2112],self.native)))
                    except ValueError:pass
            for slot in (0,1):
                identity=owner(self.read_journal(slot))
                require(identity is None or identity in accepted,'foreign journal transaction')
            mutable=set(JOURNAL_BLOCKS)
            if complete:completed={c.block:sha(c.after).hex() for c in transaction.changes}
        if resume:
            require(transaction.backup_digest == self.backup_digest, 'foreign resume backup')
            _, _, index, pending = read_transaction_state(self, transaction)
            completed = {c.block:sha(c.after).hex() for c in transaction.changes[:index]}
            mutable = set(JOURNAL_BLOCKS)
            if pending: mutable.add(transaction.changes[index].block)
        elif journal_trial_recovery:
            require(all(model.read_block(self.initial,b) == ERASED for b in JOURNAL_BLOCKS),
                    'journal recovery requires an erased original backup')
            mutable = set(JOURNAL_BLOCKS)
        with self.initial.open('rb') as source:
            for first in range(0,4096,32):
                actual = self.device.hash_blocks(first,32)
                require(len(actual) == 32, 'incomplete device fingerprint')
                for offset in range(32):
                    block = first+offset
                    original = sha(source.read(RAW_BLOCK)).hex()
                    expected = completed.get(block,original)
                    require(block in mutable or actual[offset] == expected,
                            f'physical source differs from retained plan at block {block}')
                self.event({'state':'physical-backup-read','blocks':first+32})
        self._inventory()
        self.event({'state':'physical-backup-verified','sha256':self.backup_digest.hex()})
        self._checked = True

    def authorize(self, transaction, *, uboot, approved=False):
        """Issue a nonserializable permit only after all before-images match.

        uboot is the validated boot-stream IMX corresponding to the plan, not
        the RAM recovery transport. The caller checks signatures/plan inputs.
        """
        require(approved is True and self._checked and self._token is None,
                'explicit reviewed physical transaction required')
        require(transaction.backup_digest == self.backup_digest, 'foreign transaction backup')
        require(self._resume_transaction is None or transaction is self._resume_transaction,
                'resume was inspected for another transaction')
        self._uboot = Path(uboot).resolve()
        self._transaction = transaction
        self._allowed = {c.block for c in transaction.changes} | set(JOURNAL_BLOCKS)
        for change in transaction.changes:
            require(change.block not in self.bad_blocks, 'plan writes factory-bad block')
            require(model.read_block(self.initial,change.block) == change.before,
                    'physical plan before-image differs from backup')
            self._known[change.block] = {sha(raw).hex():raw for raw in (change.before,change.after,ERASED)}
            if change.block==6 and model.STOCK_BLOCK6_SHA256 in self._known[6]:
                self._metadata.add(6)
        self._routes = {b:model.read_block(self.initial,b) for b in (*range(4),*range(240,256))}
        # Validate the proposed recovery route before authorizing a first erase.
        if transaction.mode in ('migrate','add-hp','repair-boot','refresh-dual'):
            routes = dict(self._routes)
            for c in transaction.changes:
                if c.phase in ('stage-recovery','redirect-rom'): routes[c.block] = c.after
            model.verify_routes_reader(lambda b:routes[b], self._uboot, self.bad_blocks, self.native)
        else:
            model.verify_routes_reader(lambda b:self._routes[b], self._uboot, self.bad_blocks, self.native)
        self.event({'state':'physical-transaction-authorized','transaction':transaction.id.hex()})
        self._token = object()
        return self._token

    def authorize_journal_trial(self, *, approved=False):
        """Narrow hardware qualification: only two erased journal blocks."""
        require(approved is True and self._checked and self._token is None,
                'explicit journal trial required')
        for block in JOURNAL_BLOCKS:
            require(block not in self.bad_blocks and model.read_block(self.initial,block) == ERASED,
                    'journal trial requires verified erased source blocks')
        self.event({'state':'journal-trial-authorized','blocks':list(JOURNAL_BLOCKS)})
        self._allowed = set(JOURNAL_BLOCKS)
        self._token = object()
        return self._token

    def accepts_authorization(self, transaction, authorization):
        return (authorization is not None and authorization is self._token and
                transaction is self._transaction and self._checked)

    def _write_allowed(self, block):
        require(self._token is not None and block in self._allowed and block not in self.bad_blocks,
                'write outside approved physical transaction')
        try:self._inventory()
        except Exception:
            self._token=None
            raise

    def read_block(self, block):
        require(type(block) is int and 0 <= block < 4096, 'invalid physical block')
        digest = self.device.hash_blocks(block,1)
        require(len(digest) == 1, 'incomplete block hash')
        candidates = self._known.get(block, {})
        if digest[0] == sha(ERASED).hex(): return ERASED
        if digest[0] in candidates: return candidates[digest[0]]
        raw = self.device.read_block(block)
        require(len(raw) == RAW_BLOCK and sha(raw).hex() == digest[0], 'unstable raw readback')
        return raw

    def replace_block(self, block, raw):
        self._write_allowed(block)
        require(len(raw) == RAW_BLOCK, 'complete physical block required')
        require(not self._programming, 'physical operation already active')
        self._programming = True
        try:
            pages = 64
            while pages and raw[(pages-1)*2112:pages*2112] == b'\xff'*2112: pages -= 1
            staged = raw[:pages*2112]
            if pages: self.device.stage_bytes(staged)
            self.event({'state':'erase-pending','block':block,'after':sha(raw).hex()})
            self.device.erase(block,stock_metadata=block in self._metadata)
            require(self.device.hash_blocks(block,1) == [sha(ERASED).hex()], 'physical erase did not verify')
            if pages:
                require(self.device.stage_digest(len(staged)) == sha(staged), 'staged bytes changed after erase')
                self.event({'state':'program-pending','block':block,'pages':pages})
                self.device.program_pages(block,pages)
            require(self.device.hash_blocks(block,1) == [sha(raw).hex()], 'physical block readback mismatch')
            self._known.setdefault(block,{})[sha(raw).hex()] = raw
            self.event({'state':'block-verified','block':block,'sha256':sha(raw).hex()})
        except Exception:
            # Never send another mutation after an ambiguous response. A fresh
            # reviewed connection must inspect the on-device journal first.
            self._token = None
            raise
        finally:
            self._programming = False

    def erase_block(self, block): self.replace_block(block,ERASED)

    def read_journal(self, slot):
        require(type(slot) is int and slot in (0,1), 'invalid journal slot')
        raw = self.read_block(JOURNAL_BLOCKS[slot])
        # A torn erase/program can destroy either copy. Represent only media
        # corruption as invalid data so the shared parser can use its peer.
        # Transport errors above still propagate and stop execution.
        if raw[2112:] != b'\xff'*(RAW_BLOCK-2112): return bytes(2048)
        try: return model.payload(raw[:2112],self.native)
        except ValueError: return bytes(2048)

    def write_journal(self, slot, page):
        require(type(slot) is int and slot in (0,1) and len(page) == 2048,'invalid journal')
        data, aux = model.ECC.swap_marker(page,b'\xff'*10)
        raw = model.ECC.encode(data,aux,self.native) + b'\xff'*(RAW_BLOCK-2112)
        self.replace_block(JOURNAL_BLOCKS[slot],raw)

    def verify_backup(self, digest):
        require(digest == self.backup_digest and model.file_hash(self.backup) == digest,
                'external physical backup changed')

    def verify_recovery_barrier(self, transaction):
        require(transaction is self._transaction, 'unreviewed recovery barrier')
        routes = dict(self._routes)
        for change in transaction.changes:
            if change.phase in ('stage-recovery','redirect-rom'):
                routes[change.block] = change.after
        self._verify_blocks(routes, 'physical ROM route mismatch')
        # Decode once per exact route identity, but physically hash every route
        # before every data mutation, including unchanged route blocks.
        identity = tuple((b,sha(raw)) for b,raw in sorted(routes.items()))
        if self._barrier != identity:
            model.verify_routes_reader(lambda b:routes[b],self._uboot,self.bad_blocks,self.native)
            self._barrier = identity

    def _verify_blocks(self, expected, message):
        blocks = sorted(expected)
        while blocks:
            first = blocks.pop(0)
            batch = [first]
            while blocks and blocks[0] == batch[-1]+1 and len(batch) < 32:
                batch.append(blocks.pop(0))
            require(self.device.hash_blocks(first,len(batch)) ==
                    [sha(expected[b]).hex() for b in batch], message)

    def verify_restore_barrier(self, transaction, phase):
        require(transaction is self._transaction, 'unreviewed restore barrier')
        for block in (256,257):
            require(self.read_block(block) == ERASED,'dual layout still enabled during restore')
        routes = range(240,256) if phase == 'restore-rom' else self._routes if phase == 'restore-data' else ()
        self._verify_blocks({b:self._routes[b] for b in routes},'physical restore route changed')
        if phase in ('restore-rom','restore-cleanup'):
            self._verify_blocks({c.block:c.after for c in transaction.changes if c.phase == 'restore-data'},
                                'stock data not restored')
        if phase == 'restore-cleanup':
            self._verify_blocks({c.block:c.after for c in transaction.changes if c.phase == 'restore-rom'},
                                'stock ROM route not restored')

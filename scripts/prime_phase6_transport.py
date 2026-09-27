#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded private RAM-recovery transport. No automatic hardware writes.

The Phase 6 loader hashes NAND in READBACK, preserving the separate STAGE
buffer. Its fixed-address upload digest must match before erasing anything.
"""
import hashlib
import struct
from prime_hp_raw_restore import PrimeSDP, STAGE, READBACK, ERASE, RAW_BLOCK

RAW_PAGE = 2112


class Phase6SDP(PrimeSDP):
    def check_write_budget(self):
        self.run('hprecoverybudget')
        report=self.read(0x83e02040,16)
        if len(report)!=16:
            raise ValueError('missing bounded recovery budget')
        magic,version,remaining,total=struct.unpack('<4I',report)
        if (magic,version,total)!=(0x36445242,1,5400000) or not 300000<remaining<=total:
            raise TimeoutError('recovery window nearly exhausted; stop before erase and reconnect recovery')
        return remaining

    def erase(self, block, *, stock_metadata=False):
        self.check_write_budget()
        return super().erase(block,stock_metadata=stock_metadata)

    def stage_bytes(self, data):
        if not data or len(data) > RAW_BLOCK or len(data) % RAW_PAGE:
            raise ValueError('complete bounded physical pages required')
        self._command(0x0404, STAGE, data)
        if self.stage_digest(len(data)) != hashlib.sha256(data).digest():
            raise ValueError('RAM upload SHA-256 mismatch; no erase allowed')

    def stage_digest(self, length):
        if type(length) is not int or not 0 < length <= RAW_BLOCK:
            raise ValueError('bounded stage hash required')
        self.run(f'hpstagehash {length:x}')
        report = self.read(0x83e02000, 40)
        if len(report) != 40 or struct.unpack_from('<2I', report) != (0x3648534c, length):
            raise ValueError('Phase 6 RAM verification protocol unavailable')
        return report[8:]

    def read_page(self, page):
        if type(page) is not int or not 0 <= page < 4096 * 64:
            raise ValueError('invalid NAND page')
        self.run(f'nand read.raw {READBACK:x} {page * 2048:x} 1')
        return self.read(READBACK, RAW_PAGE)

    def program_pages(self, block, count):
        self._block(block)
        if type(count) is not int or not 1 <= count <= 64:
            raise ValueError('bounded raw page program required')
        self.run(f'nand write.raw {STAGE:x} {block * ERASE:x} {count:x}')

    def verify_protocol(self):
        # A RAM-only challenge also proves that NAND hashing uses a disjoint
        # buffer. This must succeed before issuing any erase/program operation.
        self.check_write_budget()
        challenge = hashlib.sha256(b'Lefony Phase 6 bounded RAM challenge').digest() * 66
        self.stage_bytes(challenge)
        self.hash_blocks(0, 1)
        if self.stage_digest(len(challenge)) != hashlib.sha256(challenge).digest():
            raise ValueError('NAND hashing overwrites verified upload; incompatible recovery loader')

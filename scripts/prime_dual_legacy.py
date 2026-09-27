#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit addition of HP from a retained same-board stock backup.

The narrow source profile is the physically qualified Phase 1 boot manager.
Lefony app blocks stay byte-identical. No inferred HP recovery or blank-device
provisioning is supported. The source and HP recovery backups are independent.
"""
import struct
from pathlib import Path
from prime_dual_boot_contract import require, load_layout, sha
from prime_dual_boot_transaction import Change, Transaction
from prime_dual_installer import migration

LEGACY_STREAM_SHA256 = 'd96066b5eb99e3abbb0a23d86d11ccdf3c8800503a1d25f6f445c474b8fcc11a'


def inspect_legacy(backup, digest):
    m=migration();backup=Path(backup)
    require(m.file_hash(backup)==digest,'Lefony backup digest mismatch')
    bad=m.bad_inventory(backup)
    require(not bad.intersection((*range(4),*range(8,12),*range(20,24),*range(240,272))),
            'unsupported legacy boot/control bad block')
    for b in range(240,272):
        require(m.read_block(backup,b)==m.ERASED,'legacy staging area is occupied')
    with m.NativeBCH() as native:
        for b in range(4):
            raw=m.read_block(backup,b)
            fcb,corrections=m.decode_fcb(raw[:2112]);geometry=m.fcb_layout(fcb)
            require(not any(corrections) and raw[2112:]==m.ERASED[2112:], 'damaged legacy ROM control')
            require(geometry.chunks==m.ECC.chunks and geometry.page_bytes==m.ECC.page_bytes and
                    struct.unpack_from('<4I',fcb,0x68)==(512,1280,216,216),
                    'unsupported legacy boot geometry/routes')
        with backup.open('rb') as source:
            for first in (512,1280):
                source.seek(first*2112)
                stream=b''.join(m.payload(source.read(2112),native,geometry) for _ in range(216))
                require(sha(stream).hex()==LEGACY_STREAM_SHA256,'unqualified legacy boot manager')
        capsule=m.payload(m.read_block(backup,32)[:2112],native)
        require(capsule[0x24:0x28]==bytes.fromhex('18286f01') and capsule[0x30:0x34]!=b'LFL5',
                'unsupported legacy OS source')
    return bad


def build_plan(*, backup, expected_backup, hp_backup, hp_backup_sha256,
               candidate, uboot, archive, recreated, public_key, priority=None):
    m=migration()
    bad=inspect_legacy(backup,expected_backup)
    hp_digest=bytes.fromhex(hp_backup_sha256)
    stock,bad_hp=m.build_plan(hp_backup,candidate,uboot,archive,recreated,public_key,hp_digest,priority=priority)
    require(bad==m.factory_inventory(hp_backup),'HP backup belongs to a different factory inventory')
    require(bad_hp==bad or bad_hp==bad|{6} and
            sha(m.read_block(hp_backup,6)).hex()==m.STOCK_BLOCK6_SHA256,
            'unqualified HP retirement metadata')
    for b in bad:
        require(m.read_block(backup,b)==m.read_block(hp_backup,b),'HP backup changes factory-bad bytes')
    desired={c.block:c.after for c in stock.changes}
    _,regions=load_layout();changes=[]
    def add(block,phase):
        if block in bad:return
        before=m.read_block(backup,block)
        after=desired.get(block)
        if after is None:after=m.read_block(hp_backup,block)
        if before!=after:changes.append(Change(block,before,after,phase))
    for b in range(240,256):add(b,'stage-recovery')
    for b in (3,2,1,0):add(b,'redirect-rom')
    # This profile intentionally changes legacy BCH-2 ROM geometry to the
    # validated HP BCH-4 geometry, then restores HP's same-board system area.
    # Neither old OS may run during this journaled transition.
    for b in (*range(4,240),*range(272,392)):add(b,'restore-hp-system')
    for b in range(392,2048):add(b,'migrate-data')
    for name in ('hp_image','lefony_image','lefony_dtb','rescue','preference_primary','preference_secondary'):
        r=regions[name]
        for b in range(r.first,r.end):add(b,'stage-images')
    for b in (256,257):add(b,'commit-layout')
    require(not any(3456<=c.block<3968 for c in changes),'Lefony app preservation violated')
    return Transaction(changes,expected_backup,mode='add-hp'),bad

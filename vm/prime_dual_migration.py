#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private physical-codeword migration model. No USB or device executor.

Only regular files under ignored build/ are writable. Source backup, signed
payloads, all ROM routes and logical reconstruction are checked before use.
The result is an emulator qualification input, never a physical flash image.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output
from prime_dual_boot_contract import (require, sha, capacity, load_layout,
                                      select_record, verify_descriptor, ContractError)
from prime_dual_boot_transaction import Change, Transaction, Engine, RAW_BLOCK, JOURNAL_BLOCKS
from prime_gpmi_bch import Layout
from prime_bch_native import NativeBCH
from prime_nand_image import decode_fcb, fcb_layout
from prime_hp_logical_archive import verify as verify_archive

RAW_PAGE = 2112
ERASED = b'\xff' * RAW_BLOCK
ECC = Layout(0x030a0880, 0x08400880)
BOOT_ECC = Layout(0x03241080, 0x08401080, marker_metadata_index=34)
# Exact retained stock retirement record already used by the Phase 3 restore
# exception. It is not a factory defect: the original Lefony backup has a valid
# DBBT copy here. No other block or marker pattern receives this exception.
STOCK_BLOCK6_SHA256 = 'c2d0f61c3d99d4352df7ec206df2e84a88cb617ef1157421df77d8f0565dafa0'


def file_hash(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').digest()


def read_block(path, block):
    with Path(path).open('rb') as f:
        f.seek(block * RAW_BLOCK)
        data = f.read(RAW_BLOCK)
    require(len(data) == RAW_BLOCK, 'short physical image')
    return data


def bad_inventory(path):
    require(Path(path).stat().st_size == 4096 * RAW_BLOCK, 'wrong NAND geometry')
    bad = set()
    with Path(path).open('rb') as f:
        for block in range(4,4096):
            f.seek(block * RAW_BLOCK)
            raw = f.read(2 * RAW_PAGE)
            if raw[2048] != 255 or raw[RAW_PAGE+2048] != 255:
                bad.add(block)
    return bad


def factory_inventory(path):
    bad=bad_inventory(path)
    if 6 in bad and sha(read_block(path,6)).hex()==STOCK_BLOCK6_SHA256:
        bad.remove(6)
    return bad


def payload(raw, native, geometry=ECC):
    if raw == b'\xff' * RAW_PAGE:
        return b'\xff' * 2048
    decoded = geometry.decode(raw, decoder=native)
    require(not decoded.failed, 'uncorrectable migration codeword')
    return geometry.swap_marker(decoded.payload, decoded.metadata)[0]


def read_image(path, name, length, bad, native):
    data = bytearray()
    for block in capacity(name, length, bad):
        raw = read_block(path, block)
        for at in range(0, RAW_BLOCK, RAW_PAGE):
            if len(data) >= length: break
            data.extend(payload(raw[at:at+RAW_PAGE], native))
    return bytes(data[:length])


def verify_routes(path, uboot, bad, native):
    return verify_routes_reader(lambda block: read_block(path,block), uboot, bad, native)


def verify_routes_reader(read_route, uboot, bad, native):
    require(not set(range(0,4)) & bad, 'bad ROM control block unsupported')
    stream = (bytes(1024) + Path(uboot).read_bytes())
    pages = (len(stream)+2047)//2048
    stream = stream.ljust(pages*2048, b'\xff')
    require(stream[1024:1028] == bytes.fromhex('d1002040'), 'unexpected NAND IVT')
    for block in range(4):
        fcb,_ = decode_fcb(read_route(block)[:RAW_PAGE])
        geometry=fcb_layout(fcb)
        require(geometry.chunks==BOOT_ECC.chunks and geometry.page_bytes==BOOT_ECC.page_bytes and
                geometry.marker_metadata_index==BOOT_ECC.marker_metadata_index,
                'ROM recovery BCH geometry mismatch')
        require(struct.unpack_from('<4I', fcb, 0x68) == (240*64,248*64,pages,pages),
                'a ROM search route still reaches stock HP')
    for name in ('boot_primary','boot_secondary'):
        data = bytearray()
        for block in capacity(name, len(stream), bad):
            raw = read_route(block)
            for at in range(0, RAW_BLOCK, RAW_PAGE):
                if len(data) >= len(stream): break
                data.extend(payload(raw[at:at+RAW_PAGE], native, BOOT_ECC))
        require(bytes(data) == stream, 'recovery boot stream does not verify')
    return stream


def build_plan(backup, candidate, uboot, archive, recreated, public_key, expected_backup, *, priority=None):
    """Build a stock-to-dual plan; never infer an installed Lefony conversion."""
    require(priority is None or type(priority) is int and priority in (0,1), 'invalid priority')
    backup, candidate = Path(backup), Path(candidate)
    require(file_hash(backup) == expected_backup, 'external full backup hash mismatch')
    bad = bad_inventory(backup)
    require(bad_inventory(candidate) == bad, 'candidate changes factory bad markers')
    # Both streams, descriptors, journals and preferences require verified
    # empty stock staging space. No in-place legacy Lefony migration is allowed.
    for block in range(240,272):
        require(read_block(backup,block) == ERASED, 'stock staging area is occupied')
    for block in range(4):
        before=read_block(backup,block)
        require(before[RAW_PAGE:]==b'\xff'*(RAW_BLOCK-RAW_PAGE),'unexpected additional ROM-control pages')
        original,_=decode_fcb(before[:RAW_PAGE])
        updated,_=decode_fcb(read_block(candidate,block)[:RAW_PAGE])
        require(original[4:0x68]==updated[4:0x68] and original[0x78:]==updated[0x78:],
                'candidate changes FCB geometry, DBBT search or unrelated ROM controls')
    logical = verify_archive(Path(archive))
    require(logical['source_sha256'] == expected_backup.hex(), 'logical backup belongs to another source')
    restored = json.loads((Path(recreated)/'recreated.json').read_text())
    require(restored['schema'] == 1 and restored['device_flash_input'] is False and
            restored['archive_sha256'] == logical['archive_sha256'], 'logical recreation mismatch')
    good_fs = [b for b in range(392,2048) if b not in bad]
    require(restored['erase_good_blocks'] == good_fs, 'logical recreation bad-block map mismatch')
    fs = {}
    for key,digest in restored['written_blocks'].items():
        block = int(key)
        raw = (Path(recreated)/f'{block}.raw').read_bytes()
        require(block in good_fs and len(raw) == RAW_BLOCK and sha(raw).hex() == digest,
                'logical recreation readback mismatch')
        fs[block] = raw
    _, regions = load_layout()
    with NativeBCH() as native:
        verify_routes(candidate, uboot, bad, native)
        pages = [payload(read_block(candidate,b)[:RAW_PAGE],native) for b in (256,257)]
        require(pages[0] == pages[1], 'both initial layout records must agree')
        selected = select_record(pages)
        require(selected['state'] == 'committed', 'candidate not committed')
        descriptor = selected['descriptor']
        checked = verify_descriptor(descriptor, public_key)
        images = {name:read_image(candidate,name,length,bad,native)
                  for name,(length,_) in checked['images'].items()}
        verify_descriptor(descriptor, public_key, images)
    changes = []
    def change(block, raw, phase):
        before = read_block(backup,block)
        require(block not in bad, 'attempt to change bad block')
        if before != raw:
            changes.append(Change(block,before,raw,phase))
    for name in ('boot_primary','boot_secondary'):
        region = regions[name]
        for block in range(region.first,region.end):
            if block not in bad: change(block,read_block(candidate,block),'stage-recovery')
    for block in (3,2,1,0): change(block,read_block(candidate,block),'redirect-rom')
    for block in good_fs: change(block,fs.get(block,ERASED),'migrate-data')
    for block in range(3456,3968):
        if block not in bad: change(block,ERASED,'migrate-data')
    for name in (*checked['images'],'preference_primary','preference_secondary'):
        region = regions[name]
        for block in range(region.first,region.end):
            if block not in bad:
                raw=read_block(candidate,block)
                if priority is not None and name in ('preference_primary','preference_secondary'):
                    with NativeBCH() as native:
                        page=bytearray(payload(raw[:RAW_PAGE],native))
                        require(struct.unpack_from('<3I',page)==(0x5042464c,1,5) and
                                struct.unpack_from('<I',page,60)[0]==zlib.crc32(page[:60]) and
                                raw[RAW_PAGE:]==b'\xff'*(RAW_BLOCK-RAW_PAGE),'invalid initial preference record')
                        struct.pack_into('<I',page,16,priority)
                        struct.pack_into('<I',page,60,zlib.crc32(page[:60]))
                        data,aux=ECC.swap_marker(bytes(page),b'\xff'*10)
                        raw=ECC.encode(data,aux,native)+raw[RAW_PAGE:]
                change(block,raw,'stage-images')
    for block in (256,257): change(block,read_block(candidate,block),'commit-layout')
    return Transaction(changes,expected_backup), bad


class FileMedia:
    kind = 'offline-emulator'
    def __init__(self, target, backup, bad, uboot):
        self.target = private_output(Path(target))
        self.backup, self.uboot = Path(backup).resolve(), Path(uboot).resolve()
        require(self.target.is_file() and not self.target.samefile(self.backup), 'separate disposable regular file required')
        require(self.target.stat().st_size == self.backup.stat().st_size == 4096*RAW_BLOCK, 'wrong geometry')
        self.bad_blocks = set(bad)
        self.native = NativeBCH()
        self.events = []
        self.fault = None
        self.operations = 0
        self._barrier = None
        self.restore_routes = {b:self.read_block(b) for b in (*range(4),*range(240,256))}
    def close(self): self.native.__exit__()
    def event(self,kind,block):
        self.operations += 1
        self.events.append((kind,block))
        if self.fault == self.operations: raise InterruptedError('modeled power loss')
    def read_block(self,block): return read_block(self.target,block)
    def write(self,offset,data):
        with self.target.open('r+b',buffering=0) as f:
            f.seek(offset);f.write(data);os.fsync(f.fileno())
    def erase_block(self,block):
        require(block not in self.bad_blocks, 'erase of bad block')
        self.event('before-erase',block)
        self.write(block*RAW_BLOCK,ERASED)
        self.event('after-erase',block)
        if block < 256:self._barrier = None
    def program_raw_page(self,page,data):
        block,offset = divmod(page,64)
        require(block not in self.bad_blocks and len(data)==RAW_PAGE, 'invalid program')
        old = self.read_block(block)[offset*RAW_PAGE:(offset+1)*RAW_PAGE]
        require(old==b'\xff'*RAW_PAGE or all((a&b)==b for a,b in zip(old,data)), 'NAND zero-to-one program')
        self.event('before-program',block)
        self.write(page*RAW_PAGE,data[:1056])
        self.event('half-program',block)
        self.write(page*RAW_PAGE+1056,data[1056:])
        self.event('after-program',block)
    def read_journal(self,slot):
        raw = self.read_block(JOURNAL_BLOCKS[slot])[:RAW_PAGE]
        try:return payload(raw,self.native)
        except ValueError:return bytes(2048) # invalid/torn copy, never valid progress
    def write_journal(self,slot,page):
        data,aux = ECC.swap_marker(page,b'\xff'*10)
        raw = ECC.encode(data,aux,self.native)
        self.erase_block(JOURNAL_BLOCKS[slot])
        self.program_raw_page(JOURNAL_BLOCKS[slot]*64,raw)
    def verify_backup(self,digest):
        require(file_hash(self.backup)==digest, 'external backup is missing or changed')
    def verify_recovery_barrier(self,transaction):
        # Check all route bytes before each data block. Decode once per stable
        # route set, but never cache away raw readback comparison.
        for change in transaction.changes:
            if change.phase in ('stage-recovery','redirect-rom'):
                require(self.read_block(change.block)==change.after, 'ROM route changed')
        if self._barrier != transaction.id:
            verify_routes(self.target,self.uboot,self.bad_blocks,self.native)
            self._barrier = transaction.id


    def verify_restore_barrier(self,transaction,phase):
        pages=[self.read_journal_layout(b) for b in (256,257)]
        try: selected=select_record(pages)
        except ContractError: selected=None
        require(selected is None or selected['state']=='recovery','dual layout still bootable during stock restore')
        route_blocks = range(240,256) if phase=='restore-rom' else self.restore_routes if phase=='restore-data' else ()
        for block in route_blocks:
            require(self.read_block(block)==self.restore_routes[block], 'restore recovery route changed')
        if phase in ('restore-rom','restore-cleanup'):
            for change in transaction.changes:
                if change.phase=='restore-data':
                    require(self.read_block(change.block)==change.after,'stock data not fully restored')
        if phase=='restore-cleanup':
            for block in range(4):
                require(self.read_block(block)==read_block(self.backup,block),'stock ROM routes not restored')
    def read_journal_layout(self,block):
        try:return payload(self.read_block(block)[:RAW_PAGE],self.native)
        except ValueError:return bytes(2048)


def verify_preserved(media, transaction):
    changed={c.block for c in transaction.changes}|set(JOURNAL_BLOCKS)
    with media.backup.open('rb') as backup,media.target.open('rb') as target:
        for block in range(4096):
            before,after=backup.read(RAW_BLOCK),target.read(RAW_BLOCK)
            require(block in changed or before==after, 'unplanned NAND bytes differ from backup')


def build_restore_plan(current,backup,expected_backup):
    require(file_hash(backup)==expected_backup,'stock backup hash mismatch')
    bad=factory_inventory(backup)
    require(factory_inventory(current)==bad,'stock rollback bad map changed')
    changes=[]
    for block in (*range(256,258),*range(4,240),*range(260,4096),3,2,1,0,*range(240,256)):
        before,after=read_block(current,block),read_block(backup,block)
        if before==after:continue
        require(block not in bad,'cannot restore a changed factory-bad block')
        if block in (256,257):
            require(after==ERASED,'original stock control space was not empty')
            phase='disable-boot'
        elif block<4:phase='restore-rom'
        elif 240<=block<256:phase='restore-cleanup'
        else:phase='restore-data'
        changes.append(Change(block,before,after,phase))
    return Transaction(changes,expected_backup,mode='restore'),bad


def restore_stock(current,backup,uboot,expected_backup,output,*,resume=False):
    out=private_output(Path(output))
    require(out.is_dir() if resume else not out.exists(), 'restore output/resume state mismatch')
    tx,bad=build_restore_plan(current,backup,expected_backup)
    with NativeBCH() as native:verify_routes(current,uboot,bad,native)
    manifest={'schema':1,'transaction':tx.id.hex(),'backup_sha256':expected_backup.hex(),
              'device_flash_input':False,'changes':[c.identity() for c in tx.changes]}
    target=out/'nand.raw'
    if resume:
        require(json.loads((out/'plan.json').read_text())==manifest,'retained restore plan changed')
    else:
        out.mkdir(parents=True);shutil.copyfile(current,target)
        (out/'plan.json').write_text(json.dumps(manifest,indent=2)+'\n')
    media=FileMedia(target,backup,bad,uboot)
    # Routes must refer to the pre-restore candidate, not an interrupted target.
    media.restore_routes={b:read_block(current,b) for b in (*range(4),*range(240,256))}
    try:
        verify_preserved(media,tx)
        engine=Engine(media,tx)
        complete=False
        if resume:
            try:engine._read_state()
            except ContractError:
                if all(media.read_block(c.block)==c.after for c in tx.changes):
                    complete=True # only final journal cleanup remains
                else:
                    require(all(media.read_block(c.block)==c.before for c in tx.changes),
                            'restore journal lost after data changes; retained backup recovery required')
                    for block in JOURNAL_BLOCKS:media.erase_block(block)
                    engine.prepare()
        else:
            for block in JOURNAL_BLOCKS:media.erase_block(block)
            engine.prepare()
        if not complete:engine.run()
        with Path(backup).open('rb') as original,target.open('rb') as final:
            for block in range(4096):
                before,after=original.read(RAW_BLOCK),final.read(RAW_BLOCK)
                require(block in JOURNAL_BLOCKS or before==after,'stock data incomplete before journal cleanup')
        for block in JOURNAL_BLOCKS:
            require(read_block(backup,block)==ERASED,'unexpected stock journal bytes')
            media.erase_block(block)
        require(file_hash(target)==expected_backup,'full stock rollback mismatch')
        report={'schema':1,'result':'PASS all 4096 blocks match original stock backup',
                'device_flash_input':False,'sha256':expected_backup.hex(),
                'changed_blocks':len(tx.changes),'transaction':tx.id.hex()}
        (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:media.close()


def execute(backup,candidate,uboot,archive,recreated,public_key,expected_backup,output,*,resume=False,priority=None,
            hp_backup=None,hp_backup_sha256=None):
    out=private_output(Path(output))
    require(out.is_dir() if resume else not out.exists(), 'resume needs an existing plan; a new migration needs a new directory')
    if hp_backup is not None:
        from prime_dual_legacy import build_plan as legacy_plan
        tx,bad=legacy_plan(backup=backup,candidate=candidate,uboot=uboot,archive=archive,
                          recreated=recreated,public_key=public_key,expected_backup=expected_backup,
                          hp_backup=hp_backup,hp_backup_sha256=hp_backup_sha256,priority=priority)
    else:
        require(hp_backup_sha256 is None,'unexpected HP backup identity')
        tx,bad=build_plan(backup,candidate,uboot,archive,recreated,public_key,expected_backup,priority=priority)
    manifest={'schema':1,'transaction':tx.id.hex(),
        'backup_sha256':expected_backup.hex(),'device_flash_input':False,
        'bad_blocks':sorted(bad),'changes':[c.identity() for c in tx.changes]}
    target=out/'nand.raw'
    if resume:
        require(json.loads((out/'plan.json').read_text())==manifest,'retained migration plan changed')
    else:
        out.mkdir(parents=True);shutil.copyfile(backup,target)
        (out/'plan.json').write_text(json.dumps(manifest,indent=2)+'\n')
    media=FileMedia(target,backup,bad,uboot)
    try:
        verify_preserved(media,tx)
        engine=Engine(media,tx)
        if resume:
            try:engine._read_state()
            except ContractError:
                # Initialization may have lost its only valid copy. The
                # retained host plan is sufficient only before any OS/ROM
                # target changed; otherwise require explicit stock recovery.
                require(all(media.read_block(c.block)==c.before for c in tx.changes),
                        'no valid journal after data changes; stock recovery required')
                for block in JOURNAL_BLOCKS:media.erase_block(block)
                engine.prepare()
        else:engine.prepare()
        engine.run()
        require(all(media.read_block(c.block)==c.after for c in tx.changes),'final migration readback mismatch')
        with Path(backup).open('rb') as original,target.open('rb') as final:
            changed={c.block for c in tx.changes}|set(JOURNAL_BLOCKS)
            for block in range(4096):
                before,after=original.read(RAW_BLOCK),final.read(RAW_BLOCK)
                require(block in changed or before==after,'unplanned block changed')
        report={'schema':1,'result':'PASS offline transaction/readback',
                'device_flash_input':False,'transaction':tx.id.hex(),
                'sha256':file_hash(target).hex(),'persistent_events':media.operations,
                'changed_blocks':len(tx.changes),'logical_archive':json.loads((Path(archive)/'archive.json').read_text())['archive_sha256']}
        (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:media.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('backup','candidate','uboot','archive','recreated','public-key','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--backup-sha256',required=True)
    p.add_argument('--resume',action='store_true',help='resume only the matching retained offline plan')
    a=p.parse_args()
    print(execute(a.backup,a.candidate,a.uboot,a.archive,a.recreated,a.public_key,
                  bytes.fromhex(a.backup_sha256),a.output,resume=a.resume),flush=True)

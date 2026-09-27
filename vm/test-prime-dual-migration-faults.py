#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cut every persistent operation of real migration/rollback plans.

This is a copy-on-write host NAND model using the physical ECC codewords and
journal codec. Separate ARM/QEMU tests establish actual ROM and OS startup.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from functools import lru_cache
from prime_dual_migration import (FileMedia, build_plan, build_restore_plan, read_block,
    payload, ECC, ERASED, RAW_BLOCK, RAW_PAGE, NativeBCH, private_output, require,
    verify_routes)
from prime_dual_boot_transaction import Engine, JOURNAL_BLOCKS


class Model(FileMedia):
    def __init__(self,source,backup,tx,bad,uboot,native):
        self.source,self.backup,self.uboot=source,backup,uboot
        self.bad_blocks,self.native=set(bad),native
        self.snapshot={c.block:c.before for c in tx.changes}
        self.blocks={}
        self.operations=0;self.fault=None;self.events=[];self._barrier=None
        self.digest=tx.backup_digest
        # Source is a verified immutable fixture; trial writes never change it.
        self.restore_routes={b:read_block(source,b) for b in (*range(4),*range(240,256))}
    def clone(self):
        result=copy.copy(self);result.blocks=dict(self.blocks);result.events=[]
        result.decoded=self.decoded;result.encoded=self.encoded
        return result
    def read_block(self,block):
        if block in self.blocks:return self.blocks[block]
        if block not in self.snapshot:self.snapshot[block]=read_block(self.source,block)
        return self.snapshot[block]
    def write(self,offset,data):
        block,at=divmod(offset,RAW_BLOCK)
        require(at+len(data)<=RAW_BLOCK,'cross-block model write')
        original=self.read_block(block)
        self.blocks[block]=original[:at]+data+original[at+len(data):]
    def verify_backup(self,digest):require(digest==self.digest,'model backup identity changed')
    def verify_recovery_barrier(self,tx):
        for c in tx.changes:
            if c.phase in ('stage-recovery','redirect-rom'):
                require(self.read_block(c.block)==c.after,'unverified ROM route')
    def verify_restore_barrier(self,tx,phase):
        super().verify_restore_barrier(tx,phase)
        blocks=range(240,256) if phase=='restore-rom' else self.restore_routes if phase=='restore-data' else ()
        for block in blocks:
            require(self.read_block(block)==self.restore_routes[block],'restore recovery route changed')
    @lru_cache(maxsize=100000)
    def decoded(self,raw):
        try:return payload(raw,self.native)
        except ValueError:return bytes(2048)
    def read_journal(self,slot):return self.decoded(self.read_block(JOURNAL_BLOCKS[slot])[:RAW_PAGE])
    @lru_cache(maxsize=100000)
    def encoded(self,page):
        data,aux=ECC.swap_marker(page,b'\xff'*10)
        return ECC.encode(data,aux,self.native)
    def write_journal(self,slot,page):
        self.erase_block(JOURNAL_BLOCKS[slot])
        self.program_raw_page(JOURNAL_BLOCKS[slot]*64,self.encoded(page))


def qualify(source,backup,tx,bad,uboot):
    cuts=0;initialization_cuts=0;cleanup_cuts=0
    with NativeBCH() as native:
        baseline=Model(source,backup,tx,bad,uboot,native)
        # Restore/repair start after host has retained the immutable plan.
        # Cuts while replacing old journals are host-backup recovery states;
        # no filesystem/ROM data has changed at that point.
        if tx.mode in ('restore','repair-boot','refresh-dual'):
            for block in JOURNAL_BLOCKS:baseline.blocks[block]=ERASED
        pristine=baseline.clone()
        Engine(baseline,tx).prepare()
        for cut in range(pristine.operations+1,baseline.operations+1):
            trial=pristine.clone();trial.fault=cut
            try:Engine(trial,tx).prepare()
            except InterruptedError:pass
            else:raise AssertionError('initialization fault not reached')
            require(all(trial.read_block(c.block)==c.before for c in tx.changes),
                    'initialization changed OS/ROM data')
            # If neither copy decodes, the verified host plan can recreate
            # journals because every transaction target is still pristine.
            initialization_cuts+=1
        for index,c in enumerate(tx.changes):
            start=baseline.clone()
            Engine(baseline,tx).run(max_changes=1)
            # Canonicalize immutable bytes only after the engine's real raw
            # readback proved equality. Clones share verified completed blocks;
            # prefix checks need not repeatedly compare gigabytes of aliases.
            require(baseline.read_block(c.block)==c.after,'baseline readback mismatch')
            baseline.blocks[c.block]=c.after
            for cut in range(start.operations+1,baseline.operations+1):
                trial=start.clone();trial.fault=cut
                try:Engine(trial,tx).run(max_changes=1)
                except InterruptedError:pass
                else:raise AssertionError('fault boundary not reached')
                trial.fault=None
                position=Engine(trial,tx)._read_state()[2]
                require(position in (index,index+1),'journal skipped a block')
                Engine(trial,tx).run(max_changes=1 if position==index else 0)
                require(Engine(trial,tx)._read_state()[2:]==(index+1,False),'resume incomplete')
                require(trial.read_block(c.block)==c.after,'resumed data differs')
                require(all(trial.read_block(b)==baseline.read_block(b) for b in
                            set(trial.blocks)|set(baseline.blocks) if b not in JOURNAL_BLOCKS),
                        'fault changed an unrelated block')
                cuts+=1
            if index%50==0:print(tx.mode,index+1,'blocks,',cuts,'cuts',flush=True)
        require(Engine(baseline,tx).run()==tx.id.hex(),'final complete state missing')
        if tx.mode=='restore':
            start=baseline.clone()
            for block in JOURNAL_BLOCKS:baseline.erase_block(block)
            for cut in range(start.operations+1,baseline.operations+1):
                trial=start.clone();trial.fault=cut
                try:
                    for block in JOURNAL_BLOCKS:trial.erase_block(block)
                except InterruptedError:pass
                else:raise AssertionError('cleanup fault not reached')
                require(all(trial.read_block(c.block)==c.after for c in tx.changes),
                        'journal cleanup changed restored stock data')
                trial.fault=None
                for block in JOURNAL_BLOCKS:trial.erase_block(block)
                require(all(trial.read_block(b)==ERASED for b in JOURNAL_BLOCKS),'cleanup incomplete')
                cleanup_cuts+=1
    return {'mode':tx.mode,'changed_blocks':len(tx.changes),'persistent_cuts':cuts,'initialization_cuts':initialization_cuts,'cleanup_cuts':cleanup_cuts,
            'result':'PASS every erase/program/half-page/journal boundary resumes one checked step'}


def qualify_restore_journal_replacement(source,backup,tx,bad,uboot):
    with NativeBCH() as native:
        initial=Model(source,backup,tx,bad,uboot,native)
        baseline=initial.clone()
        for block in JOURNAL_BLOCKS:baseline.erase_block(block)
        for cut in range(1,baseline.operations+1):
            trial=initial.clone();trial.fault=cut
            try:
                for block in JOURNAL_BLOCKS:trial.erase_block(block)
            except InterruptedError:pass
            else:raise AssertionError('journal replacement boundary not reached')
            require(all(trial.read_block(c.block)==c.before for c in tx.changes),
                    'journal replacement altered OS/ROM targets')
            trial.fault=None
            for block in JOURNAL_BLOCKS:trial.erase_block(block)
            Engine(trial,tx).prepare()
            require(Engine(trial,tx)._read_state()[2:]==(0,False),'new restore journal not established')
        return {'result':'PASS','persistent_cuts':baseline.operations,
                'scope':'old migration journals erased before restore initialization; OS/ROM bytes remain intact'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('backup','candidate','uboot','archive','recreated','public-key','migrated','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--backup-sha256',required=True)
    a=p.parse_args();out=private_output(a.output);require(not out.exists(),'output must be new')
    digest=bytes.fromhex(a.backup_sha256)
    tx,bad=build_plan(a.backup,a.candidate,a.uboot,a.archive,a.recreated,a.public_key,digest)
    out.mkdir(parents=True)
    results=[qualify(a.backup,a.backup,tx,bad,a.uboot)]
    (out/'migration.json').write_text(json.dumps(results[0],indent=2)+'\n')
    tx,bad=build_restore_plan(a.migrated,a.backup,digest)
    with NativeBCH() as native:verify_routes(a.migrated,a.uboot,bad,native)
    replacement=qualify_restore_journal_replacement(a.migrated,a.backup,tx,bad,a.uboot)
    (out/'restore-journal-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n')
    results.append(qualify(a.migrated,a.backup,tx,bad,a.uboot))
    (out/'qualification.json').write_text(json.dumps({'results':results,
        'physical_qualification':False,'scope':'host physical-codeword transaction model; ARM boot tested separately',
        'initialization_recovery':'No valid new journal: retain original OS/ROM state and restart from verified host plan before changing data.',
        'final_journal_cleanup':'After full stock comparison, interrupted journal erases need only completion from retained host backup.'},indent=2)+'\n')
    print(results,flush=True)


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify an exact retained refresh in a disposable host NAND model.

Produces final and transition fixtures for separate actual ARM ROM tests.
No USB access, no physical writes; these fixtures must never be flashed.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from prime_dual_refresh import reviewed_plan, m, source_images
from prime_dual_boot_transaction import Engine, JOURNAL_BLOCKS
from prime_dual_boot_contract import require
faults=importlib.import_module('test-prime-dual-migration-faults')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=m.private_output(a.output);require(not out.exists(),'new output required')
    tx,bad,inputs=reviewed_plan(a.review);source=Path(inputs['source']);out.mkdir(parents=True)
    result=faults.qualify(source,source,tx,bad,Path(inputs['uboot']))
    result['journal_replacement']=faults.qualify_restore_journal_replacement(source,source,tx,bad,Path(inputs['uboot']))
    # Use the real journal engine, not a whole-image flash or a copied guess.
    target=out/'nand.raw';shutil.copyfile(source,target)
    media=m.FileMedia(target,source,bad,inputs['uboot'])
    try:
        for b in JOURNAL_BLOCKS:media.erase_block(b)
        Engine(media,tx).prepare()
        for i,c in enumerate(tx.changes):
            Engine(media,tx).run(max_changes=1)
            following=tx.changes[i+1] if i+1<len(tx.changes) else None
            if c.phase=='redirect-rom' and following.phase=='stage-recovery':
                shutil.copyfile(target,out/'expanded-fcb.raw')
            if c.phase=='stage-recovery' and c.block>=248 and following.block<248:
                shutil.copyfile(target,out/'new-secondary.raw')
        require(Engine(media,tx).run()==tx.id.hex(),'incomplete model update')
        m.verify_routes(target,inputs['uboot'],bad,media.native)
        source_images(target,inputs['public_key'],media.native,bad)
        changed={c.block for c in tx.changes}|set(JOURNAL_BLOCKS)
        for block in range(4096):
            if block not in changed:
                require(m.read_block(source,block)==m.read_block(target,block),'preserved block changed')
    finally:media.close()
    require(reviewed_plan(a.review)[0].id==tx.id,'inputs changed during test')
    result.update(transaction=tx.id.hex(),sha256=m.file_hash(target).hex(),
                  physical_qualification=False,device_flash_input=False)
    (out/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS refresh fault boundaries, signed readback and preserved regions',flush=True)


if __name__=='__main__':main()

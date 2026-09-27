#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private, retained stock or explicitly profiled Lefony-to-dual session.

Requires a Phase 6 RAM recovery loader and separately verified source backups.
Never converts legacy Lefony implicitly, opens a browser API, resets hardware,
or enables the public installer. Every invocation revalidates signed inputs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import time

from prime_dual_boot_contract import require, ContractError
from prime_dual_boot_transaction import Engine, JOURNAL_BLOCKS
from prime_dual_installer import atomic_json, checked_plan, contract, locked, normalized_bundle
from prime_dual_physical import PhysicalMedia, RAW_BLOCK, model
from prime_phase6_transport import Phase6SDP


def inspected_engine(media,tx,uboot,*,resume=False):
    initialize=not resume
    if resume:
        try:media.inspect(transaction=tx,resume=True)
        except ContractError:
            # Only an entirely pristine source (apart from owned journals)
            # can restart initialization. Partial targets or foreign owners fail.
            media.inspect(transaction=tx,initialize=True)
            initialize=True
    else:media.inspect()
    permit=media.authorize(tx,uboot=uboot,approved=True)
    engine=Engine(media,tx,research_authorization=permit)
    if initialize:
        if resume or tx.mode in ('restore','repair-boot','refresh-dual'):
            for block in JOURNAL_BLOCKS:media.erase_block(block)
        engine.prepare()
    return engine


def snapshot_verified(media, transaction, output):
    """Retain exact readback bytes, using hash-bound before/after images.

    Every physical block is freshly hashed. Unknown bytes fail; they are never
    replaced with what the host expected. Journals are read independently.
    """
    output = Path(output)
    require(not output.exists(), 'verified snapshot already exists')
    temporary = output.with_suffix('.partial')
    changes = {c.block:c.after for c in transaction.changes}
    journals = {b:media.read_block(b) for b in JOURNAL_BLOCKS}
    with media.initial.open('rb') as initial, temporary.open('wb') as final:
        os.chmod(temporary,0o600)
        for first in range(0,4096,32):
            hashes = media.device.hash_blocks(first,32)
            require(len(hashes)==32,'incomplete final device fingerprint')
            for i in range(32):
                block=first+i
                raw=initial.read(RAW_BLOCK)
                raw=journals.get(block,changes.get(block,raw))
                require(model.sha(raw).hex()==hashes[i],f'final physical block {block} differs')
                final.write(raw)
            media.event({'state':'final-device-readback','blocks':first+32})
        final.flush();os.fsync(final.fileno())
    os.replace(temporary,output)
    directory=os.open(output.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return model.file_hash(output).hex()


def run(bundle, output, *, priority, approved=False, resume=False):
    require(approved is True,'explicit physical research authorization required')
    require(priority in ('lefony','hp'),'explicit priority required')
    # All compatibility, signed payload, source layout, logical archive and
    # bad-block checks precede opening USB. Unprofiled legacy Lefony fails here.
    tx,bad,paths,digest=checked_plan(bundle,priority)
    output=model.private_output(Path(output))
    expected={'schema':1,'purpose':'phase6-stock-install-trial',
              'transaction':tx.id.hex(),'priority':priority,
              'bundle':normalized_bundle(bundle,paths,digest),
              'layout_sha256':contract()['layout_sha256'],'bad_blocks':sorted(bad),
              'changes':[c.identity() for c in tx.changes]}
    if resume:
        require(json.loads((output/'review.json').read_text())==expected,'retained hardware review changed')
    else:
        require(not output.exists(),'use a new private hardware session')
        parent=output.parent
        while not parent.exists():parent=parent.parent
        require(shutil.disk_usage(parent).free>=contract()['minimum_free_bytes'],'insufficient backup/readback space')
        output.mkdir(parents=True,mode=0o700)
        atomic_json(output/'review.json',expected)
    with locked(output), (output/'events.jsonl').open('a') as log:
        os.chmod(output/'events.jsonl',0o600)
        def event(value):
            log.write(json.dumps({'time':time.time(),**value})+'\n')
            log.flush();os.fsync(log.fileno())
            if value.get('state') not in ('physical-backup-read','final-device-readback') or value.get('blocks',0)%256==0:
                print(json.dumps(value),flush=True)
        device=Phase6SDP();media=None
        try:
            media=PhysicalMedia(device,paths['backup'],digest,event=event)
            engine=inspected_engine(media,tx,paths['uboot'],resume=resume)
            engine.run()
            destination=output/'verified-nand.raw'
            if destination.exists():
                # A completed resume still checked every physical block above.
                # Regenerate readback separately and compare, never overwrite
                # the retained artifact silently.
                fresh=output/'resumed-nand.raw'
                require(not fresh.exists(),'retained resume readback already exists')
                digest_after=snapshot_verified(media,tx,fresh)
                require(model.file_hash(destination).hex()==digest_after,'retained final readback changed')
                fresh.unlink()
            else:digest_after=snapshot_verified(media,tx,destination)
            result={'schema':1,'state':'physical-nand-verified','transaction':tx.id.hex(),
                    'snapshot_sha256':digest_after,'boot_confirmed':False,
                    'public_install_qualified':False,'changed_blocks':len(tx.changes)}
            atomic_json(output/'qualification.json',result)
            event(result)
            return result
        except Exception as error:
            event({'state':'stopped','error':str(error),'automatic_retry':False})
            raise
        finally:
            if media:media.close()
            device.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--priority',choices=('lefony','hp'),required=True)
    parser.add_argument('--approved',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    run(json.loads(args.bundle.read_text()),args.output,priority=args.priority,
        approved=args.approved,resume=args.resume)

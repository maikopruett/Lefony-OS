#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retained, explicit restoration of a dual device to its verified backup.

The initial snapshot must be a fresh complete device capture. No reset, retry,
automatic source selection or arbitrary block-write API is exposed.
"""
import argparse
import json
import os
from pathlib import Path
import time
from prime_dual_boot_contract import require, ContractError
from prime_dual_installer import atomic_json,locked
from prime_dual_physical import PhysicalMedia,model,ERASED
from prime_phase6_install_trial import snapshot_verified,inspected_engine
from prime_phase6_transport import Phase6SDP


def run(current,backup,digest,uboot,output,*,approved=False,resume=False):
    require(approved is True,'explicit physical restoration required')
    current,backup,uboot=map(lambda p:Path(p).resolve(),(current,backup,uboot))
    tx,bad=model.build_restore_plan(current,backup,digest)
    with model.NativeBCH() as native:model.verify_routes(current,uboot,bad,native)
    require(all(model.read_block(backup,b)==ERASED for b in (258,259)),'backup journal space is not empty')
    current_digest=model.file_hash(current)
    expected={'schema':1,'purpose':'phase6-restore','transaction':tx.id.hex(),
              'current':str(current),'current_sha256':current_digest.hex(),
              'backup':str(backup),'backup_sha256':digest.hex(),
              'uboot':str(uboot),'uboot_sha256':model.file_hash(uboot).hex()}
    output=model.private_output(Path(output))
    if resume:require(json.loads((output/'review.json').read_text())==expected,'restore review changed')
    else:
        require(not output.exists(),'new restore requires a new retained session')
        output.mkdir(parents=True,mode=0o700);atomic_json(output/'review.json',expected)
    with locked(output),(output/'events.jsonl').open('a') as log:
        os.chmod(output/'events.jsonl',0o600)
        def event(value):
            log.write(json.dumps({'time':time.time(),**value})+'\n');log.flush();os.fsync(log.fileno())
            if value.get('state') not in ('physical-backup-read','final-device-readback') or value.get('blocks',0)%256==0:
                print(json.dumps(value),flush=True)
        d=Phase6SDP();media=None
        try:
            media=PhysicalMedia(d,backup,digest,initial=current,initial_digest=current_digest,event=event)
            complete=False
            if resume:
                try:media.inspect(transaction=tx,complete=True);complete=True
                except ContractError:pass
            if complete:media.authorize(tx,uboot=uboot,approved=True)
            else:inspected_engine(media,tx,uboot,resume=resume).run()
            # Full physical verification precedes retiring either final journal.
            media.inspect(transaction=tx,complete=True)
            media.authorize(tx,uboot=uboot,approved=True)
            for b in (258,259):
                if media.read_block(b)!=ERASED:media.erase_block(b)
            destination=output/'verified-restore.raw'
            if destination.exists():
                require(model.file_hash(destination)==digest,'retained restoration readback changed')
            else:
                require(snapshot_verified(media,tx,destination)==digest.hex(),'full physical restore differs from backup')
            result={'state':'restore-verified','transaction':tx.id.hex(),
                    'sha256':digest.hex(),'blocks':4096,'boot_confirmed':False}
            atomic_json(output/'qualification.json',result);event(result)
            return result
        except Exception as error:
            event({'state':'stopped','error':str(error),'automatic_retry':False});raise
        finally:
            if media:media.close()
            d.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('current','backup','uboot','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--backup-sha256',required=True)
    p.add_argument('--approved',action='store_true');p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    run(a.current,a.backup,bytes.fromhex(a.backup_sha256),a.uboot,a.output,approved=a.approved,resume=a.resume)

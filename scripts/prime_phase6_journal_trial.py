#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit private qualification of the two erased dual-layout journal blocks.

Never changes boot routes, an OS image or either filesystem. It verifies all
4096 source blocks before starting, writes/reads both journals, restores their
original erased bytes, then verifies the complete original fingerprint again.
No automatic retry, reset or OS launch occurs. Public migration stays disabled.
"""
import argparse
import json
import os
from pathlib import Path
import time
from prime_dual_boot_contract import require
from prime_dual_boot_transaction import Change, Transaction, journal_page, decode_journal
from prime_dual_installer import atomic_json, locked
from prime_dual_physical import PhysicalMedia, ERASED, model
from prime_phase6_transport import Phase6SDP
from analyze_hp_prime_compatibility import private_output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--backup-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--approved',action='store_true',help='explicitly authorize this bounded NAND trial')
    parser.add_argument('--recover',action='store_true',help='restore only an interrupted trial using its retained review')
    args=parser.parse_args()
    require(args.approved is True,'explicit hardware trial authorization is required')
    digest=bytes.fromhex(args.backup_sha256)
    require(len(digest)==32,'complete external backup digest required')
    out=private_output(args.output)
    review={'schema':1,'purpose':'phase6-journal-trial','backup_sha256':digest.hex(),
            'backup':str(args.backup.resolve()),'owned_blocks':[258,259]}
    if args.recover:
        require(json.loads((out/'review.json').read_text())==review,'retained trial review changed')
    else:
        require(not out.exists(),'use a new retained trial directory')
        out.mkdir(parents=True,mode=0o700)
        atomic_json(out/'review.json',review)
    with locked(out), (out/'journal.jsonl').open('a') as log:
        os.chmod(out/'journal.jsonl',0o600)
        def event(value):
            log.write(json.dumps({'time':time.time(),**value})+'\n');log.flush();os.fsync(log.fileno())
            if value.get('state')!='physical-backup-read' or value.get('blocks',0)%256==0:
                print(json.dumps(value),flush=True)
        device=Phase6SDP();media=None
        try:
            media=PhysicalMedia(device,args.backup,digest,event=event)
            media.inspect(journal_trial_recovery=args.recover)
            media.authorize_journal_trial(approved=True)
            if not args.recover:
                # The transaction is a journal encoding fixture only. Its OS
                # target is never authorized or passed to the write engine.
                tx=Transaction([Change(2048,ERASED,b'qualification'+ERASED[13:],'stage-images')],digest)
                for slot,generation,pending in ((0,1,False),(1,2,True)):
                    page=journal_page(tx,generation,0,pending)
                    media.write_journal(slot,page)
                    require(decode_journal(media.read_journal(slot),tx)==(generation,0,pending),
                            'physical journal record does not match trial')
                event({'state':'both-journals-verified'})
            for block in (258,259):
                media.erase_block(block)
                require(media.read_block(block)==ERASED,'original journal bytes not restored')
            event({'state':'journal-bytes-restored'})
            media.inspect()  # all 4096 blocks, not just the changed records
            report={**review,'result':'PASS complete original NAND fingerprint restored',
                    'nand_blocks_changed_during_trial':[258,259],
                    'os_or_bootloader_changed':False,'full_dual_install_qualified':False}
            atomic_json(out/'qualification.json',report)
            event({'state':'trial-complete','result':report['result']})
        except Exception as error:
            event({'state':'trial-stopped','error':str(error),'automatic_retry':False})
            raise
        finally:
            if media:media.close()
            device.close()


if __name__=='__main__':main()

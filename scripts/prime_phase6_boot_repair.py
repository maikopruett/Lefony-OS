#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retained repair of the exact Phase 6 metadata[0]/[34] bootstream defect.

Only the two ROM boot streams change. A fresh complete snapshot, a completed
original install review, its recovery backup, and signed installed images are
required. No reset, automatic retry, new layout, or public installer endpoint.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import time
import zlib

from prime_dual_boot_contract import require, sha, canonical, select_record, verify_descriptor
from prime_dual_boot_transaction import Change, Transaction, Engine, JOURNAL_BLOCKS
from prime_dual_installer import atomic_json, locked
from prime_dual_physical import PhysicalMedia, model, RAW_BLOCK
from prime_phase6_install_trial import inspected_engine, snapshot_verified
from prime_phase6_transport import Phase6SDP


def completed_install(review, pages, backup_digest):
    require(review['purpose']=='phase6-stock-install-trial' and
            review['bundle']['backup_sha256']==backup_digest.hex(), 'foreign install review')
    mode='add-hp' if review['bundle'].get('source_profile')=='lefony-menu1' else 'migrate'
    identity=sha(canonical({'schema':1,'mode':mode,'backup':backup_digest.hex(),
                            'changes':review['changes']}))
    require(identity.hex()==review['transaction'], 'install review identity mismatch')
    require(len(pages)==2,'both completed install journals required')
    states=[]
    for page in pages:
        require(len(page)==2048, 'incomplete install journal')
        magic,schema,generation,index,pending,txid=struct.unpack_from('<4s4I32s',page)
        require(magic==b'LFJ5' and schema==1 and generation>0 and
                index<=len(review['changes']) and pending in (0,1) and
                (not pending or index<len(review['changes'])) and txid==identity and
                page[52:2044]==b'\xff'*1992 and
                struct.unpack_from('<I',page,2044)[0]==zlib.crc32(page[:2044]),
                'invalid original installation journal')
        states.append((generation,index,pending))
    require(states[0][0]!=states[1][0] or pages[0]==pages[1],'conflicting original journals')
    require(max(states)[1:]==(len(review['changes']),0),'original installation is not completely verified')
    return identity


def plan(current, backup, backup_digest, uboot, public_key, install_review):
    current,backup,uboot=map(Path,(current,backup,uboot))
    require(model.file_hash(backup)==backup_digest,'recovery backup hash mismatch')
    bad=model.factory_inventory(backup)
    require(model.factory_inventory(current)==bad,'current factory inventory changed')
    review=json.loads(Path(install_review).read_text())
    require(uboot.resolve()==Path(review['bundle']['uboot']).resolve(), 'different bootloader from install review')
    stream=bytes(1024)+uboot.read_bytes()
    require(stream[1024:1028]==bytes.fromhex('d1002040'),'unsupported bootloader IVT')
    pages=(len(stream)+2047)//2048;stream=stream.ljust(pages*2048,b'\xff')
    changes=[];routes={b:model.read_block(current,b) for b in (*range(4),*range(240,256))}
    with model.NativeBCH() as native:
        original=completed_install(review,[model.payload(model.read_block(current,b)[:2112],native)
                                           for b in JOURNAL_BLOCKS],backup_digest)
        records=[model.payload(model.read_block(current,b)[:2112],native) for b in (256,257)]
        selected=select_record(records)
        require(selected['state']=='committed','installed layout is not committed')
        descriptor=selected['descriptor'];checked=verify_descriptor(descriptor,public_key)
        images={name:model.read_image(current,name,size,bad,native)
                for name,(size,_) in checked['images'].items()}
        verify_descriptor(descriptor,public_key,images)
        for block in range(4):
            fcb,errors=model.decode_fcb(routes[block][:2112]);geometry=model.fcb_layout(fcb)
            require(not any(errors) and geometry.chunks==model.BOOT_ECC.chunks and
                    geometry.marker_metadata_index==34 and
                    struct.unpack_from('<4I',fcb,0x68)==(240*64,248*64,pages,pages),
                    'unsupported ROM route for marker repair')
        old=model.Layout(0x03241080,0x08401080)
        reviewed={c['block']:c for c in review['changes']}
        # Repair the secondary copy first. Retain each entire before-image;
        # neither copy is accepted merely because its first page is intact.
        for name in ('boot_secondary','boot_primary'):
            at=0;decoded=bytearray()
            for block in model.capacity(name,len(stream),bad):
                before=routes[block]
                require(block in reviewed and sha(before).hex()==reviewed[block]['after'],
                        'installed boot copy differs from completed review')
                after=bytearray(b'\xff'*RAW_BLOCK)
                for page in range(64):
                    offset=page*2112
                    if at>=len(stream):
                        require(before[offset:offset+2112]==b'\xff'*2112,'occupied bootstream tail')
                        continue
                    decoded.extend(model.payload(before[offset:offset+2112],native,old))
                    data,aux=model.BOOT_ECC.swap_marker(stream[at:at+2048],b'\xff'*36)
                    after[offset:offset+2112]=model.BOOT_ECC.encode(data,aux,native)
                    at+=2048
                require(before!=after,'boot copy already repaired; use its retained session to resume')
                changes.append(Change(block,before,bytes(after),'stage-recovery'))
                routes[block]=bytes(after)
            require(bytes(decoded)==stream,'not the exact metadata-zero bootstream defect')
        model.verify_routes_reader(lambda b:routes[b],uboot,bad,native)
    return Transaction(changes,backup_digest,mode='repair-boot'),original


def prepare(current, backup, digest, uboot, public_key, install_review, output):
    output=model.private_output(Path(output))
    require(not output.exists(),'choose a new retained repair directory')
    tx,original=plan(current,backup,digest,uboot,public_key,install_review)
    output.mkdir(parents=True,mode=0o700)
    candidate=output/'candidate.raw';shutil.copyfile(current,candidate)
    with candidate.open('r+b') as f:
        for c in tx.changes:f.seek(c.block*RAW_BLOCK);f.write(c.after)
        f.flush();os.fsync(f.fileno())
    atomic_json(output/'review.json',{'schema':1,'purpose':'phase6-boot-marker-repair',
        'transaction':tx.id.hex(),'original_transaction':original.hex(),
        'current':str(Path(current).resolve()),'current_sha256':model.file_hash(current).hex(),
        'backup':str(Path(backup).resolve()),'backup_sha256':digest.hex(),
        'uboot':str(Path(uboot).resolve()),'uboot_sha256':model.file_hash(uboot).hex(),
        'public_key':str(Path(public_key).resolve()),'public_key_sha256':model.file_hash(public_key).hex(),
        'install_review':str(Path(install_review).resolve()),
        'candidate_sha256':model.file_hash(candidate).hex(),
        'changes':[c.identity() for c in tx.changes]})
    return tx


def run(output, *, approved=False, resume=False):
    require(approved is True,'explicit physical boot repair required')
    output=model.private_output(Path(output));review=json.loads((output/'review.json').read_text())
    require(review['purpose']=='phase6-boot-marker-repair','unsupported repair review')
    for field in ('current','backup','uboot','public_key'):
        require(model.file_hash(review[field]).hex()==review[field+'_sha256'],'retained repair input changed')
    tx,original=plan(review['current'],review['backup'],bytes.fromhex(review['backup_sha256']),
                     review['uboot'],review['public_key'],review['install_review'])
    require(tx.id.hex()==review['transaction'] and original.hex()==review['original_transaction'] and
            [c.identity() for c in tx.changes]==review['changes'],'repair review changed')
    require(model.file_hash(output/'candidate.raw').hex()==review['candidate_sha256'],'offline candidate changed')
    with locked(output),(output/'events.jsonl').open('a') as log:
        def event(value):
            log.write(json.dumps({'time':time.time(),**value})+'\n');log.flush();os.fsync(log.fileno())
            if value.get('state') not in ('physical-backup-read','final-device-readback') or value.get('blocks',0)%512==0:
                print(json.dumps(value),flush=True)
        device=Phase6SDP();media=None
        try:
            media=PhysicalMedia(device,review['backup'],bytes.fromhex(review['backup_sha256']),
                initial=review['current'],initial_digest=bytes.fromhex(review['current_sha256']),event=event)
            inspected_engine(media,tx,review['uboot'],resume=resume).run()
            media.verify_recovery_barrier(tx)
            digest=snapshot_verified(media,tx,output/'verified-nand.raw')
            result={'state':'physical-boot-repair-verified','sha256':digest,
                    'transaction':tx.id.hex(),'original_transaction':original.hex(),
                    'changed_boot_blocks':len(tx.changes),'blocks_verified':4096,'boot_confirmed':False}
            atomic_json(output/'qualification.json',result);event(result);return result
        except Exception as error:
            event({'state':'stopped','error':str(error),'automatic_retry':False});raise
        finally:
            if media:media.close()
            device.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--approved',action='store_true');p.add_argument('--resume',action='store_true')
    p.add_argument('--prepare-only',action='store_true')
    for name in ('current','backup','uboot','public-key','install-review'):p.add_argument('--'+name,type=Path)
    p.add_argument('--backup-sha256')
    a=p.parse_args()
    if a.prepare_only:
        require(all((a.current,a.backup,a.uboot,a.public_key,a.install_review,a.backup_sha256)), 'all preparation inputs required')
        prepare(a.current,a.backup,bytes.fromhex(a.backup_sha256),a.uboot,a.public_key,a.install_review,a.output)
    else:run(a.output,approved=a.approved,resume=a.resume)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private, retained update of an already verified layout-5 installation.

Only boot streams, their FCB page counts, Lefony/rescue and signed descriptors
may change. HP, applications, preferences, geometry and release identity are
preserved. Preparation is offline; running requires an inspected RAM recovery
transport and a fresh complete source capture. No automatic reset or retry.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import time
import zlib

from prime_dual_boot_contract import (require, sha, canonical, load_layout,
    select_record, verify_descriptor, sign_descriptor, record)
from prime_dual_boot_transaction import Change, Transaction, JOURNAL_BLOCKS
from prime_dual_installer import atomic_json, locked
from prime_dual_physical import PhysicalMedia, model as m, RAW_BLOCK
from prime_phase6_install_trial import inspected_engine, snapshot_verified
from prime_phase6_transport import Phase6SDP
from prime_nand_image import encode_fcb, checksum


def completed_owner(review, pages):
    """Retire only the complete transaction represented by the retained review."""
    modes = {'phase6-boot-marker-repair':'repair-boot', 'dual-refresh':'refresh-dual'}
    require(review.get('purpose') in modes, 'unsupported previous transaction')
    identity = sha(canonical({'schema':1, 'mode':modes[review['purpose']],
        'backup':review['backup_sha256'], 'changes':review['changes']}))
    require(identity.hex() == review['transaction'], 'previous review identity mismatch')
    require(len(pages)==2, 'both previous journals required')
    states=[]
    for page in pages:
        require(len(page)==2048, 'short previous journal')
        magic,schema,generation,index,pending,owner=struct.unpack_from('<4s4I32s',page)
        require(magic==b'LFJ5' and schema==1 and owner==identity and generation>0 and
            index<=len(review['changes']) and pending in (0,1) and
            (not pending or index<len(review['changes'])) and
            page[52:2044]==b'\xff'*1992 and
            struct.unpack_from('<I',page,2044)[0]==zlib.crc32(page[:2044]),
            'invalid previous journal')
        states.append((generation,index,pending))
    require(states[0][0]!=states[1][0] or pages[0]==pages[1], 'conflicting previous journals')
    require(max(states)[1:]==(len(review['changes']),0), 'previous transaction incomplete')
    return identity


def source_images(source, public_key, native, bad):
    selected=select_record([m.payload(m.read_block(source,b)[:2112],native) for b in (256,257)])
    require(selected['state']=='committed', 'committed dual source required')
    checked=verify_descriptor(selected['descriptor'],public_key)
    images={n:m.read_image(source,n,size,bad,native) for n,(size,_) in checked['images'].items()}
    verify_descriptor(selected['descriptor'],public_key,images)
    return selected,checked,images


def plan(source, old_uboot, uboot, lefony, public_key, descriptor, previous_review):
    source,old_uboot,uboot,lefony=map(Path,(source,old_uboot,uboot,lefony))
    require(source.stat().st_size==4096*RAW_BLOCK, 'full source capture required')
    digest=m.file_hash(source);bad=m.factory_inventory(source);_,regions=load_layout()
    changes=[];routes={b:m.read_block(source,b) for b in (*range(4),*range(240,256))}
    previous=json.loads(Path(previous_review).read_text())
    with m.NativeBCH() as native:
        old_stream=m.verify_routes(source,old_uboot,bad,native)
        completed_owner(previous,[m.payload(m.read_block(source,b)[:2112],native) for b in JOURNAL_BLOCKS])
        for c in previous['changes']:
            # OS use may modify filesystems/preferences, but these operations
            # never own those regions. Every previous target must still match.
            require(sha(m.read_block(source,c['block'])).hex()==c['after'], 'previous target changed')
        selected,old,images=source_images(source,public_key,native,bad)
        images['lefony_image']=images['rescue']=lefony.read_bytes()
        new=verify_descriptor(descriptor,public_key,images)
        require(new['release']==old['release']+1, 'refresh must advance release exactly once')
        stream=bytes(1024)+uboot.read_bytes();pages=(len(stream)+2047)//2048
        stream=stream.ljust(pages*2048,b'\xff')
        require(stream[1024:1028]==bytes.fromhex('d1002040'), 'unsupported new NAND IVT')
        # FCB page counts change first. The old image remains executable when
        # ROM copies a longer erased tail. Shrinking/truncating it is forbidden.
        require(len(stream)>=len(old_stream), 'refresh cannot shrink ROM copy length')
        for name in ('boot_primary','boot_secondary'):
            decoded=bytearray()
            for block in m.capacity(name,len(stream),bad):
                raw=routes[block]
                for at in range(0,RAW_BLOCK,2112):
                    if len(decoded)>=len(stream):break
                    decoded.extend(m.payload(raw[at:at+2112],native,m.BOOT_ECC))
            require(bytes(decoded)==old_stream.ljust(len(stream),b'\xff'), 'old boot tail is occupied')

        def change(block,after,phase):
            before=m.read_block(source,block)
            if before!=after:changes.append(Change(block,before,after,phase))
            if block in routes:routes[block]=after

        for block in (3,2,1,0):
            before=routes[block];fcb,errors=m.decode_fcb(before[:2112])
            require(not any(errors) and before[2112:]==m.ERASED[2112:], 'unsupported FCB copy')
            fcb=bytearray(fcb);struct.pack_into('<2I',fcb,0x70,pages,pages)
            struct.pack_into('<I',fcb,0,checksum(fcb))
            change(block,encode_fcb(fcb,covered_metadata=before[:32])+m.ERASED[2112:],'redirect-rom')

        def image(name,data,codec,phase):
            region=regions[name]
            positions=([region.first] if name.startswith('layout_') else m.capacity(name,len(data),bad))
            require(not set(positions)&bad, 'bad metadata slot')
            blocks={b:bytearray(m.ERASED) for b in range(region.first,region.end) if b not in bad}
            at=0
            for block in positions:
                for page in range(64):
                    if at>=len(data):break
                    chunk=data[at:at+2048].ljust(2048,b'\xff')
                    payload,aux=codec.swap_marker(chunk,b'\xff'*(36 if codec is m.BOOT_ECC else 10))
                    blocks[block][page*2112:(page+1)*2112]=codec.encode(payload,aux,native);at+=2048
            require(at>=len(data),'image exceeds region')
            for block,raw in blocks.items():change(block,bytes(raw),phase)

        # With both FCB counts safe for old and new images, complete and verify
        # secondary before touching primary. Every prefix retains a ROM route.
        for name in ('boot_secondary','boot_primary'):image(name,stream,m.BOOT_ECC,'stage-recovery')
        m.verify_routes_reader(lambda b:routes[b],uboot,bad,native)
        for name in ('lefony_image','rescue'):image(name,images[name],m.ECC,'stage-images')
        identity=sha(digest+descriptor+sha(stream))
        for name in ('layout_secondary','layout_primary'):
            image(name,record(selected['generation']+1,'committed',identity,descriptor),m.ECC,'commit-layout')
    require(m.file_hash(source)==digest,'source changed during planning')
    return Transaction(changes,digest,mode='refresh-dual'),bad


def prepare(source,old_uboot,uboot,lefony,public_key,private_key,previous_review,output):
    output=m.private_output(Path(output));require(not output.exists(),'new retained refresh directory required')
    with m.NativeBCH() as native:
        _,old,images=source_images(source,public_key,native,m.factory_inventory(source))
    images['lefony_image']=images['rescue']=Path(lefony).read_bytes()
    descriptor=sign_descriptor(images,old['release']+1,private_key)
    tx,bad=plan(source,old_uboot,uboot,lefony,public_key,descriptor,previous_review)
    inputs={n:str(Path(p).resolve()) for n,p in dict(source=source,old_uboot=old_uboot,
        uboot=uboot,lefony=lefony,public_key=public_key,previous_review=previous_review).items()}
    output.mkdir(parents=True,mode=0o700)
    (output/'descriptor.bin').write_bytes(descriptor)
    atomic_json(output/'review.json',{'schema':1,'purpose':'dual-refresh','transaction':tx.id.hex(),
        'backup_sha256':tx.backup_digest.hex(),'inputs':inputs,
        'hashes':{n:m.file_hash(p).hex() for n,p in inputs.items()},
        'descriptor_sha256':sha(descriptor).hex(),'bad_blocks':sorted(bad),
        'changes':[c.identity() for c in tx.changes]})
    return tx,bad


def reviewed_plan(output):
    output=Path(output);review=json.loads((output/'review.json').read_text())
    require(review['purpose']=='dual-refresh','unsupported refresh review')
    for name,path in review['inputs'].items():
        require(m.file_hash(path).hex()==review['hashes'][name],'retained refresh input changed: '+name)
    descriptor=(output/'descriptor.bin').read_bytes()
    require(sha(descriptor).hex()==review['descriptor_sha256'],'reviewed descriptor changed')
    tx,bad=plan(**review['inputs'],descriptor=descriptor)
    require(tx.id.hex()==review['transaction'] and tx.backup_digest.hex()==review['backup_sha256'] and
        [c.identity() for c in tx.changes]==review['changes'] and sorted(bad)==review['bad_blocks'],
        'refresh review changed')
    return tx,bad,review['inputs']


def run(output,*,approved=False,resume=False):
    require(approved is True,'explicit physical refresh required')
    output=m.private_output(Path(output));tx,_,inputs=reviewed_plan(output)
    with locked(output),(output/'events.jsonl').open('a') as log:
        def event(value):
            log.write(json.dumps({'time':time.time(),**value})+'\n');log.flush();os.fsync(log.fileno())
            if value.get('state') not in ('physical-backup-read','final-device-readback') or value.get('blocks',0)%512==0:
                print(json.dumps(value),flush=True)
        device=Phase6SDP();media=None
        try:
            media=PhysicalMedia(device,inputs['source'],tx.backup_digest,event=event)
            inspected_engine(media,tx,inputs['uboot'],resume=resume).run()
            media.verify_recovery_barrier(tx)
            digest=snapshot_verified(media,tx,output/'verified-nand.raw')
            result={'state':'physical-refresh-verified','transaction':tx.id.hex(),'sha256':digest,
                'blocks_verified':4096,'changed_blocks':len(tx.changes),'boot_confirmed':False}
            atomic_json(output/'qualification.json',result);event(result);return result
        except Exception as error:
            event({'state':'stopped','error':str(error),'automatic_retry':False});raise
        finally:
            if media:media.close()
            device.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--approved',action='store_true');p.add_argument('--resume',action='store_true')
    for name in ('source','old-uboot','uboot','lefony','public-key','private-key','previous-review'):
        p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.prepare_only:
        fields=('source','old_uboot','uboot','lefony','public_key','private_key','previous_review')
        require(all(getattr(a,n) for n in fields),'all preparation inputs required')
        tx,_=prepare(**{n:getattr(a,n) for n in fields},output=a.output)
        print(json.dumps({'transaction':tx.id.hex(),'changed_blocks':len(tx.changes)}))
    else:run(a.output,approved=a.approved,resume=a.resume)

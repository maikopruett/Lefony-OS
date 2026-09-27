#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retained desktop reviews and resumable offline dual-install sessions.

Physical migration has no executor here. USB identity/firmware version never
stand in for a verified layout, signed payloads or an external full backup.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import sys
import time

from prime_dual_boot_contract import load_layout, layout_digest, require, INPUTS, ContractError

ROOT=Path(__file__).resolve().parents[1]
CONTRACT_PATH=ROOT/'native/prime_g2/installer_contract.json'


def contract():
    data=json.loads(CONTRACT_PATH.read_text())
    layout,regions=load_layout()
    require(data['schema']==1 and data['layout_id']==layout['layout_id'] and
            data['layout_sha256']==layout_digest().hex() and
            data['physical_migration_allowed'] is False,'installer contract changed without qualification')
    require(data['hp_profile']==layout['hp_profile'] and
            data['hp_images']==[{'bytes':INPUTS['HPPrime.img'][0],'sha256':INPUTS['HPPrime.img'][1]}] and
            data['raw_backup_bytes']==4096*2112*64 and
            data['hp_filesystem_bytes']==regions['hp_filesystem'].count*131072 and
            data['lefony_app_bytes']==regions['lefony_apps'].count*131072,
            'installer compatibility or storage contract differs from the qualified layout')
    return data


def decode_native_info(raw):
    c=contract()
    require(len(raw)==64,'incomplete installer identity')
    magic,version,model,layout,flags,release,blocks,erase=struct.unpack_from('<8I',raw)
    require((magic,version,model,blocks,erase)==(c['native_info']['magic'],1,c['model'],4096,131072),
            'unknown installer protocol/model/geometry')
    digest=raw[32:].hex()
    if layout==0:
        require(flags==release==0 and raw[32:]==bytes(32),'invalid legacy identity')
        state='lefony-legacy'
    else:
        require(layout==5 and flags in (1,3) and digest==c['layout_sha256'] and
                bool(release)==bool(flags&2),'unknown or contradictory layout identity')
        state='dual-boot' if flags==3 else 'recovery-required'
    return {'state':state,'layout':layout,'release':release,'layout_sha256':digest,
            'legacy_writes_allowed':layout==0,'physical_migration_allowed':False}


def inspect_native(device):
    """Read-only optional capability. Unsupported is distinct from corruption."""
    cap=device.read(0x4e,length=16)
    require(len(cap)==16 and struct.unpack_from('<2I',cap)==(0x3156444c,1),'invalid native capabilities')
    if not struct.unpack_from('<I',cap,8)[0]&16:
        return {'state':'legacy-unreported','legacy_writes_allowed':True,'physical_migration_allowed':False}
    return decode_native_info(device.read(0x4e,value=4,length=64))


def require_legacy_native(device):
    info=inspect_native(device)
    require(info['legacy_writes_allowed'],'This shared layout requires a compatible dual-boot installer; legacy writes are disabled.')
    return info


def atomic_json(path,value):
    temporary=path.with_suffix('.next')
    with temporary.open('w') as f:
        os.chmod(temporary,0o600);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


@contextmanager
def locked(session):
    with (session/'lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('This installer session is already running.')
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def bundle_paths(bundle):
    fields={'backup','candidate','uboot','archive','recreated','public_key','backup_sha256'}
    legacy=bundle.get('source_profile')=='lefony-menu1'
    extra={'source_profile','hp_backup','hp_backup_sha256'} if legacy else set()
    require(set(bundle)==fields|extra,'unexpected migration bundle fields')
    paths={name:Path(bundle[name]).resolve() for name in fields-{'backup_sha256'}}
    if legacy:paths.update(hp_backup=Path(bundle['hp_backup']).resolve(),hp_backup_sha256=bundle['hp_backup_sha256'])
    digest=bytes.fromhex(bundle['backup_sha256'])
    require(len(digest)==32,'complete backup digest required')
    return paths,digest


def migration():
    # Importing this path gives access only to the separately guarded file
    # executor, never a physical NAND transport disguised as an emulator.
    if str(ROOT/'vm') not in sys.path:sys.path.insert(0,str(ROOT/'vm'))
    import prime_dual_migration
    return prime_dual_migration


def checked_plan(bundle,priority):
    require(priority in ('lefony','hp'),'explicit priority required')
    paths,digest=bundle_paths(bundle)
    if bundle.get('source_profile')=='lefony-menu1':
        from prime_dual_legacy import build_plan
    else:build_plan=migration().build_plan
    tx,bad=build_plan(**paths,expected_backup=digest,priority=0 if priority=='lefony' else 1)
    return tx,bad,paths,digest


def normalized_bundle(bundle,paths,digest):
    result={k:str(v) for k,v in paths.items()}|{'backup_sha256':digest.hex()}
    if bundle.get('source_profile'):result['source_profile']=bundle['source_profile']
    return result


def prepare(bundle,session,*,mode,priority,now=None):
    require(mode=='keep-hp','This retained migration session supports Keep HP only; replacement uses the existing explicit installer.')
    require(priority in ('lefony','hp'),'choose the priority OS explicitly')
    session=migration().private_output(Path(session))
    require(not session.exists(),'choose a new retained session directory')
    tx,bad,paths,digest=checked_plan(bundle,priority)
    parent=session.parent
    while not parent.exists():parent=parent.parent
    require(shutil.disk_usage(parent).free>=contract()['minimum_free_bytes'],'Not enough free disk space for backups, migration and rollback.')
    now=time.time() if now is None else now
    session.mkdir(parents=True,mode=0o700)
    normalized=normalized_bundle(bundle,paths,digest)
    approval=secrets.token_hex(32)
    review={'schema':1,'mode':mode,'priority':priority,'phase':'review','execution':'offline-emulator',
            'physical_install_allowed':False,'transaction':tx.id.hex(),'bundle':normalized,
            'backup':{'path':str(paths['backup']),'sha256':digest.hex(),'bytes':contract()['raw_backup_bytes']},
            'layout_sha256':contract()['layout_sha256'],'bad_blocks':sorted(bad),
            'changed_blocks':len(tx.changes),'created_at':now,'approval_expires':now+300,
            'approval_sha256':hashlib.sha256(approval.encode()).hexdigest(),'approval_used':False}
    atomic_json(session/'review.json',review)
    return review|{'approval':approval}


def run(session,*,approval=None,resume=False,emulator=False,now=None):
    require(emulator is True,'Physical migration is not qualified; no calculator operation is available.')
    session=migration().private_output(Path(session))
    require(session.is_dir(),'retained session is missing')
    with locked(session):
        review=json.loads((session/'review.json').read_text())
        require(review['schema']==1 and review['execution']=='offline-emulator' and
                review['physical_install_allowed'] is False and review['mode']=='keep-hp' and
                review['priority'] in ('lefony','hp'),'unknown retained review')
        use_wall_clock = now is None
        now=time.time() if now is None else now
        if resume:
            require(review['approval_used'] and review['phase'] in ('running','reconnect','verified'),
                    'No approved migration to resume; inspect the retained review.')
        else:
            require(review['phase']=='review' and not review['approval_used'] and now<review['approval_expires'] and
                    isinstance(approval,str) and secrets.compare_digest(hashlib.sha256(approval.encode()).hexdigest(),review['approval_sha256']),
                    'Review expired or already used; no operation started.')
        tx,_,paths,digest=checked_plan(review['bundle'],review['priority'])
        require(tx.id.hex()==review['transaction'] and review['layout_sha256']==contract()['layout_sha256'],
                'Reviewed inputs changed; review again before writing.')
        if not resume:
            require((time.time() if use_wall_clock else now) < review['approval_expires'],
                    'Review expired during input verification; no operation started.')
        # Consume before execution; disconnect/ambiguous result can only resume
        # this same transaction, never obtain another automatic write approval.
        review.update(approval_used=True,phase='running');atomic_json(session/'review.json',review)
        try:
            target=session/'migration'
            result=migration().execute(**paths,expected_backup=digest,output=target,
                resume=resume and target.exists(),priority=0 if review['priority']=='lefony' else 1)
            review.update(phase='verified',result=result,boot_confirmed=False)
        except Exception as error:
            review.update(phase='recovery-required' if isinstance(error,ContractError) else 'reconnect')
            atomic_json(session/'review.json',review)
            raise
        atomic_json(session/'review.json',review)
        return review


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('review');p.add_argument('--bundle',type=Path,required=True);p.add_argument('--session',type=Path,required=True)
    p.add_argument('--mode',choices=('keep-hp','replace-hp'),required=True);p.add_argument('--priority',choices=('lefony','hp'),required=True)
    for name in ('run','resume'):
        p=sub.add_parser(name);p.add_argument('--session',type=Path,required=True);p.add_argument('--emulator',action='store_true')
        if name=='run':p.add_argument('--approval',required=True)
    sub.add_parser('contract')
    a=parser.parse_args()
    if a.action=='contract':result=contract()
    elif a.action=='review':result=prepare(json.loads(a.bundle.read_text()),a.session,mode=a.mode,priority=a.priority)
    else:result=run(a.session,approval=getattr(a,'approval',None),resume=a.action=='resume',emulator=a.emulator)
    print(json.dumps(result,indent=2))

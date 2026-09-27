#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local companion bridge for explicitly configured development dual bundles.

Browser requests contain choices and opaque session IDs only. All paths, keys,
recovery assets and source pins come from an operator-created local config.
This does not publish a release or change the layout's release qualification.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import time
import uuid
from prime_dual_boot_contract import require
from prime_dual_installer import (atomic_json,checked_plan,normalized_bundle,locked,contract,inspect_native)
from prime_dual_physical import model
from prime_phase6_transport import Phase6SDP
from prime_phase6_capture import capture
from prime_phase6_recovery_entry import enter
from prime_phase6_install_trial import run as install
from prime_phase6_restore import run as restore

ROOT=Path(__file__).resolve().parents[1]


def configure(bundle,binary,imx,state,output):
    data=json.loads(Path(bundle).read_text())
    _,_,paths,digest=checked_plan(data,'lefony')
    state=model.private_output(Path(state));state.mkdir(parents=True,exist_ok=True,mode=0o700)
    files=[p for directory in ('scripts','vm') for p in (ROOT/directory).rglob('*')
           if p.is_file() and p.suffix in ('.py','.c','.h') and '__pycache__' not in p.parts]
    config={'schema':1,'development':True,'runtime':str(ROOT),'state':str(state),
            'bundle':normalized_bundle(data,paths,digest),
            'binary':str(Path(binary).resolve()),'imx':str(Path(imx).resolve()),
            'binary_sha256':model.file_hash(binary).hex(),'imx_sha256':model.file_hash(imx).hex(),
            'sources':{str(p.relative_to(ROOT)):model.file_hash(p).hex() for p in files}}
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    atomic_json(output,config)
    return {'configured':True,'development':True}


def load(path):
    c=json.loads(Path(path).read_text())
    require(c['schema']==1 and c['development'] is True and Path(c['runtime'])==ROOT,'unsupported companion runtime')
    for name,digest in c['sources'].items():
        p=(ROOT/name).resolve()
        require(p.is_relative_to(ROOT) and model.file_hash(p).hex()==digest,'configured runtime changed; reconfigure locally')
    for field in ('binary','imx'):
        require(model.file_hash(c[field]).hex()==c[field+'_sha256'],'configured recovery asset changed')
    c['state']=model.private_output(Path(c['state']))
    return c


def session(c,identity):
    require(isinstance(identity,str) and re.fullmatch('[a-f0-9]{32}',identity),'invalid session identity')
    p=c['state']/identity
    require(p.is_dir(),'retained session missing')
    return p,json.loads((p/'state.json').read_text())


def summary(s):
    fields=('id','state','action','priority','transaction','changedBlocks','backupDirectory',
            'confirmed','expectedBoots','message','resetRequired','approvalExpires','release')
    return {k:s[k] for k in fields if k in s}|{'development':True}


def emit(value):print(json.dumps(value),flush=True)


def candidate_release(bundle):
    with model.NativeBCH() as native:
        pages=[model.payload(model.read_block(bundle['candidate'],b)[:2112],native) for b in (256,257)]
        selected=model.select_record(pages)
        require(selected['state']=='committed','candidate is not committed')
        return model.verify_descriptor(selected['descriptor'],bundle['public_key'])['release']


def current_state(c):
    current=c['state']/'current.json'
    if not current.exists():return None
    p,s=session(c,json.loads(current.read_text())['id'])
    # A process death releases the OS lock. Report a stopped job explicitly;
    # never leave the browser polling a persisted "working" state forever.
    if s['state'] in ('working','preparing'):
        with (c['state']/'lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return summary(s)
            try:
                s=json.loads((p/'state.json').read_text())
                if s['state'] in ('working','preparing'):
                    s.update(state='reconnect' if s.get('approvalUsed') else 'recovery-required',
                             message='The companion stopped. Reconnect and inspect the retained operation.'
                             if s.get('approvalUsed') else 'Backup preparation stopped. Prepare a new review.')
                    atomic_json(p/'state.json',s)
            finally:fcntl.flock(lock,fcntl.LOCK_UN)
    return summary(s)


def review(c,request):
    require(set(request)=={'priority','action'} and request['priority'] in ('lefony','hp') and
            request['action'] in ('install','restore-original','restore-hp'),'invalid dual review choices')
    identity=uuid.uuid4().hex;p=c['state']/identity;p.mkdir(mode=0o700)
    s={'id':identity,'state':'preparing','action':request['action'],'priority':request['priority'],
       'backupDirectory':str(p),'confirmed':[]}
    def save():atomic_json(p/'state.json',s)
    save();atomic_json(c['state']/'current.json',{'id':identity})
    try:
        bundle=c['bundle'].copy()
        require(shutil.disk_usage(c['state']).free>=contract()['minimum_free_bytes'],
                'insufficient space for retained backups and restoration')
        # Validate prerequisites before a working calculator leaves its OS.
        checked_plan(bundle,request['priority'])
        enter(c['binary'],c['imx'],p,event=emit)
        refs=[Path(bundle['backup'])]
        refs.extend(sorted(c['state'].glob('*/operation/verified-nand.raw'),
                           key=lambda p:p.stat().st_mtime,reverse=True)[:3])
        d=Phase6SDP()
        try:receipt=capture(d,p/'before.raw',refs,event=emit)
        finally:d.close()
        if request['action']=='install':
            if bundle.get('source_profile')!='lefony-menu1':
                require(receipt['sha256']==bundle['backup_sha256'],
                        'HP data changed; prepare a fresh logical archive before installation')
            bundle.update(backup=str(p/'before.raw'),backup_sha256=receipt['sha256'])
            tx,_,_,_=checked_plan(bundle,request['priority']);s['bundle']=bundle
            s['expectedBoots']=['lefony','hp'];s['release']=candidate_release(bundle)
        else:
            hp=request['action']=='restore-hp'
            require(not hp or 'hp_backup' in bundle,'no retained HP recovery backup configured')
            target=bundle['hp_backup' if hp else 'backup'];digest=bundle['hp_backup_sha256' if hp else 'backup_sha256']
            tx,bad=model.build_restore_plan(p/'before.raw',target,bytes.fromhex(digest))
            with model.NativeBCH() as native:model.verify_routes(p/'before.raw',bundle['uboot'],bad,native)
            s.update(target=target,target_sha256=digest,uboot=bundle['uboot'])
            s['expectedBoots']=['hp' if hp or bundle.get('source_profile')!='lefony-menu1' else 'lefony']
        approval=secrets.token_hex(32)
        s.update(state='review',transaction=tx.id.hex(),changedBlocks=len(tx.changes),
                 approvalHash=hashlib.sha256(approval.encode()).hexdigest(),approvalExpires=time.time()+300,
                 approvalUsed=False,resetRequired=False)
        save()
        return summary(s)|{'approval':approval}
    except Exception as e:
        s.update(state='recovery-required',message=str(e));save();raise


def execute(c,request,*,resume=False):
    require(set(request)==({'session'} if resume else {'session','approval'}),'invalid execution request')
    p,s=session(c,request['session'])
    if resume:require(s.get('approvalUsed') and s['state'] in ('working','reconnect'),'no interrupted approved job to resume')
    else:
        token=request['approval']
        require(isinstance(token,str) and s['state']=='review' and not s['approvalUsed'] and
                time.time()<s['approvalExpires'] and secrets.compare_digest(
                    hashlib.sha256(token.encode()).hexdigest(),s['approvalHash']), 'approval expired or already used')
    if s['action']=='install':
        tx,_,_,_=checked_plan(s['bundle'],s['priority'])
    else:tx,_=model.build_restore_plan(p/'before.raw',s['target'],bytes.fromhex(s['target_sha256']))
    require(tx.id.hex()==s['transaction'],'reviewed inputs changed')
    if not resume:require(time.time()<s['approvalExpires'],'approval expired during verification')
    s.update(state='working',approvalUsed=True);atomic_json(p/'state.json',s)
    try:
        enter(c['binary'],c['imx'],p,event=emit)
        if s['action']=='install':
            result=install(s['bundle'],p/'operation',priority=s['priority'],approved=True,
                           resume=resume and (p/'operation').exists())
        else:
            result=restore(p/'before.raw',s['target'],bytes.fromhex(s['target_sha256']),s['uboot'],
                           p/'operation',approved=True,resume=resume and (p/'operation').exists())
        s.update(state='verified',result=result,resetRequired=True,
                 message='NAND writing and readback are verified. Restart and confirm the requested OS boots.')
    except Exception as e:
        # Reconnection always re-inspects the same retained plan. Contract
        # failures remain visible; no browser disconnect retries a mutation.
        s.update(state='reconnect',message=str(e));atomic_json(p/'state.json',s);raise
    atomic_json(p/'state.json',s)
    return summary(s)


def dispatch(config,action,request):
    c=load(config)
    if action=='info':
        require(not request,'info accepts no fields')
        return {'available':True,'development':True,'sourceProfile':c['bundle'].get('source_profile','stock-hp'),
                'backupDirectory':str(c['state'])}
    if action=='current':
        require(not request,'current accepts no fields')
        return current_state(c)
    with locked(c['state']):
        if action=='review':return review(c,request)
        if action in ('run','resume'):return execute(c,request,resume=action=='resume')
        if action=='confirm':
            require(set(request)=={'session','os'},'invalid boot confirmation')
            p,s=session(c,request['session']);os_name=request['os']
            require(s['state'] in ('verified','complete') and os_name in s['expectedBoots'],'unexpected boot confirmation')
            if os_name=='lefony':
                from prime_g2_usb_diag import LibUSB
                with LibUSB() as device:identity=inspect_native(device)
                allowed=('dual-boot',) if s['action']=='install' else ('lefony-legacy','legacy-unreported')
                require(identity['state'] in allowed,'running Lefony identity does not match')
                if s['action']=='install':
                    require(identity['release']==s['release'],'running Lefony release differs from reviewed candidate')
            s['confirmed']=sorted(set(s['confirmed'])|{os_name})
            s.update(state='complete' if set(s['confirmed'])==set(s['expectedBoots']) else 'verified',resetRequired=False)
            atomic_json(p/'state.json',s);return summary(s)
        raise ValueError('unsupported dual action')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('configure')
    for name in ('bundle','binary','imx','state','output'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('info','current','review','run','resume','confirm'):
        p=sub.add_parser(name);p.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.action=='configure':result=configure(args.bundle,args.binary,args.imx,args.state,args.output)
        else:
            raw=sys.stdin.read(4097);require(len(raw)<=4096,'request too large')
            request=json.loads(raw or '{}');require(isinstance(request,dict),'object request required')
            result=dispatch(args.config,args.action,request)
        emit({'type':'dual-result','result':result})
    except Exception as error:
        emit({'type':'error','error':str(error)});sys.exit(1)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Partial registry backups and fresh OS repair consent under modeled NAND faults."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import cli
import key_snapshot
import keys_device
from build import digest,identity,write_json
from files_device import FileClient
from keys_device import Client as Keys
from replay import Controls
from runner import exercise
from sdk_notebook_probe import wait_notebook
from signing import openssl,public_der,sign
from workspace import opened


def compare_snapshot(path,original):
    raw=path.read_bytes();info=key_snapshot.inspect(raw);cursor=32
    for offset in range(0,len(original),512):
        source,size,state,reserved=struct.unpack_from('<4I',raw,cursor);cursor+=16
        assert source==offset and size==min(512,len(original)-offset) and not reserved
        assert state==int(offset<2048)
        if not state:
            assert raw[cursor:cursor+size]==original[offset:offset+size];cursor+=size
    assert cursor==len(raw) and info['unreadable_chunks']==4 and info['readable_bytes']==704
    return info


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    firmware=args.firmware.resolve();qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    sources=['vm/test-sdk-key-media.py','vm/test-sdk-minigzip-media.py','vm/test-sdk-documents.py',
        'tests/native/app_document_fixture.cpp','tests/native/app_storage.cpp','tests/native/app_documents.cpp',
        'ports/lefony-prime-g2/apps/native_apps/app.cpp',*['ports/lefony-prime-g2/ion/src/prime_g2/'+n for n in
        ('app_developer_keys.cpp','app_developer_keys.h','app_developer_key_snapshot.cpp','app_developer_key_snapshot.h',
         'app_developer_key_session.cpp','app_developer_key_session.h','app_developer_key_wire.h','app_management.cpp','usb_diagnostics.cpp','littlefs/lfs.c')]]
    report={'schema':1,'status':'running','physical':'not_tested','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),'sources':{n:digest(ROOT/n) for n in sources},'cases':[]}
    write_json(output/'report.json',report)
    def record(name,**value):
        report['cases'].append({'case':name,**value});write_json(output/'report.json',report);print('PASS:',name,flush=True)
    fault=runpy.run_path(str(ROOT/'vm/test-sdk-minigzip-media.py'))['fault']
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-key-media-') as temp:
            root=Path(temp);helper=root/'helper';helper.mkdir()
            fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            project=root/'notebook';shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
            manifest=json.loads((project/'app.json').read_text());manifest.update(id='key-media-note',version='1.0.0');write_json(project/'app.json',manifest)
            bootstrap=root/'bootstrap';(bootstrap/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'sdk/examples/counter/src/main.cpp',bootstrap/'src/main.cpp')
            write_json(bootstrap/'app.json',{'abi':1,'id':'store-counter','name':'Store counter','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
            start=output/'bootstrap.lfapp';shutil.copyfile(cli.package(bootstrap),start)
            private={};public={};fingerprints={}
            for name in ('a','b'):
                private[name]=root/(name+'-private.pem');public[name]=output/(name+'-public.pem')
                private[name].write_bytes(openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'));private[name].chmod(0o600)
                public[name].write_bytes(openssl('pkey','-in',private[name],'-pubout'))
                fingerprints[name]=hashlib.sha256(public_der(public[name])).hexdigest()
            artifact=output/'notebook.lfapp';artifact.write_bytes(sign(cli.package(project,'debug').read_bytes(),private['a']))
            shutil.copyfile(project/'build/app-debug.elf',output/'notebook.elf')
            document=b'LFNOTE1\n2+3\nx^2\n';input_file=root/'document.txt';input_file.write_bytes(document)
            before_app=None;media=None
            with opened(project,'key-media') as (workspace,_):
                for phase in ('seed','fault','cold'):
                    folder=output/phase;folder.mkdir();records=[]
                    if phase=='fault':
                        before=digest(workspace/'nand.overlay')
                        media=json.loads(subprocess.check_output([fixture,'key-media',workspace/'nand.overlay'],text=True,timeout=30))
                        assert digest(workspace/'nand.overlay')==before;write_json(output/'key-media.json',media)
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;keys=Keys(app.transport)
                        def picture(name):
                            time.sleep(.25);path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            with Image.open(path) as frame:frame.save(path.with_suffix('.png'))
                        def proposal(operation,key):
                            client=Keys(app.transport)
                            values={'public_key':public[key],'label':'Key '+key.upper()} if operation=='enroll' else {'fingerprint':fingerprints[key]}
                            client.begin(operation,**values);deadline=time.monotonic()+25
                            while time.monotonic()<deadline and client.bound_status()['state'] in ('preparing','awaiting_usb_ack'):time.sleep(.05)
                            assert client.bound_status()['state']=='awaiting_approval';picture(operation+'-'+key)
                            normal.keys(['ok']);time.sleep(.25);normal.keys([])
                            assert client.wait()['state']=='complete';normal.key('back');app.wait()
                        def command(name,arguments,action=None):
                            pressed=False;out=io.StringIO();err=io.StringIO()
                            def advance(seconds):
                                nonlocal pressed
                                if action and not pressed and keys.status()['state']=='awaiting_approval':
                                    picture(name+'-approval');pressed=True
                                    if action=='clear':fault(normal,media,0)
                                    if action=='move':fault(normal,{**media,'page':media['page']+1},2)
                                    normal.keys(['back' if action=='cancel' else 'ok']);time.sleep(.25);normal.keys([])
                                time.sleep(seconds)
                            old_usb,old_client,argv=keys_device.KeyUSB,keys_device.Client,sys.argv
                            try:
                                keys_device.KeyUSB=lambda:contextlib.nullcontext(app.transport)
                                keys_device.Client=lambda transport,**kwargs:Keys(transport,clock=kwargs.get('clock',time.monotonic),sleep=advance)
                                sys.argv=['lefony-sdk','keys',*map(str,arguments)]
                                with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=cli.main()
                            finally:keys_device.KeyUSB,keys_device.Client,sys.argv=old_usb,old_client,argv
                            value={'exit_status':code,'stdout':out.getvalue(),'stderr':err.getvalue(),'approval_presented':pressed}
                            write_json(folder/(name+'.json'),value)
                            if pressed:picture(name+'-result');normal.key('back');app.wait()
                            assert pressed==bool(action),value
                            return code,json.loads(out.getvalue()) if out.getvalue() else None,err.getvalue()
                        try:
                            normal.key('home');app.wait();normal.key('back');assert app.status()['reserved']&16384
                            if phase=='seed':
                                proposal('enroll','a');proposal('enroll','b');proposal('revoke','b')
                                app.install(artifact.read_bytes(),[public['a']])
                                FileClient(app).import_file('key-media-note','notebook.txt',input_file)
                                assert keys.keys()['serial']==3;record('seed-private-app-document-and-two-key-states')
                            elif phase=='fault':
                                overlay=digest(workspace/'nand.overlay');fault(normal,media,2)
                                destination=folder/'partial.keys';code,result,_=command('backup',['backup-unreadable',destination])
                                assert code==0 and result['status']=='partially_backed_up'
                                snapshot=compare_snapshot(destination,bytes.fromhex(media['original_hex']))
                                assert result['sha256']==snapshot['sha256'] and keys.status()['registry']=='unreadable'
                                assert digest(workspace/'nand.overlay')==overlay
                                record('CLI-read-only-partial-backup-matches-independent-readable-bytes',snapshot=snapshot)
                                code,result,_=command('existing',['repair-unreadable','--public-key',public['a'],'--label','Recovered A','--backup',destination])
                                assert code==1 and result is None and digest(workspace/'nand.overlay')==overlay
                                for action,expected in [('cancel','cancelled'),('clear','failed'),('move','failed')]:
                                    fault(normal,media,2);backup=folder/(action+'.keys')
                                    code,result,_=command(action,['repair-unreadable','--public-key',public['a'],'--label','Recovered A','--backup',backup],action)
                                    assert code==1 and result['state']==expected,result
                                    if action!='cancel':assert result['error']==('registry_fully_readable' if action=='clear' else 'stale_registry'),result
                                    assert compare_snapshot(backup,bytes.fromhex(media['original_hex']))==snapshot
                                    assert digest(workspace/'nand.overlay')==overlay
                                    record('OS-consent-'+action+'-preserves-complete-volume-and-backup')
                                fault(normal,media,2);backup=folder/'repaired.keys'
                                code,result,log=command('repair',['repair-unreadable','--public-key',public['a'],'--label','Recovered A','--backup',backup],'approve')
                                assert code==0 and result['state']=='complete' and fingerprints['a'] in log and snapshot['sha256'] in log,result
                                assert compare_snapshot(backup,bytes.fromhex(media['original_hex']))==snapshot
                                selected=keys.keys();assert selected['serial']==1 and len(selected['keys'])==1 and selected['keys'][0]['fingerprint']==fingerprints['a']
                                record('CLI-backup-and-fresh-physical-OK-repair-with-original-page-still-unreadable')
                            else:
                                assert keys.status()['sequence']==0 and keys.keys()['serial']==1
                                assert [k['fingerprint'] for k in keys.keys()['keys']]==[fingerprints['a']]
                                fault(normal,media,2)
                                entry=next(e for e in app.catalog() if e['id']=='key-media-note')
                                assert channel.command(f"APP OPEN {entry['slot']}")=='OK';wait_notebook(normal,records)
                                picture('cold-notebook');normal.key('home');app.wait();normal.key('back')
                                record('cold-repaired-trust-and-private-notebook-launch')
                            exported=folder/'notebook.txt';FileClient(app).export_file('key-media-note','notebook.txt',exported)
                            assert exported.read_bytes()==document
                        finally:
                            if media:fault(normal,media,0)
                            normal.close()
                    runtime=exercise(start,qemu,firmware,workspace=workspace,controls=controls)
                    assert runtime['result']==1 and runtime['os_responsive'];write_json(folder/'runtime.json',runtime)
                    shutil.copyfile(workspace/'nand.overlay',folder/'nand.overlay')
                    selected=json.loads(subprocess.check_output([fixture,'inspect-app',workspace/'nand.overlay','key-media-note'],text=True,timeout=30))
                    if phase=='seed':before_app=selected
                    else:assert selected==before_app,'Key repair changed the app package/data root'
                    write_json(folder/'independent-data.json',selected)
            assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
            assert report['firmware_sha256']==digest(firmware) and report['qemu_sha256']==digest(qemu)
            for name,value in report['sources'].items():assert digest(ROOT/name)==value,name
            report['status']='passed';write_json(output/'report.json',report)
    except BaseException as exc:
        report['status']='failed';report['error']=str(exc);write_json(output/'report.json',report);raise


if __name__=='__main__':main()

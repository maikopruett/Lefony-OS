#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normal ARM approval for safe key removal and backed-up registry repair."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from data_device import DataClient
from files_device import FileClient
from keys_device import Client as Keys
from replay import Controls
from runner import exercise
from sdk_notebook_probe import wait_notebook
from signing import openssl,sign,public_der
from workspace import opened
import hashlib


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    firmware=output/'firmware.elf';shutil.copyfile(args.firmware,firmware);qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    names=['sdk/tools/keys_device.py','sdk/tools/cli.py','vm/test-sdk-key-maintenance.py','tests/native/app_document_fixture.cpp',
        'ports/lefony-prime-g2/apps/native_apps/app.cpp',*['ports/lefony-prime-g2/ion/src/prime_g2/'+name for name in
        ('app_developer_keys.h','app_developer_keys.cpp','app_developer_key_session.h','app_developer_key_session.cpp',
         'app_developer_key_wire.h','app_management.cpp','usb_diagnostics.cpp')]]
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),
        'qemu_sha256':digest(qemu),'sdk_sha256':identity(ROOT/'sdk'),'sources':{name:digest(ROOT/name) for name in names},'cases':[]}
    def record(name,**value):
        report['cases'].append({'case':name,**value});write_json(output/'report.json',report);print('PASS:',name,flush=True)
    write_json(output/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='key-maintenance-') as temporary:
            root=Path(temporary);fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](root)
            project=root/'notebook';shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
            bootstrap=root/'bootstrap';(bootstrap/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'sdk/examples/counter/src/main.cpp',bootstrap/'src/main.cpp')
            write_json(bootstrap/'app.json',{'abi':1,'id':'store-counter','name':'Store counter','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
            start=output/'bootstrap.lfapp';shutil.copyfile(package(bootstrap),start)
            public={};private={};fingerprints={}
            for name in 'abcdefghij':
                private[name]=root/(name+'-private.pem');public[name]=output/(name+'-public.pem')
                private[name].write_bytes(openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'));private[name].chmod(0o600)
                public[name].write_bytes(openssl('pkey','-in',private[name],'-pubout'))
                fingerprints[name]=hashlib.sha256(public_der(public[name])).hexdigest()
            artifacts={}
            for key,version in [('a','1.0.0'),('b','1.1.0')]:
                manifest=json.loads((project/'app.json').read_text());manifest.update(id='key-document',version=version)
                write_json(project/'app.json',manifest);artifact=package(project,'debug')
                artifacts[key]=output/(key+'.lfapp');artifacts[key].write_bytes(sign(artifact.read_bytes(),private[key]))
                shutil.copyfile(project/'build/app-debug.elf',output/(key+'.elf'))
            document=b'LFNOTE1\n2+3\nx^2\n';fixture_file=root/'document.txt';fixture_file.write_bytes(document)
            prior_identity=None
            for phase in ('installed','cold','damaged','repaired-cold','empty','empty-cold'):
                folder=output/phase;folder.mkdir();records=[]
                with opened(project,'empty' if phase.startswith('empty') else 'maintained') as (media,_):
                    if phase=='damaged':subprocess.run([fixture,'corrupt-keys',media/'nand.overlay'],check=True,timeout=30)
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;keys=Keys(app.transport);data=DataClient(app)
                        def picture(name):
                            time.sleep(.3);path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            with Image.open(path) as image:image.save(path.with_suffix('.png'))
                        def settle(client):
                            deadline=time.monotonic()+25
                            while time.monotonic()<deadline:
                                state=client.bound_status()
                                if state['state'] not in ('preparing','awaiting_usb_ack'):return state
                                time.sleep(.05)
                            raise AssertionError('Key proposal did not prepare')
                        def proposal(operation,key,expected=None):
                            client=Keys(app.transport)
                            values={'public_key':public[key],'label':'Key '+key.upper()} if operation=='enroll' else {'fingerprint':fingerprints[key]}
                            client.begin(operation,**values);state=settle(client)
                            if expected:
                                assert state['state']=='failed' and state['error']==expected,state
                            else:
                                assert state['state']=='awaiting_approval',state;picture(operation+'-'+key)
                                normal.keys(['ok']);time.sleep(.25);normal.keys([])
                                state=client.wait();assert state['state']=='complete',state;normal.key('back');app.wait()
                            return state
                        def cli_operation(arguments,*,approve=True,expected_exit=0):
                            import cli,keys_device
                            pressed=False;out=io.StringIO();err=io.StringIO()
                            def advance(seconds):
                                nonlocal pressed
                                if not pressed and keys.status()['state']=='awaiting_approval':
                                    picture(arguments[0]+'-approval');pressed=True
                                    normal.keys(['ok' if approve else 'back']);time.sleep(.25);normal.keys([])
                                time.sleep(seconds)
                            class Connected:
                                def __enter__(self):return app.transport
                                def __exit__(self,*_):pass
                            old_usb,old_recovery,old_client,argv=keys_device.KeyUSB,keys_device.RecoveryUSB,keys_device.Client,sys.argv
                            try:
                                keys_device.KeyUSB=Connected;keys_device.RecoveryUSB=Connected;keys_device.Client=lambda transport:Keys(transport,sleep=advance)
                                sys.argv=['lefony-sdk',*map(str,arguments)]
                                with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):assert cli.main()==expected_exit,err.getvalue()
                            finally:
                                keys_device.KeyUSB,keys_device.RecoveryUSB,keys_device.Client,sys.argv=old_usb,old_recovery,old_client,argv
                            assert pressed;picture(arguments[0]+'-result');normal.key('back');app.wait()
                            return json.loads(out.getvalue()),err.getvalue()
                        def verify_document(name):
                            path=folder/(name+'.txt');FileClient(app).export_file('key-document','notebook.txt',path)
                            assert path.read_bytes()==document
                        try:
                            normal.key('home');app.wait();normal.key('back')
                            assert app.status()['reserved']&2048
                            if phase=='installed':
                                proposal('enroll','a');proposal('enroll','b')
                                proposal('remove','a','revoke_key_before_removal')
                                app.install(artifacts['a'].read_bytes(),[public['a']])
                                FileClient(app).import_file('key-document','notebook.txt',fixture_file)
                                proposal('revoke','a');proposal('remove','a','key_required_by_installed_or_unreadable_apps')
                                record('current-signer-removal-refused')
                                cli_operation(['install',artifacts['b'],'--public-key',public['b'],'--recover-signer'])
                                assert data.info('key-document')['pending_upgrade']
                                proposal('remove','a','key_required_by_installed_or_unreadable_apps');verify_document('pending')
                                record('retained-upgrade-signer-removal-refused')
                                entry=next(e for e in app.catalog() if e['id']=='key-document')
                                assert channel.command(f"APP OPEN {entry['slot']}")=='OK';wait_notebook(normal,records)
                                normal.key('home');app.wait();normal.key('back');assert not data.info('key-document')['pending_upgrade']
                                proposal('remove','a');verify_document('accepted')
                                assert [k['fingerprint'] for k in keys.keys()['keys']]==[fingerprints['b']]
                                record('unused-old-signer-removed-after-real-app-acceptance')
                                for key in 'cdefghi':proposal('enroll',key)
                                assert len(keys.keys()['keys'])==8;proposal('enroll','j','key_limit')
                                proposal('revoke','c');proposal('remove','c');proposal('enroll','j')
                                assert len(keys.keys()['keys'])==8
                                record('full-registry-explicit-revoked-key-removal-and-slot-reuse')
                            elif phase=='cold':
                                assert len(keys.keys()['keys'])==8 and not keys.status()['sequence'];verify_document('cold')
                                record('cold-retained-table-and-document')
                            elif phase=='damaged':
                                assert keys.status()['registry']=='corrupt' and keys.status()['unavailable_apps']==1
                                assert [e['id'] for e in app.catalog()]==['store-counter']
                                client=Keys(app.transport);info=client.damage_info()
                                client.begin('repair',public_key=public['b'],label='Recovered B',registry_hash='12'*32)
                                state=settle(client);assert state['state']=='failed' and state['error']=='stale_registry'
                                cancelled,log=cli_operation(['keys','repair','--public-key',public['b'],'--label','Recovered B',
                                    '--backup',folder/'cancelled.keys'],approve=False,expected_exit=1)
                                assert cancelled['state']=='cancelled' and keys.status()['registry']=='corrupt'
                                assert digest(folder/'cancelled.keys')==info['sha256']
                                record('damaged-registry-stale-and-cancelled-repair-preserve-backup')
                                repaired,log=cli_operation(['keys','repair','--public-key',public['b'],'--label','Recovered B',
                                    '--backup',folder/'original.keys'])
                                assert repaired['state']=='complete' and info['sha256'] in log and fingerprints['b'] in log
                                assert (folder/'original.keys').read_bytes()==(folder/'cancelled.keys').read_bytes()
                                values=keys.keys();assert values['serial']==1 and len(values['keys'])==1 and values['keys'][0]['fingerprint']==fingerprints['b']
                                verify_document('repaired');assert keys.status()['unavailable_apps']==0
                                proposal('enroll','j')
                                record('CLI-backed-up-OS-approved-repair-restores-authentication')
                            elif phase=='repaired-cold':
                                assert {k['fingerprint'] for k in keys.keys()['keys']}=={fingerprints['b'],fingerprints['j']}
                                entry=next(e for e in app.catalog() if e['id']=='key-document')
                                assert channel.command(f"APP OPEN {entry['slot']}")=='OK';wait_notebook(normal,records)
                                normal.key('home');app.wait();normal.key('back')
                                verify_document('repaired-cold');record('cold-repaired-trust-launch-and-unchanged-document')
                            elif phase=='empty':
                                proposal('enroll','a');proposal('revoke','a');proposal('remove','a')
                                assert keys.keys()=={'registry':'ready','serial':3,'keys':[]}
                                record('last-key-removal-retains-monotonic-serial')
                            else:
                                assert keys.keys()=={'registry':'ready','serial':3,'keys':[]}
                                proposal('enroll','a');assert keys.keys()['serial']==4
                                record('cold-empty-registry-and-reenrollment')
                        finally:normal.close()
                    runtime=exercise(start,qemu,firmware,workspace=media,controls=controls)
                    assert runtime['result']==1 and runtime['os_responsive'];write_json(folder/'runtime.json',runtime)
                    shutil.copyfile(media/'nand.overlay',folder/'nand.overlay')
                    if phase in ('cold','damaged','repaired-cold'):
                        selected=json.loads(subprocess.check_output([fixture,'inspect-app',media/'nand.overlay','key-document'],text=True,timeout=30))
                        if phase=='cold':prior_identity=selected
                        else:assert selected==prior_identity,'Registry repair changed the installed package/data root'
                        write_json(folder/'independent-data.json',selected)
            assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
            for name,value in report['sources'].items():assert digest(ROOT/name)==value,name
            report['status']='passed';write_json(output/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()

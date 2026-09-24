#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private app-key approval, revocation and reactivation on synthetic ARM/USB."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from data_device import DataClient,read_backup
from device import DeviceError
from files_device import FileClient
from keys_device import Client as Keys
from replay import Controls
from runner import exercise
from signing import openssl,sign
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    firmware=output/'firmware.elf';shutil.copyfile(args.firmware.resolve(),firmware)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    sources=['vm/test-sdk-developer-keys.py','sdk/tools/keys_device.py','sdk/tools/device.py','sdk/tools/cli.py',
             'ports/lefony-prime-g2/apps/native_apps/app.cpp',*['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in
             ('app_developer_key_wire.h','app_developer_key_session.h','app_developer_key_session.cpp',
              'app_developer_keys.h','app_developer_keys.cpp','app_management.cpp','app_management.h',
              'app_storage.cpp','app_document_store.cpp','native_app.cpp','usb_diagnostics.cpp','events.cpp')]]
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),
            'qemu_sha256':digest(qemu),'sdk_identity':identity(ROOT/'sdk'),
            'sources':{name:digest(ROOT/name) for name in sources},'cases':[]}
    def record(name,**detail):
        report['cases'].append({'case':name,'status':'passed',**detail});write_json(output/'progress.json',report)
        print('PASS:',name,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='sdk-private-keys-') as temporary:
            root=Path(temporary);project=root/'project';(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'sdk/examples/counter/src/main.cpp',project/'src/main.cpp')
            private={};public={}
            for name in ('a','b'):
                private[name]=root/(name+'-private.pem');public[name]=root/(name+'-public.pem')
                private[name].write_bytes(openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'));private[name].chmod(0o600)
                public[name].write_bytes(openssl('pkey','-in',private[name],'-pubout'))
                shutil.copyfile(public[name],output/(name+'-public.pem'))
            artifacts={}
            for name,app_id,version in [('bootstrap','store-counter','1.0.0'),('private','private-counter','1.0.0'),('update','private-counter','1.1.0'),
                                        ('recovery','private-counter','1.2.0'),('recovered-update','private-counter','1.3.0'),
                                        ('file-recovery','private-counter','1.4.0'),
                                        ('store-replacement','store-counter','1.1.0'),('new-id','unknown-counter','1.0.0')]:
                write_json(project/'app.json',{'abi':1,'id':app_id,'name':app_id,'version':version,'license':'CC-BY-NC-SA-4.0'})
                path=package(project);destination=output/(name+'.lfapp');shutil.copyfile(path,destination);artifacts[name]=destination
            signed_a=sign(artifacts['private'].read_bytes(),private['a'])
            update_a=sign(artifacts['update'].read_bytes(),private['a'])
            takeover_b=sign(artifacts['update'].read_bytes(),private['b'])
            recovery_b=sign(artifacts['recovery'].read_bytes(),private['b'])
            next_b=sign(artifacts['recovered-update'].read_bytes(),private['b'])
            store_b=sign(artifacts['store-replacement'].read_bytes(),private['b'])
            new_b=sign(artifacts['new-id'].read_bytes(),private['b'])
            file_recovery_a=sign(artifacts['file-recovery'].read_bytes(),private['a'])
            for name,content in (('original-a',signed_a),('update-a',update_a),('takeover-b',takeover_b),
                                 ('recovery-b',recovery_b),('next-b',next_b),('store-b',store_b),('new-b',new_b),('file-recovery-a',file_recovery_a)):
                (output/(name+'-signed.lfapp')).write_bytes(content)
            named_input=root/'document.bin';named_input.write_bytes(bytes(range(256))*269+b'preserved across signer recovery')
            for phase in ('enroll-revoke','cold-reactivate','cold-updated','cold-recovered','cold-file-recovered'):
                folder=output/phase;folder.mkdir()
                with opened(project,'key-workspace') as (workspace,_):
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;keys=Keys(app.transport);data=DataClient(app)
                        def home():
                            normal.key('home');app.wait();normal.key('back')
                        def settle(predicate,label,timeout=20):
                            deadline=time.monotonic()+timeout
                            while True:
                                value=keys.status()
                                if predicate(value):return value
                                if time.monotonic()>=deadline:raise AssertionError((label,value,channel.command('STATE')))
                                time.sleep(.05)
                        def picture(name):
                            time.sleep(.3);path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            from PIL import Image
                            with Image.open(path) as img:img.save(folder/(name+'.png'))
                        def approval(operation,name='a'):
                            client=Keys(app.transport)
                            options={'public_key':public[name],'label':'Developer '+name.upper()} if operation=='enroll' else {'fingerprint':keys.keys()['keys'][0 if name=='a' else 1]['fingerprint']}
                            current=client.begin(operation,**options)
                            assert current['state'] in ('preparing','awaiting_approval'),current
                            state=settle(lambda s:s['state']=='awaiting_approval','approval')
                            assert state['operation']==operation
                            picture(operation+'-'+name)
                            # Unlike app keypad assertions, this OS screen must
                            # not invoke a user callback. Inject only matrix edges.
                            normal.keys(['ok']);time.sleep(.25);normal.keys([]);time.sleep(.75)
                            result=client.wait();assert result['state']=='complete',result
                            picture(operation+'-'+name+'-complete');normal.key('back');app.wait()
                            return result
                        def reset_error():
                            app.write(0x60);app.wait()
                        def stored(expected,name):
                            destination=folder/(name+'.lfdata');data.export('private-counter',destination)
                            _,payload=read_backup(destination);assert payload==struct.pack('<I',expected),(name,payload)
                        def launch(app_id,allowed=True):
                            entry=next(e for e in app.catalog() if e['id']==app_id)
                            result=channel.command(f"APP OPEN {entry['slot']}")
                            assert (result=='OK')==allowed,(app_id,allowed,result)
                            return entry
                        def cli_read(command):
                            # Real CLI parsing/dispatch, with only its libusb
                            # connection replaced by the existing emulator USB.
                            import cli,keys_device
                            class Connected:
                                def __enter__(self):return app.transport
                                def __exit__(self,*_):pass
                            before=keys_device.KeyUSB;argv=sys.argv;stream=io.StringIO()
                            try:
                                keys_device.KeyUSB=Connected;sys.argv=['lefony-sdk','keys',command]
                                with contextlib.redirect_stdout(stream):assert cli.main()==0
                            finally:keys_device.KeyUSB=before;sys.argv=argv
                            return json.loads(stream.getvalue())
                        def recovery_request(content,expected=None,*,wrong_hash=False,cancel=False,disconnect=False):
                            client=Keys(app.transport)
                            app.write(0x63,argument=len(content))
                            for offset in range(0,len(content),512):app.write(0x64,content[offset:offset+512],offset)
                            client.begin('recover',fingerprint=content[24:56].hex(),package_hash=('ab'*32 if wrong_hash else hashlib.sha256(content).hexdigest()))
                            status=settle(lambda s:s['state'] not in ('preparing','awaiting_usb_ack'),'recovery prepared')
                            if expected:
                                assert status['state']=='failed' and status['error']==expected,status
                            else:
                                assert status['state']=='awaiting_approval',status
                                info=client.recovery_info();assert info['app_id']=='private-counter' and info['version']=='1.2.0',info
                                if disconnect:
                                    # A modeled USB bus reset traverses the production
                                    # disconnect handler without any approving key.
                                    app.transport.reset()
                                elif cancel:normal.key('back')
                                else:raise AssertionError('test must explicitly cancel or disconnect')
                                status=client.wait();assert status['state']=='cancelled',status
                            app.wait();normal.key('back');stored(2,'recovery-rejected-preserved-'+str(status['sequence']))
                        def cli_recover(content,key='b'):
                            import cli,keys_device
                            path=root/'recovery-signed.lfapp';path.write_bytes(content)
                            pressed=False
                            def advance(seconds):
                                nonlocal pressed
                                if not pressed and keys.status()['state']=='awaiting_approval':
                                    picture('recover-app');pressed=True
                                    normal.keys(['ok']);time.sleep(.25);normal.keys([])
                                time.sleep(seconds)
                            class Connected:
                                def __enter__(self):return app.transport
                                def __exit__(self,*_):pass
                            before_usb,before_client=keys_device.RecoveryUSB,keys_device.Client
                            argv=sys.argv;stdout,stderr=io.StringIO(),io.StringIO()
                            try:
                                keys_device.RecoveryUSB=Connected;keys_device.Client=lambda transport:Keys(transport,sleep=advance)
                                sys.argv=['lefony-sdk','install',str(path),'--public-key',str(public[key]),'--recover-signer']
                                with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):assert cli.main()==0,stderr.getvalue()
                            finally:
                                keys_device.RecoveryUSB=before_usb;keys_device.Client=before_client;sys.argv=argv
                            assert pressed and hashlib.sha256(content).hexdigest() in stderr.getvalue()
                            picture('recover-complete');normal.key('back');app.wait()
                            return json.loads(stdout.getvalue())
                        try:
                            home()
                            if phase=='enroll-revoke':
                                assert keys.status()['registry']=='empty'
                                for navigation in ('home','apps'):
                                    client=Keys(app.transport)
                                    client.begin('enroll',public_key=public['a'],label='Developer A')
                                    settle(lambda s:s['state']=='awaiting_approval','shifted navigation approval')
                                    picture('shift-'+navigation+'-pending')
                                    normal.key('shift');normal.key(navigation)
                                    state=client.wait()
                                    assert state['state']=='cancelled',state
                                    assert keys.status()['registry']=='empty' and not keys.keys()['keys']
                                    assert channel.command('STATE').split(' home_row=')[0]!=channel.native_state
                                    assert channel.command('MOD STATE')=='VALUE 0'
                                    picture('shift-'+navigation+'-dismissed')
                                    record('shift-'+navigation+'-dismisses-enrollment-without-new-trust',state=state)
                                    home()
                                approval('enroll','a');assert cli_read('list')['keys'][0]['state']=='active'
                                record('normal-OS-approval-and-SDK-key-list')
                                app.install(signed_a,[public['a']]);launch('private-counter');normal.key('ok');home();stored(1,'saved')
                                record('private-signature-install-launch-save-and-export')
                                approval('enroll','b')
                                try:app.install(takeover_b,[public['b']])
                                except DeviceError as error:assert 'error 10' in str(error),str(error)
                                else:raise AssertionError('another developer took over installed app')
                                reset_error();stored(1,'takeover-preserved')
                                record('different-developer-cannot-take-over-app')
                                approval('revoke','a')
                                assert keys.keys()['keys'][0]['state']=='revoked'
                                assert {e['id'] for e in app.catalog()}=={'store-counter','private-counter'}
                                stored(1,'revoked-export');launch('private-counter',False)
                                record('revoked-app-retains-catalog-and-data-but-cannot-launch')
                                try:app.install(signed_a,[public['a']])
                                except DeviceError as error:assert 'error 3' in str(error),str(error)
                                else:raise AssertionError('revoked key reinstalled an app')
                                reset_error();launch('store-counter');home();stored(1,'store-still-works')
                                record('revocation-rejects-install-and-preserves-store-app')
                            elif phase=='cold-reactivate':
                                status=cli_read('status');assert status['serial']==3 and not status['sequence'],status
                                assert keys.keys()['keys'][0]['state']=='revoked';stored(1,'cold-revoked');launch('private-counter',False)
                                record('cold-revocation-and-export')
                                approval('enroll','a');launch('private-counter');home();stored(1,'reactivated')
                                record('explicit-reapproval-recovers-original-private-key')
                                app.install(update_a,[public['a']]);launch('private-counter');normal.key('ok');home();stored(2,'updated')
                                record('same-signer-update-keeps-user-data')
                            elif phase=='cold-updated':
                                assert keys.keys()['keys'][0]['state']=='active';stored(2,'cold-updated')
                                assert next(e for e in app.catalog() if e['id']=='private-counter')['version']=='1.1.0'
                                launch('private-counter');home();record('cold-updated-private-app')
                                recovery_request(recovery_b,'signer_ownership');record('recovery-rejects-still-active-old-signer')
                                approval('revoke','a')
                                recovery_request(takeover_b,'invalid_recovery_package');record('recovery-rejects-same-version')
                                recovery_request(recovery_b,'invalid_recovery_package',wrong_hash=True);record('recovery-rejects-different-package-hash')
                                recovery_request(store_b,'signer_ownership');record('recovery-cannot-take-over-compiled-store-app')
                                recovery_request(new_b,'key_not_found');record('recovery-cannot-create-unowned-namespace')
                                recovery_request(recovery_b,cancel=True);record('cancelled-recovery-preserves-revoked-app-and-data')
                                recovery_request(recovery_b,disconnect=True);record('USB-reset-cancels-unapproved-recovery')
                                for partial in (True,False):
                                    app.write(0x63,argument=len(recovery_b))
                                    for offset in range(0,512 if partial else len(recovery_b),512):app.write(0x64,recovery_b[offset:offset+512],offset)
                                    app.transport.reset();assert app.wait()['state'] in (2,6)
                                    stored(2,'interrupted-upload-'+str(partial))
                                record('USB-reset-releases-partial-and-complete-uncommitted-upload')
                                installed=cli_recover(recovery_b);assert installed['id']=='private-counter' and installed['version']=='1.2.0'
                                stored(2,'recovered');launch('private-counter');home();stored(2,'recovered-launch')
                                assert keys.keys()['keys'][0]['state']=='revoked'
                                record('CLI-lost-key-replacement-with-OS-consent-preserves-data')
                            elif phase=='cold-recovered':
                                assert keys.keys()['keys'][0]['state']=='revoked';stored(2,'cold-recovered')
                                assert next(e for e in app.catalog() if e['id']=='private-counter')['version']=='1.2.0'
                                launch('private-counter');normal.key('ok');home();stored(3,'new-key-save')
                                app.install(next_b,[public['b']]);launch('private-counter');home();stored(3,'new-key-update')
                                record('cold-recovered-app-and-new-signer-update')
                                files=FileClient(app);files.import_file('private-counter','document.bin',named_input)
                                approval('enroll','a');approval('revoke','b')
                                before=files.info('private-counter')
                                assert before['file_bytes']==named_input.stat().st_size and not before['pending_upgrade'],before
                                installed=cli_recover(file_recovery_a,'a');assert installed['version']=='1.4.0'
                                named_output=folder/'recovered-document.bin';files.export_file('private-counter','document.bin',named_output)
                                assert named_output.read_bytes()==named_input.read_bytes();stored(3,'files-and-private')
                                launch('private-counter');home();record('signer-recovery-preserves-named-file-and-private-bytes',file_sha256=digest(named_output),file_bytes=named_output.stat().st_size)
                            else:
                                assert keys.keys()['keys'][1]['state']=='revoked';stored(3,'cold-files-private')
                                assert next(e for e in app.catalog() if e['id']=='private-counter')['version']=='1.4.0'
                                named_output=folder/'cold-document.bin';FileClient(app).export_file('private-counter','document.bin',named_output)
                                assert named_output.read_bytes()==named_input.read_bytes()
                                launch('private-counter');home();record('cold-recovered-named-file-and-private-data')
                        finally:normal.close()
                    result=exercise(artifacts['bootstrap'],qemu,firmware,workspace=workspace,controls=controls)
                    assert result['result']==1 and result['os_responsive'],result
                    write_json(folder/'execution.json',result)
                    shutil.copyfile(workspace/'nand.overlay',folder/'nand.overlay')
            report['status']='passed';write_json(output/'report.json',report)
    except BaseException as error:
        report['status']='failed';report['error']=str(error);write_json(output/'report.json',report);raise


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restore real cross-signer recovery archives with normal ARM OS consent."""
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
import archive_device as archive
import archive_format
import cli
import keys_device
from build import digest,identity,write_json
from data_device import DataClient
from device import Client as DeviceClient,DeviceError
from files_device import FileClient
from emulator_usb import USBError
from keys_device import Client as Keys
from replay import Controls
from runner import exercise
from signing import openssl,sign,public_der
from workspace import opened


def reject(action,match):
    try:action()
    except (DeviceError,USBError) as exc:
        assert match.lower() in str(exc).lower(),str(exc);return
    raise AssertionError('Expected refusal: '+match)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-evidence',type=Path,help='reuse an authenticated archive from a completed source phase')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    firmware=out/'firmware.elf';shutil.copyfile(args.firmware,firmware);qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    names=['vm/test-sdk-archive-consent.py','tests/native/app_document_fixture.cpp','sdk/tools/archive_device.py','sdk/tools/cli.py',
        'ports/lefony-prime-g2/apps/native_apps/app.cpp','scripts/prepare_prime_native_scheduling.py','scripts/prepare_prime_native_system.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+name for name in
          ('app_archive_session.cpp','app_archive_session.h','app_archive_wire.h','app_management.cpp','events.cpp','usb_diagnostics.cpp')]]
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),
        'sdk_sha256':identity(ROOT/'sdk'),'sources':{name:digest(ROOT/name) for name in names},'cases':[]}
    def record(name,**values):
        report['cases'].append({'case':name,**values});write_json(out/'report.json',report);print('PASS:',name,flush=True)
    write_json(out/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='archive-consent-') as temporary:
            root=Path(temporary);reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](root)
            project=root/'notebook';shutil.copytree(ROOT/'sdk/examples/notebook',project,ignore=shutil.ignore_patterns('build','.lefony','sdk.lock.json'))
            helper=root/'helper';(helper/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'sdk/examples/counter/src/main.cpp',helper/'src/main.cpp')
            write_json(helper/'app.json',{'abi':1,'id':'archive-helper','name':'Archive helper','version':'1.0.0','license':'CC-BY-NC-SA-4.0'})
            bootstrap=out/'bootstrap.lfapp';shutil.copyfile(cli.package(helper),bootstrap)
            private={};public={};fingerprints={};artifacts={}
            for key in ('a','b'):
                private[key]=root/(key+'-private.pem');public[key]=out/(key+'-public.pem')
                if args.source_evidence:
                    shutil.copyfile(args.source_evidence/(key+'-public.pem'),public[key])
                    artifacts[key]=out/(key+'.lfapp');shutil.copyfile(args.source_evidence/(key+'.lfapp'),artifacts[key])
                    fingerprints[key]=hashlib.sha256(public_der(public[key])).hexdigest()
                else:
                    private[key].write_bytes(openssl('genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048'));private[key].chmod(0o600)
                    public[key].write_bytes(openssl('pkey','-in',private[key],'-pubout'))
                    fingerprints[key]=hashlib.sha256(public_der(public[key])).hexdigest()
                    manifest=json.loads((project/'app.json').read_text());manifest.update(id='archive-document',version='1.0.0' if key=='a' else '1.1.0')
                    write_json(project/'app.json',manifest);package=cli.package(project,'debug')
                    artifacts[key]=out/(key+'.lfapp');artifacts[key].write_bytes(sign(package.read_bytes(),private[key]))
            document=root/'document.txt';document.write_bytes(b'LFNOTE1\n2+3\nx^2\n')
            attachment=root/'attachment.bin';attachment.write_bytes(bytes((i*19+(i>>8))&255 for i in range(131137)))
            snapshot=out/'pending.lfarchive';expected_identity=None
            if args.source_evidence:
                source_report=args.source_evidence/'report.json';previous=json.loads(source_report.read_text())
                receipt=next(case for case in previous['cases'] if case['case'] in
                    ('actual-signer-recovery-exported-with-document-and-large-file','reused-authenticated-source-archive'))
                if receipt['case']=='reused-authenticated-source-archive':
                    assert previous['status']=='passed','Reused archive must come from a completed qualification'
                shutil.copyfile(args.source_evidence/'pending.lfarchive',snapshot)
                inspected=archive_format.inspect(snapshot,list(public.values()))
                assert inspected.sha256==receipt['archive_sha256'] and len(inspected.snapshots)==2
                assert inspected.snapshots[0].package.sha256==digest(artifacts['b']) and inspected.snapshots[1].package.sha256==digest(artifacts['a'])
                record('reused-authenticated-source-archive',archive_sha256=inspected.sha256,source_report_sha256=digest(source_report))
            for phase in (('fresh','fresh-cold','rollback-cold') if args.source_evidence else ('source','fresh','fresh-cold','rollback-cold')):
                folder=out/phase;folder.mkdir()
                with opened(project,'source' if phase=='source' else 'destination') as (media,_):
                    def controls(channel):
                        normal=Controls(channel,folder);app=channel.app_client;keys=Keys(app.transport);c=archive.Client(app,timeout=180)
                        def picture(name):
                            time.sleep(.3);path=folder/(name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                            with Image.open(path) as image:image.save(path.with_suffix('.png'))
                        def key(operation,key):
                            client=Keys(app.transport);values={'public_key':public[key],'label':'Archive '+key.upper()} if operation=='enroll' else {'fingerprint':fingerprints[key]}
                            client.begin(operation,**values);deadline=time.monotonic()+30
                            while time.monotonic()<deadline:
                                state=client.bound_status()
                                if state['state']=='awaiting_approval':break
                                assert state['state'] in ('preparing','awaiting_usb_ack'),state;time.sleep(.05)
                            assert state['state']=='awaiting_approval',state;picture(operation+'-'+key)
                            normal.keys(['ok']);time.sleep(.25);normal.keys([]);assert client.wait()['state']=='complete'
                            normal.key('back');app.wait()
                        def run_cli(arguments,*,approve=True,expected_exit=0,archive_call=False,label='approval',navigation=None):
                            stdout=io.StringIO();stderr=io.StringIO();pressed=False
                            def advance(seconds):
                                nonlocal pressed
                                pending=c.status()['state']==archive.AWAIT_USER if archive_call else keys.status()['state']=='awaiting_approval'
                                if pending and not pressed:
                                    picture(label);pressed=True
                                    if navigation:
                                        normal.key('shift');normal.key(navigation)
                                    else:
                                        normal.keys(['ok' if approve else 'back']);time.sleep(.25);normal.keys([])
                                time.sleep(seconds)
                            old_arc,old_arc_client=archive.ArchiveUSB,archive.Client
                            old_key,old_recovery,old_keys,argv=keys_device.KeyUSB,keys_device.RecoveryUSB,keys_device.Client,sys.argv
                            try:
                                archive.ArchiveUSB=lambda:contextlib.nullcontext(app.transport)
                                archive.Client=lambda client:old_arc_client(DeviceClient(app.transport,sleep=advance),timeout=180)
                                keys_device.KeyUSB=lambda:contextlib.nullcontext(app.transport);keys_device.RecoveryUSB=keys_device.KeyUSB
                                keys_device.Client=lambda transport:Keys(transport,sleep=advance)
                                sys.argv=['lefony-sdk',*map(str,arguments)]
                                with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                                    assert cli.main()==expected_exit,stderr.getvalue()
                            finally:
                                archive.ArchiveUSB,archive.Client=old_arc,old_arc_client
                                keys_device.KeyUSB,keys_device.RecoveryUSB,keys_device.Client,sys.argv=old_key,old_recovery,old_keys,argv
                            assert pressed,'No normal OS consent occurred'
                            (folder/(label+'.stdout')).write_text(stdout.getvalue());(folder/(label+'.stderr')).write_text(stderr.getvalue())
                            picture(label+'-result');normal.key('back');app.wait();return stdout.getvalue(),stderr.getvalue()
                        def restore(*,approve=True):
                            return run_cli(['archive','restore',snapshot,'--public-key',public['a'],'--public-key',public['b'],'--allow-recovery-pair'],
                                approve=approve,expected_exit=0 if approve else 1,archive_call=True,label='approved' if approve else 'cancelled')
                        def check_files(label):
                            for name,original in [('notebook.txt',document),('attachment.bin',attachment)]:
                                target=folder/(label+'-'+name);FileClient(app).export_file('archive-document',name,target);assert target.read_bytes()==original.read_bytes()
                        try:
                            normal.key('home');app.wait();normal.key('back');assert app.status()['reserved']&4096
                            if phase=='source':
                                key('enroll','a');key('enroll','b');app.install(artifacts['a'].read_bytes(),[public['a']])
                                FileClient(app).import_file('archive-document','notebook.txt',document)
                                FileClient(app).import_file('archive-document','attachment.bin',attachment)
                                key('revoke','a');run_cli(['install',artifacts['b'],'--public-key',public['b'],'--recover-signer'],label='signer-recovery')
                                assert c.info('archive-document')['pending_upgrade'];c.export('archive-document',snapshot,list(public.values()))
                                check_files('source');record('actual-signer-recovery-exported-with-document-and-large-file',archive_sha256=digest(snapshot))
                            elif phase=='fresh':
                                key('enroll','b')
                                reject(lambda:c.restore(snapshot,list(public.values()),allow_recovery_pair=True),'authority')
                                assert not c.info('archive-document')['exists'];record('unknown-retained-signer-rejected')
                                key('enroll','a');key('revoke','a')
                                reject(lambda:c.restore(snapshot,list(public.values())),'authority')
                                assert not c.info('archive-document')['exists'];record('fresh-cross-signer-restore-requires-explicit-option')
                                restore(approve=False);assert not c.info('archive-document')['exists'];record('normal-Back-cancels-before-root-publication')
                                for navigation in ('home','apps'):
                                    run_cli(['archive','restore',snapshot,'--public-key',public['a'],'--public-key',public['b'],'--allow-recovery-pair'],
                                        approve=False,expected_exit=1,archive_call=True,label='shift-'+navigation,navigation=navigation)
                                    assert not c.info('archive-document')['exists']
                                    assert channel.command('MOD STATE')=='VALUE 0'
                                    record('shift-'+navigation+'-cancels-before-root-publication')
                                # Fully staged data cannot be committed remotely before OS approval.
                                raw=snapshot.read_bytes();binding=c._begin('archive-document',archive.RESTORE,length=len(raw),digest=bytes.fromhex(digest(snapshot)),allow_recovery_pair=True)
                                for offset in range(0,len(raw),488):
                                    app.write(0x92,struct.pack('<2I16s',binding['sequence'],offset,binding['nonce'])+raw[offset:offset+488]);c._wait(binding)
                                assert c.status()['state']==archive.AWAIT_USER
                                # Rejection withholds the control-transfer status ACK. Check
                                # that packet directly instead of waiting through host retries.
                                usb=channel.usb_host
                                usb.setup_packet(0x40,0x94,binding['sequence']&65535,binding['sequence']>>16,16)
                                usb.out_packet(binding['nonce']);assert usb.command('IN 0') in ('NAK','STALL')
                                assert c.status()['state']==archive.AWAIT_USER
                                picture('reset-before-approval');app.transport.reset();reject(lambda:c._wait(binding),'cancel')
                                normal.key('back');app.wait();assert not c.info('archive-document')['exists'];record('host-commit-refused-and-USB-reset-cancels-unapproved-restore')
                                result,notice=restore();assert json.loads(result)['committed']
                                assert all(text in notice for text in [digest(snapshot),fingerprints['a'],fingerprints['b']])
                                state=c.info('archive-document');assert state['pending_upgrade'] and state['signer']==fingerprints['b']
                                assert {k['fingerprint']:k['state'] for k in keys.keys()['keys']}[fingerprints['a']]=='revoked'
                                assert not DataClient(app).info('archive-document')['rollback_available'];check_files('restored')
                                assert any(e['id']=='archive-helper' for e in app.catalog());record('CLI-approved-fresh-restore-keeps-both-pairs-and-revocation')
                                exported=folder/'roundtrip.lfarchive';c.export('archive-document',exported,list(public.values()));assert exported.read_bytes()==snapshot.read_bytes()
                                reject(lambda:c.restore(snapshot,list(public.values()),replace=True,allow_recovery_pair=True),'absent app')
                                record('exact-archive-roundtrip-and-existing-namespace-protection')
                            elif phase=='fresh-cold':
                                exported=folder/'cold.lfarchive';c.export('archive-document',exported,list(public.values()));assert exported.read_bytes()==snapshot.read_bytes()
                                check_files('cold');assert not DataClient(app).info('archive-document')['rollback_available']
                                record('cold-restored-current-and-retained-pairs')
                                key('enroll','a');result=DataClient(app).rollback('archive-document');assert result['committed']
                                info=c.info('archive-document');assert info['version']==(1,0,0) and info['high_version']==(1,1,0) and info['signer']==fingerprints['a']
                                check_files('rollback');record('explicit-reenrollment-enables-old-signer-rollback-with-high-water-preserved')
                            else:
                                info=c.info('archive-document');assert info['version']==(1,0,0) and not info['pending_upgrade'] and info['signer']==fingerprints['a']
                                assert info['high_version']==(1,1,0);check_files('rollback-cold');record('cold-rollback-keeps-files-and-original-signer-ownership')
                            assert channel.command('PING')=='PONG'
                        finally:normal.close()
                    runtime=exercise(bootstrap,qemu,firmware,workspace=media,controls=controls)
                    assert runtime['result']==1 and runtime['os_responsive'];write_json(folder/'runtime.json',runtime)
                    selected=json.loads(subprocess.check_output([reader,'inspect-app',media/'nand.overlay','archive-document'],text=True,timeout=30))
                    assert selected['package_sha256']==digest(artifacts['a' if phase in ('fresh-cold','rollback-cold') else 'b'])
                    write_json(folder/'independent-data.json',selected);shutil.copyfile(media/'nand.overlay',folder/'nand.overlay')
            assert report['sdk_sha256']==identity(ROOT/'sdk')
            for name,value in report['sources'].items():assert digest(ROOT/name)==value,name
            report['status']='passed';write_json(out/'report.json',report)
    except BaseException as exc:
        report.update(status='failed',error=str(exc));write_json(out/'report.json',report);raise


if __name__=='__main__':main()

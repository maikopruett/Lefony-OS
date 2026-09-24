#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed whole-app archives through real ARM USB, CLI and cold synthetic storage."""
import argparse
from contextlib import nullcontext,redirect_stdout
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
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import archive_device as archive
import archive_format
import cli
from build import digest,write_json
from data_device import DataClient
from device import DeviceError
from emulator_usb import USBError
from files_device import FileClient
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened
APP='data-recovery'
KEY=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def rejected(action,match):
    try:action()
    except DeviceError as exc:
        assert match in str(exc),(match,str(exc));return str(exc)
    raise AssertionError('Expected rejection: '+match)


def command(transport,*args):
    """Run the actual CLI; substitute only its physical USB opener."""
    previous,argv=archive.ArchiveUSB,sys.argv
    try:
        archive.ArchiveUSB=lambda:nullcontext(transport)
        sys.argv=['lefony-sdk','archive',*map(str,args)];out=io.StringIO()
        with redirect_stdout(out):assert cli.main()==0,out.getvalue()
        return json.loads(out.getvalue())
    finally:archive.ArchiveUSB=previous;sys.argv=argv


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phases',nargs='+',default=['initial','cold','pending','cold-pending','rollback','fresh','corrupt-index','corrupt-private'])
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    firmware=output/'firmware.elf';shutil.copyfile(args.firmware,firmware)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';cases=[]
    sources=['vm/test-sdk-archives.py','vm/test-sdk-documents.py','tests/native/app_document_fixture.cpp',
        'tests/native/sdk_data_recovery.c','sdk/tools/archive_device.py','sdk/tools/archive_format.py','sdk/tools/cli.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in ('app_archive_source.cpp','app_archive_export.cpp',
            'app_archive_restore.cpp','app_archive_session.cpp','app_management.cpp','app_storage.cpp','usb_diagnostics.cpp')]]
    report={'schema':1,'status':'running','physical':'not_tested','firmware_sha256':digest(firmware),
        'qemu_sha256':digest(qemu),'sources':{p:digest(ROOT/p) for p in sources},'cases':cases}
    write_json(output/'report.json',report)
    current=output/'current.lfarchive';pending=output/'pending.lfarchive';blob=output/'large.bin'
    blob.write_bytes(bytes((i*17+(i>>8))&255 for i in range(131137)))
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-archives-') as temp:
            project=Path(temp)/'project';(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_data_recovery.c',project/'src/main.c')
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            artifacts={}
            for name,app_id,version,schema in [('old',APP,1,0),('new',APP,2,1),('helper','archive-helper',1,0)]:
                write_json(project/'app.json',{'abi':1,'id':app_id,'name':'Archive Validation','version':f'{version}.0.0',
                    'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':8,'required_capabilities':536,'optional_capabilities':0,'data_schema':schema})
                pkg=cli.package(project);folder=output/name;folder.mkdir(exist_ok=True)
                for filename in ('app-debug.elf','app.elf','build.json'):shutil.copyfile(project/'build'/filename,folder/filename)
                artifacts[name]=folder/'app.lfapp';artifacts[name].write_bytes(sign(pkg.read_bytes(),KEY))
            helper=Path(temp)/'reader';helper.mkdir();reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            for phase in args.phases:
                target=output/phase;target.mkdir(exist_ok=True)
                secondary=phase in ('fresh','corrupt-index','corrupt-private')
                chosen=artifacts['helper' if secondary else 'new' if phase in ('pending','cold-pending','rollback') else 'old']
                with opened(project,phase if secondary else 'archives') as (workspace,_):
                    if phase.startswith('corrupt-'):
                        shutil.copyfile(output/'cold'/'nand.overlay',workspace/'nand.overlay')
                        subprocess.run([reader,phase,workspace/'nand.overlay',APP],check=True,capture_output=True,timeout=60)
                    observed={}
                    def controls(channel):
                        normal=Controls(channel,target);client=channel.app_client;c=archive.Client(client,timeout=180);files=FileClient(client)
                        raw_command=channel.usb_host.command;transport_errors=[]
                        def checked_command(command,*a,**kw):
                            try:return raw_command(command,*a,**kw)
                            except USBError as exc:
                                transport_errors.append({'command':command.split()[0],'error':str(exc)})
                                raise
                        channel.usb_host.command=checked_command
                        try:
                            normal.run({'steps':[{'program_exit':0}]},[])
                            rejected(lambda:c.info(APP),'Close the app')
                            normal.key('home');client.wait()
                            before=c.info(APP);observed['before']=before
                            def export(path):
                                result=command(client.transport,'export',APP,path,'--public-key',PUBLIC)
                                assert archive_format.inspect(path,[PUBLIC]).signatures_checked;return result
                            def restore(path):return command(client.transport,'restore',path,'--public-key',PUBLIC,'--replace')
                            if phase=='initial':
                                files.import_file(APP,'blob.bin',blob)
                                observed['export']=export(current)
                                # Mutating the app after a backup must be undone by explicit restore.
                                changed=target/'changed';changed.write_bytes(b'changed')
                                files.import_file(APP,'blob.bin',changed,replace=True)
                                observed['restore']=restore(current)
                                out=target/'roundtrip.lfarchive';export(out);assert out.read_bytes()==current.read_bytes()
                                info=c.info(APP);raw=current.read_bytes();binding=c._begin(APP,archive.RESTORE,generation=info['generation'],
                                    length=len(raw),digest=hashlib.sha256(raw).digest(),replace=True)
                                client.write(0x92,struct.pack('<2I16s',binding['sequence'],0,binding['nonce'])+raw[:488])
                                c._wait(binding);client.transport.reset()
                                rejected(lambda:c._wait(binding),'cancel');client.wait();assert c.info(APP)['generation']==info['generation']
                                observed['cancelled_upload_preserved']=True
                                rejected(lambda:c._begin(APP,archive.RESTORE,generation=info['generation']+1,length=len(raw),
                                    digest=hashlib.sha256(raw).digest(),replace=True),'changed')
                                client.wait()
                            elif phase=='cold':
                                out=target/'cold.lfarchive';export(out);assert out.read_bytes()==current.read_bytes()
                                # Acknowledged commit drains across bus reset, with its bound receipt.
                                raw=current.read_bytes();binding=c._begin(APP,archive.RESTORE,generation=before['generation'],
                                    length=len(raw),digest=hashlib.sha256(raw).digest(),replace=True)
                                for offset in range(0,len(raw),488):
                                    client.write(0x92,struct.pack('<2I16s',binding['sequence'],offset,binding['nonce'])+raw[offset:offset+488]);c._wait(binding)
                                assert c.status()['state']==archive.READY
                                client.write(0x94,binding['nonce'],argument=binding['sequence']);client.transport.reset()
                                done=c._wait(binding);assert done['state']==archive.COMPLETE and done['flags']==1
                                client.wait();observed['committed_across_reset']=True
                            elif phase=='pending':
                                assert before['pending_upgrade'] and before['data_schema']==1
                                observed['export']=export(pending);assert len(archive_format.inspect(pending,[PUBLIC]).snapshots)==2
                                observed['restore']=restore(pending)
                            elif phase=='cold-pending':
                                out=target/'cold.lfarchive';export(out);assert out.read_bytes()==pending.read_bytes()
                            elif phase=='rollback':
                                observed['rollback']=DataClient(client).rollback(APP)
                                observed['restore_same_code_below_high']=restore(current)
                                after=c.info(APP);assert after['version']==(1,0,0) and after['high_version']==(2,0,0)
                            else:
                                assert not before['exists'] if phase=='fresh' else before['exists']
                                if phase.startswith('corrupt-'):
                                    rejected(lambda:c.export(APP,target/'damaged.lfarchive',[PUBLIC]),'integrity')
                                    assert not (target/'damaged.lfarchive').exists()
                                observed['restore']=restore(current)
                                assert any(entry['id']=='archive-helper' for entry in client.catalog())
                                out=target/'recovered.lfarchive';export(out);assert out.read_bytes()==current.read_bytes()
                            observed['after']=c.info(APP)
                            assert channel.command('PING')=='PONG'
                            # Expected archive errors are protocol statuses,
                            # not USB stalls hidden by best-effort cleanup.
                            assert not transport_errors,transport_errors
                        finally:
                            observed['transport_errors']=transport_errors
                            channel.usb_host.command=raw_command
                            normal.close()
                    try:
                        result=exercise(chosen,qemu,firmware,workspace=workspace,controls=controls,public_keys=[PUBLIC])
                        assert result['result']==1 and result['os_responsive'],result
                    except Exception:
                        shutil.copyfile(workspace/'nand.overlay',target/'failed-nand.overlay');raise
                    state=json.loads(subprocess.check_output([reader,'inspect-app',workspace/'nand.overlay',APP],text=True,timeout=60))
                    expected=222 if phase in ('pending','cold-pending') else 111
                    assert state['private_data_sha256']==hashlib.sha256(struct.pack('<I',expected)).hexdigest()
                    assert state['package_sha256']==digest(artifacts['new' if expected==222 else 'old'])
                    destination=target/'independent-blob.bin'
                    subprocess.run([reader,'export-file',workspace/'nand.overlay',APP,'blob.bin',destination],check=True,capture_output=True,timeout=60)
                    assert destination.read_bytes()==blob.read_bytes()
                    shutil.copyfile(workspace/'nand.overlay',target/'nand.overlay')
                    cases.append({'case':phase,'runtime':result,'cold_storage':state,**observed})
                    write_json(output/'report.json',report);print('PASS:',phase,flush=True)
        report['status']='passed';write_json(output/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(output/'report.json',report);raise


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private-data backups and authenticated retained-pair rollback on actual ARM USB."""
import argparse
import hashlib
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
from build import digest,write_json
from cli import package
from data_device import DataClient,encode_backup,read_backup
from device import DeviceError
from files_device import FileClient,DATA_IMPORT,ROLLBACK,WRITABLE
from lfapp import API_REVISION
from replay import Controls
from runner import exercise
from signing import sign,HEADER
from workspace import opened

APP='data-recovery'
KEY=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
PUBLIC=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'


def rejected(action, message):
    try: action()
    except DeviceError as error:
        assert message in str(error),(message,str(error));return str(error)
    raise AssertionError('Operation was unexpectedly accepted: '+message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-data-recovery-vm.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-data-recovery/arm')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';firmware=output/'firmware.elf'
    shutil.copyfile(args.firmware,firmware);cases=[]
    sources=['vm/test-sdk-data-recovery.py','tests/native/sdk_data_recovery.c','tests/native/app_document_fixture.cpp',
        'sdk/tools/data_device.py','sdk/tools/files_device.py','sdk/tools/runner.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in
          ('app_file_exchange.cpp','app_file_exchange.h','app_management.cpp','app_storage.cpp','app_document_store.cpp','usb_diagnostics.cpp')]]
    evidence={'schema':1,'physical':'not_tested','firmware_sha256':digest(firmware),'qemu_sha256':digest(qemu),
        'sources':{p:digest(ROOT/p) for p in sources},'cases':cases}
    write_json(output/'execution.json',evidence)
    def record(case, **fields):
        cases.append({'case':case,**fields});write_json(output/'progress.json',{'status':'in_progress',**evidence})
        print('PASS:',case,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='lefony-data-recovery-') as temp:
            project=Path(temp)/'project';(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_data_recovery.c',project/'src/main.c')
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
            helper=Path(temp)/'helper';helper.mkdir()
            reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
            artifacts={}
            for name,app_id,version,schema in (('old',APP,1,0),('new',APP,2,1),('wrong-id','another-app',1,0),('wrong-schema',APP,1,9),('unsupported',APP,1,0)):
                write_json(project/'app.json',{'abi':1,'id':app_id,'name':'Data Recovery','version':f'{version}.0.0',
                    'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':API_REVISION+1 if name=='unsupported' else 8,'required_capabilities':536,
                    'optional_capabilities':0,'data_schema':schema})
                artifact=package(project);target=output/name;target.mkdir(exist_ok=True)
                for filename in ('app-debug.elf','app.elf','build.json','app.json','project.json','sdk.lock.json'):
                    source=project/filename if filename.endswith('.json') and filename!='build.json' else project/'build'/filename
                    shutil.copyfile(source,target/filename)
                shutil.copyfile(artifact,target/'app-unsigned.lfapp')
                artifacts[name]=target/'app.lfapp';artifacts[name].write_bytes(sign(artifact.read_bytes(),KEY))
            broken=bytearray(artifacts['old'].read_bytes());broken[HEADER.size]^=1
            artifacts['bad-signature']=output/'bad-signature.lfapp';artifacts['bad-signature'].write_bytes(broken)
            maximum=bytes((i*13)&255 for i in range(65536));original=struct.pack('<I',111)
            backup=output/'original.lfdata';large=output/'maximum.lfdata'
            large.write_bytes(encode_backup(APP,'1.0.0',0,maximum))
            def inspect(workspace):
                return json.loads(subprocess.check_output([reader,'inspect-app',workspace/'nand.overlay',APP],text=True,timeout=60))
            def named(workspace,target,expected):
                subprocess.run([reader,'export-file',workspace/'nand.overlay',APP,'document.txt',target],check=True,capture_output=True,timeout=60)
                assert target.read_bytes()==expected
            for phase in ('initial','cold-restore','upgrade-rollback','cold-rollback','bad-signature','wrong-id','wrong-schema','unsupported'):
                target=output/phase;target.mkdir(exist_ok=True)
                negative=phase in ('bad-signature','wrong-id','wrong-schema','unsupported')
                chosen=artifacts['new' if phase=='upgrade-rollback' or negative else 'old']
                with opened(project,phase if negative else 'recovery') as (workspace,_):
                    if negative:
                        subprocess.run([reader,'seed-pending',artifacts[phase],artifacts['new'],workspace/'nand.overlay',APP],
                            check=True,capture_output=True,timeout=60)
                    observed={}
                    def controls(channel):
                        normal=Controls(channel,target);client=channel.app_client;data=DataClient(client);files=FileClient(client)
                        def value(i):
                            n=int(channel.command(f'APP DIAG {i}').split()[1]);return n-2**32 if n>=2**31 else n
                        def exported(name,expected):
                            dest=target/(name+'.lfdata');report=data.export(APP,dest)
                            metadata,payload=read_backup(dest);assert payload==expected
                            assert metadata['sha256']==hashlib.sha256(expected).hexdigest();return report
                        try:
                            deadline=time.monotonic()+120
                            while not value(15):
                                assert not value(9),(phase,value(9),value(10))
                                assert time.monotonic()<deadline,(phase,'main deadline');time.sleep(.05)
                            assert value(21)==0,(phase,'program exit',value(21))
                            observed['program_exit_before_home']=value(21)
                            rejected(lambda:data.info(APP),'Close the app')
                            normal.key('home');client.wait();info=data.info(APP);observed['before']=info
                            if phase=='initial':
                                assert info['private_bytes']==4 and not info['pending_upgrade']
                                data.export(APP,backup);assert read_backup(backup)[1]==original
                                observed['restore']=data.restore(APP,large);exported('maximum',maximum)
                                wrong=dict(data.info(APP));wrong['generation']+=1
                                rejected(lambda:data._begin(APP,DATA_IMPORT,identity=wrong),'changed')
                                client.wait();current=data.info(APP)
                                state=data._begin(APP,DATA_IMPORT,identity=current,length=0,digest=bytes(32))
                                client.write(0x74,argument=state['sequence'])
                                rejected(lambda:data._wait(sequence=state['sequence'],operation=DATA_IMPORT),'hash mismatch');client.wait()
                                state=data._begin(APP,DATA_IMPORT,identity=current,length=5,digest=bytes(32))
                                client.write(0x72,struct.pack('<2I',state['sequence'],0)+b'half')
                                state=data._wait(sequence=state['sequence'],operation=DATA_IMPORT)
                                assert state['state']==WRITABLE and state['offset']==4
                                client.transport.reset()
                                rejected(lambda:data._wait(sequence=state['sequence'],operation=DATA_IMPORT),'cancel')
                                client.wait();normal.key('back');exported('preserved',maximum)
                                observed['after']=data.info(APP);assert observed['after']['generation']==current['generation']
                            elif phase=='cold-restore':
                                exported('cold-maximum',maximum)
                                # Disconnect after the wire-acknowledged commit:
                                # completion must drain across USB enumeration.
                                state=data._begin(APP,DATA_IMPORT,identity=data.info(APP),digest=hashlib.sha256(b'').digest())
                                client.write(0x74,argument=state['sequence']);client.transport.reset()
                                state=data._wait(sequence=state['sequence'],operation=DATA_IMPORT)
                                assert state['state']==4 and state['flags']==1,state
                                client.wait();normal.key('back');exported('empty',b'')
                                observed['commit_then_USB_reset']=state['flags']
                                data.restore(APP,backup);exported('restored-original',original)
                            elif phase=='upgrade-rollback':
                                assert info['pending_upgrade'] and info['rollback_available'] and info['previous_version']=='1.0.0'
                                assert info['data_schema']==1 and info['previous_schema']==0 and info['high_version']=='2.0.0'
                                exported('before-rollback',struct.pack('<I',222))
                                rejected(lambda:data.restore(APP,backup),'upgrade is pending')
                                rejected(lambda:data._begin(APP,DATA_IMPORT,identity=info),'schema')
                                client.wait()
                                rejected(lambda:data._begin(APP,ROLLBACK,identity=info,cursor=info['previous_package']+1),'denied')
                                client.wait();state=data._begin(APP,ROLLBACK,identity=info,cursor=info['previous_package'])
                                data._cancel(state['sequence']);client.wait();assert data.info(APP)['generation']==info['generation']
                                observed['rollback']=data.rollback(APP);exported('rolled-back',original)
                                after=data.info(APP);assert after['version']=='1.0.0' and after['high_version']=='2.0.0'
                                assert after['package_sha256']==digest(artifacts['old']);observed['after']=after
                            elif phase=='cold-rollback':
                                assert info['version']=='1.0.0' and info['high_version']=='2.0.0' and not info['pending_upgrade']
                                exported('cold-old',original)
                                observed['rejected_reinstall']=rejected(lambda:client.install(artifacts['new'].read_bytes(),[PUBLIC]),'error 8')
                                client.write(0x67);client.wait();assert data.info(APP)==info
                            else:
                                assert info['pending_upgrade'] and not info['rollback_available'],info
                                rejected(lambda:data.rollback(APP),'No verified compatible recovery pair')
                                observed['denied']=rejected(lambda:data._begin(APP,ROLLBACK,identity=info,cursor=info['previous_package']),'denied')
                                client.wait();assert data.info(APP)==info
                                exported('preserved-current',struct.pack('<I',222))
                            name=target/'document.txt';files.export_file(APP,'document.txt',name)
                            assert name.read_bytes()==(b'migrated document' if negative else b'old document')
                            assert channel.command('PING')=='PONG'
                        finally:normal.close()
                    assert digest(qemu)==evidence['qemu_sha256']
                    try:
                        result=exercise(chosen.parent/'app-unsigned.lfapp',qemu,firmware,workspace=workspace,controls=controls)
                    except Exception:
                        shutil.copyfile(workspace/'nand.overlay',target/'failed-nand.overlay');raise
                    assert result['result']==1 and result['os_responsive'],result
                    state=inspect(workspace);expected=maximum if phase=='initial' else struct.pack('<I',222) if negative else original
                    assert state['private_bytes']==len(expected) and state['private_data_sha256']==hashlib.sha256(expected).hexdigest(),state
                    assert state['package_sha256']==digest(chosen if negative or phase!='upgrade-rollback' else artifacts['old'])
                    assert state['pending_upgrade']==int(negative) and state['schema']==int(negative)
                    named(workspace,target/'independent-document.txt',b'migrated document' if negative else b'old document')
                    shutil.copyfile(workspace/'nand.overlay',target/'nand.overlay')
                    record(phase,runtime=result,saved=state,**observed)
        write_json(output/'report.json',{'status':'passed',**evidence})
    except Exception as error:
        write_json(output/'failure-report.json',{'status':'failed','error':str(error),**evidence});raise


if __name__=='__main__':main()

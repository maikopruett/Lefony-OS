#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Candidate app data service: live snapshots, normal/fault/Home and migration."""
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
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-checkpoint-vm.elf')
    parser.add_argument('--old-firmware',type=Path,default=ROOT/'build/sdk-file-exchange/evidence/artifacts/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-data-checkpoint/arm')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='lefony-checkpoint-') as temporary:
        helper=Path(temporary)/'helper';helper.mkdir()
        reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
        for mode in ('fault','normal','home','migration','denied','unsupported'):
            project=Path(temporary)/mode;(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_data_checkpoint.c',project/'src/main.c')
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[mode]})
            phases=(0,1,2) if mode=='migration' else (0,) if mode in ('denied','unsupported') else (0,1)
            for phase in phases:
                # Normal journeys require API 8. The explicit old-firmware
                # probe declares the bit optional to test unsupported calls.
                metadata={'abi':1,'id':'data-checkpoint','name':'Data Checkpoint','version':('2.0.0' if mode=='migration' and phase else '1.0.0'),
                    'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':7 if mode in ('denied','unsupported') else 8,
                    'required_capabilities':24 if mode in ('denied','unsupported') else 536,
                    'optional_capabilities':512 if mode=='unsupported' else 0,'data_schema':int(mode=='migration' and phase>0)}
                write_json(project/'app.json',metadata);artifact=package(project)
                target=output/mode/str(phase);target.mkdir(parents=True,exist_ok=True)
                for name in ('app-debug.elf','app.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,target/name)
                for name in ('app.json','project.json','sdk.lock.json'):shutil.copyfile(project/name,target/name)
                observed={}
                def controls(channel):
                    normal=Controls(channel,target)
                    def value(i):
                        v=int(channel.command(f'APP DIAG {i}').split()[1]);return v-2**32 if v>=2**31 else v
                    try:
                        deadline=time.monotonic()+120
                        while True:
                            fault=value(9)
                            if mode=='fault' and phase==0 and fault:
                                symbols=subprocess.check_output(['arm-none-eabi-nm',str(project/'build/app-debug.elf')],text=True)
                                expected=next(int(line.split()[0],16) for line in symbols.splitlines() if line.endswith(' lefony_data_expected_fault'))
                                assert fault==-11 and value(10)==expected,(fault,value(10),expected)
                                observed['expected_fault']=fault;break
                            assert not fault,(mode,phase,'fault',fault,value(10))
                            if mode=='home' and phase==0:
                                frame=target/'staged.ppm';normal.execute('screendump',{'filename':str(frame)})
                                with Image.open(frame) as picture:
                                    if picture.convert('RGB').getpixel((40,40))==(0,0,255):break
                            elif value(15):
                                assert value(21)==0,(mode,phase,'program exit',value(21));break
                            assert time.monotonic()<deadline,(mode,phase,'deadline');time.sleep(.05)
                        frame=target/'finished.ppm';normal.execute('screendump',{'filename':str(frame)})
                        with Image.open(frame) as picture:picture.save(target/'finished.png')
                        normal.key('home')
                    finally:normal.close()
                firmware=args.old_firmware if mode=='unsupported' else args.firmware
                with opened(project,'data') as (workspace,_):
                    result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',firmware,workspace=workspace,controls=controls)
                    state=json.loads(subprocess.check_output([reader,'inspect-app',workspace/'nand.overlay','data-checkpoint'],text=True,timeout=60))
                    expected=(111 if phase==0 else 222) if mode=='migration' else (66 if phase else 55 if mode=='normal' else 44)
                    if mode in ('denied','unsupported'):expected=None
                    contents=b'' if expected is None else struct.pack('<I',expected)
                    assert state['private_bytes']==len(contents) and state['private_data_sha256']==hashlib.sha256(contents).hexdigest(),(mode,phase,state)
                    if mode=='migration':
                        assert state['schema']==int(phase>0) and state['pending_upgrade']==int(phase==1),state
                assert result['result']==(-11 if mode=='fault' and phase==0 else 1) and result['os_responsive'],result
                cases.append({'mode':mode,'phase':phase,'runtime':result,'saved':state,**observed})
                write_json(output/'progress.json',{'status':'in_progress','cases':cases})
                print('PASS:',mode,phase,flush=True)
    sources=['vm/test-sdk-data-checkpoint.py','tests/native/sdk_data_checkpoint.c','tests/native/app_document_fixture.cpp',
        'sdk/include/lefony/data.h','sdk/include/lefony/data_wire.h',*['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in
        ('app_data_session.cpp','app_data_session.h','app_management.cpp','app_file_session.cpp','native_app.cpp')]]
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested','cases':cases,
        'sources':{p:digest(ROOT/p) for p in sources},'firmware_sha256':digest(args.firmware),
        'qemu_sha256':digest(ROOT/'build/qemu-prime-g2/qemu-system-arm')})


if __name__=='__main__':main()

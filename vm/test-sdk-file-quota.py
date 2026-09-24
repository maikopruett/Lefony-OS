#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed ordinary C quota enforcement, failed replacement, space reclamation, cold restart and fallback."""
import argparse
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-firmware',type=Path,required=True,help='Preserved API 6 or earlier ELF')
    args=parser.parse_args();output=ROOT/'build/sdk-file-quota/arm';output.mkdir(parents=True,exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='lefony-quota-') as temp:
        directory=Path(temp);helper=directory/'helper';helper.mkdir()
        reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
        for mode in ('normal','denied','unsupported'):
            project=directory/mode;(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_file_quota.c',project/'src/main.c')
            write_json(project/'app.json',{'abi':1,'id':'file-quota','name':'File Quota',
                'version':'1.0.0','license':'GPL-3.0-or-later','schema':1,'data_schema':0,
                'minimum_api':7 if mode=='normal' else 3,
                'required_capabilities':344 if mode=='normal' else 24,'optional_capabilities':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1',
                'sources':['src/main.c'],'arguments':[mode]})
            artifact=package(project);retained=output/mode;retained.mkdir(exist_ok=True)
            for name in ('app-debug.elf','app.elf','build.json',artifact.name):
                shutil.copyfile(project/'build'/name,retained/name)
            for name in ('app.json','project.json','sdk.lock.json'):
                shutil.copyfile(project/name,retained/name)
            for stage in (['initial','full','cold'] if mode=='normal' else ['initial']):
                def controls(channel):
                    normal=Controls(channel,retained)
                    try:
                        deadline=time.monotonic()+120
                        while not int(channel.command('APP DIAG 15').split()[1]):
                            fault=int(channel.command('APP DIAG 9').split()[1])
                            if fault:
                                pc=int(channel.command('APP DIAG 10').split()[1])
                                location=subprocess.check_output(['arm-none-eabi-addr2line','-if',
                                    '-e',str(project/'build/app-debug.elf'),hex(pc)],text=True)
                                raise AssertionError(f'{mode}/{stage}: {fault}\n{location}')
                            assert time.monotonic()<deadline,'metadata proof exceeded deadline'
                            time.sleep(.025)
                        assert int(channel.command('APP DIAG 9').split()[1])==0
                        assert int(channel.command('APP DIAG 21').split()[1])==0
                        normal.key('home')
                    finally:normal.close()
                with opened(project,'quota') as (workspace,_):
                    if mode=='normal' and stage=='full':
                        filler=directory/'filler';filler.write_bytes(bytes(32*1024*1024-8))
                        value=directory/'value';value.write_bytes(b'01234567')
                        for name,path in [('filler',filler),('value',value)]:
                            subprocess.run([reader,'put-file',workspace/'nand.overlay','file-quota',name,path],
                                check=True,stdout=subprocess.DEVNULL,timeout=90)
                    firmware=args.old_firmware if mode=='unsupported' else ROOT/'dist/lefony-os-prime-g2-vm-native.elf'
                    result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',firmware,
                        workspace=workspace,controls=controls)
                    if mode=='normal' and stage!='initial':
                        exported=retained/(stage+'-value.bin')
                        subprocess.run([reader,'export-file',workspace/'nand.overlay','file-quota','value',exported],
                            check=True,stdout=subprocess.DEVNULL,timeout=30)
                        assert exported.read_bytes()==b'01234567X'
                assert result['result']==1 and result['os_responsive'],result
                cases.append({'mode':mode,'stage':stage,'runtime':result});print('PASS:',mode,stage,flush=True)
    sources=['tests/native/sdk_file_quota.c','vm/test-sdk-file-quota.py','sdk/lib/newlib/files.c',
        'sdk/include/lefony/files_wire.h','sdk/include/lefony/files.h',
        *['ports/lefony-prime-g2/ion/src/prime_g2/'+p for p in
          ('app_storage.cpp','app_document_store.cpp','app_file_store.cpp','app_file_store.h','app_file_session.cpp','native_app.cpp')]]
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested',
        'cases':cases,'sources':{p:digest(ROOT/p) for p in sources}})


if __name__=='__main__':main()

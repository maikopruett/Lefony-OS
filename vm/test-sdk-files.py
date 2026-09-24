#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed installed ARM stdio, simultaneous files, backpatch and cold reopen."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import time
from PIL import Image
from sdk_newlib_probe import ROOT,compile_probe
from build import write_json,digest
from runner import exercise
from replay import Controls
from workspace import opened
from cli import package


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-file-sessions/arm')
    parser.add_argument('--experimental-adapter',action='store_true',help='Use the earlier maintainer adapter instead of the ordinary SDK profile')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='lefony-stdio-') as temporary:
        project=Path(temporary)
        reader_path=project/'reader';reader_path.mkdir()
        reader=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](reader_path)
        if args.experimental_adapter:
            app,build=compile_probe(project,'sdk/experiments/files_probe.c',defines=['NEWLIB_KERNEL_HEAP'],
                                    app_id='files-proof',file_api=True)
        else:
            (project/'src').mkdir()
            shutil.copyfile(ROOT/'sdk/experiments/files_probe.c',project/'src/main.c')
            metadata=json.loads((ROOT/'sdk/examples/c-main/app.json').read_text())
            metadata.update(id='files-proof',name='ARM stdio proof')
            write_json(project/'app.json',metadata)
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1',
                'sources':['src/main.c'],'defines':{'LEFONY_STANDARD_MAIN':1}})
            app=package(project)
            build=json.loads((project/'build/build.json').read_text())
            retained=output/'app';retained.mkdir(exist_ok=True)
            for name in ('app-debug.elf','app.elf','app.map',app.name,'build.json'):
                shutil.copyfile(project/'build'/name,retained/name)
            for name in ('app.json','project.json','sdk.lock.json'):
                shutil.copyfile(project/name,retained/name)
        for cold in (False,True):
            def controls(channel):
                normal=Controls(channel,output)
                try:
                    end=time.monotonic()+120
                    while True:
                        fault=int(channel.command('APP DIAG 9').split()[1])
                        frame=output/('cold.ppm' if cold else 'write.ppm')
                        normal.execute('screendump',{'filename':str(frame)})
                        with Image.open(frame) as source:
                            image=source.convert('RGB')
                            if image.getpixel((40,40))==(255,0,0):
                                line=sum(1<<i for i in range(16) if image.getpixel((i*10+2,2))==(255,255,255))
                                raise AssertionError(f'ARM stdio assertion at source line {line}; fault {fault}')
                            if image.getpixel((40,40))==(33,166,66):
                                assert image.getpixel((2,2))==((255,255,255) if cold else (0,0,0))
                                break
                        assert fault==0,f'ARM fault {fault}'
                        assert time.monotonic()<end,'ARM file workload exceeded deadline'
                        time.sleep(.1)
                    normal.key('home')
                finally:normal.close()
            with opened(project,'stdio') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                                ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=controls)
                exported=output/('cold-output.bin' if cold else 'output.bin')
                metadata=json.loads(subprocess.check_output([reader,'export-file',workspace/'nand.overlay',
                    'files-proof','output',exported],text=True,timeout=30))
                payload=bytearray()
                for i in range(2*(128*1024-128)+37):
                    value=((i*131+(i>>8))^0x5d)&255
                    if value&1:payload.extend((value,value^0xa5))
                expected=b'LFW1'+len(payload).to_bytes(4,'little')+payload
                assert exported.read_bytes()==expected
                oracle={'bytes':metadata['bytes'],'sha256':hashlib.sha256(expected).hexdigest()}
            assert result['result']==1 and result['os_responsive'],result
            cases.append({'case':'cold-oracle' if cold else 'write-backpatch-replace','runtime':result,'host_oracle':oracle})
            print('PASS:',cases[-1]['case'],flush=True)
    write_json(output/'report.json',{'schema':1,'status':'passed','validation':'developer-local',
        'profile':'experimental adapter' if args.experimental_adapter else 'ordinary SDK foreground-newlib-1 startup and file adapters',
        'physical':'not_tested','build':build,'cases':cases,
        'sources':{p:digest(ROOT/p) for p in ('vm/test-sdk-files.py','sdk/experiments/files_probe.c',
          ('sdk/experiments/newlib_files.c' if args.experimental_adapter else 'sdk/lib/newlib/files.c'),'sdk/include/lefony/files_wire.h',
          'ports/lefony-prime-g2/ion/src/prime_g2/app_file_session.cpp',
          'ports/lefony-prime-g2/ion/src/prime_g2/app_management.cpp')}})


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed ARM font measurements, Unicode policy, clipping and rejected-call atomicity."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from replay import Controls
from runner import exercise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--old-firmware',type=Path,required=True)
    args=parser.parse_args();output=ROOT/'build/sdk-ui/typography';output.mkdir(parents=True,exist_ok=True)
    report={'schema':1,'status':'running','cases':[],'firmware_sha256':digest(args.firmware),'physical':'not_tested'}
    with tempfile.TemporaryDirectory(prefix='sdk-text-') as temp:
        for mode in ('baseline','normal','denied','unsupported'):
            project=Path(temp)/mode;(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_typography.c',project/'src/main.c')
            enabled=mode in ('normal','baseline')
            write_json(project/'app.json',{'abi':1,'id':'typography','name':'Typography','version':'1.0.0',
                'license':'GPL-3.0-or-later','schema':1,'minimum_api':9 if enabled else 3,
                'required_capabilities':1040 if enabled else 16,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],'arguments':[mode]})
            artifact=package(project)
            folder=output/mode;folder.mkdir(exist_ok=True)
            for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,folder/name)
            def controls(channel):
                normal=Controls(channel,folder)
                try:normal.run({'steps':[{'program_exit':0},{'capture':'frame'}]},[])
                finally:normal.close()
            result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.old_firmware if mode=='unsupported' else args.firmware,controls=controls)
            assert result['result']==1 and result['os_responsive'],result
            report['cases'].append({'mode':mode,'runtime':result});print('PASS:',mode,flush=True)
    with Image.open(output/'baseline/frame.ppm') as a,Image.open(output/'normal/frame.ppm') as b:
        assert a.tobytes()==b.tobytes(),'Rejected requests changed the surface'
        for y in range(140,180):
            for x in range(320):
                if not (20<=x<100 and 152<=y<160):assert a.getpixel((x,y))==(255,255,255),'Clip escaped'
        a.save(output/'fonts.png')
    report['status']='passed';report['sources']={p:digest(ROOT/p) for p in
        ('tests/native/sdk_typography.c','vm/test-sdk-typography.py','sdk/include/lefony/text.h',
         'sdk/include/lefony/text_wire.h','ports/lefony-prime-g2/ion/src/prime_g2/app_text.h',
         'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp')}
    write_json(output/'report.json',report)


if __name__=='__main__':main()

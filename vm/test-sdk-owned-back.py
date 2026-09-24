#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""SDK cleanup commits data even when an ordinary main app owns Back."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    output=ROOT/'build/sdk-doom/owned-back';output.mkdir(parents=True,exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='lefony-owned-back-') as temp:
        project=Path(temp);(project/'src').mkdir()
        (project/'src/main.c').write_text('''#include <lefony/app_c.h>
#include <stdio.h>
#include <stdint.h>
int main(void) {
  uint32_t navigation[]={16,1,0,1},visits=0;
  if(lefony_service(9,navigation)) return 1;
  FILE *f=fopen("visits","rb");
  if(f) { if(fread(&visits,4,1,f)!=1 || fclose(f)) return 2; }
  uint32_t previous=visits++;
  f=fopen("visits","wb");if(!f || fwrite(&visits,4,1,f)!=1 || fclose(f)) return 3;
  lefony_fill((lefony_rect_t){0,0,320,240,previous?LEFONY_GREEN:LEFONY_WHITE});
  return 0;
}
''')
        write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']})
        write_json(project/'app.json',{'abi':1,'id':'owned-back','name':'Owned Back','version':'0.1.0',
            'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':3,'required_capabilities':28,
            'optional_capabilities':0,'data_schema':0})
        app=package(project);helper=project/'helper';helper.mkdir()
        fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
        with opened(project,'visits') as (workspace,_):
            for cold in (False,True):
                def controls(channel):
                    normal=Controls(channel,output)
                    try:
                        normal.run({'steps':[{'program_exit':0},{'capture':'cold' if cold else 'first'}]},[])
                        with Image.open(normal.frames['cold' if cold else 'first']) as frame:
                            assert frame.convert('RGB').getpixel((10,10))==((33,166,66) if cold else (255,255,255))
                        # Deliberately leave shutdown to the ordinary runner.
                    finally:normal.close()
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=controls)
                assert result['result']==1 and result['program']['exit_status']==0
                assert result['workspace_cleanup']=='home-and-storage-drain'
                exported=output/('cold-count' if cold else 'first-count')
                subprocess.run([fixture,'export-file',workspace/'nand.overlay','owned-back','visits',exported],
                    check=True,timeout=30,stdout=subprocess.DEVNULL)
                assert int.from_bytes(exported.read_bytes(),'little')==(2 if cold else 1)
                cases.append({'cold':cold,'runtime':result,'saved_count':2 if cold else 1})
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested','cases':cases,
        'sources':{name:digest(ROOT/name) for name in ['sdk/tools/runner.py','vm/test-sdk-owned-back.py']}})
    print('PASS: SDK cleanup uses OS-owned Home; data survives cold boot with app-owned Back',flush=True)


if __name__=='__main__':main()

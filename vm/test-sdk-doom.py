#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local signed ARM Doom qualification, with synthetic production FILE4 assets.

The complete release source/license audit is separate; these binaries stay local.
Normal KPP controls enter the game. Fixture access only imports/exports bytes
while the guest is stopped and does not invoke game logic or private app hooks.
"""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
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
    parser.add_argument('--project',type=Path,default=ROOT/'build/sdk-doom/launch-project')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-doom/launch')
    args=parser.parse_args();project=args.project.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    app=package(project)
    helper=output/'helper';helper.mkdir(exist_ok=True)
    fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
    asset=ROOT/'build/sdk-1.0-upstream/freedoom1.wad'
    expected=json.loads((ROOT/'sdk/ports/doom/assets.json').read_text())['files']['freedoom1.wad']['sha256']
    assert digest(asset)==expected
    measurements=[]
    with opened(project,'game') as (workspace,_):
        seed=not (output/'seed.json').exists()
        if seed:
            def missing(channel):
                normal=Controls(channel,output)
                try:
                    normal.run({'steps':[{'program_exit':-1},{'capture':'missing-wad'}]},[])
                finally:normal.close()
            result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=missing)
            assert result['program']['exit_status']==-1,result
            write_json(output/'missing-wad.json',result)
            subprocess.run([fixture,'put-file',workspace/'nand.overlay','doom-proof','freedoom1.wad',asset],
                check=True,timeout=180)
            exported=output/'seed-check.wad'
            subprocess.run([fixture,'export-file',workspace/'nand.overlay','doom-proof','freedoom1.wad',exported],
                check=True,timeout=180)
            assert digest(exported)==expected
            write_json(output/'seed.json',{'wad_sha256':expected,'bytes':asset.stat().st_size,
                'workspace':str(workspace),'package_sha256':digest(app)})
        def play(channel):
            normal=Controls(channel,output)
            def value(index):return int(channel.command(f'APP DIAG {index}').split()[1])
            def frame(name):
                p=output/(name+'.ppm');normal.execute('screendump',{'filename':str(p)})
                with Image.open(p) as image:return image.convert('RGB')
            def running():
                assert value(9)==0,('Doom fault',hex(value(10)))
                assert not value(15),('Doom exited',value(21))
            try:
                start=time.monotonic();end=start+180
                while True:
                    picture=frame('loading');running()
                    # The loading/error screen is monochrome; actual game
                    # rendering has a textured world and colored HUD.
                    colors=len(picture.crop((0,20,320,220)).getcolors(64001) or [])
                    if colors>128:break
                    assert time.monotonic()<end,('Doom loading deadline',colors)
                    time.sleep(.2)
                picture.save(output/'first-frame.png')
                measurements.append({'case':'first-colored-frame','seconds':time.monotonic()-start,'colors':colors})
                time.sleep(2);normal.keys(['up']);time.sleep(1.5);normal.keys([]);time.sleep(.3)
                running();moved=frame('movement');assert moved.tobytes()!=picture.tobytes()
                moved.save(output/'movement.png')
                normal.keys(['right','xnt']);time.sleep(1);normal.keys([]);time.sleep(.3)
                running();frame('turn-and-fire').save(output/'turn-and-fire.png')
                normal.key('back');running();frame('menu').save(output/'menu.png')
                normal.key('back');running();frame('menu-closed').save(output/'menu-closed.png')
                measurements.append({'case':'movement-turn-fire-menu','status':'screens-captured-not-yet-semantic-acceptance'})
                normal.key('home');assert channel.command('PING')=='PONG'
                assert channel.command('STATE').split(' home_row=')[0]!=channel.native_state
            finally:normal.close()
        result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
            ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=play)
        assert result['result']==1 and result['os_responsive'],result
    for name in ['app-debug.elf','app.elf','app.map','build.json',app.name]:shutil.copy2(project/'build'/name,output/name)
    write_json(output/'report.json',{'schema':1,'status':'running-gameplay-qualification-incomplete',
        'runtime':result,'measurements':measurements,'wad_sha256':expected,
        'distribution':'development candidate; final source and license audit required','physical':'not_tested',
        'sources':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'sdk/ports/doom/platform.c',
            ROOT/'scripts/prepare_sdk_doom.py',ROOT/'sdk/lib/newlib/files.c',ROOT/'sdk/tools/runner.py',Path(__file__)]}})
    print('Doom launched and normal-input frames retained; semantic gameplay/save qualification remains',flush=True)


if __name__=='__main__':main()

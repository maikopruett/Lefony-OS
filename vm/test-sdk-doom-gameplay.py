#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Doom gameplay and cold save/load through normal keys, observed with real GDB.

GDB only reads engine state and resumes execution; it never calls game functions,
sets game variables or synthesizes app input. Debug pauses are not FPS evidence.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import re
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
    parser.add_argument('--project',type=Path,default=ROOT/'build/sdk-doom/gameplay-project')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-doom/gameplay')
    parser.add_argument('--workspace',default='game',help='Existing seeded synthetic workspace; preserve failed attempts by cloning it')
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--measure-resources',action='store_true')
    args=parser.parse_args();project=args.project.resolve();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True);app=package(project)
    gdb=shutil.which('arm-none-eabi-gdb');assert gdb,'Real ARM GDB is required'
    helper=output/'helper';helper.mkdir(exist_ok=True)
    fixture=runpy.run_path(str(ROOT/'vm/test-sdk-documents.py'))['fixture'](helper)
    observations={};cases=[];saved=None
    with opened(project,args.workspace) as (workspace,_):
        wad=output/'verified.wad'
        subprocess.run([fixture,'export-file',workspace/'nand.overlay','doom-proof','freedoom1.wad',wad],
            check=True,timeout=180)
        spec=json.loads((ROOT/'sdk/ports/doom/assets.json').read_text())
        assert digest(wad)==spec['files']['freedoom1.wad']['sha256']
        for cold in (False,True):
            prefix='cold-' if cold else 'first-';script=project/'build/debug.gdb';script.unlink(missing_ok=True)
            def attach_at_main():
                end=time.monotonic()+180
                while not script.exists():
                    assert time.monotonic()<end,'main debugger setup deadline';time.sleep(.05)
                result=subprocess.run([gdb,'--nx','--batch','-x',str(script),'-ex','delete breakpoints','-ex','detach'],
                    capture_output=True,text=True,timeout=120)
                (output/(prefix+'main-gdb.log')).write_text(result.stdout+result.stderr)
                assert result.returncode==0 and 'main (' in result.stdout,result.stdout+result.stderr
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                initial=pool.submit(attach_at_main)
                def controls(channel):
                    nonlocal saved
                    initial.result(timeout=180);normal=Controls(channel,output)
                    endpoint=Path(channel.socket.getpeername()).parent/'gdb'
                    def value(i):return int(channel.command(f'APP DIAG {i}').split()[1])
                    def capture(name):
                        path=output/(prefix+name+'.ppm');normal.execute('screendump',{'filename':str(path)})
                        with Image.open(path) as im:im.save(path.with_suffix('.png'))
                    def observe(name):
                        assert not value(9) and not value(15),('game fault/exit',value(9),value(10),value(21))
                        player='players[consoleplayer]'
                        fields={'state':'gamestate','tics':'gametic','episode':'gameepisode','map':'gamemap',
                            'health':player+'.health','ammo':player+'.ammo[0]',
                            'fire_binding':'key_fire','use_binding':'key_use',
                            'strafe_left_binding':'key_strafeleft','strafe_right_binding':'key_straferight',
                            'x':player+'.mo ? '+player+'.mo->x : 0',
                            'y':player+'.mo ? '+player+'.mo->y : 0',
                            'angle':player+'.mo ? (unsigned int)'+player+'.mo->angle : 0',
                            'menu':'menuactive','message':'messageToPrint','save_entry':'saveStringEnter',
                            'save_error':'savegame_error','save_request':'sendsave','action':'gameaction',
                            'leveltime':'leveltime','heap_peak':'*(unsigned int *)&__malloc_max_sbrked_mem'}
                        formats=['%u' if k in ('angle','heap_peak') else '%d' for k in fields]
                        command='printf "OBSERVE '+','.join(formats)+'\\n", '+', '.join('('+v+')' for v in fields.values())
                        result=subprocess.run([gdb,'--nx','--batch','--quiet',str(project/'build/app-debug.elf'),
                            '-ex','set pagination off','-ex','target remote '+str(endpoint),'-ex',command,'-ex','detach'],
                            capture_output=True,text=True,timeout=30)
                        (output/(prefix+name+'-gdb.log')).write_text(result.stdout+result.stderr)
                        match=re.search(r'^OBSERVE ([0-9,\-]+)$',result.stdout,re.M)
                        assert result.returncode==0 and match,result.stdout+result.stderr
                        state=dict(zip(fields,map(int,match[1].split(',')),strict=True))
                        observations[prefix+name]=state;return state
                    def until(name,predicate,timeout=60):
                        end=time.monotonic()+timeout
                        while True:
                            state=observe(name)
                            if predicate(state):return state
                            assert time.monotonic()<end,(name,state);time.sleep(.25)
                    def pose(state):return tuple(state[k] for k in ('x','y','angle','ammo'))
                    def load():
                        normal.key('symb');until('load-menu',lambda s:s['menu']==1)
                        normal.key('ok')
                        # G_DoLoadGame clears gameaction before restoring the
                        # level. Matching player fields alone can be observed
                        # mid-load. Advancing past the post-save level clock
                        # proves the restored game has resumed ticking.
                        result=until('loaded',lambda s:s['menu']==0 and s['action']==0 and
                            s['leveltime']>saved['leveltime'] and pose(s)==pose(saved),timeout=90)
                        capture('loaded');return result
                    try:
                        start=until('start',lambda s:s['state']==0 and s['tics']>2 and s['health']>0,timeout=180)
                        assert start['episode']==1 and start['map']==1,start
                        # This fixture uses the port defaults, including its
                        # four virtual action keys saved outside DOS scancodes.
                        assert tuple(start[k] for k in ('fire_binding','use_binding','strafe_left_binding','strafe_right_binding'))==(0xa3,0xa2,0xa0,0xa1),start
                        time.sleep(2);capture('world')
                        if cold:
                            restored=load();assert pose(restored)==pose(saved)
                            try:
                                normal.keys(['xnt'])
                                until('cold-fired',lambda s:s['ammo']<restored['ammo'])
                            finally:normal.keys([])
                            capture('cold-fired')
                        else:
                            normal.keys(['up']);time.sleep(1.2);normal.keys([]);time.sleep(.7)
                            moved=observe('moved');assert (moved['x'],moved['y'])!=(start['x'],start['y'])
                            normal.keys(['right','xnt']);time.sleep(1.2);normal.keys([]);time.sleep(.7)
                            fired=observe('turned-fired');capture('turned-fired')
                            assert fired['angle']!=moved['angle'] and fired['ammo']<moved['ammo'],(moved,fired)
                            normal.key('back');assert observe('menu-open')['menu']==1;capture('menu')
                            normal.key('back');assert observe('menu-closed')['menu']==0
                            normal.key('num');until('save-menu',lambda s:s['menu']==1)
                            normal.key('ok');until('save-name',lambda s:s['save_entry']==1)
                            for _ in range(24):normal.key('backspace')
                            for key in ('one','two','three'):normal.key(key)
                            before=observe('before-save');normal.key('ok')
                            saved=until('saved',lambda s:s['menu']==0 and not s['save_entry'] and not s['save_request'] and s['action']==0)
                            assert not saved['save_error'] and pose(saved)==pose(before),(before,saved)
                            capture('saved')
                            normal.keys(['left','up']);time.sleep(1.5);normal.keys([]);time.sleep(.7)
                            wandered=observe('wandered');assert pose(wandered)!=pose(saved)
                            load()
                        # Complete the ordinary engine Quit path, including its
                        # configuration saves and successful main exit, then let
                        # the SDK's Home cleanup finish the normal transaction.
                        normal.key('toolbox');until('quit-confirmation',lambda s:s['message']!=0)
                        capture('quit-confirmation');normal.key('ok')
                        # Real configuration commits verify the large WAD root.
                        # This bounded maintainer deadline is not a frame-time
                        # or physical-performance qualification budget.
                        quit_started=time.monotonic()
                        while not value(15):
                            assert not value(9),('quit fault',value(9),value(10))
                            assert time.monotonic()-quit_started<180,'configuration quit deadline'
                            time.sleep(.1)
                        assert value(21)==0,('quit status',value(21))
                        observations[prefix+'quit']={'elapsed_seconds':time.monotonic()-quit_started}
                    finally:normal.close()
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    args.firmware,workspace=workspace,controls=controls,
                    debug_project=project,debug_timeout=180,measure_resources=args.measure_resources)
                initial.result()
            assert result['result']==1 and result['program']['exit_status']==0,result
            save=output/(prefix+'doomsav0.dsg')
            subprocess.run([fixture,'export-file',workspace/'nand.overlay','doom-proof','.savegame/doomsav0.dsg',save],
                check=True,timeout=90)
            assert save.read_bytes().startswith(b'123\0') and save.stat().st_size>1000
            if cold:assert save.read_bytes()==(output/'first-doomsav0.dsg').read_bytes()
            cases.append({'cold':cold,'runtime':result,'save_bytes':save.stat().st_size,'save_sha256':digest(save)})
            write_json(output/'progress.json',{'status':'in_progress','cases':cases,'observations':observations})
            print('PASS:',prefix+'gameplay/save/load/clean-quit',flush=True)
    for name in ['app-debug.elf','app.elf','app.map','build.json',app.name]:shutil.copy2(project/'build'/name,output/name)
    write_json(output/'report.json',{'schema':1,'status':'gameplay-and-cold-save-passed','physical':'not_tested',
        'distribution':'development candidate; final source and license audit required','debug':'read-only observations; timing not qualified',
        'cases':cases,'observations':observations,'peak_sbrk_bytes':max(s['heap_peak'] for s in observations.values() if 'heap_peak' in s),
        'sources':{name:digest(ROOT/name) for name in ['sdk/ports/doom/platform.c','scripts/prepare_sdk_doom.py',
            'sdk/lib/newlib/files.c','sdk/tools/runner.py','vm/test-sdk-doom-gameplay.py']}})
    print('PASS: normal-input Doom gameplay, save/reload, cold saved state and clean exit',flush=True)


if __name__=='__main__':main()

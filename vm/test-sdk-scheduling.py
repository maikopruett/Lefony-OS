#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify foreground wakes, UI timer progress and input through normal dispatch."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from cli import package
from replay import Controls,KEYS
from runner import exercise
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-foreground-scheduling/arm')
    parser.add_argument('--cadence-only',action='store_true',help='Measure the same guest yields on an earlier candidate')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    measurements={}
    with tempfile.TemporaryDirectory(prefix='lefony-scheduling-') as temporary:
        project=Path(temporary);(project/'src').mkdir()
        (project/'src/main.c').write_bytes((ROOT/'sdk/experiments/scheduling_probe.c').read_bytes())
        write_json(project/'app.json',{'abi':1,'id':'scheduling-proof','name':'Scheduling proof',
                   'version':'0.1.0','license':'CC-BY-NC-SA-4.0'})
        app=package(project)
        def controls(channel):
            normal=Controls(channel,output)
            def diagnostic(index):
                reply=channel.command(f'APP DIAG {index}');assert reply.startswith('VALUE '),reply
                return int(reply.split()[1])
            def capture(name):
                path=output/(name+'.ppm')
                normal.execute('screendump',{'filename':str(path)})
                with Image.open(path) as img: return img.convert('RGB')
            def number(img,y):
                return sum(1<<bit for bit in range(32) if img.getpixel((bit*5+2,y+2))==(33,166,66))
            def edge(name,down):
                row,col=KEYS[name]
                normal.qtest.file.write(f'writew 0x020b8008 {(row<<8)|col|(0x8000 if down else 0):#x}\n'.encode())
                while True:
                    reply=normal.qtest.file.readline(4096)
                    if reply.startswith(b'IRQ'): continue
                    assert reply.startswith(b'OK'),reply;break
            def hold(name,duration):
                try: edge(name,True);time.sleep(duration)
                finally: edge(name,False)
                time.sleep(.4)
            try:
                end=time.monotonic()+20
                while True:
                    assert diagnostic(9)==0,'foreground workload faulted'
                    frame=capture('ready')
                    if frame.getpixel((205,5))==(33,166,66): break
                    assert time.monotonic()<end,'32 guest yields did not finish'
                    time.sleep(.1)
                measurements.update(yields=32,yield_total_model_ms=number(frame,0),
                                    yield_max_gap_model_ms=number(frame,12))
                if args.cadence_only: return
                # Regression ceilings distinguish prompt foreground scheduling
                # from the old 300 ms timer; they are not physical FPS targets.
                assert measurements['yield_total_model_ms']<320,measurements
                assert measurements['yield_max_gap_model_ms']<200,measurements
                before=diagnostic(20);start=int(channel.command('TIME GET').split()[1])
                normal.key('ok');time.sleep(.2)
                frame=capture('input-preserved');assert frame.getpixel((205,35))==(33,166,66)
                hold('backspace',1.0)
                frame=capture('repeat');assert frame.getpixel((225,35))==(33,166,66)
                hold('right',.8)
                frame=capture('direction-held');assert number(frame,54)==1
                normal.key('right')
                frame=capture('direction-repressed');assert number(frame,54)==2
                normal.run({'steps':[{'touch':[[7,90,110]]},{'touch':[]}]},[])
                frame=capture('input');assert frame.getpixel((245,35))==(33,166,66)
                elapsed=int(channel.command('TIME GET').split()[1])-start;ticks=diagnostic(20)-before
                assert max(1,elapsed//300-2)<=ticks<=elapsed//300+2,(elapsed,ticks)
                measurements.update(observed_model_ms=elapsed,ui_timer_ticks=ticks,foreground_wakes=diagnostic(19))
                # Leave through the same KPP Home path used by ordinary apps.
                normal.key('home');assert channel.command('PING')=='PONG'
                assert channel.command('STATE').split(' home_row=')[0]!=channel.native_state
                # Home unload resets counters; they remain zero in the menu
                # until the next launch starts a fresh foreground session.
                assert diagnostic(19)==0
                time.sleep(.4);assert diagnostic(19)==0
                assert channel.command(f'APP OPEN {channel.installed_slot}')=='OK'
                end=time.monotonic()+5
                while diagnostic(19)<32:
                    assert diagnostic(9)==0 and time.monotonic()<end
                    time.sleep(.05)
                frame=capture('relaunch');assert number(frame,54)==0
                normal.key('home')
            finally: normal.close()
        with opened(project,'scheduling') as (workspace,_):
            result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.firmware.resolve(),
                            workspace=workspace,controls=controls)
        assert result['result']==1 and result['os_responsive'],result
        sources=['sdk/experiments/scheduling_probe.c','vm/test-sdk-scheduling.py',
                 'scripts/prepare_prime_native_scheduling.py',
                 'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
                 'ports/lefony-prime-g2/ion/src/prime_g2/events.cpp',
                 'ports/lefony-prime-g2/apps/native_apps/app.cpp']
        if args.cadence_only:
            # An older ELF is identified by its own digest. Current kernel
            # sources are not evidence of the sources used to build that ELF.
            sources=sources[:2]
        write_json(output/'report.json',{'schema':1,'status':'measured' if args.cadence_only else 'passed',
                   'profile':'VM execution experiment; physical timing unqualified',
                   'measurements':measurements,'runtime':result,'sources':{p:digest(ROOT/p) for p in sources}})
        print(json.dumps(measurements));print('MEASURED' if args.cadence_only else 'PASS: foreground scheduling, timers, input/repeat, Home and relaunch')


if __name__=='__main__': main()

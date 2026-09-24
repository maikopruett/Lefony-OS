#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real C input stream via normal KPP/Goodix, including sleep and overflow."""
import argparse
import json
from pathlib import Path
import shutil
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
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-input-stream/arm')
    parser.add_argument('--firmware',type=Path,default=ROOT/'dist/lefony-os-prime-g2-vm-native.elf')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for denied in (False,True):
        name='undeclared' if denied else 'input-stream'
        retained=output/name;retained.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='lefony-input-stream-') as temp:
            project=Path(temp);(project/'src').mkdir()
            (project/'src/main.c').write_bytes((ROOT/'sdk/experiments/input_stream_probe.c').read_bytes())
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c'],
                        'defines':{'INPUT_STREAM_UNDECLARED':1} if denied else {}})
            write_json(project/'app.json',{'abi':1,'id':'input-stream','name':'Input Stream',
                'version':'0.1.0','license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':4,
                'required_capabilities':16 if denied else 52,'optional_capabilities':0,'data_schema':0})
            app=package(project)
            for source in ['app.json','project.json','sdk.lock.json']:
                shutil.copy2(project/source,retained/source)
            shutil.copytree(project/'build',retained/'build',dirs_exist_ok=True)
            snapshots={}
            def controls(channel):
                normal=Controls(channel,retained)
                def diagnostic(index):return int(channel.command(f'APP DIAG {index}').split()[1])
                def capture(label):
                    assert diagnostic(9)==0,('fault',hex(diagnostic(10)))
                    p=retained/(label+'.ppm');normal.execute('screendump',{'filename':str(p)})
                    with Image.open(p) as im:
                        im=im.convert('RGB')
                        return [sum(1<<bit for bit in range(32) if im.getpixel((bit*5+2,row*10+2))==(33,166,66)) for row in range(15)]
                def until(label,predicate,timeout=15):
                    end=time.monotonic()+timeout
                    while True:
                        values=capture(label)
                        if predicate(values):snapshots[label]=values;return values
                        assert time.monotonic()<end,(label,values)
                        time.sleep(.05)
                def held(v,*keys):
                    value=sum(1<<(KEYS[k][0]*8+KEYS[k][1]) for k in keys)
                    return v[1]==value&0xffffffff and v[2]==value>>32
                def touch(contacts):
                    before=diagnostic(8)
                    command='TOUCH FRAME '+str(len(contacts))+''.join(' '+' '.join(map(str,c)) for c in contacts)
                    assert channel.command(command)=='OK'
                    end=time.monotonic()+3
                    while diagnostic(8)==before:
                        assert time.monotonic()<end,('touch not dispatched',contacts)
                        time.sleep(.02)
                try:
                    until('ready',lambda v:v[0]==0x123456)
                    if denied:
                        normal.run({'steps':[{'program_exit':0}]},[]);return
                    normal.keys(['left','right'])
                    first=until('chord',lambda v:held(v,'left','right') and v[3]==1 and v[5]==1)
                    time.sleep(.4);second=capture('held-no-repeat');assert second[3:7]==first[3:7]
                    normal.keys(['right']);until('left-released',lambda v:held(v,'right') and v[4]==1)
                    normal.keys([]);until('all-released',lambda v:held(v) and v[6]==1)
                    normal.keys(['left','shift']);until('modifier-chord',lambda v:v[9]&2 and v[14]&1)
                    normal.keys([]);until('modifier-released',lambda v:held(v) and v[4]==2)
                    normal.keys(['back']);until('back-owned',lambda v:v[9]&64)
                    normal.keys([]);until('back-released',lambda v:held(v))
                    touch([[7,90,110]])
                    touch([[7,90,110],[2,200,120]])
                    touch([[2,180,130],[7,100,110]])
                    until('two-contacts',lambda v:v[9]&4 and v[12]>>8==2)
                    touch([[9,10,90]])
                    until('touch-cancel',lambda v:v[9]&16)
                    normal.run({'steps':[{'touch':[]},{'touch':[[3,110,120]]},{'touch':[]}]},[])
                    until('touch-release',lambda v:v[9]&8 and v[12]>>8==0)
                    # A sleep preserves app execution while normal input fills
                    # the finite queue; no UART call invokes the app directly.
                    normal.keys(['two']);until('sleeping',lambda v:v[13]==1)
                    normal.keys([])
                    touch([[3,20,100]])
                    for i in range(40):touch([[3,21+i,100]])
                    touch([]);normal.keys(['right'])
                    overflow=until('overflow-resync',lambda v:v[9]&32 and held(v,'right') and not v[13],timeout=20)
                    assert overflow[10]>32,overflow
                    normal.key('home');assert channel.command('PING')=='PONG'
                    assert channel.command('STATE').split(' home_row=')[0]!=channel.native_state
                    if hasattr(channel,'wait_for_storage'):channel.wait_for_storage(timeout=10)
                    assert channel.command(f'APP OPEN {channel.installed_slot}')=='OK'
                    relaunched=until('held-key-relaunch',lambda v:v[0]==0x123456 and held(v) and v[3]==0 and v[5]==0)
                    assert relaunched[11]!=overflow[11]
                    normal.keys([]);time.sleep(.15);normal.keys(['right'])
                    until('fresh-press-after-relaunch',lambda v:held(v,'right') and v[5]==1)
                    normal.keys([]);normal.key('home');assert channel.command('PING')=='PONG'
                finally:normal.close()
            with opened(project,'input') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    args.firmware,workspace=workspace,controls=controls)
            assert result['result']==1 and result['os_responsive'],result
            cases.append({'case':name,'runtime':result,'snapshots':snapshots})
            print('PASS:',name,flush=True)
    sources=['sdk/experiments/input_stream_probe.c','sdk/include/lefony/input_stream.h',
             'sdk/include/lefony/input_stream_wire.h','sdk/tools/replay.py','vm/test-sdk-input-stream.py',
             'ports/lefony-prime-g2/ion/src/prime_g2/app_input_stream.h',
             'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
             'ports/lefony-prime-g2/ion/src/prime_g2/events.cpp','scripts/prepare_prime_native_scheduling.py']
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested','cases':cases,
                                   'sources':{s:digest(ROOT/s) for s in sources}})


if __name__=='__main__':main()

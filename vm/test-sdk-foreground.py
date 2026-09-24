#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed installed public foreground runtime, pixels, waits and isolation."""
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import time
from PIL import Image
from sdk_newlib_probe import ROOT,compile_probe
from build import digest,write_json
from lfapp import pack
from runner import exercise
from replay import Controls
from workspace import opened


def main():
    output=ROOT/'build/sdk-foreground/arm';output.mkdir(parents=True,exist_ok=True)
    cases=[]
    variants=[(None,1),('FOREGROUND_UNDECLARED',1),('FOREGROUND_SPIN',1),
              ('FOREGROUND_LONG_SLEEP',1),('FOREGROUND_UNNEGOTIATED',-14),
              ('FOREGROUND_LOW_GUARD',-14),('FOREGROUND_HIGH_GUARD',-14),('FOREGROUND_EXECUTE',-13)]
    for variant,expected in variants:
        name=variant or 'allocation-registers-sleep-pixels'
        with tempfile.TemporaryDirectory(prefix='lefony-foreground-') as temporary:
            project=Path(temporary)
            app,build=compile_probe(project,'sdk/experiments/foreground_probe.c',
                defines=['NEWLIB_KERNEL_HEAP',*([variant] if variant else [])],
                foreground=True,app_id='foreground-proof',
                extra_sources=['sdk/experiments/foreground_registers.s'])
            if variant=='FOREGROUND_UNDECLARED':
                metadata=json.loads((project/'app.json').read_text());metadata['required_capabilities']=0
                write_json(project/'app.json',metadata);app.write_bytes(pack(metadata,(project/'app.elf').read_bytes()))
            retained=output/name;retained.mkdir(exist_ok=True)
            for artifact in ('app-debug.elf','app.elf','app.map','app.lfapp','app.json'):
                shutil.copy2(project/artifact,retained/artifact)
            measurements={}
            def controls(channel):
                normal=Controls(channel,output)
                def value(index):
                    v=int(channel.command(f'APP DIAG {index}').split()[1]);return v-2**32 if v>=2**31 else v
                def pixel():
                    frame=output/(name+'.ppm');normal.execute('screendump',{'filename':str(frame)})
                    with Image.open(frame) as image:return image.convert('RGB').getpixel((40,40))
                def wait(color=None):
                    deadline=time.monotonic()+90
                    while time.monotonic()<deadline:
                        fault=value(9)
                        if fault:
                            if expected>=0 or fault!=expected:
                                print('Unexpected fault',name,fault,hex(value(10)),flush=True)
                                print(subprocess.check_output(['arm-none-eabi-addr2line','-f','-i','-e',
                                    str(project/'app-debug.elf'),hex(value(10))],text=True),flush=True)
                            assert expected<0 and fault==expected,(name,fault);return
                        if color is not None and pixel()==color:return
                        if color is None and value(15):return
                        time.sleep(.025)
                    raise AssertionError(name+': did not reach expected state')
                try:
                    if variant in ('FOREGROUND_SPIN','FOREGROUND_LONG_SLEEP'):
                        wait((0,0,255));assert value(9)==0
                        if variant=='FOREGROUND_LONG_SLEEP':
                            # Ordinary keypad events must not resume user code
                            # before its requested sleep deadline.
                            deadline=time.monotonic()+10
                            while value(13)<2:
                                assert time.monotonic()<deadline;time.sleep(.01)
                            resumed=value(14);normal.key('one');time.sleep(.05)
                            assert value(14)==resumed and value(9)==0
                        before=channel.command('STATE').split(' home_row=')[0]
                        started=time.monotonic();normal.key('home')
                        measurements['home_wall_ms']=round((time.monotonic()-started)*1000)
                        assert channel.command('STATE').split(' home_row=')[0]!=before
                        assert channel.command('PING')=='PONG'
                        deadline=time.monotonic()+15
                        while channel.command(f'APP OPEN {channel.installed_slot}')!='OK':
                            assert time.monotonic()<deadline;time.sleep(.025)
                        wait((0,0,255));measurements['same_os_relaunch']='passed';normal.key('home')
                    elif variant=='FOREGROUND_UNDECLARED':
                        wait((33,166,66));assert value(9)==0 and value(12)==0
                    elif expected<0:wait()
                    else:
                        wait();assert value(9)==0
                        normal.run({'steps':[{'capture':'copied-pixels'},
                            {'pixel':['copied-pixels',40,40,[33,166,66]]},
                            {'pixel':['copied-pixels',200,40,[255,255,255]]},
                            {'pixel':['copied-pixels',40,200,[255,255,255]]},
                            {'pixel':['copied-pixels',200,200,[33,166,66]]}]},[])
                        measurements.update(preemptions=value(12),yields=value(13),resumes=value(14),
                            heap_setup_model_ms=value(16),heap_bytes=value(17),kernel_heap_bytes=value(18))
                        assert measurements['preemptions']>0 and measurements['yields']>=3
                        normal.key('ok');assert value(15)==1 and value(9)==0
                        normal.key('home')
                        deadline=time.monotonic()+15
                        while channel.command(f'APP OPEN {channel.installed_slot}')!='OK':
                            assert time.monotonic()<deadline;time.sleep(.025)
                        wait();assert value(9)==0
                        measurements['same_os_zeroed_relaunch']='passed'
                finally:normal.close()
            with opened(project,'foreground') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=controls)
            assert result['result']==expected and result['os_responsive'],result
            cases.append({'case':name,'runtime':result,'build':build,'measurements':measurements})
            print('PASS:',name,flush=True)
    sources=['vm/test-sdk-foreground.py','sdk/include/lefony/foreground_wire.h',
        'sdk/include/lefony/foreground.h','ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
        'ports/lefony-prime-g2/ion/src/prime_g2/system.cpp']
    write_json(output/'report.json',{'schema':1,'status':'passed','profile':'API 3 foreground profile 1',
        'physical':'not_tested','cases':cases,'sources':{p:digest(ROOT/p) for p in sources}})


if __name__=='__main__':main()

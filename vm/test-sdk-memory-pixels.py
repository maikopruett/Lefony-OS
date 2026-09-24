#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed ARM large allocation, guarded heap, copied pixels and recovery."""
import json
from pathlib import Path
import tempfile
import time
from sdk_newlib_probe import ROOT,compile_probe
from build import write_json,digest
from runner import exercise
from replay import Controls
from workspace import opened


def main():
    output=ROOT/'build/sdk-memory-pixels'
    output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for variant,expected in [(None,1),('HEAP_UNNEGOTIATED',-14),('HEAP_LOW_GUARD',-14),
                             ('HEAP_HIGH_GUARD',-14),('HEAP_EXECUTE',-13)]:
        with tempfile.TemporaryDirectory(prefix='lefony-memory-') as directory:
            project=Path(directory)
            app,build=compile_probe(project,'sdk/experiments/memory_pixels_probe.c',
                defines=['NEWLIB_KERNEL_HEAP',*([variant] if variant else [])],app_id='memory-pixels')
            measurements=[]
            def controls(channel):
                normal=Controls(channel,output)
                def value(index):
                    return int(channel.command(f'APP DIAG {index}').split()[1])
                def wait():
                    end=time.monotonic()+30
                    while time.monotonic()<end:
                        fault=value(9)
                        if fault:
                            if fault>=2**31: fault-=2**32
                            assert expected<0 and fault==expected,(variant,fault)
                            return
                        if value(15):
                            assert expected==1
                            return
                        time.sleep(.05)
                    raise AssertionError('memory workload did not finish')
                try:
                    wait()
                    if expected==1:
                        for launch in range(2):
                            if launch:
                                normal.key('home')
                                end=time.monotonic()+15
                                while channel.command(f'APP OPEN {channel.installed_slot}')!='OK':
                                    assert time.monotonic()<end,'saved app did not reopen'
                                    time.sleep(.05)
                                wait()
                            capture=f'launch-{launch}'
                            steps=[{'capture':capture}]
                            for x,y,color in [(20,20,[33,166,66]),(200,20,[255,255,255]),
                                              (20,200,[255,255,255]),(200,200,[33,166,66]),
                                              (2,2,[33,166,66] if launch else [255,255,255])]:
                                steps.append({'pixel':[capture,x,y,color]})
                            normal.run({'steps':steps},[])
                            measurements.append({'heap_setup_model_ms':value(16),
                                'app_heap_capacity_bytes':value(17),'kernel_heap_reserved_bytes':value(18),
                                'preemptions':value(12),'yields':value(13)})
                finally: normal.close()
            with opened(project,'memory') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=controls)
            assert result['result']==expected and result['os_responsive'],result
            cases.append({'case':variant or 'allocation-pixels-save-relaunch','build':build,'runtime':result,'measurements':measurements})
            print('PASS:',variant or '6 MiB allocation, copied pixels, saved heap transfer and same-OS zeroed relaunch',flush=True)
    sources=['ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
             'ports/lefony-prime-g2/ion/src/prime_g2/system.cpp','vm/test-sdk-memory-pixels.py',
             'vm/sdk_newlib_probe.py']
    write_json(output/'report.json',{'schema':1,'status':'passed','validation':'developer-local',
        'profile':'R0 VM-only protected 8 MiB reservation and copied pixels','physical':'not_tested',
        'cases':cases,'sources':{p:digest(ROOT/p) for p in sources}})


if __name__=='__main__': main()

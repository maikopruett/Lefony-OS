#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""R0 installed ARM proof of preemption, resumption, yield and OS-owned close."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import write_json
from lfapp import pack
from replay import Controls
from runner import exercise
from workspace import opened


def compile_probe(project, spin):
    flags=['-mcpu=cortex-a7','-marm','-mfpu=neon-vfpv4','-mfloat-abi=hard',
           '-std=c11','-Os','-g','-ffreestanding','-ffunction-sections','-fdata-sections',
           '-I',str(ROOT/'sdk/include')]
    if spin: flags+=['-DEXECUTION_SPIN=1']
    objects=[]
    for source in ['sdk/lib/start.s','sdk/experiments/execution_probe.c',
                   'sdk/experiments/execution_registers.s']:
        obj=project/(Path(source).stem+'.o')
        subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(ROOT/source),'-o',str(obj)],
                       check=True,timeout=60)
        objects.append(str(obj))
    image=project/'app.elf'
    subprocess.run(['arm-none-eabi-gcc',*flags,'-nostdlib','-nostartfiles','-static',
                    '-Wl,--build-id=none','-Wl,--gc-sections','-Wl,-z,noexecstack',
                    '-Wl,-z,max-page-size=4096','-Wl,-T,'+str(ROOT/'sdk/cmake/app.ld'),
                    *objects,'-o',str(image)],check=True,timeout=60)
    subprocess.run(['arm-none-eabi-objcopy','--strip-all',str(image)],check=True,timeout=30)
    app=project/'app.lfapp'
    manifest={'abi':1,'id':'execution-proof','name':'Execution proof','version':'0.1.0',
              'license':'CC-BY-NC-SA-4.0'}
    write_json(project/'app.json',manifest)
    app.write_bytes(pack(manifest,image.read_bytes()))
    return app


def main():
    compiler=subprocess.check_output(['arm-none-eabi-gcc','-dumpfullversion'],text=True).strip()
    assert compiler==json.loads((ROOT/'sdk/contract.json').read_text())['compiler']
    output=ROOT/'build/sdk-execution-qualification'
    output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for spin in (False,True):
        with tempfile.TemporaryDirectory(prefix='lefony-execution-') as directory:
            project=Path(directory)
            app=compile_probe(project,spin)
            measurements={}
            def controls(channel):
                normal=Controls(channel,output)
                def diagnostic(index):
                    reply=channel.command(f'APP DIAG {index}')
                    assert reply.startswith('VALUE '),reply
                    return int(reply.split()[1])
                try:
                    end=time.monotonic()+60
                    while time.monotonic()<end:
                        assert diagnostic(9)==0,'app fault during context preservation'
                        if (spin and diagnostic(12)>=3) or (not spin and diagnostic(15)==1):
                            break
                        time.sleep(.05)
                    else: raise AssertionError('resumable execution did not progress')
                    measurements.update(preemptions=diagnostic(12),yields=diagnostic(13),
                                        resumes=diagnostic(14),exited=diagnostic(15))
                    assert measurements['preemptions']>0,measurements
                    assert measurements['resumes']>0,measurements
                    if spin:
                        before=channel.command('STATE').split(' home_row=')[0]
                        started=time.monotonic()
                        normal.key('home')
                        measurements['home_wall_ms']=int((time.monotonic()-started)*1000)
                        assert channel.command('STATE').split(' home_row=')[0]!=before
                        assert channel.command('PING')=='PONG'
                        # Relaunch in the same OS instance: old user context
                        # and stack must not survive the package reload.
                        assert channel.command(f'APP OPEN {channel.installed_slot}')=='OK'
                        end=time.monotonic()+10
                        while diagnostic(12)<2 and time.monotonic()<end:
                            time.sleep(.05)
                        assert diagnostic(9)==0 and diagnostic(12)>=2
                        measurements['relaunch_preemptions']=diagnostic(12)
                        normal.key('home')
                    else:
                        assert measurements['yields']==1,measurements
                        normal.run({'steps':[{'capture':'registers'},
                            {'pixel':['registers',20,20,[33,166,66]]}]},[])
                        # Later timer/key events must not invoke main a second time.
                        try:
                            normal.key('ok')
                        except Exception:
                            print('Post-exit input diagnostics:',channel.command('STATE'),
                                  [diagnostic(i) for i in range(16)],flush=True)
                            raise
                        time.sleep(.7)
                        assert diagnostic(9)==0 and diagnostic(15)==1
                finally: normal.close()
            with opened(project,'execution') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                                ROOT/'dist/lefony-os-prime-g2-vm-native.elf',
                                workspace=workspace,controls=controls)
            assert result['result']==1 and result['os_responsive'],result
            cases.append({'case':'cpu-spin-home' if spin else 'registers-stack-yield-exit',
                          'measurements':measurements,'runtime':result})
    sources=['ports/lefony-prime-g2/ion/src/prime_g2/native_app_context.s',
             'ports/lefony-prime-g2/ion/src/prime_g2/boot/start.s',
             'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
             'ports/lefony-prime-g2/ion/src/prime_g2/key_edge_tracker.h',
             'ports/lefony-prime-g2/patches/prime-g2-key-edge-timeouts.patch',
             'sdk/experiments/execution_probe.c','sdk/experiments/execution_registers.s',
             'vm/test-sdk-execution.py']
    write_json(output/'report.json',{'schema':1,'status':'passed',
               'profile':'R0 VM-only opt-in; not a supported public ABI extension',
               'physical':'not_tested','compiler':compiler,'cases':cases,
               'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}})
    print('PASS: installed ARM preemption, integer/VFP/flags/stack preservation, yield, one main, exit and normal Home interruption')


if __name__=='__main__': main()

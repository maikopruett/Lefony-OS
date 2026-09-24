#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""ARM stdio cleanup on normal/nonzero exit, Home and fault; same-OS relaunch."""
import tempfile
import time
from pathlib import Path
from PIL import Image
from sdk_newlib_probe import ROOT,compile_probe
from build import write_json,digest
from runner import exercise
from replay import Controls
from workspace import opened


def main():
    output=ROOT/'build/sdk-file-sessions/lifecycle';output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for variant in ('FILES_HOME','FILES_FAULT','FILES_FAIL_EXIT','FILES_CLEAN_EXIT'):
        with tempfile.TemporaryDirectory(prefix='lefony-file-exit-') as temporary:
            project=Path(temporary)
            app,build=compile_probe(project,'sdk/experiments/files_lifecycle_probe.c',
                defines=['NEWLIB_KERNEL_HEAP',variant],app_id='file-lifecycle',file_api=True)
            evidence={}
            def controls(channel):
                normal=Controls(channel,output)
                def value(index):
                    result=int(channel.command(f'APP DIAG {index}').split()[1])
                    return result-2**32 if result>=2**31 else result
                def pixel():
                    frame=output/(variant+'.ppm');normal.execute('screendump',{'filename':str(frame)})
                    with Image.open(frame) as image:return image.convert('RGB').getpixel((40,40))
                try:
                    end=time.monotonic()+120
                    while True:
                        crash=value(9)
                        if variant=='FILES_FAULT' and crash:
                            assert crash==-11,f'expected undefined instruction, got {crash}';evidence['fault']= -11;break
                        assert crash==0,f'{variant}: unexpected fault {crash}'
                        if variant=='FILES_HOME' and pixel()==(0,0,255):break
                        if variant in ('FILES_CLEAN_EXIT','FILES_FAIL_EXIT') and value(15):
                            # The guest's reopen assertions distinguish private
                            # data saved by exit(0) from discarded exit(7) data.
                            evidence['program_exit_argument']=7 if variant=='FILES_FAIL_EXIT' else 0
                            break
                        assert time.monotonic()<end,f'{variant}: file stage did not complete'
                        time.sleep(.05)
                    normal.key('home')
                    end=time.monotonic()+20
                    while channel.command(f'APP OPEN {channel.installed_slot}')!='OK':
                        assert time.monotonic()<end,'cleanup prevented relaunch';time.sleep(.05)
                    end=time.monotonic()+30
                    while pixel()!=(33,166,66):
                        assert value(9)==0,f'{variant}: relaunch assertions failed'
                        assert time.monotonic()<end,'relaunch did not finish';time.sleep(.05)
                    evidence['same_os_relaunch']='passed';normal.key('home')
                finally:normal.close()
            with opened(project,'lifecycle') as (workspace,_):
                result=exercise(app,ROOT/'build/qemu-prime-g2/qemu-system-arm',
                    ROOT/'dist/lefony-os-prime-g2-vm-native.elf',workspace=workspace,controls=controls)
            assert result['result']==1 and result['os_responsive'],result
            cases.append({'case':variant,'build':build,'runtime':result,**evidence});print('PASS:',variant,flush=True)
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested','cases':cases,
      'sources':{p:digest(ROOT/p) for p in ('vm/test-sdk-file-lifecycle.py','sdk/experiments/files_lifecycle_probe.c',
      'ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp','ports/lefony-prime-g2/ion/src/prime_g2/app_management.cpp')}})


if __name__=='__main__':main()

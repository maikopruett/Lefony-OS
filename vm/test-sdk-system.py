#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed ARM system requests, normal clipboard gestures and brightness cleanup."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import time
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
    parser.add_argument('--modes',nargs='+',default=['basic','denied','unsupported','exit','restore','fault','home','clipboard','maximum','expired','telemetry'])
    args=parser.parse_args();output=ROOT/'build/sdk-system/arm';output.mkdir(parents=True,exist_ok=True)
    report={'schema':1,'status':'running','cases':[],'firmware_sha256':digest(args.firmware),'physical':'not_tested'}
    sources=('tests/native/sdk_system.cpp','vm/test-sdk-system.py','sdk/include/lefony/system.h',
         'sdk/include/lefony/system_wire.h','ports/lefony-prime-g2/ion/src/prime_g2/app_system.h',
         'ports/lefony-prime-g2/ion/src/prime_g2/app_system.cpp','ports/lefony-prime-g2/ion/src/prime_g2/native_app.cpp',
         'ports/lefony-prime-g2/ion/src/prime_g2/services.cpp','ports/lefony-prime-g2/apps/native_apps/app.cpp',
         'scripts/prepare_prime_native_system.py')
    report['sources']={p:digest(ROOT/p) for p in sources}
    with tempfile.TemporaryDirectory(prefix='sdk-system-') as temp:
        for mode in args.modes:
            project=Path(temp)/mode;(project/'src').mkdir(parents=True)
            shutil.copyfile(ROOT/'tests/native/sdk_system.cpp',project/'src/main.cpp')
            enabled=mode not in ('denied','unsupported')
            write_json(project/'app.json',{'abi':1,'id':'system-lab','name':'System Lab','version':'1.0.0',
                'license':'GPL-3.0-or-later','schema':1,'minimum_api':10 if enabled else 3,
                'required_capabilities':2066 if enabled else 18,'optional_capabilities':0,'data_schema':0})
            write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp'],'arguments':[mode]})
            artifact=package(project);folder=output/mode;folder.mkdir(exist_ok=True)
            for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,folder/name)
            records=[]
            def controls(channel):
                normal=Controls(channel,folder)
                def run(steps):normal.run({'steps':steps},records)
                def command(text):
                    reply=channel.command(text);assert reply=='OK',(text,reply)
                def brightness(value,ready=False):
                    deadline=time.monotonic()+20
                    while True:
                        actual=channel.command('BRIGHTNESS GET')
                        if actual==f'VALUE {value}':return
                        exited=channel.command('APP DIAG 15')
                        if not ready or exited!='VALUE 0' or time.monotonic()>=deadline:
                            raise AssertionError((mode,'brightness',value,actual,'exited',exited,channel.command('APP DIAG 21')))
                        time.sleep(.025)
                def ready():
                    # The first program yield follows validation and the ready
                    # frame. APP OPEN itself returns before heap/main startup.
                    deadline=time.monotonic()+20
                    while channel.command('APP DIAG 13')=='VALUE 0':
                        if channel.command('APP DIAG 15')!='VALUE 0' or time.monotonic()>=deadline:
                            raise AssertionError((mode,'not ready',channel.command('APP DIAG 21')))
                        time.sleep(.025)
                try:
                    if mode not in ('basic','denied','unsupported'):ready()
                    if mode in ('exit','restore','fault','home'):
                        brightness(112,ready=True);run([{'key':'one'}]);brightness(112)
                        if mode=='fault':
                            normal.key('ok');brightness(240)
                            code=int(channel.command('APP DIAG 9').split()[1])
                            if code>=2**31:code-=2**32
                            assert code==-11,code
                            records.append({'action':'expected-fault','status':'passed','fault':-11,'restored_brightness':240})
                        else:
                            run([{'key':'home' if mode=='home' else 'ok'}]);brightness(240)
                            if mode!='home':run([{'program_exit':0}])
                    elif mode=='clipboard':
                        run([{'key':'shift'},{'key':'view'},{'key':'shift'},{'key':'menu'},
                             {'key':'shift'},{'key':'ok'},{'capture':'gestures'},{'key':'ok'},{'program_exit':0}])
                        # New execution has no inherited grant. A fresh normal Paste
                        # still reaches the shared OS clipboard from the prior visit.
                        run([{'relaunch':True}]);ready()
                        run([{'key':'shift'},{'key':'menu'},{'key':'ok'},{'program_exit':0}])
                    elif mode=='expired':
                        run([{'key':'shift'},{'key':'view'},{'program_exit':0}])
                    elif mode=='maximum':
                        run([{'key':'shift'},{'key':'view'},{'key':'shift'},{'key':'menu'},
                             {'key':'shift'},{'key':'ok'},{'key':'shift'},{'key':'menu'},
                             {'key':'ok'},{'program_exit':0}])
                    elif mode=='telemetry':
                        command('RTC SET 2030 2 3 4 5 6 6');command('BATTERY SET 3 4000 0')
                        run([{'key':'one'}])
                        command('RTC SET 2020 2 3 4 5 6 0');command('BATTERY PF1550 SET 1 8 6')
                        run([{'key':'two'},{'capture':'telemetry'},{'key':'ok'},{'program_exit':0}])
                    else:run([{'program_exit':0}])
                finally:normal.close()
            result=exercise(artifact,ROOT/'build/qemu-prime-g2/qemu-system-arm',args.old_firmware if mode=='unsupported' else args.firmware,controls=controls)
            assert result['os_responsive'],result
            assert result['result']==(-11 if mode=='fault' else 1),result
            report['cases'].append({'mode':mode,'runtime':result,'records':records})
            write_json(output/'report.json',report);print('PASS:',mode,flush=True)
    assert report['sources']=={p:digest(ROOT/p) for p in sources},'Source changed during qualification'
    report['status']='passed';write_json(output/'report.json',report)


if __name__=='__main__':main()

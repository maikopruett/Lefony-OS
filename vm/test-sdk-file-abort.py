#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Signed ARM writer cancellation, stdio cleanup, cold data and capability fallback."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from files_device import FileClient
from replay import Controls
from runner import exercise
from workspace import opened


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('firmware','old-firmware','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    report={'schema':1,'status':'running','physical':'not_tested','sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'old_firmware_sha256':digest(args.old_firmware),'qemu_sha256':digest(qemu),'cases':[]}
    write_json(out/'report.json',report)
    try:
        with tempfile.TemporaryDirectory(prefix='file-abort-') as temp:
            for mode in ('normal','denied','unsupported'):
                project=Path(temp)/mode;(project/'src').mkdir(parents=True)
                shutil.copyfile(ROOT/'tests/native/sdk_file_abort.cpp',project/'src/main.cpp')
                write_json(project/'app.json',{'abi':1,'id':'file-abort','name':'File Abort','version':'1.0.0',
                    'license':'GPL-3.0-or-later','schema':1,'minimum_api':12 if mode=='normal' else 3,
                    'required_capabilities':8280 if mode=='normal' else 24,'optional_capabilities':0,'data_schema':0})
                write_json(project/'project.json',{'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.cpp'],'arguments':[mode]})
                artifact=package(project,'debug');folder=out/mode;folder.mkdir()
                for name in ('app-debug.elf','build.json',artifact.name):shutil.copyfile(project/'build'/name,folder/name)
                for phase in ('initial','cold') if mode=='normal' else ('initial',):
                    target=folder/phase;target.mkdir();observed={}
                    def controls(channel):
                        normal=Controls(channel,target)
                        try:
                            deadline=time.monotonic()+90
                            while channel.command('APP DIAG 15')=='VALUE 0':
                                fault=channel.command('APP DIAG 9')
                                if fault!='VALUE 0':
                                    pc=int(channel.command('APP DIAG 10').split()[1])
                                    location=subprocess.check_output(['arm-none-eabi-addr2line','-if','-e',str(folder/'app-debug.elf'),hex(pc)],text=True)
                                    raise AssertionError((mode,phase,fault,location))
                                assert time.monotonic()<deadline,'App exceeded bounded completion wait'
                                time.sleep(.025)
                            assert channel.command('APP DIAG 9')=='VALUE 0' and channel.command('APP DIAG 21')=='VALUE 0'
                            normal.key('home');channel.wait_for_storage();files=FileClient(channel.app_client)
                            observed['entries']=files.list('file-abort')['entries']
                            if mode=='normal':
                                for name,expected in (('value',b'final'),('large',bytes((i*17)&255 for i in range(8193)))):
                                    files.export_file('file-abort',name,target/name);assert (target/name).read_bytes()==expected
                                assert {e['path'] for e in observed['entries']}=={'value','large','complete'}
                            else:assert observed['entries']==[]
                        finally:normal.close()
                    with opened(project,'abort') as (workspace,_):
                        result=exercise(artifact,qemu,args.old_firmware if mode=='unsupported' else args.firmware,workspace=workspace,controls=controls)
                    assert result['result']==1 and result['os_responsive'],result
                    report['cases'].append({'mode':mode,'phase':phase,'runtime':result,**observed})
                    write_json(out/'report.json',report);print('PASS:',mode,phase,flush=True)
        assert report['sdk_sha256']==identity(ROOT/'sdk'),'SDK changed during qualification'
        report.update(status='passed',sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),
            ROOT/'tests/native/sdk_file_abort.cpp',ROOT/'sdk/include/lefony/file_writer.h',ROOT/'sdk/lib/newlib/files.c')})
        write_json(out/'report.json',report)
    except Exception as exc:
        report.update(status='failed',error=str(exc));write_json(out/'report.json',report);raise


if __name__=='__main__':main()

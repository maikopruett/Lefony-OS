#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stack diagnostics from real ARM execution, including lifecycle and identity."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json,identity
from cli import package
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--old-firmware',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm';cases=[]
    def project(name,mode=0,foreground=False):
        p=output/name;(p/'src').mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'sdk/experiments/resource_profile_probe.c',p/'src/main.c')
        defines={'PROFILE_MODE':mode}
        metadata={'abi':1,'id':name,'name':name,'version':'1.0.0','license':'CC-BY-NC-SA-4.0'}
        config={'schema':1,'sources':['src/main.c'],'defines':defines}
        if foreground:
            defines['PROFILE_MAIN']=1;config.update(schema=2,runtime='foreground-newlib-1')
            metadata.update(schema=1,minimum_api=3,required_capabilities=16,optional_capabilities=0,data_schema=0)
        write_json(p/'app.json',metadata);write_json(p/'project.json',config)
        return p,package(p)
    def record(name,result):
        cases.append({'name':name,'runtime':result})
        write_json(output/'report.json',{'schema':1,'status':'running','cases':cases})
        print('PASS:',name,flush=True)
    for name,mode in [('written',0),('reserved',1),('guard',2),('default-zero',3),('irq-timeout',4)]:
        p,app=project(name,mode)
        result=exercise(app,qemu,args.firmware,measure_resources=mode!=3)
        assert result['result']==(-14 if mode==2 else -2 if mode==4 else 1),result
        resources=result['resources']
        if mode==0:assert 8192<=resources['stack_written_bytes']<16384,resources
        if mode==1:
            assert 32768<=resources['stack_pointer_bytes']<40000,resources
            assert resources['stack_written_bytes']<1024,resources
        if mode==2:
            assert resources['faults']==1 and resources['stack_pointer_out_of_bounds'],resources
            assert resources['finished_loads']==1 and not resources['currently_loaded'],resources
        if mode==3:assert resources is None
        if mode==4:
            assert resources['stack_pointer_bytes']>=49152 and resources['faults']==1,resources
            assert resources['finished_loads']==1 and not resources['currently_loaded'],resources
        record(name,result)
    p,app=project('main-profile',foreground=True)
    def normal_exit(channel):
        normal=Controls(channel,p)
        try:normal.run({'steps':[{'program_exit':0},{'relaunch':True},{'program_exit':0}]},[])
        finally:normal.close()
    result=exercise(app,qemu,args.firmware,controls=normal_exit,measure_resources=True)
    r=result['resources'];assert result['result']==1 and r['loads']==r['finished_loads']==2,result
    assert r['stack_pointer_bytes']>=32768 and r['heap_reserved_peak_bytes']==8380416,r
    record('main-exit-relaunch',result)
    p,app=project('identity-target');_,other=project('identity-other',1)
    key=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
    public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    def switch(channel):
        normal=Controls(channel,p)
        try:
            normal.key('home');channel.app_client.wait()
            entry=channel.app_client.install(sign(other.read_bytes(),key),[public])
            normal.key('back')
            assert channel.command('APP OPEN '+str(entry['slot']))=='OK'
        finally:normal.close()
    with opened(p,'identity') as (media,_):
        result=exercise(app,qemu,args.firmware,workspace=media,controls=switch,measure_resources=True)
    r=result['resources'];assert r['loads']==r['finished_loads']==1 and not r['currently_loaded'],r
    assert 8192<=r['stack_observed_bytes']<16384,r
    record('other-package-excluded',result)
    p,app=project('fault-then-other',2)
    with opened(p,'fault-identity') as (media,_):
        result=exercise(app,qemu,args.firmware,workspace=media,controls=switch,measure_resources=True)
    r=result['resources'];assert result['result']==-14 and r['faults']==1,result
    assert r['loads']==r['finished_loads']==1 and not r['currently_loaded'],r
    assert 0x10000000<=result['fault']['pc']<0x10100000 and result['fault']['event']==0,result
    assert result['diagnostics'][9]=='VALUE 0','Other app must clear legacy fault counters for this proof'
    record('fault-survives-other-package',result)
    p,app=project('invalid-load')
    def invalid_load(channel):
        # Failed replacement finishes the old mapping, but cannot erase its
        # measurements or count as a matching successful load.
        assert channel.command('APP PROFILE ARM '+digest(app))=='ERR app loaded'
        assert channel.command('APP PROFILE ARM '+'g'*64)=='ERR profile hash'
        assert channel.command('APP LOAD 0')=='ERR app package'
        assert channel.command('APP LOAD '+str(app.stat().st_size))=='OK'
        assert channel.command('APP EVENT 0 0 0')=='RESULT 1'
    result=exercise(app,qemu,args.firmware,controls=invalid_load,measure_resources=True)
    r=result['resources'];assert r['loads']==2 and r['finished_loads']==1,r
    assert r['stack_written_bytes']>=8192 and r['currently_loaded'],r
    record('invalid-load-and-rearm-boundaries',result)
    if args.old_firmware:
        try:exercise(app,qemu,args.old_firmware,measure_resources=True)
        except RuntimeError as exc:assert 'matching VM firmware' in str(exc),exc
        else:raise AssertionError('Old firmware accepted resource profiling')
        cases.append({'name':'older-firmware-refused','status':'passed'})
    write_json(output/'report.json',{'schema':1,'status':'passed','physical':'not_tested',
        'firmware_sha256':digest(args.firmware),'sdk_sha256':identity(ROOT/'sdk'),
        'qemu_sha256':digest(qemu),'cases':cases})

if __name__=='__main__':main()

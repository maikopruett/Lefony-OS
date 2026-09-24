#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real allocator peaks, lifecycle attribution and invalid diagnostic records."""
import argparse,json
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,identity,write_json
from cli import package
from replay import Controls
from runner import exercise
from signing import sign
from workspace import opened

COMMON='''#include <lefony/foreground.h>
#include <stdlib.h>
extern volatile LefonyHeapProfile lefony_heap_profile;
volatile unsigned char *allocation;
'''
SHORT=COMMON+'''int main(void) {
 allocation=malloc(1024*1024);if(!allocation)return 1;
 allocation[0]=1;allocation[1024*1024-1]=2;
 free((void *)allocation);lefony_program_sleep(20);return 0;
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware',type=Path,required=True)
    parser.add_argument('--old-firmware',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True)
    qemu=ROOT/'build/qemu-prime-g2/qemu-system-arm'
    report={'status':'running','cases':[],'sdk_sha256':identity(ROOT/'sdk'),
        'firmware_sha256':digest(args.firmware),'qemu_sha256':digest(qemu),'physical':'not_tested'}
    def project(name,source,enabled=True):
        p=out/name;(p/'src').mkdir(parents=True)
        (p/'src/main.c').write_text(source)
        write_json(p/'app.json',{'abi':1,'id':name,'name':name,'version':'1.0.0','license':'CC-BY-NC-SA-4.0',
            'schema':1,'minimum_api':3,'required_capabilities':16,'optional_capabilities':0,'data_schema':0})
        config={'schema':2,'runtime':'foreground-newlib-1','sources':['src/main.c']}
        if enabled:config['defines']={'LEFONY_PROFILE_HEAP':1}
        write_json(p/'project.json',config)
        return p,package(p)
    def record(name,result):
        report['cases'].append({'name':name,**result});write_json(out/'report.json',report)
        print('PASS:',name,flush=True)
    cases=[('allocator-transitions',(ROOT/'sdk/experiments/heap_profile_probe.c').read_text()),
           ('short-peak',SHORT),('no-allocations','int main(void){return 0;}'),
           ('plain-build',SHORT),('relaunch',SHORT),
           ('fault-after-allocation',COMMON+'''int main(void) {
 allocation=malloc(262144);if(!allocation)return 1;allocation[0]=1;
 __asm__ volatile("udf #0");return 2;}
'''),
           ('incomplete-record',COMMON+'''int main(void) {
 allocation=malloc(65536);if(!allocation)return 1;allocation[0]=1;
 lefony_heap_profile.sequence++;lefony_program_exit(0);return 2;}
'''),
           ('corrupt-record',COMMON+'''int main(void) {
 allocation=malloc(65536);if(!allocation)return 1;allocation[0]=1;
 lefony_heap_profile.magic=0;lefony_program_exit(0);return 2;}
''')]
    for name,source in cases:
        p,app=project(name,source,name!='plain-build')
        def controls(channel):
            normal=Controls(channel,p)
            try:
                if name=='fault-after-allocation':
                    end=time.monotonic()+60
                    while int(channel.command('APP DIAG 9').split()[1])==0:
                        assert time.monotonic()<end,'expected ordinary undefined-instruction fault'
                        time.sleep(.05)
                else:
                    steps=[{'program_exit':0}]
                    if name=='relaunch':steps += [{'relaunch':True},{'program_exit':0}]
                    normal.run({'steps':steps},[])
                assert channel.command('APP PROFILE HEAP 0')=='ERR heap profile'
            finally:normal.close()
        try:
            result=exercise(app,qemu,args.firmware,controls=controls,measure_resources=True)
        except RuntimeError as exc:
            if name!='corrupt-record' or 'heap snapshot' not in str(exc):raise
            record(name,{'status':'invalid-measurement-rejected','reason':str(exc),'package_sha256':digest(app)})
            continue
        assert name!='corrupt-record','corrupt allocator metadata was accepted'
        assert result['os_responsive'],result
        resources=result['resources'];heap=resources.get('heap')
        if name=='plain-build':
            assert heap is None and resources['heap_peak_bytes'] is None,result
        elif name=='no-allocations':
            assert heap['status']=='not_observed' and resources['heap_peak_bytes'] is None,result
        elif name=='incomplete-record':
            assert heap['status']=='partial' and resources['heap_peak_bytes'] is None,result
        else:
            assert heap['status']=='observed',result
            minimum=512*1024 if name=='allocator-transitions' else 262144 if name=='fault-after-allocation' else 1024*1024
            assert minimum<=heap['allocated_peak_bytes']<2*1024*1024,result
            assert heap['arena_peak_bytes']>=heap['allocated_peak_bytes'],result
            if name=='fault-after-allocation':
                assert result['result']<0 and resources['faults']==1,result
                assert heap['allocated_bytes']>=262144,result
            else:
                assert result['result']==1 and result['program']['exit_status']==0,result
                assert heap['allocated_bytes']==0,result
            if name=='relaunch':assert heap['loads']==resources['loads']==2,result
        record(name,{'runtime':result})
    p,app=project('heap-identity',SHORT);other,other_app=project('unrelated-heap',SHORT)
    def switch(channel):
        normal=Controls(channel,p)
        try:
            normal.run({'steps':[{'program_exit':0}]},[])
            normal.key('home');channel.app_client.wait()
            assert channel.command('APP PROFILE HEAP 270536704')=='ERR heap profile'
            signed=sign(other_app.read_bytes(),ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem')
            entry=channel.app_client.install(signed,[ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'])
            normal.key('back');assert channel.command('APP OPEN '+str(entry['slot']))=='OK'
            normal.run({'steps':[{'program_exit':0}]},[])
        finally:normal.close()
    with opened(p,'identity') as (media,_):
        result=exercise(app,qemu,args.firmware,workspace=media,controls=switch,measure_resources=True)
    assert result['resources']['heap']['loads']==1 and result['resources']['loads']==1,result
    assert result['resources']['heap']['allocated_peak_bytes']>=1024*1024,result
    record('other-package-excluded',{'runtime':result})
    if args.old_firmware:
        try:exercise(app,qemu,args.old_firmware,measure_resources=True)
        except RuntimeError as exc:
            assert 'Heap profiling requires matching VM' in str(exc),exc
            record('old-heap-firmware-refused',{'status':'passed','reason':str(exc)})
        else:raise AssertionError('Older VM silently skipped allocator measurement')
    report['status']='passed';write_json(out/'report.json',report)

if __name__=='__main__':main()

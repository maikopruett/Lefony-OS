#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private exact-image instruction tests; device backends explicitly intercepted."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import Machine, PROFILES, BASE, private_output, literal, audit_format
from prime_hp_confinement import patch_image, patches, DETAILS, FIRST_BLOCK, LAST_BLOCK


def metadata_guards(name, patched):
    detail=DETAILS[name]; cases=[]
    for label,address,_,_,page in detail['guards']:
        for block in range(3,9):
            for offset in ((0,1,4,63) if page else (0,)):
                value=block*64+offset if page else block
                for caller in (*detail['bbt_callers'],0x83fe0001):
                    vm=Machine(patched);vm.set('R0',value);vm.set('LR',caller)
                    allowed=4<=block<=7 and (
                        label=='erase' and caller==detail['bbt_callers'][2] or
                        label=='ecc-program' and offset in (0,4) and caller==detail['bbt_callers'][offset//4])
                    sp=vm.get('SP')
                    vm.run(address,address+4 if allowed else caller&~1)
                    assert (vm.get('R0')==value and vm.get('SP')<sp) if allowed else (vm.get('R0')==0xfffffffe and vm.get('SP')==sp)
                    cases.append({'operation':label,'argument':value,'caller':hex(caller),'allowed':allowed})
    address,_,_,state=detail['bbt']
    for block in (391,392,2047,2048):
        for header_page in (0,256,257,1024,131072):
            vm=Machine(patched);vm.put(state,0x82020000);vm.put(0x82020078,header_page)
            vm.set('R1',block);sp=vm.get('SP');allowed=392<=block<=2047 and header_page==256
            vm.run(address,address+4 if allowed else 0x83fe0000)
            assert vm.get('SP')<sp if allowed else (vm.get('R0')==0 and vm.get('SP')==sp)
    return cases


def metadata_callback(name, patched):
    p=PROFILES[name];vm=Machine(patched);header,table=0x82020000,0x82030000
    state,geo=literal(patched,p['state_literal']),literal(patched,p['geometry_literal'])
    vm.put(state,header);vm.put(header+0x78,256)
    vm.put(state+4 if name=='HPPrime.img' else literal(patched,0x80007A58),table)
    vm.put(geo+0x14,64);vm.put(geo+0x2c,2048);vm.set('R1',500)
    events=[]
    for label,address,_,_,_ in DETAILS[name]['guards']:
        saved={'ecc-program':list(range(1,12))+[14], 'raw-program':list(range(4,9))+[14], 'erase':list(range(2,7))+[14]}[label]
        def backend(m,label=label,saved=saved):
            events.append((label,m.get('R0')))
            sp=m.get('SP')
            for index,reg in enumerate(saved):m.set('LR' if reg==14 else 'R'+str(reg),m.read(sp+index*4))
            m.set('SP',sp+len(saved)*4);m.set('R0',0)
        # Only the native hardware backend is intercepted, AFTER the real guard
        # and its displaced prologue. Denied entries cannot reach this hook.
        vm.hooks[address+4]=backend
    vm.run(p['mark_callback'])
    assert vm.get('R0')==1
    assert [x[1] for x in events if x[0]=='erase']==[4,5,6,7]
    assert [x[1] for x in events if x[0]=='ecc-program']==[b*64+i for b in range(4,8) for i in (0,4)]
    assert [x[1] for x in events if x[0]=='raw-program']==[500*64,500*64+1]
    return events


def check(name,data):
    patched,report=patch_image(name,data)
    p=PROFILES[name]
    m=Machine(patched);dev,geo=0x82000000,0x82010000
    if name=='HPPrime.img':m.set('R4',dev);m.set('R5',geo)
    else:geo,dev=literal(data,0x80007CCC),literal(data,0x80007CEC)
    m.put(geo+8,131072,8);m.put(geo+0x18,4096);m.set('R1',0)
    m.run(*p['bounds']);assert (m.read(dev+0x14),m.read(dev+0x18))==(392,2047)
    m.set('R4',dev);m.run(*p['copy']);assert (m.read(dev+0xf4),m.read(dev+0xf8))==(392,2047)
    cases=[]
    for label,address,_,_,page in DETAILS[name]['guards']:
        lo,hi=(392*64,2048*64) if page else (392,2048)
        for value in [0,lo-1,lo,lo+1,hi-1,hi,hi+1,0xfffffffe,0xffffffff]:
            vm=Machine(patched);vm.set('R0',value)
            for i in range(1,12):vm.set('R'+str(i),0x12340000+i)
            sp=vm.get('SP');allowed=lo<=value<hi
            vm.run(address, address+4 if allowed else 0x83fe0000)
            if not allowed:
                assert vm.get('R0')==0xfffffffe and vm.get('SP')==sp
                assert all(vm.get('R'+str(i))==0x12340000+i for i in range(1,12))
            else:
                assert vm.get('R0')==value
                # Original displaced prologue executed and saved caller LR.
                assert vm.get('SP')<sp
            cases.append({'function':label,'argument':value,'allowed':allowed})
    disabled=[]
    for label,address,_, in DETAILS[name]['disabled']:
        vm=Machine(patched);sp=vm.get('SP')
        for i in range(1,12):vm.set('R'+str(i),0x12340000+i)
        vm.run(address)
        assert vm.get('R0')==0 and vm.get('SP')==sp
        assert all(vm.get('R'+str(i))==0x12340000+i for i in range(1,12))
        disabled.append(label)
    # Diagnostic OS erase must reach the real guards and never reach a backend.
    vm=Machine(patched);vm.run(p['diagnostic'])
    report['disabled_entries']=disabled
    report['metadata_guard_cases']=metadata_guards(name,patched)
    report['metadata_callback']=metadata_callback(name,patched)
    if name=='HPPrime.img':
        reset=[]
        for mode in (0,1,2,3,4,0xffffffff):
            vm=Machine(patched);calls=[]
            def restart(m):calls.append('ordinary-restart');m.set('R0',0)
            vm.hooks[0x802B076C]=restart;vm.set('R0',mode);vm.run(0x80415AE0)
            assert calls==(['ordinary-restart'] if mode==0 else [])
            assert vm.get('R0')==int(mode==0)
            reset.append({'mode':mode,'result':vm.get('R0'),'calls':calls})
        report['reset_policy']=reset
    report['diagnostic_erase']='actual diagnostic routine returns without reaching NAND MMIO'
    report['instruction_cases']=cases
    report['format']=audit_format(patched,p,2047,(400,2047))
    report['limits']=['Synthetic geometry, function-level execution',
                      'Allowed writer backends not executed by this test',
                      'Full boot, GC, reset, update/reload and failure cases need separate qualification']
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--fixture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=private_output(a.output);out.mkdir(parents=True,exist_ok=False)
    reports=[check(name,(a.fixture/name).read_bytes()) for name in DETAILS]
    (out/'qualification.json').write_text(json.dumps(reports,indent=2)+'\n')
    print('PASS exact-image bounds, 54 filesystem boundaries, metadata ownership/callbacks, reset/update rejection and format loops')
if __name__=='__main__':main()

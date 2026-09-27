#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify the fixed HP RAM confinement profile against disposable NAND copies.

Private V15751 inputs and a prepared physical-codeword fixture are required.
No USB device access, physical flashing, release signing or layout migration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_hp_prime_compatibility import private_output,require
from analyze_prime_hp_write_trace import analyze
from prime_hp_confinement import PROFILE
import importlib


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def events(path):
    return [json.loads(line.split(': ',1)[1]) for line in path.read_text().splitlines()
            if line.startswith('phase4-storage: ')]


def between(log,start,end):
    result=[];offset=0
    for line in log.read_bytes().splitlines(keepends=True):
        if start<=offset<end and line.startswith(b'prime-nand-write: '):
            result.append(json.loads(line.split(b': ',1)[1]))
        offset+=len(line)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True,help='directory made by prepare-prime-hp-confined-fixture.py')
    p.add_argument('--uboot',type=Path,required=True)
    p.add_argument('--ddr-image',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--resume',action='store_true',help='recheck completed private runs with identical inputs, then run missing stages')
    a=p.parse_args();out=private_output(a.output);out.mkdir(parents=True,exist_ok=a.resume)
    for name in ('images','fixture','uboot','ddr_image'):setattr(a,name,getattr(a,name).resolve())
    backing=a.fixture/'confined-physical.raw'
    metadata=json.loads((a.fixture/'fixture.json').read_text())
    backing_hash=digest(backing)
    require(backing_hash==metadata['fixture_sha256'] and metadata['device_flash_input'] is False,'invalid disposable fixture')
    helper=out/'storage-gdb.py'
    if helper.exists():require(digest(helper)==digest(ROOT/'vm/prime_hp_storage_gdb.py'),'changed experiment helper; use new output directory')
    else:shutil.copyfile(ROOT/'vm/prime_hp_storage_gdb.py',helper)
    if not (out/'instructions/qualification.json').exists():
        subprocess.run([sys.executable,str(ROOT/'vm/test-prime-hp-confinement-instructions.py'),
                        '--fixture',str(a.images),'--output',str(out/'instructions')],check=True,timeout=120)
    for component in json.loads((out/'instructions/qualification.json').read_text()):
        require(component['profile']==PROFILE,'stale instruction qualification')
    common=[sys.executable,str(ROOT/'vm/probe-prime-hp-handoff.py'),
            '--uboot',str(a.uboot),'--ddr-image',str(a.ddr_image),'--ram-loader',
            '--stock-nand',str(backing),'--physical-pages','--confinement','--trace-writes']
    reports={}
    def validate_observation(target, image):
        observation=json.loads((target/'observation.json').read_text())
        require(observation['confinement_profile']['profile']==PROFILE,'stale RAM profile')
        for field,path in [('image',image),('uboot',a.uboot),('ddr_image',a.ddr_image),
                           ('qemu',importlib.import_module('test-prime-g2-rom-recovery').QEMU),
                           ('probe',ROOT/'vm/probe-prime-hp-handoff.py')]:
            require(observation[field+'_sha256']==digest(path),'changed '+field+'; use new output directory')
        require(observation['trace_writes'] and observation['nand_representation']=='physical codewords',
                'physical NAND write observation required')
        require(not observation['model_rejected_bch_layout'],'unsupported BCH layout')
        return observation

    def run(name,mode,mib,fault=-1,seed=None):
        target=out/name;script=out/(name+'.gdb')
        script.write_text(f'set $p4_mode={mode}\nset $p4_mib={mib}\nset $p4_fault={fault}\n'+
                          'python P4_LOG = '+repr(str(target/'qemu.log'))+'\n'+
                          'source '+str(helper.relative_to(ROOT))+'\n')
        command=common+['--image',str(a.images/'HPPrime.img'),'--menu','--seconds','2',
                        '--output',str(target),'--gdb-script',str(script),'--gdb-timeout','600']
        if seed:command+=['--overlay-from',str(out/seed/'nand.overlay')]
        if not (a.resume and (target/'observation.json').exists()):
            require(not target.exists(),'incomplete stage; preserve it and use a new output directory')
            print('Running '+name,flush=True)
            with (out/(name+'-host.log')).open('w') as log:
                subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=720)
        observed=events(target/'gdb.log')
        require(observed and observed[-1]['event']=='complete','incomplete filesystem experiment')
        trace=analyze(target/'qemu.log',target/'nand.overlay')
        require(not trace['escaped_attempts'] and not trace['escaped_commits'],'write escaped declared regions')
        observation=validate_observation(target,a.images/'HPPrime.img')
        require(observation['gdb_experiment_sha256']==digest(script),'changed GDB experiment')
        require(observation['selected_through_menu'],'storage test bypassed the menu')
        report={'events':observed,'writes':trace,'loader':observation}
        (target/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
        reports[name]=report
        print('PASS '+name+': '+str(trace['attempt_count'])+' observed write attempts',flush=True)
    run('save-scan-checkpoint',0,4)
    run('cold-read-delete-format',1,4,seed='save-scan-checkpoint')
    run('program-failure-retirement',0,4,fault=400)
    run('cold-bad-block-retention',1,4,fault=400,seed='program-failure-retirement')
    run('capacity-reclaim-format',2,220)
    stress=reports['capacity-reclaim-format']['events']
    by_name={e['event']:e for e in stress}
    require(by_name['full']['bytes']>200*1024*1024,'capacity test did not exceed 200 MiB')
    reclaim=between(out/'capacity-reclaim-format/qemu.log',by_name['deleted']['nand_log_bytes'],by_name['reclaimed']['nand_log_bytes'])
    erased={e['block'] for e in reclaim if e['operation']=='erase'}
    require(len(erased)>=100,'reclaimed writes did not exercise NAND block reclamation')
    # This captured stock table already retires metadata blocks 6 and 7.
    # Derive available copies from the fault-free baseline rather than assume
    # all four physical copies are usable. Both components' instruction tests
    # separately exercise the all-four-good case.
    baseline=(out/'save-scan-checkpoint/runtime.bin').read_bytes()
    def runtime_word(address):
        offset=address-0x80000000
        require(0<=offset<=len(baseline)-4,'metadata pointer outside captured RAM')
        return int.from_bytes(baseline[offset:offset+4],'little')
    table=runtime_word(0x807bdee8);count=runtime_word(table+0x804)
    require(count<=4096,'invalid bad-block count')
    initial_bad={runtime_word(table+0x808+4*i) for i in range(count)}
    copies=set(range(4,8))-initial_bad
    require(copies,'no usable metadata copies')
    require(reports['save-scan-checkpoint']['writes']['attempt_regions'].get('hp-bad-block-metadata',0)==0,'baseline changed metadata')
    require(reports['program-failure-retirement']['writes']['attempt_regions'].get('hp-bad-block-metadata')==3*len(copies),
            'metadata copies did not match the stock bad-block policy')
    updater=out/'updater'
    print('Running separately verified updater transfer',flush=True)
    if not (a.resume and (updater/'observation.json').exists()):
        require(not updater.exists(),'incomplete updater stage; use a new output directory')
        subprocess.run(common+['--image',str(a.images/'bootloader.img'),'--seconds','4',
                        '--output',str(updater)],check=True,timeout=120)
    updater_observation=validate_observation(updater,a.images/'bootloader.img')
    if any(line.startswith('prime-nand-write: ') for line in (updater/'qemu.log').read_text().splitlines()):
        updater_writes=analyze(updater/'qemu.log',updater/'nand.overlay')
        require(not updater_writes['escaped_attempts'] and not updater_writes['escaped_commits'],
                'updater write escaped declared regions')
    else:
        require((updater/'nand.overlay').read_bytes()==b'PG2RAW1\n',
                'updater overlay changed without write observations')
        updater_writes={'attempt_count':0,'commit_count':0,
                        'result':'No writes observed; instruction and transfer coverage only'}
    (updater/'qualification.json').write_text(json.dumps(
        {'loader':updater_observation,'writes':updater_writes},indent=2)+'\n')
    require(digest(backing)==backing_hash,'read-only backing changed')
    summary={'result':'PASS tested RAM-profile confinement matrix','profile':PROFILE,
             'fixture':metadata,'storage_harness_sha256':digest(helper),
             'uboot_sha256':digest(a.uboot),'ddr_image_sha256':digest(a.ddr_image),
             'qemu_sha256':reports['capacity-reclaim-format']['loader']['qemu_sha256'],
             'capacity_file_bytes':by_name['full']['bytes'],'reclamation_erased_blocks':len(erased),
             'metadata_copies_used':sorted(copies),
             'updater_writes':updater_writes,
             'runs':{name:report['writes'] for name,report in reports.items()},
             'limits':['Emulator only; no physical installation or final shared layout',
                       'GDB calls actual HP filesystem APIs in an application context; not a UI test',
                       'Failed empty block explicitly reclaimed through HP YAFFS; physical failure timing not modeled',
                       'Factory resets, official updates and maintenance reload intentionally rejected by research policy',
                       'Updater instruction/transfer coverage only; its UI is not qualified',
                       'Fresh welcome-screen touch remains unqualified; this matrix does not bypass that screen for user acceptance']}
    (out/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS complete confinement matrix; physical migration remains disabled',flush=True)


if __name__=='__main__':main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile pinned Doom portable code for ARM; report actual platform dependencies.

This does not claim a working/distributable port and supplies no successful
dummy platform hooks. Linkable engine objects and symbol evidence remain in build/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from source import collect, decode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'build/sdk-1.0-upstream/doomgeneric')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sdk-doom-architecture')
    args=parser.parse_args()
    pin=json.loads((ROOT/'sdk/ports/doom/source.json').read_text())
    source=args.source.resolve()/pin['directory']
    for name,expected in pin['source_files'].items():
        if digest(source/name)!=expected: raise ValueError('Doom source differs from the pinned tree: '+name)
    license_path=source.parent/pin['license']['path']
    if digest(license_path)!=pin['license']['sha256']: raise ValueError('Doom license differs from the pinned tree')
    libc=ROOT/'build/sdk-newlib'
    candidate=json.loads((libc/'candidate.json').read_text())
    compiler=shutil.which('arm-none-eabi-gcc')
    if not compiler or digest(compiler)!=candidate['compiler_sha256']:
        raise ValueError('Use the same pinned compiler as the newlib architecture candidate')
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    (output/'report.json').unlink(missing_ok=True)
    # Exercise the same inert project/source format used by ordinary SDK apps.
    # This source snapshot is an architecture input, not a runnable .lfapp.
    with tempfile.TemporaryDirectory(prefix='lefony-doom-source-') as temp:
        project=Path(temp)
        tree=project/'src/doomgeneric'
        tree.mkdir(parents=True)
        for name in pin['source_files']:
            shutil.copyfile(source/name,tree/name)
        write_json(project/'app.json',{'abi':1,'id':'doom-architecture','name':'Doom architecture',
                   'version':'0.1.0','license':'GPL-2.0-or-later'})
        write_json(project/'project.json',{'schema':1,'sources':['src/doomgeneric/'+p for p in pin['portable_sources']],
                   'include_dirs':['src/doomgeneric'],'defines':pin['defines'],
                   'c_flags':['-fwrapv','-fno-strict-aliasing','-Wno-error']})
        (project/'notices').mkdir()
        shutil.copyfile(license_path,project/'notices/doomgeneric-license.txt')
        snapshot=collect(project,2)
        (output/'doom-source.lfsrc').write_bytes(snapshot)
        source_report={'format':'lefony-source-2','bytes':len(snapshot),
                       'files':len(decode(snapshot)['files']),
                       'sha256':hashlib.sha256(snapshot).hexdigest()}
    flags=['-std=c11','-mcpu=cortex-a7','-marm','-mfpu=neon-vfpv4','-mfloat-abi=hard',
           '-Os','-g','-ffreestanding','-ffunction-sections','-fdata-sections',
           '-fno-strict-aliasing','-fwrapv','-I',str(source),'-isystem',str(libc/'install/arm-none-eabi/include'),
           f'-ffile-prefix-map={source}=/doomgeneric',
           *[f'-D{name}={value}' for name,value in pin['defines'].items()]]
    objects=[]
    for name in pin['portable_sources']:
        obj=output/(Path(name).stem+'.o')
        subprocess.run([compiler,*flags,'-c',str(source/name),'-o',str(obj)],check=True,timeout=60)
        objects.append(str(obj))
    engine=output/'engine.o'
    subprocess.run(['arm-none-eabi-ld','-r',*objects,'-o',str(engine)],check=True,timeout=60)
    sizes=subprocess.check_output(['arm-none-eabi-size',str(engine)],text=True,timeout=10)
    values=sizes.splitlines()[1].split()
    symbols=subprocess.check_output(['arm-none-eabi-nm','--undefined-only','--format=posix',str(engine)],text=True,timeout=10)
    unresolved=sorted(line.split()[0] for line in symbols.splitlines() if line.strip())
    write_json(output/'report.json',{'schema':1,'status':'portable-core-compiled-not-runnable',
        'pin':pin,'source_bundle':source_report,'compiler':candidate['compiler'],'compiler_sha256':digest(compiler),
        'newlib':candidate['version'],'translation_units':len(objects),'engine_sha256':digest(engine),
        'before_dead_code_elimination':{'code_constants_bytes':int(values[0]),'data_bytes':int(values[1]),'bss_bytes':int(values[2])},
        'unresolved_symbols':unresolved,'flags':flags,
        'remaining':'Platform adapters, real files/assets, conventional public runtime, gameplay/save/input/performance and distribution qualification'})
    print(sizes.strip())
    print('ARM portable core compiled:',len(objects),'units;',len(unresolved),'unresolved library/platform symbols')


if __name__=='__main__': main()

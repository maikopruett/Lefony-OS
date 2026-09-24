# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared pinned newlib compilation for the R0 ARM probes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from build import digest,write_json
from lfapp import pack,elf_segments


def compile_probe(directory,source,*,defines=(),app_id='libc-proof',file_api=False,foreground=False,extra_sources=()):
    libc=ROOT/'build/sdk-newlib'
    candidate=json.loads((libc/'candidate.json').read_text())
    libraries=libc/'install/arm-none-eabi/lib'
    for name,evidence in candidate['libraries'].items():
        assert digest(libraries/name)==evidence['sha256']
    compiler=shutil.which('arm-none-eabi-gcc')
    assert compiler and digest(compiler)==candidate['compiler_sha256']
    assert subprocess.check_output([compiler,'-dumpfullversion'],text=True).strip()==candidate['compiler']
    flags=['-mcpu=cortex-a7','-marm','-mfpu=neon-vfpv4','-mfloat-abi=hard',
           '-Os','-g','-ffreestanding','-ffunction-sections','-fdata-sections',
           '-I',str(ROOT/'sdk/include'),'-isystem',str(libc/'install/arm-none-eabi/include'),
           *['-D'+define for define in defines]]
    directory.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'sdk/lib/start.s',ROOT/'sdk/experiments/newlib_os.c',ROOT/source,*[ROOT/p for p in extra_sources]]
    foreground=foreground or file_api
    if foreground:
        flags.append('-DLEFONY_PUBLIC_FOREGROUND')
    if file_api:
        flags.append('-DNEWLIB_FILES')
        sources.append(ROOT/'sdk/experiments/newlib_files.c')
    objects=[]
    for item in sources:
        obj=directory/(item.stem+'.o')
        language=['-std=c11','-Wall','-Wextra','-Werror'] if item.suffix=='.c' else []
        subprocess.run([compiler,*flags,*language,'-c',str(item),'-o',str(obj)],check=True,timeout=60)
        objects.append(str(obj))
    debug=directory/'app-debug.elf'
    subprocess.run([compiler,*flags,'-nostdlib','-nostartfiles','-static',
                    '-Wl,--build-id=none','-Wl,--gc-sections','-Wl,-z,noexecstack',
                    '-Wl,-z,max-page-size=4096','-Wl,-T,'+str(ROOT/'sdk/cmake/app.ld'),
                    '-Wl,-Map,'+str(directory/'app.map'),*objects,
                    '-L',str(libraries),'-Wl,--start-group','-lc','-lm','-lgcc','-Wl,--end-group',
                    '-o',str(debug)],check=True,timeout=60)
    image=directory/'app.elf'
    subprocess.run(['arm-none-eabi-objcopy','--strip-all',str(debug),str(image)],check=True,timeout=30)
    metadata={'abi':1,'id':app_id,'name':'ARM runtime proof','version':'0.1.0','license':'CC-BY-NC-SA-4.0'}
    if file_api:
        metadata.update(schema=1,minimum_api=2,required_capabilities=8,optional_capabilities=0,data_schema=0)
    if foreground:
        metadata.update(schema=1,minimum_api=3,required_capabilities=16|(8 if file_api else 0),optional_capabilities=0,data_schema=0)
    write_json(directory/'app.json',metadata)
    app=directory/'app.lfapp'
    app.write_bytes(pack(metadata,image.read_bytes()))
    _,segments=elf_segments(image.read_bytes())
    return app,{'libc':candidate,'code_bytes':sum(m for _,_,m,p in segments if p==5),
                'data_bytes':sum(m for _,_,m,p in segments if p==6),
                'sources':{s.relative_to(ROOT).as_posix():digest(s) for s in sources},
                'defines':[f[2:] for f in flags if f.startswith('-D')]}

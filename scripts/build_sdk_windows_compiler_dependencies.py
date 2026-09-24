#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Windows MPC/ISL/zlib/zstd atop a verified Windows GMP/MPFR candidate.

Uses the pinned, retained Ubuntu source packages, with their downstream patches.
No downloads or system installation. This is a cross build, not Windows testing.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_toolchain import run_step

LOCK = Path(__file__).with_name('sdk-windows')/'compiler-dependencies.json'


def relocate_base_metadata(install):
    """Relocate text metadata while preserving the verified static libraries."""
    archive=install/'lib/libgmp.la'
    match=re.search(r"^libdir='(/[^\n']+)/lib'$",archive.read_text(),re.M)
    if not match:
        raise ValueError('Base GMP libtool metadata has an unexpected installation prefix')
    original=match.group(1)
    changed={}
    for path in sorted(install.rglob('*')):
        if path.is_file() and path.suffix in ('.la','.pc'):
            before=digest(path);text=path.read_text()
            if original in text:
                path.write_text(text.replace(original,str(install)))
                changed[path.relative_to(install).as_posix()]={'before':before,'after':digest(path)}
    return {'original_prefix':original,'prefix':str(install),'files':changed}


def verify_base(base, expected):
    if not re.fullmatch('[0-9a-f]{64}', expected) or digest(base/'candidate.json') != expected:
        raise ValueError('Base dependency candidate does not match the selected hash')
    candidate = json.loads((base/'candidate.json').read_text())
    if (candidate.get('status') != 'passed' or candidate.get('platform') != 'Windows'
            or candidate.get('architecture') != 'AMD64'):
        raise ValueError('Base dependencies must be a completed Windows x86-64 candidate')
    for name, checksum in candidate['files'].items():
        path = base/'install'/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or digest(path) != checksum:
            raise ValueError('Base dependency file changed: ' + name)
    for name in ('include/gmp.h', 'include/mpfr.h', 'lib/libgmp.a', 'lib/libmpfr.a'):
        if name not in candidate['files']:
            raise ValueError('Base dependencies are incomplete: ' + name)
    return candidate


def copy_sources(materials, output):
    pins = json.loads(LOCK.read_text())
    for component in pins.values():
        for name, checksum in component['archives'].items():
            path = materials/component['directory']/'archives'/name
            if (not path.is_file() or path.is_symlink() or path.stat().st_size > 64*1024**2
                    or digest(path) != checksum):
                raise ValueError('Compiler dependency source differs from its pin: ' + name)
    for name, component in pins.items():
        folder = output/name; folder.mkdir()
        for filename, checksum in component['archives'].items():
            shutil.copyfile(materials/component['directory']/'archives'/filename, folder/filename)
            if digest(folder/filename) != checksum:
                raise ValueError('Compiler dependency source changed during copy: ' + filename)
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-sha256', required=True)
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work-parent', type=Path, required=True)
    parser.add_argument('--cross-prefix', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    parent, output, base = args.work_parent.resolve(), args.output.resolve(), args.base.resolve()
    if os.name == 'nt' or not 1 <= args.jobs <= 32:
        parser.error('Use a Unix build host and 1–32 jobs')
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):
        parser.error('--work-parent must be an existing directory without whitespace')
    if output.exists():
        parser.error('Use a new output directory')
    base_candidate = verify_base(base, args.base_sha256)
    _, tools, _, _, _ = host_configuration(True, args.cross_prefix)
    output.mkdir(parents=True)
    recipes = {Path(__file__).name: Path(__file__), 'build_sdk_gdb.py': Path(__file__).with_name('build_sdk_gdb.py'),
               'build_sdk_linux_toolchain.py': Path(__file__).with_name('build_sdk_linux_toolchain.py'),
               'sdk-windows/compiler-dependencies.json': LOCK}
    for name, path in recipes.items():
        target=output/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path,target)
    report = {'schema': 1, 'status': 'running', 'platform': 'Windows', 'architecture': 'AMD64',
              'execution_checked': False, 'base_candidate_sha256': args.base_sha256,
              'build_host': {'platform': platform.system(), 'architecture': platform.machine()},
              'recipes': {name:digest(path) for name,path in recipes.items()},
              'cross_tools': {name:{'path':path,'sha256':digest(Path(path))} for name,path in tools.items()}}
    def save():
        (output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    save(); commands=[]
    try:
        sources=output/'sources'; sources.mkdir()
        report['sources']=copy_sources(args.materials.resolve(),sources)
        (output/'base-candidate.json').write_text(json.dumps(base_candidate,indent=2)+'\n')
        install=output/'install'; install.mkdir()
        for name in base_candidate['files']:
            target=install/name; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(base/'install'/name,target)
            if digest(target)!=base_candidate['files'][name]:raise ValueError('Base changed during copy: '+name)
        report['base_metadata_relocation']=relocate_base_metadata(install)
        with build_directory(output,parent) as scratch:
            flags='-O2 -g0 -ffile-prefix-map='+str(scratch)+'=/lefony-windows-compiler-deps'
            env={**os.environ,**tools,'CFLAGS':flags,'CXXFLAGS':flags,'LC_ALL':'C'}
            for key in ('CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','LIBRARY_PATH','PKG_CONFIG_PATH'):
                env.pop(key,None)
            for name,component in report['sources'].items():
                source=scratch/name; work=scratch/(name+'-build'); work.mkdir()
                def run(label,command,cwd=work):
                    run_step(name+'-'+label,command,cwd,env,output,commands,timeout=1800)
                run('extract',['dpkg-source','-x',next((sources/name).glob('*.dsc')),source],scratch)
                if name in ('mpc','isl'):
                    run('autoreconf',['autoreconf','-fiv'],source)
                    build=subprocess.check_output(['sh',next(source.rglob('config.guess'))],text=True,timeout=10).strip()
                    options=['--build='+build,'--host=x86_64-w64-mingw32','--prefix='+str(install),
                             '--disable-shared','--enable-static']
                    if name=='mpc':options+=['--with-gmp='+str(install),'--with-mpfr='+str(install)]
                    else:options+=['--with-gmp=system','--with-gmp-prefix='+str(install)]
                    run('configure',[source/'configure',*options])
                    run('build',['make','-j'+str(args.jobs)])
                    run('install',['make','install'])
                elif name=='zlib':
                    env['CHOST']='x86_64-w64-mingw32'
                    run('configure',[source/'configure','--static','--prefix='+str(install)])
                    run('build',['make','-j'+str(args.jobs)])
                    run('install',['make','install'])
                    env.pop('CHOST')
                else:
                    make=['make','-C',str(source/'lib'),'-j'+str(args.jobs),'CC='+tools['CC'],
                          'AR='+tools['AR'],'CFLAGS='+flags,'PREFIX='+str(install),'LIBDIR='+str(install/'lib')]
                    run('build',[*make,'libzstd.a-mt'])
                    run('install',[*make,'install-static','install-includes'])
                notices=sources/name/'notices'; notices.mkdir()
                for path in sorted(source.rglob('*')):
                    if path.is_file() and (path.name.startswith(('COPYING','LICENSE')) or path.relative_to(source).as_posix()=='debian/copyright'):
                        target=notices/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
            for name in ('gmp','mpfr','mpc','isl','z','zstd'):
                if not (install/'lib'/('lib'+name+'.a')).is_file():raise ValueError('Missing compiler library: '+name)
        report.update(status='passed',files={p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()});save()
    except BaseException as error:
        report.update(status='failed',error=str(error) or type(error).__name__);save();raise
    print(json.dumps({'status':report['status'],'files':len(report['files'])}))


if __name__=='__main__':
    main()

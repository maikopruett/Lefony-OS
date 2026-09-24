#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-build the pinned Prime QEMU as a Windows x86-64 component on Linux ARM64.

Consumes a verified prepared QEMU source archive and a verified Windows library
candidate. This build never executes Windows programs or accesses USB devices.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_qemu import extract_source, VERSION, PATCHSET
from build_sdk_linux_toolchain import run_step
from native_desktop_windows import imports


def dependency_prefix(folder, expected):
    manifest=folder/'candidate.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or not manifest.is_file() or manifest.is_symlink() or digest(manifest)!=expected:
        raise ValueError('Windows QEMU dependency candidate hash mismatch')
    c=json.loads(manifest.read_text());prefix=folder/'install'
    if c.get('status')!='passed' or c.get('platform')!='Windows' or c.get('architecture')!='AMD64':
        raise ValueError('Use a completed Windows x86-64 dependency candidate')
    if set(c['files'])!={p.relative_to(prefix).as_posix() for p in prefix.rglob('*') if p.is_file()}:
        raise ValueError('Windows QEMU dependency file set differs from its candidate')
    for n,h in c['files'].items():
        p=prefix/n
        if Path(n).is_absolute() or '..' in Path(n).parts or not p.resolve().is_relative_to(prefix.resolve()) or digest(p)!=h:
            raise ValueError('Windows QEMU dependency file differs: '+n)
    for name in ('glib-2.0','gmodule-2.0','gthread-2.0','sdl2','pixman-1','libusb-1.0','zlib'):
        if 'lib/pkgconfig/'+name+'.pc' not in c['files']:raise ValueError('Missing Windows QEMU library metadata: '+name)
    return prefix,c


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--archive-sha256',required=True)
    parser.add_argument('--dependencies',type=Path,required=True)
    parser.add_argument('--dependencies-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--work-parent',type=Path,required=True)
    parser.add_argument('--cross-prefix',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args();output=args.output.resolve();parent=args.work_parent.resolve();archive=args.archive.resolve()
    if platform.system()!='Linux' or platform.machine()!='aarch64':parser.error('Use the Linux ARM64 cross-build host')
    if not 1<=args.jobs<=32:parser.error('Use 1–32 jobs')
    if output.exists() or any(c.isspace() for c in str(output)):parser.error('Use a fresh output directory without whitespace')
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):parser.error('Use an existing scratch directory without whitespace')
    if not re.fullmatch('[0-9a-f]{64}',args.archive_sha256) or not archive.is_file() or archive.stat().st_size>200*1024**2 or digest(archive)!=args.archive_sha256:
        parser.error('Prepared QEMU source archive differs from the selected input')
    prefix,dependencies=dependency_prefix(args.dependencies.resolve(),args.dependencies_sha256)
    _,tools,_,_,_=host_configuration(True,args.cross_prefix)
    build_tools={n:shutil.which(n) for n in ('cc','ninja','pkg-config')}
    if not all(build_tools.values()):parser.error('Native cc, ninja and pkg-config are required')
    build_tools={n:str(Path(p).resolve()) for n,p in build_tools.items()}
    output.mkdir(parents=True)
    names=('build_sdk_windows_qemu.py','build_sdk_gdb.py','build_sdk_linux_qemu.py',
           'build_sdk_linux_cross.py','build_sdk_linux_toolchain.py','native_desktop_windows.py')
    for n in names:shutil.copyfile(Path(__file__).with_name(n),output/n)
    shutil.copyfile(archive,output/'source.tar.gz')
    if digest(output/'source.tar.gz')!=args.archive_sha256:raise ValueError('QEMU source changed during copy')
    report={'schema':1,'status':'running','platform':'Windows','architecture':'AMD64','build_architecture':'aarch64',
            'version':VERSION,'patchset':PATCHSET,'source_sha256':args.archive_sha256,
            'dependencies_sha256':args.dependencies_sha256,'native_execution_checked':False,
            'desktop_bundle_qualified':False,'clean_host_qualified':False,'usb_devices_accessed':False,
            'recipes':{n:digest(output/n) for n in names},
            'tools':{n:{'path':p,'sha256':digest(Path(p))} for n,p in tools.items()},
            'build_tools':{n:{'path':p,'sha256':digest(Path(p))} for n,p in build_tools.items()}}
    (output/'dependency-candidate.json').write_bytes((args.dependencies.resolve()/'candidate.json').read_bytes())
    def save():(output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    save();commands=[]
    try:
        env={**os.environ,**tools,'LC_ALL':'C','PKG_CONFIG':build_tools['pkg-config'],
             'PKG_CONFIG_LIBDIR':str(prefix/'lib/pkgconfig'),
             'LDFLAGS':'-L'+str(prefix/'lib')}
        for n in ('CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','LIBRARY_PATH','PKG_CONFIG_PATH','PKG_CONFIG_SYSROOT_DIR'):
            env.pop(n,None)
        with build_directory(output,parent) as scratch:
            source=extract_source(output/'source.tar.gz',scratch);work=scratch/'build';work.mkdir()
            def run(label,command):run_step(label,command,work,env,output,commands,timeout=3600)
            run('configure',[source/'configure','--target-list=arm-softmmu',
                '--cross-prefix='+str(args.cross_prefix.resolve()),'--host-cc='+build_tools['cc'],
                '--extra-cflags=-I'+str(prefix/'include'),'--extra-cxxflags=-I'+str(prefix/'include'),
                '--cpu=x86_64','--disable-download','--disable-docs','--disable-werror',
                '--enable-fdt=internal','--enable-sdl','--enable-pixman','--enable-libusb','--python='+sys.executable])
            run('compile',[build_tools['ninja'],'-j'+str(args.jobs),'qemu-system-arm.exe'])
            install=output/'install';install.mkdir();program=install/'qemu-system-arm.exe'
            shutil.copyfile(work/program.name,program)
            # Retain generated configuration as evidence of the selected build profile.
            config=output/'configuration';config.mkdir()
            for n in ('config-host.h','config-host.mak','arm-softmmu-config-target.h','meson-info/intro-buildoptions.json'):
                p=work/n
                if p.is_file():
                    target=config/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
            notices=output/'notices';notices.mkdir()
            for n in ('COPYING','COPYING.LIB','LICENSE'):
                if (source/n).is_file():shutil.copyfile(source/n,notices/n)
        report.update(status='passed',qemu_sha256=digest(program),pe_imports=imports(program),
                      build_steps_sha256=digest(output/'commands.json'),
                      files={'qemu-system-arm.exe':digest(program)})
        save()
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    print(json.dumps({'status':report['status'],'qemu_sha256':report['qemu_sha256'],'native_execution_checked':False}))


if __name__=='__main__':main()

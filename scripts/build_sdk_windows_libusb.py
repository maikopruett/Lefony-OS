#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-build Windows x86-64 libusb from the retained Linux source package.

All exact source files and downstream patches are retained. This build does not
execute the DLL, enumerate USB devices or qualify native Windows USB behavior.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_toolchain import run_step
from native_desktop_windows import imports, native_files

VERSION='1.0.27-1'
SOURCE_FILES={
    'libusb-1.0_1.0.27.orig.tar.bz2.asc':'1cd22bbfe4ce382ca9b091e2a6275c48f1c776253815cbb615da295ae0bfe687',
    'libusb-1.0_1.0.27-1.debian.tar.xz':'560bc02e704b8f28b04be3e6a551ccbf2b5c5cb0850864d6a5416ad05723f0b4',
    'libusb-1.0_1.0.27-1.dsc':'8bb3b5e8ad48159cc562cc98b1d86ab78c0c24076bfaa25175855e332392503b',
    'libusb-1.0_1.0.27.orig.tar.bz2':'ffaa41d741a8a3bee244ac8e54a72ea05bf2879663c098c82fc5757853441575',
}


def copy_sources(materials, output):
    for name, expected in SOURCE_FILES.items():
        path=materials/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size>16*1024**2 or digest(path)!=expected:
            raise ValueError('libusb source differs from the pinned input: '+name)
    output.mkdir()
    for name, expected in SOURCE_FILES.items():
        shutil.copyfile(materials/name,output/name)
        if digest(output/name)!=expected:
            raise ValueError('libusb source changed during copy: '+name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--work-parent',type=Path,required=True)
    parser.add_argument('--cross-prefix',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args()
    output,parent=args.output.resolve(),args.work_parent.resolve()
    if os.name=='nt' or not 1<=args.jobs<=32:parser.error('Use a Unix build host and 1–32 jobs')
    if output.exists():parser.error('Use a new output directory; previous candidates are retained')
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):
        parser.error('--work-parent must be an existing directory without whitespace')
    _,tools,_,_,_=host_configuration(True,args.cross_prefix)
    output.mkdir(parents=True)
    recipes={name:Path(__file__).with_name(name) for name in
             ('build_sdk_windows_libusb.py','build_sdk_gdb.py','build_sdk_linux_toolchain.py','native_desktop_windows.py')}
    for name,path in recipes.items():shutil.copyfile(path,output/name)
    report={'schema':1,'status':'running','platform':'Windows','architecture':'AMD64','version':VERSION,
            'native_execution_checked':False,'usb_devices_accessed':False,'source_files':SOURCE_FILES,
            'recipes':{name:digest(path) for name,path in recipes.items()},
            'build_host':{'platform':platform.system(),'architecture':platform.machine()},
            'cross_tools':{name:{'path':path,'sha256':digest(Path(path))} for name,path in tools.items()}}
    def save():(output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    save();commands=[]
    try:
        copy_sources(args.source_directory.resolve(),output/'sources')
        install=output/'install'
        with build_directory(output,parent) as scratch:
            source=scratch/'source';work=scratch/'work';work.mkdir()
            flags='-O2 -g0 -ffile-prefix-map='+str(scratch)+'=/lefony-windows-libusb'
            env={**os.environ,**tools,'CFLAGS':flags,'CXXFLAGS':flags,'LC_ALL':'C'}
            for key in ('CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','LIBRARY_PATH','PKG_CONFIG_PATH'):
                env.pop(key,None)
            def run(label,command,cwd=work):run_step(label,command,cwd,env,output,commands,timeout=1800)
            run('extract',['dpkg-source','-x',output/'sources/libusb-1.0_1.0.27-1.dsc',source],scratch)
            run('autoreconf',['autoreconf','-fiv'],source)
            build=subprocess.check_output(['sh',next(source.rglob('config.guess'))],text=True,timeout=10).strip()
            run('configure',[source/'configure','--build='+build,'--host=x86_64-w64-mingw32',
                             '--prefix='+str(install),'--enable-shared','--enable-static',
                             '--disable-examples-build','--disable-tests-build'])
            run('build',['make','-j'+str(args.jobs)])
            run('install',['make','install'])
            notices=output/'notices';notices.mkdir()
            for path in sorted(source.rglob('*')):
                if path.is_file() and (path.name.startswith(('COPYING','LICENSE')) or path.relative_to(source).as_posix()=='debian/copyright'):
                    target=notices/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        library=install/'bin/libusb-1.0.dll'
        if not library.is_file():raise ValueError('Windows libusb DLL is missing')
        report['pe_imports']={p.relative_to(install).as_posix():imports(p) for p in native_files(install)}
        import pefile
        with pefile.PE(str(library)) as pe:
            exports={s.name.decode('ascii') for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
        required={'libusb_init','libusb_exit','libusb_get_device_list','libusb_open_device_with_vid_pid',
                  'libusb_close','libusb_control_transfer','libusb_bulk_transfer','libusb_get_version'}
        if not required<=exports:raise ValueError('Windows libusb DLL lacks required public exports')
        report.update(status='passed',exports=sorted(exports),inspection_pefile_version=pefile.__version__,
                      files={p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()})
        save()
    except BaseException as error:
        report.update(status='failed',error=str(error) or type(error).__name__);save();raise
    print(json.dumps({'status':report['status'],'dll_sha256':digest(library),'exports':len(exports)}))


if __name__=='__main__':main()

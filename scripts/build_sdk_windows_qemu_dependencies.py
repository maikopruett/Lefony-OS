#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-build the Windows x86-64 QEMU libraries from explicit retained sources.

No downloads, Windows execution or USB access. Original source archives, patches,
notices, recipes and per-component build records accompany the installation.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_toolchain import run_step
from native_desktop_windows import imports, native_files

LOCK=Path(__file__).with_name('sdk-windows')/'qemu-dependencies.json'


def retain_recipes(output):
    names=('build_sdk_windows_qemu_dependencies.py','build_sdk_gdb.py',
           'build_sdk_linux_toolchain.py','native_desktop_windows.py',
           'sdk-windows/qemu-dependencies.json','sdk-windows/Dockerfile.qemu-cross')
    for name in names:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(__file__).parent/name,target)
    return {name:digest(output/name) for name in names}


def copy_sources(materials, gnu, output):
    pins=json.loads(LOCK.read_text())
    inputs={}
    for name,component in pins.items():
        folder=gnu if component['kind']=='gnu' else materials/component['directory']/'archives'
        for filename,expected in component['archives'].items():
            p=folder/filename
            if not p.is_file() or p.is_symlink() or p.stat().st_size>64*1024**2 or digest(p)!=expected:
                raise ValueError('Windows QEMU source differs from the pinned input: '+filename)
            inputs[name,filename]=p
    for name,component in pins.items():
        folder=output/name;folder.mkdir()
        for filename,expected in component['archives'].items():
            shutil.copyfile(inputs[name,filename],folder/filename)
            if digest(folder/filename)!=expected:raise ValueError('Windows QEMU source changed during copy: '+filename)
    return pins


def extract_gnu(archive, destination, root):
    with tarfile.open(archive) as stream:
        members=stream.getmembers();names=set()
        if len(members)>50000 or sum(m.size for m in members)>512*1024**2:
            raise ValueError('GNU source archive exceeds extraction limits')
        for m in members:
            p=Path(m.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=root or m.name in names:
                raise ValueError('GNU source archive has an unexpected path')
            names.add(m.name)
        stream.extractall(destination,filter='data')
    return destination/root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials',type=Path,required=True)
    parser.add_argument('--gnu-inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--work-parent',type=Path,required=True)
    parser.add_argument('--cross-prefix',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=2)
    args=parser.parse_args();output=args.output.resolve();parent=args.work_parent.resolve()
    if platform.system()!='Linux' or not 1<=args.jobs<=32:parser.error('Use Linux and 1–32 jobs')
    if output.exists() or any(c.isspace() for c in str(output)):parser.error('Use a fresh output directory without whitespace')
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):parser.error('Use an existing scratch directory without whitespace')
    _,tools,_,_,_=host_configuration(True,args.cross_prefix)
    for name in ('meson','ninja','pkg-config','msgfmt','make','dpkg-source','autoreconf'):
        if not shutil.which(name):parser.error('Missing build tool: '+name)
    output.mkdir(parents=True);recipes=retain_recipes(output);sources=output/'sources';sources.mkdir()
    report={'schema':1,'status':'running','platform':'Windows','architecture':'AMD64',
            'native_execution_checked':False,'usb_devices_accessed':False,'recipes':recipes,
            'build_host':{'platform':platform.system(),'architecture':platform.machine()},
            'tools':{name:{'path':path,'sha256':digest(Path(path))} for name,path in tools.items()},'components':{}}
    def save():(output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    commands=[];save()
    try:
        report['sources']=copy_sources(args.materials.resolve(),args.gnu_inputs.resolve(),sources);save()
        install=output/'install';install.mkdir()
        with build_directory(output,parent) as scratch:
            flags='-O2 -g0 -ffile-prefix-map='+str(scratch)+'=/lefony-windows-qemu-deps'
            env={**os.environ,**tools,'CFLAGS':flags,'CXXFLAGS':flags,'LC_ALL':'C',
                 'CPPFLAGS':'-I'+str(install/'include'),'LDFLAGS':'-L'+str(install/'lib'),
                 'PKG_CONFIG_LIBDIR':str(install/'lib/pkgconfig')}
            for name in ('CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','LIBRARY_PATH','PKG_CONFIG_PATH','PKG_CONFIG_SYSROOT_DIR'):
                env.pop(name,None)
            cross=output/'meson-cross.ini'
            cross.write_text('[binaries]\n'+''.join(name+' = '+repr(value)+'\n' for name,value in
                [('c',tools['CC']),('cpp',tools['CXX']),('ar',tools['AR']),('strip',tools['STRIP']),
                 ('windres',tools['WINDRES']),('pkg-config',shutil.which('pkg-config'))])+
                "[host_machine]\nsystem = 'windows'\ncpu_family = 'x86_64'\ncpu = 'x86_64'\nendian = 'little'\n"+
                "[properties]\nneeds_exe_wrapper = true\n")
            for name,component in report['sources'].items():
                def run(label,command,cwd=scratch):run_step(name+'-'+label,command,cwd,env,output,commands,timeout=1800)
                if component['kind']=='gnu':
                    archive=next(p for p in (sources/name).iterdir() if p.name.endswith(('.tar.gz','.tar.xz')))
                    source=extract_gnu(archive,scratch,component['source_root'])
                else:
                    source=scratch/name
                    run('extract',['dpkg-source','-x',next((sources/name).glob('*.dsc')),source])
                work=scratch/(name+'-build')
                if name=='glib':
                    run('configure',['meson','setup',work,source,'--cross-file',cross,'--prefix',install,
                                     '--libdir=lib','--buildtype=release','--wrap-mode=nodownload',
                                     '-Dtests=false','-Dinstalled_tests=false','-Ddocumentation=false',
                                     '-Dman-pages=disabled','-Dintrospection=disabled','-Dnls=enabled'])
                    run('build',['meson','compile','-C',work,'-j',str(args.jobs)])
                    run('install',['meson','install','-C',work,'--no-rebuild'])
                elif name=='zlib':
                    work.mkdir();env['CHOST']='x86_64-w64-mingw32'
                    run('configure',[source/'configure','--static','--prefix='+str(install)],work)
                    run('build',['make','-j'+str(args.jobs)],work)
                    run('install',['make','install'],work)
                    env.pop('CHOST')
                else:
                    configure_source=source/component.get('configure_directory','.')
                    if name=='sdl':
                        # SDL owns its configuration-header template; its
                        # bootstrap intentionally does not invoke autoheader.
                        run('autogen',['sh','./autogen.sh'],configure_source)
                    elif component['kind']=='debian':run('autoreconf',['autoreconf','-fiv'],configure_source)
                    work.mkdir()
                    guess=next(source.rglob('config.guess'))
                    build=subprocess.check_output(['sh',guess],text=True,timeout=10).strip()
                    configure=[configure_source/'configure','--build='+build,'--host=x86_64-w64-mingw32',
                               '--prefix='+str(install),'--enable-shared','--enable-static']
                    if name=='gettext':configure+=['--disable-java','--disable-csharp','--disable-d','--disable-c++',
                                                  '--disable-libasprintf','--with-libiconv-prefix='+str(install),
                                                  '--enable-threads=windows','--enable-relocatable']
                    if name=='libiconv':configure+=['--enable-relocatable']
                    if name=='pcre2':configure+=['--enable-jit','--enable-pcre2-16','--enable-pcre2-32']
                    if name=='libusb':configure+=['--disable-examples-build','--disable-tests-build']
                    run('configure',configure,work)
                    run('build',['make','-j'+str(args.jobs)],work)
                    run('install',['make','install'],work)
                notices=sources/name/'notices';notices.mkdir()
                for p in sorted(source.rglob('*')):
                    if p.is_file() and (p.name.startswith(('COPYING','LICENSE')) or p.relative_to(source).as_posix()=='debian/copyright'):
                        target=notices/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
                report['components'][name]={'status':'passed','files':{p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()}}
                save()
        report.update(status='passed',files={p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()},
                      pe_imports={p.relative_to(install).as_posix():imports(p) for p in native_files(install)})
        save()
    except BaseException as error:report.update(status='failed',error=str(error));save();raise
    print(json.dumps({'status':report['status'],'components':len(report['components']),'files':len(report['files'])}))


if __name__=='__main__':main()

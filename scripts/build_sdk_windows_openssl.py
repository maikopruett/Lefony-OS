#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-build Windows x86-64 OpenSSL with the retained Ubuntu security patches.

Produces the CLI, DLLs, modules, configuration and sources. No Windows program
is executed, no key is generated, and no system installation is performed.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil

from build_sdk_gdb import build_directory, digest, host_configuration
from build_sdk_linux_toolchain import run_step
from native_desktop_windows import imports, native_files

VERSION='3.0.13-0ubuntu3.15'
SOURCE_FILES={
    'openssl_3.0.13.orig.tar.gz':'88525753f79d3bec27d2fa7c66aa0b92b3aa9498dafd93d7cfa4b3780cdae313',
    'openssl_3.0.13-0ubuntu3.15.debian.tar.xz':'a48bc18f3afd7030cd73712f180af343c4642e2d0ac65ac06fe1ec0ca7506077',
    'openssl_3.0.13-0ubuntu3.15.dsc':'ae1c9a23219f0617b866d765f750ebd3bac74d93b7a235e6e53289781a056f0a',
}
PATCH_NAME='sdk-windows/openssl-mingw-avx512.patch'
PATCH_SHA256='b8a6f5d6e24d40b8d54db4587e93baaa62048fd73070beec98262df3cb725a2d'
PATCH_FILES={
    'crypto/modes/asm/aes-gcm-avx512.pl':(
        'f3b8ccb0d483289e6a17aa96ce985de14bde340723d8f784e01185983dcf7713',
        'c4bdf42c6d7de4ccf8ce63780c965527c3bf4fb354813b87133aaa35b333a0f6'),
    'crypto/perlasm/x86_64-xlate.pl':(
        '37e52c1012247e8c57ab691ce4b1173c85a89c8f27a65a6544531c9d265e298b',
        '95231ddf205710b1b9f0f2c1635c07daf23880b2f772e5f973a3a86e900dfc73'),
}
ENV_PATCH_NAME='sdk-windows/openssl-portable-getenv.patch'
ENV_PATCH_SHA256='88afffd23be21ee8f4711d37728c77a763b9dc59da245684415b3c8433b6a641'
ENV_PATCH_FILES={'crypto/fips_mode.c':(
    'e7242341a95e8d7c5b56083dafb7478b46cc5ea165970cd6709e1dab5c548f79',
    '0f99fbea85870359f8652a045ef09099f5441913539d58be3e6f79d77dd00a65')}


def prepare_source(source, patch, run, *, patch_sha256=None, files=None, label='patch-mingw-avx512'):
    """Apply a pinned Windows adaptation with exact pre/post context, idempotently."""
    patch_sha256=PATCH_SHA256 if patch_sha256 is None else patch_sha256
    files=PATCH_FILES if files is None else files
    if not patch.is_file() or patch.is_symlink() or digest(patch)!=patch_sha256:
        raise ValueError('OpenSSL MinGW patch differs from the pinned input')
    current={}
    for name in files:
        path=source/name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Unexpected OpenSSL assembly source: '+name)
        current[name]=digest(path)
    if all(current[n]==pair[1] for n,pair in files.items()):return
    if any(current[n]!=pair[0] for n,pair in files.items()):
        raise ValueError('Unexpected OpenSSL assembly source context')
    run(label,['patch','--batch','--fuzz=0','-p1','-i',patch],source)
    if any(digest(source/n)!=pair[1] for n,pair in files.items()):
        raise ValueError('OpenSSL MinGW patch output differs from the pinned result')


def copy_sources(materials, output):
    for name, expected in SOURCE_FILES.items():
        path=materials/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size>64*1024**2 or digest(path)!=expected:
            raise ValueError('OpenSSL source differs from the pinned input: '+name)
    output.mkdir()
    for name, expected in SOURCE_FILES.items():
        shutil.copyfile(materials/name,output/name)
        if digest(output/name)!=expected:raise ValueError('OpenSSL source changed during copy: '+name)


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
    if output.exists():parser.error('Use a new output directory')
    if not parent.is_dir() or any(c.isspace() for c in str(parent)):
        parser.error('--work-parent must be an existing directory without whitespace')
    _,tools,_,_,_=host_configuration(True,args.cross_prefix)
    output.mkdir(parents=True)
    recipes={name:Path(__file__).with_name(name) for name in
             ('build_sdk_windows_openssl.py','build_sdk_gdb.py','build_sdk_linux_toolchain.py','native_desktop_windows.py')}
    recipes[PATCH_NAME]=Path(__file__).parent/PATCH_NAME
    recipes[ENV_PATCH_NAME]=Path(__file__).parent/ENV_PATCH_NAME
    for name,path in recipes.items():
        (output/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,output/name)
    report={'schema':1,'status':'running','platform':'Windows','architecture':'AMD64','version':VERSION,
            'native_execution_checked':False,'keys_generated':False,'source_files':SOURCE_FILES,
            'recipes':{name:digest(path) for name,path in recipes.items()},
            'build_host':{'platform':platform.system(),'architecture':platform.machine()},
            'cross_tools':{name:{'path':path,'sha256':digest(Path(path))} for name,path in tools.items()}}
    def save():(output/'candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    save();commands=[]
    try:
        copy_sources(args.source_directory.resolve(),output/'sources')
        with build_directory(output,parent) as scratch:
            source=scratch/'source';work=scratch/'work';work.mkdir();stage=scratch/'stage'
            env={**os.environ,'LC_ALL':'C'}
            # Configure prepends CROSS_COMPILE itself; do not prepend it twice
            # through an inherited CC/AR setting or mix host include directories.
            for key in ('CC','CXX','AR','AS','LD','RANLIB','WINDRES','CROSS_COMPILE','CFLAGS','CXXFLAGS',
                        'CPPFLAGS','LDFLAGS','CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','LIBRARY_PATH','PKG_CONFIG_PATH'):
                env.pop(key,None)
            def run(label,command,cwd=work):run_step(label,command,cwd,env,output,commands,timeout=1800)
            run('extract',['dpkg-source','-x',output/'sources/openssl_3.0.13-0ubuntu3.15.dsc',source],scratch)
            prepare_source(source,output/PATCH_NAME,run)
            # Ubuntu's added FIPS switch reader uses glibc secure_getenv.
            # Use OpenSSL's existing portable, privilege-aware wrapper on Windows.
            prepare_source(source,output/ENV_PATCH_NAME,run,patch_sha256=ENV_PATCH_SHA256,
                           files=ENV_PATCH_FILES,label='patch-portable-getenv')
            report['source_preparation']={'upstream_commit':'224ea84b4054de105447cde407fa3d39004a563d',
                                          'patch_sha256':PATCH_SHA256,'files':PATCH_FILES,
                                          'portable_environment':{'patch_sha256':ENV_PATCH_SHA256,'files':ENV_PATCH_FILES}}
            prefix='/opt/lefony-sdk/openssl'
            run('configure',['perl',source/'Configure','mingw64','shared','no-tests',
                             '--cross-compile-prefix='+str(args.cross_prefix.resolve()),
                             '--prefix='+prefix,'--openssldir='+prefix+'/ssl','--libdir=lib',
                             '-O2','-g0','-ffile-prefix-map='+str(scratch)+'=/lefony-windows-openssl'])
            run('build',['make','-j'+str(args.jobs),'build_sw'])
            run('install',['make','install_sw','install_ssldirs','DESTDIR='+str(stage)])
            shutil.copytree(stage/prefix.lstrip('/'),output/'install')
            notices=output/'notices';notices.mkdir()
            for path in sorted(source.rglob('*')):
                if path.is_file() and (path.name.startswith(('COPYING','LICENSE')) or path.relative_to(source).as_posix()=='debian/copyright'):
                    target=notices/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        install=output/'install'
        required=('bin/openssl.exe','bin/libcrypto-3-x64.dll','bin/libssl-3-x64.dll',
                  'lib/ossl-modules/legacy.dll','ssl/openssl.cnf')
        for name in required:
            if not (install/name).is_file():raise ValueError('Missing Windows OpenSSL component: '+name)
        report['pe_imports']={p.relative_to(install).as_posix():imports(p) for p in native_files(install)}
        import pefile
        exports={}
        for name,required_names in (('libcrypto-3-x64.dll',{'EVP_DigestSignInit','EVP_PKEY_keygen','RAND_bytes','OSSL_PROVIDER_load'}),
                                    ('libssl-3-x64.dll',{'SSL_CTX_new','SSL_connect','OPENSSL_init_ssl'})):
            with pefile.PE(str(install/'bin'/name)) as pe:
                found={s.name.decode('ascii') for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
            if not required_names<=found:raise ValueError('Missing OpenSSL exports: '+name)
            exports[name]=sorted(found)
        report.update(status='passed',exports=exports,configured_prefix=prefix,
                      inspection_pefile_version=pefile.__version__,
                      files={p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()})
        save()
    except BaseException as error:
        report.update(status='failed',error=str(error) or type(error).__name__);save();raise
    print(json.dumps({'status':report['status'],'openssl_sha256':digest(install/'bin/openssl.exe'),'files':len(report['files'])}))


if __name__=='__main__':main()

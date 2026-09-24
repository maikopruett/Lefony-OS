#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the pinned Linux or Windows x86-64 ARM toolchain on Linux ARM64.

This Canadian cross-build requires an existing native ARM64-hosted compiler
with the same GCC/target pins. Build tools never use the new x86-64 executables.
The completed compiler is then exercised explicitly through Linux binfmt/QEMU.
That probe is emulated-host evidence, not native Linux SDK qualification.
--windows-host produces PE executables without attempting host execution;
it requires a separately built, checksum-selected Windows dependency prefix.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from build_sdk_linux_toolchain import SOURCES, digest, extract, run_step, source_archive

BUILD = 'aarch64-linux-gnu'
HOST = 'x86_64-linux-gnu'
TARGET = 'arm-none-eabi'


def require_elf(path, machine, bits):
    """Do not confuse build tools, deployed host tools and ARM app objects."""
    with Path(path).open('rb') as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:6] != b'\x7fELF' + bytes((2 if bits == 64 else 1, 1)) or int.from_bytes(header[18:20], 'little') != machine:
        raise ValueError(f'{path} is not the expected little-endian ELF{bits} machine {machine}')


def executable(name, env):
    path = shutil.which(str(name), path=env['PATH'])
    if path is None:
        raise ValueError('Required build tool is unavailable: ' + str(name))
    result = Path(path).resolve()
    require_elf(result, 183, 64)
    return result


def verify_windows_dependencies(folder, expected):
    if not expected or digest(folder/'candidate.json') != expected:
        raise ValueError('Windows dependency candidate differs from the selected hash')
    candidate=json.loads((folder/'candidate.json').read_text())
    if (candidate.get('status')!='passed' or candidate.get('platform')!='Windows'
            or candidate.get('architecture')!='AMD64'):
        raise ValueError('Use a completed Windows x86-64 dependency candidate')
    for name, checksum in candidate['files'].items():
        path=folder/'install'/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or digest(path)!=checksum:
            raise ValueError('Windows dependency input changed: '+name)
    for name in ('gmp','mpfr','mpc','isl','z','zstd'):
        if 'lib/lib'+name+'.a' not in candidate['files']:
            raise ValueError('Missing Windows compiler dependency: '+name)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-toolchain', type=Path, required=True)
    parser.add_argument('--binutils-archive', type=Path, required=True)
    parser.add_argument('--gcc-archive', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--windows-host', action='store_true')
    parser.add_argument('--host-dependencies', type=Path)
    parser.add_argument('--host-dependencies-sha256')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('Run the Canadian build on Linux ARM64')
    if not 1 <= args.jobs <= 32:
        parser.error('Use 1–32 build jobs')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; preserve it and choose a fresh candidate')
    host='x86_64-w64-mingw32' if args.windows_host else HOST
    dependency=None
    if args.windows_host:
        if not args.host_dependencies or not args.host_dependencies_sha256:
            parser.error('Windows builds require an explicit dependency candidate and SHA-256')
        args.host_dependencies=args.host_dependencies.resolve()
        dependency=verify_windows_dependencies(args.host_dependencies,args.host_dependencies_sha256)
    elif args.host_dependencies or args.host_dependencies_sha256:
        parser.error('Host dependency arguments require --windows-host')
    native = args.build_toolchain.resolve()
    env = {**os.environ, 'PATH': str(native / 'bin') + os.pathsep + os.environ.get('PATH', ''),
           'CFLAGS': '-O2', 'CXXFLAGS': '-O2'}
    for key in ('GCC_EXEC_PREFIX', 'COMPILER_PATH', 'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH'):
        env.pop(key, None)
    tools = {}
    for variable, name in (('CC_FOR_BUILD', 'gcc'), ('CXX_FOR_BUILD', 'g++'),
                           ('CC', host + '-gcc'), ('CXX', host + '-g++')):
        tools[variable] = executable(name, env)
    for variable, name in (('AR', 'ar'), ('AS', 'as'), ('LD', 'ld'), ('NM', 'nm'), ('RANLIB', 'ranlib'), ('STRIP', 'strip')):
        tools[variable] = executable(host + '-' + name, env)
        tools[variable + '_FOR_TARGET'] = executable(native / 'bin' / (TARGET + '-' + name), env)
    tools['CC_FOR_TARGET'] = executable(native / 'bin' / (TARGET + '-gcc'), env)
    tools['GCC_FOR_TARGET'] = tools['CC_FOR_TARGET']
    tools['CXX_FOR_TARGET'] = executable(native / 'bin' / (TARGET + '-g++'), env)
    if args.windows_host:
        tools['WINDRES']=executable(host+'-windres',env)
        prefix=args.host_dependencies/'install'
        env.update(CPPFLAGS='-I'+str(prefix/'include'),LDFLAGS='-L'+str(prefix/'lib'))
    env.update({key: str(path) for key, path in tools.items()})
    def query(command):
        return subprocess.check_output(list(map(str, command)), env=env, text=True, timeout=30).strip()
    if query([tools['CC_FOR_BUILD'], '-dumpmachine']) != BUILD or query([tools['CC'], '-dumpmachine']) != host:
        raise ValueError('Build/host compiler triples do not match the Canadian build')
    if query([tools['CC_FOR_TARGET'], '-dumpmachine']) != TARGET or query([tools['CC_FOR_TARGET'], '-dumpfullversion']) != SOURCES['gcc']['version']:
        raise ValueError('Native target compiler does not match the SDK GCC/target pins')
    output.mkdir(parents=True)
    for path in (Path(__file__).resolve(), Path(__file__).with_name('build_sdk_linux_toolchain.py').resolve()):
        shutil.copyfile(path, output / path.name)
    if args.windows_host:
        helper=Path(__file__).with_name('native_desktop_windows.py')
        shutil.copyfile(helper,output/helper.name)
    commands = []
    def run(label, command, cwd):
        run_step(label, command, cwd, env, output, commands)
    inputs = {'schema': 1, 'status': 'building', 'build': BUILD, 'host': host, 'target': TARGET,
              'execution': 'canadian-cross', 'tools': {key: {'path': str(path), 'sha256': digest(path)} for key, path in tools.items()},
              'sources': SOURCES, 'recipes': {name: digest(output / name) for name in ('build_sdk_linux_cross.py', 'build_sdk_linux_toolchain.py')}}
    if args.windows_host:
        inputs['recipes']['native_desktop_windows.py']=digest(output/'native_desktop_windows.py')
        inputs['host_dependencies']={'candidate_sha256':args.host_dependencies_sha256,'candidate':dependency}
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    archives = {name: source_archive(name, getattr(args, name + '_archive'), output) for name in SOURCES}
    scratch = output / 'scratch'; scratch.mkdir()
    install = output / 'install'
    # Keep native target tools first even after installing the new host tools.
    # In particular, building libgcc must use the native same-version compiler.
    common = ['--build=' + BUILD, '--host=' + host, '--target=' + TARGET,
              '--prefix=' + str(install), '--disable-nls', '--enable-multilib']
    try:
        for name in SOURCES:
            source = extract(archives[name], scratch, name)
            work = scratch / (name + '-build'); work.mkdir()
            flags = list(common)
            if name == 'gcc':
                flags += ['--without-headers', '--enable-languages=c,c++', '--with-multilib-list=aprofile,rmprofile',
                          '--disable-bootstrap', '--enable-link-serialization=1', '--with-system-zlib', '--with-zstd',
                          '--with-build-time-tools=' + str(native / TARGET / 'bin')]
                if args.windows_host:
                    flags += ['--with-'+library+'='+str(prefix) for library in ('gmp','mpfr','mpc','isl')]
                    flags += ['--with-zstd-include='+str(prefix/'include'),'--with-zstd-lib='+str(prefix/'lib')]
                else:
                    flags += ['--with-gmp-include=/usr/include/x86_64-linux-gnu']
                    flags += ['--with-' + library + '-lib=/usr/lib/x86_64-linux-gnu' for library in ('gmp', 'mpfr', 'mpc', 'isl', 'zstd')]
            run(name + '-configure', [source / 'configure', *flags], work)
            targets = ('all-gcc', 'install-gcc', 'all-target-libgcc', 'install-target-libgcc') if name == 'gcc' else ('all', 'install')
            for target in targets:
                run(name + '-' + target, ['make', '-j' + str(args.jobs), target], work)
            notices = output / 'notices' / name; notices.mkdir(parents=True)
            for path in source.iterdir():
                if path.is_file() and path.name.startswith(('COPYING', 'COPYRIGHT', 'LICENSE')):
                    shutil.copyfile(path, notices / path.name)
        if args.windows_host:
            from native_desktop_windows import imports, native_files
            pe_inputs={p.relative_to(install).as_posix():imports(p) for p in native_files(install)}
            for name in ('gcc','g++','as','ld','ar','nm','objcopy','objdump','readelf','size','strip'):
                if 'bin/'+TARGET+'-'+name+'.exe' not in pe_inputs:
                    raise ValueError('Missing Windows compiler tool: '+name)
            # Link the newly built ARM libgcc using native build tools. This
            # checks target runtime objects, not execution of Windows programs.
            flags=['-mcpu=cortex-a7','-marm','-mfpu=neon-vfpv4','-mfloat-abi=hard','-ffreestanding','-O2']
            directory=query([tools['CC_FOR_TARGET'],*flags,'-print-multi-directory'])
            if Path(directory).is_absolute() or '..' in Path(directory).parts:
                raise ValueError('Native compiler reported an unsafe multilib directory')
            libgcc=install/'lib/gcc'/TARGET/SOURCES['gcc']['version']/directory/'libgcc.a'
            probe=output/'probe';probe.mkdir()
            (probe/'c.c').write_text('unsigned long long divide(unsigned long long a, unsigned long long b) { return a / b; }\n')
            run('target-probe-c',[tools['CC_FOR_TARGET'],*flags,'-c','c.c','-o','c.o'],probe)
            run('target-probe-link',[tools['CC_FOR_TARGET'],*flags,'-nostdlib','-r','c.o',libgcc,'-o','mixed.o'],probe)
            require_elf(probe/'mixed.o',40,32)
            result={**inputs,'status':'passed','platform':'Windows','architecture':'AMD64',
                    'build_architecture':'aarch64','compiler':SOURCES['gcc']['version'],
                    'host_probe_execution':'not_run','native_execution_checked':False,
                    'clean_host_qualified':False,'desktop_bundle_qualified':False,
                    'pe_imports':pe_inputs,
                    'files':{p.relative_to(install).as_posix():digest(p) for p in sorted(install.rglob('*')) if p.is_file()},
                    'probe':{'execution':'native-build-tools','mixed_arm_object_sha256':digest(probe/'mixed.o'),
                             'libgcc':libgcc.relative_to(install).as_posix(),'libgcc_sha256':digest(libgcc)},
                    'build_steps_sha256':digest(output/'commands.json')}
            (output/'candidate.json').write_text(json.dumps(result,indent=2)+'\n')
            print('PASS: Windows compiler cross-build '+str(output),flush=True)
            return
        # Only this final phase executes the produced x86-64 compiler through
        # the environment's existing binfmt interpreter. It cannot be native
        # execution on this ARM64 build machine.
        compiler = install / 'bin/arm-none-eabi-g++'
        require_elf(compiler, 62, 64)
        for name in ('gcc', 'as', 'ld', 'ar'):
            require_elf(install / 'bin' / (TARGET + '-' + name), 62, 64)
        if query([compiler, '-dumpfullversion']) != SOURCES['gcc']['version']:
            raise ValueError('New host compiler does not match the SDK GCC pin')
        run('host-compiler-configuration', [compiler, '-v'], output)
        probe = output / 'probe'; probe.mkdir()
        (probe / 'c.c').write_text('unsigned long long divide(unsigned long long a, unsigned long long b) { return a / b; }\n')
        (probe / 'cpp.cpp').write_text('extern "C" unsigned long long divide(unsigned long long, unsigned long long);\n'
                                     'template<class T> T compute(T x) { return T(divide(x, 7)); }\n'
                                     'extern "C" unsigned long long result(unsigned long long x) { return compute(x); }\n')
        flags = ['-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4', '-mfloat-abi=hard', '-ffreestanding', '-O2']
        run('host-probe-c', [install / 'bin/arm-none-eabi-gcc', *flags, '-std=c11', '-c', 'c.c', '-o', 'c.o'], probe)
        run('host-probe-cpp', [compiler, *flags, '-std=c++17', '-fno-exceptions', '-fno-rtti', '-c', 'cpp.cpp', '-o', 'cpp.o'], probe)
        run('host-probe-link', [compiler, *flags, '-nostdlib', '-r', 'c.o', 'cpp.o', '-lgcc', '-o', 'mixed.o'], probe)
        require_elf(probe / 'mixed.o', 40, 32)
        libgcc = Path(query([compiler, *flags, '-print-libgcc-file-name'])).resolve()
        if not libgcc.is_file() or not libgcc.is_relative_to(install):
            raise ValueError('Host compiler did not resolve its installed ARM libgcc')
        result = {**inputs, 'status': 'passed', 'platform': 'Linux', 'architecture': 'x86_64',
                  'build_architecture': 'aarch64', 'host_probe_execution': 'emulated-binfmt',
                  'compiler': SOURCES['gcc']['version'], 'clean_host_qualified': False, 'desktop_bundle_qualified': False,
                  'files': {p.relative_to(install).as_posix(): digest(p) for p in sorted(install.rglob('*')) if p.is_file()},
                  'probe': {'mixed_arm_object_sha256': digest(probe / 'mixed.o'), 'libgcc': str(libgcc.relative_to(install)), 'libgcc_sha256': digest(libgcc)},
                  'build_steps_sha256': digest(output / 'commands.json')}
        (output / 'candidate.json').write_text(json.dumps(result, indent=2) + '\n')
        print('PASS: Canadian compiler candidate ' + str(output), flush=True)
    except BaseException as error:
        (output / 'failure.json').write_text(json.dumps({'schema': 1, 'status': 'failed', 'error': str(error)}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()

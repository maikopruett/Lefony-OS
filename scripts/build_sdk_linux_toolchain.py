#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the pinned ARM compiler/binutils on Linux x86-64 for a desktop SDK.

Use a dedicated output folder on the native host or in an explicitly identified
x86-64 container. Containers on another CPU provide emulated-host evidence only.
Nothing is installed into system directories. Source archives, notices, recipes,
logs and file hashes are retained; failed builds retain their scratch trees.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import time
import urllib.request

SOURCES = {
    'binutils': {'version': '2.47', 'archive': 'binutils-2.47.tar.bz2',
                 'url': 'https://ftp.gnu.org/gnu/binutils/binutils-2.47.tar.bz2',
                 'sha256': '3068128c75cda9f898ccb4211d360246e8e195ffcc9dfb655b23ae23a54800e8'},
    'gcc': {'version': '16.2.0', 'archive': 'gcc-16.2.0.tar.xz',
            'url': 'https://ftp.gnu.org/gnu/gcc/gcc-16.2.0/gcc-16.2.0.tar.xz',
            'sha256': 'e6738e29597f733270731aa90600f37ffdc045079dfc27ec7e8192cc81085c3e'},
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_archive(name, supplied, output):
    record = SOURCES[name]
    destination = output / record['archive']
    if supplied:
        if not supplied.is_file() or supplied.stat().st_size > 200 * 1024 * 1024:
            raise ValueError('Compiler source input must be a regular archive within its size bound')
        shutil.copyfile(supplied, destination)
    else:
        with urllib.request.urlopen(record['url'], timeout=60) as response, destination.open('wb') as stream:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 200 * 1024 * 1024:
                    raise ValueError('Compiler source archive exceeds its bound')
                stream.write(chunk)
    if digest(destination) != record['sha256']:
        raise ValueError(name + ' source archive differs from the pinned input')
    return destination


def extract(archive, output, name):
    directory = name + '-' + SOURCES[name]['version']
    with tarfile.open(archive) as stream:
        members = stream.getmembers()
        if len(members) > 200000 or sum(m.size for m in members) > 3 * 1024**3:
            raise ValueError('Compiler source extraction exceeds expected bounds')
        if any(not Path(m.name).parts or Path(m.name).parts[0] != directory for m in members):
            raise ValueError('Compiler source archive has an unexpected root')
        stream.extractall(output, filter='data')
    return output / directory


def run_step(label, command, cwd, env, output, commands, timeout=6 * 60 * 60):
    """Retain each real command's terminal outcome, including failed host tools."""
    command = list(map(str, command))
    step = {'label': label, 'arguments': command, 'cwd': str(cwd), 'status': 'running'}
    commands.append(step)
    record = output / 'commands.json'
    record.write_text(json.dumps(commands, indent=2) + '\n')
    print('START: ' + label, flush=True)
    started = time.monotonic()
    try:
        with (output / (label + '.log')).open('w') as log:
            subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        step.update(status='failed', returncode=exc.returncode)
        raise
    except subprocess.TimeoutExpired:
        step.update(status='timed_out', timeout_seconds=timeout)
        raise
    except OSError as exc:
        step.update(status='failed', error=str(exc))
        raise
    else:
        step.update(status='passed', returncode=0)
        print('PASS: ' + label, flush=True)
    finally:
        step['elapsed_seconds'] = time.monotonic() - started
        record.write_text(json.dumps(commands, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binutils-archive', type=Path)
    parser.add_argument('--gcc-archive', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--execution', choices=('native', 'emulated-container'), required=True,
                        help='Record the actual host execution mode; uname alone cannot distinguish emulation')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('Run with Linux x86-64 userspace and native Linux build tools')
    if not 1 <= args.jobs <= 32:
        parser.error('Use 1–32 build jobs')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; preserve it and choose a fresh candidate')
    output.mkdir(parents=True)
    recipe = output / Path(__file__).name
    shutil.copyfile(__file__, recipe)
    archives = {name: source_archive(name, getattr(args, name + '_archive'), output) for name in SOURCES}
    scratch = output / 'scratch'; scratch.mkdir()
    install = output / 'install'
    env = {**os.environ, 'PATH': str(install / 'bin') + os.pathsep + os.environ.get('PATH', ''),
           'CFLAGS': '-O2', 'CXXFLAGS': '-O2'}
    for key in ('GCC_EXEC_PREFIX', 'COMPILER_PATH', 'LIBRARY_PATH'):
        env.pop(key, None)
    commands = []

    def run(label, command, cwd):
        run_step(label, command, cwd, env, output, commands)

    for name in SOURCES:
        source = extract(archives[name], scratch, name)
        work = scratch / (name + '-build'); work.mkdir()
        flags = ['--target=arm-none-eabi', '--prefix=' + str(install), '--disable-nls', '--enable-multilib']
        if name == 'gcc':
            flags += ['--without-headers', '--enable-languages=c,c++', '--with-multilib-list=aprofile,rmprofile',
                      '--with-system-zlib', '--with-zstd']
        run(name + '-configure', [source / 'configure', *flags], work)
        if name == 'gcc':
            for target in ('all-gcc', 'install-gcc', 'all-target-libgcc', 'install-target-libgcc'):
                run(name + '-' + target, ['make', '-j' + str(args.jobs), target], work)
        else:
            run(name + '-build', ['make', '-j' + str(args.jobs)], work)
            run(name + '-install', ['make', 'install'], work)
        notices = output / 'notices' / name; notices.mkdir(parents=True)
        for path in source.iterdir():
            if path.is_file() and path.name.startswith(('COPYING', 'COPYRIGHT', 'LICENSE')):
                shutil.copyfile(path, notices / path.name)
    compiler = install / 'bin/arm-none-eabi-g++'
    version = subprocess.check_output([compiler, '-dumpfullversion'], env=env, text=True, timeout=30).strip()
    if version != SOURCES['gcc']['version']:
        raise ValueError('Installed compiler does not match the SDK pin')
    run('compiler-configuration', [compiler, '-v'], output)
    run('binutils-version', [install / 'bin/arm-none-eabi-as', '--version'], output)
    probe = output / 'probe'; probe.mkdir()
    (probe / 'c.c').write_text('unsigned long long divide(unsigned long long a, unsigned long long b) { return a / b; }\n')
    (probe / 'cpp.cpp').write_text('extern "C" unsigned long long divide(unsigned long long, unsigned long long);\n'
                                 'template<class T> T compute(T x) { return T(divide(x, 7)); }\n'
                                 'extern "C" unsigned long long result(unsigned long long x) { return compute(x); }\n')
    flags = ['-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4', '-mfloat-abi=hard',
             '-ffreestanding', '-O2']
    run('probe-c', [install / 'bin/arm-none-eabi-gcc', *flags, '-std=c11', '-c', 'c.c', '-o', 'c.o'], probe)
    run('probe-cpp', [compiler, *flags, '-std=c++17', '-fno-exceptions', '-fno-rtti',
                      '-c', 'cpp.cpp', '-o', 'cpp.o'], probe)
    run('probe-link', [compiler, *flags, '-nostdlib', '-r', 'c.o', 'cpp.o', '-lgcc', '-o', 'mixed.o'], probe)
    mixed = (probe / 'mixed.o').read_bytes()
    if mixed[:6] != b'\x7fELF\x01\x01' or int.from_bytes(mixed[18:20], 'little') != 40:
        raise ValueError('Compiler probe did not produce a little-endian ARM ELF32 object')
    libgcc = Path(subprocess.check_output([compiler, *flags, '-print-libgcc-file-name'],
                                         env=env, text=True, timeout=30).strip()).resolve()
    if not libgcc.is_file() or not libgcc.is_relative_to(install):
        raise ValueError('Compiler probe did not resolve its installed ARM libgcc')
    files = {str(p.relative_to(install)): digest(p) for p in sorted(install.rglob('*')) if p.is_file()}
    report = {'schema': 1, 'platform': platform.system(), 'architecture': platform.machine(),
              'execution': args.execution, 'compiler': version, 'sources': SOURCES,
              'recipe_sha256': digest(recipe), 'files': files, 'clean_host_qualified': False,
              'desktop_bundle_qualified': False, 'probe': {'mixed_arm_object_sha256': digest(probe / 'mixed.o'),
              'libgcc': str(libgcc.relative_to(install)), 'libgcc_sha256': digest(libgcc)},
              'build_steps_sha256': digest(output / 'commands.json')}
    (output / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.rmtree(scratch)
    print('PASS: compiler candidate ' + str(output), flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Linux x86-64 Prime QEMU with native Linux ARM64 build tools.

Supply a checksum-verified, prepared source archive with the current Prime
patches and offline subprojects. Verify its provenance against the normal VM
build before using this recipe. Output/logs/source are retained on failure.
The final executable probes use existing binfmt emulation, not a native host.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile

from build_sdk_linux_cross import executable, require_elf
from build_sdk_linux_toolchain import digest, run_step

VERSION = '11.1.1'
PATCHSET = 'r75'
SOURCE_ROOT = 'qemu-prime-g2-source-v' + VERSION + '-' + PATCHSET
HOST = 'x86_64-linux-gnu'


def extract_source(archive, output):
    with tarfile.open(archive) as stream:
        members = stream.getmembers()
        if len(members) > 25000 or sum(m.size for m in members) > 1024**3:
            raise ValueError('QEMU source extraction exceeds expected bounds')
        names = set()
        for member in members:
            path = Path(member.name)
            if not path.parts and member.isdir():
                continue
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] != SOURCE_ROOT or path.as_posix() in names):
                raise ValueError('QEMU source archive has an unexpected or duplicate path')
            if '.git' in path.parts or '__pycache__' in path.parts or path.suffix == '.pyc':
                raise ValueError('Use a prepared source archive without Git metadata or bytecode')
            names.add(path.as_posix())
        stream.extractall(output, filter='data')
    source = output / SOURCE_ROOT
    if (source / 'VERSION').read_text().strip() != VERSION:
        raise ValueError('QEMU source version differs from the SDK pin')
    for name in ('configure', 'hw/arm/prime_g2_peripherals.c',
                 'include/hw/arm/prime_g2_peripherals.h', 'hw/arm/prime_g2_bch.c'):
        if not (source / name).is_file():
            raise ValueError('Missing prepared Prime QEMU source: ' + name)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--cross-prefix', type=Path, required=True)
    parser.add_argument('--sysroot', type=Path, required=True,
                        help='Directory containing the isolated x86-64 library packages')
    parser.add_argument('--pkg-config-libdir', required=True,
                        help='Colon-separated x86-64/common pkg-config directories')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('Run this cross build on Linux ARM64')
    if not 1 <= args.jobs <= 32 or not re.fullmatch('[0-9a-f]{64}', args.archive_sha256):
        parser.error('Use 1–32 jobs and an exact lowercase archive SHA-256')
    output = args.output.resolve()
    if output.exists() or any(c.isspace() for c in str(output)):
        parser.error('Use a fresh output directory without whitespace')
    if not args.archive.is_file() or args.archive.stat().st_size > 200 * 1024**2:
        parser.error('Source archive is missing or exceeds its size bound')
    if digest(args.archive) != args.archive_sha256:
        parser.error('QEMU archive differs from the selected source input')
    sysroot = args.sysroot.resolve()
    if not sysroot.is_dir() or any(c.isspace() for c in str(sysroot)):
        parser.error('Use an existing dependency sysroot without whitespace')
    libdirs = [Path(value).resolve() for value in args.pkg_config_libdir.split(':')]
    if not libdirs or not all(p.is_dir() for p in libdirs):
        parser.error('Every pkg-config directory must exist')
    env = {**os.environ, 'LC_ALL': 'C', 'PYTHONDONTWRITEBYTECODE': '1'}
    for key in ('CC', 'CXX', 'AR', 'AS', 'LD', 'NM', 'RANLIB', 'STRIP', 'READELF',
                'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'GCC_EXEC_PREFIX', 'COMPILER_PATH',
                'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH',
                'PKG_CONFIG_PATH', 'PKG_CONFIG_SYSROOT_DIR', 'LD_LIBRARY_PATH'):
        env.pop(key, None)
    prefix = str(args.cross_prefix.resolve())
    tools = {name: executable(prefix + name, env)
             for name in ('gcc', 'g++', 'ar', 'as', 'ld', 'nm', 'ranlib', 'strip', 'readelf')}
    tools.update({name: executable(name, env) for name in ('cc', 'ninja', 'pkg-config')})
    require_elf(Path(sys.executable).resolve(), 183, 64)
    triplet = subprocess.check_output([tools['gcc'], '-dumpmachine'], text=True, timeout=10).strip()
    if triplet != HOST:
        parser.error('Use a Linux x86-64 cross compiler')
    env.update(CC=str(tools['gcc']), CXX=str(tools['g++']),
               PKG_CONFIG=str(tools['pkg-config']),
               PKG_CONFIG_LIBDIR=':'.join(map(str, libdirs)),
               PKG_CONFIG_SYSROOT_DIR=str(sysroot))
    library_dirs = [sysroot / 'usr/lib/x86_64-linux-gnu',
                    sysroot / 'usr/lib/x86_64-linux-gnu/pulseaudio']
    library_path = ':'.join(str(path) for path in library_dirs if path.is_dir())
    env['LDFLAGS'] = '-Wl,-rpath-link,' + library_path
    output.mkdir(parents=True)
    archives = output / 'source.tar.gz'
    shutil.copyfile(args.archive, archives)
    recipe_names = ('build_sdk_linux_qemu.py', 'build_sdk_linux_cross.py', 'build_sdk_linux_toolchain.py')
    for name in recipe_names:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    inputs = {'schema': 1, 'version': VERSION, 'patchset': PATCHSET,
              'source_sha256': digest(archives), 'build_architecture': 'aarch64',
              'architecture': 'x86_64', 'platform': 'Linux',
              'recipes': {name: digest(output / name) for name in recipe_names},
              'tools': {name: {'path': str(path), 'sha256': digest(path)} for name, path in tools.items()},
              'pkg_config_libdir': env['PKG_CONFIG_LIBDIR'], 'dependency_sysroot': str(sysroot),
              'dependency_library_path': library_path}
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    commands = []
    def run(label, command, cwd, timeout=3600, host_probe=False):
        selected_env = env
        if host_probe:
            selected_env = {**env, 'LD_LIBRARY_PATH': library_path}
        run_step(label, command, cwd, selected_env, output, commands, timeout=timeout)
    try:
        scratch = output / 'scratch'; scratch.mkdir()
        source = extract_source(archives, scratch)
        work = scratch / 'build'; work.mkdir()
        run('configure', [source / 'configure', '--target-list=arm-softmmu',
                         '--cross-prefix=' + prefix, '--host-cc=' + str(tools['cc']),
                         '--extra-cflags=-isystem ' + str(sysroot / 'usr/include/x86_64-linux-gnu'),
                         '--extra-cxxflags=-isystem ' + str(sysroot / 'usr/include/x86_64-linux-gnu'),
                         '--cpu=x86_64', '--disable-download', '--disable-docs',
                         '--disable-werror', '--enable-fdt=internal', '--enable-sdl', '--enable-pixman',
                         '--enable-libusb', '--python=' + sys.executable], work)
        run('compile', [tools['ninja'], '-j' + str(args.jobs), 'qemu-system-arm'], work)
        install = output / 'install'; install.mkdir()
        program = install / 'qemu-system-arm'
        shutil.copyfile(work / program.name, program); program.chmod(0o755)
        require_elf(program, 62, 64)
        run('version', [program, '--version'], output, timeout=30, host_probe=True)
        run('display-help', [program, '-display', 'help'], output, timeout=30, host_probe=True)
        run('machine-help', [program, '-machine', 'help'], output, timeout=30, host_probe=True)
        if VERSION not in (output / 'version.log').read_text() or 'sdl' not in (output / 'display-help.log').read_text().split():
            raise ValueError('QEMU version or SDL support differs from the selected profile')
        if 'hp-prime-g2' not in (output / 'machine-help.log').read_text():
            raise ValueError('QEMU is missing the Prime machine')
        notices = output / 'notices'; notices.mkdir()
        for name in ('COPYING', 'COPYING.LIB', 'LICENSE'):
            if (source / name).is_file():shutil.copyfile(source / name, notices / name)
        result = {**inputs, 'status': 'passed', 'execution': 'cross-build',
                  'host_probe_execution': 'emulated-binfmt', 'clean_host_qualified': False,
                  'desktop_bundle_qualified': False, 'qemu_sha256': digest(program),
                  'build_steps_sha256': digest(output / 'commands.json')}
        (output / 'candidate.json').write_text(json.dumps(result, indent=2) + '\n')
        print('PASS: Linux x86-64 Prime QEMU component', flush=True)
    except BaseException as error:
        (output / 'failure.json').write_text(json.dumps({'status': 'failed', 'error': str(error)}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()

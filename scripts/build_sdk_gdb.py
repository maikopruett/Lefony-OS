#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build pinned ARM GDB for a native SDK bundle, without a second Python runtime.

Run on a Unix build host with make, GMP, MPFR and Expat. --windows-host uses
an explicit MinGW-w64 cross toolchain and Windows dependency prefixes.
--linux-host uses a Linux x86-64 cross compiler and matching dependency prefixes.
Cross-builds do not qualify native host execution or install onto a device.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '17.2'
ARCHIVE = 'gdb-' + VERSION + '.tar.xz'
URL = 'https://ftp.gnu.org/gnu/gdb/' + ARCHIVE
SHA256 = '1c036c0d72e4b3d1fb5c94c88632add6f9d76f4d7c4d2ea793c12a9f19a3228c'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def build_directory(output, parent=None):
    """Keep make paths free of spaces and retain diagnostics after a failure."""
    directory = Path(tempfile.mkdtemp(prefix='lefony-gdb-', dir=parent or '/tmp')).resolve()
    (output / 'build-directory.json').write_text(
        json.dumps({'directory': str(directory)}, indent=2) + '\n')
    yield directory
    shutil.rmtree(directory)


def host_configuration(windows, cross_prefix, linux=False):
    if windows and linux:
        raise ValueError('Choose one GDB host platform')
    if not windows and not linux:
        if cross_prefix:
            raise ValueError('--cross-prefix requires --windows-host or --linux-host')
        return [], {}, platform.system(), platform.machine(), ''
    option = '--windows-host' if windows else '--linux-host'
    if not cross_prefix:
        raise ValueError(option + ' requires an explicit --cross-prefix')
    names = {'CC': 'gcc', 'CXX': 'g++', 'AR': 'ar', 'RANLIB': 'ranlib',
             'STRIP': 'strip'}
    if windows:
        names['WINDRES'] = 'windres'
    tools = {}
    for variable, name in names.items():
        path = Path(str(cross_prefix) + name).resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Missing GDB cross tool: ' + str(path))
        tools[variable] = str(path)
    triplet = subprocess.check_output([tools['CC'], '-dumpmachine'], text=True, timeout=10).strip()
    expected = 'x86_64-w64-mingw32' if windows else 'x86_64-linux-gnu'
    if triplet != expected:
        raise ValueError('GDB requires ' + expected + ' cross tools')
    return ['--host=' + triplet], tools, 'Windows' if windows else 'Linux', 'AMD64' if windows else 'x86_64', '.exe' if windows else ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--work-parent', type=Path,
                        help='Existing directory without spaces for build scratch (default: /tmp); failed scratch is retained')
    parser.add_argument('--gmp-prefix', type=Path)
    parser.add_argument('--mpfr-prefix', type=Path)
    parser.add_argument('--expat-prefix', type=Path)
    hosts = parser.add_mutually_exclusive_group()
    hosts.add_argument('--windows-host', action='store_true', help='Cross-build native Windows x86-64 GDB on this Unix host')
    hosts.add_argument('--linux-host', action='store_true', help='Cross-build Linux x86-64 GDB; execution requires a matching host or emulator')
    parser.add_argument('--cross-prefix', type=Path, help='Absolute compiler prefix, e.g. /opt/mingw/bin/x86_64-w64-mingw32-')
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 1, 4))
    args = parser.parse_args()
    if os.name == 'nt' or not 1 <= args.jobs <= 64:
        parser.error('Use a Unix build host and 1–64 jobs')
    if args.work_parent:
        args.work_parent = args.work_parent.resolve()
        if not args.work_parent.is_dir() or any(c.isspace() for c in str(args.work_parent)):
            parser.error('--work-parent must be an existing directory without whitespace')
    try:
        host_flags, cross_environment, target_system, target_machine, suffix = host_configuration(args.windows_host, args.cross_prefix, args.linux_host)
    except ValueError as exc:
        parser.error(str(exc))
    if (args.windows_host or args.linux_host) and not all((args.gmp_prefix, args.mpfr_prefix, args.expat_prefix)):
        parser.error('Cross builds require explicit host GMP, MPFR and Expat prefixes')
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; use a fresh candidate directory')
    make = shutil.which('make')
    if not make:
        parser.error('A native compiler and make are required')
    output.mkdir(parents=True)
    archive = output / ARCHIVE
    if args.archive:
        shutil.copyfile(args.archive, archive)
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(64 * 1024 * 1024 + 1)
        if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('GDB download differs from the pinned archive')
        archive.write_bytes(data)
    if digest(archive) != SHA256:
        raise ValueError('GDB archive differs from the pinned source')
    with build_directory(output, args.work_parent) as temporary:
        with tarfile.open(archive) as source_archive:
            members = source_archive.getmembers()
            if len(members) > 60000 or sum(m.size for m in members) > 1024 * 1024 * 1024:
                raise ValueError('GDB extraction exceeds expected bounds')
            source_archive.extractall(temporary, filter='data')
        source = temporary / ('gdb-' + VERSION)
        if cross_environment:
            build_triplet = subprocess.check_output(
                [source / 'config.guess'], text=True, timeout=10).strip()
            host_flags = ['--build=' + build_triplet, *host_flags]
        work = temporary / 'work'; work.mkdir()
        stage = temporary / 'stage'
        prefix = '/opt/lefony-sdk/toolchain'
        configure = [str(source / 'configure'), '--target=arm-none-eabi', '--prefix=' + prefix,
                     *host_flags,
                     '--disable-binutils', '--disable-gas', '--disable-ld', '--disable-gold',
                     '--disable-gprofng', '--disable-sim', '--disable-nls', '--disable-werror',
                     '--without-python', '--without-guile', '--without-debuginfod',
                     '--without-lzma', '--without-babeltrace', '--without-intel-pt',
                     '--without-xxhash', '--without-zstd', '--disable-tui',
                     '--with-expat', '--without-system-zlib' if args.windows_host else '--with-system-zlib']
        for name in ('gmp', 'mpfr'):
            value = getattr(args, name + '_prefix')
            if value:
                configure.append('--with-' + name + '=' + str(value.resolve()))
        if args.expat_prefix:
            configure.append('--with-libexpat-prefix=' + str(args.expat_prefix.resolve()))
        flags = '-O2 -g0 -ffile-prefix-map=' + str(temporary) + '=/lefony-gdb-build'
        environment = {**os.environ, **cross_environment, 'CFLAGS': flags, 'CXXFLAGS': flags, 'LC_ALL': 'C'}
        commands = [configure, [make, '-j' + str(args.jobs), 'all-gdb', 'MAKEINFO=true'],
                    [make, 'install-gdb', 'MAKEINFO=true', 'DESTDIR=' + str(stage)]]
        for index, command in enumerate(commands):
            print(('configure', 'build', 'install')[index] + ': ARM GDB ' + VERSION, flush=True)
            with (output / (str(index) + '.log')).open('w') as log:
                subprocess.run(command, cwd=work, env=environment, check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        shutil.copytree(stage / prefix.lstrip('/'), output / 'install')
        notices = output / 'notices'; notices.mkdir()
        for name in ('COPYING', 'COPYING3', 'COPYING.LIB', 'COPYING3.LIB'):
            if (source / name).is_file():
                shutil.copyfile(source / name, notices / name)
    program = output / ('install/bin/arm-none-eabi-gdb' + suffix)
    if args.windows_host:
        from native_desktop_windows import imports
        imports(program)  # PE architecture/import validation, not execution.
        configuration = None
    else:
        if args.linux_host:
            with program.open('rb') as stream:
                header = stream.read(20)
            if len(header) != 20 or header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 62:
                raise ValueError('Linux cross GDB is not an x86-64 ELF executable')
        version = subprocess.check_output([program, '--version'], text=True, timeout=10)
        configuration = subprocess.check_output([program, '--configuration'], text=True, timeout=10)
        if '--without-python' not in configuration or VERSION not in version.splitlines()[0]:
            raise ValueError('Unexpected GDB build configuration')
    shutil.copyfile(Path(__file__), output / 'build_sdk_gdb.py')
    helper = Path(__file__).with_name('native_desktop_windows.py')
    shutil.copyfile(helper, output / helper.name)
    report = {'schema': 1, 'version': VERSION, 'platform': target_system,
              'architecture': target_machine, 'source_url': URL, 'source_sha256': SHA256,
              'recipe_sha256': digest(Path(__file__)), 'configuration': configuration,
              'recipe_inputs': {helper.name: digest(helper)},
              'execution_checked': not args.windows_host, 'configure_arguments': configure[1:],
              'native_execution_checked': not args.windows_host and platform.system() == target_system and platform.machine().lower() == target_machine.lower(),
              'execution': 'not_run' if args.windows_host else 'emulated-host' if args.linux_host and platform.machine().lower() != 'x86_64' else 'native',
              'build_host': {'platform': platform.system(), 'architecture': platform.machine()},
              'cross_tools': {name: digest(Path(path)) for name, path in cross_environment.items()},
              'files': {p.relative_to(output / 'install').as_posix(): digest(p)
                        for p in sorted((output / 'install').rglob('*')) if p.is_file()}}
    (output / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    print(program, flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a pinned Cortex-A7 newlib candidate for SDK architecture qualification.

This builds libraries only. It supplies no successful syscall stubs and does not
change the default SDK linker, firmware trust roots, or any connected device.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '4.6.0.20260123'
ARCHIVE = 'newlib-' + VERSION + '.tar.gz'
URL = 'https://sourceware.org/pub/newlib/' + ARCHIVE
SHA256 = '6ff27e3bf022666f43f7802255be680eeff722ac181b1725d21e2e8318604ee3'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_source(source):
    """Keep newlib FILE descriptors wide enough for the OS's non-reused handles.

    This changes an app-linked library structure, not the firmware ABI. Rebuild
    all newlib objects and ship matching headers. Preserve upstream notices.
    """
    adjustments = json.loads((ROOT / 'sdk/contracts/newlib.json').read_text())['source_adjustments']
    change = adjustments['stdio-descriptor-32-v1']
    header = source / change['path']
    current = digest(header)
    if current == change['after_sha256']:
        return adjustments
    if current != change['before_sha256']:
        raise ValueError('Unexpected pinned newlib FILE header; refusing descriptor transformation')
    before = b'  short\t_file;\t\t/* fileno, if Unix descriptor, else -1 */'
    after = before.replace(b'short', b'int', 1)
    data = header.read_bytes()
    if data.count(before) != 2:
        raise ValueError('Expected both normal and large-file newlib descriptor fields')
    data = data.replace(before, after)
    if hashlib.sha256(data).hexdigest() != change['after_sha256']:
        raise ValueError('Unexpected transformed newlib FILE header')
    header.write_bytes(data)
    return adjustments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sdk-newlib')
    parser.add_argument('--archive', type=Path, help='Use this exact pinned archive without downloading')
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 1, 8))
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be between 1 and 64')
    compiler = shutil.which('arm-none-eabi-gcc')
    make = shutil.which('make')
    expected_compiler = json.loads((ROOT / 'sdk/contract.json').read_text())['compiler']
    if not compiler or not make:
        parser.error('Pinned arm-none-eabi-gcc and make are required')
    version = subprocess.check_output([compiler, '-dumpfullversion'], text=True, timeout=10).strip()
    if version != expected_compiler:
        parser.error(f'Expected GCC {expected_compiler}; found {version}')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.build-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        parser.error('Output is locked; confirm no build is running before removing its .build-lock')
    try:
        archive = args.archive.resolve() if args.archive else output / ARCHIVE
        if not archive.exists():
            if args.archive:
                parser.error('The supplied archive does not exist')
            with urllib.request.urlopen(URL, timeout=60) as response:
                data = response.read(16 * 1024 * 1024 + 1)
            if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA256:
                raise ValueError('Newlib download size or digest differs from the pinned archive')
            archive.write_bytes(data)
        if digest(archive) != SHA256:
            raise ValueError('Newlib archive differs from the pinned source')
        if archive != output / ARCHIVE:
            shutil.copyfile(archive, output / ARCHIVE)
        report = output / 'candidate.json'
        report.unlink(missing_ok=True)
        # Fresh extracted source and object tree ensure no previous local source
        # edits become part of this candidate. Existing successful install files
        # are never a substitute for a successful build/report in this run.
        # Upstream configure rejects a source path containing spaces. Keep its
        # private build/staging paths neutral; the SDK output may contain spaces.
        with tempfile.TemporaryDirectory(prefix='lefony-newlib-', dir='/tmp') as directory:
            # macOS resolves /tmp to /private/tmp for DW_AT_comp_dir. Use the
            # canonical path everywhere so the prefix map covers source and CWD.
            temporary = Path(directory).resolve()
            with tarfile.open(archive, 'r:gz') as source_archive:
                members = source_archive.getmembers()
                if len(members) > 30000 or sum(m.size for m in members) > 256 * 1024 * 1024:
                    raise ValueError('Newlib extraction exceeds expected bounds')
                source_archive.extractall(temporary, filter='data')
            source = temporary / ('newlib-' + VERSION)
            adjustments = prepare_source(source)
            work = temporary / 'work'
            work.mkdir()
            stage = temporary / 'install'
            flags = ['-Os', '-g', '-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4',
                     '-mfloat-abi=hard', '-ffunction-sections', '-fdata-sections',
                     f'-ffile-prefix-map={temporary}=/lefony-newlib-build']
            environment = {**os.environ, 'CFLAGS_FOR_TARGET': ' '.join(flags),
                           'SOURCE_DATE_EPOCH': '1769126400', 'LC_ALL': 'C'}
            configure = [str(source / 'configure'), '--target=arm-none-eabi',
                         '--prefix=' + str(stage), '--disable-multilib',
                         '--disable-newlib-supplied-syscalls', '--disable-libgloss',
                         '--disable-newlib-multithread', '--disable-newlib-reent-small',
                         '--disable-newlib-atexit-dynamic-alloc', '--disable-nls',
                         '--enable-newlib-io-long-long', '--enable-newlib-io-c99-formats']
            commands = [configure, [make, '-j' + str(args.jobs), 'all-target-newlib', 'MAKEINFO=true'],
                        [make, 'install-target-newlib', 'MAKEINFO=true']]
            for index, command in enumerate(commands):
                print(('configure', 'build', 'install')[index] + ': pinned newlib ' + VERSION, flush=True)
                with (output / (str(index) + '.log')).open('w') as log:
                    subprocess.run(command, cwd=work, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
            install = output / 'install'
            if install.exists():
                shutil.rmtree(install)
            shutil.copytree(stage, install)
            libraries = {}
            for name in ('libc.a', 'libm.a'):
                path = install / 'arm-none-eabi/lib' / name
                libraries[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
            shutil.copyfile(source / 'COPYING.NEWLIB', output / 'COPYING.NEWLIB')
            report.write_text(json.dumps({'schema': 1, 'status': 'library-built-not-runtime-qualified',
                'source': URL, 'source_sha256': SHA256, 'version': VERSION,
                'compiler': version, 'compiler_sha256': digest(Path(compiler)),
                'target': 'arm-none-eabi cortex-a7 arm hard-float neon-vfpv4',
                'libraries': libraries, 'syscall_adapter': 'not supplied',
                'headers': {p.relative_to(install / 'arm-none-eabi/include').as_posix(): digest(p)
                            for p in sorted((install / 'arm-none-eabi/include').rglob('*')) if p.is_file()},
                'physical': 'not_tested', 'flags': [f.replace(str(temporary), '/lefony-newlib-build') for f in flags],
                'configure_options': [c for c in configure[1:] if not c.startswith('--prefix=')],
                'source_adjustments': adjustments,
                'license_sha256': digest(output / 'COPYING.NEWLIB')}, indent=2) + '\n')
            print('Built candidate: ' + str(report), flush=True)
    finally:
        lock.rmdir()


if __name__ == '__main__':
    main()

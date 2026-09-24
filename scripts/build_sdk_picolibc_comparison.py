#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an isolated Picolibc input for the SDK library comparison.

This does not select a new SDK runtime, provide OS adapters or qualify apps.
The default developer profile remains newlib. Meson 1.7.2, Ninja and the pinned
ARM compiler must already be installed; only the pinned source is downloaded.
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
VERSION = '1.8.12'
COMMIT = '2ae376c6cdf4fef90ca2388ecf7a07457fa63cff'
URL = 'https://codeload.github.com/picolibc/picolibc/tar.gz/' + COMMIT
SHA256 = '2946ea55b915f7f4555d60bffbaea6a3edc0b8993b7ded3935be9a15cfb7157b'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--meson', default='meson')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--fast-bufio', action='store_true', help='Compare Picolibc\'s optional faster buffered I/O')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists(): parser.error('Choose a fresh output directory')
    if not 1 <= args.jobs <= 64: parser.error('jobs must be in 1..64')
    meson = shutil.which(args.meson)
    if not meson or subprocess.check_output([meson, '--version'], text=True, timeout=10).strip() != '1.7.2':
        parser.error('The comparison recipe requires Meson 1.7.2')
    compiler = shutil.which('arm-none-eabi-gcc')
    expected = json.loads((ROOT / 'sdk/contract.json').read_text())['compiler']
    if not compiler or subprocess.check_output([compiler, '-dumpfullversion'], text=True, timeout=10).strip() != expected:
        parser.error('The comparison requires the SDK-pinned ARM GCC')
    if not shutil.which('ninja'): parser.error('Ninja is required')
    output.mkdir(parents=True)
    archive = output / ('picolibc-' + VERSION + '.tar.gz')
    if args.archive: shutil.copyfile(args.archive, archive)
    else:
        with urllib.request.urlopen(URL, timeout=30) as response: data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('Picolibc source differs from the pinned archive')
        archive.write_bytes(data)
    if digest(archive) != SHA256: raise ValueError('Picolibc source differs from the pinned archive')
    options = ['-Dmultilib=false', '-Dpicocrt=false', '-Dpicocrt-lib=false', '-Dsemihost=false',
               '-Dthread-local-storage=false', '-Dposix-console=true', '-Dstdio-exit-flush=true',
               '-Dinitfini-array=false', '-Dtests=false', '-Dformat-default=double',
               '-Dfast-bufio=' + str(args.fast_bufio).lower()]
    with tempfile.TemporaryDirectory(prefix='lefony-picolibc-', dir='/tmp') as folder:
        folder = Path(folder).resolve()
        with tarfile.open(archive) as source:
            members = source.getmembers()
            if len(members) > 30000 or sum(m.size for m in members) > 256 * 1024 * 1024:
                raise ValueError('Picolibc source extraction exceeds expected bounds')
            source.extractall(folder, filter='data')
        source = folder / ('picolibc-' + COMMIT); work = folder / 'work'; stage = folder / 'install'
        flags = ['-Os', '-g', '-mcpu=cortex-a7', '-marm', '-mfpu=neon-vfpv4', '-mfloat-abi=hard',
                 '-ffunction-sections', '-fdata-sections', f'-ffile-prefix-map={folder}=/lefony-picolibc-build']
        cross = folder / 'arm.ini'
        cross.write_text("[binaries]\nc = " + repr(compiler) + "\nar = 'arm-none-eabi-ar'\nstrip = 'arm-none-eabi-strip'\n"
            "[host_machine]\nsystem = 'none'\ncpu_family = 'arm'\ncpu = 'cortex-a7'\nendian = 'little'\n"
            "[properties]\nneeds_exe_wrapper = true\n[built-in options]\nc_args = " + repr(flags) +
            "\nc_link_args = " + repr(flags[2:6]) + '\n')
        environment = {**os.environ, 'LC_ALL': 'C', 'SOURCE_DATE_EPOCH': '1754006400'}
        commands = [[meson, 'setup', str(work), str(source), '--cross-file', str(cross),
                     '--prefix', str(stage), '--libdir', 'lib', '--buildtype', 'plain', *options],
                    ['ninja', '-C', str(work), '-j' + str(args.jobs)],
                    [meson, 'install', '-C', str(work), '--no-rebuild']]
        for number, command in enumerate(commands):
            print(('configure', 'build', 'install')[number] + ': Picolibc comparison ' + VERSION, flush=True)
            with (output / (str(number) + '.log')).open('w') as log:
                subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=900)
        shutil.copytree(stage, output / 'install')
        # Picolibc's notice inventory has its own name. Missing notices are a
        # build failure; silently probing newlib's filenames lost this file.
        notice = output / 'COPYING.picolibc'
        shutil.copyfile(source / notice.name, notice)
        report = {'schema': 1, 'status': 'library-built-not-runtime-qualified', 'version': VERSION,
            'commit': COMMIT, 'source_url': URL, 'source_sha256': SHA256, 'compiler': expected,
            'meson': '1.7.2', 'ninja': subprocess.check_output(['ninja', '--version'], text=True).strip(),
            'options': options, 'flags': [f.replace(str(folder), '/lefony-picolibc-build') for f in flags],
            'files': {p.relative_to(output / 'install').as_posix(): digest(p)
                      for p in sorted((output / 'install').rglob('*')) if p.is_file()},
            'recipe_sha256': digest(Path(__file__)), 'syscall_adapter': 'not supplied', 'physical': 'not_tested'}
        report['notices'] = {notice.name: digest(notice)}
        (output / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Built comparison input: ' + str(output / 'candidate.json'), flush=True)


if __name__ == '__main__': main()

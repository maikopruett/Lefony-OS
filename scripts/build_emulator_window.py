#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Freeze the shared desktop window on its native macOS, Linux or Windows host."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = '6.11.2'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def executable_name(system):
    if system == 'Darwin':
        return 'Lefony Emulator.app/Contents/MacOS/Lefony Emulator'
    if system == 'Windows':
        return 'Lefony Emulator.exe'
    if system == 'Linux':
        return 'Lefony Emulator'
    raise ValueError('Desktop emulator requires macOS, Linux or Windows')


def verify(directory, system=None, machine=None):
    system, machine = system or platform.system(), machine or platform.machine()
    record = json.loads((directory / 'window.json').read_text())
    if (record['system'] != system or record['machine'] != machine or
            record['qt_version'] != VERSION or record['executable'] != executable_name(system) or
            record['source_sha256'] != digest(ROOT / 'sdk/tools/emulator_window.py')):
        raise ValueError('Desktop window must match this host and renderer source')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and p.name != 'window.json'}
    if actual != set(record['files']):
        raise ValueError('Desktop window bundle has missing or extra files')
    if any(p.is_symlink() and not p.resolve().is_relative_to(directory.resolve()) for p in directory.rglob('*')):
        raise ValueError('Desktop window bundle has an external symlink')
    for name, expected in record['files'].items():
        path = directory / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Unsafe desktop window bundle path')
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Desktop window bundle changed: ' + name)
    if record['executable'] not in record['files']:
        raise ValueError('Desktop window executable is not recorded')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; select a new build directory')
    for name in ('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6'):
        if importlib.metadata.version(name) != VERSION:
            parser.error('Install sdk/requirements-emulator.txt first')
    system = platform.system()
    executable_name(system)
    stage = output.parent / (output.name + '-work')
    source = ROOT / 'sdk/tools/emulator_window.py'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--name', 'Lefony Emulator', '--distpath', str(stage / 'dist'),
               '--workpath', str(stage / 'build'), '--specpath', str(stage),
               '--copy-metadata', 'PySide6', '--copy-metadata', 'PySide6_Addons',
               '--copy-metadata', 'PySide6_Essentials', '--copy-metadata', 'shiboken6']
    if system in ('Darwin', 'Windows'):
        command += ['--windowed']
    command += [str(source)]
    subprocess.run(command, check=True)
    if system == 'Darwin':
        output.mkdir(parents=True)
        shutil.copytree(stage / 'dist/Lefony Emulator.app', output / 'Lefony Emulator.app', symlinks=True)
    else:
        shutil.copytree(stage / 'dist/Lefony Emulator', output, symlinks=True)
    # Retain the wrapper source and notices alongside the independently built runtime.
    shutil.copyfile(source, output / 'emulator_window.py')
    shutil.copyfile(ROOT / 'LICENSES/GPL-3.0-or-later.txt', output / 'COPYING.txt')
    record = dict(schema=1, system=system, machine=platform.machine(), qt_version=VERSION,
                  source_sha256=digest(source), executable=executable_name(system),
                  files={p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob('*')) if p.is_file()})
    (output / 'window.json').write_text(json.dumps(record, indent=2)+'\n')
    verify(output)
    print(output)


if __name__ == '__main__':
    main()

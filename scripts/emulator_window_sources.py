#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory native window inputs and bind them to exact corresponding sources.

Inventory runs in the window's build environment. Its Debian input file is
private build evidence for collect_native_linux_sources.py. The public report
contains provider identities and hashes, never local build paths.
"""
import argparse
import ast
import base64
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

from build_emulator_window import VERSION, digest, verify

QT_SOURCES = {
    'qt-everywhere-src-6.11.2.tar.xz': {
        'bytes': 1019661552,
        'sha256': '6dcfbca271d76a6502741a2c0dc6fc98ef7dd0b7b4cfd0abcebb285a86a26f33',
        'url': 'https://download.qt.io/archive/qt/6.11/6.11.2/single/qt-everywhere-src-6.11.2.tar.xz'},
    'pyside-setup-everywhere-src-6.11.2.tar.xz': {
        'bytes': 18053248,
        'sha256': 'cba47efbaad1bedd529725cbc14e21f156c7a19366f07b3edfbb076ffd7afdf8',
        'url': 'https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz'},
}


def binary_inputs(toc):
    if toc.stat().st_size > 16 * 1024 ** 2:
        raise ValueError('Window input table exceeds bound')
    result = {}
    def visit(value):
        if not isinstance(value, (list, tuple)):
            return
        if len(value) == 3 and all(isinstance(v, str) for v in value) and value[2] in ('BINARY', 'EXTENSION'):
            target, source, _ = value
            if target in result and result[target] != source:
                raise ValueError('Conflicting window input')
            result[target] = source
        else:
            for item in value:
                visit(item)
    visit(ast.literal_eval(toc.read_text()))
    if not result:
        raise ValueError('Window has no native inputs')
    return result


def debian_provider(source):
    candidates = [source, Path('/' + str(source).removeprefix('/usr/'))]
    for path in candidates:
        query = subprocess.run(['dpkg-query', '-S', str(path)], text=True, capture_output=True, timeout=10)
        if query.returncode == 0:
            owner = query.stdout.split(': ', 1)[0]
            fields = subprocess.check_output(['dpkg-query', '-W',
                '-f=${Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}',
                owner], text=True, timeout=10).split('\t')
            if len(fields) != 5 or fields[2] != 'amd64':
                raise ValueError('Unexpected native package architecture')
            return dict(kind='debian-package', package=fields[0], version=fields[1],
                        source_package=fields[3], source_version=fields[4])
    raise ValueError('Unmapped native dependency: ' + str(source))


def inventory(toc, window):
    record = verify(window)
    wheels = {}
    for name in ('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6'):
        distribution = importlib.metadata.distribution(name)
        if distribution.version != VERSION:
            raise ValueError('Window wheel version differs')
        for file in distribution.files or []:
            if file.hash and file.hash.mode == 'sha256':
                wheels[Path(distribution.locate_file(file)).resolve()] = (name, file)
    files, private = {}, []
    for target, origin in binary_inputs(toc).items():
        source = Path(origin).resolve()
        hashed = digest(source)
        if source in wheels:
            name, wheel_file = wheels[source]
            expected = base64.urlsafe_b64decode(wheel_file.hash.value + '===').hex()
            if hashed != expected:
                raise ValueError('Installed Qt wheel file differs from RECORD: ' + target)
            provider = dict(component='qt-pyside', version=VERSION, wheel=name)
        elif platform.system() == 'Darwin' and 'Cellar' in source.parts:
            index = source.parts.index('Cellar')
            name = source.parts[index+1]
            receipt = json.loads(Path(*source.parts[:index+3], 'INSTALL_RECEIPT.json').read_text())
            provider = dict(component=name, version=receipt['source']['versions']['stable'])
        elif platform.system() == 'Linux':
            debian = debian_provider(source)
            private.append(dict(source=str(source), source_sha256=hashed, origin=debian))
            provider = dict(component='debian-' + debian['source_package'], version=debian['source_version'])
        else:
            raise ValueError('Unmapped window input: ' + target)
        relative = ('Lefony Emulator.app/Contents/Frameworks/' if platform.system() == 'Darwin' else '_internal/') + target
        if relative not in record['files'] and (window/relative).is_file():
            relative = (window/relative).resolve().relative_to(window.resolve()).as_posix()
        if relative not in record['files'] and platform.system() == 'Darwin':
            relative = 'Lefony Emulator.app/Contents/Resources/' + target
        if relative not in record['files']:
            raise ValueError('Native window input is absent from bundle: ' + target)
        files[relative] = dict(input_sha256=hashed, bundled_sha256=record['files'][relative], **provider)
    return dict(schema=1, system=record['system'], machine=record['machine'],
                window_manifest_sha256=digest(window/'window.json'),
                pyinstaller_version=importlib.metadata.version('pyinstaller'), files=files), dict(inputs=private)


def verify_sources(window, inputs, materials, qt_sources):
    window_record = verify(window)
    record = json.loads(inputs.read_text())
    if record['window_manifest_sha256'] != digest(window/'window.json') or not record['files']:
        raise ValueError('Window source inventory differs from bundle')
    for name, expected in QT_SOURCES.items():
        path = qt_sources/name
        if path.stat().st_size != expected['bytes'] or digest(path) != expected['sha256']:
            raise ValueError('Qt source archive differs from pinned upstream: ' + name)
    manifest = json.loads((materials/'manifest.json').read_text())
    components = {c['component']: c for c in manifest['components']}
    selected = {'pyinstaller'}
    if components['pyinstaller']['version'] != record['pyinstaller_version']:
        raise ValueError('Window bootloader source version differs')
    for name, item in record['files'].items():
        if window_record['files'].get(name) != item['bundled_sha256']:
            raise ValueError('Window native file differs from source inventory')
        if item['component'] == 'qt-pyside':
            if item['version'] != VERSION:
                raise ValueError('Qt input version differs')
        else:
            component = components[item['component']]
            if component['version'] != item['version']:
                raise ValueError('Window native source version differs: ' + item['component'])
            selected.add(item['component'])
    for name in selected:
        component = components[name]
        if not component.get('inputs'):
            raise ValueError('Missing window source inputs: ' + name)
        for entry in component['inputs'] + component.get('installed_notices', []):
            path = (materials/entry['file']).resolve()
            if not path.is_relative_to(materials.resolve()) or digest(path) != entry['sha256']:
                raise ValueError('Window corresponding source changed: ' + name)
    return dict(schema=1, qt_version=VERSION, native_files=len(record['files']),
                inputs_sha256=digest(inputs), qt_sources=QT_SOURCES,
                components=sorted(selected), corresponding_sources_verified=True,
                source_rebuild_qualified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toc', type=Path, required=True)
    parser.add_argument('--window', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    public, private = inventory(args.toc, args.window)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'inputs.json').write_text(json.dumps(public, indent=2)+'\n')
    (args.output/'debian-private.json').write_text(json.dumps(private, indent=2)+'\n')

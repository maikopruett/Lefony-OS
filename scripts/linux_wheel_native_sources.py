#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the Linux SDK's selected native wheel inputs to reviewed sources.

Collection reads wheel/source archives without executing or extracting their
code. Packaging records PyInstaller's actual inputs before removing its stage.
This is source correspondence, not a reproducible rebuild of upstream wheels.
"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
from urllib.parse import urlsplit
import zipfile

LOCK = Path(__file__).with_suffix('.json')
COMPONENT = 'linux-wheel-native'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scoped(root, name):
    if not isinstance(name, str):
        raise ValueError('Invalid wheel source path')
    path = PurePosixPath(name)
    if ('\\' in name or '\0' in name or path.is_absolute() or path.as_posix() != name
            or not path.parts or any(p in ('.', '..') for p in name.split('/'))):
        raise ValueError('Invalid wheel source path: ' + name)
    result = root.joinpath(*path.parts)
    if result.is_symlink() or not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Wheel source path escapes its root: ' + name)
    return result


def checksum(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid wheel/source checksum')


def load_lock(path=LOCK):
    lock = json.loads(path.read_text(encoding='utf-8'))
    if lock.get('schema') != 1 or lock.get('platform') != 'linux-x86_64':
        raise ValueError('Unsupported Linux wheel source lock')
    ids = set(); files = set()
    for source in lock['sources']:
        scoped(Path('.'), source['file']); checksum(source['sha256'])
        url = urlsplit(source['url'])
        if (not isinstance(source['id'], str) or not re.fullmatch('[a-z0-9][a-z0-9._+-]*', source['id'])
                or source['id'] in ids or source['file'] in files or url.scheme != 'https'
                or not url.hostname or url.username or url.password
                or not isinstance(source['bytes'], int) or not 0 < source['bytes'] <= 300 * 1024 * 1024):
            raise ValueError('Duplicate or invalid wheel source input')
        ids.add(source['id']); files.add(source['file'])
    if not ids or not lock['wheels']:
        raise ValueError('Empty Linux wheel source lock')
    binaries = set()
    for name, wheel in lock['wheels'].items():
        if not re.fullmatch('[a-z0-9][a-z0-9-]*', name) or not wheel['version']:
            raise ValueError('Invalid locked wheel identity')
        scoped(Path('.'), wheel['file']); checksum(wheel['sha256'])
        if not wheel['binaries'] or not wheel['metadata']:
            raise ValueError('Wheel lacks native inputs or license metadata')
        for file, record in wheel['binaries'].items():
            scoped(Path('.'), file); checksum(record['sha256'])
            if (file in binaries or not isinstance(record['source_ids'], list)
                    or not record['source_ids'] or not set(record['source_ids']) <= ids):
                raise ValueError('Unmapped or duplicate native wheel file: ' + file)
            binaries.add(file)
        for file, sha in wheel['metadata'].items():
            scoped(Path('.'), file); checksum(sha)
    return lock


def source_notices(path, source_id):
    """Deterministic top-level/project license notices; full archives also remain."""
    if not tarfile.is_tarfile(path):
        return
    with tarfile.open(path, 'r|*') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (not member.isfile() or len(name.parts) > 4 or member.size > 2 * 1024 * 1024
                    or not re.match(r'^(COPYING|COPYRIGHT|LICENSE|NOTICE|AUTHORS)([._-]|$)', name.name, re.I)):
                continue
            filename = hashlib.sha256(member.name.encode()).hexdigest()[:16] + '-' + name.name
            yield 'notices/sources/' + source_id + '/' + filename, archive.extractfile(member).read()


def metadata_inputs(lock, wheel_directory):
    for name, wheel in lock['wheels'].items():
        path = scoped(wheel_directory, wheel['file'])
        if digest(path) != wheel['sha256']:
            raise ValueError('Wheel archive differs from lock: ' + name)
        with zipfile.ZipFile(path) as archive:
            names = [info.filename for info in archive.infolist()]
            if len(names) != len(set(names)):
                raise ValueError('Duplicate wheel archive member')
            for file, record in wheel['binaries'].items():
                info = archive.getinfo(file)
                if info.file_size > 64 * 1024 * 1024 or hashlib.sha256(archive.read(info)).hexdigest() != record['sha256']:
                    raise ValueError('Native wheel file differs from lock: ' + file)
            for file, expected in wheel['metadata'].items():
                info = archive.getinfo(file)
                if info.file_size > 8 * 1024 * 1024:
                    raise ValueError('Wheel metadata exceeds bound')
                data = archive.read(info)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError('Wheel metadata differs from lock: ' + file)
                yield 'notices/wheels/' + name + '/' + file, data


def verify_inventory(inventory, bundle, lock):
    if inventory.get('status') != 'passed' or not inventory.get('inputs'):
        raise ValueError('A passing native-input inventory is required')
    seen = set(); result = {}
    for item in inventory['inputs']:
        origin = item['origin']
        if origin['kind'] == 'debian-package':
            continue
        name = origin.get('name', '').lower()
        if origin['kind'] != 'python-wheel' or name not in lock['wheels']:
            raise ValueError('Unmapped native wheel in frozen inventory')
        wheel = lock['wheels'][name]
        file = item['source'].partition('/site-packages/')[2]
        record = wheel['binaries'].get(file)
        if (record is None or origin['version'] != wheel['version']
                or origin['download']['archive_info']['hashes']['sha256'] != wheel['sha256']
                or item['source_sha256'] != record['sha256'] or (name, file) in seen
                or item['target'] in result):
            raise ValueError('Frozen wheel input differs from reviewed coverage: ' + item['target'])
        output = scoped(bundle, '_internal/' + item['target'])
        actual = digest(output)
        if actual != item['bundled_sha256']:
            raise ValueError('Frozen wheel output changed: ' + item['target'])
        with output.open('rb') as stream:
            header = stream.read(20)
        if header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 62:
            raise ValueError('Frozen native wheel input is not ELF64 x86-64')
        seen.add((name, file))
        result[item['target']] = {'wheel': name, 'wheel_file': file,
            'input_sha256': record['sha256'], 'bundled_sha256': actual, 'source_ids': record['source_ids']}
    required = {(name, file) for name, wheel in lock['wheels'].items() for file in wheel['binaries']}
    if seen != required:
        raise ValueError('Incomplete frozen native wheel inventory')
    return result


def collect(output, wheel_directory, inventory_path, bundle, *, caches=(), offline=False, lock_path=LOCK):
    lock = load_lock(lock_path)
    inventory = json.loads(inventory_path.read_text())
    verified = verify_inventory(inventory, bundle, lock)
    if output.exists():
        raise ValueError('Output exists; retain it and choose a new directory')
    output.mkdir(parents=True); folder = output / COMPONENT; folder.mkdir()
    component = {'component': COMPONENT, 'version': '1', 'source_lock_sha256': digest(lock_path), 'inputs': []}
    manifest = {'schema': 1, 'platform': 'linux-x86_64', 'status': 'collecting',
        'components': [component], 'complete_desktop_sources': False,
        'scope': 'Reviewed native wheel inputs only; system libraries and built tools remain separate',
        'inventory_sha256': digest(inventory_path), 'wheel_rebuild_qualified': False}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def write(file, data, role):
        target = scoped(folder, file); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        component['inputs'].append({'file': str(target.relative_to(output)), 'sha256': digest(target), 'role': role})
    save()
    try:
        write('source-lock.json', lock_path.read_bytes(), 'source-lock')
        for file, data in metadata_inputs(lock, wheel_directory):
            write(file, data, 'upstream-wheel-metadata')
        for source in lock['sources']:
            target = scoped(folder, source['file']); target.parent.mkdir(parents=True, exist_ok=True)
            cached = next((scoped(cache, source['file']) for cache in caches if scoped(cache, source['file']).is_file()), None)
            if cached is not None:
                if digest(cached) != source['sha256']:
                    raise ValueError('Cached source differs from lock: ' + source['file'])
                shutil.copyfile(cached, target)
            elif offline:
                raise ValueError('Offline source input missing: ' + source['file'])
            else:
                from collect_native_desktop_sources import download
                download(source['url'], target, source['sha256'])
            if target.stat().st_size != source['bytes'] or digest(target) != source['sha256']:
                raise ValueError('Source differs from reviewed input: ' + source['file'])
            component['inputs'].append({**source, 'file': str(target.relative_to(output))})
            for file, data in source_notices(target, source['id']):
                write(file, data, 'source-notice')
            save(); print('Verified ' + source['id'], flush=True)
        (output / 'native-inputs.json').write_text(json.dumps(verified, indent=2) + '\n')
        manifest['status'] = 'collected'; save()
    except BaseException as error:
        manifest.update(status='failed', error=str(error)); save(); raise


def verify_materials(materials, manifest, *, lock_path=LOCK):
    lock = load_lock(lock_path)
    if manifest.get('platform') != 'linux-x86_64' or manifest.get('status') != 'collected':
        raise ValueError('Completed Linux source collection is required')
    selected = [c for c in manifest['components'] if c['component'] == COMPONENT]
    if len(selected) != 1 or selected[0].get('source_lock_sha256') != digest(lock_path):
        raise ValueError('Matching Linux native wheel sources are required')
    expected = {COMPONENT + '/source-lock.json': digest(lock_path)}
    for name, wheel in lock['wheels'].items():
        for file, sha in wheel['metadata'].items():
            expected[COMPONENT + '/notices/wheels/' + name + '/' + file] = sha
    for source in lock['sources']:
        file = COMPONENT + '/' + source['file']; path = scoped(materials, file)
        if path.stat().st_size != source['bytes'] or digest(path) != source['sha256']:
            raise ValueError('Native wheel source archive changed: ' + file)
        expected[file] = source['sha256']
        for file, data in source_notices(path, source['id']):
            expected[COMPONENT + '/' + file] = hashlib.sha256(data).hexdigest()
    supplied = {}
    for item in selected[0]['inputs']:
        if item['file'] in supplied:
            raise ValueError('Duplicate Linux wheel source input')
        supplied[item['file']] = item['sha256']
        if digest(scoped(materials, item['file'])) != item['sha256']:
            raise ValueError('Linux wheel source material changed: ' + item['file'])
    if supplied != expected:
        raise ValueError('Incomplete or unrecognized Linux wheel sources/notices')
    actual = {p.relative_to(materials).as_posix() for p in (materials / COMPONENT).rglob('*')
              if p.is_file() or p.is_symlink()}
    if actual != set(supplied):
        raise ValueError('Unlisted file in Linux wheel source materials')
    return lock


def verify_installation(lock):
    roots = {}
    for name, wheel in lock['wheels'].items():
        distribution = importlib.metadata.distribution(name)
        if distribution.version != wheel['version']:
            raise ValueError('Installed wheel version differs from source lock: ' + name)
        root = Path(distribution.locate_file('')).resolve(); roots[name] = root
        for file, record in wheel['binaries'].items():
            if digest(scoped(root, file)) != record['sha256']:
                raise ValueError('Installed wheel binary differs from source lock: ' + file)
    return roots


def record_bundle(toc, bundle, lock):
    verify_installation(lock)
    if toc.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('PyInstaller input table exceeds bound')
    table = ast.literal_eval(toc.read_text())
    installed = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name'].lower().replace('_', '-')
        for entry in distribution.files or []:
            if '.so' in PurePosixPath(str(entry)).name:
                installed[Path(distribution.locate_file(entry)).resolve()] = (name, str(entry))
    records = {}; seen = set()
    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if len(value) == 3 and all(isinstance(x, str) for x in value) and value[2] in ('BINARY', 'EXTENSION'):
            target, source, kind = value; source = Path(source).resolve()
            if source not in installed:
                return
            name, file = installed[source]
            if name not in lock['wheels']:
                raise ValueError('Unmapped native wheel in packaging inputs: ' + name)
            record = lock['wheels'][name]['binaries'].get(file)
            if record is None or digest(source) != record['sha256']:
                raise ValueError('Unmapped or changed native wheel input: ' + file)
            output = scoped(bundle, '_internal/' + target)
            result = {'wheel': name, 'wheel_file': file, 'input_sha256': digest(source),
                      'bundled_sha256': digest(output), 'source_ids': record['source_ids']}
            if target in records and records[target] != result:
                raise ValueError('Conflicting native wheel target')
            records[target] = result; seen.add((name, file))
        else:
            for item in value:
                visit(item)
    visit(table)
    expected = {(name, file) for name, wheel in lock['wheels'].items() for file in wheel['binaries']}
    if seen != expected:
        raise ValueError('Packaged native wheel inputs differ from reviewed coverage')
    actual = set()
    for wheel in lock['wheels'].values():
        for file in wheel['binaries']:
            parts = PurePosixPath(file).parts
            if len(parts) > 1:
                candidates = scoped(bundle, '_internal/' + parts[0]).rglob('*')
            else:
                candidates = (bundle / '_internal').glob(parts[0].split('.', 1)[0] + '*.so')
            for path in candidates:
                if path.is_file() and not path.is_symlink() and '.so' in path.name:
                    actual.add(path.relative_to(bundle / '_internal').as_posix())
    if not actual <= records.keys():
        raise ValueError('Unmapped native wheel output in bundle')
    return {'schema': 1, 'platform': 'linux-x86_64', 'files': records, 'wheel_rebuild_qualified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheel-directory', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--source-cache', type=Path, action='append', default=[])
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--lock', type=Path, default=LOCK)
    args = parser.parse_args()
    collect(args.output, args.wheel_directory, args.inventory, args.bundle,
            caches=args.source_cache, offline=args.offline, lock_path=args.lock)

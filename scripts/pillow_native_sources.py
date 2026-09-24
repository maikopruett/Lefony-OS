# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind the selected macOS Pillow wheel to native sources and PyInstaller inputs.

Source archives are retained without executing or extracting their build scripts.
This records source correspondence, not a reproducible rebuild of upstream wheels.
Other Python/platform wheels require their own reviewed input lock.
"""
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil

LOCK = Path(__file__).with_suffix('.json')
COMPONENT = 'pillow-native'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scoped(root, name):
    if not isinstance(name, str):
        raise ValueError('Invalid Pillow source path: ' + str(name))
    parts = PurePosixPath(name)
    if ('\\' in name or parts.is_absolute() or parts.as_posix() != name
            or not parts.parts or any(p in ('.', '..') for p in name.split('/'))):
        raise ValueError('Invalid Pillow source path: ' + str(name))
    path = root.joinpath(*parts.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Pillow source path escapes its root: ' + name)
    return path


def supported_host():
    return platform.system() == 'Darwin' and platform.machine() == 'arm64'


def load_lock(path=LOCK):
    lock = json.loads(path.read_text(encoding='utf-8'))
    if lock.get('schema') != 1 or lock.get('platform') != 'darwin-arm64':
        raise ValueError('Unsupported Pillow native source lock')
    names = set()
    for item in lock['sources']:
        scoped(Path('.'), item['file'])
        if item['file'] in names or not item['url'].startswith('https://'):
            raise ValueError('Duplicate source or non-HTTPS Pillow source URL')
        names.add(item['file'])
        if not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid Pillow source checksum')
    for name, sha in lock['installed_files'].items():
        scoped(Path('.'), name)
        if not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Invalid Pillow installed checksum')
    source_ids = {item['id'] for item in lock['sources']}
    for name, sources in lock['binaries'].items():
        if name not in lock['installed_files'] or not sources or not set(sources) <= source_ids:
            raise ValueError('Unmapped Pillow native source: ' + name)
    return lock


def installed_root():
    return Path(importlib.metadata.distribution('pillow').locate_file('')).resolve()


def verify_installation(lock, root=None):
    root = installed_root() if root is None else root
    for name, sha in lock['installed_files'].items():
        path = scoped(root, name)
        if not path.is_file() or digest(path) != sha:
            raise ValueError('Installed Pillow differs from the reviewed wheel: ' + name)
    native = {p.relative_to(root).as_posix() for p in (root/'PIL').rglob('*')
              if p.is_file() and p.suffix in ('.so', '.dylib')}
    if not native <= lock['installed_files'].keys():
        raise ValueError('Installed Pillow has unrecognized native files')
    return root


def collect(output, download, *, lock_path=LOCK, root=None):
    lock = load_lock(lock_path)
    root = verify_installation(lock, root)
    folder = scoped(output, COMPONENT)
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for item in lock['sources']:
        path = scoped(folder, item['file'])
        path.parent.mkdir(parents=True, exist_ok=True)
        download(item['url'], path, item['sha256'])
        if digest(path) != item['sha256']:
            raise ValueError('Pillow source differs from the reviewed input: ' + item['file'])
        entries.append({**item, 'file': path.relative_to(output).as_posix()})
    copied_lock = folder/'source-lock.json'
    shutil.copyfile(lock_path, copied_lock)
    entries.append({'file': copied_lock.relative_to(output).as_posix(),
                    'sha256': digest(copied_lock), 'role': 'source-lock'})
    for name in lock['metadata_files']:
        source = scoped(root, name)
        target = folder/'notices'/PurePosixPath(name).name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        entries.append({'file': target.relative_to(output).as_posix(),
                        'sha256': digest(target), 'role': 'upstream-wheel-metadata'})
    return {'component': COMPONENT, 'version': lock['pillow_version'],
            'wheel_sha256': lock['wheel']['sha256'], 'source_lock_sha256': digest(lock_path),
            'inputs': entries, 'wheel_rebuild_qualified': False}


def verify_materials(materials, manifest, *, lock_path=LOCK):
    lock = load_lock(lock_path)
    records = [item for item in manifest['components'] if item['component'] == COMPONENT]
    if len(records) != 1 or records[0].get('source_lock_sha256') != digest(lock_path):
        raise ValueError('Matching Pillow native sources are required; refresh the source materials')
    record = records[0]
    if record.get('version') != lock['pillow_version'] or record.get('wheel_sha256') != lock['wheel']['sha256']:
        raise ValueError('Pillow wheel/source version mismatch')
    required = {COMPONENT+'/'+item['file']: item['sha256'] for item in lock['sources']}
    required[COMPONENT+'/source-lock.json'] = digest(lock_path)
    for name in lock['metadata_files']:
        required[COMPONENT+'/notices/'+PurePosixPath(name).name] = lock['installed_files'][name]
    supplied = {}
    for item in record['inputs']:
        if item['file'] in supplied:
            raise ValueError('Duplicate Pillow source input')
        supplied[item['file']] = item['sha256']
        path = scoped(materials, item['file'])
        if not path.is_file() or digest(path) != item['sha256']:
            raise ValueError('Pillow source material changed: ' + item['file'])
    if supplied != required:
        raise ValueError('Incomplete or unrecognized Pillow source inputs')
    return lock


def record_bundle(toc, bundle, lock, *, root=None):
    """Use PyInstaller's actual input table, before its temporary stage is removed."""
    root = verify_installation(lock, root)
    if toc.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('PyInstaller input table exceeds bound')
    table = ast.literal_eval(toc.read_text(encoding='utf-8'))
    entries = []

    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if len(value) == 3 and all(isinstance(x, str) for x in value) and value[2] in ('BINARY', 'EXTENSION'):
            entries.append(value)
        else:
            for child in value:
                visit(child)

    visit(table)
    records = {}
    for target, source, kind in entries:
        original = Path(source).resolve()
        if not original.is_relative_to(root/'PIL'):
            continue
        name = original.relative_to(root).as_posix()
        if name not in lock['binaries'] or digest(original) != lock['installed_files'][name]:
            raise ValueError('Unmapped or changed Pillow binary input: ' + name)
        output = scoped(bundle, '_internal/'+target)
        if not output.is_file():
            raise ValueError('Missing packaged Pillow binary: ' + target)
        key = output.relative_to(bundle).as_posix()
        record = {'wheel_file': name, 'input_sha256': digest(original),
                  'bundled_sha256': digest(output), 'source_ids': lock['binaries'][name]}
        if key in records and records[key] != record:
            raise ValueError('Ambiguous packaged Pillow binary: ' + key)
        records[key] = record
    actual = {p.relative_to(bundle).as_posix() for p in (bundle/'_internal/PIL').rglob('*')
              if p.is_file() and not p.is_symlink() and p.suffix in ('.so', '.dylib')}
    if set(records) != actual or {x['wheel_file'] for x in records.values()} != set(lock['binaries']):
        raise ValueError('Pillow bundled native inventory differs from the reviewed source coverage')
    return {'schema': 1, 'platform': lock['platform'], 'pillow_version': lock['pillow_version'],
            'wheel_sha256': lock['wheel']['sha256'], 'files': records,
            'wheel_rebuild_qualified': False}


def wheel_libraries(bundle):
    """Identify only verified wheel outputs before mapping other dylibs to Homebrew."""
    path = bundle/'pillow-native-inputs.json'
    candidate = json.loads((bundle/'candidate.json').read_text(encoding='utf-8'))
    if not path.is_file() or digest(path) != candidate.get('pillow_native_inputs_sha256'):
        raise ValueError('Pillow native inventory missing or changed; rebuild with the current packager')
    report = json.loads(path.read_text(encoding='utf-8'))
    lock = load_lock()
    if report.get('wheel_sha256') != lock['wheel']['sha256'] or not report.get('files'):
        raise ValueError('Unrecognized Pillow wheel in desktop inventory')
    if {item['wheel_file'] for item in report['files'].values()} != set(lock['binaries']):
        raise ValueError('Incomplete Pillow native inventory')
    result = set()
    for name, item in report['files'].items():
        path = scoped(bundle, name)
        source = item['wheel_file']
        if (source not in lock['binaries'] or item['input_sha256'] != lock['installed_files'][source]
                or item['source_ids'] != lock['binaries'][source] or digest(path) != item['bundled_sha256']):
            raise ValueError('Changed Pillow native inventory: ' + name)
        result.add(path.resolve())
    return result

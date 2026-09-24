#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect the reviewed full Windows CPython runtime and corresponding sources.

This does not execute Windows binaries or rebuild upstream releases. Reviewed
archive hashes are enforced; retained Sigstore bundles can be verified separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import sys
import tarfile
from urllib.parse import urlsplit
import zipfile

from windows_python_sources import copy_archive, digest, relative, source_file, source_notices

LOCK = Path(__file__).with_suffix('.json')
COMPONENT = 'windows-cpython'
MAX_ARCHIVE = 128 * 1024**2
MAX_EXPANDED = 512 * 1024**2
NATIVE_SUFFIXES = ('.exe', '.dll', '.pyd')


def load_lock(path=LOCK):
    lock = json.loads(path.read_text(encoding='utf-8'))
    if (lock.get('schema') != 1 or lock.get('platform') != 'windows-AMD64'
            or lock.get('python_full_version') != '3.14.7'
            or lock.get('release_id') != 'pythoncore-3.14-64'):
        raise ValueError('Require the reviewed full Windows CPython 3.14.7 x64 runtime')
    names = set()
    for item in [*lock['artifacts'], *lock['sources']]:
        relative(item['file']); url = urlsplit(item['url'])
        if (len(Path(item['file']).parts) != 1 or item['file'].casefold() in names
                or url.scheme != 'https' or not url.hostname or url.username or url.password
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])
                or type(item['bytes']) is not int or not 0 < item['bytes'] <= MAX_ARCHIVE):
            raise ValueError('Invalid Windows CPython archive input')
        names.add(item['file'].casefold())
    for role in ('runtime', 'source'):
        if len([a for a in lock['artifacts'] if a['role'] == role]) != 1:
            raise ValueError('Require one CPython runtime and source archive')
    ids = [s['id'] for s in lock['sources']]
    if len(ids) != len(set(ids)):
        raise ValueError('Repeated CPython dependency source')
    allowed = set(ids) | {'cpython', 'microsoft-vc-runtime'}
    if not lock['native_files'] or not lock['notice_files']:
        raise ValueError('Missing CPython runtime inventory')
    for name, item in lock['native_files'].items():
        relative(name)
        if (not name.lower().endswith(NATIVE_SUFFIXES) or not item['sources']
                or not set(item['sources']) <= allowed
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])
                or item['machine'] not in (0x14c, 0x8664, 0xaa64)):
            raise ValueError('Invalid CPython native source mapping')
        if not name.startswith('Lib/site-packages/') and item['machine'] != 0x8664:
            raise ValueError('Core CPython binaries must be x86-64')
    return lock


def zip_entries(archive):
    """Bound extraction and reject Windows aliases, links and duplicate entries."""
    entries = {}; kinds = {}; expanded = 0
    for index, member in enumerate(archive.infolist()):
        if index >= 100000:
            raise ValueError('CPython ZIP has too many entries')
        name = member.filename.rstrip('/') if member.is_dir() else member.filename
        parts = relative(name).parts
        for part in parts:
            if (part.endswith((' ', '.')) or any(ord(c) < 32 or c in '<>"|?*' for c in part)
                    or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
                raise ValueError('Unsafe Windows ZIP name: ' + name)
        mode = member.external_attr >> 16
        if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or member.flag_bits & 1:
            raise ValueError('Linked, special or encrypted CPython ZIP entry')
        key = name.casefold()
        if key in entries:
            raise ValueError('Duplicate or case-colliding CPython ZIP entry')
        entries[key] = member
        for i in range(1, len(parts)):
            parent = '/'.join(parts[:i]).casefold()
            if kinds.get(parent) == 'file':
                raise ValueError('CPython ZIP file used as a directory')
            kinds[parent] = 'dir'
        kind = 'dir' if member.is_dir() else 'file'
        if key in kinds and kinds[key] != kind:
            raise ValueError('CPython ZIP file/directory collision')
        kinds[key] = kind
        expanded += member.file_size
        if member.file_size > 128*1024**2 or expanded > MAX_EXPANDED:
            raise ValueError('CPython ZIP exceeds expanded size bound')
    return [m for m in entries.values() if not m.is_dir()]


def inspect_runtime(path, lock, destination=None):
    item = next(a for a in lock['artifacts'] if a['role'] == 'runtime')
    if path.is_symlink() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
        raise ValueError('CPython runtime differs from the reviewed archive')
    files = {}; native = {}; notices = {}
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(path) as archive:
        members = zip_entries(archive)
        for member in members:
            name = member.filename; data = archive.read(member)
            sha = hashlib.sha256(data).hexdigest(); files[name] = sha
            if name.lower().endswith(NATIVE_SUFFIXES):
                if len(data) < 64 or data[:2] != b'MZ':
                    raise ValueError('Invalid CPython PE file')
                offset = struct.unpack_from('<I', data, 0x3c)[0]
                if offset + 6 > len(data) or data[offset:offset+4] != b'PE\0\0':
                    raise ValueError('Invalid CPython PE header')
                expected = lock['native_files'].get(name, {})
                actual = {'sha256':sha, 'bytes':len(data),
                          'machine':struct.unpack_from('<H',data,offset+4)[0],
                          'sources':expected.get('sources')}
                native[name] = actual
            if name in lock['notice_files']:
                notices[name] = sha
            if destination is not None:
                target = destination/name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    if native != lock['native_files'] or notices != lock['notice_files']:
        raise ValueError('CPython native files or notices differ from the reviewed inventory')
    return files


def collect_notices(archive, destination, extra=()):
    if archive.suffix.lower() != '.zip':
        records = source_notices(archive, destination)
        if extra:
            with tarfile.open(archive) as source:
                for name in extra:
                    relative(name); member = source.getmember(name)
                    if not member.isfile() or member.size > 4*1024**2:
                        raise ValueError('Invalid supplemental CPython source notice')
                    data = source.extractfile(member).read(); target = destination/name
                    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
                    records[name] = hashlib.sha256(data).hexdigest()
        return records
    records = {}; total = 0
    with zipfile.ZipFile(archive) as source:
        for member in zip_entries(source):
            if not Path(member.filename).name.upper().startswith(('LICENSE','COPYING','COPYRIGHT','NOTICE','PATENTS')):
                continue
            total += member.file_size
            if member.file_size > 4*1024**2 or total > 32*1024**2:
                raise ValueError('CPython source notices exceed bounds')
            data = source.read(member); target = destination/member.filename
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
            records[member.filename] = hashlib.sha256(data).hexdigest()
    return records


def validate_release(metadata, lock):
    name = 'windows-'+lock['python_full_version']+'.json'
    manifest = json.loads((metadata/name).read_text(encoding='utf-8'))
    rows = [r for r in manifest['versions'] if r['id'] == lock['release_id']]
    runtime = next(a for a in lock['artifacts'] if a['role'] == 'runtime')
    if (len(rows) != 1 or rows[0]['sort-version'] != lock['python_full_version']
            or rows[0]['url'] != runtime['url'] or rows[0]['hash']['sha256'] != runtime['sha256']):
        raise ValueError('CPython runtime is not bound by the reviewed release manifest')
    sbom = json.loads((metadata/(runtime['file']+'.spdx.json')).read_text(encoding='utf-8'))
    for item in lock['sources']:
        matches = [p for p in sbom['packages'] if p.get('downloadLocation') == item['sbom_reference']['url']
                   and p.get('versionInfo') == item['version']]
        if len(matches) != 1 or {'algorithm':'SHA256','checksumValue':item['sbom_reference']['sha256']} not in matches[0].get('checksums',[]):
            raise ValueError('CPython source differs from SBOM reference: '+item['id'])


def collect(output, *, lock_path=LOCK, cache=None):
    lock = load_lock(lock_path); output.mkdir(parents=True, exist_ok=False)
    folder = output/COMPONENT; folder.mkdir(); metadata = folder/'metadata'; metadata.mkdir()
    sources = folder/'sources'; sources.mkdir(); inputs = []
    manifest = {'schema':1,'platform':lock['platform'],'status':'collecting','components':[],
                'native_execution_qualified':False,'upstream_rebuild_qualified':False,
                'complete_desktop_sources':False,'scope':lock['scope']}
    def save():
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for item in lock['artifacts']:
            parent = output if item['role'] == 'runtime' else sources if item['role'] == 'source' else metadata
            target = parent/item['file']; copy_archive(item,target,cache)
            if item['role'] != 'runtime':
                inputs.append({'file':target.relative_to(output).as_posix(),'sha256':digest(target),'url':item['url']})
            if item['role'] == 'source':
                collect_notices(target,folder/'notices/cpython-source')
        validate_release(metadata, lock)
        runtime = next(a for a in lock['artifacts'] if a['role'] == 'runtime')
        runtime_files = inspect_runtime(output/runtime['file'],lock,output/'runtime')
        for name in lock['notice_files']:
            target = folder/'notices/runtime'/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output/'runtime'/name,target)
        for item in lock['sources']:
            target = sources/item['file']; copy_archive(item,target,cache)
            collect_notices(target,folder/'notices'/item['id'],item.get('extra_notice_members',()))
            inputs.append({'file':target.relative_to(output).as_posix(),'sha256':digest(target),'url':item['url']})
            print('Collected CPython source '+item['id'],flush=True)
        for source in (lock_path, Path(__file__), Path(__file__).with_name('windows_python_sources.py')):
            name = 'windows_cpython_sources.json' if source == lock_path else source.name
            shutil.copyfile(source,folder/name)
            inputs.append({'file':COMPONENT+'/'+name,'sha256':digest(source)})
        component = {'component':COMPONENT,'version':lock['python_full_version'],'inputs':inputs,
                     'native_files':lock['native_files'],'microsoft_runtime':lock['microsoft_runtime'],
                     'files':{p.relative_to(output).as_posix():digest(p) for p in sorted(folder.rglob('*')) if p.is_file()}}
        manifest.update(status='collected',components=[component],runtime=runtime,
                        runtime_files=runtime_files,source_lock_sha256=digest(lock_path))
        verify_materials(output,manifest,lock_path=lock_path)
        save()
    except BaseException as exc:
        manifest.update(status='failed',error=str(exc)); save(); raise
    return manifest


def verify_materials(materials, manifest, *, lock_path=LOCK):
    lock = load_lock(lock_path)
    components = [c for c in manifest['components'] if c['component'] == COMPONENT]
    if manifest.get('platform') != lock['platform'] or len(components) != 1:
        raise ValueError('Missing or repeated Windows CPython source component')
    component = components[0]; folder = source_file(materials,COMPONENT)
    if (component.get('version') != lock['python_full_version'] or component.get('native_files') != lock['native_files']
            or component.get('microsoft_runtime') != lock['microsoft_runtime']):
        raise ValueError('Windows CPython source identity differs')
    files = component.get('files',{})
    if any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Linked Windows CPython source material')
    actual = {p.relative_to(materials).as_posix() for p in folder.rglob('*') if p.is_file()}
    if not files or actual != files.keys():
        raise ValueError('Windows CPython material file set differs')
    for name, sha in files.items():
        if not name.startswith(COMPONENT+'/') or digest(source_file(materials,name)) != sha:
            raise ValueError('Windows CPython material changed: '+name)
    expected = {COMPONENT+'/windows_cpython_sources.json':digest(lock_path)}
    for item in [*lock['artifacts'], *lock['sources']]:
        role = item.get('role','source')
        if role != 'runtime':
            expected[COMPONENT+('/sources/' if role == 'source' else '/metadata/')+item['file']] = item['sha256']
    supplied = {i['file']:i['sha256'] for i in component['inputs']}
    recipes = {COMPONENT+'/'+n for n in ('windows_cpython_sources.py','windows_python_sources.py')}
    if (len(supplied) != len(component['inputs']) or supplied.keys() != expected.keys() | recipes
            or any(supplied[n] != sha for n,sha in expected.items())):
        raise ValueError('Windows CPython source inputs differ from lock')
    for name, sha in supplied.items():
        if digest(source_file(materials,name)) != sha:
            raise ValueError('Windows CPython source input changed')
    for name, sha in lock['notice_files'].items():
        if digest(source_file(materials,COMPONENT+'/notices/runtime/'+name)) != sha:
            raise ValueError('Original CPython license notice changed')
    for name, sha in lock['source_notice_files'].items():
        if digest(source_file(materials,COMPONENT+'/notices/'+name)) != sha:
            raise ValueError('CPython dependency notice changed: '+name)
    expected_files = supplied.keys() | {COMPONENT+'/notices/'+n for n in lock['source_notice_files']} | {COMPONENT+'/notices/runtime/'+n for n in lock['notice_files']}
    if files.keys() != expected_files:
        raise ValueError('Unreviewed CPython source material file set')
    validate_release(folder/'metadata',lock)
    return lock


def verify_installation(lock, runtime_archive, *, root=None):
    """An explicit root checks offline layout; native packaging checks base_prefix."""
    if root is None and (platform.system() != 'Windows' or platform.machine().lower() not in ('amd64','x86_64')
                         or platform.python_implementation() != 'CPython'
                         or platform.python_version() != lock['python_full_version']):
        raise ValueError('Require native Windows CPython '+lock['python_full_version']+' x86-64')
    root = Path(sys.base_prefix) if root is None else root
    files = inspect_runtime(runtime_archive,lock)
    selected = {n:h for n,h in files.items() if (n.startswith('Lib/') and not n.startswith('Lib/site-packages/'))
                or n in lock['native_files'] and not n.startswith('Lib/site-packages/') or n == 'LICENSE.txt'}
    for name, sha in selected.items():
        path = source_file(root,name)
        if not path.is_file() or digest(path) != sha:
            raise ValueError('Installed CPython input changed: '+name)
    native = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and p.suffix.lower() in NATIVE_SUFFIXES and not p.relative_to(root).as_posix().startswith('Lib/site-packages/')}
    expected = {n for n in lock['native_files'] if not n.startswith('Lib/site-packages/')}
    if native != expected:
        raise ValueError('Unreviewed installed CPython native binary')
    return {'schema':1,'platform':lock['platform'],'python_full_version':lock['python_full_version'],
            'runtime_sha256':next(a['sha256'] for a in lock['artifacts'] if a['role']=='runtime'),
            'checked_files':len(selected),'native_files':{n:lock['native_files'][n] for n in sorted(expected)},
            'native_execution_qualified':False,'upstream_rebuild_qualified':False}


def record_bundle(bundle, lock):
    """Require frozen CPython DLLs to retain their reviewed input identities."""
    from native_desktop_windows import native_files
    known = {Path(n).name.lower():(n,item) for n,item in lock['native_files'].items()
             if not n.startswith('Lib/site-packages/')}
    records = {}; internal = bundle/'_internal'
    for path in native_files(internal):
        if path.is_relative_to(internal/'runtime'):
            continue
        name = path.name.lower()
        if name in known:
            original, item = known[name]
            if digest(path) != item['sha256']:
                raise ValueError('Frozen CPython binary changed: '+name)
            records[path.relative_to(bundle).as_posix()] = {'original':original,**item}
    if '_internal/python314.dll' not in records:
        raise ValueError('Frozen bundle is missing the reviewed CPython core')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cache',type=Path,help='Flat cache of exact reviewed runtime, metadata and source archives')
    args = parser.parse_args()
    result = collect(args.output.resolve(),cache=args.cache.resolve() if args.cache else None)
    print(json.dumps({'status':result['status'],'runtime_files':len(result['runtime_files']),
                      'source_files':len(result['components'][0]['files']),'native_execution_qualified':False}))

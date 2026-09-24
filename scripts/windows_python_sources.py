#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect reviewed Windows Python wheels, sdists and embedded library sources.

Runs on any host without installing/importing Windows wheels or executing their
build scripts. Native CPython/tool sources and clean-host execution are separate.
"""
import argparse
import base64
import csv
from email.parser import BytesParser
import email.policy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
from urllib.parse import urlsplit
from urllib.request import urlopen
import zipfile

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.tags import cpython_tags, compatible_tags
from packaging.version import Version

LOCK = Path(__file__).with_suffix('.json')
MAX_ARCHIVE = 64 * 1024**2
MAX_EXPANDED = 256 * 1024**2


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def relative(name):
    p = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or p.is_absolute() or
            p.as_posix() != name or any(x in ('', '.', '..') for x in name.split('/'))):
        raise ValueError('Unsafe Windows Python input path: ' + name)
    return p


def source_file(root, name):
    p = relative(name)
    result = root.joinpath(*p.parts)
    if (any(root.joinpath(*p.parts[:i]).is_symlink() for i in range(len(p.parts)+1))
            or not result.resolve().is_relative_to(root.resolve())):
        raise ValueError('Windows Python input escapes its root: ' + name)
    return result


def dependency_closure(lock):
    environment = lock['environment']
    expected = {'implementation_name':'cpython', 'implementation_version':'3.14.7',
                'os_name':'nt', 'platform_machine':'AMD64', 'platform_release':'10',
                'platform_system':'Windows', 'platform_version':'10.0',
                'python_full_version':'3.14.7', 'platform_python_implementation':'CPython',
                'python_version':'3.14', 'sys_platform':'win32', 'extra':''}
    if environment != expected:
        raise ValueError('Require the reviewed Windows CPython marker environment')
    distributions = {d['name']:d for d in lock['distributions']}
    if len(distributions) != len(lock['distributions']):
        raise ValueError('Repeated Windows Python distribution')
    pending = list(lock['requested']); seen = set()
    while pending:
        req = Requirement(pending.pop())
        if req.marker and not req.marker.evaluate(environment):
            continue
        name = canonicalize_name(req.name)
        if req.url or req.extras or name not in distributions:
            raise ValueError('Unmapped Windows Python dependency: ' + str(req))
        item = distributions[name]
        if Version(item['version']) not in req.specifier:
            raise ValueError('Windows Python dependency version conflict: ' + name)
        if name not in seen:
            seen.add(name); pending.extend(item['requires_dist'])
    if seen != distributions.keys():
        raise ValueError('Windows lock contains unrelated distributions')


def load_lock(path=LOCK):
    lock = json.loads(path.read_text(encoding='utf-8'))
    if lock.get('schema') != 1 or lock.get('platform') != 'windows-AMD64':
        raise ValueError('Unsupported Windows Python source lock')
    dependency_closure(lock)
    source_ids = {s['id'] for s in lock['sources']}
    if len(source_ids) != len(lock['sources']):
        raise ValueError('Repeated Windows embedded source id')
    names = set()
    for item in [*lock['sources'], *(d[k] for d in lock['distributions'] for k in ('wheel','sdist'))]:
        relative(item['file']); parsed = urlsplit(item['url'])
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or item['file'] in names or not re.fullmatch('[0-9a-f]{64}', item['sha256'])
                or type(item['bytes']) is not int or not 0 < item['bytes'] <= MAX_ARCHIVE):
            raise ValueError('Invalid or duplicate Windows Python archive input')
        names.add(item['file'])
    for d in lock['distributions']:
        if canonicalize_name(d['name']) != d['name'] or not d['notice_files']:
            raise ValueError('Invalid Windows Python distribution/notices')
        for name, ids in d['native_sources'].items():
            if name not in d['native_files'] or not ids or not set(ids) <= source_ids | {d['name']+'-sdist'}:
                raise ValueError('Unmapped Windows wheel native sources')
        if d['native_sources'].keys() != d['native_files'].keys():
            raise ValueError('Incomplete Windows wheel native source mapping')
    return lock


def inspect_wheel(path, item):
    if path.is_symlink() or path.stat().st_size != item['wheel']['bytes'] or digest(path) != item['wheel']['sha256']:
        raise ValueError('Windows wheel differs from its reviewed input')
    tags = set(cpython_tags((3,14), abis=['cp314'], platforms=['win_amd64']))
    tags.update(compatible_tags((3,14), interpreter='cp314', platforms=['win_amd64']))
    name, version, _, wheel_tags = parse_wheel_filename(item['wheel']['file'])
    if name != item['name'] or str(version) != item['version'] or not wheel_tags & tags:
        raise ValueError('Incompatible Windows wheel identity or ABI')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 20000 or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise ValueError('Windows wheel exceeds extraction bounds')
        files = {}; folded = set()
        for entry in entries:
            name = entry.filename.rstrip('/')
            relative(name)
            if (name.casefold() in folded or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1):
                raise ValueError('Duplicate, linked or encrypted wheel member')
            folded.add(name.casefold())
            if not entry.is_dir():
                files[name] = archive.read(entry)
        info = item['metadata_file']
        if info not in files or hashlib.sha256(files[info]).hexdigest() != item['metadata_sha256']:
            raise ValueError('Windows wheel metadata differs from its lock')
        metadata = BytesParser(policy=email.policy.default).parsebytes(files[info])
        if (canonicalize_name(metadata['Name']) != item['name'] or metadata['Version'] != item['version']
                or metadata.get_all('Requires-Dist', []) != item['requires_dist']
                or Version('3.14.7') not in SpecifierSet(metadata.get('Requires-Python',''))):
            raise ValueError('Windows wheel requirements differ from lock')
        record = str(PurePosixPath(info).parent/'RECORD')
        indexed = {}
        for name, checksum, size in csv.reader(io.StringIO(files[record].decode())):
            relative(name)
            if name in indexed or name not in files:
                raise ValueError('Duplicate or missing wheel RECORD member')
            indexed[name] = checksum
            if name == record:
                if checksum or size:raise ValueError('Wheel RECORD self-hash must be empty')
            elif (checksum != 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(files[name]).digest()).rstrip(b'=').decode()
                  or size != str(len(files[name]))):
                raise ValueError('Windows wheel RECORD checksum differs: ' + name)
        if indexed.keys() != files.keys():
            raise ValueError('Windows wheel has unrecorded members')
        actual_native = {n:hashlib.sha256(b).hexdigest() for n,b in files.items() if n.lower().endswith(('.exe','.dll','.pyd'))}
        if actual_native != item['native_files']:
            raise ValueError('Windows wheel native file set differs')
        for name, sha in {**item['metadata_files'], **item['notice_files']}.items():
            if name not in files or hashlib.sha256(files[name]).hexdigest() != sha:
                raise ValueError('Windows wheel metadata/license changed: '+name)
        return files


def copy_archive(item, destination, cache=None):
    cached = cache/item['file'] if cache else None
    if cached is not None and cached.is_file():
        if cached.is_symlink() or cached.stat().st_size != item['bytes'] or digest(cached) != item['sha256']:
            raise ValueError('Changed cached Windows Python archive: '+item['file'])
        shutil.copyfile(cached, destination)
    else:
        with urlopen(item['url'], timeout=45) as response, destination.open('xb') as output:
            remaining = item['bytes']
            while remaining:
                data = response.read(min(1024**2, remaining))
                if not data:raise ValueError('Truncated Windows Python archive')
                output.write(data);remaining -= len(data)
            if response.read(1):raise ValueError('Windows Python archive exceeds recorded size')
    if destination.stat().st_size != item['bytes'] or digest(destination) != item['sha256']:
        raise ValueError('Windows Python archive checksum differs: '+item['file'])


def source_notices(archive, destination):
    records = {}; total = 0
    with tarfile.open(archive) as source:
        for count, member in enumerate(source):
            if count >= 100000:raise ValueError('Source archive has too many members')
            if not member.isfile() or not Path(member.name).name.upper().startswith(('LICENSE','COPYING','COPYRIGHT','NOTICE','PATENTS')):
                continue
            name = member.name.removeprefix('./')
            relative(name)
            total += member.size
            if member.size > 4*1024**2 or total > 32*1024**2:
                raise ValueError('Source notices exceed bounds')
            path = destination/name;path.parent.mkdir(parents=True,exist_ok=True)
            data = source.extractfile(member).read()
            if path.exists():raise ValueError('Repeated source notice')
            path.write_bytes(data);records[name] = hashlib.sha256(data).hexdigest()
    return records


def collect(output, *, lock_path=LOCK, cache=None):
    lock = load_lock(lock_path)
    output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(lock_path,output/'windows_python_sources.json')
    shutil.copyfile(Path(__file__),output/Path(__file__).name)
    manifest = {'schema':1,'platform':'windows-AMD64','status':'collecting','components':[],
                'complete_desktop_sources':False,'wheel_rebuild_qualified':False,
                'native_execution_qualified':False,'source_lock_sha256':digest(lock_path),
                'scope':lock['scope'],'recipe_sha256':digest(Path(__file__))}
    def save():(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        wheels=output/'wheels';wheels.mkdir()
        for item in lock['distributions']:
            folder=output/item['name'];folder.mkdir();notices=folder/'notices';notices.mkdir()
            wheel=wheels/item['wheel']['file'];copy_archive(item['wheel'],wheel,cache)
            contents=inspect_wheel(wheel,item)
            sdist=folder/item['sdist']['file'];copy_archive(item['sdist'],sdist,cache)
            source_notices(sdist,notices/'source')
            for name in item['metadata_files']:
                target=folder/'wheel-metadata'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(contents[name])
            for name in item['notice_files']:
                target=notices/'wheel'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(contents[name])
            manifest['components'].append({'component':item['name'],'version':item['version'],
                'inputs':[{'file':sdist.relative_to(output).as_posix(),'url':item['sdist']['url'],'sha256':digest(sdist)}],
                'wheel':item['wheel'],'native_files':item['native_files'],'native_sources':item['native_sources']})
            save()
            print('Collected '+item['name']+'='+item['version'],flush=True)
        folder=output/'windows-python-native';folder.mkdir();inputs=[]
        for item in lock['sources']:
            target=folder/item['file'];copy_archive(item,target,cache)
            source_notices(target,folder/'notices'/item['id'])
            inputs.append({**item,'file':target.relative_to(output).as_posix()})
            print('Collected native source '+item['id'],flush=True)
        shutil.copyfile(lock_path,folder/'source-lock.json')
        inputs.append({'file':'windows-python-native/source-lock.json','sha256':digest(lock_path)})
        manifest['components'].append({'component':'windows-python-native','version':'1',
            'inputs':inputs,'wheel_rebuild_qualified':False})
        for component in manifest['components']:
            component['files']={p.relative_to(output).as_posix():digest(p)
                                for p in sorted((output/component['component']).rglob('*')) if p.is_file()}
        files={p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}
        manifest.update(status='collected',files=files);save()
    except BaseException as exc:
        manifest.update(status='failed',error=str(exc));save();raise
    return manifest


def verify_materials(materials, manifest, *, lock_path=LOCK):
    """Accept the component records inside a larger assembled source manifest."""
    lock=load_lock(lock_path)
    if manifest.get('platform') != lock['platform']:
        raise ValueError('Windows Python sources require matching host materials')
    components={}
    for c in manifest['components']:
        if c['component'] in components:raise ValueError('Repeated source component')
        components[c['component']]=c
    required={d['name'] for d in lock['distributions']} | {'windows-python-native'}
    if not required <= components.keys():raise ValueError('Missing Windows Python source components')
    for name in required:
        component=components[name]
        files=component.get('files',{})
        if any(p.is_symlink() for p in (materials/name).rglob('*')):
            raise ValueError('Linked Windows Python source material: '+name)
        actual={p.relative_to(materials).as_posix() for p in (materials/name).rglob('*') if p.is_file()}
        if not files or actual != files.keys():raise ValueError('Windows Python material file set differs: '+name)
        for filename,sha in files.items():
            if not filename.startswith(name+'/'):raise ValueError('Windows source component escapes its folder')
            if digest(source_file(materials,filename)) != sha:raise ValueError('Windows Python material changed: '+filename)
    expected={'windows-python-native/'+s['file']:s['sha256'] for s in lock['sources']}
    expected['windows-python-native/source-lock.json']=digest(lock_path)
    supplied={x['file']:x['sha256'] for x in components['windows-python-native']['inputs']}
    if supplied != expected:raise ValueError('Windows embedded native sources differ from lock')
    for name,sha in expected.items():
        if digest(source_file(materials,name)) != sha:raise ValueError('Windows embedded source changed')
    for d in lock['distributions']:
        component=components[d['name']]
        name=d['name']+'/'+d['sdist']['file']
        if (component.get('version')!=d['version'] or component.get('wheel')!=d['wheel'] or
                component.get('native_files')!=d['native_files'] or component.get('native_sources')!=d['native_sources'] or
                component['inputs']!=[{'file':name,'url':d['sdist']['url'],'sha256':d['sdist']['sha256']}] or
                digest(source_file(materials,name))!=d['sdist']['sha256']):
            raise ValueError('Windows Python source identity differs: '+d['name'])
        inspect_wheel(source_file(materials,'wheels/'+d['wheel']['file']),d)
        for filename,sha in d['metadata_files'].items():
            if digest(source_file(materials,d['name']+'/wheel-metadata/'+filename))!=sha:
                raise ValueError('Windows wheel metadata changed')
        for filename,sha in d['notice_files'].items():
            if digest(source_file(materials,d['name']+'/notices/wheel/'+filename))!=sha:
                raise ValueError('Windows wheel notice changed')
    return lock


def verify_installation(lock, materials, *, root=None):
    """Bind actual installed Python/wheel bytes before freezing on Windows.

    Explicit root is for offline wheel-layout checks. It never qualifies Windows
    execution or an installed CPython runtime.
    """
    import importlib.metadata
    import platform
    if root is None and (platform.system()!='Windows' or platform.machine().lower() not in ('amd64','x86_64') or
                         platform.python_implementation()!='CPython' or platform.python_version()!=lock['python_full_version']):
        raise ValueError('This Windows Python source lock requires native CPython '+lock['python_full_version']+' x86-64')
    records={}
    for d in lock['distributions']:
        distribution=importlib.metadata.distribution(d['name']) if root is None else None
        if distribution and distribution.version!=d['version']:
            raise ValueError('Installed Windows Python version differs: '+d['name'])
        base=Path(distribution.locate_file('')).resolve() if distribution else root.resolve()
        contents=inspect_wheel(materials/'wheels'/d['wheel']['file'],d)
        checked={}
        for name,data in contents.items():
            if name==str(PurePosixPath(d['metadata_file']).parent/'RECORD'):continue
            if any(p.endswith('.data') for p in PurePosixPath(name).parts):
                raise ValueError('Unreviewed wheel installation relocation: '+name)
            path=source_file(base,name)
            expected=hashlib.sha256(data).hexdigest()
            if not path.is_file() or digest(path)!=expected:
                raise ValueError('Installed Windows Python input changed: '+name)
            checked[name]=expected
        owned={PurePosixPath(n).parts[0] for n in contents if len(PurePosixPath(n).parts)>1 and '.dist-info/' not in n}
        actual={p.relative_to(base).as_posix() for folder in owned for p in (base/folder).rglob('*')
                if p.is_file() and p.suffix.lower() in ('.pyd','.dll','.exe')}
        # Several distributions share the jaraco namespace, which has no PE files.
        if actual!=d['native_files'].keys():raise ValueError('Unreviewed installed Windows wheel binary')
        records[d['name']]={'version':d['version'],'wheel_sha256':d['wheel']['sha256'],
                            'checked_files':len(checked),'native_files':d['native_files'],'native_sources':d['native_sources']}
    return {'schema':1,'platform':lock['platform'],'python_full_version':lock['python_full_version'],
            'distributions':records,'scope':'Installed inputs before freezing; CPython and native tools require separate source audit',
            'native_execution_qualified':False,'wheel_rebuild_qualified':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cache',type=Path,help='Optional flat directory of exact retained archives')
    args=parser.parse_args()
    result=collect(args.output.resolve(),cache=args.cache.resolve() if args.cache else None)
    print(json.dumps({'status':result['status'],'components':len(result['components']),'files':len(result['files']),
                      'native_execution_qualified':False,'complete_desktop_sources':False}))

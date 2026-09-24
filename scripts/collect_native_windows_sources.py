#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Assemble reviewed Windows tool sources and Python materials without execution.

Accepts extracted, retained component artifacts. Every input file is checked
against a pinned SHA256SUMS before copying. Firmware/newlib and final frozen
input correspondence remain separate; this never qualifies native execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from windows_python_sources import digest, source_file, relative

LOCK = Path(__file__).parent/'sdk-windows/native-components.json'
OMIT_SOURCE_DIRECTORIES = {'.git','output','__pycache__','.pytest_cache'}
GROUPS = {
    'arm-none-eabi-toolchain': {'artifact':'compiler','version':'16.2.0',
        'prefix':'','omit':('compiler/install','compiler/probe','base-dependencies/install',
                          'compiler-dependencies/install','mingw-runtime/runtime'),
        'installed':('compiler/install','mingw-runtime/runtime')},
    'arm-none-eabi-gdb': {'artifact':'gdb','version':'17.2','prefix':'',
        'omit':('gdb-candidate/install','toolchain','dependencies/install'),
        'installed':('gdb-candidate/install','toolchain/bin')},
    'windows-qemu': {'artifact':'qemu','version':'11.1.1-r70','prefix':'',
        'omit':('qemu/install','dependencies/install','mingw-runtime/runtime'),
        'installed':('qemu/install','dependencies/install','mingw-runtime/runtime')},
    'windows-libusb': {'artifact':'libraries','version':'1.0.27-1','prefix':'libusb',
        'omit':('libusb/install',),'installed':('libusb/install',)},
    'windows-openssl': {'artifact':'libraries','version':'3.0.13-0ubuntu3.15','prefix':'openssl',
        'omit':('openssl/install',),'installed':('openssl/install',)},
}


def within(name, prefix):
    return name == prefix or name.startswith(prefix+'/')


def parse_sums(sums):
    records = {}; folded = set()
    for line in sums.read_text(encoding='utf-8').splitlines():
        sha, separator, name = line.partition('  ')
        relative(name)
        if (not separator or not re.fullmatch('[0-9a-f]{64}',sha)
                or name.casefold() in folded or name == 'SHA256SUMS'):
            raise ValueError('Invalid Windows component checksum inventory')
        folded.add(name.casefold()); records[name] = sha
    return records


def verify_artifact(root, item):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Missing or linked Windows component directory')
    sums = source_file(root,'SHA256SUMS')
    if sums.stat().st_size > 2*1024**2 or digest(sums) != item['sums_sha256']:
        raise ValueError('Windows component checksum inventory differs from reviewed input')
    records = parse_sums(sums)
    actual = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked Windows component input')
        if path.is_file():actual[path.relative_to(root).as_posix()] = path
    if actual.keys() != records.keys() | {'SHA256SUMS'}:
        raise ValueError('Windows component input file set differs')
    for name, sha in records.items():
        if digest(source_file(root,name)) != sha:
            raise ValueError('Windows component file changed: '+name)
    return {**records,'SHA256SUMS':item['sums_sha256']}


def copy_checked(source, target, sha):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Repeated Windows source destination')
    shutil.copyfile(source,target)
    if digest(target) != sha:raise ValueError('Windows source input changed during copying')


def gcc_runtime_notices(outer):
    """Read exact GCC 13 terms from Ubuntu's nested original source archive."""
    wanted = {'COPYING','COPYING3','COPYING.LIB','COPYING3.LIB','COPYING.RUNTIME'}
    nested = 'gcc-13-13.2.0/gcc-13.2.0.tar.xz'
    with tarfile.open(outer) as archive, tempfile.TemporaryFile() as stream:
        member = archive.getmember(nested)
        if not member.isfile() or member.size > 128*1024**2:
            raise ValueError('Invalid nested GCC runtime source')
        shutil.copyfileobj(archive.extractfile(member),stream)
        stream.seek(0); result = {}
        with tarfile.open(fileobj=stream,mode='r|xz') as source:
            for count, member in enumerate(source):
                if count > 200000:raise ValueError('GCC source member bound exceeded')
                if member.name not in {'gcc-13.2.0/'+n for n in wanted}:continue
                if not member.isfile() or member.size > 1024**2:
                    raise ValueError('Invalid GCC runtime license member')
                name = Path(member.name).name
                if name in result:raise ValueError('Duplicate GCC runtime license')
                result[name] = source.extractfile(member).read()
        if result.keys() != wanted:raise ValueError('Missing GCC runtime license terms')
        return result


def collect(python_materials, artifacts, output, *, lock_path=LOCK, newlib=None):
    import windows_python_sources as wheels
    import windows_cpython_sources as cpython
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if lock.get('schema') != 1 or lock.get('platform') != 'windows-AMD64' or set(artifacts) != set(lock['artifacts']):
        raise ValueError('Require all four reviewed Windows native component artifacts')
    tables = {name:verify_artifact(artifacts[name],item) for name,item in lock['artifacts'].items()}
    manifest = json.loads((python_materials/'manifest.json').read_text(encoding='utf-8'))
    wheels.verify_materials(python_materials,manifest); cpython.verify_materials(python_materials,manifest)
    if len(manifest['components']) != 16:
        raise ValueError('Require only the 16 reviewed Python source components as assembly input')
    output.mkdir(parents=True,exist_ok=False)
    manifest = {k:manifest[k] for k in ('schema','platform','components')}
    manifest.update(status='assembling',complete_desktop_sources=False,native_execution_qualified=False,
        source_rebuild_qualified=False,scope='Windows tool and Python source inputs; newlib, firmware/project sources and complete frozen input coverage remain separate.',
        native_component_lock_sha256=digest(lock_path),windows_tool_inputs={})
    def save():
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for component in manifest['components']:
            for name, sha in component['files'].items():
                copy_checked(source_file(python_materials,name),output/name,sha)
        # Wheel archives remain preflight inputs outside the corresponding-source groups.
        for path in sorted((python_materials/'wheels').iterdir()):
            if not path.is_file() or path.is_symlink():raise ValueError('Invalid retained wheel input')
            copy_checked(path,output/'wheels'/path.name,digest(path))
        for name, group in GROUPS.items():
            root = artifacts[group['artifact']]; table = tables[group['artifact']]
            provenance = name+'/provenance/SHA256SUMS'
            copy_checked(root/'SHA256SUMS',output/provenance,table['SHA256SUMS'])
            files = {provenance:table['SHA256SUMS']}; inputs = [{'file':provenance,'sha256':table['SHA256SUMS']}]; installed = {}; notices = {}
            for source_name, sha in sorted(table.items()):
                if group['prefix'] and not within(source_name,group['prefix']):
                    continue
                if any(within(source_name,p) for p in group['installed']):
                    installed[source_name] = sha
                if any(within(source_name,p) for p in group['omit']) or OMIT_SOURCE_DIRECTORIES.intersection(Path(source_name).parts):
                    continue
                target_name = name+'/inputs/'+source_name
                copy_checked(source_file(root,source_name),output/target_name,sha)
                files[target_name] = sha; inputs.append({'file':target_name,'sha256':sha})
                if 'notices' in Path(source_name).parts or 'common-licenses' in Path(source_name).parts:
                    target_name = name+'/notices/'+source_name
                    copy_checked(source_file(root,source_name),output/target_name,sha)
                    files[target_name] = sha; notices[target_name] = sha
            if group['artifact'] in ('compiler','gdb','qemu'):
                source_names = [n for n in table if n.endswith('/gcc-13_13.2.0.orig.tar.gz')]
                if len(source_names)!=1:raise ValueError('Require the exact GCC runtime base source')
                for filename, data in gcc_runtime_notices(source_file(root,source_names[0])).items():
                    target_name = name+'/notices/gcc-runtime/'+filename
                    target = output/target_name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                    sha = hashlib.sha256(data).hexdigest();files[target_name] = sha;notices[target_name] = sha
            if not installed or not notices:
                raise ValueError('Windows native component lacks installed inputs or notices: '+name)
            component = {'component':name,'version':group['version'],'inputs':inputs,'files':files,
                'native_artifact':group['artifact'],'artifact':lock['artifacts'][group['artifact']],
                'installed_inputs':installed,'installed_notices':[{'file':n,'sha256':h} for n,h in notices.items()]}
            manifest['components'].append(component)
            for filename, sha in installed.items():
                manifest['windows_tool_inputs'][name+'/'+filename] = {'component':name,'version':group['version'],'sha256':sha}
            print('Collected '+name+': '+str(len(files))+' source/notice files, '+str(len(installed))+' installed inputs',flush=True)
            save()
        # Keep the reviewed lock and assembly recipe with the source groups.
        component = next(c for c in manifest['components'] if c['component']=='windows-qemu')
        for source, name in ((lock_path,'native-components.json'),(Path(__file__),'collect_native_windows_sources.py')):
            target = 'windows-qemu/assembly/'+name; sha = digest(source)
            copy_checked(source,output/target,sha);component['files'][target] = sha
            component['inputs'].append({'file':target,'sha256':sha})
        if newlib is not None:
            from native_desktop_project import collect_newlib
            manifest['components'].append(collect_newlib(Path(__file__).resolve().parents[1]/'sdk',newlib,output))
        manifest['status'] = 'collected';save()
        verify_materials(output,manifest,lock_path=lock_path)
        return manifest
    except BaseException as exc:
        manifest.update(status='failed',error=str(exc));save();raise


def verify_materials(materials, manifest, *, lock_path=LOCK, required=None):
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if (manifest.get('platform') != 'windows-AMD64' or manifest.get('native_component_lock_sha256') != digest(lock_path)):
        raise ValueError('Windows native source lock differs')
    components = {c['component']:c for c in manifest['components']}
    selected = set(GROUPS) if required is None else set(required)
    if not selected or not selected <= GROUPS.keys():
        raise ValueError('Unknown or empty Windows native source group')
    if len(components) != len(manifest['components']) or not selected <= components.keys():
        raise ValueError('Missing or duplicate Windows native source component')
    expected_catalog = {}
    for name in sorted(selected):
        group = GROUPS[name]
        component = components[name]; folder = source_file(materials,name)
        if (component.get('version') != group['version'] or component.get('artifact') != lock['artifacts'][group['artifact']]):
            raise ValueError('Windows native source identity differs')
        files = component.get('files',{})
        actual = {p.relative_to(materials).as_posix() for p in folder.rglob('*') if p.is_file()}
        if any(p.is_symlink() for p in folder.rglob('*')) or not files or files.keys()!=actual:
            raise ValueError('Windows native source material file set differs')
        for filename, sha in files.items():
            if not within(filename,name) or digest(source_file(materials,filename)) != sha:
                raise ValueError('Windows native source material changed')
        provenance = name+'/provenance/SHA256SUMS'
        if files.get(provenance) != lock['artifacts'][group['artifact']]['sums_sha256']:
            raise ValueError('Windows component provenance differs')
        table = parse_sums(source_file(materials,provenance))
        table['SHA256SUMS'] = files[provenance]
        expected_inputs = {provenance:files[provenance]}; expected_notices = {}; installed = {}
        for original, sha in table.items():
            if group['prefix'] and not within(original,group['prefix']):continue
            if any(within(original,p) for p in group['installed']):installed[original] = sha
            if any(within(original,p) for p in group['omit']) or OMIT_SOURCE_DIRECTORIES.intersection(Path(original).parts):continue
            expected_inputs[name+'/inputs/'+original] = sha
            if 'notices' in Path(original).parts or 'common-licenses' in Path(original).parts:
                expected_notices[name+'/notices/'+original] = sha
        if group['artifact'] in ('compiler','gdb','qemu'):
            source_names = [n for n in table if n.endswith('/gcc-13_13.2.0.orig.tar.gz')]
            if len(source_names)!=1:raise ValueError('Require the exact GCC runtime base source')
            for filename, data in gcc_runtime_notices(source_file(materials,name+'/inputs/'+source_names[0])).items():
                expected_notices[name+'/notices/gcc-runtime/'+filename] = hashlib.sha256(data).hexdigest()
        if name == 'windows-qemu':
            expected_inputs['windows-qemu/assembly/native-components.json'] = digest(lock_path)
            recipe = 'windows-qemu/assembly/collect_native_windows_sources.py'
            expected_inputs[recipe] = files.get(recipe)
        inputs = {i['file']:i['sha256'] for i in component['inputs']}
        notices = {i['file']:i['sha256'] for i in component['installed_notices']}
        if (len(inputs)!=len(component['inputs']) or len(notices)!=len(component['installed_notices'])
                or inputs!=expected_inputs or notices!=expected_notices or not installed or not notices
                or component['installed_inputs']!=installed or files!={**expected_inputs,**expected_notices}):
            raise ValueError('Windows native sources/catalog differ from pinned provenance')
        for filename, sha in installed.items():
            expected_catalog[name+'/'+filename] = {'component':name,'version':group['version'],'sha256':sha}
    if expected_catalog != manifest.get('windows_tool_inputs'):
        raise ValueError('Windows tool input catalog differs')
    return expected_catalog


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-materials',type=Path,required=True)
    for name in ('compiler','gdb','qemu','libraries'):
        parser.add_argument('--'+name,type=Path,required=True,help='Extracted reviewed component artifact root')
    parser.add_argument('--newlib',type=Path,help='Matching newlib candidate; required for a Windows binary packaging input set')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = collect(args.python_materials,{n:getattr(args,n) for n in ('compiler','gdb','qemu','libraries')},args.output,newlib=args.newlib)
    print(json.dumps({'status':result['status'],'components':len(result['components']),
                      'tool_inputs':len(result['windows_tool_inputs']),'complete_desktop_sources':False}))

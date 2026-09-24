#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package public source, explicit upstream trees and checked dependency inputs."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def project_inputs(manifest_path):
    """Require explicit archived inputs; never infer firmware from a build tree."""
    if manifest_path is None:
        raise ValueError('lefony-qemu requires --project-sources with all three source archives')
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError('Project source manifest exceeds bound')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 1 or set(manifest.get('archives', {})) != {
            'lefony', 'qemu-prime', 'prepared-firmware'}:
        raise ValueError('Project sources require Lefony, QEMU and prepared firmware archives')
    for key in ('firmware_sha256', 'qemu_input_sha256'):
        value = manifest.get(key, '')
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Project sources require exact binary identities: ' + key)
    inputs = []
    root = manifest_path.parent.resolve()
    groups = [('archives', manifest['archives'])]
    if 'evidence' in manifest:
        if set(manifest['evidence']) != {'firmware-rebuild','firmware-build-log'}:
            raise ValueError('Unknown or incomplete project rebuild evidence')
        groups.append(('evidence',manifest['evidence']))
    for group, entries in groups:
        for name, entry in sorted(entries.items()):
            value = entry['file'];relative = PurePosixPath(value)
            path = root.joinpath(*relative.parts)
            if (not value or relative.is_absolute() or relative.as_posix()!=value
                    or any(p in ('','..','.') for p in value.split('/')) or ':' in value or '\\' in value
                    or any(root.joinpath(*relative.parts[:i]).is_symlink() for i in range(len(relative.parts)+1))
                    or not path.resolve().is_relative_to(root) or not path.is_file()):
                raise ValueError('Unsafe or missing project source input: '+name)
            if (digest(path)!=entry['sha256'] or entry.get('bytes',path.stat().st_size)!=path.stat().st_size
                    or group=='archives' and not tarfile.is_tarfile(path)):
                raise ValueError('Project source input changed or is not a tar archive: '+name)
            archived = ('' if group=='archives' else 'evidence/')+name+'/'+path.name
            inputs.append((path,archived));entry['file'] = archived
    return manifest, inputs

class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()

    def read(self, size):
        data = self.stream.read(size)
        self.hash.update(data)
        return data


def add(archive,path,name,expected=None):
    if path.is_symlink():raise ValueError('Source material must not be a symlink: ' + name)
    if path.is_dir():
        for item in sorted(path.iterdir()):
            if item.name in ('.git','output','__pycache__','.pytest_cache'):continue
            add(archive,item,name+'/'+item.name,expected)
    elif path.is_file():
        # Hash the bytes actually passed to tar, rather than reopening the path
        # after copying. A source can change after the preflight hash check.
        with path.open('rb') as stream:
            info = archive.gettarinfo(fileobj=stream,arcname=name)
            if not info.isfile():raise ValueError('Source material is not a regular file: '+name)
            reader = HashedReader(stream)
            archive.addfile(info,reader)
            if stream.read(1) or (expected is not None and name in expected
                                  and reader.hash.hexdigest()!=expected[name]):
                raise ValueError('Source material changed while archiving: '+name)
    else:raise ValueError('Missing source material: ' + name)

def package(materials,output,groups=('toolchain','runtime','lefony-qemu'),*,project_sources=None):
    if not groups or set(groups)-{'toolchain','runtime','lefony-qemu'}:
        raise ValueError('Unknown or empty source groups')
    project = project_inputs(project_sources) if 'lefony-qemu' in groups else None
    sources=json.loads((materials/'manifest.json').read_text())
    dependencies = set(groups) - {'lefony-qemu'}
    if dependencies and sources.get('platform') == 'darwin-arm64':
        from pillow_native_sources import verify_materials
        verify_materials(materials, sources)
    elif dependencies and sources.get('platform') == 'linux-x86_64':
        from linux_wheel_native_sources import verify_materials
        verify_materials(materials, sources)
    elif dependencies and sources.get('platform') == 'windows-AMD64':
        from windows_python_sources import verify_materials
        verify_materials(materials, sources)
        from windows_cpython_sources import verify_materials as verify_cpython_materials
        verify_cpython_materials(materials, sources)
        if sources.get("windows_tool_inputs") or any(c["component"] in ("arm-none-eabi-toolchain", "windows-qemu", "windows-openssl", "windows-libusb") for c in sources["components"]):
            from collect_native_windows_sources import verify_materials as verify_native_materials
            verify_native_materials(materials, sources)
    # Windows collection records the selected sysroot as a structured bundle.
    # Linux/macOS source catalogs retain the original input/notice inventories;
    # their native source checks and the common hashes below validate that format.
    if (dependencies and sources.get('platform') == 'windows-AMD64'
            and any(c['component']=='arm-none-eabi-newlib' for c in sources['components'])):
        from native_desktop_project import verify_newlib_materials
        verify_newlib_materials(Path(__file__).resolve().parents[1]/'sdk',materials,sources)
    expected = {}
    for component in sources['components'] if dependencies else []:
        for item in component['inputs'] + component.get('installed_notices', []):
            path=materials/item['file']
            if path.is_symlink() or not path.resolve().is_relative_to(materials.resolve()) or digest(path)!=item['sha256']:raise ValueError('Source material changed')
            if item['file'] in expected and expected[item['file']]!=item['sha256']:
                raise ValueError('Conflicting source input hashes')
            expected[item['file']] = item['sha256']
    if project:
        for group in ('archives','evidence'):
            for entry in project[0].get(group,{}).values():expected[entry['file']] = entry['sha256']
    output.mkdir(parents=True,exist_ok=True)
    previous=json.loads((output/'sources.json').read_text()) if (output/'sources.json').exists() else []
    replaced={f'lefony-sdk-source-{group}.tar.gz' for group in groups}
    results=[item for item in previous if item['filename'] not in replaced]
    # Finish every archive and the catalog before replacing any prior output.
    # Source changes, cancellation and write failures during construction leave
    # the previous distribution intact. This is not a multi-file power-loss commit.
    with tempfile.TemporaryDirectory(prefix='.source-stage-',dir=output) as directory:
        stage = Path(directory)
        for group in dict.fromkeys(groups):
            path=stage/f'lefony-sdk-source-{group}.tar.gz'
            with tarfile.open(path,'w:gz') as archive:
                if group=='lefony-qemu':
                    manifest, inputs = project
                    for source, name in inputs:add(archive,source,name,expected)
                    data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
                else:
                    selected=[c for c in sources['components'] if (c['component'].startswith('arm-none-eabi-'))==(group=='toolchain')]
                    for component in selected:add(archive,materials/component['component'],component['component'],expected)
                    manifest={key:sources[key] for key in ('platform','status','complete_desktop_sources','scope','wheel_rebuild_qualified','native_component_lock_sha256') if key in sources}
                    manifest.update(schema=1,components=selected)
                    if 'windows_tool_inputs' in sources:
                        names={c['component'] for c in selected}
                        manifest['windows_tool_inputs']={n:item for n,item in sources['windows_tool_inputs'].items() if item['component'] in names}
                    data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
            results.append({'filename':path.name,'bytes':path.stat().st_size,'sha256':digest(path),'kind':'corresponding-source'})
        catalog=stage/'sources.json';catalog.write_text(json.dumps(results,indent=2)+'\n')
        for group in dict.fromkeys(groups):
            path=stage/f'lefony-sdk-source-{group}.tar.gz';path.replace(output/path.name)
        catalog.replace(output/'sources.json')
    print(json.dumps(results,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--materials',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--group',action='append',choices=('toolchain','runtime','lefony-qemu'))
    parser.add_argument('--project-sources',type=Path,help='Manifest binding exact Lefony/QEMU/prepared-firmware archives to binary inputs')
    args=parser.parse_args();package(args.materials,args.output,args.group or ('toolchain','runtime','lefony-qemu'),project_sources=args.project_sources)

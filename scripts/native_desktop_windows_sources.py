# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind bundled Windows PE and tool files to verified source component inputs."""
import hashlib
from pathlib import Path

from native_desktop_windows import digest, native_files


def providers(manifest, cpython_lock, wheel_lock):
    table = {}
    def add(sha, record):
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid Windows source input digest')
        table.setdefault(sha,[]).append(record)
    components = {c['component']:c for c in manifest['components']}
    if len(components)!=len(manifest['components']):
        raise ValueError('Duplicate Windows source component')
    for name, item in manifest['windows_tool_inputs'].items():
        component = components.get(item['component'])
        if not component or component['version']!=item['version'] or not component.get('inputs'):
            raise ValueError('Missing Windows native source provider')
        add(item['sha256'],{'component':item['component'],'version':item['version'],'original':name})
    for name, item in cpython_lock['native_files'].items():
        add(item['sha256'],{'component':'windows-cpython','version':cpython_lock['python_full_version'],
                           'original':name,'source_ids':item['sources']})
    for distribution in wheel_lock['distributions']:
        for name, sha in distribution['native_files'].items():
            add(sha,{'component':distribution['name'],'version':distribution['version'],
                     'original':name,'source_ids':distribution['native_sources'][name]})
    return table


def record_bundle(bundle, manifest, cpython_lock, wheel_lock):
    """Manifest and Python locks must pass their material verifiers first.

    The generated launcher embeds PyInstaller's reviewed bootloader. Other PE
    binaries and the copied toolchain/OpenSSL files must retain their input bytes.
    Firmware, newlib and full release qualification have their separate gates.
    """
    table = providers(manifest,cpython_lock,wheel_lock)
    launcher = bundle/'lefony-sdk.exe'
    files = set(native_files(bundle))-{launcher}
    for folder in ('_internal/toolchain','_internal/openssl'):
        root = bundle/folder
        for path in root.rglob('*'):
            if path.is_symlink():raise ValueError('Linked Windows tool input')
            if path.is_file():files.add(path)
    records = {}
    for path in sorted(files):
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()):
            raise ValueError('Windows source audit input escaped the bundle')
        sha = digest(path)
        if sha not in table:
            raise ValueError('Unmapped or changed Windows bundle input: '+path.relative_to(bundle).as_posix())
        records[path.relative_to(bundle).as_posix()] = {'sha256':sha,'providers':table[sha]}
    pyinstaller = next(d for d in wheel_lock['distributions'] if d['name']=='pyinstaller')
    name = 'PyInstaller/bootloader/Windows-64bit-intel/run.exe'
    if name not in pyinstaller['native_files'] or not launcher.is_file() or launcher.is_symlink():
        raise ValueError('Missing reviewed Windows PyInstaller launcher input')
    return {'schema':1,'platform':'windows-AMD64','files':records,
            'bootloader':{'component':'pyinstaller','version':pyinstaller['version'],
                          'original':name,'sha256':pyinstaller['native_files'][name]},
            'launcher_sha256':digest(launcher),'native_execution_qualified':False,
            'source_rebuild_qualified':False,
            'scope':'Bundled Windows PE and toolchain/OpenSSL input correspondence; generated launcher uses reviewed PyInstaller. Firmware/newlib and full release qualification remain separate.'}

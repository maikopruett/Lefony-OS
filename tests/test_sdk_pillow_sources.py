# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact wheel/source correspondence and actual packager input-table boundaries."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import pillow_native_sources as pillow


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    installed = tmp_path/'installed'
    files = {'PIL/_image.so': b'extension input',
             'PIL/.dylibs/codec.dylib': b'codec input',
             'pillow.dist-info/LICENSE': b'original notices',
             'pillow.dist-info/sbom.json': b'{"components":["patched codec"]}'}
    for name, data in files.items():
        target = installed/name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    archives = {'source.tar.gz': b'source archive bytes', 'codec.patch': b'required upstream patch'}
    lock = {'schema': 1, 'platform': 'darwin-arm64', 'pillow_version': 'test',
            'wheel': {'sha256': sha(b'original wheel')},
            'sources': [{'id': name, 'file': name, 'url': 'https://example.com/'+name,
                         'sha256': sha(data)} for name, data in archives.items()],
            'installed_files': {name: sha(data) for name, data in files.items()},
            'binaries': {name: list(archives) for name in files if name.startswith('PIL/')},
            'metadata_files': [name for name in files if '.dist-info/' in name]}
    lock_path = tmp_path/'lock.json'; lock_path.write_text(json.dumps(lock), encoding='utf-8')
    materials = tmp_path/'materials'

    def download(url, target, expected):
        data = archives[url.rsplit('/', 1)[-1]]
        assert sha(data) == expected
        target.write_bytes(data)

    component = pillow.collect(materials, download, lock_path=lock_path, root=installed)
    return installed, lock_path, lock, materials, {'components': [component]}


def test_collected_sources_keep_patch_wheel_notices_and_sbom(inputs):
    installed, path, lock, materials, manifest = inputs
    assert pillow.verify_materials(materials, manifest, lock_path=path) == lock
    assert (materials/'pillow-native/notices/sbom.json').read_bytes() == (installed/'pillow.dist-info/sbom.json').read_bytes()
    assert (materials/'pillow-native/codec.patch').read_bytes() == b'required upstream patch'
    assert manifest['components'][0]['wheel_rebuild_qualified'] is False


@pytest.mark.parametrize('change', ['missing-patch', 'changed-patch', 'changed-lock', 'changed-notice', 'duplicate'])
def test_source_correspondence_rejects_incomplete_or_changed_inputs(inputs, change):
    _, path, _, materials, manifest = inputs
    component = manifest['components'][0]
    if change == 'missing-patch':
        component['inputs'] = [x for x in component['inputs'] if not x['file'].endswith('codec.patch')]
    elif change == 'duplicate':
        component['inputs'].append(component['inputs'][0])
    else:
        name = {'changed-patch': 'codec.patch', 'changed-lock': 'source-lock.json',
                'changed-notice': 'notices/LICENSE'}[change]
        (materials/'pillow-native'/name).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Incomplete|changed|Duplicate'):
        pillow.verify_materials(materials, manifest, lock_path=path)


def test_source_path_escape_is_rejected_before_read(inputs):
    _, path, _, materials, manifest = inputs
    manifest['components'][0]['inputs'][0]['file'] = '../secret'
    with pytest.raises(ValueError, match='Invalid Pillow source path'):
        pillow.verify_materials(materials, manifest, lock_path=path)


@pytest.mark.parametrize('change', ['changed', 'extra'])
def test_installed_wheel_cannot_silently_change(inputs, change):
    installed, _, lock, _, _ = inputs
    target = installed/('PIL/_image.so' if change == 'changed' else 'PIL/new.dylib')
    target.write_bytes(b'unknown input')
    with pytest.raises(ValueError, match='differs|unrecognized'):
        pillow.verify_installation(lock, installed)


def make_bundle(tmp_path, installed, lock):
    bundle = tmp_path/'relocated bundle'
    entries = []
    for name in lock['binaries']:
        target = bundle/'_internal'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'relocated load commands '+(installed/name).read_bytes())
        entries.append((name, str(installed/name), 'EXTENSION' if name.endswith('.so') else 'BINARY'))
    toc = tmp_path/'Analysis-00.toc'; toc.write_text(repr(([], entries, [])), encoding='utf-8')
    return bundle, toc


def test_record_binds_actual_input_and_relocated_output_separately(inputs, tmp_path):
    installed, _, lock, _, _ = inputs
    bundle, toc = make_bundle(tmp_path, installed, lock)
    report = pillow.record_bundle(toc, bundle, lock, root=installed)
    assert len(report['files']) == 2 and not report['wheel_rebuild_qualified']
    for name, entry in report['files'].items():
        assert entry['input_sha256'] == sha((installed/entry['wheel_file']).read_bytes())
        assert entry['bundled_sha256'] == sha((bundle/name).read_bytes())
        assert entry['input_sha256'] != entry['bundled_sha256']
        assert entry['source_ids'] == ['source.tar.gz', 'codec.patch']


@pytest.mark.parametrize('change', ['missing-table-entry', 'extra-bundle-binary', 'wrong-input-root'])
def test_unknown_packager_inputs_cannot_receive_source_coverage(inputs, tmp_path, change):
    installed, _, lock, _, _ = inputs
    bundle, toc = make_bundle(tmp_path, installed, lock)
    if change == 'missing-table-entry':
        toc.write_text(repr([]), encoding='utf-8')
    elif change == 'extra-bundle-binary':
        (bundle/'_internal/PIL/extra.dylib').write_bytes(b'unknown binary')
    else:
        toc.write_text(toc.read_text(encoding='utf-8').replace(str(installed), str(tmp_path/'other')), encoding='utf-8')
    with pytest.raises(ValueError, match='inventory differs'):
        pillow.record_bundle(toc, bundle, lock, root=installed)


def test_checked_lock_accounts_for_avif_codecs_and_exact_installed_wheel():
    lock = pillow.load_lock()
    assert len(lock['binaries']) == 19
    assert set(lock['binaries']['PIL/.dylibs/libavif.16.4.2.dylib']) == {'avif', 'aom', 'dav1d', 'libyuv', 'sharpyuv-static'}
    assert 'pillow' in lock['binaries']['PIL/.dylibs/libtiff.6.dylib']
    if pillow.supported_host() and sys.version_info[:2] == (3, 14):
        pillow.verify_installation(lock)


@pytest.mark.parametrize('change', ['none', 'changed-output', 'changed-report', 'incomplete-report'])
def test_collector_uses_verified_wheel_outputs_and_aliases(inputs, tmp_path, monkeypatch, change):
    installed, _, lock, _, _ = inputs
    bundle, toc = make_bundle(tmp_path, installed, lock)
    report = pillow.record_bundle(toc, bundle, lock, root=installed)
    if change == 'incomplete-report':
        report['files'].pop(next(iter(report['files'])))
    path = bundle/'pillow-native-inputs.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    (bundle/'candidate.json').write_text(json.dumps({'pillow_native_inputs_sha256': pillow.digest(path)}), encoding='utf-8')
    alias = bundle/'_internal/codec.dylib'
    alias.symlink_to('PIL/.dylibs/codec.dylib')
    monkeypatch.setattr(pillow, 'load_lock', lambda: lock)
    if change == 'changed-output':
        (bundle/'_internal/PIL/_image.so').write_bytes(b'changed output')
    elif change == 'changed-report':
        path.write_text('{}', encoding='utf-8')
    if change == 'none':
        assert alias.resolve() in pillow.wheel_libraries(bundle)
    else:
        with pytest.raises(ValueError, match='changed|Changed|Incomplete'):
            pillow.wheel_libraries(bundle)

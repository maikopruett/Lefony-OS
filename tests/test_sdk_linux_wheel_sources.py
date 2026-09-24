# SPDX-License-Identifier: GPL-3.0-or-later
"""Native wheel/source boundaries for the actual Linux packaging inputs."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import linux_wheel_native_sources as wheel


@pytest.fixture
def inputs(tmp_path):
    binary = b'\x7fELF\x02\x01' + b'\0' * 12 + b'\x3e\x00' + b'native code'
    source = tmp_path / 'source'; source.mkdir()
    archive = source / 'library.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        for name, data in [('library/LICENSE', b'upstream license'), ('library/fix.patch', b'required patch')]:
            member = tarfile.TarInfo(name); member.size = len(data); output.addfile(member, io.BytesIO(data))
    installed = tmp_path / 'installed'; (installed / 'PIL').mkdir(parents=True)
    (installed / 'PIL/native.so').write_bytes(binary)
    bundle = tmp_path / 'bundle'; (bundle / '_internal/PIL').mkdir(parents=True)
    (bundle / '_internal/PIL/native.so').write_bytes(binary)
    wheels = tmp_path / 'wheels'; wheels.mkdir()
    metadata = {'pillow-1.dist-info/LICENSE': b'wheel license', 'pillow-1.dist-info/sbom.json': b'{"version":1}'}
    with zipfile.ZipFile(wheels / 'pillow-1.whl', 'w') as output:
        output.writestr('PIL/native.so', binary)
        for name, data in metadata.items(): output.writestr(name, data)
    lock = {'schema': 1, 'platform': 'linux-x86_64',
        'sources': [{'id': 'library', 'file': archive.name, 'url': 'https://example.org/library.tar.gz',
                     'sha256': wheel.digest(archive), 'bytes': archive.stat().st_size}],
        'wheels': {'pillow': {'file': 'pillow-1.whl', 'version': '1', 'sha256': wheel.digest(wheels / 'pillow-1.whl'),
            'binaries': {'PIL/native.so': {'sha256': hashlib.sha256(binary).hexdigest(), 'source_ids': ['library']}},
            'metadata': {name: hashlib.sha256(data).hexdigest() for name, data in metadata.items()}}}}
    lock_path = tmp_path / 'lock.json'; lock_path.write_text(json.dumps(lock))
    inventory = {'status': 'passed', 'inputs': [{'target': 'PIL/native.so', 'source': '/venv/site-packages/PIL/native.so',
        'source_sha256': hashlib.sha256(binary).hexdigest(), 'bundled_sha256': hashlib.sha256(binary).hexdigest(),
        'origin': {'kind': 'python-wheel', 'name': 'pillow', 'version': '1',
            'download': {'archive_info': {'hashes': {'sha256': lock['wheels']['pillow']['sha256']}}}}}]}
    inventory_path = tmp_path / 'inventory.json'; inventory_path.write_text(json.dumps(inventory))
    output = tmp_path / 'materials'
    wheel.collect(output, wheels, inventory_path, bundle, caches=[source], offline=True, lock_path=lock_path)
    manifest = json.loads((output / 'manifest.json').read_text())
    return SimpleNamespace(root=tmp_path, lock=lock, lock_path=lock_path, inventory=inventory,
        inventory_path=inventory_path, source=source, archive=archive, wheels=wheels, installed=installed,
        bundle=bundle, output=output, manifest=manifest)


def test_offline_collection_keeps_exact_archives_and_notices(inputs):
    assert inputs.manifest['status'] == 'collected'
    assert inputs.manifest['complete_desktop_sources'] is False
    assert (inputs.output / wheel.COMPONENT / inputs.archive.name).read_bytes() == inputs.archive.read_bytes()
    assert list((inputs.output / wheel.COMPONENT / 'notices/sources/library').glob('*LICENSE'))
    wheel.verify_materials(inputs.output, inputs.manifest, lock_path=inputs.lock_path)
    with pytest.raises(ValueError, match='Output exists'):
        wheel.collect(inputs.output, inputs.wheels, inputs.inventory_path, inputs.bundle, lock_path=inputs.lock_path)


@pytest.mark.parametrize('change', ['archive', 'notice', 'missing-notice', 'extra-file', 'duplicate-input', 'manifest-lock', 'failed-collection'])
def test_changed_or_incomplete_source_materials_are_rejected(inputs, change):
    component = inputs.manifest['components'][0]
    if change == 'archive': (inputs.output / wheel.COMPONENT / inputs.archive.name).write_bytes(b'changed')
    elif change == 'notice':
        notice = next(i for i in component['inputs'] if i.get('role') == 'source-notice')
        (inputs.output / notice['file']).write_bytes(b'changed')
    elif change == 'missing-notice':
        notice = next(i for i in component['inputs'] if i.get('role') == 'source-notice')
        component['inputs'].remove(notice); (inputs.output / notice['file']).unlink()
    elif change == 'extra-file': (inputs.output / wheel.COMPONENT / 'unlisted.bin').write_bytes(b'not a source input')
    elif change == 'duplicate-input': component['inputs'].append(component['inputs'][0])
    elif change == 'manifest-lock': component['source_lock_sha256'] = '0' * 64
    elif change == 'failed-collection': inputs.manifest['status'] = 'failed'
    with pytest.raises(ValueError): wheel.verify_materials(inputs.output, inputs.manifest, lock_path=inputs.lock_path)


@pytest.mark.parametrize('change', ['native-bytes', 'unknown-wheel', 'unreviewed-file', 'wheel-version', 'missing-input', 'duplicate-target'])
def test_frozen_inventory_is_bound_to_reviewed_wheel_bytes(inputs, change):
    record = inputs.inventory['inputs'][0]
    if change == 'native-bytes': (inputs.bundle / '_internal/PIL/native.so').write_bytes(b'changed')
    elif change == 'unknown-wheel': record['origin']['name'] = 'new-package'
    elif change == 'unreviewed-file': record['source'] = '/venv/site-packages/PIL/new.so'
    elif change == 'wheel-version': record['origin']['version'] = '2'
    elif change == 'missing-input': inputs.inventory['inputs'] = []
    elif change == 'duplicate-target': inputs.inventory['inputs'].append(dict(record))
    with pytest.raises(ValueError): wheel.verify_inventory(inputs.inventory, inputs.bundle, inputs.lock)


def test_source_path_and_identifier_cannot_escape(inputs):
    for name in ('../outside', '/outside', 'link/../../outside', 'a\\b', './relative'):
        with pytest.raises(ValueError): wheel.scoped(inputs.root, name)
    inputs.lock['sources'][0]['id'] = '../../outside'
    inputs.lock_path.write_text(json.dumps(inputs.lock))
    with pytest.raises(ValueError): wheel.load_lock(inputs.lock_path)


def test_offline_failure_retains_diagnostic_manifest(inputs):
    output = inputs.root / 'missing-cache'
    with pytest.raises(ValueError, match='Offline source'):
        wheel.collect(output, inputs.wheels, inputs.inventory_path, inputs.bundle, offline=True, lock_path=inputs.lock_path)
    report = json.loads((output / 'manifest.json').read_text())
    assert report['status'] == 'failed' and report['complete_desktop_sources'] is False


def distribution(root, name='pillow', files=('PIL/native.so', 'PIL/unreviewed.so')):
    return SimpleNamespace(version='1', metadata={'Name': name}, files=list(map(Path, files)),
                           locate_file=lambda path: root / path)


@pytest.mark.parametrize('change', [None, 'unreviewed-input', 'new-wheel', 'missing-input', 'extra-output'])
def test_packager_records_actual_inputs_and_rejects_unmapped_native_code(inputs, monkeypatch, change):
    package = distribution(inputs.installed)
    packages = [package]
    monkeypatch.setattr(wheel.importlib.metadata, 'distribution', lambda name: package)
    monkeypatch.setattr(wheel.importlib.metadata, 'distributions', lambda: packages)
    entries = [('PIL/native.so', str(inputs.installed / 'PIL/native.so'), 'EXTENSION')]
    if change == 'unreviewed-input':
        (inputs.installed / 'PIL/unreviewed.so').write_bytes(b'new code')
        entries.append(('PIL/unreviewed.so', str(inputs.installed / 'PIL/unreviewed.so'), 'EXTENSION'))
    elif change == 'new-wheel':
        (inputs.installed / 'new.so').write_bytes(b'new dependency')
        packages.append(distribution(inputs.installed, 'new-dependency', ('new.so',)))
        entries.append(('new.so', str(inputs.installed / 'new.so'), 'EXTENSION'))
    elif change == 'missing-input': entries = []
    elif change == 'extra-output': (inputs.bundle / '_internal/PIL/unlisted.so').write_bytes(b'unlisted code')
    toc = inputs.root / 'Analysis.toc'; toc.write_text(repr([entries]))
    if change:
        with pytest.raises(ValueError): wheel.record_bundle(toc, inputs.bundle, inputs.lock)
    else:
        report = wheel.record_bundle(toc, inputs.bundle, inputs.lock)
        assert report['files']['PIL/native.so']['source_ids'] == ['library']
        assert report['files']['PIL/native.so']['bundled_sha256'] == wheel.digest(inputs.bundle / '_internal/PIL/native.so')


@pytest.mark.parametrize('changed', [False, True])
def test_source_archive_requires_wheel_materials_and_keeps_partial_scope(inputs, monkeypatch, changed):
    import package_native_desktop_sources as packager
    original = wheel.verify_materials
    monkeypatch.setattr(wheel, 'verify_materials',
                        lambda root, manifest: original(root, manifest, lock_path=inputs.lock_path))
    # Explicit dependency source groups must also work from an extracted kit.
    # They contain no implicit checkout files and must not require Git metadata.
    def no_git(*args, **kwargs):
        raise AssertionError('Dependency source packaging must not inspect a Git checkout')
    import subprocess
    monkeypatch.setattr(subprocess, 'check_output', no_git)
    if changed:
        (inputs.output / wheel.COMPONENT / inputs.archive.name).write_bytes(b'changed')
        with pytest.raises(ValueError, match='source archive changed'):
            packager.package(inputs.output, inputs.root / 'distribution', ('runtime',))
        assert not list((inputs.root / 'distribution').glob('*.tar.gz'))
    else:
        packager.package(inputs.output, inputs.root / 'distribution', ('runtime',))
        with tarfile.open(inputs.root / 'distribution/lefony-sdk-source-runtime.tar.gz') as archive:
            manifest = json.load(archive.extractfile('manifest.json'))
            assert manifest['platform'] == 'linux-x86_64'
            assert manifest['complete_desktop_sources'] is False
            assert manifest['wheel_rebuild_qualified'] is False
            for entry in manifest['components'][0]['inputs']:
                assert hashlib.sha256(archive.extractfile(entry['file']).read()).hexdigest() == entry['sha256']

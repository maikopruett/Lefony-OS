# SPDX-License-Identifier: GPL-3.0-or-later
"""Bind Python source selection to the exact wheels used by a Linux freeze."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_native_linux_python_sources as sources


def fixture(tmp_path, monkeypatch):
    binary = tmp_path / 'native.so'; binary.write_bytes(b'actual frozen input')
    download = {'url': 'https://example.org/sample-1.2-py3-none-any.whl',
                'archive_info': {'hashes': {'sha256': 'a' * 64}}}
    report = {'install': [{'metadata': {'name': 'Sample_Package', 'version': '1.2'},
                           'download_info': download}]}
    inventory = {'status': 'passed', 'inputs': [{'target': 'native.so', 'source': str(binary),
        'source_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'origin': {'kind': 'python-wheel', 'name': 'sample-package', 'version': '1.2', 'download': copy.deepcopy(download)}}]}
    monkeypatch.setattr(sources.importlib.metadata, 'version', lambda name: '1.2')
    return report, inventory


def test_installed_version_and_actual_binary_must_match(tmp_path, monkeypatch):
    report, inventory = fixture(tmp_path, monkeypatch)
    assert set(sources.validate_inputs(report, inventory)) == {'sample-package'}
    monkeypatch.setattr(sources.importlib.metadata, 'version', lambda name: '1.3')
    with pytest.raises(ValueError, match='Installed Python version'):
        sources.validate_inputs(report, inventory)
    monkeypatch.setattr(sources.importlib.metadata, 'version', lambda name: '1.2')
    Path(inventory['inputs'][0]['source']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='native input differs'):
        sources.validate_inputs(report, inventory)


@pytest.mark.parametrize('change', ['wheel-hash', 'wheel-url', 'version', 'missing-wheel', 'unknown-origin'])
def test_native_wheel_provenance_cannot_be_substituted(tmp_path, monkeypatch, change):
    report, inventory = fixture(tmp_path, monkeypatch)
    origin = inventory['inputs'][0]['origin']
    if change == 'wheel-hash': origin['download']['archive_info']['hashes']['sha256'] = 'b' * 64
    if change == 'wheel-url': origin['download']['url'] = 'https://example.org/other.whl'
    if change == 'version': origin['version'] = '1.1'
    if change == 'missing-wheel': origin['name'] = 'other'
    if change == 'unknown-origin': origin['kind'] = 'unmapped'
    with pytest.raises(ValueError): sources.validate_inputs(report, inventory)


@pytest.mark.parametrize('url', ['http://example.org/sample.whl', 'https://user:pass@example.org/sample.whl',
                               'https://example.org/sample.tar.gz'])
def test_wheel_requires_https_archive_identity(tmp_path, monkeypatch, url):
    report, inventory = fixture(tmp_path, monkeypatch)
    report['install'][0]['download_info']['url'] = url
    with pytest.raises(ValueError, match='exact HTTPS wheel'):
        sources.validate_inputs(report, inventory)


def test_repeated_packages_and_failed_inventory_rejected(tmp_path, monkeypatch):
    report, inventory = fixture(tmp_path, monkeypatch)
    report['install'].append(copy.deepcopy(report['install'][0]))
    with pytest.raises(ValueError, match='Repeated'):
        sources.validate_inputs(report, inventory)
    inventory['status'] = 'failed'
    with pytest.raises(ValueError, match='passing native'):
        sources.validate_inputs(report, inventory)


def test_nested_vendor_metadata_is_retained_within_its_directory():
    assert sources.metadata_root('sample-1.2.dist-info/METADATA') == Path('sample-1.2.dist-info')
    assert sources.metadata_root('setuptools/_vendor/sample-1.2.dist-info/LICENSE') == Path('setuptools/_vendor/sample-1.2.dist-info')
    assert sources.metadata_root('../../../bin/tool') is None
    for path in ('../sample.dist-info/METADATA', '/sample.dist-info/METADATA', 'sample.dist-info/../../outside'):
        with pytest.raises(ValueError, match='Unsafe'):
            sources.metadata_root(path)


def test_failed_collection_retains_its_attempt(tmp_path, monkeypatch):
    report, inventory = fixture(tmp_path, monkeypatch)
    install = tmp_path / 'install.json'; install.write_text(json.dumps(report))
    inputs = tmp_path / 'inputs.json'; inputs.write_text(json.dumps(inventory))
    output = tmp_path / 'sources'
    monkeypatch.setattr(sources.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(sources.platform, 'machine', lambda: 'x86_64')
    def fail(*args, **kwargs):
        raise RuntimeError('Source download failed')
    monkeypatch.setattr(sources, 'collect_python', fail)
    with pytest.raises(RuntimeError, match='download failed'):
        sources.collect(install, inputs, output)
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['status'] == 'failed' and manifest['complete_desktop_sources'] is False
    assert (output / 'install-report.json').read_bytes() == install.read_bytes()
    assert (output / 'native-inputs.json').read_bytes() == inputs.read_bytes()
    with pytest.raises(ValueError, match='Output exists'):
        sources.collect(install, inputs, output)

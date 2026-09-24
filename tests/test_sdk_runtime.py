# SPDX-License-Identifier: GPL-3.0-or-later
"""Public project profile, source/manifest consistency and actual ARM linking."""
import json
from pathlib import Path
import shutil
import sys
import runpy
import tarfile
import hashlib
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from build import build, project_lock
from runtime import resolve
from source import collect, decode, extract


def project(path):
    (path / 'src').mkdir(parents=True)
    shutil.copyfile(ROOT / 'tests/native/sdk_main.cpp', path / 'src/main.cpp')
    (path / 'project.json').write_text(json.dumps({'schema':2, 'runtime':'foreground-newlib-1',
        'sources':['src/main.cpp'], 'arguments':['clean', 'quoted "text"', 'back\\slash']}))
    metadata = json.loads((ROOT / 'sdk/examples/c-main/app.json').read_text())
    metadata.update(id='main-proof', name='Conventional main')
    (path / 'app.json').write_text(json.dumps(metadata))
    return metadata


def test_foreground_source_requires_public_manifest(tmp_path):
    metadata = project(tmp_path)
    assert decode(collect(tmp_path, 2))['manifest'] == metadata
    metadata['minimum_api'] = 2
    (tmp_path / 'app.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='minimum_api'): collect(tmp_path, 2)
    with pytest.raises(ValueError, match='minimum_api'): build(tmp_path, ROOT / 'sdk')


def test_main_profile_build_source_roundtrip_and_lock(tmp_path):
    if not (ROOT / 'build/sdk-newlib/candidate.json').exists():
        pytest.skip('requires the pinned newlib sysroot; build scripts/build_sdk_newlib.py')
    sdk = ROOT / 'sdk'
    project(tmp_path / 'Original é')
    original = tmp_path / 'Original é'
    _, image = build(original, sdk)
    expected = image.read_bytes()
    assert project_lock(original, sdk) == json.loads((original / 'sdk.lock.json').read_text())
    build(original, sdk)
    assert json.loads((original / 'build/build.json').read_text())['compiled'] == []
    restored = tmp_path / 'Restored'
    extract(collect(original, 2), restored)
    assert build(restored, sdk)[1].read_bytes() == expected
    assert json.loads((restored / 'build/build.json').read_text())['resources']['heap_reserved_bytes'] == 8380416
    wrong = json.loads((restored / 'sdk.lock.json').read_text())
    wrong['dependencies'][-1]['libraries']['libc.a'] = '0'*64
    (restored / 'sdk.lock.json').write_text(json.dumps(wrong))
    with pytest.raises(ValueError, match='lock'): build(restored, sdk)


def test_sysroot_content_changes_are_rejected(tmp_path, monkeypatch):
    if not (ROOT / 'build/sdk-newlib/candidate.json').exists():
        pytest.skip('requires the pinned newlib sysroot')
    root = tmp_path / 'sysroot'
    source = resolve(ROOT / 'sdk')['root']
    shutil.copytree(source / 'install', root / 'install')
    for name in ('candidate.json', 'COPYING.NEWLIB'): shutil.copyfile(source / name, root / name)
    monkeypatch.setenv('LEFONY_SDK_NEWLIB', str(root))
    assert resolve(ROOT / 'sdk')['root'] == root
    header = root / 'install/arm-none-eabi/include/stdio.h'
    header.write_bytes(header.read_bytes() + b'\n/* changed */\n')
    with pytest.raises(ValueError, match='headers'): resolve(ROOT / 'sdk')


def test_pinned_newlib_descriptor_adjustment_is_checked_and_repeatable(tmp_path):
    recipe = runpy.run_path(str(ROOT / 'scripts/build_sdk_newlib.py'))
    archive = ROOT / 'build/sdk-newlib' / recipe['ARCHIVE']
    if not archive.is_file(): pytest.skip('requires the pinned newlib source archive')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == recipe['SHA256']
    spec = json.loads((ROOT / 'sdk/contracts/newlib.json').read_text())
    change = spec['source_adjustments']['stdio-descriptor-32-v1']
    with tarfile.open(archive) as source:
        original = source.extractfile('newlib-' + spec['version'] + '/' + change['path']).read()
    header = tmp_path / change['path']; header.parent.mkdir(parents=True); header.write_bytes(original)
    assert recipe['prepare_source'](tmp_path) == spec['source_adjustments']
    modified = header.read_bytes()
    assert hashlib.sha256(modified).hexdigest() == change['after_sha256']
    # Both FILE variants must retain the full int handle; every other byte,
    # including upstream copyright notices, is identical to the pinned source.
    assert modified.count(b'  int\t_file;') == 2
    assert modified.replace(b'  int\t_file;', b'  short\t_file;') == original
    recipe['prepare_source'](tmp_path)
    assert header.read_bytes() == modified
    header.write_bytes(original + b'\n/* unexpected upstream change */\n')
    unexpected = header.read_bytes()
    with pytest.raises(ValueError, match='Unexpected pinned'): recipe['prepare_source'](tmp_path)
    assert header.read_bytes() == unexpected, 'Unknown source must not be rewritten'


def test_old_or_mixed_newlib_abi_is_rejected(tmp_path):
    if not (ROOT / 'build/sdk-newlib/candidate.json').exists():
        pytest.skip('requires the pinned newlib sysroot')
    source = resolve(ROOT / 'sdk')['root']
    root = tmp_path / 'mixed'
    shutil.copytree(source / 'install', root / 'install')
    for name in ('candidate.json', 'COPYING.NEWLIB'): shutil.copyfile(source / name, root / name)
    path = root / 'candidate.json'; candidate = json.loads(path.read_text())
    adjustments = candidate.pop('source_adjustments'); path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError, match='source_adjustments'): resolve(ROOT / 'sdk', root)
    candidate['source_adjustments'] = adjustments
    header = root / 'install/arm-none-eabi/include/sys/reent.h'
    original = header.read_bytes().replace(b'  int\t_file;', b'  short\t_file;')
    header.write_bytes(original)
    # A self-consistent inventory cannot qualify the incompatible 16-bit ABI.
    candidate['headers']['sys/reent.h'] = hashlib.sha256(original).hexdigest()
    path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError, match='FILE descriptors'): resolve(ROOT / 'sdk', root)

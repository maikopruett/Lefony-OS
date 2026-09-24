# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build_sdk_windows_gdb_dependencies as builder


def test_retained_recipe_finds_its_own_pins_without_the_checkout(tmp_path):
    recipes = builder.retain_recipes(tmp_path)
    for name, checksum in recipes.items():
        assert builder.digest(tmp_path/name) == checksum
    code = ('import sys; sys.path.insert(0, sys.argv[1]); '
            'import build_sdk_windows_gdb_dependencies as b; '
            'print(b.digest(b.LOCK))')
    result = subprocess.run([sys.executable, '-I', '-c', code, str(tmp_path)],
                            cwd=tmp_path, text=True, capture_output=True, check=True, timeout=10)
    assert result.stdout.strip() == builder.digest(builder.LOCK)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    materials = tmp_path/'materials'
    pins = {}
    for name in ('gmp', 'mpfr', 'expat'):
        folder = materials/name/'archives'; folder.mkdir(parents=True)
        files = {name+'.dsc': b'descriptor', name+'.tar.xz': b'source'}
        for filename, data in files.items():
            (folder/filename).write_bytes(data)
        pins[name] = {'directory': name, 'archives': {
            filename: hashlib.sha256(data).hexdigest() for filename, data in files.items()}}
    lock = tmp_path/'pins.json'; lock.write_text(json.dumps(pins))
    monkeypatch.setattr(builder, 'LOCK', lock)
    output = tmp_path/'sources'; output.mkdir()
    return materials, output, pins


def test_exact_sources_are_retained_and_inputs_unchanged(inputs):
    materials, output, pins = inputs
    assert builder.copy_sources(materials, output) == pins
    for name, component in pins.items():
        for filename, checksum in component['archives'].items():
            assert builder.digest(output/name/filename) == checksum
            assert builder.digest(materials/name/'archives'/filename) == checksum


@pytest.mark.parametrize('damage', ['changed', 'missing', 'symlink'])
def test_reject_all_inputs_before_any_copy(inputs, damage):
    materials, output, _ = inputs
    target = materials/'expat/archives/expat.tar.xz'
    if damage == 'changed':
        target.write_bytes(b'changed source')
    else:
        data = target.read_bytes(); target.unlink()
        if damage == 'symlink':
            alternate = materials/'replacement'; alternate.write_bytes(data)
            target.symlink_to(alternate)
    with pytest.raises(ValueError, match='differs from the pinned input'):
        builder.copy_sources(materials, output)
    assert not list(output.iterdir())


def test_source_change_during_copy_cannot_become_accepted(inputs, monkeypatch):
    materials, output, _ = inputs
    original = builder.shutil.copyfile
    def changed(source, target):
        original(source, target)
        if target.name.endswith('.tar.xz'):
            target.write_bytes(b'racing source change')
    monkeypatch.setattr(builder.shutil, 'copyfile', changed)
    with pytest.raises(ValueError, match='changed during copy'):
        builder.copy_sources(materials, output)

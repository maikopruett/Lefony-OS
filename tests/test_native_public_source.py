# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual public archives preserve working-tree bytes and reject unsafe inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import package_native_public_source as source


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'repository'
    root.mkdir()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root / '.gitignore').write_text('build/\n')
    (root / 'main.c').write_text('int main(void) { return 0; }\n')
    (root / 'removed.c').write_text('old source\n')
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    (root / 'removed.c').unlink()
    (root / 'main.c').write_text('int main(void) { return 1; }\n')
    (root / 'new.sh').write_text('#!/bin/sh\nexit 0\n')
    (root / 'new.sh').chmod(0o755)
    (root / 'build').mkdir()
    (root / 'build/private.key').write_text('private generated input\n')
    return root


def test_archive_contains_actual_working_tree_and_is_reproducible(repository, tmp_path):
    first, second = tmp_path / 'one', tmp_path / 'two'
    a = source.package(repository, first)
    b = source.package(repository, second)
    assert a == b and (first / 'source.tar.gz').read_bytes() == (second / 'source.tar.gz').read_bytes()
    assert set(a['files']) == {'.gitignore', 'main.c', 'new.sh'}
    assert a['source_kind'] == 'working-tree'
    assert json.loads((first / 'manifest.json').read_text()) == a
    with tarfile.open(first / 'source.tar.gz') as tar:
        assert tar.extractfile('lefony/main.c').read() == (repository / 'main.c').read_bytes()
        assert tar.getmember('lefony/new.sh').mode == 0o755
        assert all(m.uid == m.gid == m.mtime == 0 for m in tar)
    with pytest.raises(ValueError, match='new public-source output'):
        source.package(repository, first)


@pytest.mark.parametrize('kind', ['key', 'symlink'])
def test_unsafe_untracked_inputs_are_rejected_before_output(repository, tmp_path, kind):
    if kind == 'key':
        (repository / 'accident.txt').write_text('-----BEGIN ' + 'PRIVATE KEY-----\n')
    else:
        (repository / 'link').symlink_to(repository / 'main.c')
    output = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        source.package(repository, output)
    assert not output.exists()


@pytest.mark.parametrize('change', ['content', 'mode', 'added', 'reappeared'])
def test_concurrent_changes_cannot_publish_a_manifest(repository, tmp_path, monkeypatch, change):
    original = source.unchanged
    def changed(root, names, files):
        if change == 'content': (root / 'main.c').write_text('changed\n')
        elif change == 'mode': (root / 'new.sh').chmod(0o644)
        elif change == 'added': (root / 'extra.c').write_text('new file\n')
        else: (root / 'removed.c').write_text('restored\n')
        original(root, names, files)
    monkeypatch.setattr(source, 'unchanged', changed)
    output = tmp_path / 'changed'
    with pytest.raises(ValueError):
        source.package(repository, output)
    assert list(output.iterdir()) == []

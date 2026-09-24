# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject invalid compiler build inputs before they can be configured/executed."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('linux_toolchain', ROOT / 'scripts/build_sdk_linux_toolchain.py')
toolchain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolchain)


def test_incorrect_archive_hash_is_rejected(tmp_path):
    source = tmp_path / 'input.tar.xz'; source.write_bytes(b'not pinned compiler source')
    output = tmp_path / 'out'; output.mkdir()
    with pytest.raises(ValueError, match='differs from the pinned input'):
        toolchain.source_archive('gcc', source, output)


def test_directory_and_oversized_input_are_rejected_before_copy(tmp_path):
    output = tmp_path / 'out'; output.mkdir()
    with pytest.raises(ValueError, match='regular archive'):
        toolchain.source_archive('gcc', tmp_path, output)
    source = tmp_path / 'oversized'
    with source.open('wb') as stream:
        stream.truncate(201 * 1024 * 1024)
    with pytest.raises(ValueError, match='size bound'):
        toolchain.source_archive('gcc', source, output)
    assert not list(output.iterdir())


@pytest.mark.parametrize('name', ['different/configure', '/gcc-16.2.0/configure', 'gcc-16.2.0/../../escape'])
def test_archive_root_and_traversal_are_rejected(tmp_path, name):
    path = tmp_path / 'source.tar'
    with tarfile.open(path, 'w') as archive:
        item = tarfile.TarInfo(name); item.size = 5
        archive.addfile(item, io.BytesIO(b'hello'))
    with pytest.raises((ValueError, tarfile.FilterError)):
        toolchain.extract(path, tmp_path / 'extract', 'gcc')
    assert not (tmp_path / 'escape').exists()


def test_valid_root_extracts_without_executing_configuration(tmp_path):
    path = tmp_path / 'source.tar'
    with tarfile.open(path, 'w') as archive:
        item = tarfile.TarInfo('gcc-16.2.0/configure'); item.size = 5
        archive.addfile(item, io.BytesIO(b'hello'))
    folder = toolchain.extract(path, tmp_path / 'extract', 'gcc')
    assert (folder / 'configure').read_bytes() == b'hello'


def test_source_pins_match_the_existing_toolchain_recipe():
    recipe = (ROOT / 'sdk/publisher/Dockerfile.toolchain').read_text()
    for record in toolchain.SOURCES.values():
        assert record['url'] in recipe and record['sha256'] in recipe


@pytest.mark.parametrize('outcome', ['passed', 'failed', 'timed_out'])
def test_real_host_command_outcomes_are_retained(tmp_path, outcome):
    code = {'passed': 'print("built")', 'failed': 'print("compiler failed"); raise SystemExit(7)',
            'timed_out': 'import time; print("started", flush=True); time.sleep(10)'}[outcome]
    command = [sys.executable, '-c', code]
    records = []
    if outcome == 'passed':
        toolchain.run_step('host-command', command, tmp_path, os.environ.copy(), tmp_path, records, timeout=5)
    else:
        expected = subprocess.CalledProcessError if outcome == 'failed' else subprocess.TimeoutExpired
        with pytest.raises(expected):
            toolchain.run_step('host-command', command, tmp_path, os.environ.copy(), tmp_path, records,
                               timeout=5 if outcome == 'failed' else .2)
    retained = json.loads((tmp_path / 'commands.json').read_text())
    assert retained == records and len(retained) == 1
    assert retained[0]['status'] == outcome and retained[0]['elapsed_seconds'] >= 0
    if outcome == 'timed_out':
        assert retained[0]['timeout_seconds'] == .2
    else:
        assert retained[0]['returncode'] == (0 if outcome == 'passed' else 7)
    assert (tmp_path / 'host-command.log').read_text().strip() == {
        'passed': 'built', 'failed': 'compiler failed', 'timed_out': 'started'}[outcome]

# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject unprepared or ambiguous emulator source before cross compilation."""
import importlib.util
import io
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    spec = importlib.util.spec_from_file_location('linux_qemu', ROOT / 'scripts/build_sdk_linux_qemu.py')
    qemu = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qemu)
finally:
    sys.path.pop(0)


def source_archive(tmp_path, extra=(), version=None, missing=None):
    files = {'VERSION': version or qemu.VERSION, 'configure': '#!/bin/sh\n',
             'hw/arm/prime_g2_peripherals.c': 'board',
             'include/hw/arm/prime_g2_peripherals.h': 'header',
             'hw/arm/prime_g2_bch.c': 'bch'}
    if missing:
        del files[missing]
    path = tmp_path / 'source.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        entries = [(qemu.SOURCE_ROOT + '/' + name, text) for name, text in files.items()]
        for name, text in [*entries, *extra]:
            payload = text.encode(); member = tarfile.TarInfo(name); member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return path


def test_prepared_prime_source_is_extracted(tmp_path):
    source = qemu.extract_source(source_archive(tmp_path), tmp_path / 'out')
    assert (source / 'VERSION').read_text() == qemu.VERSION
    assert (source / 'hw/arm/prime_g2_peripherals.c').read_text() == 'board'


@pytest.mark.parametrize('path', [
    '../escape', '/absolute', 'unrelated/file',
    qemu.SOURCE_ROOT + '/VERSION', qemu.SOURCE_ROOT + '/../escape',
    qemu.SOURCE_ROOT + '/scripts/__pycache__/x.pyc', qemu.SOURCE_ROOT + '/.git/config',
])
def test_unexpected_source_members_rejected_before_extraction(tmp_path, path):
    output = tmp_path / 'out'
    with pytest.raises(ValueError):
        qemu.extract_source(source_archive(tmp_path, [(path, 'bad')]), output)
    assert not output.exists()


def test_other_qemu_version_rejected(tmp_path):
    with pytest.raises(ValueError, match='version differs'):
        qemu.extract_source(source_archive(tmp_path, version='0.0'), tmp_path / 'out')


def test_unpatched_qemu_source_rejected(tmp_path):
    with pytest.raises(ValueError, match='Missing prepared Prime'):
        qemu.extract_source(source_archive(tmp_path, missing='hw/arm/prime_g2_peripherals.c'), tmp_path / 'out')

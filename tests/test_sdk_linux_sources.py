# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact source selection and integrity checks before desktop redistribution."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_native_linux_sources import source_files, source_identity, source_urls, verify_files

DATA = {'sample_1.0.dsc': b'descriptor', 'sample_1.0.orig.tar.xz': b'original',
        'sample_1.0-2.debian.tar.xz': b'patches'}


def record(version='1:1.0-2'):
    lines = ['Package: sample', 'Version: ' + version, 'Checksums-Sha256:']
    for name, data in DATA.items():
        lines.append(' ' + hashlib.sha256(data).hexdigest() + ' ' + str(len(data)) + ' ' + name)
    return '\n'.join(lines) + '\n'


def test_exact_source_version_and_duplicate_mirrors():
    text = record('1:1.0-1') + '\n' + record() + '\n' + record()
    files = source_files(text, 'sample', '1:1.0-2')
    assert set(files) == set(DATA)
    with pytest.raises(ValueError, match='missing'):
        source_files(text, 'sample', '1:1.0-3')
    bad = record().replace(hashlib.sha256(b'original').hexdigest(), 'a' * 64)
    with pytest.raises(ValueError, match='conflicting'):
        source_files(record() + '\n' + bad, 'sample', '1:1.0-2')


@pytest.mark.parametrize('old,new', [('sample_1.0.dsc', '../sample_1.0.dsc'),
    ('sample_1.0.dsc', '/sample_1.0.dsc'), ('sample_1.0.dsc', 'sample_1.0.orig.tar.xz'),
    ('Checksums-Sha256', 'Files'), ('Version: 1:1.0-2', 'Version: 1:1.0-2\nVersion: 1:1.0-2')])
def test_invalid_source_records_rejected(old, new):
    with pytest.raises(ValueError):
        source_files(record().replace(old, new), 'sample', '1:1.0-2')


@pytest.mark.parametrize('name,version', [('--option', '1'), ('sample', '1;command'),
    ('../sample', '1'), ('sample', '1 other'), ('sample', None)])
def test_source_arguments_are_data(name, version):
    with pytest.raises(ValueError):
        source_identity(name, version)


def uris():
    return '\n'.join(f"'https://example.org/pool/{name}' {name} {len(data)} SHA256:{hashlib.sha256(data).hexdigest()}"
                     for name, data in DATA.items())


def test_source_uris_cover_only_selected_files():
    files = source_files(record(), 'sample', '1:1.0-2')
    assert set(source_urls('APT information\n' + uris(), files)) == set(DATA)
    for text in (uris().replace('https:', 'http:'), uris().replace('example.org', 'user:password@example.org'),
                 uris().replace('sample_1.0.dsc', 'unexpected.dsc'), uris().splitlines()[0],
                 uris() + '\n' + uris().splitlines()[0]):
        with pytest.raises(ValueError):
            source_urls(text, files)


def test_downloads_match_exact_files_sizes_hashes_and_types(tmp_path):
    files = source_files(record(), 'sample', '1:1.0-2')
    for name, data in DATA.items():
        (tmp_path / name).write_bytes(data)
    verify_files(tmp_path, files)
    path = tmp_path / 'sample_1.0.dsc'
    path.write_bytes(b'X' * len(DATA[path.name]))
    with pytest.raises(ValueError, match='differs'):
        verify_files(tmp_path, files)
    path.write_bytes(DATA[path.name])
    (tmp_path / 'unexpected').write_bytes(b'')
    with pytest.raises(ValueError, match='file set'):
        verify_files(tmp_path, files)
    (tmp_path / 'unexpected').unlink()
    path.unlink(); path.symlink_to(tmp_path / 'sample_1.0.orig.tar.xz')
    with pytest.raises(ValueError, match='differs'):
        verify_files(tmp_path, files)

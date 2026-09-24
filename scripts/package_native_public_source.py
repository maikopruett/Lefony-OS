#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Snapshot the reviewed public working tree for desktop source distribution.

Includes tracked and non-ignored files, with the same boundary checks as
make check-public. No Git metadata, ignored build inputs or device captures.
The manifest describes actual working-tree bytes, not a clean-commit release.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

from check_public_tree import check_paths

ROOT = Path(__file__).resolve().parents[1]


def public_paths(root):
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=root, check=True, capture_output=True)
    return sorted(set(result.stdout.decode('utf-8').rstrip('\0').split('\0'))) if result.stdout else []


def snapshot(root):
    names = public_paths(root)
    problems = check_paths(root, names)
    if problems:
        raise ValueError('\n'.join(problems))
    files = {}
    for name in names:
        path = root / name
        if not path.exists():
            continue  # A tracked deletion is part of the working tree.
        files[name] = (path.read_bytes(), 0o755 if path.stat().st_mode & 0o111 else 0o644)
    if not files:
        raise ValueError('The public working tree is empty')
    # Check the snapshot's inputs again before writing; a concurrent edit must
    # not sneak new private material into the interval after the first check.
    problems = check_paths(root, names)
    if problems:
        raise ValueError('\n'.join(problems))
    return names, files


def unchanged(root, names, files):
    if public_paths(root) != names:
        raise ValueError('Public file selection changed during source packaging')
    for name in names:
        path = root / name
        if name not in files:
            if path.exists() or path.is_symlink():
                raise ValueError('A deleted public file reappeared: ' + name)
            continue
        data, mode = files[name]
        if (path.is_symlink() or not path.is_file() or path.read_bytes() != data
                or (0o755 if path.stat().st_mode & 0o111 else 0o644) != mode):
            raise ValueError('Public source changed during packaging: ' + name)


def package(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Use a new public-source output directory')
    names, files = snapshot(root)
    revision = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=root,
                              text=True, capture_output=True)
    output.mkdir(parents=True)
    temporary = output / 'source.tar.gz.partial'
    try:
        with temporary.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb',
                filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, (data, mode) in files.items():
                item = tarfile.TarInfo('lefony/' + name)
                item.size, item.mode = len(data), mode
                archive.addfile(item, io.BytesIO(data))
        with tarfile.open(temporary) as archive:
            members = archive.getmembers()
            if len(members) != len(files):
                raise ValueError('Public source archive member count differs')
            for member, (name, (data, mode)) in zip(members, files.items()):
                if (member.name != 'lefony/' + name or not member.isfile()
                        or member.mode != mode or archive.extractfile(member).read() != data):
                    raise ValueError('Public source archive differs: ' + name)
        unchanged(root, names, files)
        with temporary.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest = {
            'schema': 1, 'source_kind': 'working-tree',
            'base_commit': revision.stdout.strip() if revision.returncode == 0 else None,
            'archive': 'source.tar.gz', 'archive_sha256': checksum,
            'files': {name: {'sha256': hashlib.sha256(data).hexdigest(),
                             'bytes': len(data), 'mode': mode}
                      for name, (data, mode) in files.items()},
        }
        temporary.replace(output / 'source.tar.gz')
        (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n',
                                              encoding='utf-8', newline='\n')
        return manifest
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = package(ROOT, args.output)
    print(json.dumps({'archive_sha256': result['archive_sha256'], 'files': len(result['files'])}))

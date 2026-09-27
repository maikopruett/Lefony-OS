#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Collect corresponding public sources for the separate dual-boot release.

Uses Git's tracked/nonignored selection, including prepared upstream changes.
Never includes generated build outputs, local keys, HP images or NAND backups.
"""
import argparse
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
import subprocess
import tarfile

from check_public_tree import check_paths, PUBLIC_KEYS


def selected(root):
    result = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root)
    for name in sorted(set(result.decode().rstrip('\0').split('\0'))):
        path = root / name
        if not path.exists():
            continue
        if path.is_dir():  # Include pinned upstream submodules.
            yield from (name + '/' + child for child in selected(path))
        else:
            yield name


def package(args):
    roots = {'lefony': Path(__file__).resolve().parents[1],
             'website': args.website, 'upsilon': args.firmware,
             'uboot-menu': args.boot, 'uboot-recovery': args.recovery}
    paths = {label: list(selected(root)) for label, root in roots.items()}
    problems = check_paths(roots['lefony'], paths['lefony'])
    if problems:
        raise ValueError('\n'.join(problems))
    if args.output.exists():
        raise ValueError('Use a new source archive path')
    manifest = {'schema': 1, 'kind': 'prepared-working-tree', 'files': {}}
    with args.output.open('xb') as out, gzip.GzipFile(fileobj=out, mode='wb', filename='', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w') as archive:
        for name, config in (('uboot-menu.config', args.boot_config), ('uboot-recovery.config', args.recovery_config)):
            data = config.read_bytes()
            item = tarfile.TarInfo(name); item.size = len(data); item.mode = 0o644
            archive.addfile(item, io.BytesIO(data))
            manifest['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        for label, root in roots.items():
            for name in paths[label]:
                path = root / name
                if Path(name).parts[0] in ('.git', '.local', 'node_modules', 'output') or '__pycache__' in Path(name).parts:
                    raise ValueError('Non-source directory selected: ' + label + '/' + name)
                if path.is_symlink():
                    if not path.resolve().is_relative_to(root.resolve()):
                        raise ValueError('External source link: ' + name)
                    archive.add(path, arcname=label + '/' + name, recursive=False)
                    continue
                data = path.read_bytes()
                if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{40,}', data):
                    allowed = label == 'lefony' and name in PUBLIC_KEYS and hashlib.sha256(data).hexdigest() == PUBLIC_KEYS[name]
                    if not allowed:
                        raise ValueError('Private key material selected: ' + label + '/' + name)
                item = tarfile.TarInfo(label + '/' + name)
                item.size = len(data)
                item.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(item, io.BytesIO(data))
                manifest['files'][item.name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        data = (json.dumps(manifest, sort_keys=True) + '\n').encode()
        item = tarfile.TarInfo('SOURCE-MANIFEST.json'); item.size = len(data); item.mode = 0o644
        archive.addfile(item, io.BytesIO(data))
    print(json.dumps({'files': len(manifest['files']), 'bytes': args.output.stat().st_size,
                      'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('website', 'firmware', 'boot', 'recovery', 'boot-config', 'recovery-config', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    package(p.parse_args())

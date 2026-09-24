# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent, exclusively owned synthetic emulator media. Never physical media."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import shutil
import zipfile
from build import digest, exclusive, write_json

MAX_OVERLAY = 512 * 1024 * 1024


def location(project, name):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}', name):
        raise ValueError('workspace name must be 1–48 letters, digits, underscores or hyphens')
    directory = project / '.lefony/workspaces' / name
    for path in (project / '.lefony', directory.parent, directory):
        if path.is_symlink():
            raise ValueError('workspace symlinks are forbidden')
    return directory


@contextmanager
def opened(project, name):
    directory = location(project, name)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive(directory / '.lock'):
        descriptor = directory / 'workspace.json'
        overlay = directory / 'nand.overlay'
        if not descriptor.exists() and not overlay.exists():
            overlay.write_bytes(b'PG2OVL1\n')
            write_json(descriptor, {'schema': 1, 'kind': 'synthetic-prime-g2', 'app': None})
        if descriptor.is_symlink() or overlay.is_symlink():
            raise ValueError('workspace files must not be symlinks')
        if descriptor.stat().st_size > 4096:
            raise ValueError('workspace descriptor exceeds 4096 bytes')
        state = json.loads(descriptor.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or type(state.get('schema')) is not int or state.get('schema') != 1 or state.get('kind') != 'synthetic-prime-g2':
            raise ValueError('unrecognized workspace; no media was changed')
        with overlay.open('rb') as stream:
            if stream.read(8) != b'PG2OVL1\n' or overlay.stat().st_size > MAX_OVERLAY:
                raise ValueError('invalid or oversized synthetic overlay')
        yield directory, state


def manage(project, action, name, target=None):
    if action in ('info', 'clone', 'export') and not location(project, name).exists():
        raise ValueError('workspace does not exist')
    with opened(project, name) as (directory, state):
        if action == 'info':
            return {**state, 'overlay_bytes': (directory / 'nand.overlay').stat().st_size}
        if action == 'reset':
            (directory / 'nand.overlay').write_bytes(b'PG2OVL1\n')
            write_json(directory / 'workspace.json', {'schema': 1, 'kind': 'synthetic-prime-g2', 'app': None})
        elif action == 'clone':
            dest = location(project, str(target))
            if dest.exists():
                raise ValueError('clone destination already exists')
            dest.mkdir(mode=0o700)
            for name in ('nand.overlay', 'workspace.json'):
                shutil.copyfile(directory / name, dest / name)
        elif action == 'export':
            # Explicit exchange includes saved app content. Bug reports never do.
            with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ('nand.overlay', 'workspace.json'):
                    archive.write(directory / name, name)
                archive.writestr('integrity.json', json.dumps({name: digest(directory / name)
                    for name in ('nand.overlay', 'workspace.json')}))
        else:
            raise ValueError('unsupported workspace operation')
        return {'workspace': name, 'operation': action, 'status': 'complete'}


def restore(project, name, archive_path):
    target = location(project, name)
    if target.exists():
        raise ValueError('restore requires a new workspace name; existing data was preserved')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.restoring')
    temporary.mkdir(mode=0o700)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if len(entries) != 3 or {x.filename for x in entries} != {'workspace.json', 'nand.overlay', 'integrity.json'}:
                raise ValueError('unexpected workspace archive entries')
            for entry in entries:
                limit = MAX_OVERLAY if entry.filename == 'nand.overlay' else 4096
                if entry.file_size > limit or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('oversized or symbolic workspace entry')
                with archive.open(entry) as source, (temporary / entry.filename).open('xb') as output:
                    total = 0
                    while chunk := source.read(65536):
                        total += len(chunk)
                        if total > limit:
                            raise ValueError('expanded workspace entry exceeds limit')
                        output.write(chunk)
        hashes = json.loads((temporary / 'integrity.json').read_text(encoding='utf-8'))
        if hashes != {name: digest(temporary / name) for name in ('workspace.json', 'nand.overlay')}:
            raise ValueError('workspace integrity mismatch')
        state = json.loads((temporary / 'workspace.json').read_text(encoding='utf-8'))
        with (temporary / 'nand.overlay').open('rb') as stream:
            if not isinstance(state, dict) or type(state.get('schema')) is not int or state.get('schema') != 1 or state.get('kind') != 'synthetic-prime-g2' or stream.read(8) != b'PG2OVL1\n':
                raise ValueError('invalid synthetic workspace')
        (temporary / 'integrity.json').unlink()
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'workspace': name, 'operation': 'restore', 'status': 'complete'}

# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-secret local project links; absolute locations never leave this host."""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import tempfile
from lfapp import manifest
from store_client import StoreError


def state_directory():
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/Lefony SDK'
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Lefony SDK'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'lefony-sdk'


def safe_directory(path):
    # Reject links before mkdir/replace, including an existing intermediate path.
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise StoreError('Local store state must not use symbolic links or reparse points.')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


def write_json(path, value):
    safe_directory(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise StoreError('Local store metadata must be a regular file.')
    fd, name = tempfile.mkstemp(prefix='.store-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def registry_directory(root, origin, account_id):
    key = hashlib.sha256((origin + '\n' + account_id).encode()).hexdigest()
    return root / 'projects' / key


def link(project, client, account, app_id, *, state_root=None):
    from store_publish import publication_lock
    from store_listing_sync import pending
    project = project.resolve()
    with publication_lock(project):
        pending(project)
        return _link(project, client, account, app_id, state_root=state_root)


def _link(project, client, account, app_id, *, state_root=None):
    remote = client.app(app_id)
    if remote['app'].get('owner_id') != account['id']:
        raise StoreError('This app belongs to a different store account.')
    target = project.resolve() / '.lefony/store.json'
    already_linked = target.exists()
    value = bind_project(project, client.origin, account['id'], app_id, state_root=state_root)
    # Repeating link must not refresh a stale baseline behind the author's back.
    if not already_linked or not target.with_name('store-base.json').exists():
        from store_listing_sync import snapshot
        observed = snapshot(client, app_id)
        write_json(target.with_name('store-base.json'), {**value, 'revision': observed['revision'], 'content': observed['content']})
    return value


def bind_project(project, origin, account_id, app_id, *, state_root=None):
    """Record explicit project identity, including a not-yet-published attempt."""
    from store_snapshot import read_file
    project = project.resolve()
    metadata = manifest(json.loads(read_file(project, 'app.json', 8192)))
    if metadata['id'] != app_id:
        raise StoreError('The app ID must match app.json. Linking does not rename or overwrite source.')
    value = {'schema': 1, 'origin': origin, 'account_id': account_id, 'app_id': app_id}
    target = project / '.lefony/store.json'
    safe_directory(target.parent)
    if target.is_symlink():
        raise StoreError('Project link must not be a symbolic link.')
    if target.exists():
        if json.loads(read_file(project, '.lefony/store.json', 8192)) != value:
            raise StoreError('Project is already linked differently. Use project unlink first.')
    directory = registry_directory(state_root or state_directory(), origin, account_id)
    entry = directory / (hashlib.sha256(str(project).encode()).hexdigest() + '.json')
    # Publish the link only after the private host index was writable. The index
    # is advisory; listing rechecks the current link and marks missing folders.
    write_json(entry, {**value, 'path': str(project)})
    write_json(target, value)
    return value


def projects(origin, account_id, *, state_root=None):
    directory = registry_directory(state_root or state_directory(), origin, account_id)
    if not directory.exists():
        return []
    safe_directory(directory)
    result = []
    for entry in sorted(directory.glob('*.json')):
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > 16384:
            raise StoreError('Invalid local project index.')
        value = json.loads(entry.read_text(encoding='utf-8'))
        if value.get('origin') != origin or value.get('account_id') != account_id or not isinstance(value.get('path'), str):
            raise StoreError('Invalid local project index.')
        target = Path(value['path']) / '.lefony/store.json'
        present = target.is_file() and not target.is_symlink() and target.stat().st_size <= 8192
        expected = {key: value[key] for key in ('schema', 'origin', 'account_id', 'app_id')}
        present = present and json.loads(target.read_text(encoding='utf-8')) == expected
        result.append({**value, 'linked': bool(present)})
    return result


def unlink(project):
    from store_publish import publication_lock
    from store_listing_sync import pending
    project = project.resolve()
    with publication_lock(project):
        pending(project)
        return _unlink(project)


def _unlink(project):
    target = project.resolve() / '.lefony/store.json'
    if not target.exists() and not target.is_symlink():
        return {'linked': False}
    safe_directory(target.parent)
    if target.is_symlink() or not target.is_file():
        raise StoreError('Project link must be a regular file.')
    target.unlink()
    return {'linked': False}

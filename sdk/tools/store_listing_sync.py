# SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewable three-way listing pulls. No source upload or calculator access."""
import base64
import html
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

from lfapp import manifest
from store_client import StoreError
from store_listing import canonical, image, parse_json, repository_url, require, text, short_description, short_description_fallback
from store_projects import safe_directory, write_json
from store_publish import identity, local_json, publication_lock, revision, UUID
from store_snapshot import no_link, read_file, sha

FIELDS = ('name', 'short_description', 'description', 'release_notes', 'repository_url', 'icon', 'screenshots')
# A review holds both base and remote text. JSON escaping can use six ASCII
# bytes per permitted UTF-16 unit, even when the underlying UTF-8 is shorter.
PLAN_LIMIT = 131072
SCREEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.png\Z')
FIXED = {'app.json': 8192, 'store/listing.json': 8192, 'store/description.md': 16000,
         'store/release-notes.md': 32000, 'store/icon.png': 262144,
         '.lefony/store-base.json': 65536, '.lefony/store.json': 8192}


def path_limit(name):
    if name in FIXED:
        return FIXED[name]
    if name.startswith('store/screenshots/') and SCREEN.fullmatch(name[len('store/screenshots/'):]):
        return 1048576
    raise StoreError('Unsafe listing file path.')


def optional_file(project, name):
    maximum = path_limit(name)
    path = project
    try:
        for part in name.split('/'):
            path /= part
            require(no_link(path.lstat()), name + ': links are not allowed')
    except FileNotFoundError:
        return None
    return read_file(project, name, maximum)


def checked_content(value):
    require(isinstance(value, dict) and set(value) in (set(FIELDS), set(FIELDS) - {'short_description'}), 'Invalid listing content fields')
    if 'short_description' not in value:
        value = {**value, 'short_description': short_description_fallback(value['description'])}
    require(text(value['short_description'], 120, 'Short description') == value['short_description'] and not any(c in value['short_description'] for c in '\r\n\u2028\u2029'), 'Short description is not normalized')
    for name, limit in (('name', 80), ('description', 2000), ('release_notes', 4000)):
        require(text(value[name], limit, name, name == 'name') == value[name], 'Listing text is not normalized')
    if value['repository_url'] is not None:
        repository_url(value['repository_url'])
    require(isinstance(value['screenshots'], list) and len(value['screenshots']) <= 5, 'Invalid listing screenshots')
    for kind, media in [('icon', value['icon']), *[('screenshot', m) for m in value['screenshots']]]:
        if kind == 'icon' and media is None:
            continue
        require(isinstance(media, dict) and set(media) == {'sha256', 'bytes', 'width', 'height'} and
                isinstance(media['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', media['sha256']) and
                all(type(media[k]) is int for k in ('bytes', 'width', 'height')), 'Invalid listing media descriptor')
        require(57 <= media['bytes'] <= (262144 if kind == 'icon' else 1048576), 'Invalid listing image length')
        require((media['width'] == media['height'] and 64 <= media['width'] <= 512) if kind == 'icon' else
                (160 <= media['width'] <= 1280 and 120 <= media['height'] <= 960), 'Invalid listing image dimensions')
    return value


def snapshot(client, app_id):
    value = client.request('/sdk/apps/' + app_id + '/listing')
    require(isinstance(value, dict) and value.get('schema') == 1 and value.get('app_id') == app_id and
            revision(value.get('revision')) and type(value.get('hidden')) is bool and
            isinstance(value.get('latest_version_key'), str), 'Invalid store listing snapshot')
    value['content'] = checked_content(value.get('content'))
    return value


def local_listing(project):
    raw = {name: optional_file(project, name) for name in FIXED}
    require(raw['app.json'] is not None, 'Choose a project containing app.json')
    app = manifest(parse_json(raw['app.json']))
    config = parse_json(raw['store/listing.json']) if raw['store/listing.json'] is not None else {'schema': 1, 'publish_source': False}
    require(isinstance(config, dict) and set(config) <= {'schema', 'publish_source', 'repository_url', 'short_description'} and
            type(config.get('schema')) is int and config['schema'] == 1 and type(config.get('publish_source')) is bool,
            'store/listing.json: expected schema 1 and a boolean publish_source')
    content = {'name': app['name'], 'description': text((raw['store/description.md'] or b'').decode('utf-8'), 2000, 'Description'),
               'release_notes': text((raw['store/release-notes.md'] or b'').decode('utf-8'), 4000, 'Release notes'),
               'repository_url': repository_url(config['repository_url']) if 'repository_url' in config else None,
               'icon': None, 'screenshots': []}
    saved = parse_json(raw['.lefony/store-base.json']) if raw['.lefony/store-base.json'] else {}
    previous = saved.get('content', {}).get('short_description') if isinstance(saved, dict) and saved.get('app_id') == app['id'] and isinstance(saved.get('content'), dict) else None
    content['short_description'] = text(config.get('short_description', previous if previous is not None else short_description_fallback(content['description'])), 120, 'Short description')
    directory = project / 'store/screenshots'
    names = []
    if directory.exists() or directory.is_symlink():
        require(no_link(directory.lstat()) and directory.is_dir(), 'Screenshots must be a directory without links')
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entry.name in ('.gitkeep', 'README.md'):
                    continue
                require(SCREEN.fullmatch(entry.name), 'Use PNG screenshot filenames with ASCII letters, numbers, hyphens or underscores')
                names.append('store/screenshots/' + entry.name)
                require(len(names) <= 5, 'At most five screenshots are supported')
        require(len({n.lower() for n in names}) == len(names), 'Screenshot names collide on a case-insensitive host')
    pictures = {}
    for name in ['store/icon.png', *sorted(names)]:
        data = optional_file(project, name)
        raw[name] = data
        if data is not None:
            cleaned, descriptor = image(data, 'icon' if name == 'store/icon.png' else 'screenshot')
            pictures[descriptor['sha256']] = cleaned
            if name == 'store/icon.png':
                content['icon'] = descriptor
            else:
                content['screenshots'].append(descriptor)
    checked_content(content)
    return content, raw, pictures


def hashes(raw):
    return {name: sha(data) if data is not None else None for name, data in sorted(raw.items())}


def merge(base, local, remote, take_local=(), take_remote=()):
    base = checked_content(base) if base is not None else None
    local, remote = checked_content(local), checked_content(remote)
    require(set(take_local) <= set(FIELDS) and set(take_remote) <= set(FIELDS) and
            not set(take_local) & set(take_remote), 'Choose either local or remote once for each listing field')
    merged, conflicts, changes = {}, [], {}
    for field in FIELDS:
        a, b = local[field], remote[field]
        if field in take_local:
            choice = 'local'
        elif field in take_remote:
            choice = 'remote'
        elif a == b or base is not None and b == base[field]:
            choice = 'local'
        elif base is not None and a == base[field] or base is None and a in (None, '', []):
            choice = 'remote'
        else:
            conflicts.append(field)
            choice = 'conflict'
        merged[field] = b if choice == 'remote' else a
        changes[field] = {'choice': choice, 'base': base[field] if base is not None else None, 'local': a, 'remote': b}
    return merged, conflicts, changes


def plan_directory(project, identifier):
    require(isinstance(identifier, str) and UUID.fullmatch(identifier), 'Use the saved listing plan UUID')
    directory = project / '.lefony/listing' / identifier
    for path in (project / '.lefony', directory.parent, directory):
        require(path.exists() and no_link(path.lstat()) and path.is_dir(), 'Listing plan must be a directory without links')
    return directory


def preview(directory, changes, pictures):
    def shown(value):
        if isinstance(value, dict) and 'sha256' in value:
            return '<img alt="Listing image" src="data:image/png;base64,' + base64.b64encode(pictures[value['sha256']]).decode() + '">'
        if isinstance(value, list):
            return ''.join(shown(v) for v in value) or '<p>None</p>'
        return '<pre>' + html.escape(str(value) if value is not None else 'None') + '</pre>'
    rows = ''.join('<section><h2>' + field.replace('_', ' ').title() + ' · ' + value['choice'] + '</h2><div><article><h3>Local</h3>' +
                   shown(value['local']) + '</article><article><h3>Store</h3>' + shown(value['remote']) + '</article></div></section>' for field, value in changes.items())
    (directory / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">'
        '<title>Review listing changes</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#192d24}'
        'section{border-top:1px solid #ccc}section>div{display:grid;grid-template-columns:1fr 1fr;gap:24px}article{min-width:0}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}img{max-width:100%;max-height:320px;margin:4px}'
        '@media(max-width:600px){section>div{grid-template-columns:1fr}}</style><h1>Review listing changes</h1>'
        '<p>These are saved local and store snapshots. Resolve conflicting fields with the listing pull command. '
        'Applying checks both snapshots again before changing project files.</p>' + rows, encoding='utf-8', newline='\n')


def prepare_pull(project, client, account, take_local=(), take_remote=()):
    local, raw, pictures = local_listing(project)
    app_id = manifest(parse_json(raw['app.json']))['id']
    binding = identity(client, account, app_id)
    require(local_json(project, '.lefony/store.json') == binding, 'Link this project to the current account and app before pulling its listing')
    remote = snapshot(client, app_id)
    require(remote['content']['icon'] and remote['content']['screenshots'], 'This stored listing has no complete media set. Add an icon and screenshots before pulling')
    saved = local_json(project, '.lefony/store-base.json')
    base = None
    if isinstance(saved, dict) and all(saved.get(k) == v for k, v in binding.items()):
        require(revision(saved.get('revision')) and saved['revision'] <= remote['revision'], 'Saved listing revision is invalid or newer than the store')
        if 'content' in saved:
            base = checked_content(saved['content'])
    merged, conflicts, changes = merge(base, local, remote['content'], take_local, take_remote)
    for kind, descriptor in [('icon', remote['content']['icon']), *[('screenshot', m) for m in remote['content']['screenshots']]]:
        if descriptor['sha256'] not in pictures:
            data = client.get_image(app_id, descriptor['sha256'])
            cleaned, actual = image(data, kind)
            require(actual == descriptor and data == cleaned, 'Store image differs from the listing snapshot')
            pictures[descriptor['sha256']] = cleaned
    identifier = str(uuid.uuid4())
    directory = project / '.lefony/listing' / identifier
    safe_directory(directory.parent)
    directory.mkdir(mode=0o700)
    # The journal contains bounded copies, not filesystem destinations supplied
    # by the server. There are no tokens, source files or executable packages.
    plan = {**binding, 'plan_id': identifier, 'state': 'review', 'snapshot': remote, 'base': base,
            'local_hashes': hashes(raw), 'take_local': list(take_local), 'take_remote': list(take_remote)}
    write_json(directory / 'plan.json', plan)
    safe_directory(directory / 'media')
    for digest, data in pictures.items():
        (directory / 'media' / (digest + '.png')).write_bytes(data)
    preview(directory, changes, pictures)
    return {'state': 'conflicts' if conflicts else 'review', 'plan_id': identifier, 'revision': remote['revision'],
            'conflicts': conflicts, 'changes': changes, 'preview': str(directory / 'index.html')}


def target_files(raw, content, local, media):
    target = dict(raw)
    if content['name'] != local['name']:
        app = parse_json(raw['app.json'])
        app['name'] = content['name']
        manifest(app)
        target['app.json'] = canonical(app) + b'\n'
    for field, path in (('description', 'store/description.md'), ('release_notes', 'store/release-notes.md')):
        if content[field] != local[field] or raw[path] is None:
            target[path] = (content[field] + '\n').encode('utf-8')
    if content['short_description'] != local['short_description'] or content['repository_url'] != local['repository_url'] or raw['store/listing.json'] is None or 'short_description' not in parse_json(raw['store/listing.json']):
        config = parse_json(raw['store/listing.json']) if raw['store/listing.json'] is not None else {'schema': 1, 'publish_source': False}
        config['short_description'] = content['short_description']
        config.pop('repository_url', None)
        if content['repository_url'] is not None:
            config['repository_url'] = content['repository_url']
        target['store/listing.json'] = canonical(config) + b'\n'
    if content['icon'] != local['icon']:
        require(content['icon'] is not None, 'Pull cannot implicitly remove the local icon')
        target['store/icon.png'] = media[content['icon']['sha256']]
    if content['screenshots'] != local['screenshots']:
        require(content['screenshots'], 'Pull cannot implicitly remove all screenshots')
        for name in raw:
            if name.startswith('store/screenshots/'):
                target[name] = None
        for index, descriptor in enumerate(content['screenshots']):
            target[f'store/screenshots/{index + 1:02d}.png'] = media[descriptor['sha256']]
    return target


def replace_file(project, name, expected, data):
    """Compare immediately before a bounded atomic replacement."""
    path_limit(name)
    require(optional_file(project, name) == expected, name + ': changed during listing apply; user edits were preserved')
    path = project / name
    safe_directory(path.parent)
    if data is None:
        if expected is not None:
            path.unlink()
        return
    require(len(data) <= path_limit(name), 'Listing output exceeds its limit')
    fd, temporary = tempfile.mkstemp(prefix='.listing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require(optional_file(project, name) == expected, name + ': changed during listing apply; user edits were preserved')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def encoded(raw):
    return {name: base64.b64encode(data).decode('ascii') if data is not None else None for name, data in raw.items()}


def decoded(value):
    require(isinstance(value, dict) and len(value) <= 20, 'Invalid listing journal')
    result = {}
    for name, data in value.items():
        limit = path_limit(name)
        require(data is None or isinstance(data, str) and len(data) <= (limit + 2) // 3 * 4, 'Invalid listing journal data')
        result[name] = None if data is None else base64.b64decode(data, validate=True)
    return result


def rollback(project, directory):
    journal = parse_json(read_file(directory, 'journal.json', 20000000))
    before, after = decoded(journal['before']), decoded(journal['after'])
    require(set(before) == set(after), 'Invalid listing journal paths')
    # Validate every path first; never partially roll back over unknown user edits.
    for name in before:
        require(optional_file(project, name) in (before[name], after[name]), name + ': edited after interrupted pull; retain the saved journal and reconcile this file first')
    # Restore the old baseline first, so an interrupted rollback cannot let a
    # subsequent publish acknowledge changes it has not finished restoring.
    names = sorted(before, key=lambda n: (n != '.lefony/store-base.json', n))
    for name in names:
        current = optional_file(project, name)
        if current != before[name]:
            replace_file(project, name, current, before[name])
    journal['state'] = 'rolled_back'
    write_json(directory / 'journal.json', journal)
    return {'state': 'rolled_back', 'plan_id': directory.name}


def apply_pull(project, client, account, identifier, take_local=(), take_remote=()):
    directory = plan_directory(project, identifier)
    plan = parse_json(read_file(directory, 'plan.json', PLAN_LIMIT))
    local, raw, pictures = local_listing(project)
    binding = identity(client, account, manifest(parse_json(raw['app.json']))['id'])
    require(all(plan.get(k) == v for k, v in binding.items()) and local_json(project, '.lefony/store.json') == binding,
            'Listing plan belongs to a different store, account or app')
    require(plan.get('state') == 'review' and hashes(raw) == plan.get('local_hashes'), 'Local listing changed since review. Prepare a fresh listing pull')
    remote = snapshot(client, binding['app_id'])
    require(remote == plan['snapshot'], 'Store listing changed since review. Prepare a fresh listing pull')
    require(not set(take_local) & set(take_remote), 'Choose either local or remote once for each listing field')
    local_choices = (set(plan['take_local']) - set(take_remote)) | set(take_local)
    remote_choices = (set(plan['take_remote']) - set(take_local)) | set(take_remote)
    merged, conflicts, changes = merge(plan['base'], local, remote['content'], local_choices, remote_choices)
    if conflicts:
        return {'state': 'conflicts', 'plan_id': identifier, 'conflicts': conflicts, 'changes': changes, 'preview': str(directory / 'index.html')}
    for kind, descriptor in [('icon', remote['content']['icon']), *[('screenshot', m) for m in remote['content']['screenshots']]]:
        data = read_file(directory, 'media/' + descriptor['sha256'] + '.png', 1048576)
        cleaned, actual = image(data, kind)
        require(data == cleaned and actual == descriptor, 'Saved listing media changed since review')
        pictures[descriptor['sha256']] = data
    target = target_files(raw, merged, local, pictures)
    # The merge base is exactly the store snapshot, even when local edits are
    # retained. Remembering the merged result would conceal future conflicts.
    target['.lefony/store-base.json'] = canonical({**binding, 'revision': remote['revision'], 'content': remote['content']}) + b'\n'
    changed = {name: data for name, data in target.items() if data != raw.get(name)}
    before = {name: raw.get(name) for name in changed}
    require(hashes(local_listing(project)[1]) == plan['local_hashes'], 'Local listing changed while applying; retry with a fresh review')
    journal = {'schema': 1, 'state': 'applying', 'before': encoded(before), 'after': encoded(changed)}
    write_json(directory / 'journal.json', journal)
    try:
        for name in sorted(changed, key=lambda n: (n == '.lefony/store-base.json', n)):
            replace_file(project, name, before[name], changed[name])
        journal['state'] = 'applied'
        write_json(directory / 'journal.json', journal)
    except (OSError, ValueError):
        rollback(project, directory)
        raise
    plan['state'] = 'applied'
    write_json(directory / 'plan.json', plan)
    return {'state': 'applied', 'plan_id': identifier, 'revision': remote['revision'], 'changed_files': sorted(changed)}


def pending(project):
    root = project / '.lefony/listing'
    if not root.exists():
        return
    require(no_link(root.lstat()) and root.is_dir(), 'Listing state must be a directory without links')
    for path in root.iterdir():
        if not UUID.fullmatch(path.name):
            continue
        directory = plan_directory(project, path.name)
        if (directory / 'journal.json').exists():
            journal = parse_json(read_file(directory, 'journal.json', 20000000))
            if journal.get('state') == 'applying':
                raise StoreError('An interrupted listing pull needs recovery: lefony-sdk listing recover ' + path.name)


def pull(project, client, account, *, dry_run=False, plan_id=None, take_local=(), take_remote=()):
    project = Path(project).absolute()
    require(project.exists() and no_link(project.lstat()) and project.is_dir(), 'Project must be a directory without links')
    project = project.resolve()
    with publication_lock(project):
        pending(project)
        if plan_id is None:
            result = prepare_pull(project, client, account, take_local, take_remote)
            if dry_run or result['conflicts']:
                return result
            plan_id = result['plan_id']
        return apply_pull(project, client, account, plan_id, take_local, take_remote)


def recover(project, plan_id):
    project = Path(project).absolute()
    require(project.exists() and no_link(project.lstat()) and project.is_dir(), 'Project must be a directory without links')
    project = project.resolve()
    with publication_lock(project):
        directory = plan_directory(project, plan_id)
        journal = parse_json(read_file(directory, 'journal.json', 20000000))
        require(journal.get('state') == 'applying', 'Only an interrupted listing pull can be recovered')
        return rollback(project, directory)

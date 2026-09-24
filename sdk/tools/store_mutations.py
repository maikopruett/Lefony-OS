# SPDX-License-Identifier: GPL-3.0-or-later
"""Recoverable listing-only edits and explicit store withdrawal. No build or device I/O."""
import base64
from pathlib import Path
import time
import uuid

from store_client import APP_ID, StoreError
from store_listing import canonical, image, parse_json, require, short_description
from store_listing_sync import checked_content, local_listing, pending, snapshot
from store_projects import safe_directory, state_directory, write_json
from store_publish import UUID, identity, local_json, publication_lock, retry, revision
from store_snapshot import no_link, read_file, sha

REQUEST_LIMIT = 8388608


def operation_directory(root, identifier):
    require(isinstance(identifier, str) and UUID.fullmatch(identifier), 'Use the saved operation UUID')
    path = root / '.lefony/operations' / identifier
    for parent in (root / '.lefony', path.parent, path):
        require(parent.exists() and no_link(parent.lstat()) and parent.is_dir(), 'Operation state must be a directory without links')
    return path


def save(root, binding, kind, body, content):
    encoded = canonical(body)
    require(len(encoded) <= (REQUEST_LIMIT if kind == 'listing' else 4096), 'Listing operation exceeds its request limit')
    path = root / '.lefony/operations' / body['request_id']
    safe_directory(path.parent)
    path.mkdir(mode=0o700)
    record = {**binding, 'kind': kind, 'request_sha256': sha(encoded), 'content': content}
    # Both durable files precede the first mutation request. No credentials,
    # source archive, package bytes or local filesystem paths leave this host.
    write_json(path / 'request.json', body)
    write_json(path / 'operation.json', record)
    return path, record


def load(root, identifier, client, account, kind, app_id=None):
    path = operation_directory(root, identifier)
    record = parse_json(read_file(path, 'operation.json', 65536))
    require(isinstance(record, dict) and isinstance(record.get('app_id'), str) and APP_ID.fullmatch(record['app_id']), 'Invalid saved app identity')
    expected = identity(client, account, app_id or record['app_id'])
    require(set(record) == set(expected) | {'kind', 'request_sha256', 'content'} and
            all(record.get(k) == v for k, v in expected.items()) and record['kind'] == kind,
            'Saved operation belongs to a different store, account, app or action')
    # Pretty JSON may escape Unicode; the transmitted canonical form remains
    # bounded by REQUEST_LIMIT. Only saved presentation fields are permitted.
    body = parse_json(read_file(path, 'request.json', REQUEST_LIMIT + 65536))
    require(isinstance(body, dict) and set(body) == {'schema', 'request_id', 'base_revision'} | ({'content'} if kind == 'listing' else set()) and
            type(body['schema']) is int and body['schema'] == 1 and body['request_id'] == identifier and revision(body['base_revision']) and
            len(canonical(body)) <= (REQUEST_LIMIT if kind == 'listing' else 4096) and sha(canonical(body)) == record['request_sha256'],
            'Saved operation request changed or is invalid')
    if kind == 'listing':
        target = checked_content(record['content'])
        require(target['icon'] and target['screenshots'] and isinstance(body['content'], dict) and set(body['content']) in (set(target), set(target) - {'short_description'}), 'Invalid saved listing')
        for field in ('name', 'short_description', 'description', 'release_notes', 'repository_url'):
            require((field == 'short_description' and field not in body['content']) or body['content'][field] == target[field], 'Saved listing text changed')
        require(isinstance(body['content']['screenshots'], list) and len(body['content']['screenshots']) == len(target['screenshots']), 'Saved screenshot order changed')
        for role, value, wanted in [('icon', body['content']['icon'], target['icon']),
                                    *[('screenshot', a, b) for a, b in zip(body['content']['screenshots'], target['screenshots'])]]:
            require(isinstance(value, dict) and len(value) == 1, 'Invalid saved image')
            if set(value) == {'sha256'}:
                require(value['sha256'] == wanted['sha256'], 'Saved image reference changed')
            else:
                require(set(value) == {'png'} and isinstance(value['png'], str), 'Invalid saved PNG')
                try:
                    raw = base64.b64decode(value['png'], validate=True)
                except ValueError:
                    raise StoreError('Invalid saved PNG encoding') from None
                cleaned, actual = image(raw, role)
                require(cleaned == raw and actual == wanted, 'Saved image bytes changed')
    else:
        require(record['content'] is None, 'Withdrawal must not contain listing content')
    return path, record, body


def accept(root, path, record, body, response, *, project=None):
    require(isinstance(response, dict) and response.get('schema') == 1 and response.get('state') == 'accepted' and
            isinstance(response.get('operation'), dict) and isinstance(response.get('current'), dict), 'Store did not return an operation receipt')
    operation, current = response['operation'], response['current']
    expected = {'id': body['request_id'], 'app_id': record['app_id'], 'kind': record['kind'],
                'request_sha256': record['request_sha256'], 'base_revision': body['base_revision'], 'content': record['content']}
    compared = dict(operation)
    if record['kind'] == 'listing' and 'short_description' not in record['content'] and isinstance(compared.get('content'), dict):
        compared['content'] = {k: v for k, v in compared['content'].items() if k != 'short_description'}
    require(all(compared.get(k) == v for k, v in expected.items()) and revision(operation.get('revision')) and
            operation['revision'] > body['base_revision'] and current.get('app_id') == record['app_id'] and
            revision(current.get('revision')) and current['revision'] >= operation['revision'], 'Store receipt differs from this saved operation')
    if record['kind'] == 'listing':
        require(operation['revision'] == body['base_revision'] + 1 and isinstance(operation.get('release_id'), str) and
                UUID.fullmatch(operation['release_id']), 'Invalid listing commit revision or release')
    else:
        require(operation.get('release_id') is None, 'Withdrawal receipt must not describe a new release')
    result = {'state': 'accepted', 'operation_id': path.name, 'operation': operation, 'current': current}
    try:
        write_json(path / 'receipt.json', response)
        if project is not None:
            binding = {k: record[k] for k in ('schema', 'origin', 'account_id', 'app_id')}
            old = local_json(project, '.lefony/store-base.json')
            if local_json(project, '.lefony/store.json') == binding and (old is None or isinstance(old, dict) and
                    all(old.get(k) == v for k, v in binding.items()) and revision(old.get('revision')) and old['revision'] <= operation['revision']):
                write_json(project / '.lefony/store-base.json', {**binding, 'revision': operation['revision'], 'content': record['content']})
    except (OSError, ValueError):
        command = 'listing push' if record['kind'] == 'listing' else 'apps withdraw ' + record['app_id']
        result['warning'] = 'Store operation accepted, but local tracking could not be saved. Restore write access and run ' + command + ' --status ' + path.name + '.'
    return result


def transfer(root, identifier, client, account, kind, *, operation='resume', app_id=None, project=None, emit=print, sleep=time.sleep):
    require(operation in ('resume', 'status'), 'Choose operation status or resume')
    path, record, body = load(root, identifier, client, account, kind, app_id)
    if project is not None and operation == 'resume':
        require(local_json(project, '.lefony/store.json') == identity(client, account, record['app_id']), 'Relink the original app before resuming its listing operation')
    endpoint = '/sdk/apps/' + record['app_id']
    call = lambda action: retry(action, emit=emit, sleep=sleep)
    try:
        response = call(lambda: client.request(endpoint + '/operations/' + identifier))
    except StoreError as error:
        if error.status != 404:
            raise
        if operation == 'status':
            return {'state': 'unaccepted', 'operation_id': identifier, 'message': 'No accepted receipt was found. Resume this saved operation to retry its exact request.'}
        emit('Submitting saved operation ' + identifier)
        try:
            response = call(lambda: client.request(endpoint + ('/listing' if kind == 'listing' else '/withdraw'),
                                                  'PUT' if kind == 'listing' else 'POST', body))
        except StoreError as failure:
            # The saved UUID remains authoritative after an ambiguous response.
            # A fresh request must never substitute for this attempt on retry.
            command = 'listing push' if kind == 'listing' else 'apps withdraw ' + record['app_id']
            raise StoreError(str(failure) + ' Saved operation: ' + identifier + '. Run ' + command + ' --status ' + identifier +
                             ' before deciding whether to resume.', failure.status, failure.retry_after, failure.details) from None
    return accept(root, path, record, body, response, project=project)


def push(project, client, account, *, dry_run=False, operation_id=None, operation='resume', emit=print, sleep=time.sleep):
    project = Path(project).resolve()
    require(not dry_run or operation_id is None, 'Use --dry-run for a new review, or status/resume for a saved operation')
    with publication_lock(project):
        pending(project)
        if operation_id is not None:
            return transfer(project, operation_id, client, account, 'listing', operation=operation, project=project, emit=emit, sleep=sleep)
        content, raw, pictures = local_listing(project)
        app_id = parse_json(raw['app.json'])['id']
        binding = identity(client, account, app_id)
        require(local_json(project, '.lefony/store.json') == binding, 'Link this project to the current account before editing its listing')
        require(content['icon'] and content['screenshots'], 'Listing edits require an icon and at least one screenshot; missing local files never delete remote media')
        remote = snapshot(client, app_id)
        require(not remote['hidden'] and remote.get('release'), 'This app needs an editable release before changing its listing')
        saved = local_json(project, '.lefony/store-base.json')
        require(isinstance(saved, dict) and all(saved.get(k) == v for k, v in binding.items()) and revision(saved.get('revision')),
                'Record a listing baseline with project link or listing pull first')
        changes = {field: {'local': content[field], 'remote': remote['content'][field]} for field in content if content[field] != remote['content'][field]}
        if saved['revision'] != remote['revision']:
            return {'state': 'conflicts', 'base_revision': saved['revision'], 'current_revision': remote['revision'], 'changes': changes,
                    'message': 'Listing changed. Run listing pull --dry-run and review/merge before pushing.'}
        if dry_run:
            return {'state': 'review', 'app_id': app_id, 'base_revision': saved['revision'], 'changes': changes}
        short_description(content['short_description'])
        if not changes:
            return {'state': 'unchanged', 'app_id': app_id, 'revision': saved['revision']}
        owned = {m['sha256'] for m in [remote['content']['icon'], *remote['content']['screenshots']] if m is not None}
        def media(descriptor):
            digest = descriptor['sha256']
            return {'sha256': digest} if digest in owned else {'png': base64.b64encode(pictures[digest]).decode('ascii')}
        body = {'schema': 1, 'request_id': str(uuid.uuid4()), 'base_revision': saved['revision'],
                'content': {**content, 'icon': media(content['icon']), 'screenshots': [media(m) for m in content['screenshots']]}}
        path, _ = save(project, binding, 'listing', body, content)
        return transfer(project, path.name, client, account, 'listing', project=project, emit=emit, sleep=sleep)


def withdraw(client, account, app_id, *, dry_run=False, operation_id=None, operation='resume', state_root=None, emit=print, sleep=time.sleep):
    require(isinstance(app_id, str) and APP_ID.fullmatch(app_id), 'Invalid app ID')
    require(not dry_run or operation_id is None, 'Use --dry-run for a new review, or status/resume for a saved operation')
    binding = identity(client, account, app_id)
    # Withdrawal does not require a local source project. Its private journal is
    # isolated by store/account/app, and does not advance any project's baseline.
    root = (state_root or state_directory()) / 'operations' / sha(canonical(binding))
    with publication_lock(root):
        if operation_id is not None:
            return transfer(root, operation_id, client, account, 'withdraw', operation=operation, app_id=app_id, emit=emit, sleep=sleep)
        current = client.request('/sdk/apps/' + app_id + '/publication')
        require(current.get('app_id') == app_id and current.get('exists') is True and revision(current.get('revision')), 'Invalid owned app revision')
        if dry_run:
            return {'state': 'review', 'app_id': app_id, 'base_revision': current['revision'],
                    'effect': 'Withdraw every active version and pending submission. Existing installations and ratings remain.'}
        body = {'schema': 1, 'request_id': str(uuid.uuid4()), 'base_revision': current['revision']}
        path, _ = save(root, binding, 'withdraw', body, None)
        return transfer(root, path.name, client, account, 'withdraw', app_id=app_id, emit=emit, sleep=sleep)

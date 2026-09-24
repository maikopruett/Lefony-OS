# SPDX-License-Identifier: GPL-3.0-or-later
"""Metadata-only SDK edits, ambiguous responses, and operation identity boundaries."""
import base64
import copy
import json
from pathlib import Path
import uuid

import pytest
from test_sdk_store_publication import project
from test_sdk_store_listing_sync import Store, ACCOUNT, png
from store_client import StoreClient, StoreError
from store_listing import canonical, image
from store_projects import write_json
from store_publish import identity
from store_snapshot import sha
import store_mutations as mutations


class MutationStore(Store):
    def __init__(self, project):
        super().__init__(project)
        self.current['release']['id'] = str(uuid.uuid4())
        self.calls, self.receipts, self.losses, self.active = [], {}, 0, 2

    def request(self, path, method='GET', body=None):
        self.calls.append((path, method, copy.deepcopy(body)))
        if method == 'GET' and path.endswith('/listing'):
            return copy.deepcopy(self.current)
        if path.endswith('/publication'):
            return {'app_id': 'hello-app', 'exists': True, 'revision': self.current['revision']}
        if '/operations/' in path:
            key = path.rsplit('/', 1)[-1]
            if key not in self.receipts:
                raise StoreError('Not accepted', 404)
            return self.receipt(key)
        assert (method, path.rsplit('/', 1)[-1]) in [('PUT', 'listing'), ('POST', 'withdraw')]
        key = body['request_id']
        if key not in self.receipts:
            if body['base_revision'] != self.current['revision']:
                raise StoreError('Listing changed', 409)
            kind = 'listing' if method == 'PUT' else 'withdraw'
            if kind == 'listing':
                content = copy.deepcopy(body['content'])
                def picture(value, role):
                    if 'sha256' in value:
                        return image(self.images[value['sha256']], role)[1]
                    data, descriptor = image(base64.b64decode(value['png']), role)
                    self.images[descriptor['sha256']] = data
                    return descriptor
                content['icon'] = picture(content['icon'], 'icon')
                content['screenshots'] = [picture(m, 'screenshot') for m in content['screenshots']]
                self.edit(**content)
            else:
                content = None
                self.current['revision'] += 1 + self.active
                self.active = 0
            self.receipts[key] = {'id': key, 'app_id': 'hello-app', 'kind': kind, 'base_revision': body['base_revision'],
                'revision': self.current['revision'], 'request_sha256': sha(canonical(body)), 'content': content,
                'release_id': self.current['release']['id'] if kind == 'listing' else None, 'created_at': 1}
        if self.losses:
            self.losses -= 1
            raise StoreError('Synthetic lost acknowledgement')
        return self.receipt(key)

    def receipt(self, key):
        return {'schema': 1, 'state': 'accepted', 'operation': copy.deepcopy(self.receipts[key]),
                'current': {'app_id': 'hello-app', 'revision': self.current['revision'], 'active': self.active}}


def linked(project):
    store = MutationStore(project)
    binding = identity(store, ACCOUNT, 'hello-app')
    write_json(project / '.lefony/store.json', binding)
    write_json(project / '.lefony/store-base.json', {**binding, 'revision': store.current['revision'], 'content': store.current['content']})
    return store


def push(project, store, **kwargs):
    return mutations.push(project, store, ACCOUNT, emit=lambda _: None, sleep=lambda _: None, **kwargs)


def test_metadata_dry_run_then_push_sends_only_changed_presentation_without_building(project):
    store = linked(project)
    (project / 'src/main.cpp').write_text('unfinished source is deliberately not compilable')
    (project / 'store/description.md').write_text('New description')
    (project / 'store/listing.json').write_text('{"schema":1,"publish_source":false,"short_description":"A local example."}')
    (project / 'store/icon.png').write_bytes(png(96, 96, (180, 20, 60)))
    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file() and '.lefony' not in p.parts}
    review = push(project, store, dry_run=True)
    assert review['state'] == 'review' and set(review['changes']) == {'description', 'icon'}
    assert all(method == 'GET' for _, method, _ in store.calls)
    result = push(project, store)
    assert result['state'] == 'accepted' and result['operation']['kind'] == 'listing'
    assert {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file() and '.lefony' not in p.parts} == before
    request = next(body for _, method, body in store.calls if method == 'PUT')
    assert set(request) == {'schema', 'request_id', 'base_revision', 'content'}
    assert set(request['content']['icon']) == {'png'} and set(request['content']['screenshots'][0]) == {'sha256'}
    assert b'unfinished' not in canonical(request) and b'publish_source' not in canonical(request) and b'private_local_path' not in canonical(request)
    base = json.loads((project / '.lefony/store-base.json').read_text())
    assert base['content'] == store.current['content'] and base['revision'] == result['operation']['revision']
    assert push(project, store)['state'] == 'unchanged'


def test_lost_acknowledgement_recovers_saved_request_even_after_source_edits(project):
    store = linked(project)
    (project / 'store/description.md').write_text('Original submitted edit')
    store.losses = 3
    with pytest.raises(StoreError, match='Saved operation:'):
        push(project, store)
    operation = next((project / '.lefony/operations').iterdir())
    requests = [body for _, method, body in store.calls if method == 'PUT']
    assert len(requests) == 3 and requests[0] == requests[1] == requests[2]
    (project / 'store/description.md').write_text('Future draft')
    store.edit(release_notes='A later website edit')
    result = push(project, store, operation_id=operation.name, operation='status')
    assert result['operation']['content']['description'] == 'Original submitted edit'
    assert result['current']['revision'] > result['operation']['revision']
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == result['operation']['revision']
    assert (project / 'store/description.md').read_text() == 'Future draft'
    assert len([method for _, method, _ in store.calls if method == 'PUT']) == 3
    assert push(project, store)['state'] == 'conflicts'


def test_resume_of_unaccepted_operation_uses_saved_bytes_not_current_project(project, monkeypatch):
    store = linked(project)
    (project / 'store/description.md').write_text('Saved edit')
    request = store.request
    def disconnected(path, method='GET', body=None):
        if method == 'PUT':
            raise StoreError('Connection lost before submission')
        return request(path, method, body)
    monkeypatch.setattr(store, 'request', disconnected)
    with pytest.raises(StoreError):
        push(project, store)
    operation = next((project / '.lefony/operations').iterdir())
    assert push(project, store, operation_id=operation.name, operation='status')['state'] == 'unaccepted'
    assert not store.receipts
    (project / 'store/description.md').write_text('Later draft')
    monkeypatch.setattr(store, 'request', request)
    result = push(project, store, operation_id=operation.name)
    assert result['operation']['content']['description'] == 'Saved edit'
    assert (project / 'store/description.md').read_text() == 'Later draft'


def test_old_receipt_never_rolls_back_a_newer_baseline(project):
    store = linked(project)
    (project / 'store/description.md').write_text('First edit')
    first = push(project, store)
    (project / 'store/description.md').write_text('Second edit')
    second = push(project, store)
    result = push(project, store, operation_id=first['operation_id'], operation='status')
    assert result['operation']['revision'] == first['operation']['revision']
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == second['operation']['revision']


@pytest.mark.parametrize('change', ['account', 'origin', 'request', 'link', 'symlink'])
def test_changed_identity_or_journal_is_rejected_before_request(project, change):
    store = linked(project)
    (project / 'store/description.md').write_text('Edited')
    accepted = push(project, store)
    directory = project / '.lefony/operations' / accepted['operation_id']
    if change == 'account':
        record = json.loads((directory / 'operation.json').read_text());record['account_id'] = 'github:other'
        write_json(directory / 'operation.json', record)
    if change == 'origin':
        store.origin = 'https://other.example'
    if change == 'request':
        body = json.loads((directory / 'request.json').read_text());body['content']['description'] = 'Tampered'
        write_json(directory / 'request.json', body)
    if change == 'link':
        (project / '.lefony/store.json').unlink()
    if change == 'symlink':
        path = directory / 'request.json';data = path.read_bytes();path.unlink()
        target = project / 'elsewhere.json';target.write_bytes(data);path.symlink_to(target)
    calls = len(store.calls)
    with pytest.raises(ValueError):
        push(project, store, operation_id=accepted['operation_id'])
    assert len(store.calls) == calls


def test_missing_media_cannot_delete_remote_content(project):
    store = linked(project)
    (project / 'store/icon.png').unlink()
    with pytest.raises(ValueError, match='require an icon'):
        push(project, store)
    assert not store.calls


def test_receipt_mismatch_never_advances_baseline(project, monkeypatch):
    store = linked(project)
    (project / 'store/description.md').write_text('Edit')
    original = store.receipt
    def corrupt(key):
        value = original(key);value['operation']['request_sha256'] = '0' * 64
        return value
    monkeypatch.setattr(store, 'receipt', corrupt)
    with pytest.raises(ValueError, match='receipt differs'):
        push(project, store)
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == 4


def test_local_tracking_failure_reports_remote_acceptance(project, monkeypatch):
    store = linked(project)
    (project / 'store/description.md').write_text('Edit')
    write = mutations.write_json
    def fail_receipt(path, value):
        if path.name == 'receipt.json':
            raise OSError('Disk full')
        write(path, value)
    monkeypatch.setattr(mutations, 'write_json', fail_receipt)
    result = push(project, store)
    assert result['state'] == 'accepted' and '--status ' + result['operation_id'] in result['warning']
    assert len(store.receipts) == 1


def test_withdrawal_has_no_source_dependency_and_replay_preserves_new_publications(project, tmp_path):
    store = linked(project)
    state = tmp_path / 'host-state'
    def withdraw(**kwargs):
        return mutations.withdraw(store, ACCOUNT, 'hello-app', state_root=state, emit=lambda _: None, sleep=lambda _: None, **kwargs)
    assert withdraw(dry_run=True)['state'] == 'review'
    assert not store.receipts
    store.losses = 3
    with pytest.raises(StoreError, match='Saved operation:'):
        withdraw()
    identifier = next(iter(store.receipts))
    assert store.active == 0
    store.active = 1;store.current['revision'] += 4
    result = withdraw(operation_id=identifier)
    assert result['current']['active'] == 1
    assert result['operation']['revision'] < result['current']['revision']
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == 4
    assert result['operation']['content'] is None


def test_only_exact_listing_put_allows_large_json(monkeypatch):
    client = StoreClient()
    captured = []
    monkeypatch.setattr(client, '_request', lambda *args, **kwargs: captured.append(args) or {})
    body = {'content': 'x' * 200000}
    client.request('/sdk/apps/hello-app/listing', 'PUT', body)
    assert captured[0][2] == canonical(body)
    for path, method in [('/sdk/apps/hello-app/withdraw', 'POST'), ('/sdk/apps/hello-app/listing', 'POST'),
                         ('/sdk/apps/hello-app/listing/media/' + 'a' * 64, 'PUT'), ('/sdk/uploads', 'POST')]:
        with pytest.raises(StoreError, match='too large'):
            client.request(path, method, body)
    with pytest.raises(StoreError, match='too large'):
        client.request('/sdk/apps/hello-app/listing', 'PUT', {'content': 'x' * mutations.REQUEST_LIMIT})

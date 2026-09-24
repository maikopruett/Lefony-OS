# SPDX-License-Identifier: GPL-3.0-or-later
"""SDK transfer recovery and account/revision boundaries; Worker integration is separate."""
import copy
import json
from pathlib import Path
import uuid

import pytest
from test_sdk_store_publication import project, prepared
from store_client import StoreClient, StoreError
from store_listing import canonical, submission_content
from store_projects import link
from store_publish import CHUNK, publication_lock, publish, transfer
from store_snapshot import sha, verify

ACCOUNT = {'id': 'github:123', 'login': 'publisher'}


class UploadStore:
    origin = 'https://store.example'

    def __init__(self):
        self.upload_id = str(uuid.uuid4())
        self.current_revision = 0
        self.saved = None
        self.chunks = {}
        self.files = set()
        self.receipt = None
        self.calls = []
        self.lose = None
        self.losses = 0
        self.state = 'uploading'
        self.status_patch = {}

    def app(self, app_id):
        return {'app': {'id': app_id, 'owner_id': ACCOUNT['id'], 'revision': self.current_revision}}

    def status(self):
        if self.receipt:
            return {'schema': 1, 'state': 'accepted', 'upload_id': self.upload_id, 'release': self.receipt}
        value = {'schema': 1, 'upload_id': self.upload_id, 'state': self.state,
                 'base_revision': self.saved['base_revision'], 'submission_sha256': sha(canonical(self.saved['submission'])),
                 'chunk_bytes': CHUNK, 'expires_at': 1999999999, 'retry_after': 0,
                 'parts': [{'file_index': i, 'part_index': p, 'bytes': len(b), 'hash': sha(b)} for (i, p), b in self.chunks.items()],
                 'files': [{'file_index': i, 'bytes': self.saved['submission']['files'][i]['bytes'],
                            'hash': self.saved['submission']['files'][i]['sha256']} for i in self.files]}
        return {**value, **self.status_patch}

    def dropped(self, operation):
        if self.lose == operation and self.losses:
            self.losses -= 1
            raise StoreError('Response was lost.')

    def request(self, path, method='GET', body=None):
        self.calls.append((path, method, copy.deepcopy(body)))
        if path.endswith('/listing'):
            return {'schema': 1, 'app_id': path.split('/')[3], 'revision': self.current_revision, 'hidden': False,
                    'latest_version_key': '', 'release': None, 'content': submission_content(self.saved['submission']) if self.saved else
                    {'name': 'Hello app', 'description': 'Recorded store listing', 'release_notes': '', 'repository_url': None, 'icon': None, 'screenshots': []}}
        if path.endswith('/publication'):
            return {'app_id': path.split('/')[3], 'exists': self.current_revision != 0, 'revision': self.current_revision, 'latest_version_key': ''}
        if path.startswith('/sdk/receipts?'):
            if self.receipt:
                return {'schema': 1, 'state': 'accepted', 'release': self.receipt}
            raise StoreError('No accepted receipt.', 404)
        if path == '/sdk/uploads':
            self.saved = copy.deepcopy(body)
            result = self.status()
            self.dropped('start')
            return result
        if path == '/sdk/uploads/' + self.upload_id:
            return self.status()
        if path.endswith('/complete'):
            index = int(path.split('/')[-2])
            data = b''.join(self.chunks[(index, n)] for n in range((self.saved['submission']['files'][index]['bytes'] + CHUNK - 1) // CHUNK))
            self.files.add(index)
            self.dropped('complete')
            return {'upload_id': self.upload_id, 'file_index': index, 'bytes': len(data), 'sha256': sha(data)}
        if path.endswith('/finalize'):
            if not self.receipt:
                submission = self.saved['submission']
                self.current_revision += 4
                self.receipt = {'id': str(uuid.uuid4()), 'app_id': submission['app']['id'], 'version': submission['app']['version'],
                    'submission_hash': sha(canonical(submission)), 'source_sha256': submission['files'][0]['sha256'],
                    'unsigned_package_sha256': submission['files'][1]['sha256'], 'local_report_sha256': submission['files'][2]['sha256'],
                    'package_sha256': 'a' * 64, 'state': 'published', 'available': True,
                    'publication_revision': self.current_revision, 'revision': self.current_revision}
            self.dropped('finalize')
            return self.status()
        if path.endswith('/cancel'):
            self.state = 'cancelled'
            return {'schema': 1, 'upload_id': self.upload_id, 'state': 'cancelled'}
        raise AssertionError(path)

    def put_chunk(self, path, data):
        self.calls.append((path, 'PUT', data))
        fields = path.split('/')
        key = (int(fields[-3]), int(fields[-1]))
        if key in self.chunks:
            assert self.chunks[key] == data
        self.chunks[key] = data
        self.dropped('chunk')
        return {'upload_id': self.upload_id, 'file_index': key[0], 'part_index': key[1], 'bytes': len(data), 'sha256': sha(data)}


def run(project, attempt, server, operation='resume', account=ACCOUNT):
    return publish(project, None, None, None, server, account, attempt_id=attempt.name, operation=operation,
                   emit=lambda _: None, sleep=lambda _: None, state_root=project.parent / 'private-state')


def test_publishes_allowlisted_bytes_records_identity_and_idempotent_receipt(project):
    result = prepared(project); attempt = Path(result['directory']); server = UploadStore()
    published = run(project, attempt, server)
    assert published['published'] is True
    assert published['app_url'] == server.origin + '/#apps/hello-app'
    assert set(server.files) == set(range(len(verify(attempt)['files'])))
    assert not any(b'private_local_path' in data or b'never-upload' in data for data in server.chunks.values())
    for index, descriptor in enumerate(verify(attempt)['files']):
        data = b''.join(data for (i, _), data in sorted(server.chunks.items()) if i == index)
        assert data == (attempt / 'upload' / descriptor['path']).read_bytes()
    remote = json.loads((attempt / 'remote.json').read_text())
    assert remote['account_id'] == ACCOUNT['id'] and remote['upload_id'] == server.upload_id
    assert 'token' not in remote and 'path' not in remote
    count = len(server.chunks)
    assert run(project, attempt, server)['release']['id'] == published['release']['id']
    assert len(server.chunks) == count


@pytest.mark.parametrize('operation', ['start', 'chunk', 'complete', 'finalize'])
def test_lost_acknowledgement_retries_identical_operation(project, operation):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    server.lose, server.losses = operation, 1
    assert run(project, attempt, server)['published'] is True
    if operation == 'start':
        calls = [c[2] for c in server.calls if c[0] == '/sdk/uploads']
        assert len(calls) == 2 and calls[0] == calls[1]
    if operation == 'chunk':
        calls = [c for c in server.calls if c[1] == 'PUT']
        assert calls[0] == calls[1]


def test_resume_after_process_failure_and_original_source_edits(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    server.lose, server.losses = 'chunk', 3
    with pytest.raises(StoreError, match='lost'):
        run(project, attempt, server)
    first = server.chunks.copy()
    (project / 'src/main.cpp').write_text('unfinished edits for the next attempt')
    (project / 'store/description.md').write_text('new description')
    calls = len(server.calls)
    assert run(project, attempt, server)['published']
    assert all(server.chunks[k] == v for k, v in first.items())
    first_path = '/sdk/uploads/' + server.upload_id + '/files/0/parts/0'
    assert not any(path == first_path and method == 'PUT' for path, method, _ in server.calls[calls:])


def test_stale_website_revision_stops_before_build_and_old_receipt_does_not_refresh(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    run(project, attempt, server)
    server.current_revision += 1
    server.receipt['revision'] = server.current_revision
    run(project, attempt, server)
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == server.receipt['publication_revision']
    with pytest.raises(StoreError, match='Listing changed'):
        publish(project, None, None, None, server, ACCOUNT)
    # Repeating project link is not an implicit pull or stale-edit override.
    link(project, server, ACCOUNT, 'hello-app', state_root=project.parent / 'private-state')
    with pytest.raises(StoreError, match='Listing changed'):
        publish(project, None, None, None, server, ACCOUNT)


def test_explicit_new_link_records_baseline_but_wrong_identity_cannot_resume(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore(); server.current_revision = 8
    link(project, server, ACCOUNT, 'hello-app', state_root=project.parent / 'private-state')
    assert json.loads((project / '.lefony/store-base.json').read_text())['revision'] == 8
    server.lose, server.losses = 'chunk', 3
    with pytest.raises(StoreError): run(project, attempt, server)
    before = len(server.calls)
    with pytest.raises(ValueError, match='different bytes, store, account'):
        run(project, attempt, server, account={'id': 'github:456', 'login': 'other'})
    assert len(server.calls) == before


def test_tampered_file_rejected_before_resume_but_status_and_cancel_remain_available(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    server.lose, server.losses = 'chunk', 3
    with pytest.raises(StoreError): run(project, attempt, server)
    (attempt / 'upload/package.lfapp').unlink()
    before = len(server.calls)
    with pytest.raises(ValueError, match='missing'): run(project, attempt, server)
    assert len(server.calls) == before
    assert run(project, attempt, server, operation='status')['state'] == 'uploading'
    assert run(project, attempt, server, operation='cancel')['state'] == 'cancelled'


def test_rejects_conflicting_remote_chunk_and_does_not_finalize(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    server.lose, server.losses = 'chunk', 3
    with pytest.raises(StoreError): run(project, attempt, server)
    data = server.chunks[(0, 0)]
    server.chunks[(0, 0)] = b'x' * len(data)
    with pytest.raises(ValueError, match='remote chunk differs'): run(project, attempt, server)
    assert server.receipt is None


def test_live_lock_and_symlink_attempt_rejected(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    with publication_lock(project):
        with pytest.raises(StoreError, match='Another publication'): run(project, attempt, server)
    other = project / '.lefony/publish' / str(uuid.uuid4())
    other.symlink_to(attempt, target_is_directory=True)
    with pytest.raises(ValueError, match='without links'): run(project, other, server)
    assert not server.calls


def test_streams_multiple_chunks_and_recovers_a_middle_chunk(project):
    for index in range(3):
        (project / f'src/large{index}.h').write_text('//' + chr(65 + index) * 200000)
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    original = server.put_chunk
    interrupted = False
    def put_chunk(path, data):
        nonlocal interrupted
        if path.endswith('/files/0/parts/1') and not interrupted:
            interrupted = True
            server.lose, server.losses = 'chunk', 3
        return original(path, data)
    server.put_chunk = put_chunk
    with pytest.raises(StoreError): run(project, attempt, server)
    assert set(server.chunks) == {(0, 0), (0, 1)}
    previous = len(server.calls)
    assert run(project, attempt, server)['published']
    assert (0, 2) in server.chunks
    assert not any(method == 'PUT' and path.endswith(('/files/0/parts/0', '/files/0/parts/1')) for path, method, _ in server.calls[previous:])


def test_local_disk_failure_after_commit_still_reports_accepted_release(project, monkeypatch):
    import store_publish
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    original = store_publish.write_json
    def fail_receipt(path, value):
        if path.name == 'receipt.json': raise OSError('No space left on device')
        return original(path, value)
    monkeypatch.setattr(store_publish, 'write_json', fail_receipt)
    result = run(project, attempt, server)
    assert result['published'] and result['release']['id'] == server.receipt['id']
    assert 'local tracking could not be saved' in result['warning']


def test_removed_unaccepted_staging_requires_fresh_attempt_but_old_receipt_still_resumes(project):
    attempt = Path(prepared(project)['directory']); server = UploadStore()
    server.lose, server.losses = 'chunk', 3
    with pytest.raises(StoreError): run(project, attempt, server)
    original = server.request
    def removed(path, method='GET', body=None):
        if path == '/sdk/uploads/' + server.upload_id:
            raise StoreError('Removed upload.', 404)
        return original(path, method, body)
    server.request = removed
    count = len([c for c in server.calls if c[0] == '/sdk/uploads'])
    with pytest.raises(StoreError, match='fresh publication'):
        run(project, attempt, server)
    assert len([c for c in server.calls if c[0] == '/sdk/uploads']) == count
    assert run(project, attempt, server, operation='status')['state'] == 'not_found'
    # An accepted transaction remains discoverable via the read-only receipt.
    server.request = original
    released = run(project, attempt, server)
    server.request = removed
    assert run(project, attempt, server)['release']['id'] == released['release']['id']


def test_https_serialization_and_chunk_header(monkeypatch):
    client = StoreClient('https://store.example', token='lfsdk1_' + '01' * 32)
    requests = []
    def transport(request, ca_file):
        requests.append(request)
        return 200, 'application/json', None, 0, b'{"ok":true}'
    monkeypatch.setattr('store_client.exchange', transport)
    client.request('/sdk/uploads', 'POST', {'z': 'é 🌍', 'a': 1})
    assert requests[-1].data == canonical({'z': 'é 🌍', 'a': 1})
    chunk = b'\0binary\xff'
    client.put_chunk('/sdk/uploads/' + str(uuid.uuid4()) + '/files/0/parts/0', chunk)
    headers = dict(requests[-1].header_items())
    assert requests[-1].data == chunk and headers['X-lefony-sha256'] == sha(chunk)
    assert headers['Content-type'] == 'application/octet-stream'
    assert not {'Cookie', 'Origin'} & set(headers)
    with pytest.raises(StoreError): client.put_chunk('/sdk/logout', chunk)
    with pytest.raises(StoreError): client.put_chunk('/sdk/uploads/' + str(uuid.uuid4()) + '/files/0/parts/0', b'x' * (CHUNK + 1))
    with pytest.raises(StoreError): client.request('/sdk/../auth/login')

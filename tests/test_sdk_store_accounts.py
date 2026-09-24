# SPDX-License-Identifier: GPL-3.0-or-later
"""Hermetic account lifecycle, credential boundary and local project tests."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from store_accounts import authenticated, login, logout
from store_client import StoreClient, StoreError, store_origin
from store_credentials import Credentials
from store_projects import link, projects, unlink
from source import collect


class MemoryKeyring:
    def __init__(self):
        self.values = {}
        self.fail_save = self.fail_read = False

    def get_password(self, service, user):
        if self.fail_read:
            raise RuntimeError('sensitive backend details')
        return self.values.get((service, user))

    def set_password(self, service, user, value):
        if self.fail_save:
            raise RuntimeError('sensitive backend details')
        self.values[service, user] = value

    def delete_password(self, service, user):
        self.values.pop((service, user), None)


class AccountServer:
    origin = 'https://store.example'

    def __init__(self):
        self.token = None
        self.calls = []
        self.mode = 'success'
        self.user = {'id': 'github:123', 'login': 'publisher'}
        self.session_id = str(uuid.uuid4())
        self.responses = []

    def response(self):
        return {'account': copy.deepcopy(self.user), 'session_id': self.session_id,
                'expires_at': 1999999999, 'scopes': ['store:read', 'store:publish']}

    def request(self, path, method='GET', body=None, *, authenticated=True):
        self.calls.append((path, method, copy.deepcopy(body), authenticated, self.token))
        if path == '/sdk/authorizations':
            self.challenge = body['token_hash']
            return {'schema': 1, 'id': 'ab' * 32, 'user_code': 'ABCD-EFGH',
                    'verification_uri': self.origin + '/api/store/sdk/authorize?id=' + 'ab' * 32, 'expires_in': 600, 'interval': 5}
        if path.endswith('/poll'):
            assert hashlib.sha256(body['token'].encode()).hexdigest() == self.challenge
            if self.responses:
                result = self.responses.pop(0)
                if isinstance(result, Exception):
                    raise result
                return result
            if self.mode == 'denied':
                raise StoreError('Denied.', 403)
            if self.mode == 'pending':
                return {'state': 'pending'}
            return {'state': 'authorized', **self.response()}
        if path.endswith('/cancel') or path == '/sdk/logout':
            if self.mode == 'offline':
                raise StoreError('Network unavailable.')
            return {'ok': True}
        if path == '/sdk/me':
            if self.mode == 'expired':
                raise StoreError('Session expired.', 401)
            return self.response()
        raise AssertionError(path)


def sign_in(server, credentials, output=None, **kwargs):
    clock = [0]
    def sleep(seconds): clock[0] += seconds
    return login(server, credentials, emit=(output if output is not None else []).append,
                 sleep=sleep, monotonic=lambda: clock[0], open_browser=False, **kwargs)


def test_login_hashed_request_secure_store_and_no_token_output(tmp_path):
    server = AccountServer(); backend = MemoryKeyring(); saved = Credentials(server.origin, backend=backend); output = []
    result = sign_in(server, saved, output)
    assert result['account']['id'] == 'github:123'
    assert server.calls[0][2].keys() == {'token_hash', 'label'}
    token = saved.read()['token']
    assert token not in '\n'.join(output)
    assert server.calls[1][3] is False
    assert server.calls[1][2] == {'token': token}
    assert Credentials('https://other.example', backend=backend).read() is None
    assert list(tmp_path.iterdir()) == []
    assert authenticated(server, saved)['account'] == result['account']


def test_dropped_poll_pending_and_slowdown_retry_the_same_credential():
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring())
    server.responses = [StoreError('Lost response.'), {'state': 'pending'}, StoreError('Slow down.', 429, 10)]
    sign_in(server, saved)
    polls = [c for c in server.calls if c[0].endswith('/poll')]
    assert len(polls) == 4 and len({c[2]['token'] for c in polls}) == 1
    assert len([c for c in server.calls if c[0] == '/sdk/authorizations']) == 1


@pytest.mark.parametrize('mode', ['denied', 'pending'])
def test_denial_timeout_cancel_and_preserve_previous_credential(mode):
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring())
    sign_in(server, saved); previous = saved.read(); server.calls.clear(); server.mode = mode
    with pytest.raises(StoreError): sign_in(server, saved)
    assert saved.read() == previous
    assert server.calls[-1][0].endswith('/cancel')


def test_storage_failure_cancels_remote_and_redacts_backend_error():
    server = AccountServer(); backend = MemoryKeyring(); saved = Credentials(server.origin, backend=backend)
    backend.fail_save = True
    with pytest.raises(StoreError, match='Could not save') as error: sign_in(server, saved)
    assert 'sensitive' not in str(error.value)
    assert server.calls[-1][0].endswith('/cancel')
    assert backend.values == {}


def test_browser_failure_prints_copyable_url_and_interrupt_cancels():
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring()); output = []
    def browser(_): raise RuntimeError('No browser')
    def interrupted(_): raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        login(server, saved, emit=output.append, browser_open=browser, sleep=interrupted)
    assert any('Browser could not be opened' in line for line in output)
    assert server.calls[-1][0].endswith('/cancel')
    assert saved.read() is None


def test_account_switch_revokes_old_session_without_reusing_ownership():
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring())
    sign_in(server, saved); previous = saved.read()
    server.user = {'id': 'github:456', 'login': 'other'}; server.session_id = str(uuid.uuid4())
    sign_in(server, saved)
    assert saved.read()['account']['id'] == 'github:456'
    assert saved.read()['token'] != previous['token']
    assert any(c[0] == '/sdk/logout' and c[4] == previous['token'] for c in server.calls)
    assert server.token == saved.read()['token']


def test_expiry_revocation_and_logout_network_failure():
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring())
    sign_in(server, saved); original = saved.read(); server.mode = 'offline'
    with pytest.raises(StoreError): logout(server, saved)
    assert saved.read() == original
    server.mode = 'success'; assert logout(server, saved) == {'signed_out': True}
    assert saved.read() is None
    sign_in(server, saved); server.mode = 'expired'
    with pytest.raises(StoreError): authenticated(server, saved)
    assert saved.read() is None


def test_unexpected_account_or_scope_rejected():
    server = AccountServer(); saved = Credentials(server.origin, backend=MemoryKeyring())
    sign_in(server, saved); server.user = {'id': 'github:456', 'login': 'other'}
    with pytest.raises(StoreError, match='identity changed'): authenticated(server, saved)
    server.responses = [{'state': 'authorized', **server.response(), 'scopes': ['repository:all']}]
    with pytest.raises(StoreError, match='permissions'): sign_in(server, saved)


@pytest.mark.parametrize('origin', ['http://site.example', 'https://user:secret@site.example', 'https://site.example/path',
                                  'https://site.example?token=x', 'https://site.example/#x', 'https://site.example:0',
                                  'https://site.example:99999', 'https://site.example\n', 'https://site.example\\x'])
def test_reject_bad_store_origins(origin):
    with pytest.raises(StoreError): store_origin(origin)


def test_canonical_store_origin():
    assert store_origin('https://STORE.example:443/') == 'https://store.example'
    assert store_origin('https://[::1]:8443') == 'https://[::1]:8443'


def test_paginated_clients_follow_every_page_and_reject_loops():
    client = StoreClient('https://store.example')
    pages = [{'apps': [{'id': 'first'}], 'next': 'first'}, {'apps': [{'id': 'second'}], 'next': None}]
    paths = []
    def request(path): paths.append(path); return pages.pop(0)
    client.request = request
    assert [a['id'] for a in client.apps()] == ['first', 'second']
    assert paths == ['/sdk/apps', '/sdk/apps?after=first']
    pages[:] = [{'apps': [{'id': 'first'}], 'next': 'first'}, {'apps': [{'id': 'first'}], 'next': 'first'}]
    with pytest.raises(StoreError): client.apps()


def project_at(tmp_path):
    path = tmp_path / 'local project'; (path / 'src').mkdir(parents=True)
    (path / 'app.json').write_text(json.dumps({'id': 'sample', 'name': 'Sample', 'version': '1.0.0', 'abi': 1, 'license': 'MIT'}))
    (path / 'src/main.cpp').write_text('extern "C" void lefony_event() {}\n')
    return path


def test_project_link_is_owned_scoped_offline_unlink_and_not_uploaded(tmp_path):
    project = project_at(tmp_path); state = tmp_path / 'private-state'; before = collect(project)
    client = StoreClient('https://store.example')
    client.app = lambda app_id: {'app': {'id': app_id, 'owner_id': 'github:123'}}
    client.request = lambda path: {'schema': 1, 'app_id': 'sample', 'revision': 0, 'hidden': False, 'latest_version_key': '',
                                  'release': None, 'content': {'name': 'Sample', 'description': '', 'release_notes': '', 'repository_url': None, 'icon': None, 'screenshots': []}}
    link(project, client, {'id': 'github:123'}, 'sample', state_root=state)
    assert collect(project) == before
    value = json.loads((project / '.lefony/store.json').read_text())
    assert 'path' not in value and 'token' not in value
    assert projects(client.origin, 'github:123', state_root=state)[0]['linked']
    assert projects(client.origin, 'github:456', state_root=state) == []
    assert projects('https://elsewhere.example', 'github:123', state_root=state) == []
    with pytest.raises(StoreError, match='different store account'): link(project, client, {'id': 'github:456'}, 'sample', state_root=state)
    with pytest.raises(StoreError, match='match app.json'): link(project, client, {'id': 'github:123'}, 'another', state_root=state)
    unlink(project)
    assert not projects(client.origin, 'github:123', state_root=state)[0]['linked']
    assert collect(project) == before


def test_link_rejects_symlink_and_preserves_other_files(tmp_path):
    project = project_at(tmp_path); outside = tmp_path / 'outside'; outside.mkdir()
    (project / '.lefony').symlink_to(outside, target_is_directory=True)
    client = StoreClient('https://store.example'); client.app = lambda _: {'app': {'owner_id': 'github:123'}}
    with pytest.raises(StoreError, match='symbolic'): link(project, client, {'id': 'github:123'}, 'sample', state_root=tmp_path / 'state')
    assert list(outside.iterdir()) == []

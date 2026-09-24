# SPDX-License-Identifier: GPL-3.0-or-later
"""Browser-authorized, scoped SDK sessions. All secret exchanges use POST/TLS."""
import hashlib
import re
import secrets
import time
import webbrowser
from store_client import StoreClient, StoreError
from store_credentials import Credentials, credential


def session_record(response, token):
    if response.get('scopes') != ['store:read', 'store:publish']:
        raise StoreError('Store returned unsupported SDK session permissions.')
    return credential({'schema': 1, 'token': token, 'account': response.get('account'),
                       'session_id': response.get('session_id'), 'expires_at': response.get('expires_at')})


def login(client, credentials, *, label='Lefony SDK', open_browser=True, emit=print,
          browser_open=webbrowser.open, sleep=time.sleep, monotonic=time.monotonic):
    if not isinstance(label, str) or not re.fullmatch(r'[\x20-\x7e]{1,64}', label) or label.strip() != label:
        raise StoreError('Use an SDK session label of 1–64 printable ASCII characters.')
    old = credentials.read()
    token = 'lfsdk1_' + secrets.token_hex(32)
    ticket = client.request('/sdk/authorizations', 'POST', {'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'label': label}, authenticated=False)
    identifier, code = ticket.get('id'), ticket.get('user_code')
    if ticket.get('schema') != 1 or not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{64}', identifier) or not isinstance(code, str) or not re.fullmatch('[A-Z2-9]{4}-[A-Z2-9]{4}', code) or ticket.get('expires_in') != 600 or ticket.get('interval') != 5:
        raise StoreError('Store returned an invalid sign-in request.')
    verification_uri = client.origin + '/api/store/sdk/authorize?id=' + identifier
    if ticket.get('verification_uri') != verification_uri:
        raise StoreError('Store returned an unexpected sign-in URL.')
    path = '/sdk/authorizations/' + identifier
    saved = False
    try:
        emit('Open ' + verification_uri)
        emit('Enter SDK code ' + code + ' to authorize your GitHub account. This code expires in 10 minutes.')
        if open_browser:
            try:
                browser_open(verification_uri)
            except Exception:
                emit('Browser could not be opened. Use the URL above.')
        deadline = monotonic() + 600
        delay = 5
        while monotonic() < deadline:
            sleep(min(delay, max(0, deadline - monotonic())))
            if monotonic() >= deadline:
                break
            try:
                response = client.request(path + '/poll', 'POST', {'token': token}, authenticated=False)
            except StoreError as error:
                if error.status == 429:
                    delay = max(5, error.retry_after)
                    continue
                # A dropped poll may have issued the session. Retry the same
                # credential rather than starting another grant or account.
                if error.status in (0, 502, 503, 504):
                    delay = min(30, delay + 5)
                    continue
                raise
            delay = 5
            if response.get('state') == 'pending':
                continue
            if response.get('state') != 'authorized':
                raise StoreError('Store returned an invalid sign-in state.')
            record = session_record(response, token)
            credentials.save(record)
            saved = True
            client.token = token
            if old:
                client.token = old['token']
                try:
                    client.request('/sdk/logout', 'POST', {})
                except StoreError:
                    emit('Signed in, but the previous remote session could not be revoked. Manage it at ' + client.origin + '/api/store/sdk/access')
                finally:
                    client.token = token
            emit('Signed in as ' + record['account']['login'] + '.')
            return {key: value for key, value in response.items() if key != 'token'}
        raise StoreError('SDK sign-in expired. Run lefony-sdk login again.')
    finally:
        if not saved:
            try:
                client.request(path + '/cancel', 'POST', {'token': token}, authenticated=False)
            except StoreError:
                emit('Could not confirm remote cancellation. Check SDK access at ' + client.origin + '/api/store/sdk/access')


def authenticated(client, credentials):
    record = credentials.read()
    if record is None:
        raise StoreError('Sign in with lefony-sdk login.')
    client.token = record['token']
    try:
        response = client.request('/sdk/me')
    except StoreError as error:
        if error.status == 401:
            credentials.clear()
        raise
    current = session_record(response, record['token'])
    if current['account']['id'] != record['account']['id'] or current['session_id'] != record['session_id']:
        raise StoreError('Store account identity changed unexpectedly. Sign in again.')
    return response


def logout(client, credentials):
    record = credentials.read()
    if record is not None:
        client.token = record['token']
        client.request('/sdk/logout', 'POST', {})
        credentials.clear()
    client.token = None
    return {'signed_out': True}


def configured(args):
    client = StoreClient(args.store_origin, ca_file=args.store_ca_file)
    return client, Credentials(client.origin)

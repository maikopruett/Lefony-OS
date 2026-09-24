#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in frozen platform-credential test with ephemeral local HTTPS accounts.

Uses the actual SDK login/whoami/apps/logout commands and platform credentials. The
local service authorizes synthetic accounts; this does not test GitHub OAuth,
the production Worker, publication or a browser. Credentials are removed after
the test. Existing credentials at a selected origin cause an immediate refusal.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import uuid

from sdk_frozen_access import command_prefix

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-credentials', action='store_true', required=True,
                        help='explicitly allow temporary test records in the platform credential store')
    parser.add_argument('--access-launcher', type=Path, help='Required on Linux: native isolation launcher')
    parser.add_argument('--interpreter', type=Path, help='Explicit interpreter for the frozen tools')
    parser.add_argument('--bundle-in-place', action='store_true', help='Verify an existing relocated bundle without copying it')
    parser.add_argument('--isolated-secret-service', type=Path,
                        help='Linux only: control directory from sdk_test_secret_service.py; permits lock/restart fixture tests')
    args = parser.parse_args()
    system = platform.system()
    assert system in ('Darwin', 'Linux'), 'This harness supports macOS and Linux'
    if system == 'Linux':
        assert args.access_launcher and os.environ.get('DBUS_SESSION_BUS_ADDRESS'), 'Linux requires a native isolation launcher and explicit session bus'
    backend_name = 'macOS Keychain' if system == 'Darwin' else 'Linux Secret Service'
    fixture = None
    if args.isolated_secret_service:
        assert system == 'Linux'
        fixture = args.isolated_secret_service.resolve(strict=True)
        ready = json.loads((fixture/'ready.json').read_text())
        assert ready['schema'] == 1 and ready['isolated_test_service'] is True
        assert ready['bus_address'] == os.environ['DBUS_SESSION_BUS_ADDRESS']
        assert isinstance(ready['nonce'], str) and len(ready['nonce']) == 64
    bundle, output = args.bundle.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected, name
    actions, results = [], []
    credential_checks = []
    def control(operation, **values):
        assert fixture is not None
        identifier = uuid.uuid4().hex
        request = {'id':identifier, 'nonce':ready['nonce'], 'operation':operation, **values}
        temporary = fixture/'command.partial'; destination = fixture/'command.json'
        assert not temporary.exists() and not destination.exists()
        temporary.write_text(json.dumps(request)); temporary.chmod(0o600); temporary.replace(destination)
        response = fixture/(identifier+'.json'); deadline = time.monotonic()+30
        while not response.exists():
            assert time.monotonic() < deadline, 'Credential fixture control timed out'
            time.sleep(.05)
        value = json.loads(response.read_text())
        assert value['id'] == identifier and value['operation'] == operation and value['status'] == 'passed', value
        credential_checks.append(value)
        return value
    tickets, sessions, issued_tokens = {}, {}, set()
    with tempfile.TemporaryDirectory(prefix='lf-account-', dir='/tmp') as temp:
        folder = Path(temp); relocated = bundle if args.bundle_in_place else folder / 'SDK accounts é'
        if not args.bundle_in_place:
            shutil.copytree(bundle, relocated, symlinks=True)
        prefix, access = command_prefix(ROOT, relocated, folder,
                                        launcher=args.access_launcher, interpreter=args.interpreter)
        program = relocated / 'lefony-sdk'
        cert, key = folder / 'localhost.pem', folder / 'localhost-key.pem'
        subprocess.run([shutil.which('openssl'), 'req', '-x509', '-newkey', 'rsa:2048',
                        '-nodes', '-days', '1', '-subj', '/CN=localhost', '-addext',
                        'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(cert)],
                       capture_output=True, check=True, timeout=15)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *unused): pass
            def reply(self, body, status=200):
                raw = json.dumps(body).encode()
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers()
                self.wfile.write(raw)
            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                assert 0 < length <= 16384
                body = json.loads(self.rfile.read(length))
                if self.path == '/api/store/sdk/authorizations':
                    assert 'Authorization' not in self.headers and set(body) == {'token_hash', 'label'}
                    identifier = uuid.uuid4().hex + uuid.uuid4().hex
                    number = len(tickets) + 1
                    tickets[identifier] = {'digest': body['token_hash'], 'number': number}
                    actions.append({'operation': 'authorize', 'account_number': number})
                    self.reply({'schema': 1, 'id': identifier, 'user_code': 'ABCD-EFGH',
                                'expires_in': 600, 'interval': 5,
                                'verification_uri': origin + '/api/store/sdk/authorize?id=' + identifier})
                elif self.path.endswith('/poll'):
                    identifier = self.path.split('/')[-2]; ticket = tickets[identifier]
                    assert hashlib.sha256(body['token'].encode()).hexdigest() == ticket['digest']
                    record = {'state': 'authorized', 'account': {
                        'id': 'github:' + str(900000000 + ticket['number']),
                        'login': 'sdk-local-fixture-' + str(ticket['number'])},
                        'session_id': str(uuid.uuid4()), 'expires_at': int(time.time()) + 3600,
                        'scopes': ['store:read', 'store:publish']}
                    sessions[body['token']] = record
                    issued_tokens.add(body['token'])
                    actions.append({'operation': 'session', 'account_number': ticket['number']})
                    self.reply(record)
                elif self.path == '/api/store/sdk/logout':
                    token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                    record = sessions.pop(token, None)
                    actions.append({'operation': 'revoke', 'account': record['account']['id'] if record else None})
                    self.reply({'signed_out': True})
                elif self.path.endswith('/cancel'):
                    actions.append({'operation': 'cancel'}); self.reply({'cancelled': True})
                else: self.reply({'error': 'Unknown fixture endpoint'}, 404)
            def do_GET(self):
                token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                record = sessions.get(token)
                if not record:
                    actions.append({'operation': 'unauthorized'})
                    return self.reply({'error': 'Test session revoked'}, 401)
                if self.path == '/api/store/sdk/me':
                    actions.append({'operation': 'me', 'account': record['account']['id']})
                    self.reply(record)
                elif self.path == '/api/store/sdk/apps':
                    actions.append({'operation': 'apps', 'account': record['account']['id']})
                    self.reply({'apps': [{'id': 'fixture-' + state, 'status': state}
                                       for state in ('draft', 'published', 'withdrawn')], 'next': None})
                else: self.reply({'error': 'Unknown fixture endpoint'}, 404)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        origin = f'https://localhost:{server.server_port}'
        other_origin = origin.replace('localhost', '127.0.0.1')
        env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
        env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
        owned = False

        def run(name, *arguments, expected=0, target=origin, environment=None):
            started = time.monotonic()
            command = [*prefix, str(program), *arguments,
                       '--store-origin', target, '--store-ca-file', str(cert)]
            try:
                result = subprocess.run(command, cwd=folder, env=environment or env, capture_output=True, text=True, timeout=35)
            except subprocess.TimeoutExpired:
                (output/(name+'.timeout.json')).write_text(json.dumps({'case':name,'timeout_seconds':35})+'\n')
                raise
            # Tokens live only in memory/Keychain. Fail if a command exposes one.
            assert all(token not in result.stdout + result.stderr for token in issued_tokens)
            (output / (name + '.stdout')).write_text(result.stdout)
            (output / (name + '.stderr')).write_text(result.stderr)
            assert result.returncode == expected, result.stderr
            results.append({'case': name, 'exit_code': result.returncode,
                            'elapsed_seconds': round(time.monotonic() - started, 3)})
            print('PASS: frozen ' + backend_name + ' ' + name, flush=True)
            return result

        try:
            initial = run('initial-empty', 'whoami', expected=1)
            assert 'Sign in with lefony-sdk login' in initial.stderr, 'Origin already has a credential or the platform store is unavailable'
            isolated = run('other-origin-empty', 'whoami', expected=1, target=other_origin)
            assert 'Sign in with lefony-sdk login' in isolated.stderr
            owned = True
            run('first-login', 'login', '--no-browser', '--label', 'Temporary SDK qualification')
            assert json.loads(run('first-whoami', 'whoami').stdout)['account']['id'] == 'github:900000001'
            apps = json.loads(run('owned-apps', 'apps', 'list').stdout)['apps']
            assert [app['status'] for app in apps] == ['draft', 'published', 'withdrawn']
            if fixture:
                audit = control('audit', service='Lefony SDK: '+origin)
                token_hash = hashlib.sha256(next(iter(sessions)).encode()).hexdigest()
                assert audit['items'] == 1 and audit['token_sha256'] == token_hash
                assert audit['plaintext_token_on_disk'] is False
                before = len(actions)
                unavailable = {**env, 'DBUS_SESSION_BUS_ADDRESS':'unix:path='+str(folder/'missing-bus')}
                assert 'credential storage' in run('unavailable-bus', 'whoami', expected=1, environment=unavailable).stderr.lower()
                assert len(actions) == before
                run('bus-reconnected', 'whoami')
                control('lock')
                try:
                    before = len(actions)
                    assert 'credential storage' in run('locked-read', 'whoami', expected=1).stderr.lower()
                    assert len(actions) == before
                finally:
                    control('unlock')
                run('unlocked-read', 'whoami')
                control('restart')
                assert json.loads(run('daemon-restarted', 'whoami').stdout)['account']['id'] == 'github:900000001'
                audit = control('audit', service='Lefony SDK: '+origin)
                assert audit['items'] == 1 and audit['token_sha256'] == token_hash and audit['plaintext_token_on_disk'] is False
            before = len(actions)
            assert 'Sign in with lefony-sdk login' in run('origin-isolation', 'whoami', expected=1, target=other_origin).stderr
            assert len(actions) == before, 'Other origin retrieved or sent the active session'
            run('replace-login', 'login', '--no-browser', '--label', 'Temporary SDK qualification replacement')
            assert len(sessions) == 1 and {'operation': 'revoke', 'account': 'github:900000001'} in actions
            assert json.loads(run('replacement-whoami', 'whoami').stdout)['account']['id'] == 'github:900000002'
            sessions.clear()  # Controlled remote revocation, not a Keychain edit.
            assert 'Test session revoked' in run('remote-revocation', 'whoami', expected=1).stderr
            assert 'Sign in with lefony-sdk login' in run('revoked-local-cleanup', 'whoami', expected=1).stderr
            if fixture: assert control('audit', service='Lefony SDK: '+origin)['items'] == 0
            run('login-for-logout', 'login', '--no-browser', '--label', 'Temporary SDK logout qualification')
            run('explicit-logout', 'logout')
            assert not sessions
            assert 'Sign in with lefony-sdk login' in run('logout-local-cleanup', 'whoami', expected=1).stderr
        finally:
            try:
                if owned:
                    run('final-cleanup', 'logout')
                    assert 'Sign in with lefony-sdk login' in run('final-empty', 'whoami', expected=1).stderr
                    if fixture:
                        assert control('audit', service='Lefony SDK: '+origin)['items'] == 0
                        control('shutdown')
            finally:
                sessions.clear(); tickets.clear()
                server.shutdown(); server.server_close(); thread.join(2)
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected, name
    (output / 'report.json').write_text(json.dumps({
        'schema': 1, 'status': 'passed', 'native_credential_backend': backend_name,
        'host_machine': platform.machine(), 'native_clean_host_qualified': False,
        'access': access, 'bundle_in_place': args.bundle_in_place,
        'interpreter_sha256': hashlib.sha256(args.interpreter.read_bytes()).hexdigest() if args.interpreter else None,
        'candidate': json.loads((bundle / 'candidate.json').read_text()),
        'bundle_checksums_sha256': hashlib.sha256((bundle / 'SHA256SUMS').read_bytes()).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'homebrew_and_checkout_access': 'denied', 'credentials_removed': True,
        'server': 'controlled local HTTPS fixture with explicit CA',
        'github_oauth': 'not_tested', 'production_worker': 'not_tested',
        'cases': results, 'server_actions': actions,
        'credential_checks': credential_checks,
        'issued_sessions_checked_for_output_leaks': len(issued_tokens),
    }, indent=2) + '\n')


if __name__ == '__main__': main()

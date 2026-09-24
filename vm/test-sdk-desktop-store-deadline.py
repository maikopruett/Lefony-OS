#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual frozen macOS store CLI deadlines against controlled local HTTPS.

No account is issued or saved, no browser opens and no calculator is accessed.
The CLI reads the native credential backend; an existing credential at the
fixture's ephemeral origin causes refusal. Faults affect the first login POST.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import ssl
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def alive(pid):
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Darwin', 'This qualification uses the macOS sandbox'
    bundle, output = args.bundle.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected, name
    profile = ('(version 1)(allow default)(deny file-read* (subpath "/opt/homebrew"))'
               '(deny process-exec (subpath "/opt/homebrew"))'
               f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    results = []
    with tempfile.TemporaryDirectory(prefix='lf-store-deadline-', dir='/tmp') as temporary:
        folder = Path(temporary); relocated = folder / 'SDK network é'
        shutil.copytree(bundle, relocated, symlinks=True)
        program = relocated / 'lefony-sdk'
        cert, key = folder / 'cert.pem', folder / 'key.pem'
        subprocess.run([shutil.which('openssl'), 'req', '-x509', '-newkey', 'rsa:2048',
                        '-nodes', '-days', '1', '-subj', '/CN=localhost', '-addext',
                        'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(cert)],
                       capture_output=True, check=True, timeout=15)
        env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}

        for mode in ('error', 'headers', 'drip', 'tls', 'cancel', 'truncated', 'redirect'):
            received, stop = threading.Event(), threading.Event()
            requests = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *unused): pass
                def do_POST(self):
                    raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                    body = json.loads(raw)
                    assert self.path == '/api/store/sdk/authorizations'
                    assert set(body) == {'label', 'token_hash'} and 'Authorization' not in self.headers
                    requests.append({'method': 'POST', 'path': self.path, 'bytes': len(raw),
                                     'authorization_header': False})
                    received.set()
                    if mode in ('headers', 'cancel'): stop.wait(40)
                    content = b'{"error":"Controlled fixture rejection."}'
                    try:
                        self.send_response(307 if mode == 'redirect' else 403)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(content) + (100 if mode == 'truncated' else 0)))
                        if mode == 'redirect': self.send_header('Location', origin + '/api/store/sdk/should-not-follow')
                        self.end_headers()
                        if mode == 'drip':
                            for byte in content:
                                self.wfile.write(bytes([byte])); self.wfile.flush()
                                if stop.wait(1): break
                        else: self.wfile.write(content)
                    except OSError: pass

            if mode == 'tls':
                server = socket.socket(); server.bind(('127.0.0.1', 0)); server.listen(); server.settimeout(30)
                port = server.getsockname()[1]
                def peer():
                    with server.accept()[0] as connection:
                        connection.settimeout(5)
                        hello = connection.recv(4096)
                        assert hello and b'lfsdk1_' not in hello
                        received.set(); stop.wait(40)
                thread = threading.Thread(target=peer, daemon=True)
            else:
                server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                port = server.server_port
                thread = threading.Thread(target=server.serve_forever, daemon=True)
            origin = f'https://localhost:{port}'
            thread.start()
            options = ['--store-origin', origin, '--store-ca-file', str(cert)]
            prefix = ['/usr/bin/sandbox-exec', '-p', profile, str(program)]
            # Check before submitting any request; this must not touch the network.
            initial = subprocess.run([*prefix, 'whoami', *options], cwd=folder, env=env,
                                     capture_output=True, text=True, timeout=15)
            assert initial.returncode == 1 and 'Sign in with lefony-sdk login' in initial.stderr
            assert not received.is_set()
            started = time.monotonic(); seen = set(); interrupted_at = None
            process = subprocess.Popen([*prefix, 'login', '--no-browser', '--label', 'Temporary deadline fixture', *options],
                                       cwd=folder, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            try:
                while process.poll() is None:
                    snapshot = subprocess.run(['/bin/ps', '-axo', 'pid=,pgid='], capture_output=True, text=True, check=True, timeout=3)
                    seen.update(int(pid) for pid, group in (line.split() for line in snapshot.stdout.splitlines())
                                if int(group) == process.pid and int(pid) != process.pid)
                    if mode == 'cancel' and received.is_set() and interrupted_at is None:
                        interrupted_at = time.monotonic(); process.send_signal(signal.SIGINT)
                    assert time.monotonic() - started < 29, 'Frozen command exceeded its deadline and startup allowance'
                    time.sleep(.03)
                stdout, stderr = process.communicate(timeout=3)
                elapsed = time.monotonic() - started
                (output / (mode + '.stdout')).write_text(stdout)
                (output / (mode + '.stderr')).write_text(stderr)
                assert 'lfsdk1_' not in stdout + stderr
                assert received.is_set(), 'Fault stage was not reached'
                assert process.returncode == (130 if mode == 'cancel' else 1), stderr
                expected = ('cancelled' if mode == 'cancel' else 'timed out' if mode in ('headers', 'drip', 'tls')
                            else 'incomplete' if mode == 'truncated' else 'redirected' if mode == 'redirect'
                            else 'Controlled fixture rejection')
                assert expected in stderr, stderr
                assert len(requests) == (0 if mode == 'tls' else 1), 'A request was retried or redirected'
                if interrupted_at is not None: assert time.monotonic() - interrupted_at < 3
                deadline = time.monotonic() + 3
                while any(alive(pid) for pid in seen) and time.monotonic() < deadline: time.sleep(.05)
                assert seen and not any(alive(pid) for pid in seen), 'Frozen worker/tracker survived command completion'
                empty = subprocess.run([*prefix, 'whoami', *options], cwd=folder, env=env,
                                       capture_output=True, text=True, timeout=15)
                assert empty.returncode == 1 and 'Sign in with lefony-sdk login' in empty.stderr
                result = {'case': mode, 'exit_code': process.returncode, 'elapsed_seconds': round(elapsed, 3),
                          'requests': requests, 'observed_children': sorted(seen), 'children_stopped': True,
                          'credential_not_saved': True}
                if interrupted_at: result['interrupt_to_exit_seconds'] = round(started + elapsed - interrupted_at, 3)
                results.append(result)
                print(f'PASS: frozen store {mode} ({elapsed:.3f}s)', flush=True)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.communicate(timeout=3)
                    except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.communicate(timeout=3)
                stop.set()
                if mode == 'tls': server.close()
                else: server.shutdown(); server.server_close()
                thread.join(3)
    (output / 'report.json').write_text(json.dumps({
        'schema': 1, 'status': 'passed', 'candidate': json.loads((bundle / 'candidate.json').read_text()),
        'bundle_checksums_sha256': hashlib.sha256((bundle / 'SHA256SUMS').read_bytes()).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'homebrew_and_checkout_access': 'denied', 'server': 'controlled local TLS',
        'accounts_issued': 0, 'credentials_saved': 0, 'cases': results,
    }, indent=2) + '\n')


if __name__ == '__main__': main()

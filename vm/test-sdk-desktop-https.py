#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qualify frozen macOS HTTPS trust and worker shutdown after relocation.

Public HTTPS is opt-in. Controlled fixtures never change system certificates,
access accounts or open a calculator. This is not a full companion/USB test.
"""
import argparse
from contextlib import contextmanager
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


@contextmanager
def fixtures(folder):
    cert, key = folder / 'localhost.pem', folder / 'localhost-key.pem'
    subprocess.run([shutil.which('openssl'), 'req', '-x509', '-newkey', 'rsa:2048',
                    '-nodes', '-days', '1', '-subj', '/CN=localhost', '-addext',
                    'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(cert)],
                   check=True, capture_output=True, timeout=15)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused): pass
        def do_HEAD(self):
            requests.append({'method': 'HEAD', 'path': self.path,
                             'authorization_present': 'Authorization' in self.headers})
            self.send_response(503)
            self.send_header('Content-Length', '123456789')
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'https://localhost:{server.server_port}', cert, requests
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


@contextmanager
def stalled_handshake():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(20)
    accepted, stop = threading.Event(), threading.Event()

    def receive():
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(5)
                if connection.recv(4096): accepted.set()
                stop.wait(20)
        except OSError:
            pass

    thread = threading.Thread(target=receive, daemon=True); thread.start()
    try:
        yield f'https://localhost:{listener.getsockname()[1]}', accepted
    finally:
        stop.set(); listener.close(); thread.join(2)


def descendants(pid):
    pairs = [tuple(map(int, line.split())) for line in subprocess.check_output(
        ['/bin/ps', '-axo', 'pid=,ppid='], text=True).splitlines()]
    found = {pid}
    while True:
        updated = found | {child for child, parent in pairs if parent in found}
        if updated == found: return found - {pid}
        found = updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--public-origin', help='explicit read-only HEAD probe using native public roots')
    args = parser.parse_args()
    assert platform.system() == 'Darwin', 'This denied-access harness requires macOS'
    bundle, output = args.bundle.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected, name
    profile = ('(version 1)(allow default)'
               '(deny file-read* (subpath "/opt/homebrew"))'
               '(deny process-exec (subpath "/opt/homebrew"))'
               f'(deny file-read* (subpath {json.dumps(str(ROOT))}))')
    results = []
    with tempfile.TemporaryDirectory(prefix='lf-tls-', dir='/tmp') as temp:
        folder = Path(temp)
        relocated = folder / 'SDK HTTPS é'
        shutil.copytree(bundle, relocated, symlinks=True)
        program = relocated / 'lefony-sdk'
        env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
               'SSL_CERT_FILE': str(folder / 'absent-ca.pem'),
               'SSL_CERT_DIR': str(folder / 'absent-ca-directory')}

        def run(name, origin=None, ca=None, cancel=None):
            command = ['/usr/bin/sandbox-exec', '-p', profile, str(program), 'doctor']
            if origin: command += ['--https-origin', origin]
            if ca: command += ['--https-ca-file', str(ca)]
            started = time.monotonic()
            with subprocess.Popen(command, cwd=folder, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
                try:
                    children = set()
                    if cancel is not None:
                        assert cancel.wait(8), 'Frozen worker never started the TLS handshake'
                        children = descendants(process.pid)
                        assert children, 'No frozen child process observed'
                        started_cancel = time.monotonic()
                        process.send_signal(signal.SIGINT)
                    stdout, stderr = process.communicate(timeout=25)
                    elapsed = time.monotonic() - started
                    if cancel is not None:
                        assert process.returncode == 130, stderr
                        assert time.monotonic() - started_cancel < 3
                        deadline = time.monotonic() + 2
                        while children:
                            existing = set(map(int, subprocess.check_output(
                                ['/bin/ps', '-axo', 'pid='], text=True).split()))
                            children &= existing
                            if not children: break
                            assert time.monotonic() < deadline, 'Frozen child survived cancellation'
                            time.sleep(.02)
                        report = {'status': 'cancelled', 'children_stopped': True}
                    else:
                        report = json.loads(stdout)['https']
                        assert process.returncode == (1 if report['status'] == 'failed' else 0), stderr
                        if origin: assert report['worker_stopped'], report
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=5)
            (output / (name + '.stdout')).write_text(stdout)
            (output / (name + '.stderr')).write_text(stderr)
            result = {'case': name, 'https': report, 'elapsed_seconds': round(elapsed, 3),
                      'exit_code': process.returncode}
            results.append(result)
            print(json.dumps(result), flush=True)
            return report, elapsed

        report, _ = run('offline-doctor')
        assert report == {'status': 'not_checked'}
        with fixtures(folder) as (origin, cert, requests):
            report, _ = run('untrusted-local', origin)
            assert report['status'] == 'failed' and report['error'] == 'tls' and not requests
            report, _ = run('explicit-local-ca', origin, cert)
            assert report['status'] == 'passed' and report['http_status'] == 503
            assert requests == [{'method': 'HEAD', 'path': '/', 'authorization_present': False}]
            report, _ = run('wrong-hostname', origin.replace('localhost', '127.0.0.1'), cert)
            assert report['status'] == 'failed' and report['error'] == 'tls'
            report, _ = run('native-trust-still-isolated', origin)
            assert report['status'] == 'failed' and report['error'] == 'tls' and len(requests) == 1
        with stalled_handshake() as (origin, accepted):
            report, elapsed = run('handshake-deadline', origin)
            assert accepted.is_set() and report['error'] == 'timeout' and 9 <= elapsed < 15
        with stalled_handshake() as (origin, accepted):
            run('handshake-cancel', origin, cancel=accepted)
        if args.public_origin:
            report, _ = run('native-public-roots', args.public_origin)
            assert report['status'] == 'passed' and report['trust'] == 'native-system'
    (output / 'report.json').write_text(json.dumps({
        'schema': 1, 'status': 'passed', 'host': {'system': platform.system(),
        'version': platform.mac_ver()[0], 'architecture': platform.machine()},
        'candidate': json.loads((bundle / 'candidate.json').read_text()),
        'bundle_checksums_sha256': hashlib.sha256((bundle / 'SHA256SUMS').read_bytes()).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'homebrew_and_checkout_access': 'denied', 'ambient_openssl_ca_paths': 'absent',
        'public_https': bool(args.public_origin), 'cases': results,
        'accounts': 'not_tested', 'companion_usb_streaming': 'not_tested', 'physical': 'not_tested',
    }, indent=2) + '\n')


if __name__ == '__main__': main()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Real local HTTPS plus blocked DNS/trust/IPC, cancellation and mutation checks."""
from functools import partial
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
import store_http
from store_client import StoreClient, StoreError
from store_listing import canonical

TOKEN = 'lfsdk1_' + 'c' * 64


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    folder = tmp_path_factory.mktemp('store-http')
    cert, key = folder / 'cert.pem', folder / 'key.pem'
    subprocess.run([shutil.which('openssl'), 'req', '-x509', '-newkey', 'rsa:2048',
                    '-nodes', '-days', '1', '-subj', '/CN=localhost', '-addext',
                    'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(cert)],
                   check=True, capture_output=True, timeout=15)
    requests, received = [], threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *unused): pass
        def handle_request(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            requests.append((self.path, self.command, dict(self.headers), hashlib.sha256(body).hexdigest(), len(body)))
            received.set()
            case = self.path.rsplit('/', 1)[-1]
            content, status, kind = b'{"ok":true}', 200, 'application/json'
            if case == 'large': content = b'x' * (store_http.RESPONSE_LIMIT + 1)
            if case == 'exact': content = b'{"value":"' + b'x' * (store_http.RESPONSE_LIMIT - 12) + b'"}'
            if case == 'error': content, status = b'{"error":"Slow down.","retry_after":7}', 429
            if case == 'secret': content, status = json.dumps({'error': TOKEN}).encode(), 403
            if case == 'redirect': status = 307
            if case == 'binary': content, kind = b'\x89PNG\x00\xff', 'image/png'
            try:
                if case == 'headers': time.sleep(5)
                self.send_response(status)
                self.send_header('Content-Type', kind)
                self.send_header('Connection', 'close')
                if case == 'redirect': self.send_header('Location', origin + '/api/store/sdk/target')
                if case == 'chunked': self.send_header('Transfer-Encoding', 'chunked')
                else: self.send_header('Content-Length', str(len(content) + (100 if case == 'truncated' else 0)))
                self.end_headers()
                if case == 'drip':
                    for byte in content:
                        self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.3)
                elif case == 'chunked':
                    self.wfile.write(f'{len(content):x}\r\n'.encode() + content + b'\r\n0\r\n\r\n')
                else: self.wfile.write(content)
            except OSError: pass
            self.close_connection = True
        do_GET = do_POST = do_PUT = handle_request

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    origin = f'https://localhost:{httpd.server_port}'
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try: yield origin, str(cert), requests, received
    finally: httpd.shutdown(); httpd.server_close(); thread.join(2)


def client(server):
    origin, cert, _, _ = server
    return StoreClient(origin, ca_file=cert, token=TOKEN)


def no_workers():
    assert not multiprocessing.active_children()
    assert not any(t.name == 'sdk-store-ipc' for t in threading.enumerate())


@pytest.mark.parametrize('path', ['fixed', 'chunked', 'exact'])
def test_complete_bounded_json_response(server, path):
    result = client(server).request('/sdk/' + path)
    assert result == ({'value': 'x' * (store_http.RESPONSE_LIMIT - 12)} if path == 'exact' else {'ok': True})
    no_workers()


@pytest.mark.parametrize('path,message,status', [
    ('large', 'exceeded', 200), ('truncated', 'incomplete', 200),
    ('redirect', 'redirected', 307), ('binary', 'invalid response', 200),
    ('error', 'Slow down', 429), ('secret', 'Store request failed', 403),
])
def test_errors_redirects_and_truncation_preserve_status_without_retries(server, path, message, status):
    before = len(server[2])
    with pytest.raises(StoreError, match=message) as error:
        client(server).request('/sdk/' + path)
    assert error.value.status == status and TOKEN not in str(error.value)
    if path == 'error': assert error.value.retry_after == 7
    assert len(server[2]) == before + 1
    no_workers()


def test_large_listing_and_binary_upload_cross_ipc_exactly(server):
    api = client(server)
    body = {'text': 'x' * (8 * 1024 * 1024 - 11)}
    raw = canonical(body)
    assert len(raw) == 8 * 1024 * 1024
    assert api.request('/sdk/apps/hello/listing', 'PUT', body) == {'ok': True}
    request = server[2][-1]
    assert request[1] == 'PUT' and request[3:] == (hashlib.sha256(raw).hexdigest(), len(raw))
    assert request[2]['Authorization'] == 'Bearer ' + TOKEN
    chunk = bytes(range(256)) * 1024
    api.put_chunk('/sdk/uploads/01234567-89ab-cdef-0123-456789abcdef/files/0/parts/0', chunk)
    request = server[2][-1]
    assert request[3:] == (hashlib.sha256(chunk).hexdigest(), len(chunk))
    assert request[2]['X-Lefony-Sha256'] == hashlib.sha256(chunk).hexdigest()
    before = len(server[2])
    body['text'] += 'x'
    with pytest.raises(StoreError, match='too large'): api.request('/sdk/apps/hello/listing', 'PUT', body)
    assert len(server[2]) == before
    no_workers()


@pytest.mark.parametrize('phase', ['headers', 'drip'])
def test_total_deadline_stops_live_slow_response_and_does_not_retry_mutation(server, monkeypatch, phase):
    monkeypatch.setattr('store_client.exchange', partial(store_http.exchange, timeout=1))
    before = len(server[2]); start = time.monotonic()
    with pytest.raises(StoreError, match='timed out.*saved attempt'):
        client(server).request('/sdk/' + phase, 'POST', {'mutate': True})
    assert time.monotonic() - start < 2.5
    assert len(server[2]) == before + 1 and server[2][-1][1] == 'POST'
    no_workers()


def _fault_worker(pipe, *, phase, ready):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    def stall(*args, **kwargs):
        ready.set(); time.sleep(60)
    if phase == 'dns': socket.getaddrinfo = stall
    elif phase == 'trust':
        import importlib
        importlib.import_module('truststore._api')._verify_peercerts = stall
    elif phase == 'missing-trust':
        sys.modules['truststore'] = None
    elif phase == 'send':
        stall(); return
    elif phase == 'partial':
        pipe.recv()
        # A partial IPC frame must not block the supervising thread's deadline.
        os.write(pipe.fileno(), struct.pack('!i', 1000000) + b'partial')
        stall(); return
    elif phase == 'death':
        pipe.recv(); ready.set(); os._exit(9)
    store_http._worker(pipe)


@pytest.mark.parametrize('phase', ['dns', 'trust', 'send', 'partial', 'death', 'missing-trust'])
def test_stalled_or_dead_worker_is_bounded_and_reaped(server, monkeypatch, phase):
    if phase == 'partial' and os.name == 'nt':
        pytest.skip('Raw POSIX pipe framing fault; Windows has a different pipe implementation')
    ready = multiprocessing.get_context('spawn').Event()
    monkeypatch.setattr(store_http, '_worker', partial(_fault_worker, phase=phase, ready=ready))
    monkeypatch.setattr('store_client.exchange', partial(store_http.exchange, timeout=1.5))
    # Native verification must actually run before injecting its stalled return.
    # A self-signed local fixture reaches that hook without sending HTTP secrets.
    api = StoreClient(server[0], token=TOKEN) if phase in ('trust', 'missing-trust') else client(server)
    body = {'text': 'x' * (8 * 1024 * 1024 - 12)} if phase == 'send' else {}
    start = time.monotonic(); before = len(server[2])
    message = 'Native HTTPS trust is unavailable' if phase == 'missing-trust' else 'securely' if phase == 'death' else 'timed out'
    with pytest.raises(StoreError, match=message) as error:
        api.request('/sdk/apps/hello/listing', 'PUT', body)
    assert time.monotonic() - start < 3 and TOKEN not in str(error.value)
    assert len(server[2]) == before
    if phase != 'missing-trust': assert ready.is_set(), 'Fault stage was not reached'
    no_workers()


def test_ctrl_c_stops_request_worker_and_ipc_without_resending(server):
    received = server[3]; received.clear(); before = len(server[2])
    def interrupt():
        if received.wait(5): signal.raise_signal(signal.SIGINT)
    interrupter = threading.Thread(target=interrupt); interrupter.start()
    start = time.monotonic()
    try:
        with pytest.raises(KeyboardInterrupt):
            client(server).request('/sdk/headers', 'POST', {'mutate': True})
    finally: interrupter.join(6)
    assert time.monotonic() - start < 3
    assert len(server[2]) == before + 1
    no_workers()


def test_stalled_tls_handshake_is_bounded_before_credentials(monkeypatch):
    monkeypatch.setattr('store_client.exchange', partial(store_http.exchange, timeout=1))
    listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(3)
    accepted = threading.Event(); stop = threading.Event(); data = []
    def peer():
        with listener.accept()[0] as connection:
            connection.settimeout(3); data.append(connection.recv(4096)); accepted.set(); stop.wait(3)
    thread = threading.Thread(target=peer); thread.start()
    start = time.monotonic()
    try:
        with pytest.raises(StoreError, match='timed out'):
            StoreClient(f'https://localhost:{listener.getsockname()[1]}', token=TOKEN).request('/sdk/me')
        assert accepted.is_set() and data and all(TOKEN.encode() not in value for value in data)
        assert time.monotonic() - start < 2.5
        no_workers()
    finally: stop.set(); thread.join(4); listener.close()


def test_ctrl_c_during_spawn_and_cleanup_cannot_orphan_a_worker(monkeypatch):
    real_context = multiprocessing.get_context('spawn')
    ready = real_context.Event()
    monkeypatch.setattr(store_http, '_worker', partial(_fault_worker, phase='send', ready=ready))
    class Context:
        Pipe = staticmethod(real_context.Pipe)
        @staticmethod
        def Process(**kwargs):
            process = real_context.Process(**kwargs)
            class OwnedProcess:
                def __getattr__(self, name): return getattr(process, name)
                def start(self):
                    process.start()
                    signal.raise_signal(signal.SIGINT)
                def terminate(self):
                    signal.raise_signal(signal.SIGINT)
                    process.terminate()
            return OwnedProcess()
    monkeypatch.setattr(store_http.multiprocessing, 'get_context', lambda _: Context())
    with pytest.raises(KeyboardInterrupt):
        StoreClient('https://store.invalid', token=TOKEN).request('/sdk/me')
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    no_workers()

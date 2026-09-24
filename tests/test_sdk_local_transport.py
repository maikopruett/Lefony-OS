# SPDX-License-Identifier: GPL-3.0-or-later
"""Local socket lifecycle; Windows address checks do not qualify native Windows."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import errno
import os
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
import local_transport as transport
from emulator_usb import PrimeUSBHost, USBError
from runner import Channel


def unix_server(path, action, delay=0):
    time.sleep(delay)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.settimeout(2)
        server.bind(str(path)); server.listen(1)
        with server.accept()[0] as connection:
            connection.settimeout(2)
            return action(connection)


@pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='Native Python AF_UNIX server required')
def test_delayed_server_fragmented_lines_and_explicit_session_path():
    with transport.session_directory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
        path = Path(directory) / 'control'
        if os.name != 'nt':
            assert Path(directory).stat().st_mode & 0o777 == 0o700
        def reply(connection):
            assert connection.recv(128) == b'PING\n'
            connection.sendall(b'PO'); time.sleep(.01); connection.sendall(b'NG\n')
            assert connection.recv(128) == b''
        future = pool.submit(unix_server, path, reply, .05)
        channel = Channel(path, None, timeout=1)
        try:
            assert channel.session_directory == path.parent.resolve()
            assert channel.command('PING') == 'PONG'
        finally:
            channel.close()
        future.result(timeout=2)


@pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='Native Python AF_UNIX server required')
def test_failed_usb_greeting_closes_the_connection():
    with transport.session_directory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
        path = Path(directory) / 'usb'
        def reply(connection):
            assert connection.recv(128) == b'HELLO\n'
            connection.sendall(b'USBHOST 99\n')
            assert connection.recv(128) == b''
        future = pool.submit(unix_server, path, reply)
        with pytest.raises(USBError, match='unsupported'):
            PrimeUSBHost(path, timeout=1)
        future.result(timeout=2)


@pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='Native Python AF_UNIX required')
def test_missing_socket_deadline_closes_every_attempt(monkeypatch):
    factory = socket.socket; created = []
    def recording(*args, **kwargs):
        sock = factory(*args, **kwargs); created.append(sock); return sock
    monkeypatch.setattr(transport.socket, 'socket', recording)
    with transport.session_directory() as directory:
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            transport.connect(Path(directory) / 'absent', timeout=.08)
        assert .08 <= time.monotonic() - start < 1
    assert created and all(sock.fileno() == -1 for sock in created)


def test_dead_emulator_does_not_open_a_socket(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('Socket opened after emulator exited')
    monkeypatch.setattr(transport.socket, 'socket', forbidden)
    with transport.session_directory() as directory, pytest.raises(RuntimeError, match='exited'):
        transport.connect(Path(directory) / 'control', process=SimpleNamespace(poll=lambda: 1))


@pytest.mark.parametrize('timeout', [True, 0, -1, float('nan'), float('inf'), 3601, 10**1000])
def test_invalid_deadline_is_rejected_before_connection(tmp_path, timeout):
    with pytest.raises(ValueError, match='timeouts'):
        transport.connect(tmp_path / 'control', timeout=timeout)


def test_unix_backlog_exhaustion_retries_with_a_new_socket(monkeypatch, tmp_path):
    created = []
    class Socket:
        def __init__(self, error): self.error = error; self.closed = False
        def setblocking(self, value): assert value is False
        def connect_ex(self, path): return self.error
        def settimeout(self, value): self.timeout = value
        def close(self): self.closed = True
    def factory(*args):
        sock = Socket(errno.EAGAIN if not created else 0); created.append(sock); return sock
    monkeypatch.setattr(transport.socket, 'socket', factory)
    def forbidden(*args): raise AssertionError('Unix EAGAIN treated as a pending connection')
    monkeypatch.setattr(transport.select, 'select', forbidden)
    monkeypatch.setattr(transport.time, 'sleep', lambda _: None)
    if os.name == 'nt': pytest.skip('Unix backlog contract')
    result = transport.connect(tmp_path / 'control')
    assert len(created) == 2 and created[0].closed and result is created[1]
    result.close()


def test_windows_sockaddr_uses_utf8_and_the_documented_layout():
    value = transport.windows_address('C:\\Users\\é\\control')
    assert ctypes.sizeof(value) == 110 and value.family == 1
    assert transport.WindowsUnixAddress.path.offset == 2
    assert value.path == 'C:\\Users\\é\\control'.encode('utf-8')
    assert bytes(value)[2 + len(value.path)] == 0
    assert len(transport.windows_address('x' * 107).path) == 107


@pytest.mark.parametrize('path', ['', 'x' * 108, 'é' * 54, 'one\0two'])
def test_windows_socket_path_rejects_truncation_and_nuls(path):
    with pytest.raises(ValueError): transport.windows_address(path)


def test_qemu_option_paths_escape_commas_without_shell_quoting():
    assert transport.qemu_path('C:\\user, name\\é') == 'C:\\user,, name\\é'
    for path in ('one\0two', 'one\ntwo', 'one\rtwo'):
        with pytest.raises(ValueError): transport.qemu_path(path)

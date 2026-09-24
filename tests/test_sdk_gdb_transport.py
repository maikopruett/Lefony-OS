# SPDX-License-Identifier: GPL-3.0-or-later
"""Real relay subprocess I/O and shutdown, without connecting a calculator."""
from concurrent.futures import ThreadPoolExecutor
import os
import errno
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
from gdb_transport import gdb_quote, remote_command
from local_transport import session_directory
from test_sdk_local_transport import unix_server

UNIX = pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='Native Python AF_UNIX server required')


def process(path, *, frozen_entry=False, timeout='1'):
    entry = ROOT / 'sdk/tools' / ('portable_entry.py' if frozen_entry else 'gdb_transport.py')
    command = [sys.executable, str(entry)]
    if frozen_entry:
        command.append('--internal-gdb-relay')
    return subprocess.Popen([*command, '--endpoint', str(path), '--connect-timeout', timeout],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@UNIX
@pytest.mark.parametrize('frozen_entry', [False, True])
def test_binary_transfer_and_debugger_disconnect(frozen_entry):
    # Includes NUL, CR/LF, 0x1a and all RSP framing/escape bytes.
    payload = bytes(range(256)) * 1024
    with session_directory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
        path = Path(directory) / 'gdb'
        def server(channel):
            received = bytearray()
            while len(received) < len(payload):
                chunk = channel.recv(16381)
                assert chunk
                received.extend(chunk)
            assert received == payload
            for offset in range(0, len(payload), 997):
                channel.sendall(payload[offset:offset + 997])
            assert channel.recv(1) == b''
        result = pool.submit(unix_server, path, server, .05)
        with process(path, frozen_entry=frozen_entry) as child:
            try:
                child.stdin.write(payload); child.stdin.flush()
                assert child.stdout.read(len(payload)) == payload
                child.stdin.close()
                assert child.wait(timeout=2) == 0, child.stderr.read()
                assert child.stdout.read() == b'' and child.stderr.read() == b''
            finally:
                if child.poll() is None: child.kill()
        result.result(timeout=2)


@UNIX
def test_emulator_disconnect_exits_with_debugger_input_still_open():
    with session_directory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
        path = Path(directory) / 'gdb'
        result = pool.submit(unix_server, path, lambda channel: None)
        with process(path) as child:
            try:
                assert child.wait(timeout=2) == 0
                assert child.stdout.read() == b'' and child.stderr.read() == b''
            finally:
                if child.poll() is None: child.kill()
        result.result(timeout=2)


@UNIX
def test_debugger_disconnect_exits_even_with_blocked_output():
    with session_directory() as directory, ThreadPoolExecutor(max_workers=1) as pool:
        path = Path(directory) / 'gdb'
        def server(channel):
            try:
                channel.sendall(b'x' * (16 * 1024 * 1024))
            except OSError as exc:
                assert exc.errno in (errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN)
                return
            raise AssertionError('Relay buffered unbounded output')
        result = pool.submit(unix_server, path, server)
        with process(path) as child:
            try:
                assert child.stdout.read(1) == b'x'
                child.stdin.close()
                assert child.wait(timeout=2) == 0, child.stderr.read()
            finally:
                if child.poll() is None: child.kill()
        result.result(timeout=2)


@UNIX
def test_missing_endpoint_fails_with_clean_stdout_and_bounded_exit():
    with session_directory() as directory:
        start = time.monotonic()
        with process(Path(directory) / 'absent', timeout='.1') as child:
            output, errors = child.communicate(timeout=2)
            assert child.returncode == 1 and output == b'' and b'deadline' in errors
        assert time.monotonic() - start < 2


@pytest.mark.parametrize('value', ['one\ntwo', 'one\rtwo', 'one\0two'])
def test_gdb_command_terminators_are_rejected(value):
    with pytest.raises(ValueError, match='terminators'):
        gdb_quote(value)
    with pytest.raises(ValueError):
        remote_command(Path(value))


def test_gdb_argument_quotes_for_native_buildargv():
    assert gdb_quote('C:\\A & %PATH%\\\"é\"') == '"C:\\\\A & %PATH%\\\\\\"é\\""'


@pytest.mark.skipif(os.name == 'nt', reason='Unix shell parser')
def test_remote_command_preserves_special_paths_without_shell_expansion(tmp_path):
    endpoint = tmp_path / 'space é \' " $HOME `echo boom` ; $(echo boom) %PATH%'
    argv = shlex.split(remote_command(endpoint).removeprefix('target remote | '))
    assert argv == [sys.executable, str(ROOT / 'sdk/tools/gdb_transport.py'), '--endpoint', str(endpoint)]

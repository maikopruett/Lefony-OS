# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded connections to private local emulator sockets, including Winsock.

QEMU 11 supports Windows AF_UNIX, but CPython's Windows socket module does not
expose its sockaddr parser. Only connect uses ctypes there; subsequent I/O and
timeouts use the normal Python socket. No TCP listener or network fallback.
"""
import ctypes
import errno
import math
import os
from pathlib import Path
import select
import socket
import sys
import tempfile
import time


class WindowsUnixAddress(ctypes.Structure):
    _fields_ = [('family', ctypes.c_ushort), ('path', ctypes.c_char * 108)]


def windows_address(path):
    # Windows AF_UNIX takes a UTF-8 DOS pathname, including a trailing NUL.
    encoded = os.fspath(path).encode('utf-8')
    if not encoded or b'\0' in encoded or len(encoded) >= 108:
        raise ValueError('Local emulator socket needs a UTF-8 path shorter than 108 bytes')
    return WindowsUnixAddress(1, encoded)


def _windows_connect(sock, path):
    address = windows_address(path)
    winsock = ctypes.WinDLL('ws2_32', use_last_error=True)
    winsock.connect.argtypes = [ctypes.c_size_t, ctypes.POINTER(WindowsUnixAddress), ctypes.c_int]
    winsock.connect.restype = ctypes.c_int
    winsock.WSAGetLastError.argtypes = []
    winsock.WSAGetLastError.restype = ctypes.c_int
    result = winsock.connect(sock.fileno(), ctypes.byref(address), ctypes.sizeof(address))
    return winsock.WSAGetLastError() if result == -1 else 0


def socket_path(path):
    # Do not resolve Windows AF_UNIX reparse points as ordinary symlinks.
    return Path(os.path.abspath(path)) if os.name == 'nt' else Path(path).resolve()


def connect(path, *, timeout=30, io_timeout=5, process=None):
    """Connect within one deadline, closing every failed or cancelled attempt."""
    for value in (timeout, io_timeout):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 3600 or not math.isfinite(value):
            raise ValueError('Local socket timeouts must be finite and within 0–3600 seconds')
    windows = os.name == 'nt'
    path = socket_path(path)
    if '\0' in os.fspath(path):
        raise ValueError('Invalid local socket path')
    family = 1 if windows else socket.AF_UNIX
    if windows:
        windows_address(path)
    pending = {errno.EINPROGRESS, errno.EALREADY, 10035, 10036, 10037}
    # AF_UNIX backlog exhaustion is EAGAIN, not a successful pending connect.
    retry = {errno.ENOENT, errno.ECONNREFUSED, errno.EAGAIN, 10061}
    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        if process is not None and process.poll() is not None:
            raise RuntimeError('Emulator exited before opening its local control socket') from last_error
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Emulator did not open its local control socket before the deadline') from last_error
        connection = socket.socket(family, socket.SOCK_STREAM)
        try:
            connection.setblocking(False)
            error = _windows_connect(connection, path) if windows else connection.connect_ex(os.fspath(path))
            if error in pending:
                while True:
                    if process is not None and process.poll() is not None:
                        raise RuntimeError('Emulator exited during local socket connection')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Local emulator socket connection timed out')
                    _, writable, failed = select.select([], [connection], [connection], min(.05, remaining))
                    if writable or failed:
                        error = connection.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        break
            if error:
                raise OSError(error, 'Local emulator socket connection failed')
            connection.settimeout(io_timeout)
            return connection
        except OSError as exc:
            connection.close()
            if exc.errno not in retry:
                raise
            last_error = exc
        except BaseException:
            connection.close()
            raise
        time.sleep(min(.02, max(0, deadline - time.monotonic())))


def session_directory():
    """Use short private paths; Windows mkdir(0700) needs Python 3.13 or newer."""
    if os.name == 'nt' and sys.version_info < (3, 13):
        raise RuntimeError('Native Windows emulator sessions require Python 3.13 or newer')
    directory = tempfile.TemporaryDirectory(prefix='lfs-', dir=None if os.name == 'nt' else '/tmp')
    if os.name == 'nt':
        try:
            windows_address(Path(directory.name) / 'layout-gdb')
        except ValueError:
            directory.cleanup()
            raise ValueError('Windows TEMP is too long for local emulator sockets; choose a shorter private TEMP directory') from None
    return directory


def qemu_path(path):
    """Escape a pathname inside a QEMU comma-separated option, not a shell."""
    value = os.fspath(path)
    if any(c in value for c in ('\0', '\n', '\r')):
        raise ValueError('QEMU paths cannot contain command terminators')
    return value.replace(',', ',,')

# SPDX-License-Identifier: GPL-3.0-or-later
"""Private GDB pipe relay. Invoked as a separate process, never in the CLI loop."""
import argparse
import os
from pathlib import Path
import shlex
import socket
import sys
import threading

from local_transport import connect, socket_path


def gdb_quote(value):
    """One GDB CLI/buildargv argument; this is not shell quoting."""
    text = os.fspath(value)
    if any(c in text for c in ('\0', '\n', '\r')):
        raise ValueError('GDB paths cannot contain command terminators')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def remote_command(endpoint):
    """Use a pipe on every host so ordinary Unix trials also exercise the relay.

    GDB 17.2 ser-mingw.c uses buildargv and pex/CreateProcess, without cmd.exe.
    ser-pipe.c on Unix uses the host shell. Quote for the actual parser.
    """
    endpoint = socket_path(endpoint)
    if getattr(sys, 'frozen', False):
        argv = [sys.executable, '--internal-gdb-relay', '--endpoint', str(endpoint)]
    else:
        argv = [sys.executable, str(Path(__file__).resolve()), '--endpoint', str(endpoint)]
    for value in argv:
        gdb_quote(value)  # Reject line/command terminators before shell quoting.
    command = ' '.join(gdb_quote(value) for value in argv) if os.name == 'nt' else shlex.join(argv)
    return 'target remote | ' + command


def relay(endpoint, *, timeout=10):
    """Forward bytes until either peer closes; bound connection and stalled sends.

    Raw fd I/O avoids text translation and Python buffered-stream shutdown locks.
    A blocked inherited pipe may outlive a worker briefly; workers are daemon
    threads in this dedicated helper process, whose main thread always exits.
    No listener, subprocess or detached helper is created by the relay itself.
    """
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(0, os.O_BINARY)
        msvcrt.setmode(1, os.O_BINARY)
    done = threading.Event()
    failures = []
    with connect(endpoint, timeout=timeout, io_timeout=5) as channel:
        def transfer(to_socket):
            try:
                while not done.is_set():
                    if to_socket:
                        data = os.read(0, 65536)
                    else:
                        try:
                            data = channel.recv(65536)
                        except TimeoutError:
                            continue  # A developer may pause at a breakpoint.
                    if not data:
                        break
                    if to_socket:
                        channel.sendall(data)
                    else:
                        remaining = memoryview(data)
                        while remaining and not done.is_set():
                            count = os.write(1, remaining)
                            if count <= 0:
                                raise OSError('GDB output pipe stopped accepting bytes')
                            remaining = remaining[count:]
            except OSError as exc:
                if not done.is_set():
                    failures.append(exc)
            finally:
                done.set()

        workers = [threading.Thread(target=transfer, args=(direction,), daemon=True)
                   for direction in (True, False)]
        for worker in workers:
            worker.start()
        try:
            while not done.wait(.05):
                pass
        finally:
            done.set()
            try:
                channel.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            for worker in workers:
                worker.join(.1)
    if failures:
        raise failures[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', type=Path, required=True)
    parser.add_argument('--connect-timeout', type=float, default=10)
    args = parser.parse_args(argv)
    try:
        relay(args.endpoint, timeout=args.connect_timeout)
    except (OSError, ValueError) as exc:
        print('GDB relay: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

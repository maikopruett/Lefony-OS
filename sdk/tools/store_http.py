# SPDX-License-Identifier: GPL-3.0-or-later
"""One store HTTPS request with a parent-enforced deadline and no retries.

DNS and native certificate verification run only in the disposable child. A
single IPC thread moves the bounded request/response so a blocked pipe cannot
hold up the supervising thread. Credentials never enter command lines or files.
"""
from contextlib import contextmanager
from http.client import HTTPException
import multiprocessing
import signal
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler

from tls_context import client_context, TrustError

TIMEOUT_SECONDS = 20
RESPONSE_LIMIT = 1024 * 1024
NETWORK_ERROR = 'Could not reach the store securely. Query any saved attempt before retrying.'
TIMEOUT_ERROR = 'Store request timed out. Query any saved attempt before retrying.'


class TransportError(ValueError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@contextmanager
def _defer_sigint():
    # Complete process-handle ownership/cleanup before delivering Ctrl-C.
    # Preserve an embedding application's custom signal policy.
    if threading.current_thread() is not threading.main_thread() or signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        yield
        return
    pending = []
    signal.signal(signal.SIGINT, lambda *args: pending.append(True))
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    if pending:
        raise KeyboardInterrupt


def _exchange(request, ca_file):
    opener = build_opener(ProxyHandler({}), NoRedirect(),
                         HTTPSHandler(context=client_context(ca_file)))
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except HTTPError as error:
        response = error
    with response:
        status = response.code
        # Reject redirects before reading an attacker-controlled redirect body.
        if 300 <= status < 400:
            raise TransportError('Store redirected the request. Credentials were not forwarded.', status)
        chunks, size = [], 0
        while size <= RESPONSE_LIMIT:
            piece = response.read1(min(65536, RESPONSE_LIMIT + 1 - size))
            if not piece:
                break
            chunks.append(piece)
            size += len(piece)
        if size > RESPONSE_LIMIT:
            raise TransportError('Store response exceeded its limit.', status)
        # read1 may reach EOF without raising IncompleteRead. Do not accept a
        # valid JSON prefix when a fixed-length response was truncated.
        length = response.headers.get('Content-Length')
        if length is not None and (not length.isascii() or not length.isdecimal() or int(length) != size):
            raise TransportError('Store returned an incomplete or invalid response.', status)
        return (status, response.headers.get_content_type(),
                response.headers.get('X-Lefony-SHA256'), response.headers.get('Retry-After', 0),
                b''.join(chunks))


def _worker(pipe):
    # The parent owns Ctrl-C, including cleanup when a terminal signals the
    # entire process group. Do not interrupt a child midway through IPC.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        request, ca_file = pipe.recv()
        try:
            result = ('response', _exchange(request, ca_file))
        except TransportError as exc:
            result = ('error', (str(exc), exc.status))
        except TrustError as exc:
            result = ('error', (str(exc), 0))
        except (URLError, OSError, HTTPException, ValueError):
            # Peer text, URLs, CA paths and authorization values are private.
            result = ('error', (NETWORK_ERROR, 0))
        pipe.send(result)
    except (EOFError, OSError):
        pass
    finally:
        pipe.close()


def exchange(request, ca_file=None, *, timeout=TIMEOUT_SECONDS):
    """Return one bounded response, or stop/reap the worker on failure/Ctrl-C.

    StoreClient validates requests before this boundary (at most 8 MiB of body).
    Only one request is sent; no network error triggers an implicit retry.
    The deadline includes child startup, IPC and the complete HTTPS exchange.
    Cleanup adds at most one second of bounded joins under normal OS scheduling.
    """
    deadline = time.monotonic() + timeout
    context = multiprocessing.get_context('spawn')
    pipe, child = context.Pipe()
    process = context.Process(target=_worker, args=(child,), daemon=True)
    done, result = threading.Event(), []

    def transfer():
        try:
            pipe.send((request, ca_file))
            result.append(pipe.recv())
        except (EOFError, OSError):
            result.append(('error', (NETWORK_ERROR, 0)))
        finally:
            pipe.close()
            done.set()

    thread = threading.Thread(target=transfer, name='sdk-store-ipc', daemon=True)
    started = False
    try:
        with _defer_sigint():
            process.start()
            started = True
            child.close()
            thread.start()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError(TIMEOUT_ERROR)
            # Short waits also deliver Ctrl-C promptly on native Windows.
            if done.wait(min(.05, remaining)):
                break
        kind, value = result[0]
        if kind == 'error':
            raise TransportError(*value)
        return value
    finally:
        with _defer_sigint():
            child.close()
            if started:
                if process.is_alive():
                    process.terminate()
                process.join(.2)
                if process.is_alive():
                    process.kill()
                    process.join(.5)
                if thread.ident is not None:
                    thread.join(.2)
                else:
                    pipe.close()
                if process.is_alive() or thread.is_alive():
                    raise TransportError('Could not stop the store request worker. Check running SDK processes before retrying.')
                process.close()
            else:
                pipe.close()

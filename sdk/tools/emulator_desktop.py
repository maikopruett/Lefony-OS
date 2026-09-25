# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared window/process lifecycle for SDK app and native OS emulator sessions."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

from sdk_environment import SDK


def wait_for_boot_ui(channel):
    """Allow two normal 300 ms UI timer ticks before dismissing the USB sheet."""
    def guest_time():
        reply = channel.command('TIME GET')
        if not reply.startswith('VALUE '):
            raise RuntimeError('Guest clock unavailable during desktop startup')
        return int(reply[6:])
    start = guest_time()
    deadline = time.monotonic() + 10
    while guest_time() - start < 600:
        if time.monotonic() >= deadline:
            raise TimeoutError('Guest UI clock did not advance during desktop startup')
        time.sleep(.05)


def window_command(url, title, ready_file):
    if getattr(sys, 'frozen', False):
        directory = SDK.parent / 'emulator-window'
        if sys.platform == 'darwin':
            executable = directory / 'Lefony Emulator.app/Contents/MacOS/Lefony Emulator'
        else:
            executable = directory / ('Lefony Emulator.exe' if sys.platform == 'win32' else 'Lefony Emulator')
        if not executable.is_file():
            raise RuntimeError('Desktop window is missing from this SDK installation; reinstall the complete SDK.')
        command = [str(executable)]
    else:
        if importlib.util.find_spec('PySide6') is None:
            raise RuntimeError('Install sdk/requirements-emulator.txt with this Python interpreter to run the desktop emulator.')
        command = [sys.executable, str(SDK / 'tools/emulator_window.py')]
    return [*command, url, '--title', title, '--ready-file', str(ready_file)]


@contextmanager
def window_process(url, title, folder):
    ready = Path(folder) / 'desktop-ready'
    ready.unlink(missing_ok=True)
    log = Path(folder) / 'desktop-window.log'
    with log.open('wb') as errors:
        process = subprocess.Popen(window_command(url, title, ready), stdout=subprocess.DEVNULL, stderr=errors)
        try:
            yield process, ready, log
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


def serve_desktop(panel, title, alive):
    from emulator_ui import make_server
    with make_server(panel, title) as server:
        with window_process(server.url, title, panel.folder) as (window, ready, log):
            print('Lefony Emulator desktop window opened. Close the window or press Ctrl-C to finish.', flush=True)
            deadline = time.monotonic() + 30
            try:
                while not panel.stopped and alive():
                    code = window.poll()
                    if code is not None:
                        if code != 0 or not ready.is_file():
                            detail = log.read_text(encoding='utf-8', errors='replace')[-2000:]
                            raise RuntimeError('Desktop emulator window failed to start or exited unexpectedly. ' + detail)
                        break
                    if not ready.is_file() and time.monotonic() > deadline:
                        raise TimeoutError('Desktop emulator window did not load within 30 seconds')
                    server.handle_request()
                    panel.expire()
                if panel.failure:
                    raise RuntimeError('Emulator display connection failed') from panel.failure
            except KeyboardInterrupt:
                pass
            finally:
                if alive():
                    failure = sys.exception()
                    try:
                        panel.release()
                    except Exception:
                        if failure is None:
                            raise

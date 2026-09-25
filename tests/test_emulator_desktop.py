# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop process ownership, failure cleanup and frozen platform dispatch."""
from contextlib import contextmanager
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sdk/tools'))
import emulator_desktop as desktop
from emulator_window import validate_url

URL = 'http://127.0.0.1:12345/' + 'x' * 43 + '/'


@pytest.mark.parametrize('url', ['https://example.com/', 'file:///tmp/test',
    'http://localhost:1234/session/', 'http://127.0.0.1:1234/',
    'http://user@127.0.0.1:1234/session/', 'http://127.0.0.1:1234/session/?outside=1'])
def test_window_rejects_non_session_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_source_window_uses_current_python_and_exact_arguments(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop.importlib.util, 'find_spec', lambda name: object())
    command = desktop.window_command(URL, 'Counter with spaces', tmp_path / 'ready')
    assert command == [sys.executable, str(ROOT / 'sdk/tools/emulator_window.py'), URL,
                       '--title', 'Counter with spaces', '--ready-file', str(tmp_path / 'ready')]
    assert validate_url(URL) == URL


@pytest.mark.parametrize('host,relative', [('darwin','Lefony Emulator.app/Contents/MacOS/Lefony Emulator'),
                                         ('win32','Lefony Emulator.exe'), ('linux','Lefony Emulator')])
def test_frozen_window_is_bundled_not_system_browser(tmp_path, monkeypatch, host, relative):
    monkeypatch.setattr(desktop, 'SDK', tmp_path / 'sdk')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'platform', host)
    with pytest.raises(RuntimeError, match='missing'):
        desktop.window_command(URL, 'OS', tmp_path / 'ready')
    executable = tmp_path / 'emulator-window' / relative
    executable.parent.mkdir(parents=True)
    executable.write_text('fixture')
    assert desktop.window_command(URL, 'OS', tmp_path / 'ready')[0] == str(executable)


def test_missing_source_toolkit_is_an_error_not_browser_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop.importlib.util, 'find_spec', lambda name: None)
    with pytest.raises(RuntimeError, match='requirements-emulator'):
        desktop.window_command(URL, 'OS', tmp_path / 'ready')


@pytest.mark.parametrize('exit_code,ready,stopped,expected', [(0, True, False, None),
    (1, False, False, RuntimeError), (0, False, False, RuntimeError), (None, True, True, None)])
def test_window_exit_stop_and_failure_release_guest(tmp_path, monkeypatch, exit_code, ready, stopped, expected):
    events = []
    panel = SimpleNamespace(folder=tmp_path, stopped=stopped, failure=None,
                            release=lambda: events.append('release'))
    @contextmanager
    def server(panel, title):
        yield SimpleNamespace(url=URL)
    @contextmanager
    def window(*args):
        marker, log = tmp_path / 'ready', tmp_path / 'log'
        log.write_text('fixture error')
        if ready:
            marker.touch()
        try:
            yield SimpleNamespace(poll=lambda: exit_code), marker, log
        finally:
            events.append('window-cleanup')
    monkeypatch.setattr('emulator_ui.make_server', server)
    monkeypatch.setattr(desktop, 'window_process', window)
    if expected:
        with pytest.raises(expected):
            desktop.serve_desktop(panel, 'OS', lambda: True)
    else:
        desktop.serve_desktop(panel, 'OS', lambda: True)
    assert events == ['release', 'window-cleanup']


def test_window_cleanup_kills_an_unresponsive_process(tmp_path, monkeypatch):
    events = []
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: events.append('terminate'),
                              kill=lambda: events.append('kill'))
    def wait(timeout):
        events.append(('wait', timeout))
        if 'kill' not in events:
            raise desktop.subprocess.TimeoutExpired('window', timeout)
    process.wait = wait
    monkeypatch.setattr(desktop, 'window_command', lambda *args: ['fixture'])
    monkeypatch.setattr(desktop.subprocess, 'Popen', lambda *args, **kwargs: process)
    with desktop.window_process(URL, 'OS', tmp_path):
        pass
    assert events == ['terminate', ('wait', 3), 'kill', ('wait', 3)]


def test_window_bundle_checks_source_host_hashes_and_extra_files(tmp_path, monkeypatch):
    import json
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_emulator_window as builder
    binary = tmp_path / 'Lefony Emulator'
    binary.write_bytes(b'fixture')
    record = dict(system='Linux', machine='x86_64', qt_version=builder.VERSION,
                  source_sha256=builder.digest(ROOT / 'sdk/tools/emulator_window.py'),
                  executable=binary.name, files={binary.name: builder.digest(binary)})
    manifest = tmp_path / 'window.json'
    manifest.write_text(json.dumps(record))
    assert builder.verify(tmp_path, 'Linux', 'x86_64') == record
    with pytest.raises(ValueError, match='match this host'):
        builder.verify(tmp_path, 'Windows', 'AMD64')
    binary.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        builder.verify(tmp_path, 'Linux', 'x86_64')
    binary.write_bytes(b'fixture')
    (tmp_path / 'unexpected.dll').touch()
    with pytest.raises(ValueError, match='extra files'):
        builder.verify(tmp_path, 'Linux', 'x86_64')


@pytest.mark.parametrize('clock', ['stalled', 'unavailable'])
def test_boot_ui_wait_fails_boundedly(monkeypatch, clock):
    ticks = iter([0, 11])
    monkeypatch.setattr(desktop.time, 'monotonic', lambda: next(ticks))
    channel = SimpleNamespace(command=lambda command: 'VALUE 0' if clock == 'stalled' else 'ERR unsupported')
    with pytest.raises((TimeoutError, RuntimeError)):
        desktop.wait_for_boot_ui(channel)

# SPDX-License-Identifier: GPL-3.0-or-later
import http.client
import json
from pathlib import Path
import re
import sys
import threading
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
from emulator_ui import Panel, make_server, validate_input
from emulator_ui_page import page
from replay import KEYS


class Device:
    def __init__(self):
        self.events = []
        self.channel = SimpleNamespace(command=self.command)

    def command(self, command):
        self.events.append(command)
        return 'OK'

    def keys(self, names):
        self.events.append(list(names))


def test_panel_exposes_every_matrix_key_once_and_escapes_app_name():
    document = page('<script>untrusted</script>')
    names = re.findall(r'data-key="([a-z]+)"', document)
    assert len(names) == len(KEYS) == len(set(names))
    assert set(names) == set(KEYS)
    assert '<script>untrusted</script>' not in document
    assert '&lt;script&gt;untrusted&lt;/script&gt;' in document


@pytest.mark.parametrize('value', [None, {}, {'keys': [], 'touch': [], 'command': 'quit'},
    {'keys': ['onoff'], 'touch': []}, {'keys': ['one', 'one'], 'touch': []},
    {'keys': [1], 'touch': []}, {'keys': [], 'touch': [[0, 320, 0]]},
    {'keys': [], 'touch': [[0, 0, 240]]}, {'keys': [], 'touch': [[0, False, 0]]},
    {'keys': [], 'touch': [[0, 1, 2], [0, 3, 4]]}])
def test_untrusted_input_rejected_before_guest_commands(tmp_path, value):
    device = Device()
    panel = Panel(device, tmp_path, KEYS)
    with pytest.raises(ValueError):
        panel.input(value)
    assert device.events == []


def test_guest_edges_and_lease_release(tmp_path):
    device = Device()
    panel = Panel(device, tmp_path, KEYS)
    panel.input({'keys': ['shift', 'seven'], 'touch': [[0, 319, 239], [1, 0, 0]]})
    assert device.events == [['shift', 'seven'], 'TOUCH FRAME 2 0 319 239 1 0 0']
    panel.last_input -= 2
    panel.expire()
    assert device.events[-2:] == [[], 'TOUCH FRAME 0']
    assert panel.pressed_at == {} and panel.touch == []


def test_short_click_survives_guest_debounce(tmp_path, monkeypatch):
    now = [10.0]
    sleeps = []
    monkeypatch.setattr('emulator_ui.time.monotonic', lambda: now[0])
    monkeypatch.setattr('emulator_ui.time.sleep', sleeps.append)
    panel = Panel(Device(), tmp_path, KEYS)
    panel.input({'keys': ['ok'], 'touch': []})
    now[0] += .01
    panel.release()
    assert sleeps == pytest.approx([.07])


def test_repeated_same_key_has_a_visible_release_edge(tmp_path, monkeypatch):
    now = [10.0]
    sleeps = []
    monkeypatch.setattr('emulator_ui.time.monotonic', lambda: now[0])
    monkeypatch.setattr('emulator_ui.time.sleep', sleeps.append)
    panel = Panel(Device(), tmp_path, KEYS)
    panel.input({'keys': ['one'], 'touch': []})
    now[0] += .1
    panel.release()
    now[0] += .01
    panel.input({'keys': ['one'], 'touch': []})
    assert sleeps == pytest.approx([.04])


def test_local_http_origin_token_limits_and_stop(tmp_path):
    device = Device()
    panel = Panel(device, tmp_path, set(KEYS) | {'onoff'})
    with make_server(panel, 'Notebook') as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02})
        worker.start()
        root = server.url.split(server.authority)[1]

        def request(method, path, value=None, **overrides):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
            headers = {'Origin': 'http://' + server.authority, 'Content-Type': 'application/json'}
            headers.update(overrides)
            try:
                connection.request(method, path, body=json.dumps(value) if value is not None else None, headers=headers)
                response = connection.getresponse()
                return response.status, response.read(), dict(response.getheaders())
            finally:
                connection.close()
        try:
            status, body, headers = request('GET', root)
            assert status == 200 and b'Calculator touchscreen' in body
            assert headers['Cache-Control'] == 'no-store'
            assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
            assert request('GET', '/wrong-token/')[0] == 403
            assert request('GET', root, Host='attacker.example')[0] == 403
            value = {'keys': ['one'], 'touch': []}
            assert request('POST', root + 'input', value, Origin='https://attacker.example')[0] == 403
            assert request('POST', root + 'input', value, **{'Sec-Fetch-Site': 'cross-site'})[0] == 403
            assert request('POST', root + 'input', 'x' * 5000)[0] == 400
            assert request('POST', root + 'input', value, **{'Content-Type': 'text/plain'})[0] == 400
            assert device.events == []
            assert request('POST', root + 'input', value)[0] == 204
            assert request('POST', root + 'stop', {})[0] == 204
            assert device.events == [['one'], []]
            assert panel.stopped
        finally:
            server.shutdown()
            worker.join(2)

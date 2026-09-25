# SPDX-License-Identifier: GPL-3.0-or-later
"""Skin validation, bundled resources, input and HTTP boundary checks."""
import http.client
import hashlib
import json
import runpy
import tarfile
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
from emulator_skin import load_skins
from emulator_ui import Panel, make_server
from emulator_ui_page import page
from replay import Controls, KEYS


def test_bundled_skins_are_default_and_match_provenance(monkeypatch):
    monkeypatch.delenv('LEFONY_EMULATOR_ASSETS', raising=False)
    skins, assets = load_skins()
    assert len(skins) == 5 and len(assets) == 15
    assert all({key['name'] for key in skin['keys']} == set(KEYS) | {'onoff'} for skin in skins)
    medium = next(skin for skin in skins if skin['title'] == 'Medium')
    assert medium['screen'] == dict(x=28, y=58, width=320, height=240)
    base = Path(__file__).resolve().parents[1] / 'sdk/assets/prime'
    for name, digest in json.loads((base / 'provenance.json').read_text())['files'].items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == digest


def test_source_kit_contains_working_default_skins(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    archive = tmp_path / 'sdk.tar.gz'
    runpy.run_path(str(root / 'scripts/package_native_sdk.py'))['package'](archive)
    with tarfile.open(archive) as kit:
        kit.extractall(tmp_path / 'unpacked', filter='data')
    sdk = tmp_path / 'unpacked/lefony-native-sdk/sdk'
    monkeypatch.setattr('emulator_skin.SDK', sdk)
    monkeypatch.delenv('LEFONY_EMULATOR_ASSETS', raising=False)
    skins, assets = load_skins()
    assert len(skins) == 5 and len(assets) == 15
    assert (sdk / 'assets/prime/EULA_en.txt').is_file()
    assert (sdk.parent / 'docs/images/emulator-device-sdk.png').is_file()
    assert 'emulator-device-sdk.png' in (sdk / 'README.md').read_text()


def test_missing_asset_directory_fails_instead_of_using_generic_keyboard(tmp_path):
    with pytest.raises(ValueError, match='Skin directory'):
        load_skins(tmp_path)


@pytest.fixture
def synthetic_skin(tmp_path):
    (tmp_path / 'skins').mkdir()
    (tmp_path / 'images').mkdir()
    Image.new('RGB', (400, 800)).save(tmp_path / 'images/test.png')
    keys = ''.join(f'<key note="{name}" x="{(i%6)*50}" y="{300+(i//6)*45}" '
                   f'x2="{(i%6)*50+40}" y2="{340+(i//6)*45}"/>'
                   for i, name in enumerate([*KEYS, 'onoff']))
    xml = ('<skin><picture file="test.png"/><picture_hover file="test.png"/>'
           '<picture_pressed file="test.png"/><trans lang="EN" id="Test"/>'
           '<screen x="20" y="30" width="320" height="240"/>'
           '<keys xoffset="5" yoffset="7" xscale="1.1" yscale="1.1">'+keys+'</keys></skin>')
    (tmp_path / 'skins/test.primeskin').write_text(xml)
    return tmp_path


def test_transformed_regions(synthetic_skin):
    skins, assets = load_skins(synthetic_skin)
    assert len(assets) == 3 and len(skins[0]['keys']) == 51
    assert skins[0]['keys'][0] == dict(name='back', label='back', x=5, y=337, width=44, height=44)
    assert {k['name'] for k in skins[0]['keys']} == set(KEYS) | {'onoff'}


@pytest.mark.parametrize('replacement', ['../outside.png', '/tmp/outside.png'])
def test_image_paths_cannot_escape_asset_directory(synthetic_skin, replacement):
    path = synthetic_skin / 'skins/test.primeskin'
    path.write_text(path.read_text().replace('test.png', replacement))
    with pytest.raises(ValueError, match='local image'):
        load_skins(synthetic_skin)


def test_invalid_screen_and_duplicate_keys(synthetic_skin):
    path = synthetic_skin / 'skins/test.primeskin'
    original = path.read_text()
    path.write_text(original.replace('width="320"', 'width="999"'))
    with pytest.raises(ValueError, match='outside'):
        load_skins(synthetic_skin)
    path.write_text(original.replace('note="backspace"', 'note="back"'))
    with pytest.raises(ValueError, match='distinct'):
        load_skins(synthetic_skin)


def test_skin_labels_cannot_end_script():
    document = page('Preview', [{'title': '</script><script>bad()</script>'}])
    assert '</script><script>bad()' not in document
    assert '\\u003c/script>' in document


def test_only_declared_images_are_served(synthetic_skin, monkeypatch):
    monkeypatch.setenv('LEFONY_EMULATOR_ASSETS', str(synthetic_skin))
    panel = Panel(SimpleNamespace(), synthetic_skin, set(KEYS) | {'onoff'})
    with make_server(panel, 'Preview') as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        worker.start()
        root = server.url.split(server.authority)[1]
        try:
            for route, expected in [('skin/0/normal.png', 200), ('skin/../../eula/EULA_en.txt', 404), ('inventory.json', 404)]:
                connection = http.client.HTTPConnection(server.authority, timeout=2)
                connection.request('GET', root+route)
                response = connection.getresponse()
                data = response.read()
                assert response.status == expected
                if expected == 200:
                    assert data.startswith(b'\x89PNG')
                connection.close()
        finally:
            server.shutdown()
            worker.join(timeout=2)


def test_power_edges_use_separate_input_not_matrix():
    commands = []
    controls = Controls.__new__(Controls)
    controls.channel = SimpleNamespace(command=lambda c: commands.append(c) or 'OK')
    controls.held_keys = set()
    controls.keys(['onoff'])
    controls.keys(['onoff'])
    controls.keys([])
    assert commands == ['POWER STATE', 'KEY 116 1', 'KEY 116 0']


def test_power_key_wakes_emulator_without_immediately_resuspending():
    commands = []
    controls = Controls.__new__(Controls)
    def command(value):
        commands.append(value)
        return 'VALUE 1' if value == 'POWER STATE' else 'OK'
    controls.channel = SimpleNamespace(command=command)
    controls.held_keys = set()
    controls.keys(['onoff'])
    controls.keys([])
    assert commands == ['POWER STATE', 'POWER RESUME', 'KEY 116 0']

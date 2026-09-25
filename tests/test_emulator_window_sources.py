# SPDX-License-Identifier: GPL-3.0-or-later
"""Release sources must stay bound to the selected desktop window."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import emulator_window_sources as sources


@pytest.mark.parametrize('change', ['none', 'qt', 'runtime', 'version', 'window', 'native'])
def test_window_source_binding(tmp_path, monkeypatch, change):
    window, materials, qt = (tmp_path/n for n in ('window', 'materials', 'qt'))
    for path in (window, materials, qt):
        path.mkdir()
    (window/'window.json').write_text('manifest')
    (qt/'qt.tar.xz').write_bytes(b'qt source')
    (materials/'python.tar.gz').write_bytes(b'python source')
    (materials/'pyinstaller.tar.gz').write_bytes(b'bootloader source')
    monkeypatch.setattr(sources, 'QT_SOURCES', {'qt.tar.xz': {
        'bytes': 9, 'sha256': sources.digest(qt/'qt.tar.xz')}})
    monkeypatch.setattr(sources, 'verify', lambda _: {'files': {'native': 'binary-hash'}})
    manifest = {'components': [dict(component=name, version=version, inputs=[
        dict(file=name+'.tar.gz', sha256=sources.digest(materials/(name+'.tar.gz')))])
        for name, version in (('python', '3.12.3'), ('pyinstaller', '6.20.0'))]}
    record = dict(window_manifest_sha256=sources.digest(window/'window.json'),
        pyinstaller_version='6.20.0', files={'native': dict(component='python',
        version='3.12.3', bundled_sha256='binary-hash')})
    if change == 'qt': (qt/'qt.tar.xz').write_bytes(b'changed!!')
    if change == 'runtime': (materials/'python.tar.gz').write_bytes(b'changed')
    if change == 'version': record['files']['native']['version'] = '3.12.2'
    if change == 'window': (window/'window.json').write_text('changed')
    if change == 'native': record['files']['native']['bundled_sha256'] = 'changed'
    (materials/'manifest.json').write_text(json.dumps(manifest))
    inputs = tmp_path/'inputs.json'; inputs.write_text(json.dumps(record))
    if change == 'none':
        assert sources.verify_sources(window, inputs, materials, qt)['corresponding_sources_verified']
    else:
        with pytest.raises(ValueError):
            sources.verify_sources(window, inputs, materials, qt)

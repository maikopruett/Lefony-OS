# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenSSL packaging/data relocation gates; Windows PE execution is separate."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'sdk/tools')]
import native_desktop_openssl as runtime
import sdk_environment
import signing
from lfapp import pack
from test_native_app_package import META, image


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path/'original candidate'
    files = {name: name.encode() for name in (
        'bin/openssl.exe', 'bin/libcrypto-3-x64.dll', 'bin/libssl-3-x64.dll',
        'ssl/openssl.cnf', 'lib/ossl-modules/legacy.dll', 'lib/engines-3/capi.dll')}
    for name, data in files.items():
        path = root/'install'/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(data)
    (root/'sources').mkdir()
    (root/'sources/source.tar.gz').write_bytes(b'source')
    (root/'recipe.py').write_bytes(b'recipe')
    report = {'schema': 1, 'status': 'passed', 'platform': 'Windows', 'architecture': 'AMD64',
              'version': '3.fixture', 'files': {n: hashlib.sha256(d).hexdigest() for n,d in files.items()},
              'source_files': {'source.tar.gz': runtime.digest(root/'sources/source.tar.gz')},
              'recipes': {'recipe.py': runtime.digest(root/'recipe.py')}}
    (root/'candidate.json').write_text(json.dumps(report))
    return root, report


def test_staged_runtime_survives_relocation_and_is_exact(candidate, tmp_path):
    root, expected = candidate
    assert runtime.verify_candidate(root, root/'install/bin/openssl.exe') == expected
    staged = tmp_path/'stage'
    record = runtime.stage_runtime(root, expected, staged)
    moved = tmp_path/'moved SDK with spaces'/'openssl'
    moved.parent.mkdir();shutil.move(staged, moved)
    runtime.verify_runtime(moved, record)
    assert set(record['files']) == {'ssl/openssl.cnf','lib/ossl-modules/legacy.dll','lib/engines-3/capi.dll'}
    assert record['candidate_sha256'] == runtime.digest(root/'candidate.json')
    assert record['native_execution_qualified'] is False


@pytest.mark.parametrize('damage', ['tamper', 'missing', 'extra', 'symlink', 'source', 'recipe',
                                   'failed', 'architecture', 'required', 'escape', 'executable'])
def test_candidate_rejects_invalid_inputs(candidate, tmp_path, damage):
    root, report = candidate
    program = root/'install/bin/openssl.exe'
    if damage == 'tamper':(root/'install/ssl/openssl.cnf').write_bytes(b'changed')
    elif damage == 'missing':(root/'install/lib/ossl-modules/legacy.dll').unlink()
    elif damage == 'extra':(root/'install/extra.dll').write_bytes(b'extra')
    elif damage == 'symlink':
        path=root/'install/ssl/openssl.cnf';data=path.read_bytes();path.unlink()
        outside=tmp_path/'outside';outside.write_bytes(data);path.symlink_to(outside)
    elif damage == 'source':(root/'sources/source.tar.gz').write_bytes(b'changed')
    elif damage == 'recipe':(root/'recipe.py').write_bytes(b'changed')
    elif damage == 'failed':report['status']='failed'
    elif damage == 'architecture':report['architecture']='ARM64'
    elif damage == 'required':del report['files']['ssl/openssl.cnf']
    elif damage == 'escape':report['recipes']={'../outside': hashlib.sha256(b'outside').hexdigest()}
    else:program=tmp_path/'other.exe';shutil.copyfile(root/'install/bin/openssl.exe', program)
    (root/'candidate.json').write_text(json.dumps(report))
    with pytest.raises(ValueError):runtime.verify_candidate(root, program)


def test_source_materials_must_include_exact_recipes_and_archives(candidate):
    root, report = candidate
    sources={'components':[{'component':'windows-openssl','version':report['version'],
        'inputs':[{'sha256':value} for value in (*report['source_files'].values(), *report['recipes'].values())]}]}
    runtime.verify_candidate(root, root/'install/bin/openssl.exe', sources)
    sources['components'][0]['inputs'].pop()
    with pytest.raises(ValueError, match='corresponding sources'):
        runtime.verify_candidate(root, root/'install/bin/openssl.exe', sources)


def test_runtime_copy_race_and_post_freeze_tamper_rejected(candidate, tmp_path, monkeypatch):
    root, report = candidate
    copy = runtime.shutil.copyfile
    def damaged(source, target):
        copy(source, target);target.write_bytes(b'changed during copy')
    with monkeypatch.context() as patch:
        patch.setattr(runtime.shutil, 'copyfile', damaged)
        with pytest.raises(ValueError, match='file differs'):
            runtime.stage_runtime(root, report, tmp_path/'bad copy')
    staged=tmp_path/'good copy';record=runtime.stage_runtime(root, report, staged)
    (staged/'ssl/openssl.cnf').write_bytes(b'changed after freezing')
    with pytest.raises(ValueError, match='file differs'):runtime.verify_runtime(staged, record)


def test_windows_environment_is_child_only_and_rejects_missing_data(candidate, monkeypatch):
    root, _ = candidate
    ambient={'PATH':'unchanged', 'OPENSSL_CONF':'ambient', 'openssl_modules':'ambient modules'}
    result=sdk_environment.openssl_environment(root/'install', ambient)
    assert ambient['OPENSSL_CONF']=='ambient' and result['PATH']=='unchanged'
    assert result['OPENSSL_CONF']==str(root/'install/ssl/openssl.cnf')
    assert 'openssl_modules' not in result
    (root/'install/ssl/openssl.cnf').unlink()
    with pytest.raises(ValueError, match='Missing bundled'):
        sdk_environment.openssl_environment(root/'install', ambient)


def test_source_environment_keeps_explicit_host_configuration(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    ambient={'OPENSSL_CONF':'host config', 'OPENSSL_MODULES':'host modules'}
    assert sdk_environment.openssl_environment(environment=ambient)==ambient


def test_frozen_windows_signing_uses_absolute_tool_and_child_data(candidate, monkeypatch):
    root, _ = candidate
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'platform','win32')
    monkeypatch.setattr(sys,'_MEIPASS',str(root),raising=False)
    shutil.copytree(root/'install',root/'openssl')
    monkeypatch.setenv('OPENSSL_CONF','ambient config')
    def execute(command, **kwargs):
        assert command[0]==str(root/'toolchain/bin/openssl.exe')
        assert kwargs['env']['OPENSSL_CONF']==str(root/'openssl/ssl/openssl.cnf')
        assert kwargs['timeout']==30 and kwargs['check'] is True
        assert os.environ['OPENSSL_CONF']=='ambient config'
        return subprocess.CompletedProcess(command,0,stdout=b'checked')
    monkeypatch.setattr(signing.subprocess,'run',execute)
    assert signing.openssl('version')==b'checked'


def test_real_host_signing_with_relocated_configuration_and_poisoned_ambient(tmp_path, monkeypatch):
    """Native host OpenSSL exercises config/crypto; this does not execute PE."""
    program=shutil.which('openssl');assert program
    runtime_root=tmp_path/'moved OpenSSL data'
    (runtime_root/'ssl').mkdir(parents=True)
    (runtime_root/'lib/ossl-modules').mkdir(parents=True)
    (runtime_root/'lib/engines-3').mkdir()
    (runtime_root/'ssl/openssl.cnf').write_text('openssl_conf = init\n[init]\n')
    poison=tmp_path/'broken.cnf';poison.write_text('THIS IS NOT A CONFIGURATION\n')
    monkeypatch.setenv('OPENSSL_CONF',str(poison))
    monkeypatch.setenv('OPENSSL_MODULES',str(tmp_path/'absent modules'))
    original=signing.openssl
    monkeypatch.setattr(signing,'openssl',lambda *args,**kwargs: original(
        *args,**{**kwargs,'program':program,'runtime':runtime_root}))
    private=ROOT/'tests/fixtures/prime_g2_emulator_update_private.pem'
    public=ROOT/'tests/fixtures/prime_g2_emulator_update_public.pem'
    signed=signing.sign(pack(META,image()),private)
    assert signing.verify(signed,[public])==(META,image())
    assert os.environ['OPENSSL_CONF']==str(poison)

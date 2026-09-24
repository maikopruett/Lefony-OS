# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_sdk_windows_libusb as libusb
import build_sdk_windows_openssl as openssl


@pytest.fixture(params=[libusb,openssl],ids=['libusb','openssl'])
def builder(request):
    return request.param


@pytest.fixture
def sources(tmp_path,monkeypatch,builder):
    root=tmp_path/'input';root.mkdir()
    pins={}
    for name,data in (('source.dsc',b'descriptor'),('source.tar.xz',b'sources')):
        (root/name).write_bytes(data);pins[name]=hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(builder,'SOURCE_FILES',pins)
    return root,tmp_path/'output',pins


def test_exact_sources_are_copied_without_changing_inputs(sources,builder):
    root,out,pins=sources
    builder.copy_sources(root,out)
    assert set(p.name for p in out.iterdir())==set(pins)
    for n,h in pins.items():assert builder.digest(root/n)==builder.digest(out/n)==h


@pytest.mark.parametrize('kind',['changed','missing','symlink'])
def test_all_sources_are_verified_before_output_is_created(sources,kind,builder):
    root,out,_=sources;path=root/'source.tar.xz'
    if kind=='changed':path.write_bytes(b'changed')
    else:
        data=path.read_bytes();path.unlink()
        if kind=='symlink':
            target=root/'other';target.write_bytes(data);path.symlink_to(target)
    with pytest.raises(ValueError,match='differs from the pinned input'):
        builder.copy_sources(root,out)
    assert not out.exists()


def test_copy_race_is_reported_and_partial_source_retained(sources,monkeypatch,builder):
    root,out,_=sources;original=builder.shutil.copyfile
    def changed(a,b):
        original(a,b);b.write_bytes(b'changed while copying')
    monkeypatch.setattr(builder.shutil,'copyfile',changed)
    with pytest.raises(ValueError,match='changed during copy'):
        builder.copy_sources(root,out)
    assert out.exists()


@pytest.fixture
def assembly_sources(tmp_path,monkeypatch):
    source=tmp_path/'assembly';source.mkdir()
    pins={}
    for name in ('generator.pl','translator.pl'):
        old=('original '+name).encode();new=('patched '+name).encode()
        (source/name).write_bytes(old)
        pins[name]=(hashlib.sha256(old).hexdigest(),hashlib.sha256(new).hexdigest())
    monkeypatch.setattr(openssl,'PATCH_FILES',pins)
    patch=Path(openssl.__file__).parent/openssl.PATCH_NAME
    return source,patch


def test_mingw_patch_checks_both_outputs_and_is_idempotent(assembly_sources):
    source,patch=assembly_sources;calls=[]
    def run(label,command,cwd):
        calls.append(command)
        assert cwd==source and '--fuzz=0' in command
        for name in openssl.PATCH_FILES:(source/name).write_bytes(('patched '+name).encode())
    openssl.prepare_source(source,patch,run)
    openssl.prepare_source(source,patch,run)
    assert len(calls)==1


@pytest.mark.parametrize('kind',['changed','missing','symlink','mixed'])
def test_mingw_patch_rejects_unexpected_source_before_running(assembly_sources,kind):
    source,patch=assembly_sources;p=source/'generator.pl'
    if kind=='changed':p.write_bytes(b'unknown')
    elif kind=='mixed':p.write_bytes(b'patched generator.pl')
    else:
        p.unlink()
        if kind=='symlink':p.symlink_to(source/'translator.pl')
    before=(source/'translator.pl').read_bytes()
    def run(*args):pytest.fail('Unexpected context must not execute a patch')
    with pytest.raises(ValueError,match='Unexpected OpenSSL assembly source'):
        openssl.prepare_source(source,patch,run)
    assert (source/'translator.pl').read_bytes()==before


def test_mingw_patch_rejects_changed_patch(assembly_sources,tmp_path):
    source,_=assembly_sources;p=tmp_path/'patch';p.write_bytes(b'wrong patch')
    with pytest.raises(ValueError,match='patch differs'):
        openssl.prepare_source(source,p,lambda *args:pytest.fail('Must not execute changed patch'))


def test_mingw_patch_rejects_incomplete_patch_output(assembly_sources):
    source,patch=assembly_sources
    with pytest.raises(ValueError,match='patch output differs'):
        openssl.prepare_source(source,patch,lambda *args:None)

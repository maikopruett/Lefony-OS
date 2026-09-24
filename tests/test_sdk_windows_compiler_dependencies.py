# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_sdk_windows_compiler_dependencies as builder


def test_relocated_metadata_keeps_library_bytes_and_records_original_hashes(tmp_path):
    (tmp_path/'lib/pkgconfig').mkdir(parents=True)
    old='/old/dependencies/install'
    la=tmp_path/'lib/libgmp.la';la.write_text("libdir='"+old+"/lib'\ndependency_libs=''\n")
    mpfr=tmp_path/'lib/libmpfr.la';mpfr.write_text("dependency_libs='"+old+"/lib/libgmp.la'\n")
    pc=tmp_path/'lib/pkgconfig/gmp.pc';pc.write_text('prefix='+old+'\nlibdir=${prefix}/lib\n')
    binary=tmp_path/'lib/libgmp.a';binary.write_bytes(old.encode())
    originals={p.relative_to(tmp_path).as_posix():builder.digest(p) for p in (la,mpfr,pc)}
    report=builder.relocate_base_metadata(tmp_path)
    assert report['original_prefix']==old and set(report['files'])==set(originals)
    for name,checksum in originals.items():
        assert report['files'][name]['before']==checksum
        assert report['files'][name]['after']==builder.digest(tmp_path/name)
        assert old not in (tmp_path/name).read_text()
    assert binary.read_bytes()==old.encode()


def candidate(root, **changes):
    files={}
    for name in ('include/gmp.h','include/mpfr.h','lib/libgmp.a','lib/libmpfr.a'):
        path=root/'install'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
        files[name]=builder.digest(path)
    data={'status':'passed','platform':'Windows','architecture':'AMD64','files':files,**changes}
    path=root/'candidate.json';path.write_text(json.dumps(data))
    return builder.digest(path),data


def test_base_requires_selected_hash_and_exact_installed_files(tmp_path):
    checksum,expected=candidate(tmp_path)
    assert builder.verify_base(tmp_path,checksum)==expected
    with pytest.raises(ValueError,match='selected hash'):builder.verify_base(tmp_path,'0'*64)
    (tmp_path/'install/include/gmp.h').write_bytes(b'changed header')
    with pytest.raises(ValueError,match='file changed'):builder.verify_base(tmp_path,checksum)


@pytest.mark.parametrize('changes',[{'status':'failed'},{'platform':'Linux'},{'architecture':'ARM64'},{'files':{}}])
def test_base_refuses_incomplete_or_other_platform_candidates(tmp_path,changes):
    checksum,_=candidate(tmp_path,**changes)
    with pytest.raises(ValueError):builder.verify_base(tmp_path,checksum)


@pytest.mark.parametrize('name',['../outside.a','/outside.a'])
def test_base_does_not_follow_manifest_paths_outside_install(tmp_path,name):
    checksum,_=candidate(tmp_path,files={name:'0'*64})
    with pytest.raises(ValueError,match='file changed'):builder.verify_base(tmp_path,checksum)


def test_pinned_source_validation_finishes_before_copying(tmp_path,monkeypatch):
    root=tmp_path/'materials';archives=root/'package/archives';archives.mkdir(parents=True)
    (archives/'first.dsc').write_bytes(b'first')
    (archives/'second.tar.xz').write_bytes(b'wrong')
    lock=tmp_path/'pins.json';lock.write_text(json.dumps({'test':{'directory':'package','archives':{
        'first.dsc':hashlib.sha256(b'first').hexdigest(),'second.tar.xz':hashlib.sha256(b'expected').hexdigest()}}}))
    monkeypatch.setattr(builder,'LOCK',lock)
    out=tmp_path/'sources';out.mkdir()
    with pytest.raises(ValueError,match='differs from its pin'):builder.copy_sources(root,out)
    assert not list(out.iterdir())

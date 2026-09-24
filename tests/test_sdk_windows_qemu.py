# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_sdk_windows_qemu as builder


@pytest.fixture
def dependency(tmp_path):
    install=tmp_path/'install';(install/'lib/pkgconfig').mkdir(parents=True)
    for n in ('glib-2.0','gmodule-2.0','gthread-2.0','sdl2','pixman-1','libusb-1.0','zlib'):
        (install/'lib/pkgconfig'/(n+'.pc')).write_text(n)
    c={'status':'passed','platform':'Windows','architecture':'AMD64',
       'files':{p.relative_to(install).as_posix():builder.digest(p) for p in install.rglob('*') if p.is_file()}}
    manifest=tmp_path/'candidate.json';manifest.write_text(json.dumps(c))
    return tmp_path,builder.digest(manifest)


def test_accept_exact_dependency_candidate(dependency):
    root,h=dependency;prefix,c=builder.dependency_prefix(root,h)
    assert prefix==root/'install' and c['status']=='passed'


@pytest.mark.parametrize('kind',['changed','missing','extra','outside_symlink'])
def test_reject_changed_dependency_files(dependency,tmp_path,kind):
    root,h=dependency;p=root/'install/lib/pkgconfig/zlib.pc'
    if kind=='changed':p.write_text('changed')
    elif kind=='missing':p.unlink()
    elif kind=='extra':(p.parent/'unrecorded.dll').write_bytes(b'extra')
    else:
        q=root/'outside';q.write_bytes(p.read_bytes());p.unlink();p.symlink_to(q)
    with pytest.raises(ValueError,match='dependency file'):builder.dependency_prefix(root,h)


def test_reject_changed_manifest(dependency):
    root,h=dependency;(root/'candidate.json').write_text('{}')
    with pytest.raises(ValueError,match='candidate hash mismatch'):builder.dependency_prefix(root,h)


@pytest.mark.parametrize('field,value',[('status','failed'),('platform','Linux'),('architecture','ARM64')])
def test_reject_wrong_build_candidate(dependency,field,value):
    root,_=dependency;p=root/'candidate.json';c=json.loads(p.read_text());c[field]=value;p.write_text(json.dumps(c))
    with pytest.raises(ValueError,match='completed Windows'):builder.dependency_prefix(root,builder.digest(p))


def test_required_library_metadata_cannot_be_omitted(dependency):
    root,_=dependency;p=root/'candidate.json';c=json.loads(p.read_text());n='lib/pkgconfig/sdl2.pc';del c['files'][n];(root/'install'/n).unlink();p.write_text(json.dumps(c))
    with pytest.raises(ValueError,match='Missing Windows QEMU library'):builder.dependency_prefix(root,builder.digest(p))

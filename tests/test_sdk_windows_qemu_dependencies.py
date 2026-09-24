# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_sdk_windows_qemu_dependencies as builder


def test_retained_recipe_uses_its_own_pins(tmp_path):
    records=builder.retain_recipes(tmp_path)
    for name,h in records.items():assert builder.digest(tmp_path/name)==h
    code='import sys;sys.path.insert(0,sys.argv[1]);import build_sdk_windows_qemu_dependencies as b;print(b.digest(b.LOCK))'
    r=subprocess.run([sys.executable,'-I','-c',code,str(tmp_path)],cwd=tmp_path,capture_output=True,text=True,check=True,timeout=10)
    assert r.stdout.strip()==builder.digest(builder.LOCK)


@pytest.fixture
def inputs(tmp_path,monkeypatch):
    materials=tmp_path/'materials';gnu=tmp_path/'gnu';gnu.mkdir();out=tmp_path/'out';out.mkdir()
    pins={}
    for name,kind in [('one','gnu'),('two','debian')]:
        folder=gnu if kind=='gnu' else materials/name/'archives';folder.mkdir(parents=True,exist_ok=True)
        p=folder/(name+'.tar.xz');p.write_bytes(name.encode())
        pins[name]={'kind':kind,'directory':name,'archives':{p.name:builder.digest(p)}}
    lock=tmp_path/'pins.json';lock.write_text(json.dumps(pins));monkeypatch.setattr(builder,'LOCK',lock)
    return materials,gnu,out,pins


def test_sources_are_copied_exactly(inputs):
    materials,gnu,out,pins=inputs
    assert builder.copy_sources(materials,gnu,out)==pins
    for n,p in pins.items():
        for f,h in p['archives'].items():assert builder.digest(out/n/f)==h


@pytest.mark.parametrize('name',['one','two'])
@pytest.mark.parametrize('damage',['changed','missing','symlink'])
def test_invalid_source_rejected_before_copy(inputs,name,damage):
    materials,gnu,out,pins=inputs
    folder=gnu if name=='one' else materials/name/'archives';p=folder/(name+'.tar.xz')
    if damage=='changed':p.write_bytes(b'changed')
    else:
        data=p.read_bytes();p.unlink()
        if damage=='symlink':
            q=folder/'other';q.write_bytes(data);p.symlink_to(q)
    with pytest.raises(ValueError,match='differs from the pinned input'):builder.copy_sources(materials,gnu,out)
    assert not list(out.iterdir())


def test_copy_race_cannot_produce_accepted_source(inputs,monkeypatch):
    materials,gnu,out,_=inputs;copy=builder.shutil.copyfile
    def race(src,dst):copy(src,dst);dst.write_bytes(b'racing bytes')
    monkeypatch.setattr(builder.shutil,'copyfile',race)
    with pytest.raises(ValueError,match='changed during copy'):builder.copy_sources(materials,gnu,out)


def archive(tmp_path,names):
    p=tmp_path/'source.tar.gz'
    with tarfile.open(p,'w:gz') as t:
        for n in names:
            m=tarfile.TarInfo(n);m.size=1;t.addfile(m,io.BytesIO(b'x'))
    return p


def test_gnu_source_extraction_keeps_expected_root(tmp_path):
    p=archive(tmp_path,['source-1/configure']);out=tmp_path/'out';out.mkdir()
    source=builder.extract_gnu(p,out,'source-1')
    assert (source/'configure').read_bytes()==b'x'


@pytest.mark.parametrize('names',[['/source-1/configure'],['source-1/../escape'],['other/configure'],['source-1/a','source-1/a']])
def test_gnu_source_paths_rejected_before_extraction(tmp_path,names):
    p=archive(tmp_path,names);out=tmp_path/'out';out.mkdir()
    with pytest.raises(ValueError,match='unexpected path'):builder.extract_gnu(p,out,'source-1')
    assert not list(out.iterdir())


def test_gnu_source_external_link_is_rejected(tmp_path):
    p=tmp_path/'source.tar.gz'
    with tarfile.open(p,'w:gz') as t:
        m=tarfile.TarInfo('source-1/link');m.type=tarfile.SYMTYPE;m.linkname='../../outside';t.addfile(m)
    with pytest.raises(tarfile.LinkOutsideDestinationError):builder.extract_gnu(p,tmp_path/'out','source-1')
    assert not (tmp_path/'outside').exists()

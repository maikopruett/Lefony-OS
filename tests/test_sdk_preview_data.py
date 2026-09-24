# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import pytest
from test_sdk_archive import signed,snapshot,encoded,PUBLIC,signing
import archive_format
from preview_data import Checkpoints,compose,fixtures,fixture_identity,Part,regular


def unsigned(tmp_path,version='2.0.0',schema=0,app_id='document',name='app'):
    path=tmp_path/(name+'.lfapp');path.write_bytes(signing.envelope(signed(version,app_id,schema))[1]);return path


def saved(tmp_path,raw,name='saved'):
    path=tmp_path/(name+'.lfarchive');path.write_bytes(raw);return path,hashlib.sha256(raw).hexdigest()


def test_nested_fixtures_and_empty_entries_become_verified_named_data(tmp_path):
    inputs=tmp_path/'fixtures';(inputs/'docs/empty').mkdir(parents=True)
    data=bytes(range(256))*513;(inputs/'docs/data.bin').write_bytes(data);(inputs/'zero').write_bytes(b'')
    before=fixture_identity(inputs);dest=tmp_path/'seed'
    package,result=compose(unsigned(tmp_path),dest,fixture_dir=inputs)
    assert result.signatures_checked and len(result.snapshots)==1
    entries={e.path:e for e in result.snapshots[0].entries}
    assert set(entries)=={'docs','docs/empty','docs/data.bin','zero'}
    assert entries['docs/empty'].directory and entries['zero'].content.size==0
    assert entries['docs/data.bin'].content.sha256==hashlib.sha256(data).hexdigest()
    assert result.snapshots[0].package.sha256==hashlib.sha256(package).hexdigest()
    assert fixture_identity(inputs)==before


def test_same_version_source_edit_keeps_saved_private_files_and_original_snapshot(tmp_path):
    original=signed();raw=encoded(snapshot(original,b'private',(('dir',None),('dir/notes',b'written by app'))))
    path,sha=saved(tmp_path,raw);source=unsigned(tmp_path)
    # Change code bytes while preserving the declared version and schema.
    from lfapp import unpack,pack
    metadata,elf=unpack(source.read_bytes());elf=bytearray(elf);elf[-4:] = b'\x01\x00\x00\xef'
    source.write_bytes(pack(metadata,elf))
    package,result=compose(source,tmp_path/'next',saved=path,saved_hash=sha)
    assert package!=original and result.snapshots[0].metadata['version']=='2.0.0'
    assert result.snapshots[0].private.sha256==hashlib.sha256(b'private').hexdigest()
    assert result.snapshots[0].entries[1].content.sha256==hashlib.sha256(b'written by app').hexdigest()
    assert path.read_bytes()==raw


def test_versioned_schema_migration_retains_the_exact_previous_pair(tmp_path):
    path,sha=saved(tmp_path,encoded(snapshot(signed(),b'old schema',(('note',b'old data'),))))
    dest=tmp_path/'upgraded';_,result=compose(unsigned(tmp_path,'3.0.0',schema=1),dest,saved=path,saved_hash=sha)
    assert len(result.snapshots)==2 and result.high_version==(3,0,0)
    current,old=result.snapshots
    assert current.metadata['data_schema']==1 and current.data_schema==0
    assert old.metadata['version']=='2.0.0' and old.package.sha256==hashlib.sha256(signed()).hexdigest()
    assert current.private.sha256==old.private.sha256 and current.entries[0].content.sha256==old.entries[0].content.sha256
    _,again=compose(unsigned(tmp_path,'3.0.0',schema=1,name='retry'),tmp_path/'rebuilt',saved=dest,saved_hash=result.sha256)
    assert len(again.snapshots)==2 and again.snapshots[1].package.sha256==old.package.sha256
    with pytest.raises(ValueError,match='pending app upgrade'):
        compose(unsigned(tmp_path,'4.0.0',schema=1,name='later'),tmp_path/'blocked',saved=dest,saved_hash=result.sha256)


@pytest.mark.parametrize('kind',['app','version','schema','hash','high'])
def test_incompatible_preview_data_is_preserved_with_actionable_error(tmp_path,kind):
    raw=encoded(snapshot(signed(),b'preserved'),high=(4,0,0) if kind=='high' else (2,0,0))
    path,sha=saved(tmp_path,raw);source=unsigned(tmp_path,'1.0.0' if kind=='version' else '3.0.0' if kind=='high' else '2.0.0',
        schema=1 if kind=='schema' else 0,app_id='other' if kind=='app' else 'document')
    with pytest.raises(ValueError):compose(source,tmp_path/'bad',saved=path,saved_hash='0'*64 if kind=='hash' else sha)
    assert path.read_bytes()==raw


def test_checkpoints_atomically_select_verified_data_and_keep_one_previous(tmp_path,monkeypatch):
    store=Checkpoints(tmp_path);assert store.read() is None
    first,_=saved(tmp_path,encoded(snapshot(signed(),b'first')),'one')
    a=store.commit(first,None,None);assert store.path(store.read()).read_bytes()==first.read_bytes()
    second,_=saved(tmp_path,encoded(snapshot(signed(),b'second')),'two')
    before=store.receipt.read_bytes();original=os.replace
    def failure(source,target):
        if target==store.receipt:raise OSError('receipt publication failed')
        return original(source,target)
    with monkeypatch.context() as m:
        m.setattr(os,'replace',failure)
        with pytest.raises(OSError):store.commit(second,None,a)
    assert store.receipt.read_bytes()==before and store.path(store.read()).read_bytes()==first.read_bytes()
    b=store.commit(second,'1'*64,a);assert b['previous']==a['archive']
    third,_=saved(tmp_path,encoded(snapshot(signed(),b'third')),'three')
    c=store.commit(third,'1'*64,b)
    assert {p.stem for p in store.directory.glob('*.lfarchive')}=={b['archive'],c['archive']}


def test_snapshot_changes_and_damaged_receipts_never_become_a_new_checkpoint(tmp_path):
    source=io.BytesIO(b'changed');part=Part(source,0,7,hashlib.sha256(b'initial').hexdigest())
    with pytest.raises(ValueError,match='changed'):part.write(io.BytesIO())
    store=Checkpoints(tmp_path);store.receipt.write_text(json.dumps({'schema':1,'archive':'../outside'}))
    with pytest.raises(ValueError,match='receipt'):store.read()
    source,sha=saved(tmp_path,encoded(snapshot(signed())))
    a=store.commit(source,None,None);store.path(a).write_bytes(b'damaged')
    with pytest.raises(ValueError,match='damaged'):store.commit(source,None,a)
    assert store.read()['archive']==sha


@pytest.mark.parametrize('kind',['symlink','fifo','path','quota','count'])
def test_fixture_contract_rejects_unbounded_or_indirect_inputs(tmp_path,kind):
    folder=tmp_path/'fixtures';folder.mkdir()
    if kind=='symlink':(folder/'outside').symlink_to(tmp_path)
    elif kind=='fifo':
        if not hasattr(os,'mkfifo'):pytest.skip('no FIFO support')
        os.mkfifo(folder/'pipe')
    elif kind=='path':(folder/('x'*49)).write_bytes(b'')
    elif kind=='quota':
        with (folder/'large').open('wb') as f:f.truncate(32*1024*1024+1)
    else:
        for i in range(128):(folder/str(i)).mkdir()
    with pytest.raises(ValueError):fixtures(folder)


def test_fixture_identity_tracks_empty_directories_and_content(tmp_path):
    folder=tmp_path/'fixtures';folder.mkdir();a=fixture_identity(folder)
    (folder/'empty').mkdir();b=fixture_identity(folder);assert b!=a
    (folder/'file').write_text('data');c=fixture_identity(folder);assert c!=b
    (folder/'file').write_text('edit');assert fixture_identity(folder)!=c


def test_checkpoint_directory_and_file_symlinks_are_refused(tmp_path):
    real=tmp_path/'real';real.mkdir();project=tmp_path/'project';project.mkdir();(project/'.lefony').symlink_to(real)
    with pytest.raises(ValueError,match='symlink'):Checkpoints(project)
    file=tmp_path/'data';file.write_bytes(b'private');link=tmp_path/'link';link.symlink_to(file)
    if hasattr(os,'O_NOFOLLOW'):
        with pytest.raises(OSError):
            with regular(link):pass


def test_interrupted_preview_marks_stale_and_keeps_checkpoint_and_image(tmp_path,monkeypatch):
    import preview
    from PIL import Image
    project=tmp_path/'project'
    shutil.copytree(Path(__file__).resolve().parents[1]/'sdk/templates/basic',project)
    output=project/'build/preview';output.mkdir(parents=True)
    Image.new('RGB',(320,240),'green').save(output/'frame.png')
    image=(output/'frame.png').read_bytes()
    store=Checkpoints(project)
    source,_=saved(tmp_path,encoded(snapshot(signed(),b'preserved')))
    receipt=store.commit(source,None,None)
    (output/'status.json').write_text(json.dumps({'status':'ready','checkpoint':receipt}))
    def interrupt(*args,**kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(preview.subprocess,'run',interrupt)
    with pytest.raises(KeyboardInterrupt):preview.once(project,tmp_path/'qemu',tmp_path/'firmware')
    assert store.read()==receipt and store.path(receipt).read_bytes()==source.read_bytes()
    assert (output/'frame.png').read_bytes()==image
    assert json.loads((output/'status.json').read_text())['status']=='cancelled'
    assert 'STALE' in (output/'index.html').read_text()

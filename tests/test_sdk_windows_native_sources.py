# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned component assembly and final source correspondence; no PE execution."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collect_native_windows_sources as collect
import native_desktop_windows_sources as native
import windows_python_sources as wheels
import windows_cpython_sources as cpython


def sha(data):return hashlib.sha256(data).hexdigest()


def put(root,name,data):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p


def gcc_archive(path):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:xz') as tar:
        for n in ('COPYING','COPYING3','COPYING.LIB','COPYING3.LIB','COPYING.RUNTIME'):
            data=('exact upstream '+n).encode();m=tarfile.TarInfo('gcc-13.2.0/'+n);m.size=len(data);tar.addfile(m,io.BytesIO(data))
    path.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(path,'w:gz') as tar:
        data=stream.getvalue();m=tarfile.TarInfo('gcc-13-13.2.0/gcc-13.2.0.tar.xz');m.size=len(data);tar.addfile(m,io.BytesIO(data))


@pytest.fixture
def inputs(tmp_path,monkeypatch):
    artifacts={n:tmp_path/n for n in ('compiler','gdb','qemu','libraries')}
    for root in artifacts.values():root.mkdir()
    for name,g in collect.GROUPS.items():
        root=artifacts[g['artifact']]
        for prefix in g['installed']:put(root,prefix+'/tool.exe',('binary '+prefix).encode())
        prefix=g['prefix']+'/' if g['prefix'] else ''
        put(root,prefix+'sources/source.tar',b'original source archive')
        put(root,prefix+'notices/LICENSE',b'original license')
    for name in ('compiler','gdb','qemu'):
        gcc_archive(artifacts[name]/'gcc-base-sources/gcc-13_13.2.0.orig.tar.gz')
        put(artifacts[name],'source-collection-recipes/__pycache__/build.pyc',b'generated cache')
    lock={'schema':1,'platform':'windows-AMD64','artifacts':{}}
    for name,root in artifacts.items():
        sums=''.join(collect.digest(p)+'  '+p.relative_to(root).as_posix()+'\n' for p in sorted(root.rglob('*')) if p.is_file())
        (root/'SHA256SUMS').write_text(sums)
        lock['artifacts'][name]={'version':'fixture','archive_sha256':'0'*64,'sums_sha256':sha(sums.encode())}
    path=tmp_path/'lock.json';path.write_text(json.dumps(lock))
    python=tmp_path/'python';python.mkdir();components=[]
    for i in range(16):
        name='python-fixture-'+str(i);p=put(python,name+'/LICENSE',b'fixture Python notice')
        components.append({'component':name,'files':{p.relative_to(python).as_posix():collect.digest(p)}})
    (python/'wheels').mkdir();(python/'manifest.json').write_text(json.dumps({'schema':1,'platform':'windows-AMD64','components':components}))
    # Python's independent material gates have their own real archive tests.
    monkeypatch.setattr(wheels,'verify_materials',lambda *args:None)
    monkeypatch.setattr(cpython,'verify_materials',lambda *args:None)
    return artifacts,path,lock,python


def test_pinned_components_collect_sources_and_nested_gcc_terms(inputs,tmp_path):
    artifacts,path,_,python=inputs;out=tmp_path/'out'
    manifest=collect.collect(python,artifacts,out,lock_path=path)
    assert len(manifest['components'])==21 and not manifest['complete_desktop_sources']
    assert collect.verify_materials(out,manifest,lock_path=path)==manifest['windows_tool_inputs']
    assert (out/'windows-qemu/notices/gcc-runtime/COPYING.RUNTIME').read_bytes()==b'exact upstream COPYING.RUNTIME'
    assert not list(out.rglob('tool.exe'))
    assert not list(out.rglob('*.pyc'))
    assert manifest['windows_tool_inputs']


@pytest.mark.parametrize('change',['modified','missing','extra','linked_file','linked_dir','inventory'])
def test_input_artifact_changes_rejected(inputs,tmp_path,change):
    artifacts,_,lock,_=inputs;root=artifacts['compiler'];p=root/'sources/source.tar'
    if change=='modified':p.write_bytes(b'changed')
    elif change=='missing':p.unlink()
    elif change=='extra':put(root,'extra',b'x')
    elif change=='linked_file':p.unlink();p.symlink_to(root/'notices/LICENSE')
    elif change=='linked_dir':(root/'extra').symlink_to(tmp_path,target_is_directory=True)
    else:(root/'SHA256SUMS').write_text('changed inventory')
    with pytest.raises(ValueError):collect.verify_artifact(root,lock['artifacts']['compiler'])


@pytest.mark.parametrize('change',['source','notice','self_consistent_catalog','removed_notice','extra','linked','provenance'])
def test_assembled_materials_cannot_rewrite_pinned_provenance(inputs,tmp_path,change):
    artifacts,path,_,python=inputs;out=tmp_path/'out';manifest=collect.collect(python,artifacts,out,lock_path=path)
    comp=next(c for c in manifest['components'] if c['component']=='windows-qemu')
    if change=='source':(out/'windows-qemu/inputs/sources/source.tar').write_bytes(b'changed')
    elif change=='notice':(out/'windows-qemu/notices/gcc-runtime/COPYING.RUNTIME').write_bytes(b'changed')
    elif change=='self_consistent_catalog':
        n=next(iter(comp['installed_inputs']));comp['installed_inputs'][n]='1'*64
        manifest['windows_tool_inputs']['windows-qemu/'+n]['sha256']='1'*64
    elif change=='removed_notice':
        n='windows-qemu/notices/gcc-runtime/COPYING.RUNTIME';(out/n).unlink();comp['files'].pop(n)
        comp['installed_notices']=[x for x in comp['installed_notices'] if x['file']!=n]
    elif change=='extra':put(out,'windows-qemu/extra',b'x')
    elif change=='linked':(out/'windows-qemu/extra').symlink_to(tmp_path,target_is_directory=True)
    else:
        n='windows-qemu/provenance/SHA256SUMS';(out/n).write_text('changed');comp['files'][n]=collect.digest(out/n)
    with pytest.raises(ValueError):collect.verify_materials(out,manifest,lock_path=path)


def test_copy_race_is_rejected(tmp_path,monkeypatch):
    source=put(tmp_path,'source',b'original');copy=collect.shutil.copyfile
    def change(a,b):copy(a,b);b.write_bytes(b'changed')
    monkeypatch.setattr(collect.shutil,'copyfile',change)
    with pytest.raises(ValueError,match='during copying'):collect.copy_checked(source,tmp_path/'target',sha(b'original'))


def test_native_source_audit_binds_tools_and_preserves_all_same_hash_providers(tmp_path):
    bundle=tmp_path/'bundle';binary=b'original input'
    put(bundle,'lefony-sdk.exe',b'generated launcher');put(bundle,'_internal/toolchain/bin/gcc.exe',binary)
    put(bundle,'_internal/runtime/qemu.exe',binary);put(bundle,'_internal/toolchain/lib/crt.o',b'ARM object')
    comp={'component':'compiler','version':'1','inputs':[{'file':'source','sha256':'0'*64}]}
    manifest={'components':[comp],'windows_tool_inputs':{'compiler/gcc.exe':{'component':'compiler','version':'1','sha256':sha(binary)},'compiler/crt.o':{'component':'compiler','version':'1','sha256':sha(b'ARM object')}}}
    manifest['windows_tool_inputs']['compiler/gcc-alias.exe']={'component':'compiler','version':'1','sha256':sha(binary)}
    cp={'python_full_version':'3.14.7','native_files':{}}
    wheel={'distributions':[{'name':'pyinstaller','version':'1','native_files':{'PyInstaller/bootloader/Windows-64bit-intel/run.exe':sha(b'bootloader')},'native_sources':{'PyInstaller/bootloader/Windows-64bit-intel/run.exe':['pyinstaller']}}]}
    result=native.record_bundle(bundle,manifest,cp,wheel)
    assert len(result['files'])==3 and not result['native_execution_qualified']
    assert len(result['files']['_internal/toolchain/bin/gcc.exe']['providers'])==2
    put(bundle,'_internal/runtime/qemu.exe',b'changed')
    with pytest.raises(ValueError,match='Unmapped or changed'):native.record_bundle(bundle,manifest,cp,wheel)

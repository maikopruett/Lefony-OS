# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime/source byte gates and hostile archive layouts, without Windows execution."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import struct
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import windows_cpython_sources as cpython


def sha(data):return hashlib.sha256(data).hexdigest()


def pe_bytes():
    data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80)
    data[0x80:0x84]=b'PE\0\0';struct.pack_into('<H',data,0x84,0x8664)
    return bytes(data)


@pytest.fixture
def inputs(tmp_path):
    cache=tmp_path/'cache';cache.mkdir()
    runtime=cache/'python-3.14.7-amd64.zip'
    files={'python314.dll':pe_bytes(),'DLLs/_ctypes.pyd':pe_bytes(),
           'LICENSE.txt':b'Original runtime terms','Lib/pathlib.py':b'# fixture stdlib\n'}
    with zipfile.ZipFile(runtime,'w') as z:
        for n,data in files.items():z.writestr(n,data)
    source=cache/'Python-3.14.7.tar.xz'
    with tarfile.open(source,'w:xz') as t:
        data=b'Original source terms';m=tarfile.TarInfo('Python/LICENSE');m.size=len(data);t.addfile(m,io.BytesIO(data))
    def item(path,role):return {'file':path.name,'sha256':cpython.digest(path),'bytes':path.stat().st_size,'url':'https://example.test/'+path.name,'role':role}
    runtime_item=item(runtime,'runtime')
    manifest=cache/'windows-3.14.7.json';manifest.write_text(json.dumps({'versions':[{'id':'pythoncore-3.14-64','sort-version':'3.14.7','url':runtime_item['url'],'hash':{'sha256':runtime_item['sha256']}}]}))
    sbom=cache/(runtime.name+'.spdx.json');sbom.write_text(json.dumps({'packages':[]}))
    lock={'schema':1,'platform':'windows-AMD64','python_full_version':'3.14.7','release_id':'pythoncore-3.14-64','scope':'Public fixture',
          'artifacts':[runtime_item,item(source,'source'),item(manifest,'metadata'),item(sbom,'metadata')],
          'sources':[],'native_files':{n:{'sha256':sha(data),'bytes':len(data),'machine':0x8664,'sources':['cpython']} for n,data in files.items() if n.endswith(('.dll','.pyd'))},
          'notice_files':{'LICENSE.txt':sha(files['LICENSE.txt'])},'microsoft_runtime':{'source_available':False,'notice':'LICENSE.txt'},
          'source_notice_files':{'cpython-source/Python/LICENSE':sha(b'Original source terms')}}
    path=tmp_path/'lock.json';path.write_text(json.dumps(lock))
    return cache,path,lock,files


def test_reviewed_full_runtime_has_sources_and_original_microsoft_notice():
    lock=cpython.load_lock()
    assert len(lock['sources'])==33 and len(lock['native_files'])==45
    assert next(i for i in lock['artifacts'] if i['role']=='runtime')['sha256']=='ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0'
    assert lock['native_files']['vcruntime140.dll']['sources']==['microsoft-vc-runtime']
    assert lock['microsoft_runtime']['source_available'] is False
    assert lock['native_files']['DLLs/libtommath.dll']['sources']==['cpython','tcl']
    assert 'Lib/ctypes/macholib/README.ctypes' in lock['notice_files']
    assert any(n.endswith('/sqlite3.h') for n in lock['source_notice_files'])


def test_collection_source_gate_and_offline_installation(inputs,tmp_path):
    cache,path,lock,files=inputs;out=tmp_path/'materials'
    result=cpython.collect(out,lock_path=path,cache=cache)
    assert result['status']=='collected' and not result['native_execution_qualified']
    assert cpython.verify_materials(out,result,lock_path=path)==lock
    checked=cpython.verify_installation(lock,out/'python-3.14.7-amd64.zip',root=out/'runtime')
    assert checked['checked_files']==len(files) and not checked['native_execution_qualified']
    assert all((out/'runtime'/n).read_bytes()==data for n,data in files.items())


@pytest.mark.parametrize('name',['../escape','/absolute','a\\b','a:b','a/../b','NUL.txt','CON','a.','a ','a/COM1.log','a\x01b'])
def test_runtime_zip_rejects_windows_aliases_and_escape(tmp_path,name):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr(name,b'unsafe')
    with zipfile.ZipFile(path) as z,pytest.raises(ValueError):cpython.zip_entries(z)


@pytest.mark.parametrize('names',[['A.dll','a.dll'],['folder','folder/file'],['folder/file','folder'],['folder/','FOLDER/']])
def test_runtime_zip_rejects_case_and_directory_collisions(tmp_path,names):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        for n in names:z.writestr(n,b'x')
    with zipfile.ZipFile(path) as z,pytest.raises(ValueError):cpython.zip_entries(z)


def test_runtime_zip_rejects_symlink_and_expansion_bound(tmp_path,monkeypatch):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        m=zipfile.ZipInfo('link');m.create_system=3;m.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(m,b'elsewhere')
    with zipfile.ZipFile(path) as z,pytest.raises(ValueError,match='Linked'):cpython.zip_entries(z)
    with zipfile.ZipFile(path,'w') as z:z.writestr('ordinary',b'12345')
    monkeypatch.setattr(cpython,'MAX_EXPANDED',4)
    with zipfile.ZipFile(path) as z,pytest.raises(ValueError,match='expanded'):cpython.zip_entries(z)


@pytest.mark.parametrize('change',['source','notice','license','version','source_map','extra','symlink','linked_dir','removed_notice_with_manifest'])
def test_material_tampering_rejected(inputs,tmp_path,change):
    cache,path,lock,_=inputs;out=tmp_path/'materials';manifest=cpython.collect(out,lock_path=path,cache=cache)
    component=manifest['components'][0];folder=out/'windows-cpython'
    if change=='source':(folder/'sources/Python-3.14.7.tar.xz').write_bytes(b'changed')
    elif change=='notice':(folder/'notices/cpython-source/Python/LICENSE').write_bytes(b'changed')
    elif change=='license':(folder/'notices/runtime/LICENSE.txt').write_bytes(b'changed')
    elif change=='version':component['version']='0'
    elif change=='source_map':component['native_files']={}
    elif change=='extra':(folder/'extra').write_text('unexpected')
    elif change=='symlink':
        p=folder/'notices/runtime/LICENSE.txt';p.unlink();p.symlink_to(out/'runtime/LICENSE.txt')
    elif change=='linked_dir':(folder/'notices/extra').symlink_to(out/'runtime',target_is_directory=True)
    else:
        n='windows-cpython/notices/cpython-source/Python/LICENSE';(out/n).unlink();component['files'].pop(n)
    with pytest.raises((ValueError,FileNotFoundError)):cpython.verify_materials(out,manifest,lock_path=path)


@pytest.mark.parametrize('change',['stdlib','native','extra_native','linked_native'])
def test_installed_runtime_must_match_reviewed_bytes(inputs,tmp_path,change):
    cache,path,lock,_=inputs;out=tmp_path/'materials';cpython.collect(out,lock_path=path,cache=cache);root=out/'runtime'
    if change=='stdlib':(root/'Lib/pathlib.py').write_text('changed')
    elif change=='native':(root/'python314.dll').write_bytes(b'changed')
    elif change=='extra_native':(root/'other.dll').write_bytes(pe_bytes())
    else:
        p=root/'python314.dll';p.unlink();p.symlink_to(root/'DLLs/_ctypes.pyd')
    with pytest.raises(ValueError):cpython.verify_installation(lock,out/'python-3.14.7-amd64.zip',root=root)


def test_release_manifest_must_bind_runtime_hash(inputs,tmp_path):
    cache,_,lock,_=inputs
    path=cache/'windows-3.14.7.json';data=json.loads(path.read_text());data['versions'][0]['hash']['sha256']='0'*64;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='bound'):cpython.validate_release(cache,lock)


def test_archive_change_rejected_before_extraction(inputs,tmp_path):
    cache,_,lock,_=inputs;archive=cache/'python-3.14.7-amd64.zip';archive.write_bytes(b'changed')
    with pytest.raises(ValueError,match='reviewed archive'):cpython.inspect_runtime(archive,lock,tmp_path/'runtime')
    assert not (tmp_path/'runtime').exists()


def test_native_preflight_rejects_cross_host(inputs,monkeypatch):
    cache,_,lock,_=inputs;monkeypatch.setattr(cpython.platform,'system',lambda:'Darwin')
    with pytest.raises(ValueError,match='native Windows'):cpython.verify_installation(lock,cache/'python-3.14.7-amd64.zip')


def test_frozen_cpython_hash_gate_keeps_qemu_scope_separate(inputs,tmp_path):
    _,_,lock,files=inputs;bundle=tmp_path/'bundle';internal=bundle/'_internal';internal.mkdir(parents=True)
    (internal/'python314.dll').write_bytes(files['python314.dll'])
    (internal/'runtime').mkdir();(internal/'runtime/python314.dll').write_bytes(b'not a Python process input')
    assert list(cpython.record_bundle(bundle,lock))==['_internal/python314.dll']
    (internal/'python314.dll').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Frozen CPython'):cpython.record_bundle(bundle,lock)

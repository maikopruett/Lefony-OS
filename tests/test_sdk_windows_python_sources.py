# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-host wheel/source collection and native packaging preflight boundaries."""
import base64
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import windows_python_sources as windows


def checksum(data):return hashlib.sha256(data).hexdigest()


def make_wheel(path, *, extra=None, broken_record=False, duplicate=False):
    metadata=b'Metadata-Version: 2.3\nName: fixture-pkg\nVersion: 1.0\nRequires-Python: >=3.13\n'
    files={'fixture_pkg/__init__.py':b'# public fixture\n',
           'fixture_pkg/native.pyd':b'fixture binary bytes',
           'fixture_pkg-1.0.dist-info/METADATA':metadata,
           'fixture_pkg-1.0.dist-info/licenses/LICENSE':b'Fixture public license\n'}
    files.update(extra or {})
    record='fixture_pkg-1.0.dist-info/RECORD'
    stream=io.StringIO();writer=csv.writer(stream,lineterminator='\n')
    for name,data in files.items():
        value='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256=changed' if broken_record else value,len(data)))
    writer.writerow((record,'',''));files[record]=stream.getvalue().encode()
    with zipfile.ZipFile(path,'w') as archive:
        for name,data in files.items():archive.writestr(name,data)
        if duplicate:archive.writestr('Fixture_pkg/NATIVE.pyd',b'case collision')
    item={'name':'fixture-pkg','version':'1.0','requires_dist':[],
          'metadata_file':'fixture_pkg-1.0.dist-info/METADATA','metadata_sha256':checksum(metadata),
          'wheel':{'file':path.name,'sha256':windows.digest(path),'bytes':path.stat().st_size,'url':'https://example.test/'+path.name},
          'native_files':{'fixture_pkg/native.pyd':checksum(files['fixture_pkg/native.pyd'])},
          'native_sources':{'fixture_pkg/native.pyd':['fixture-pkg-sdist']},
          'notice_files':{'fixture_pkg-1.0.dist-info/licenses/LICENSE':checksum(files['fixture_pkg-1.0.dist-info/licenses/LICENSE'])},
          'metadata_files':{n:checksum(b) for n,b in files.items() if '.dist-info/' in n}}
    return item, files


@pytest.fixture
def inputs(tmp_path):
    cache=tmp_path/'cache';cache.mkdir()
    wheel=cache/'fixture_pkg-1.0-py3-none-any.whl';item,files=make_wheel(wheel)
    sdist=cache/'fixture_pkg-1.0.tar.gz'
    with tarfile.open(sdist,'w:gz') as t:
        data=b'Fixture license';info=tarfile.TarInfo('fixture_pkg-1.0/LICENSE');info.size=len(data);t.addfile(info,io.BytesIO(data))
    item['sdist']={'file':sdist.name,'sha256':windows.digest(sdist),'bytes':sdist.stat().st_size,'url':'https://example.test/'+sdist.name}
    actual=windows.load_lock()
    lock={'schema':1,'platform':'windows-AMD64','environment':actual['environment'],
          'python_full_version':'3.14.7','scope':'test fixture','requested':['fixture-pkg==1.0'],
          'sources':[],'distributions':[item]}
    path=tmp_path/'lock.json';path.write_text(json.dumps(lock))
    return path,cache,lock,files


def test_public_lock_exact_windows_dependency_set_and_sdk_pins():
    lock=windows.load_lock()
    assert len(lock['distributions'])==14 and len(lock['sources'])==17
    names={d['name'] for d in lock['distributions']}
    assert 'pywin32-ctypes' in names
    assert not names & {'secretstorage','jeepney','cryptography','cffi','macholib'}
    requested=[x for x in (ROOT/'sdk/requirements-desktop.txt').read_text().splitlines() if x and not x.startswith('#')]
    assert {str(windows.Requirement(x)).lower() for x in requested}=={x.lower() for x in lock['requested']}
    pins=(ROOT/'scripts/sdk-windows/requirements-python-x86_64.txt').read_text()
    for d in lock['distributions']:
        assert d['name']+'=='+d['version']+' --hash=sha256:'+d['wheel']['sha256'] in pins


def test_target_markers_do_not_resolve_host_dependencies(inputs):
    _,_,lock,_=inputs
    lock['distributions'][0]['requires_dist']=['windows-only; sys_platform == "win32"','linux-only; sys_platform == "linux"']
    lock['distributions'].append({'name':'windows-only','version':'1','requires_dist':[]})
    windows.dependency_closure(lock)
    lock['distributions'].pop()
    with pytest.raises(ValueError,match='Unmapped'):windows.dependency_closure(lock)


@pytest.mark.parametrize('change', ['environment','duplicate','unrelated','version','extra','url'])
def test_dependency_identity_rejections(inputs, change):
    _,_,lock,_=inputs
    if change=='environment':lock['environment']['sys_platform']='darwin'
    elif change=='duplicate':lock['distributions']*=2
    elif change=='unrelated':lock['distributions'].append({'name':'unused','version':'1','requires_dist':[]})
    elif change=='version':lock['requested']=['fixture-pkg>=2']
    elif change=='extra':lock['requested']=['fixture-pkg[unknown]']
    else:lock['requested']=['fixture-pkg @ https://example.test/source']
    with pytest.raises(ValueError):windows.dependency_closure(lock)


@pytest.mark.parametrize('change', ['tamper','record','case','traversal','native','metadata','abi'])
def test_wheel_rejections(tmp_path, change):
    path=tmp_path/'fixture_pkg-1.0-py3-none-any.whl'
    item,_=make_wheel(path,broken_record=change=='record',duplicate=change=='case',
                      extra={'../outside':b'no'} if change=='traversal' else None)
    if change=='tamper':path.write_bytes(path.read_bytes()+b'changed')
    elif change=='native':item['native_files']={}
    elif change=='metadata':item['metadata_sha256']='0'*64
    elif change=='abi':item['wheel']['file']='fixture_pkg-1.0-cp314-cp314-manylinux_2_28_x86_64.whl'
    with pytest.raises(ValueError):windows.inspect_wheel(path,item)


def test_offline_collection_verifies_installed_bytes_and_preserves_inputs(inputs,tmp_path,monkeypatch):
    path,cache,lock,files=inputs
    before={p.name:windows.digest(p) for p in cache.iterdir()}
    monkeypatch.setattr(windows,'urlopen',lambda *a,**k:pytest.fail('Offline cache should not download'))
    output=tmp_path/'collected';manifest=windows.collect(output,lock_path=path,cache=cache)
    assert manifest['status']=='collected' and not manifest['complete_desktop_sources']
    assert windows.load_lock(output/'windows_python_sources.json')==lock
    assert windows.verify_materials(output,manifest,lock_path=path)==lock
    installed=tmp_path/'installed';installed.mkdir()
    for name,data in files.items():
        target=installed/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (installed/'fixture_pkg-1.0.dist-info/RECORD').write_text('pip may rewrite RECORD\n')
    result=windows.verify_installation(lock,output,root=installed)
    assert not result['native_execution_qualified']
    (installed/'fixture_pkg/__init__.py').write_text('# modified\n')
    with pytest.raises(ValueError,match='Installed Windows Python input changed'):
        windows.verify_installation(lock,output,root=installed)
    assert before=={p.name:windows.digest(p) for p in cache.iterdir()}


@pytest.mark.parametrize('change',['source','notice','metadata','extra','symlink','linked_directory','manifest','native_map'])
def test_material_rejections(inputs,tmp_path,change):
    path,cache,lock,_=inputs;output=tmp_path/'collected'
    manifest=windows.collect(output,lock_path=path,cache=cache)
    folder=output/'fixture-pkg'
    if change=='source':(folder/lock['distributions'][0]['sdist']['file']).write_bytes(b'changed')
    elif change=='notice':next((folder/'notices/wheel').rglob('LICENSE')).write_bytes(b'changed')
    elif change=='metadata':next((folder/'wheel-metadata').rglob('METADATA')).write_bytes(b'changed')
    elif change=='extra':(folder/'extra.pyd').write_bytes(b'changed')
    elif change=='symlink':
        original=next((folder/'notices/wheel').rglob('LICENSE'));outside=tmp_path/'outside';shutil.copyfile(original,outside)
        original.unlink();original.symlink_to(outside)
    elif change=='linked_directory':
        outside=tmp_path/'external';outside.mkdir();(outside/'private').write_bytes(b'not source material')
        (folder/'notices/extra').symlink_to(outside,target_is_directory=True)
    elif change=='manifest':manifest['components'][0]['version']='2'
    else:manifest['components'][0]['native_sources']={}
    with pytest.raises(ValueError):windows.verify_materials(output,manifest,lock_path=path)


def test_cache_hash_and_copy_race_rejections(inputs,tmp_path,monkeypatch):
    _,cache,lock,_=inputs;item=lock['distributions'][0]['wheel'];original=cache/item['file']
    copyfile=shutil.copyfile
    def changed(source,target):copyfile(source,target);target.write_bytes(b'copy race')
    with monkeypatch.context() as patch:
        patch.setattr(windows.shutil,'copyfile',changed)
        with pytest.raises(ValueError,match='checksum differs'):windows.copy_archive(item,tmp_path/'race',cache)
    original.write_bytes(b'changed cache')
    with pytest.raises(ValueError,match='Changed cached'):windows.copy_archive(item,tmp_path/'bad',cache)


def test_notice_traversal_is_rejected_without_extracting(tmp_path):
    archive=tmp_path/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        item=tarfile.TarInfo('../LICENSE');item.size=4;t.addfile(item,io.BytesIO(b'evil'))
    with pytest.raises(ValueError,match='Unsafe'):windows.source_notices(archive,tmp_path/'notices')
    assert not (tmp_path/'LICENSE').exists()

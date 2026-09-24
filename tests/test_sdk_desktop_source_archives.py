# SPDX-License-Identifier: GPL-3.0-or-later
"""Corresponding-source bundles must contain each explicitly pinned input."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import package_native_desktop_sources as sources


@pytest.fixture
def inputs(tmp_path):
    materials = tmp_path / 'materials'
    materials.mkdir()
    (materials / 'manifest.json').write_text(json.dumps({'schema': 1, 'components': []}))
    manifest = {'schema': 1, 'firmware_sha256': 'a' * 64,
                'qemu_input_sha256': 'b' * 64, 'archives': {}}
    for name in ('lefony', 'qemu-prime', 'prepared-firmware'):
        path = tmp_path / (name + '.tar.gz')
        with tarfile.open(path, 'w:gz') as archive:
            data = (name + ' source').encode()
            info = tarfile.TarInfo(name + '/main.c')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        manifest['archives'][name] = {'file': path.name, 'sha256': sources.digest(path)}
    path = tmp_path / 'project-sources.json'
    path.write_text(json.dumps(manifest))
    return materials, path, manifest, tmp_path / 'distribution'


def test_archives_retain_exact_inputs_and_binary_identities(inputs):
    materials, path, expected, output = inputs
    sources.package(materials, output, ('lefony-qemu',), project_sources=path)
    with tarfile.open(output / 'lefony-sdk-source-lefony-qemu.tar.gz') as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        assert manifest['firmware_sha256'] == expected['firmware_sha256']
        assert manifest['qemu_input_sha256'] == expected['qemu_input_sha256']
        assert len(archive.getmembers()) == 4
        for name, entry in manifest['archives'].items():
            data = archive.extractfile(entry['file']).read()
            assert hashlib.sha256(data).hexdigest() == expected['archives'][name]['sha256']
            with tarfile.open(fileobj=io.BytesIO(data)) as source:
                assert source.extractfile(name + '/main.c').read() == (name + ' source').encode()
    record = json.loads((output / 'sources.json').read_text())[0]
    assert record['sha256'] == sources.digest(output / record['filename'])


@pytest.mark.parametrize('change', ['missing-manifest', 'missing-firmware', 'changed',
                                  'not-tar', 'escape', 'symlink', 'identity'])
def test_incomplete_or_changed_project_sources_cannot_produce_archive(inputs, change):
    materials, path, manifest, output = inputs
    if change == 'missing-manifest':
        path = None
    elif change == 'missing-firmware':
        del manifest['archives']['prepared-firmware']
    elif change in ('changed', 'not-tar'):
        archive = path.parent / manifest['archives']['lefony']['file']
        archive.write_bytes(b'not source')
        if change == 'not-tar':
            manifest['archives']['lefony']['sha256'] = sources.digest(archive)
    elif change == 'escape':
        manifest['archives']['lefony']['file'] = '../lefony.tar.gz'
    elif change == 'symlink':
        archive = path.parent / manifest['archives']['lefony']['file']
        archive.rename(archive.with_suffix('.retained'))
        archive.symlink_to(archive.with_suffix('.retained').name)
    elif change == 'identity':
        del manifest['firmware_sha256']
    if path:
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        sources.package(materials, output, ('lefony-qemu',), project_sources=path)
    assert not output.exists()


def test_missing_dependency_directory_is_not_silently_omitted(inputs):
    materials, _, _, output = inputs
    (materials / 'manifest.json').write_text(json.dumps({'components': [
        {'component': 'dependency', 'inputs': []}]}))
    with pytest.raises(ValueError, match='Missing source material'):
        sources.package(materials, output, ('runtime',))
    assert not (output / 'sources.json').exists()


@pytest.mark.parametrize('platform', ['linux-x86_64', 'darwin-arm64'])
@pytest.mark.parametrize('change', [None, 'source', 'notice', 'notice-link'])
def test_original_newlib_catalogs_remain_packageable_and_checked(inputs, monkeypatch, platform, change):
    """Unix collectors use inputs/notices, not the Windows bundle schema."""
    import linux_wheel_native_sources
    import pillow_native_sources
    materials, _, _, output = inputs
    checked = []
    validator = linux_wheel_native_sources if platform == 'linux-x86_64' else pillow_native_sources
    monkeypatch.setattr(validator, 'verify_materials', lambda *args: checked.append(args))
    folder = materials / 'arm-none-eabi-newlib'
    (folder / 'notices').mkdir(parents=True)
    original = {'source.tar.gz': b'original source', 'candidate.json': b'original candidate',
                'notices/COPYING.NEWLIB': b'original license'}
    for name, data in original.items():
        (folder / name).write_bytes(data)
    component = {'component': folder.name, 'version': '1', 'inputs': [
        {'file': folder.name+'/'+name, 'sha256': hashlib.sha256(data).hexdigest()}
        for name, data in original.items() if not name.startswith('notices/')],
        'installed_notices': [{'file': folder.name+'/notices/COPYING.NEWLIB',
                              'sha256': hashlib.sha256(original['notices/COPYING.NEWLIB']).hexdigest()}]}
    manifest = {'schema': 1, 'platform': platform, 'components': [component]}
    (materials / 'manifest.json').write_text(json.dumps(manifest))
    if change:
        target = folder / ('source.tar.gz' if change == 'source' else 'notices/COPYING.NEWLIB')
        if change == 'notice-link':
            target.unlink()
            target.symlink_to(folder / 'candidate.json')
        else:
            target.write_bytes(b'changed')
        with pytest.raises(ValueError, match='Source material changed'):
            sources.package(materials, output, ('toolchain',))
        assert not output.exists()
    else:
        sources.package(materials, output, ('toolchain',))
        with tarfile.open(output / 'lefony-sdk-source-toolchain.tar.gz') as archive:
            assert json.load(archive.extractfile('manifest.json'))['components'] == [component]
            for name, data in original.items():
                assert archive.extractfile(folder.name+'/'+name).read() == data
    assert checked == [(materials, manifest)]


def test_windows_newlib_still_requires_bundle_correspondence(inputs, monkeypatch):
    import native_desktop_project
    import windows_python_sources
    import windows_cpython_sources
    materials, _, _, output = inputs
    manifest = {'platform': 'windows-AMD64', 'components': [
        {'component': 'arm-none-eabi-newlib', 'inputs': []}]}
    (materials / 'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(windows_python_sources, 'verify_materials', lambda *args: None)
    monkeypatch.setattr(windows_cpython_sources, 'verify_materials', lambda *args: None)
    def reject(*args):
        raise ValueError('Newlib sources differ from selected sysroot')
    monkeypatch.setattr(native_desktop_project, 'verify_newlib_materials', reject)
    with pytest.raises(ValueError, match='Newlib sources differ'):
        sources.package(materials, output, ('toolchain',))
    assert not output.exists()


@pytest.mark.parametrize('kind', ['project', 'dependency'])
def test_changed_source_after_preflight_cannot_be_archived(inputs, monkeypatch, kind):
    materials, project, _, output = inputs
    if kind=='project':
        changed=project.parent/'lefony.tar.gz';groups=('lefony-qemu',)
    else:
        changed=materials/'dependency/source.tar.gz';changed.parent.mkdir()
        changed.write_bytes(b'original source')
        (materials/'manifest.json').write_text(json.dumps({'components':[
            {'component':'dependency','inputs':[{'file':'dependency/source.tar.gz',
             'sha256':sources.digest(changed)}]}]}))
        groups=('runtime',)
    original=sources.add
    def racing_add(archive,path,name,*args,**kwargs):
        if path==changed:path.write_bytes(b'changed after preflight')
        return original(archive,path,name,*args,**kwargs)
    monkeypatch.setattr(sources,'add',racing_add)
    with pytest.raises(ValueError,match='Source material changed while archiving'):
        sources.package(materials,output,groups,project_sources=project if kind=='project' else None)
    assert not (output/'sources.json').exists()
    assert not list(output.glob('lefony-sdk-source-*.tar.gz'))


@pytest.mark.parametrize('change',['modify','append','truncate'])
def test_archive_checks_bytes_consumed_during_copy(inputs, monkeypatch,change):
    materials, _, _, output=inputs
    source=materials/'dependency/source.tar.gz';source.parent.mkdir()
    # Exceed the file object's read-ahead buffer so the changed tail has not
    # already been copied into memory when the first tar block is consumed.
    source.write_bytes(b'A'*(2*1024*1024))
    (materials/'manifest.json').write_text(json.dumps({'components':[
        {'component':'dependency','inputs':[{'file':'dependency/source.tar.gz','sha256':sources.digest(source)}]}]}))
    original=sources.HashedReader.read;changed=False
    def racing_read(reader,size):
        nonlocal changed
        data=original(reader,size)
        if not changed:
            changed=True
            with source.open('r+b') as stream:
                if change=='modify':
                    stream.seek(2*1024*1024-65536);stream.write(b'B'*65536)
                elif change=='append':stream.seek(0,2);stream.write(b'extra source bytes')
                else:stream.truncate(1000)
        return data
    monkeypatch.setattr(sources.HashedReader,'read',racing_read)
    with pytest.raises((ValueError,OSError)):
        sources.package(materials,output,('runtime',))
    assert not list(output.iterdir())


@pytest.mark.parametrize('failure',['late-source','disk-full','cancel','catalog-write'])
def test_construction_failure_preserves_all_prior_groups_and_catalog(inputs,monkeypatch,failure):
    import errno
    materials,project,_,output=inputs
    groups=('toolchain','lefony-qemu')
    sources.package(materials,output,groups,project_sources=project)
    before={p.name:p.read_bytes() for p in output.iterdir()}
    if failure=='catalog-write':
        write=Path.write_text
        def fail_catalog(path,*args,**kwargs):
            if path.name=='sources.json':raise OSError(errno.ENOSPC,'injected catalog disk full')
            return write(path,*args,**kwargs)
        monkeypatch.setattr(Path,'write_text',fail_catalog)
        error=OSError
    else:
        add=sources.add
        def fail_after_first_archive(archive,path,name,*args,**kwargs):
            if name.startswith('lefony/'):
                if failure=='disk-full':raise OSError(errno.ENOSPC,'injected archive disk full')
                if failure=='cancel':raise KeyboardInterrupt('injected cancellation')
                raise ValueError('injected late source failure')
            return add(archive,path,name,*args,**kwargs)
        monkeypatch.setattr(sources,'add',fail_after_first_archive)
        error={'late-source':ValueError,'disk-full':OSError,'cancel':KeyboardInterrupt}[failure]
    with pytest.raises(error):sources.package(materials,output,groups,project_sources=project)
    assert {p.name:p.read_bytes() for p in output.iterdir()}==before


def test_successful_group_refresh_retains_other_archive_and_updates_catalog(inputs):
    materials,project,manifest,output=inputs
    sources.package(materials,output,('runtime','lefony-qemu'),project_sources=project)
    runtime=(output/'lefony-sdk-source-runtime.tar.gz').read_bytes()
    source=project.parent/'lefony.tar.gz'
    with tarfile.open(source,'w:gz') as archive:
        data=b'updated source';info=tarfile.TarInfo('lefony/new.c');info.size=len(data);archive.addfile(info,io.BytesIO(data))
    manifest['archives']['lefony']['sha256']=sources.digest(source);project.write_text(json.dumps(manifest))
    sources.package(materials,output,('lefony-qemu',),project_sources=project)
    assert (output/'lefony-sdk-source-runtime.tar.gz').read_bytes()==runtime
    catalog=json.loads((output/'sources.json').read_text())
    assert len(catalog)==2
    for item in catalog:assert sources.digest(output/item['filename'])==item['sha256']
    with tarfile.open(output/'lefony-sdk-source-lefony-qemu.tar.gz') as archive:
        stored=json.load(archive.extractfile('manifest.json'))
        assert stored['archives']['lefony']['sha256']==sources.digest(source)


def test_process_kill_during_construction_preserves_prior_distribution_and_allows_retry(inputs):
    import subprocess
    import time
    materials,project,_,output=inputs
    groups=('toolchain','lefony-qemu')
    sources.package(materials,output,groups,project_sources=project)
    before={p.name:p.read_bytes() for p in output.iterdir()}
    marker=project.parent/'copy-paused'
    code='''import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import package_native_desktop_sources as source
original=source.add
marker=Path(sys.argv[5])
def paused(*args,**kwargs):
 original(*args,**kwargs)
 if not marker.exists():
  marker.write_text('archive construction paused')
  time.sleep(30)
source.add=paused
source.package(Path(sys.argv[2]),Path(sys.argv[3]),('toolchain','lefony-qemu'),project_sources=Path(sys.argv[4]))
'''
    child=subprocess.Popen([sys.executable,'-I','-c',code,str(Path(sources.__file__).parent),
        str(materials),str(output),str(project),str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+10
        while not marker.exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert marker.exists(),child.communicate(timeout=1)
        child.kill();child.wait(timeout=5)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
    assert {name:(output/name).read_bytes() for name in before}==before
    abandoned=set(output.glob('.source-stage-*'));assert len(abandoned)==1
    sources.package(materials,output,groups,project_sources=project)
    for item in json.loads((output/'sources.json').read_text()):
        assert sources.digest(output/item['filename'])==item['sha256']
    assert set(output.glob('.source-stage-*'))==abandoned

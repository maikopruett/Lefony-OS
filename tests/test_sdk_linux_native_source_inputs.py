# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject binaries whose bytes or source provider differ from a Linux inventory."""
import copy
from pathlib import Path
import struct
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import native_desktop_linux_sources as sources


def elf(path, marker=b'', machine=62):
    path.parent.mkdir(parents=True,exist_ok=True)
    header=bytearray(64);header[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<HH',header,16,3,machine)
    path.write_bytes(header+marker)
    return path


@pytest.fixture
def candidate(tmp_path,monkeypatch):
    source=elf(tmp_path/'input/libtest.so',b'original')
    firmware=elf(tmp_path/'firmware.elf',b'ARM firmware',machine=40)
    bundle=tmp_path/'Moved SDK é'
    elf(bundle/'_internal/libtest.so',b'relocated output')
    output_firmware=bundle/'_internal/runtime/firmware.elf'
    output_firmware.parent.mkdir();output_firmware.write_bytes(firmware.read_bytes())
    elf(bundle/'lefony-sdk',b'archive')
    toc=tmp_path/'Analysis-00.toc'
    toc.write_text(repr(([('libtest.so',str(source),'BINARY'),
        ('runtime/firmware.elf',str(firmware),'BINARY')],)))
    manifest={'components':[
        {'component':'debian-libtest','version':'1.2-3','inputs':[{'file':'source.tar.gz'}]},
        {'component':'pyinstaller','version':'6.20.0','inputs':[{'file':'pyinstaller.tar.gz'}]},
        {'component':'lefony-public-source','version':'working-tree','inputs':[{'file':'source.tar.gz'}]}],
        'linux_native_inputs':{'libtest.so':{'source_sha256':sources.digest(source),
            'component':'debian-libtest','version':'1.2-3'}},
        'linux_non_host_inputs':{'runtime/firmware.elf':{'source_sha256':sources.digest(firmware),
            'component':'lefony-public-source','version':'working-tree'}},
        'linux_bootloader':{'component':'pyinstaller','version':'6.20.0','source_sha256':'a'*64}}
    monkeypatch.setattr(sources,'bootloader',lambda:('6.20.0','a'*64))
    return toc,bundle,manifest,source


def test_correspondence_binds_hashes_and_classifies_arm_firmware(candidate):
    toc,bundle,manifest,source=candidate
    result=sources.record_bundle(toc,bundle,manifest)
    assert list(result['files'])==['libtest.so']
    record=result['files']['libtest.so']
    assert record['input_sha256']==sources.digest(source)
    assert record['bundled_sha256']==sources.digest(bundle/'_internal/libtest.so')
    assert record['input_sha256']!=record['bundled_sha256']
    assert record['component']=='debian-libtest' and result['source_rebuild_qualified'] is False
    assert result['launcher_sha256']==sources.digest(bundle/'lefony-sdk')
    assert list(result['non_host_files'])==['runtime/firmware.elf']


def test_changed_native_binary_fails_even_with_valid_component(candidate):
    toc,bundle,manifest,source=candidate
    source.write_bytes(source.read_bytes()+b'changed library')
    with pytest.raises(ValueError,match='differs from its source inventory'):
        sources.record_bundle(toc,bundle,manifest)


@pytest.mark.parametrize('change',['extra','missing'])
def test_inventory_must_cover_exact_native_target_set(candidate,change):
    toc,bundle,manifest,source=candidate
    if change=='extra':
        toc.write_text(repr([('libtest.so',str(source),'BINARY'),('unreviewed.so',str(source),'BINARY')]))
    else:
        manifest['linux_native_inputs']['absent.so']=copy.deepcopy(manifest['linux_native_inputs']['libtest.so'])
    with pytest.raises(ValueError,match='differs from the freeze targets'):
        sources.record_bundle(toc,bundle,manifest)


@pytest.mark.parametrize('change',['missing','version','empty','duplicate'])
def test_source_provider_is_required_at_exact_version(candidate,change):
    toc,bundle,manifest,_=candidate
    if change=='missing':manifest['components'].pop(0)
    elif change=='version':manifest['components'][0]['version']='1.2-4'
    elif change=='empty':manifest['components'][0]['inputs']=[]
    else:manifest['components'].append(copy.deepcopy(manifest['components'][0]))
    with pytest.raises(ValueError,match='source provider|Duplicate source component'):
        sources.record_bundle(toc,bundle,manifest)


def test_changed_bootloader_cannot_reuse_source_correspondence(candidate,monkeypatch):
    toc,bundle,manifest,_=candidate
    monkeypatch.setattr(sources,'bootloader',lambda:('6.20.0','b'*64))
    with pytest.raises(ValueError,match='bootloader differs'):
        sources.record_bundle(toc,bundle,manifest)


def test_no_inventory_is_not_an_implicit_source_pass(candidate):
    toc,bundle,manifest,_=candidate
    del manifest['linux_native_inputs']
    with pytest.raises(ValueError,match='complete native source inventory'):
        sources.record_bundle(toc,bundle,manifest)


def test_target_library_bytes_cannot_change_behind_unchanged_compiler(candidate,tmp_path):
    toc,bundle,manifest,_=candidate
    archive=tmp_path/'libgcc.a';archive.write_bytes(b'!<arch>\noriginal ARM archive')
    import ast
    entries=ast.literal_eval(toc.read_text())[0]
    entries.append(('toolchain/libgcc.a',str(archive),'BINARY'));toc.write_text(repr(entries))
    target=bundle/'_internal/toolchain/libgcc.a';target.parent.mkdir();target.write_bytes(archive.read_bytes())
    manifest['linux_non_host_inputs']['toolchain/libgcc.a']={
        'source_sha256':sources.digest(archive),'component':'debian-libtest','version':'1.2-3'}
    assert 'toolchain/libgcc.a' in sources.record_bundle(toc,bundle,manifest)['non_host_files']
    archive.write_bytes(b'!<arch>\nunreviewed ARM archive')
    with pytest.raises(ValueError,match='target-library/firmware input differs'):
        sources.record_bundle(toc,bundle,manifest)


def test_target_library_inventory_is_mandatory(candidate):
    toc,bundle,manifest,_=candidate
    del manifest['linux_non_host_inputs']
    with pytest.raises(ValueError,match='target-library/firmware inventory differs'):
        sources.record_bundle(toc,bundle,manifest)


def test_analysis_rejects_conflicting_bytes_at_one_target(candidate,tmp_path):
    toc,_,_,source=candidate
    other=elf(tmp_path/'different.so',b'different')
    toc.write_text(repr([('libtest.so',str(source),'BINARY'),('libtest.so',str(other),'BINARY')]))
    with pytest.raises(ValueError,match='Conflicting Linux freeze input'):
        sources.native_inputs(toc)


def test_analysis_and_output_paths_stay_inside_bundle(candidate,tmp_path):
    toc,bundle,manifest,source=candidate
    target=bundle/'_internal/libtest.so';target.unlink();target.symlink_to(source)
    with pytest.raises(ValueError,match='escapes its root'):
        sources.record_bundle(toc,bundle,manifest)
    toc.write_text(repr([('../libtest.so',str(source),'BINARY')]))
    with pytest.raises(ValueError,match='Invalid wheel source path'):
        sources.native_inputs(toc)

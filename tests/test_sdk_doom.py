# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned Doom preparation, complete source exchange and offline kit inputs."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from cli import package
from source import collect,extract

@pytest.fixture
def upstream():
    path=ROOT/'build/sdk-1.0-upstream/doomgeneric'
    if not path.exists():pytest.skip('requires the pinned Doom checkout; run scripts/fetch_sdk_doom.py')
    return path

def test_doom_sources_roundtrip_and_build(tmp_path,upstream):
    if not (ROOT/'build/sdk-newlib/candidate.json').exists():pytest.skip('requires the pinned newlib sysroot')
    prepare=runpy.run_path(str(ROOT/'scripts/prepare_sdk_doom.py'))['prepare']
    first,second=tmp_path/'Original',tmp_path/'Repeated'
    prepare(first,upstream);prepare(second,upstream)
    def files(p):return {str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}
    assert files(first)==files(second)
    app=package(first);image=(first/'build/app.elf').read_bytes()
    restored=tmp_path/'Restored C tree é';extract(collect(first,2),restored)
    rebuilt=package(restored)
    assert rebuilt.read_bytes()==app.read_bytes() and (restored/'build/app.elf').read_bytes()==image

def test_changed_upstream_is_rejected_before_creating_project(tmp_path,upstream):
    changed=tmp_path/'changed';shutil.copytree(upstream,changed,ignore=shutil.ignore_patterns('.git'))
    source=changed/'doomgeneric/g_game.c';source.write_bytes(source.read_bytes()+b'\n/* unexpected input */\n')
    prepare=runpy.run_path(str(ROOT/'scripts/prepare_sdk_doom.py'))['prepare']
    destination=tmp_path/'untouched'
    with pytest.raises(ValueError,match='Pinned source differs'):prepare(destination,changed)
    assert not destination.exists()

def test_source_kit_can_prepare_complete_doom_project(tmp_path,upstream):
    if not (ROOT/'build/sdk-newlib/candidate.json').exists():pytest.skip('requires the pinned newlib sysroot for the portable build')
    pack=runpy.run_path(str(ROOT/'scripts/package_native_sdk.py'))['package']
    archive=tmp_path/'sdk.tar.gz';pack(archive,newlib=ROOT/'build/sdk-newlib')
    with tarfile.open(archive) as bundle:bundle.extractall(tmp_path,filter='data')
    kit=tmp_path/'lefony-native-sdk'
    prepare=runpy.run_path(str(kit/'scripts/prepare_sdk_doom.py'))['prepare']
    destination=tmp_path/'External Doom';config=prepare(destination,upstream)
    assert all((destination/p).is_file() for p in config['sources'])
    assert (destination/'src/output.c').read_bytes()==(ROOT/'sdk/ports/doom/output.c').read_bytes()
    assert (destination/'src/output.h').read_bytes()==(ROOT/'sdk/ports/doom/output.h').read_bytes()
    environment={k:v for k,v in os.environ.items() if k!='LEFONY_SDK_NEWLIB'}
    subprocess.run([sys.executable,str(kit/'sdk/tools/cli.py'),'--project',str(destination),'package'],
                   env=environment,check=True,timeout=120,capture_output=True,text=True)
    built=json.loads((destination/'build/build.json').read_text())
    assert any(str(kit/'sdk/runtime/newlib') in value for value in built['link'])
    metadata=json.loads((destination/'app.json').read_text())
    portable=(destination/'build'/f"{metadata['id']}-{metadata['version']}.lfapp").read_bytes()
    assert package(destination).read_bytes()==portable

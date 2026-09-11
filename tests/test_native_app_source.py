# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
from source import collect, decode, encode, extract
from lfapp import PackageError

SOURCE = {'format':'lefony-source-0','manifest':{'abi':0,'id':'hello','name':'Hello','version':'0.1.0','license':'CC-BY-NC-SA-4.0'},'files':{'src/main.cpp':'// Hello\n'}}

def test_source_roundtrip_is_canonical_and_source_only(tmp_path):
    data=encode(SOURCE)
    target=tmp_path/'app'
    assert extract(data,target)==SOURCE
    assert collect(target)==data
    (target/'build').mkdir()
    (target/'build/key.pem').write_text('not source')
    (target/'AGENTS.md').write_text('local instructions')
    assert collect(target)==data
    assert decode(data)==SOURCE

@pytest.mark.parametrize('name',['../evil.cpp','src/../../evil.cpp','/src/evil.cpp','src/hook.py','src/Makefile','src/name..cpp','src\\evil.cpp'])
def test_bad_paths_and_non_native_files_rejected(name):
    with pytest.raises(PackageError): encode({**SOURCE,'files':{name:'x'}})

def test_source_bounds_and_symlinks(tmp_path):
    for files in ({'src/main.cpp':'x'*65537},{'src/main.cpp':'x\0y'},{}, {'src/a.h':'header only'}):
        with pytest.raises(PackageError): encode({**SOURCE,'files':files})
    target=tmp_path/'app'; extract(encode(SOURCE),target)
    (target/'src/link.h').symlink_to(target/'app.json')
    with pytest.raises(PackageError): collect(target)


def test_sandbox_rejects_mutable_image_before_launch():
    spec=importlib.util.spec_from_file_location('publisher_worker',ROOT/'sdk/publisher/worker.py')
    worker=importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
    with pytest.raises(ValueError,match='immutable'): worker.sandbox('builder:latest',b'{}')

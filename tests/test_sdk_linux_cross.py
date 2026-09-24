# SPDX-License-Identifier: GPL-3.0-or-later
"""Do not ship build-host tools as the x86-64 compiler or confuse ARM objects."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    spec = importlib.util.spec_from_file_location('linux_cross', ROOT / 'scripts/build_sdk_linux_cross.py')
    cross = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cross)
finally:
    sys.path.pop(0)


def elf(machine, elf_class=2, endian=1):
    header = bytearray(64)
    header[:6] = b'\x7fELF' + bytes((elf_class, endian))
    header[18:20] = machine.to_bytes(2, 'little')
    return header


@pytest.mark.parametrize('content', [elf(183), elf(40, 1), elf(62, 1), elf(62, endian=2),
                                     elf(62)[:19], b'#!/bin/sh\nexit 0\n'])
def test_incompatible_host_executable_is_rejected(tmp_path, content):
    path = tmp_path / 'compiler'; path.write_bytes(content)
    with pytest.raises(ValueError, match='expected little-endian ELF64 machine 62'):
        cross.require_elf(path, 62, 64)


def test_build_host_and_target_architectures_are_distinct(tmp_path):
    path = tmp_path / 'tool'
    for machine, bits in ((183, 64), (62, 64), (40, 32)):
        path.write_bytes(elf(machine, 2 if bits == 64 else 1))
        cross.require_elf(path, machine, bits)
        with pytest.raises(ValueError):
            cross.require_elf(path, 183 if machine != 183 else 62, 64)


def test_wrong_architecture_build_tool_is_not_executed(tmp_path):
    path = tmp_path / 'gcc'; path.write_bytes(elf(62)); path.chmod(0o700)
    with pytest.raises(ValueError, match='machine 183'):
        cross.executable('gcc', {'PATH': str(tmp_path)})


def test_windows_dependency_selection_binds_all_libraries(tmp_path):
    files={}
    for name in ('gmp','mpfr','mpc','isl','z','zstd'):
        path=tmp_path/'install/lib'/('lib'+name+'.a');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(name.encode());files[path.relative_to(tmp_path/'install').as_posix()]=cross.digest(path)
    candidate=tmp_path/'candidate.json'
    record={'status':'passed','platform':'Windows','architecture':'AMD64','files':files}
    candidate.write_text(json.dumps(record));checksum=cross.digest(candidate)
    assert cross.verify_windows_dependencies(tmp_path,checksum)==record
    with pytest.raises(ValueError,match='selected hash'):
        cross.verify_windows_dependencies(tmp_path,'0'*64)
    (tmp_path/'install/lib/libzstd.a').write_bytes(b'changed')
    with pytest.raises(ValueError,match='input changed'):
        cross.verify_windows_dependencies(tmp_path,checksum)


@pytest.mark.parametrize('changes',[{'status':'failed'},{'platform':'Linux'},{'architecture':'ARM64'},{}])
def test_windows_dependency_gate_rejects_incomplete_or_other_host_inputs(tmp_path,changes):
    candidate=tmp_path/'candidate.json'
    candidate.write_text(json.dumps({'status':'passed','platform':'Windows','architecture':'AMD64','files':{},**changes}))
    with pytest.raises(ValueError):cross.verify_windows_dependencies(tmp_path,cross.digest(candidate))

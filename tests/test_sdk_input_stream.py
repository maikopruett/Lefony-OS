# SPDX-License-Identifier: GPL-3.0-or-later
"""Public input negotiation, host queue semantics and stable physical key IDs."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdk/tools'))
import lfapp


def test_input_stream_state_order_overflow_focus_and_debounce(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++')
    assert compiler,'Host C++ compiler required'
    binary=tmp_path/'input-stream'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-sanitize-recover=all',
                    '-I',str(ROOT/'sdk/include'),'-I',str(ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'),
                    str(ROOT/'tests/native/app_input_stream.cpp'),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([binary],check=True,timeout=30)


def test_c_physical_key_ids_match_authoritative_contract():
    header=(ROOT/'sdk/include/lefony/input_stream.h').read_text()
    actual={name.lower():int(position) for name,position in re.findall(r'LEFONY_PHYSICAL_(\w+)=(\d+)',header)}
    expected={name:row*8+col for name,(row,col) in json.loads((ROOT/'sdk/contracts/keys.json').read_text()).items()}
    assert actual==expected


def test_input_stream_manifest_rejects_old_api_and_missing_feature():
    metadata={'abi':1,'id':'input-stream','name':'Input Stream','version':'0.1.0',
              'license':'CC-BY-NC-SA-4.0','schema':1,'minimum_api':4,
              'required_capabilities':32,'optional_capabilities':0,'data_schema':1}
    assert lfapp.compatible(metadata)
    for api,features in [(3,63),(4,31)]:
        with pytest.raises(lfapp.PackageError):lfapp.compatible(metadata,api=api,features=features)

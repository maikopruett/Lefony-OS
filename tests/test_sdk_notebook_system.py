# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name,language',[('sdk_number_format','c'),('sdk_notebook_model','cpp')])
def test_notebook_formatting_migration_and_input_models(tmp_path,name,language):
    compiler=shutil.which('clang' if language=='c' else 'clang++') or shutil.which('cc' if language=='c' else 'c++')
    if not compiler:pytest.skip('C/C++ compiler required')
    binary=tmp_path/name
    subprocess.run([compiler,'-std=c11' if language=='c' else '-std=c++17','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),
        '-I',str(ROOT/'sdk/examples/notebook/src'),str(ROOT/f'tests/native/{name}.{language}'),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([str(binary)],check=True,timeout=30)

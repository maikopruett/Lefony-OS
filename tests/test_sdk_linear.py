# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_bounded_linear_algebra_under_sanitizers(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    source = tmp_path / 'linear.cpp'
    source.write_text('#include "sdk_linear_cases.h"\nint main() { return LinearTests::test()?0:1; }\n')
    executable = tmp_path / 'linear'
    subprocess.run([compiler, '-std=c++17', '-O1', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'tests/native'),
                    str(source), '-o', str(executable)], check=True, timeout=60)
    subprocess.run([str(executable)], check=True, timeout=30)

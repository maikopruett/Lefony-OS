# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise progress and modal lifetime independently of device hardware."""
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

def test_install_progress_and_automatic_dismissal(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('Host C++ compiler unavailable')
    binary = tmp_path / 'install-progress'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I',
                    str(ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'),
                    str(ROOT / 'tests/native/app_install_progress.cpp'), '-o', str(binary)],
                   check=True, timeout=60)
    subprocess.run([str(binary)], check=True, timeout=30)

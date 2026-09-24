# SPDX-License-Identifier: GPL-3.0-or-later
"""Launcher ordering preserves identity across catalog changes and restarts."""
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]

def test_home_order_identity_and_record_validation(tmp_path):
    compiler=shutil.which('c++')
    if not compiler:pytest.skip('Host C++ compiler unavailable')
    binary=tmp_path/'home-order'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I',str(ROOT/'ports/lefony-prime-g2/apps/native_apps'),
                    str(ROOT/'tests/native/home_order.cpp'),'-o',str(binary)],check=True,timeout=60)
    subprocess.run([str(binary)],check=True,timeout=30)

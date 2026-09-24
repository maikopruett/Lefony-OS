# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
from test_app_files import ROOT, compile_fixture


def test_verified_snapshot_cache_and_fast_completion(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT / 'tests/native/app_read_cache.cpp',
                             extra_sources=('app_file_session.cpp',))
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr

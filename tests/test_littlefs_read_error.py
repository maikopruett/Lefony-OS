# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual NAND-sized littlefs caching under persistent backend read errors."""
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_failed_reads_do_not_become_cache_hits(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT/'tests/native/littlefs_read_error.cpp')
    result = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['retry_cases'] == 8 and report['status'] == 'passed'

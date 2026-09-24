# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from test_app_files import compile_fixture, ROOT

def test_metadata_cache_reduces_reads_without_migrating_existing_media(tmp_path):
    binary=compile_fixture(tmp_path,source=ROOT/'tests/native/app_storage_cache.cpp')
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout)
    assert report['new_page_reads']*2<report['old_page_reads']

# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from test_app_files import ROOT,compile_fixture


def test_stream_commit_reserves_payload_index_and_metadata(tmp_path):
    binary=compile_fixture(tmp_path,source=ROOT/'tests/native/app_root_headroom.cpp')
    result=subprocess.run([binary],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout);assert report['boundary_cases']==2 and report['reserved_blocks']==24
    output=ROOT/'build/sdk-root-recovery';output.mkdir(parents=True,exist_ok=True)
    (output/'headroom-report.json').write_text(json.dumps(report,indent=2)+'\n')

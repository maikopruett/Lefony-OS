# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from test_app_files import ROOT,compile_fixture


def test_root_copy_atomicity_media_recovery_and_allocation(tmp_path):
    faults=(ROOT/'tests/native/app_developer_keys.cpp').read_text()
    (tmp_path/'app_key_fault_fixture.h').write_text(faults[faults.index('struct KeyFlash:Flash {'):faults.index('static void finish(KeyStore')])
    binary=compile_fixture(tmp_path,source=ROOT/'tests/native/app_root_record.cpp')
    result=subprocess.run([binary],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout);assert report['status']=='passed'
    assert report['interruption_cases']>=20 and report['media_cases']==11 and len(report['allocation'])==8
    output=ROOT/'build/sdk-root-recovery';output.mkdir(parents=True,exist_ok=True)
    (output/'prototype-report.json').write_text(json.dumps(report,indent=2)+'\n')

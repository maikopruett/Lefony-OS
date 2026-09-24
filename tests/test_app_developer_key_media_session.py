# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_unreadable_registry_consent_rechecks_and_cancellation(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT/'tests/native/app_developer_key_media_session.cpp',
                             extra_sources=('app_developer_keys.cpp','app_developer_key_snapshot.cpp','app_developer_key_session.cpp'))
    result = subprocess.run([binary],capture_output=True,text=True,timeout=120)
    assert result.returncode == 0, result.stdout+result.stderr
    report = json.loads(result.stdout)
    assert report == {'cases':13,'precommit_cancellations':20}
    output=ROOT/'build/sdk-key-media';output.mkdir(parents=True,exist_ok=True)
    (output/'session-host-report.json').write_text(json.dumps(report,indent=2)+'\n')

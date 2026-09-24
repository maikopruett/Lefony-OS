# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
from test_app_files import ROOT, compile_fixture


def test_developer_key_consent_protocol_and_durable_reactivation(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT / 'tests/native/app_developer_key_session.cpp',
                             extra_sources=('app_developer_keys.cpp', 'app_developer_key_snapshot.cpp', 'app_developer_key_session.cpp'))
    result = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr

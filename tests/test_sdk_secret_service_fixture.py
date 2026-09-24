# SPDX-License-Identifier: GPL-3.0-or-later
"""The destructive fixture cleanup must never own an existing user's directory."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['file', 'directory', 'symlink'])
def test_secret_fixture_refuses_existing_or_redirected_session(tmp_path, kind):
    session = tmp_path/'session'
    if kind == 'symlink':
        target = tmp_path/'real-session'; target.mkdir()
        session.symlink_to(target, target_is_directory=True)
    else:
        session.mkdir(); marker = session/'keep'
        if kind == 'directory': marker.mkdir(); marker = marker/'private-record'
        marker.write_bytes(b'existing user data must survive fixture refusal')
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    output = tmp_path/'output'
    result = subprocess.run([sys.executable, str(ROOT/'vm/sdk_test_secret_service.py'),
        '--session', str(session), '--output', str(output), '--isolated-test-service'],
        capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'Use a new empty session directory' in result.stderr
    assert not output.exists()
    assert {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    if kind == 'symlink': assert session.is_symlink() and not any(target.iterdir())

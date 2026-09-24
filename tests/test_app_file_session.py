# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_authenticated_file_sessions_and_atomic_replace(tmp_path):
    binary = compile_fixture(tmp_path, source=ROOT / 'tests/native/app_file_session.cpp',
                             extra_sources=('app_file_session.cpp',))
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    sources = ['tests/native/app_file_session.cpp', 'tests/test_app_file_session.py',
               'ports/lefony-prime-g2/ion/src/prime_g2/app_file_session.cpp',
               'ports/lefony-prime-g2/ion/src/prime_g2/app_file_store.cpp',
               'ports/lefony-prime-g2/ion/src/prime_g2/app_storage.cpp']
    output = ROOT / 'build/sdk-file-sync'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'host-report.json').write_text(json.dumps({'schema':1, 'status':'passed',
        'physical':'not_tested', 'output':result.stdout,
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}, indent=2) + '\n')

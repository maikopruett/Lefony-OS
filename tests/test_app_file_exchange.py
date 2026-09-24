# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_host_file_exchange_transactions(tmp_path):
    source = ROOT / 'tests/native/app_file_exchange.cpp'
    binary = compile_fixture(tmp_path, source=source, extra_sources=('app_file_session.cpp','app_file_exchange.cpp'))
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    sources = [source.relative_to(ROOT).as_posix(), 'tests/test_app_file_exchange.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/' + p for p in
          ('app_file_exchange.h','app_file_exchange.cpp','app_file_session.cpp','app_file_store.cpp','app_storage.cpp')]]
    output = ROOT / 'build/sdk-file-exchange';output.mkdir(exist_ok=True)
    (output / 'host-report.json').write_text(json.dumps({'schema':1,'status':'passed','physical':'not_tested',
        'output':result.stdout,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}},indent=2)+'\n')

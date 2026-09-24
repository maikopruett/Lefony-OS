# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_file_catalog_usage_and_generation_ownership(tmp_path):
    source = ROOT / 'tests/native/app_file_catalog.cpp'
    binary = compile_fixture(tmp_path, source=source, extra_sources=('app_file_session.cpp',))
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    sources = [source.relative_to(ROOT).as_posix(), 'tests/test_app_file_catalog.py',
        *['ports/lefony-prime-g2/ion/src/prime_g2/' + p for p in
          ('app_storage.cpp','app_document_store.cpp','app_file_session.cpp')], 'sdk/include/lefony/files_wire.h']
    output = ROOT / 'build/sdk-file-catalog';output.mkdir(exist_ok=True)
    (output / 'host-report.json').write_text(json.dumps({'schema':1, 'status':'passed',
        'physical':'not_tested', 'output':result.stdout,
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}, indent=2) + '\n')

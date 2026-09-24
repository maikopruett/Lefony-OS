# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import subprocess
from test_app_files import ROOT, compile_fixture


def test_private_checkpoint_snapshots_migration_and_recovery(tmp_path):
    source = ROOT / 'tests/native/app_data_session.cpp'
    binary = compile_fixture(tmp_path, source=source, extra_sources=('app_file_session.cpp', 'app_data_session.cpp'))
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['checkpoint_interruption_cases'] > 10
    sources = ['tests/native/app_data_session.cpp', 'tests/test_app_data_session.py', 'sdk/include/lefony/data_wire.h',
        *['ports/lefony-prime-g2/ion/src/prime_g2/' + name for name in
          ('app_data_session.h', 'app_data_session.cpp', 'app_file_session.h', 'app_file_session.cpp',
           'app_storage.cpp', 'app_document_store.cpp', 'app_file_store.cpp')]]
    report['sources'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    output = ROOT / 'build/sdk-data-checkpoint'
    output.mkdir(exist_ok=True)
    (output / 'host-report.json').write_text(json.dumps(report, indent=2) + '\n')

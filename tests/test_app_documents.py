# SPDX-License-Identifier: GPL-3.0-or-later
"""Production FILE3 transactions on the same synthetic NAND as legacy storage."""
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'


def test_production_document_transactions_and_recovery(tmp_path):
    fixture = (ROOT / 'tests/native/app_storage.cpp').read_text()
    (tmp_path / 'app_storage_fixture.h').write_text(
        fixture[fixture.index('struct PowerCut'):fixture.index('static void finish')])
    flags = ['-DLFS_NO_MALLOC', '-DLFS_NO_DEBUG', '-DLFS_NO_WARN', '-DLFS_NO_ERROR',
             '-DLFS_NO_ASSERT', '-fsanitize=address,undefined', '-fexceptions', '-O1', '-g',
             '-I', str(PORT), '-I', str(tmp_path)]
    objects = []
    for name in ('lfs', 'lfs_util'):
        obj = tmp_path / (name + '.o')
        subprocess.run([shutil.which('cc'), '-std=c99', *flags,
                        '-DLFS_DEFINES=littlefs_compat/defines.h', '-c', str(PORT / f'littlefs/{name}.c'),
                        '-o', str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    binary = tmp_path / 'app-documents'
    subprocess.run([shutil.which('c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror', *flags,
                    str(ROOT / 'tests/native/app_documents.cpp'), str(PORT / 'app_storage.cpp'),
                    str(PORT / 'app_document_store.cpp'), str(PORT / 'app_root_record.cpp'), str(PORT / 'app_file_store.cpp'), str(PORT / 'legacy_app_storage.cpp'),
                    *objects, '-o', str(binary)], check=True, timeout=60)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['interruption_cases'] > 100
    assert report['checkpoint_package_writes'] == 0
    assert report['checkpoint_programmed_bytes'] < report['package_bytes'] / 2
    output = ROOT / 'build/sdk-production-documents'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')

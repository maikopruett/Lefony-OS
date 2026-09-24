# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from sdk_math_vectors import build_objects, cpp, vectors

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / 'sdk'


def test_math_vendor_matches_exact_pinned_manifest():
    directory = SDK / 'lib/vendor/openbsd-math'
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['source_revision'] == 'f36520e0ed5faabbfea8a2b9f4e1309edc077927'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert {p.name for p in directory.glob('*.c')} == {name for name in manifest['files'] if name.endswith('.c')}


def test_math_known_answers_and_edge_cases_under_sanitizers(tmp_path):
    cc, cxx = shutil.which('cc'), shutil.which('c++')
    if not cc or not cxx:
        pytest.skip('C/C++ compiler unavailable')
    objects = build_objects(tmp_path)
    source = tmp_path / 'vectors.cpp';source.write_text(cpp())
    binary = tmp_path / 'math'
    subprocess.run([cxx, '-std=c++17', '-O1', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-I', str(SDK / 'include'), str(source), *objects, '-o', str(binary)], check=True, timeout=30)
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    report = ROOT / 'build/sdk-math-host.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({'status': 'passed', 'cases': len(vectors()), 'oracle': 'mpmath 1.3.0 / 400 decimal digits',
                                 'target': 'host', 'sanitizers': ['address','undefined'], 'physical': 'not_tested'}, indent=2)+'\n')

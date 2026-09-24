# SPDX-License-Identifier: GPL-3.0-or-later
"""Architecture candidates exercise real engines without enabling new formats."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from sdk_math_vectors import build_objects

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2/ion/src/prime_g2'


def test_data_only_generation_pairs_at_every_modeled_write(tmp_path):
    cc, cxx = shutil.which('cc'), shutil.which('c++')
    if not cc or not cxx:
        pytest.skip('Architecture experiment needs C and C++ host compilers')
    flags = ['-DLFS_NO_MALLOC', '-DLFS_NO_DEBUG', '-DLFS_NO_WARN', '-DLFS_NO_ERROR',
             '-fsanitize=address,undefined', '-fexceptions', '-g', '-O1', '-I', str(PORT)]
    objects = []
    for name in ('lfs', 'lfs_util'):
        obj = tmp_path / (name + '.o')
        subprocess.run([cc, '-std=c99', *flags, '-c', str(PORT / f'littlefs/{name}.c'), '-o', str(obj)],
                       check=True, timeout=60)
        objects.append(str(obj))
    binary = tmp_path / 'document-store'
    subprocess.run([cxx, '-std=c++17', *flags, '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT / 'sdk/experiments'), str(ROOT / 'tests/native/document_store.cpp'),
                    *objects, '-o', str(binary)], check=True, timeout=60)
    result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'passed'
    assert report['interruption_cases'] > 100
    assert report['checkpoint_package_writes'] == 0
    assert report['checkpoint_programmed_bytes'] < report['package_bytes']
    output = ROOT / 'build/sdk-architecture'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'document-store.json').write_text(json.dumps(report, indent=2) + '\n')


def test_bounded_expression_context_and_known_answers(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    binary = tmp_path / 'expressions'
    objects = build_objects(tmp_path)
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1',
                    '-fsanitize=address,undefined', '-I', str(ROOT / 'sdk/include'),
                    str(ROOT / 'tests/native/sdk_expression.cpp'), *objects, '-o', str(binary)], check=True, timeout=60)
    run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(run.stdout)
    assert report['status'] == 'passed' and report['context_bytes'] <= 8192
    output = ROOT / 'build/sdk-architecture'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'expressions.json').write_text(json.dumps(report, indent=2) + '\n')


def test_input_wire_and_utf8_payloads_on_firmware_language_baseline(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    source = tmp_path / 'input.cpp'
    source.write_text(r'''
#include <lefony/input_wire.h>
#include <cassert>
#include <cstring>
#include <initializer_list>
int main() {
  Lefony::InputSnapshot snapshot;
  assert(sizeof(snapshot)==128 && snapshot.size==128 && snapshot.version==1);
  assert(snapshot.physicalKey==255 && snapshot.contactCount==0 && snapshot.textBytes==0);
  snapshot.contacts[0]={7,12,13};assert(snapshot.contacts[0].id==7);
  using Lefony::validInputText;
  assert(validInputText(nullptr,0));assert(!validInputText(nullptr,1));
  for(const char *text:{"text", "\xc3\xa9", "\xce\xb1", "\xe2\x88\x9a", "\xf0\x9f\x93\x96"})
    assert(validInputText(text,strlen(text)));
  for(const char *text:{"\x11", "\x7f", "\xc2\x80", "\xc0\xaf", "\xe0\x80\xaf", "\xed\xa0\x80", "\xf4\x90\x80\x80", "\xf0\x9f", "\xff"})
    assert(!validInputText(text,strlen(text)));
  char text[33];memset(text,'a',sizeof(text));assert(validInputText(text,32));assert(!validInputText(text,33));
}
''')
    binary = tmp_path / 'input'
    subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-I', str(ROOT / 'sdk/include'), str(source), '-o', str(binary)], check=True, timeout=30)
    subprocess.run([str(binary)], check=True, timeout=10)


def test_ui_focus_capture_layout_and_utf8_selection(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    binary = tmp_path / 'ui-model'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-I', str(ROOT / 'sdk/include'), str(ROOT / 'tests/native/sdk_ui_model.cpp'),
                    '-o', str(binary)], check=True, timeout=30)
    subprocess.run([str(binary)], check=True, timeout=15)

# SPDX-License-Identifier: GPL-3.0-or-later
"""Actual C frontend, mixed linkage and reproducible ARM artifacts."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / 'sdk'
sys.path.insert(0, str(SDK / 'tools'))
from build import build
from lfapp import elf_segments


def require_toolchain():
    for name in ('gcc', 'g++', 'objcopy'):
        tool = shutil.which('arm-none-eabi-' + name)
        if not tool:
            pytest.skip('C SDK tests require the pinned ARM compiler tools')
        if name != 'objcopy' and subprocess.check_output([tool, '-dumpfullversion'], text=True).strip() != '16.2.0':
            pytest.skip('C SDK tests require GCC 16.2.0')


def project_at(path):
    (path / 'src/nested').mkdir(parents=True)
    (path / 'app.json').write_text(json.dumps({
        'id': 'c-proof', 'name': 'C proof', 'version': '0.1.0',
        'abi': 1, 'license': 'CC-BY-NC-SA-4.0'}))
    return path


def test_pure_c_frontend_and_incremental_relocation(tmp_path):
    require_toolchain()
    project = project_at(tmp_path / 'C project é')
    # _Generic and designated array initializers distinguish C11 from C++.
    (project / 'src/main.c').write_text('''
#include <lefony/app_c.h>
_Static_assert(sizeof(lefony_rect_t) == 20, "rectangle wire");
_Static_assert(sizeof(lefony_text_t) == 24, "text wire");
_Static_assert(sizeof(lefony_data_transfer_t) == 12, "data wire");
static const unsigned colors[3] = {[2] = LEFONY_GREEN};
void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)first; (void)second;
  _Static_assert(_Generic(event, uint32_t: 1, default: 0), "event wire");
  lefony_rect_t rect = {.x = 0, .y = 0, .width = 320, .height = 240, .color = colors[2]};
  if (event == LEFONY_START) lefony_fill(rect);
}
''')
    _, image = build(project, SDK)
    original = image.read_bytes()
    assert elf_segments(original)[1]
    commands = json.loads((project / 'compile_commands.json').read_text())
    assert commands[0]['arguments'][0].endswith('arm-none-eabi-gcc')
    assert '-std=c11' in commands[0]['arguments']
    assert '-fno-rtti' not in commands[0]['arguments']
    build(project, SDK)
    assert json.loads((project / 'build/build.json').read_text())['compiled'] == []
    relocated = tmp_path / 'C relocated'
    shutil.copytree(project, relocated, ignore=shutil.ignore_patterns('build', 'compile_commands.json'))
    _, copied = build(relocated, SDK)
    assert copied.read_bytes() == original


def test_mixed_c_cpp_linkage_and_language_specific_incremental_build(tmp_path):
    require_toolchain()
    project = project_at(tmp_path / 'mixed')
    (project / 'src/nested/value.c').write_text('''
unsigned c_value(void) { return 123; }
''')
    (project / 'src/main.cpp').write_text('''
#include <lefony/app.h>
#include <lefony/app_c.h>
#include <stddef.h>
static_assert(sizeof(lefony_rect_t) == sizeof(Lefony::Rect), "rect size");
static_assert(offsetof(lefony_text_t, value) == offsetof(Lefony::Text, value), "text pointer");
static_assert(sizeof(lefony_data_transfer_t) == sizeof(Lefony::DataTransfer), "data size");
extern "C" unsigned c_value(void);
extern "C" void lefony_event(Lefony::Event, uint32_t, uint32_t) {
  Lefony::fill({0, 0, 320, 240, c_value()});
}
''')
    build(project, SDK)
    commands = json.loads((project / 'compile_commands.json').read_text())
    assert {Path(item['file']).suffix for item in commands} == {'.c', '.cpp'}
    for item in commands:
        assert ('-std=c11' if item['file'].endswith('.c') else '-std=c++17') in item['arguments']
    (project / 'src/nested/value.c').write_text('unsigned c_value(void) { return 456; }\n')
    build(project, SDK)
    report = json.loads((project / 'build/build.json').read_text())
    assert report['compiled'] == ['src/nested/value.c']
    assert report['languages'] == ['c++17', 'c11']


def test_c_frontend_error_is_not_ignored(tmp_path):
    require_toolchain()
    project = project_at(tmp_path / 'broken')
    (project / 'src/main.c').write_text('this is not C;\n')
    with pytest.raises(subprocess.CalledProcessError):
        build(project, SDK)
    assert not (project / 'build/build.json').exists()

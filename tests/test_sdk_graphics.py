# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import pytest
from sdk_math_vectors import build_objects

ROOT = Path(__file__).resolve().parents[1]


def test_graphics_clipping_and_bounded_buffers_under_sanitizers(tmp_path):
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    source = tmp_path / 'graphics.cpp'
    source.write_text('#include "sdk_graphics_cases.h"\n#include "sdk_plot_cases.h"\n#include "sdk_gesture_cases.h"\nint main() { return GraphicsTests::test() && PlotTests::test() && GestureTests::test()?0:1; }\n')
    executable = tmp_path / 'graphics'
    objects = build_objects(tmp_path)
    subprocess.run([compiler, '-std=c++17', '-O1', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'tests/native'),
                    str(source), *objects, '-o', str(executable)], check=True, timeout=60)
    subprocess.run([str(executable)], check=True, timeout=30)

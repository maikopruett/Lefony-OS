# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import importlib.util
import shutil
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]


def test_system_ownership_expiration_text_and_request_validation(tmp_path):
    compiler = shutil.which('clang++') or shutil.which('g++')
    assert compiler
    binary = tmp_path / 'system'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-I', str(ROOT/'sdk/include'), '-I', str(ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'),
        str(ROOT/'tests/native/app_system.cpp'), '-o', str(binary)], check=True, timeout=30)
    subprocess.run([binary], check=True, timeout=30)


def test_clipboard_transform_idempotence_and_context(tmp_path):
    spec = importlib.util.spec_from_file_location('prepare_system', ROOT/'scripts/prepare_prime_native_system.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    container=tmp_path/'apps/apps_container.cpp';container.parent.mkdir(parents=True)
    container.write_text('bool AppsContainer::dispatchEvent(Ion::Events::Event event) {\n}\n')
    path = tmp_path/'escher/include/escher/clipboard.h';path.parent.mkdir(parents=True)
    path.write_text('class Clipboard {\n  const char * storedText();\n};\n')
    module.prepare(tmp_path);once=path.read_bytes();dispatch=container.read_bytes();module.prepare(tmp_path)
    assert path.read_bytes()==once and container.read_bytes()==dispatch
    path.write_text('class Unexpected {};\n')
    with pytest.raises(ValueError, match='Unexpected'):module.prepare(tmp_path)


def test_c_and_cpp_wire_layout(tmp_path):
    for language,standard in (('c','c11'),('cpp','c++17')):
        source=tmp_path/f'wire.{language}';source.write_text('#include <lefony/system.h>\nint main(void) { return sizeof(LefonySystemInfo)!=160; }\n')
        compiler=shutil.which('arm-none-eabi-gcc' if language=='c' else 'arm-none-eabi-g++')
        if not compiler:pytest.skip('System wire checks require the ARM compiler tools')
        subprocess.run([compiler,f'-std={standard}','-Wall','-Wextra','-Werror','-ffreestanding','-mcpu=cortex-a7','-marm',
            '-I',str(ROOT/'sdk/include'),'-c',str(source),'-o',str(tmp_path/f'wire-{language}.o')],check=True,timeout=30)

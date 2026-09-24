# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]


def test_channel_ownership_queues_replay_and_lifecycle(tmp_path):
    compiler=shutil.which('clang++') or shutil.which('g++');assert compiler
    binary=tmp_path/'channel'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','-I',str(ROOT/'sdk/include'),'-I',str(ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'),
        str(ROOT/'tests/native/app_channel.cpp'),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([str(binary)],check=True,timeout=30)


@pytest.mark.parametrize('language,standard',[('c','c11'),('cpp','c++17')])
def test_channel_c_and_cpp_wire(tmp_path,language,standard):
    source=tmp_path/f'wire.{language}';source.write_text('#include <lefony/channel.h>\nint main(void) {return sizeof(LefonyChannelInfo)!=320;}\n')
    compiler=shutil.which('arm-none-eabi-gcc' if language=='c' else 'arm-none-eabi-g++')
    if not compiler:pytest.skip('ARM C/C++ compiler required')
    subprocess.run([compiler,f'-std={standard}','-Wall','-Wextra','-Werror','-ffreestanding','-mcpu=cortex-a7','-marm',
        '-I',str(ROOT/'sdk/include'),'-c',str(source),'-o',str(tmp_path/'wire.o')],check=True,timeout=30)

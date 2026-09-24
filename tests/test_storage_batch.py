# SPDX-License-Identifier: GPL-3.0-or-later
"""Ensure faster storage cannot monopolize input, even with a stopped timer."""
from pathlib import Path
import shutil
import subprocess

def test_storage_batch_yields_on_deadline_completion_and_stopped_clock(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=tmp_path/'batch.cpp'
    source.write_text(r'''
#include "storage_batch.h"
#include <cassert>
using PrimeG2::StorageBatch::run;
int main() {
  unsigned steps=0;uint32_t now=0;
  run([&]{return now;},[]{return true;},[&]{steps++;now+=16000;});
  assert(steps==3); // 16 ms budget.
  steps=0;now=0xffffc000u;
  run([&]{return now;},[]{return true;},[&]{steps++;now+=24000;});
  assert(steps==2); // Unsigned timer wrap.
  steps=0;
  run([]{return 0u;},[]{return true;},[&]{steps++;});
  assert(steps==64); // Stopped/absent timer cannot spin forever.
  steps=0;
  run([]{return 0u;},[&]{return steps<2;},[&]{steps++;});
  assert(steps==2); // Completion/failure ends work immediately.
  steps=0;
  run([]{return 0u;},[]{return false;},[&]{steps++;});
  assert(steps==1); // Normal USB/service poll still occurs while idle.
}
''')
    binary=tmp_path/'batch'
    subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror',
        '-I',str(root/'ports/lefony-prime-g2/ion/src/prime_g2'),str(source),'-o',str(binary)],check=True,timeout=60)
    subprocess.run([str(binary)],check=True,timeout=10)

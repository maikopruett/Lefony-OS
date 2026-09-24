# SPDX-License-Identifier: GPL-3.0-or-later
"""Key edges survive event-wait boundaries without changing held-key behavior."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_key_release_history_survives_timeouts(tmp_path):
    compiler=shutil.which('c++')
    if not compiler: pytest.skip('C++ host compiler unavailable')
    source=tmp_path/'keys.cpp'
    source.write_text('''
#include "key_edge_tracker.h"
#include <cassert>
int main() {
  PrimeG2::KeyEdgeTracker edges;
  constexpr uint64_t ok=uint64_t(1)<<4, right=uint64_t(1)<<3;
  assert(edges.update(ok)==0); // A key already held at boot is not a new edge.
  assert(edges.update(0)==0);
  for(unsigned i=0;i<1000;i++) assert(edges.update(0)==0);
  // An OS event wait times out here; the next wait sees the key already down.
  assert(edges.update(ok)==ok);
  for(unsigned i=0;i<1000;i++) assert(edges.update(ok)==0);
  assert(edges.update(0)==0);
  assert(edges.update(ok)==ok); // Release and repress: exactly one new action.
  assert(edges.update(ok|right)==right);
  assert(edges.update(ok|right)==0);
  assert(edges.update(0)==0);
  assert(edges.update(ok|right)==(ok|right)); // Consume the complete chord.
  assert(edges.update(right)==0);
  assert(edges.update(0)==0);
  assert(edges.update(right)==right);
  // All 64 matrix bits, including the high bit, have identical semantics.
  assert(edges.update(0)==0);
  for(unsigned bit=0;bit<64;bit++) {
    uint64_t mask=uint64_t(1)<<bit;
    assert(edges.update(mask)==mask);
    assert(edges.update(mask)==0);
    assert(edges.update(0)==0);
  }
}
''')
    binary=tmp_path/'keys'
    subprocess.run([compiler,'-std=c++11','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-I',str(ROOT/'ports/lefony-prime-g2/ion/src/prime_g2'),
                    str(source),'-o',str(binary)],check=True,timeout=30)
    subprocess.run([str(binary)],check=True,timeout=10)

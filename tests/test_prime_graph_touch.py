"""Execute the production tracker and gesture geometry on the host."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports/lefony-prime-g2"


class GraphTouchTest(unittest.TestCase):
    def test_contact_transitions_and_graph_geometry(self):
        code = r'''
#include "touch_tracker.h"
#include "prime_graph_gesture.h"
#include <cassert>
#include <cmath>
using Ion::Touch::Phase;
int main() {
  PrimeG2::TouchTracker t;
  PrimeG2::GraphGesture g;
  PrimeG2::GraphGesture::Delta d;
  assert(t.report(1, 5, 100, 100));
  assert(!g.update(t.event(), &d));
  t.report(1, 5, 102, 102);
  assert(!g.update(t.event(), &d)); // tap slop, retain original pan anchor
  t.report(1, 5, 120, 130);
  assert(g.update(t.event(), &d));
  assert(d.ratio == 1 && d.fromX == 100 && d.toX == 120 && d.toY == 130);
  // A lower ID joins: sorted records must not imply a replacement or pan.
  assert(t.report(2, 5, 120, 130, 2, 200, 130));
  assert(t.event().contactsChanged && t.event().dragging);
  assert(!g.update(t.event(), &d));
  assert(!t.report(2, 2, 200, 130, 5, 120, 130)); // reordered same points
  t.report(2, 5, 90, 140, 2, 250, 140);
  assert(g.update(t.event(), &d));
  assert(d.ratio == .5f && d.fromX == 160 && d.toX == 170 && d.toY == 140);
  t.report(2, 2, 210, 140, 5, 130, 140);
  assert(g.update(t.event(), &d) && d.ratio == 2.f); // pinch inward
  // Either finger may lift; continuing pan must start at the survivor.
  t.report(1, 5, 130, 140);
  assert(t.event().contactsChanged && !g.update(t.event(), &d));
  t.report(1, 5, 140, 150);
  assert(g.update(t.event(), &d) && d.fromX == 130 && d.toX == 140 && d.ratio == 1);
  t.report(0, 0, 65535, 65535);
  assert(t.event().phase == Phase::Up && t.event().x == 140);
  assert(!g.update(t.event(), &d));
  // Simultaneous two-finger down and near-coincident contacts remain finite.
  t.report(2, 0, 100, 100, 1, 101, 100);
  assert(!g.update(t.event(), &d));
  t.report(2, 0, 100, 100, 1, 100, 100);
  assert(g.update(t.event(), &d) && d.ratio == 1 && std::isfinite(d.ratio));
  t.report(2, 0, 80, 100, 1, 120, 100);
  assert(g.update(t.event(), &d) && d.ratio == 1);
  t.report(2, 0, 60, 100, 1, 140, 100);
  assert(g.update(t.event(), &d) && d.ratio == .5f);
  // Third finger cancels until all lift, without a new tap on the survivor.
  assert(t.report(3, 0, 60, 100) && t.cancelled());
  assert(!g.update(t.event(), &d));
  assert(!t.report(1, 0, 60, 100));
  assert(!t.report(0, 0, 0, 0));
  assert(t.report(2, 0, 60, 100, 1, 140, 100));
  assert(t.report(2, 0, 60, 100, 3, 140, 100) && t.cancelled()); // replaced ID
  t.report(0, 0, 0, 0);
  t.report(2, 0, 60, 100, 1, 140, 100);
  assert(t.report(2, 0, 60, 100, 0, 140, 100) && t.cancelled()); // duplicate ID
  t.report(0, 0, 0, 0);
  t.report(2, 0, 60, 100, 1, 140, 100);
  assert(t.report(2, 0, 60, 100, 1, 320, 100) && t.cancelled());
}
'''
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "graph-touch"
            subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(PORT / "ion/include"), "-I", str(PORT / "ion/src/prime_g2"),
                            "-I", str(PORT / "apps"), "-x", "c++", "-", "-o", str(binary)],
                           input=code, text=True, check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()

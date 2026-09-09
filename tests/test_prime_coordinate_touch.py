from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports/lefony-prime-g2"


class CoordinateTouchTest(unittest.TestCase):
    def test_compiled_contact_state_machine(self):
        code = r'''
#include "touch_tracker.h"
#include <cassert>
using PrimeG2::TouchTracker;
using Ion::Touch::Phase;
int main() {
  TouchTracker t;
  assert(!t.report(0, 0, 65535, 65535));
  assert(t.report(1, 2, 220, 180));
  assert(t.event().phase == Phase::Down);
  assert(!t.report(1, 2, 220, 180));
  assert(t.report(1, 2, 223, 182) && !t.event().dragging);
  assert(t.report(0, 99, 0, 0));
  assert(t.event().phase == Phase::Up && t.event().x == 223 && t.event().y == 182);
  assert(!t.report(0, 0, 0, 0));
  assert(t.report(1, 0, 100, 100));
  assert(t.report(1, 0, 100, 90) && t.event().dragging);
  assert(t.report(1, 0, 100, 100) && t.event().dragging);
  assert(t.report(0, 0, 65535, 65535) && t.event().dragging);
  assert(t.report(1, 1, 50, 50));
  assert(t.report(2, 1, 50, 50) && t.cancelled());
  assert(t.event().phase == Phase::Cancel);
  assert(!t.report(1, 1, 50, 50)); // second finger lifting is not a new tap
  assert(!t.report(0, 0, 0, 0));
  assert(t.report(1, 1, 50, 50));
  assert(t.report(1, 3, 50, 50) && t.event().phase == Phase::Cancel);
  t.report(0, 0, 0, 0);
  assert(t.report(1, 0, 50, 50));
  assert(t.report(1, 0, 320, 50) && t.cancelled());
  t.report(0, 0, 0, 0);
  assert(t.report(1, 0, 50, 50));
  assert(t.cancel()); // failed I2C transaction
  assert(!t.report(1, 0, 50, 50));
  t.report(0, 0, 0, 0);
  assert(t.report(1, 0, 50, 50) && !t.cancelled());
}
'''
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "touch-test"
            subprocess.run(["c++", "-std=c++11", "-I", str(PORT / "ion/include"),
                            "-I", str(PORT / "ion/src/prime_g2"), "-x", "c++", "-",
                            "-o", str(binary)], input=code, text=True, check=True)
            subprocess.run([str(binary)], check=True)

    def test_touch_does_not_turn_into_global_keyboard_shortcuts(self):
        source = (PORT / "ion/src/prime_g2/touch.cpp").read_text()
        for event in ("Left", "Right", "Up", "Down", "OK", "Apps", "Back"):
            self.assertNotIn("Ion::Events::" + event, source)
        self.assertIn("sTracker.report(contacts, report[1] & 0x0F, x, y,", source)

    def test_table_capture_scroll_and_activation_guards(self):
        source = (PORT / "apps/prime_touch_table_impl.h").read_text()
        self.assertIn("m_contentView.touchOrigin()", source)
        self.assertIn("m_contentView.cellFrame(i, j).contains(point)", source)
        self.assertIn("setContentOffset(KDPoint(x, y))", source)
        self.assertIn("bool activate = !touch.dragging", source)
        self.assertIn("column == m_touchColumn && row == m_touchRow", source)
        self.assertIn("canSelectCellByTouch", source)
        self.assertIn("if (!cell->isHighlighted()) cell->setHighlighted(true);", source)
        self.assertIn("markRectAsDirty(bounds());", source)

    def test_build_integration_and_modal_cancellation(self):
        script = (ROOT / "scripts/prepare_prime_touch.py").read_text()
        self.assertIn("Activation may destroy this App", script)
        self.assertIn("void App::willBecomeInactive()", script)
        self.assertIn("void App::dismissModalViewController", script)
        self.assertIn("if (event.isKeyboardEvent()) cancelTouch();", script)
        self.assertIn("prepare_prime_touch.py", (ROOT / "scripts/build_lefony_prime_g2.sh").read_text())

    def test_calculation_history_has_coordinate_recall_not_generic_ok(self):
        source = (PORT / "apps/prime_calculation_touch_impl.h").read_text()
        self.assertIn("cell->inputView()", source)
        self.assertIn("cell->outputView()", source)
        self.assertIn("touchTargetsApproximate", source)
        self.assertIn("target == m_historyTouchTarget && row == m_historyTouchRow", source)
        self.assertIn("m_historyTouchTarget = 0;", source)
        self.assertIn("Phase::Cancel", source)
        self.assertIn("setContentOffset", source)
        self.assertNotIn("processEvent(Ion::Events::OK)", source)
        script = (ROOT / "scripts/prepare_prime_touch.py").read_text()
        self.assertIn("return m_contentView.mainView()->handleTouch(touch);", script)
        self.assertIn("strlcpy(text, source, sizeof(text));", script)
        self.assertIn("insertTextBody(text)", script)


if __name__ == "__main__":
    unittest.main()

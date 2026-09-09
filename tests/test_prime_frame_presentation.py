from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports/lefony-prime-g2"


class FramePresentationTest(unittest.TestCase):
    def test_compiled_frame_ownership_and_timeout_recovery(self):
        code = r'''
#include "frame_presenter.h"
#include <cassert>
#include <cstring>
struct Hardware {
  uint32_t * front;
  uint32_t * next = nullptr;
  uint32_t * published = nullptr;
  bool stalled = false;
  unsigned waits = 0, queues = 0;
  explicit Hardware(uint32_t * initial): front(initial) {}
  const uint32_t * current() { return front; }
  void publish(uint32_t * p, size_t bytes) {
    assert(p != front && bytes == 16); published = p;
  }
  void queue(uint32_t * p) {
    assert(p == published && p != front); next = p; queues++;
  }
  void pause() { waits++; if (!stalled) front = next; }
};
int main() {
  uint32_t source[] = {1,2,3,4}, a[] = {0,0,0,0}, b[] = {0,0,0,0};
  Hardware h(a);
  PrimeG2::FramePresenter<4> p;
  assert(p.present(source,a,b,h));
  assert(h.front == b && h.queues == 1 && p.frames() == 1);
  assert(!memcmp(source,b,16) && a[0] == 0);
  // No dirty frame means no copy, no queued swap, and no busy wait.
  assert(p.present(source,a,b,h) && h.queues == 1);
  source[2] = 9; p.changed();
  h.stalled = true;
  assert(!p.present(source,a,b,h));
  assert(h.front == b && h.next == a && h.queues == 2);
  assert(b[2] == 3 && a[2] == 9 && p.timeouts() == 1);
  unsigned waits = h.waits;
  // Rendering can continue in the shadow after a stopped LCDIF. Neither
  // pending nor active DMA memory may be written even across many failures.
  source[0] = 8; p.changed();
  for (unsigned i=0; i<3; i++) assert(!p.present(source,a,b,h));
  assert(h.waits == waits + 1500 && h.queues == 2);
  assert(a[0] == 1 && b[0] == 1);
  h.stalled = false;
  assert(p.present(source,a,b,h));
  assert(h.front == b && h.queues == 3 && p.frames() == 3);
  // A partial redraw must retain all other pixels from the logical image.
  assert(b[0] == 8 && b[1] == 2 && b[2] == 9 && b[3] == 4);
  // Reinitialization after standby resets pending ownership and republishes.
  p.reset(); h.front = a;
  assert(p.present(source,a,b,h) && h.front == b);
  // An unexpected CUR address is never guessed or overwritten.
  h.front = source; p.changed(); waits = h.queues;
  assert(!p.present(source,a,b,h) && h.queues == waits);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "frame-test"
            subprocess.run(["c++", "-std=c++11", "-I", str(PORT / "ion/src/prime_g2"),
                            "-x", "c++", "-", "-o", str(binary)],
                           input=code, text=True, check=True)
            subprocess.run([str(binary)], check=True)

    def test_window_hook_is_idempotent_and_precedes_backlight(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("display_prepare", ROOT / "scripts/prepare_prime_display.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "apps").mkdir()
            (source / "apps/apps_container.cpp").write_text(
                '#include "prime_g2_boot_progress.h"\n    // Exception\n')
            (source / "escher/src").mkdir(parents=True)
            path = source / "escher/src/window.cpp"
            path.write_text('#include <escher/window.h>\nvoid redraw() {\n'
                            '  View::redraw(bounds());\n  PrimeG2BootProgress(20);\n'
                            '  PrimeG2FirstFrameReady();\n}\n')
            module.prepare(source)
            first = path.read_text()
            module.prepare(source)
            self.assertEqual(first, path.read_text())
            self.assertIn('PrimeFrame::cancel();', (source / 'apps/apps_container.cpp').read_text())
            self.assertEqual(first.count("PrimeFrame frame;"), 1)
            self.assertLess(first.index("PrimeFrame frame;"), first.index("View::redraw"))
            self.assertIn("  } // Present the complete frame before revealing the backlight.\n  PrimeG2FirstFrameReady();", first)

    def test_build_and_lcdif_integration(self):
        source = (PORT / "ion/src/prime_g2/display.cpp").read_text()
        self.assertIn("FramebufferStorage sScanout[2]", source)
        self.assertIn("sizeof(FramebufferStorage) * 3 <= 1024 * 1024", source)
        self.assertIn("sScanout[0].pixels", source)
        self.assertIn("PrimeG2::LCDIF + 0x50", source)
        self.assertIn("prepare_prime_display.py", (ROOT / "scripts/build_lefony_prime_g2.sh").read_text())


if __name__ == "__main__":
    unittest.main()

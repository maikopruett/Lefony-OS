from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'ports/lefony-prime-g2'


class DisplaySettingsTests(unittest.TestCase):
    def test_compiled_refresh_confirmation_deadline(self):
        code = r'''
#include "refresh_trial.h"
#include <cassert>
int main() {
  PrimeG2::RefreshTrial trial;
  assert(!trial.active() && !trial.confirm(0));
  trial.start(100);
  assert(trial.active() && !trial.expired(15099));
  assert(trial.expired(15100));
  assert(!trial.confirm(15100)); // no accepting a stale confirmation
  trial.cancel(); assert(!trial.active());
  trial.start(1ull << 33); // clock is 64 bit, not a wrapping 32-bit tick
  assert(trial.confirm((1ull << 33) + 1000));
  assert(!trial.active());
  trial.start(50000);
  assert(trial.expired(50000 + 172800000)); // large elapsed/suspend gap
}
'''
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'trial'
            subprocess.run(['c++', '-std=c++11', '-I', str(PORT / 'ion/src/prime_g2'),
                            '-x', 'c++', '-', '-o', str(binary)], input=code, text=True, check=True)
            subprocess.run([str(binary)], check=True)

    def test_usb_keeps_awake_without_forcing_full_brightness(self):
        text = (PORT / 'apps/lefony_usb_page.h').read_text()
        self.assertIn('GlobalPreferences::sharedGlobalPreferences()->brightnessLevel()', text)
        self.assertIn('setBrightness(chosen)', text)
        self.assertNotIn('setBrightness(Ion::Backlight::MaxBrightness)', text)
        script = (ROOT / 'scripts/prepare_prime_settings.py').read_text()
        self.assertIn('prime_g2_update_in_progress() || prime_g2_external_power_present()', script)
        self.assertIn('e.isKeyboardEvent() || e == Ion::Events::Touch', script)

    def test_refresh_is_physical_bounded_and_session_only(self):
        text = (PORT / 'ion/src/prime_g2/display.cpp').read_text()
        self.assertIn('(sRefreshRate == 55 ? 7u : 5u) << 12', text)
        self.assertIn('(sRefreshRate == 55 ? 3u : 4u) << 23', text)
        self.assertIn('hz != 55 && hz != 59', text)
        self.assertIn('sRefreshTrial.start(Timing::elapsedMillis())', text)
        self.assertIn('applyRefreshRate(59)', text)
        self.assertNotIn('sRefreshRate', (PORT / 'apps/prime_g2_persistent_preferences.cpp').read_text())
        ui = (PORT / 'apps/settings/sub_menu/lefony_refresh_controller.h').read_text()
        self.assertIn('viewDidDisappear()', ui)
        self.assertIn('cancelRefreshTrial()', ui)
        self.assertIn('if (!m_timerAdded)', ui)
        self.assertIn('removeTimer(this)', ui)
        self.assertIn('setNext(nullptr)', ui)
        self.assertIn('touch.dragging', ui)
        self.assertIn('experimental', ui)
        self.assertNotIn('setFirstResponder(this)', ui) # already the modal's first responder

    def test_timing_derivation_and_emulator_clock(self):
        self.assertEqual(528000000 * 1000 // (6 * 5 * 1132 * 264), 58892)
        self.assertEqual(528000000 * 1000 // (8 * 4 * 1132 * 264), 55212)
        patch = (ROOT / 'vm/patches/qemu-prime-g2-refresh-clock.patch').read_text()
        self.assertIn('prime_panel_frame_period_ns(s)', patch)
        self.assertIn('timer_mod(s->frame_timer, now + period)', patch)
        self.assertIn('prepare_prime_brightness.py', (ROOT / 'scripts/build_lefony_prime_g2.sh').read_text())


if __name__ == '__main__':
    unittest.main()

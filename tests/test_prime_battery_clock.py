import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BatteryClockTests(unittest.TestCase):
    def test_clock_hidden_by_default_without_stopping_battery_timebase(self):
        source = (ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/services.cpp").read_text()
        self.assertIn("sRTCMode = Ion::RTC::Mode::Disabled", source)
        mode = source.split("void setMode(Mode mode)", 1)[1].split("Mode mode()", 1)[0]
        self.assertIn("sRTCMode = mode", mode)
        self.assertIn("setBits(SNVSLPCR, SNVSRtcEnable)", mode)
        self.assertNotIn("clearBits", mode)

    def test_real_clock_arithmetic_wrap_and_rtc_adjustment(self):
        source = r'''
#include "elapsed_clock.h"
#include <cassert>
int main() {
  PrimeG2::ElapsedClock clock;
  assert(clock.update(0xfffffff0u) == 0);
  assert(clock.update(0xfffffff0u) == 0); // stopped counter
  assert(clock.update(0x100007ff0ULL) == 1000); // low-word rollover
  assert(clock.update(0x10000fff0ULL) == 2000);
  clock.rebase(0x3ff0); // calendar moved backwards: elapsed unchanged
  assert(clock.update(0x3ff0) == 2000);
  clock.rebase(0x700000003ff0ULL); // calendar moved decades forwards
  assert(clock.update(0x700000003ff0ULL) == 2000);
  assert(clock.update(0x700000007ff0ULL) == 2500);
  PrimeG2::ElapsedClock samples;
  samples.update(0);
  for (unsigned n = 1; n <= 100; ++n)
    assert(samples.update(n * 32768 / 10) >= n * 100 - 1);
  PrimeG2::ElapsedClock sleep;
  sleep.update(123);
  // Sleep beyond the old low-word rollover (~36 hours), no one-second cap.
  const uint64_t twoDays = 2ULL * 86400 * 32768;
  assert(sleep.update(123 + twoDays) == 172800000);
  // One overdue poll is due immediately; no need to replay missed samples.
  assert(sleep.update(123 + twoDays) >= 30000);
  PrimeG2::ElapsedClock wrap;
  wrap.update(PrimeG2::ElapsedClock::CounterMask - 15);
  assert(wrap.update(32752) == 1000); // full 47-bit rollover
  assert(wrap.update(0) == 1000); // unexpected backwards reset ignored
  assert(wrap.update(32768) == 2000);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "clock-test"
            subprocess.run(["c++", "-std=c++11", "-x", "c++", "-",
                            "-I", str(ROOT / "ports/lefony-prime-g2/ion/src/prime_g2"),
                            "-o", str(binary)], input=source, text=True, check=True)
            subprocess.run([str(binary)], check=True)

    def test_physical_sampling_and_charger_refresh_share_live_clock(self):
        source = (ROOT / "ports/lefony-prime-g2/ion/src/prime_g2/services.cpp").read_text()
        clock = source.split("uint64_t batteryClock()", 1)[1].split("bool leapYear", 1)[0]
        self.assertIn("PrimeG2::Timing::elapsedMillis()", clock)
        setter = source.split("void writeSNVSSeconds", 1)[1].split("emulatedDateTime", 1)[0]
        self.assertLess(setter.index("Timing::elapsedMillis()"), setter.index("clearBits"))
        self.assertLess(setter.index("reg32(SNVSLPSRTCMR) ="), setter.index("calendarClockDidChange()"))
        self.assertLess(setter.index("calendarClockDidChange()"), setter.index("setBits"))
        poll = source.split("void poll()", 1)[1].split("void noteUserActivity", 1)[0]
        self.assertIn("batteryNow >= sNextBatterySample", poll)
        self.assertIn("batteryNow >= sNextBatteryPoll", poll)
        self.assertNotIn("Ion::Timing::millis()", poll)

#pragma once

#include <stdint.h>

namespace PrimeG2 {

/* Sleep-aware elapsed time, independent of calendar time. The full 47-bit
 * SNVS counter keeps multi-day sleeps (and low-word rollovers) unambiguous.
 * A calendar setter must update before changing the hardware, then rebase
 * afterwards. Rebasing changes the reference, never the elapsed duration. */
class ElapsedClock {
public:
  static constexpr uint64_t CounterMask = (uint64_t{1} << 47) - 1;

  uint64_t update(uint64_t counter) {
    counter &= CounterMask;
    if (m_initialized) {
      uint64_t delta = (counter - m_previous) & CounterMask;
      // An unexpected backwards hardware reset is not decades of sleep.
      if (delta <= CounterMask / 2) m_ticks += delta;
    }
    rebase(counter);
    return (m_ticks / 32768) * 1000 + (m_ticks % 32768) * 1000 / 32768;
  }

  void rebase(uint64_t counter) {
    m_initialized = true;
    m_previous = counter & CounterMask;
  }

private:
  bool m_initialized = false;
  uint64_t m_previous = 0;
  uint64_t m_ticks = 0;
};

}

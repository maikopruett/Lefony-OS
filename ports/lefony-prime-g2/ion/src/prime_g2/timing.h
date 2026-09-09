#ifndef ION_PRIME_G2_TIMING_H
#define ION_PRIME_G2_TIMING_H

#include <stdint.h>

namespace PrimeG2 {
namespace Timing {

void init();
void enableInterrupt();
void enterRuntime();
// Main-loop API: includes sleep; unaffected by supported date/time changes.
uint64_t elapsedMillis();
// Calendar setters: sample elapsedMillis before the write, then rebase after.
void calendarClockDidChange();
uint64_t interruptTicks();
uint32_t missedDeadlines();
#if PRIME_G2_EMULATOR
uint64_t testOffset();
void advanceForTest(uint32_t milliseconds);
bool rolloverSelfTest();
#endif

}
}

#endif

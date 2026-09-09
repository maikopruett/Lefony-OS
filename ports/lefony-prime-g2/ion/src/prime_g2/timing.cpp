#include "registers.h"
#include "timing.h"
#include "interrupts.h"
#include "elapsed_clock.h"

#include <ion/timing.h>

namespace {
constexpr uintptr_t GPT_CR = PrimeG2::GPT1 + 0x00;
constexpr uintptr_t GPT_PR = PrimeG2::GPT1 + 0x04;
constexpr uintptr_t GPT_IR = PrimeG2::GPT1 + 0x0C;
constexpr uintptr_t GPT_SR = PrimeG2::GPT1 + 0x08;
constexpr uintptr_t GPT_OCR1 = PrimeG2::GPT1 + 0x10;
constexpr uintptr_t GPT_CNT = PrimeG2::GPT1 + 0x24;

constexpr uint32_t CR_EN = 1u << 0;
constexpr uint32_t CR_WAITEN = 1u << 3;
/* Own the PERCLK clock before enabling GPT, rather than depending on the
 * inherited oscillator input or letting backlight setup change PERCLK under
 * a running timer. OSC / 1, then the GPT prescaler / 8 gives 3 MHz on both
 * hardware and the emulator. Selector 2 bypasses GPT's separate PRE24M path. */
constexpr uint32_t CR_CLKSRC = 2u << 6;
constexpr uint32_t Prescaler = 7;
constexpr uint32_t TICKS_PER_MICROSECOND = 3;
constexpr uint32_t CR_FRR = 1u << 9;
constexpr uint32_t CompareInterrupt = 1u;
constexpr uint32_t InterruptPeriodMilliseconds = 10;
#if PRIME_G2_EMULATOR
uint64_t sTestOffset = 0;
#endif
volatile uint64_t sInterruptTicks = 0;
volatile uint32_t sMissedDeadlines = 0;
uint32_t sNextCompare = 0;
PrimeG2::ElapsedClock sElapsedClock;
bool sCalendarRebasePending = false;
constexpr uint64_t InvalidSleepCounter = ~uint64_t{0};

uint64_t readSleepCounter() {
  // SNVS crosses an asynchronous clock domain: require two identical full
  // reads, as Linux rtc-snvs does, not just matching high words. Bounded so
  // a malfunctioning peripheral cannot hang the UI.
  uint64_t previous = InvalidSleepCounter;
  for (unsigned attempt = 0; attempt < 100; ++attempt) {
    uint32_t high = PrimeG2::reg32(PrimeG2::SNVS + 0x50) & 0x7fffu;
    uint32_t low = PrimeG2::reg32(PrimeG2::SNVS + 0x54);
    uint64_t counter = (static_cast<uint64_t>(high) << 32) | low;
    if (counter == previous) return counter;
    previous = counter;
  }
  return InvalidSleepCounter; // invalid sample; do not advance or rebase
}
#if !PRIME_G2_EMULATOR
bool sRuntimeDelays = false;
#endif

void timerInterrupt() {
  PrimeG2::reg32(GPT_SR) = CompareInterrupt;
  uint32_t now = PrimeG2::reg32(GPT_CNT);
  unsigned advanced = 0;
  do {
    sNextCompare += TICKS_PER_MICROSECOND * 1000 * InterruptPeriodMilliseconds;
    sInterruptTicks += InterruptPeriodMilliseconds;
    advanced++;
  } while (static_cast<int32_t>(now - sNextCompare) >= 0 && advanced < 1024);
  if (advanced > 1) sMissedDeadlines += advanced - 1;
  PrimeG2::reg32(GPT_OCR1) = sNextCompare;
}

uint64_t extendCounter(uint32_t now, uint32_t &previous, uint64_t &high) {
  if (now < previous) high += uint64_t{1} << 32;
  previous = now;
  return high + now;
}
}

namespace PrimeG2 {
namespace Timing {

void init() {
  gate(0x6C, 20);
  gate(0x6C, 22);
  reg32(GPT_CR) = 0;
  reg32(GPT_IR) = 0;
  updateBits(CCM + 0x1C, (1u << 6) | 0x3Fu, 1u << 6);
  reg32(GPT_PR) = Prescaler;
  reg32(GPT_CR) = CR_EN | CR_WAITEN | CR_CLKSRC | CR_FRR;
}

void enableInterrupt() {
  sNextCompare = reg32(GPT_CNT) +
    TICKS_PER_MICROSECOND * 1000 * InterruptPeriodMilliseconds;
  reg32(GPT_SR) = 0x3Fu;
  reg32(GPT_OCR1) = sNextCompare;
  if (Interrupts::registerHandler(Interrupts::GPT1, timerInterrupt, 0x40)) {
    reg32(GPT_IR) = CompareInterrupt;
    Interrupts::enable(Interrupts::GPT1);
  }
}

void enterRuntime() {
#if !PRIME_G2_EMULATOR
  sRuntimeDelays = true;
#endif
}

uint64_t elapsedMillis() {
#if PRIME_G2_EMULATOR
  // Preserve the existing TIME ADVANCE control in emulator-target builds.
  return Ion::Timing::millis();
#else
  static uint64_t last = 0;
  uint64_t counter = readSleepCounter();
  if (counter != InvalidSleepCounter) {
    if (sCalendarRebasePending) {
      sElapsedClock.rebase(counter);
      sCalendarRebasePending = false;
    }
    last = sElapsedClock.update(counter);
  }
  return last;
#endif
}

void calendarClockDidChange() {
  uint64_t counter = readSleepCounter();
  sCalendarRebasePending = counter == InvalidSleepCounter;
  if (counter != InvalidSleepCounter) sElapsedClock.rebase(counter);
}

uint64_t interruptTicks() { return sInterruptTicks; }
uint32_t missedDeadlines() { return sMissedDeadlines; }

#if PRIME_G2_EMULATOR
uint64_t testOffset() {
  return sTestOffset;
}

void advanceForTest(uint32_t milliseconds) {
  sTestOffset += milliseconds;
}

bool rolloverSelfTest() {
  uint32_t previous = 0;
  uint64_t high = 0;
  uint64_t a = extendCounter(0xFFFFFFF0, previous, high);
  uint64_t b = extendCounter(0x00000010, previous, high);
  uint64_t c = extendCounter(0xFFFFFFF0, previous, high);
  uint64_t d = extendCounter(0x00000010, previous, high);
  return a == 0x00000000FFFFFFF0ULL && b == 0x0000000100000010ULL &&
    c == 0x00000001FFFFFFF0ULL && d == 0x0000000200000010ULL &&
    a < b && b < c && c < d;
}
#endif

}
}

namespace Ion {
namespace Timing {

static uint32_t ticks() {
  return PrimeG2::reg32(GPT_CNT);
}

uint64_t millis() {
  /* Extend the 32-bit, 3 MHz counter in software. Calling millis at least once
   * per 23 minutes is guaranteed by Upsilon's event loop. */
  static uint32_t previous = 0;
  static uint64_t high = 0;
  uint32_t now = ticks();
  uint64_t result = extendCounter(now, previous, high) /
    (TICKS_PER_MICROSECOND * 1000);
#if PRIME_G2_EMULATOR
  result += PrimeG2::Timing::testOffset();
#endif
  return result;
}

void usleep(uint32_t us) {
#if !PRIME_G2_EMULATOR
  if (sRuntimeDelays) {
    /* The panel and touch power-up sequences already completed with the
     * proven GPT delay path. Runtime event sleeps use a bounded Cortex-A7
     * instruction loop so a later stopped GPT cannot freeze input forever. */
    while (us-- != 0) {
      uint32_t loops = 132;
      __asm volatile(
        "1: subs %0, %0, #1\n"
        "bne 1b"
        : "+r"(loops) :: "cc");
    }
    return;
  }
#endif
  uint32_t start = ticks();
  uint32_t duration = us * TICKS_PER_MICROSECOND;
  while (static_cast<uint32_t>(ticks() - start) < duration) {
    __asm volatile("nop");
  }
}

void msleep(uint32_t ms) {
  while (ms--) {
    usleep(1000);
  }
}

}
}

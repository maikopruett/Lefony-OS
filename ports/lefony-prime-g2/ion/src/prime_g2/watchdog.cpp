#include "watchdog.h"

#include "registers.h"
#include "system.h"

#include <ion/timing.h>

namespace {
constexpr uintptr_t WCR = PrimeG2::WDOG1 + 0x00;
constexpr uintptr_t WSR = PrimeG2::WDOG1 + 0x02;
constexpr uintptr_t WRSR = PrimeG2::WDOG1 + 0x04;
constexpr uintptr_t ReasonMagic = PrimeG2::SNVS + 0x68;
constexpr uintptr_t ReasonValue = PrimeG2::SNVS + 0x6C;
constexpr uint32_t Magic = 0x57444752; // WDGR
constexpr uint32_t BootSuccessMagic = 0x4b4f464c; // LFOK, owned by U-Boot
constexpr uint16_t Enable = 1u << 2;
constexpr uint16_t SuspendInLowPower = 1u << 0;
constexpr uint16_t AssertReset = (1u << 5) | (1u << 4);
constexpr uint16_t TimeoutTwoSeconds = 3u << 8;

bool sEnabled = false;
uint32_t sFeeds = 0;
uint32_t sUnhealthy = 0;
uint64_t sLastFeed = 0;
uint16_t sHardwareResetStatus = 0;
PrimeG2::Watchdog::ResetReason sPreviousReason =
  PrimeG2::Watchdog::ResetReason::None;

void feed() {
  PrimeG2::reg16(WSR) = 0x5555;
  PrimeG2::reg16(WSR) = 0xAAAA;
  PrimeG2::barrier();
  sLastFeed = Ion::Timing::millis();
  sFeeds++;
}

void recordResetReason(PrimeG2::Watchdog::ResetReason reason) {
  /* A healthy pending-slot token has precedence until U-Boot consumes it.
   * Sharing the two battery-backed words must never turn a deliberate reboot
   * into an accidental rollback. */
  if (PrimeG2::reg32(ReasonMagic) == BootSuccessMagic) return;
  PrimeG2::reg32(ReasonValue) = static_cast<uint32_t>(reason);
  PrimeG2::reg32(ReasonMagic) = Magic;
}

[[noreturn]] void resetSystem() {
  /* Ordinary NAND boot also consumes the one-shot U-Boot recovery token. */
  PrimeG2::reg16(WCR) = 0;
  PrimeG2::reg16(WCR) = 0;
  PrimeG2::reg16(WCR) = 0;
  PrimeG2::barrier();
  while (true) asm volatile("wfi");
}
}

namespace PrimeG2 {
namespace Watchdog {

void init() {
  sHardwareResetStatus = reg16(WRSR);
  if (reg32(ReasonMagic) == Magic) {
    uint32_t value = reg32(ReasonValue);
    if (value <= static_cast<uint32_t>(ResetReason::DeliberateTest))
      sPreviousReason = static_cast<ResetReason>(value);
    reg32(ReasonMagic) = 0;
    reg32(ReasonValue) = 0;
  } else if (sHardwareResetStatus & 2u) {
    sPreviousReason = ResetReason::Timeout;
  } else if (sHardwareResetStatus & 1u) {
    sPreviousReason = ResetReason::Software;
  }
  /* Do not arm WDOG1 here. Board::init returns before AppsContainer has
   * constructed the initial UI, while the only health-checked feed path runs
   * from the event loop. On physical hardware that unserviceable startup gap
   * can exceed the two-second timeout and cause a permanent boot loop. The
   * first healthy poll below proves that the feed loop exists before setting
   * WDE, whose i.MX lock semantics then keep the watchdog enabled until reset. */
  /* Keep destructive watchdog resets enabled in the hardware-faithful VM,
   * where reset and restart are part of the automated contract. During
   * physical bring-up, never set the one-way WDE latch ourselves: a later
   * driver fault must remain visible instead of becoming an opaque boot loop.
   * If U-Boot handed us an already-enabled watchdog, recognize and service it
   * rather than incorrectly treating it as disabled. */
#if PRIME_G2_EMULATOR
  sEnabled = false;
#else
  sEnabled = (reg16(WCR) & Enable) != 0;
#endif
  sFeeds = 0;
  sUnhealthy = 0;
  sLastFeed = 0;
#if !PRIME_G2_EMULATOR
  if (sEnabled) feed();
#endif
}

void poll(bool healthy) {
#if !PRIME_G2_EMULATOR
  /* Observation build: retain health telemetry, but do not arm WDOG1. An
   * inherited watchdog is fed even after a health failure so the first real
   * fault remains stationary and inspectable on the screen. */
  if (!healthy) sUnhealthy++;
  if (sEnabled) feed();
  return;
#else
  if (!healthy) {
    sUnhealthy++;
    return;
  }
  if (!sEnabled) {
    reg16(WCR) = TimeoutTwoSeconds | AssertReset | Enable;
    barrier();
    sEnabled = true;
    feed();
    return;
  }
  uint64_t now = Ion::Timing::millis();
  if (now - sLastFeed >= 250) feed();
#endif
}

void noteStorageProgress() {
  /* A completed sector is proof of forward progress, and servicing here keeps
   * a long atomic commit safe without turning the watchdog into an
   * unconditional interrupt feed. */
  if (sEnabled) feed();
}

void prepareForSuspend() {
  if (!sEnabled) return;
  /* WDZST is the i.MX6ULL watchdog's write-once low-power suspend control.
   * Set it before WFI so an inherited U-Boot watchdog cannot reset a device
   * that is legitimately waiting for the power key. */
  reg16(WCR) = reg16(WCR) | SuspendInLowPower;
  barrier();
  feed();
}

void prepareForHang(ResetReason reason) {
  recordResetReason(reason);
  barrier();
}

bool canRequestUBootRecovery() {
  // SNVS LPGPR is the single documented retained word on i.MX6ULL.
  // Never overwrite a pending signed A/B boot confirmation.
  return reg32(ReasonMagic) != BootSuccessMagic &&
    !(reg32(PrimeG2::SNVS) & (1u << 5)) &&
    !(reg32(PrimeG2::SNVS + 0x34) & (1u << 5));
}

bool requestUBootRecovery() {
  if (!canRequestUBootRecovery()) return false;
  // Linux rtc-snvs.c initializes LPPGDR before clearing the power-glitch
  // latch. A latched PGD event continuously zeroizes LPGPR despite unlocked
  // GPR_SL/GPR_HL. Preserve every other status bit and all RTC state.
  if (reg32(PrimeG2::SNVS + 0x4c) & 8u) {
    reg32(PrimeG2::SNVS + 0x64) = 0x41736166;
    barrier();
    reg32(PrimeG2::SNVS + 0x4c) = 8u;
    for (unsigned attempt = 0; attempt < 100; attempt++) {
      if (!(reg32(PrimeG2::SNVS + 0x4c) & 8u)) break;
      Ion::Timing::usleep(100);
    }
    if (reg32(PrimeG2::SNVS + 0x4c) & 8u) return false;
  }
  reg32(ReasonMagic) = 0x3153464c; // LFS1, consumed before U-Boot's sdp 0
  barrier();
  // SNVS LP writes cross the 32 kHz clock domain. DSB alone does not
  // guarantee that the retained word is visible on the first read.
  for (unsigned attempt = 0; attempt < 100; attempt++) {
    if (reg32(ReasonMagic) == 0x3153464c) return true;
    Ion::Timing::usleep(100);
  }
  return false;
}

bool rebootToUBootRecovery() {
  if (System::bootloaderRecoveryVersion() != 1 || !requestUBootRecovery()) return false;
  // Ordinary reset: ROM loads the installed NAND bootloader. No SRC override.
  resetSystem();
}

[[noreturn]] void rebootForUpdate() {
  recordResetReason(ResetReason::Software);
  /* This is an explicit post-commit reset, not the physical observation
   * watchdog. The inactive slot and redundant metadata are already verified. */
  resetSystem();
}

bool enabled() { return sEnabled; }
uint32_t feedCount() { return sFeeds; }
uint32_t unhealthyCount() { return sUnhealthy; }
ResetReason previousResetReason() { return sPreviousReason; }
uint16_t hardwareResetStatus() { return sHardwareResetStatus; }

}
}

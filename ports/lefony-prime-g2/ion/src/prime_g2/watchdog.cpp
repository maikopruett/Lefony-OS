#include "watchdog.h"

#include "registers.h"

#include <ion/timing.h>

namespace {
constexpr uintptr_t WCR = PrimeG2::WDOG1 + 0x00;
constexpr uintptr_t WSR = PrimeG2::WDOG1 + 0x02;
constexpr uintptr_t WRSR = PrimeG2::WDOG1 + 0x04;
constexpr uintptr_t WMCR = PrimeG2::WDOG1 + 0x08;
constexpr uintptr_t ReasonMagic = PrimeG2::SNVS + 0x68;
constexpr uintptr_t ReasonValue = PrimeG2::SNVS + 0x6C;
constexpr uint32_t Magic = 0x57444752; // WDGR
constexpr uint32_t BootSuccessMagic = 0x4b4f464c; // LFOK, owned by U-Boot
constexpr uint16_t Enable = 1u << 2;
constexpr uint16_t SuspendInLowPower = 1u << 0;
constexpr uint16_t AssertReset = (1u << 5) | (1u << 4);
constexpr uint16_t TimeoutTwoSeconds = 3u << 8;
constexpr uintptr_t SRCGPR9 = PrimeG2::SRC + 0x40;
constexpr uintptr_t SRCGPR10 = PrimeG2::SRC + 0x44;
constexpr uint32_t ROMUSBBoot = 0x20;
constexpr uint32_t BootModeEnable = 1u << 28;

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

[[noreturn]] void rebootForUpdate() {
  recordResetReason(ResetReason::Software);
  /* This is an explicit post-commit reset, not the physical observation
   * watchdog. The inactive slot and redundant metadata are already verified. */
  /* WDA/SRS are active-low assertion controls. Clearing SRS requests the
   * immediate software reset even when WDE was already write-once latched. */
  reg16(WCR) = 0;
  barrier();
  while (true) {
    asm volatile("wfi");
  }
}

[[noreturn]] void rebootToROMRecovery() {
  /* Reproduce the Linux command verified on 2026-09-01T00:46:46Z:
   * devmem GPR9 32 0x20; devmem GPR10 32 0x10000000; sleep 1; sysrq b.
   * This is a retained override, not a NAND modification. The installer
   * clears it before requesting a normal boot. Do not touch SNVS here:
   * Linux's command does not depend on our reset-reason bookkeeping. */
  reg32(SRCGPR9) = ROMUSBBoot;
  reg32(SRCGPR10) = BootModeEnable;
  barrier();
  // Flush posted writes with the same register reads as the Linux command.
  uint32_t bootModeReadback = reg32(SRCGPR9);
  uint32_t bootEnableReadback = reg32(SRCGPR10);
  asm volatile("" :: "r"(bootModeReadback), "r"(bootEnableReadback) : "memory");
  Ion::Timing::msleep(1000);
  asm volatile("cpsid if" ::: "memory");
  /* Internal-only Linux restart sequence: WDA stays high, so WDOG_B is not
   * asserted alongside SRS. Avoid the inherited warm-DDR reset handshake.
   * Keep WDOG1 clocked and do not enter WFI: WDZST may already be latched. */
  reg32(PrimeG2::CCM + 0x74) |= 3u << 16; // CCGR3: WDOG1
  reg32(PrimeG2::SRC) &= ~1u;             // SCR: WARM_RESET_ENABLE
  reg16(WMCR) = 0; // imx2_wdt_probe: disable watchdog power-down counter
  barrier();
  constexpr uint16_t internalReset = Enable | (1u << 4); // WDA=1, SRS=0
  reg16(WCR) = internalReset;
  /* imx2_wdt_restart checks hardware WDE after the first write, then pings.
   * Do not use feed(): restart must not depend on event-loop telemetry. */
  if (reg16(WCR) & Enable) {
    reg16(WSR) = 0x5555;
    reg16(WSR) = 0xAAAA;
  }
  reg16(WCR) = internalReset;
  reg16(WCR) = internalReset;
  barrier();
  while (true) {
    asm volatile("nop");
  }
}

bool enabled() { return sEnabled; }
uint32_t feedCount() { return sFeeds; }
uint32_t unhealthyCount() { return sUnhealthy; }
ResetReason previousResetReason() { return sPreviousReason; }
uint16_t hardwareResetStatus() { return sHardwareResetStatus; }

}
}

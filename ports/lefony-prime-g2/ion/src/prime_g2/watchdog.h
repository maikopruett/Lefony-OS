#ifndef ION_PRIME_G2_WATCHDOG_H
#define ION_PRIME_G2_WATCHDOG_H

#include <stdint.h>

namespace PrimeG2 {
namespace Watchdog {

enum class ResetReason : uint32_t {
  None = 0,
  Timeout = 1,
  Software = 2,
  EventLoopDeadlock = 3,
  InterruptStorm = 4,
  DeliberateTest = 5
};

void init();
void poll(bool healthy);
void noteStorageProgress();
void prepareForSuspend();
void prepareForHang(ResetReason reason);
[[noreturn]] void rebootForUpdate();
bool canRequestUBootRecovery();
bool requestUBootRecovery();
// Returns false without resetting if support/mailbox is unavailable.
bool rebootToUBootRecovery();
bool enabled();
uint32_t feedCount();
uint32_t unhealthyCount();
ResetReason previousResetReason();
uint16_t hardwareResetStatus();

}
}

#endif

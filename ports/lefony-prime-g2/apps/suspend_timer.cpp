#include "suspend_timer.h"
#include "apps_container.h"
#include "prime_g2_boot_progress.h"

extern "C" bool prime_g2_update_in_progress();

SuspendTimer::SuspendTimer() :
  Timer(GlobalPreferences::sharedGlobalPreferences()->idleBeforeSuspendSeconds()*1000/Timer::TickDuration)
{
  PrimeG2BootProgress(15);
}

bool SuspendTimer::fire() {
  /* USB update traffic is not an Ion keyboard event, so the ordinary app
   * timer does not see it as activity. Defer auto-suspend while a signed
   * capsule is staged, committed, or waiting for its requested reboot. */
  if (prime_g2_update_in_progress()) return false;
  AppsContainer * container = AppsContainer::sharedAppsContainer();
  container->dispatchEvent(Ion::Events::OnOff);
  return false;
}

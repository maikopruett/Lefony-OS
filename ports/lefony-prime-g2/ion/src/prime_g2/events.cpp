#include "emulator.h"
#include "diagnostics.h"
#include "usb_diagnostics.h"
#include "services.h"
#include "touch.h"
#include "display.h"
#include "development_update.h"
#include "app_management.h"

#include <ion/events.h>

namespace Ion {
namespace Events {

Event getPlatformEvent() {
  static bool firstPhysicalPoll = true;
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) {
    PrimeG2::Display::resetBootProgress();
    PrimeG2::Display::bootProgress(1);
  }
#endif
  PrimeG2::USBDiagnostics::poll();
  PrimeG2::Display::pollRefreshTrial();
  PrimeG2::DevelopmentUpdate::poll();
  PrimeG2::AppManagement::poll();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) PrimeG2::Display::bootProgress(2);
#endif
  PrimeG2::Diagnostics::monitorDisplay();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) PrimeG2::Display::bootProgress(3);
#endif
  PrimeG2::Emulator::poll();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) PrimeG2::Display::bootProgress(4);
#endif
  PrimeG2::Services::poll();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) PrimeG2::Display::bootProgress(5);
#endif
  Event event = PrimeG2::Emulator::popEvent();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) PrimeG2::Display::bootProgress(6);
#endif
  if (event != None) {
    PrimeG2::Services::noteUserActivity();
    return event;
  }
  event = PrimeG2::Touch::pollEvent();
#if !PRIME_G2_EMULATOR
  if (firstPhysicalPoll) {
    PrimeG2::Display::bootProgress(7);
    firstPhysicalPoll = false;
  }
#else
  (void)firstPhysicalPoll;
#endif
  if (event != None) PrimeG2::Services::noteUserActivity();
  return event;
}

void didPressNewKey() {
  PrimeG2::Services::noteUserActivity();
}

const char * Event::text() const {
  if (*this == ExternalText) {
    return PrimeG2::Emulator::eventText();
  }
  return defaultText();
}

}
}

namespace Ion { namespace Touch {
const Event & currentEvent() { return PrimeG2::Touch::currentEvent(); }
}}

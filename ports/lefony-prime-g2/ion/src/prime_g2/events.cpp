#include "emulator.h"
#include "diagnostics.h"
#include "usb_diagnostics.h"
#include "services.h"
#include "touch.h"
#include "display.h"
#include "development_update.h"
#include "app_management.h"
#include "app_channel.h"
#include "native_app.h"
#include "storage_batch.h"
#include "storage_profile.h"

#include <ion/events.h>
#include <ion/keyboard.h>

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
  PrimeG2::Display::pollRefreshTrial();
  PrimeG2::StorageBatch::run(PrimeG2::StorageProfile::ticks,[] {
    return PrimeG2::DevelopmentUpdate::busy() || PrimeG2::AppManagement::needsPolling();
  },[] {
    // Service USB between steps so cancellation/status stays responsive.
    // Each existing state machine still owns writes, verification and commit.
    PrimeG2::USBDiagnostics::poll();
    PrimeG2::DevelopmentUpdate::poll();
    PrimeG2::AppManagement::poll();
  });
  PrimeG2::AppChannel::poll();
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

// Capture every normal scan before the logical event loop selects one key from
// a chord. The stream applies its own 10 ms per-key stability filter; it does
// not alter driver ownership, logical key selection or OS repeat behavior.
void observeNativeKeyboard(Keyboard::State state) {
  uint64_t physical=0;
#define PRIME_G2_KEY(name, evdev, ion, row, col) \
  if(row<8 && col<8 && state.keyDown(Keyboard::Key::ion)) \
    physical|=UINT64_C(1)<<((row*8+col)%64);
#include "keymap.inc"
#undef PRIME_G2_KEY
  PrimeG2::AppManagement::developerKeyObserve(physical);
  PrimeG2::AppManagement::archiveObserve(physical);
  // Home, Apps and the dedicated power GPIO remain OS-owned in every mode.
  physical&=~((UINT64_C(1)<<35)|(UINT64_C(1)<<36));
  uint32_t modifiers=(isShiftActive() || state.keyDown(Keyboard::Key::Shift)?1u:0u) |
    (isAlphaActive() || state.keyDown(Keyboard::Key::Alpha)?2u:0u) | (isLockActive()?4u:0u);
  PrimeG2::NativeApp::observeKeyboard(physical,modifiers);
}

// The shared event loop asks only after polling services, Goodix and normal
// key edges/repeats. This does not count as user activity or a global timer tick.
Event getDeferredPlatformEvent() {
  if(PrimeG2::AppManagement::developerKeyNeedsPresentation()) return NativeKeyApproval;
  if(PrimeG2::AppManagement::archiveNeedsPresentation()) return NativeArchiveApproval;
  return PrimeG2::NativeApp::resumePending()?NativeAppResume:None;
}
bool hasDeferredPlatformWork() {
  return PrimeG2::DevelopmentUpdate::busy() || PrimeG2::AppManagement::needsPolling() || PrimeG2::USBDiagnostics::needsPolling();
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

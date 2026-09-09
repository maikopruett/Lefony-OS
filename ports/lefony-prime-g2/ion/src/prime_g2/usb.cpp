#include "usb_diagnostics.h"

#include <ion/usb.h>

namespace Ion {
namespace USB {

bool isPlugged() { return PrimeG2::USBDiagnostics::plugged(); }
bool isEnumerated() { return PrimeG2::USBDiagnostics::configured(); }
void clearEnumerationInterrupt() {}
void DFU(bool, void *) {
  /* The Prime ROM recovery strap cannot safely be synthesized while running.
   * Keep the diagnostic/recovery device alive; the host installer stages a
   * signed capsule and U-Boot performs the actual slot switch. */
  PrimeG2::USBDiagnostics::init();
}
void enable() { PrimeG2::USBDiagnostics::init(); }
void disable() { PrimeG2::USBDiagnostics::shutdown(); }

}
}

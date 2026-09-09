#include "board.h"
#include "backlight.h"
#include "display.h"
#include "persistence.h"
#include "registers.h"
#include "diagnostics.h"
#include "usb_diagnostics.h"
#include "i2c.h"
#include "services.h"
#include "touch.h"
#include "timing.h"
#include "interrupts.h"
#include "watchdog.h"

#include <ion/backlight.h>

namespace PrimeG2 {

void mux(uint32_t muxOffset, uint32_t padOffset, uint32_t mode,
         uint32_t padControl) {
  reg32(IOMUXC + muxOffset) = mode;
  reg32(IOMUXC + padOffset) = padControl;
}

void gate(uint32_t ccgrOffset, unsigned bit) {
  updateBits(CCM + ccgrOffset, 3u << bit, 3u << bit);
}

namespace Display { void init(); }
namespace Keyboard { void init(); }
namespace Timing { void init(); }
namespace Console { void init(); }

namespace Board {

void init() {
  Timing::init();
  Console::init();
  Diagnostics::init();
  Interrupts::init();
  Timing::enableInterrupt();
  USBDiagnostics::init();
  I2C::init();
  Services::init();
  Touch::init();
  Keyboard::init();
  Display::init();
  /* Configure PWM now, but keep the optical path disabled until the first
   * complete application redraw. This prevents panel-reset and blank-buffer
  * states from appearing as a white cold-boot flash. */
  PrimeG2::Backlight::prepare();
  Diagnostics::record(Diagnostics::BacklightReady);
  Display::bootProgress(2);
  Persistence::init();
  Display::bootProgress(3);
  Watchdog::init();
  /* Preserve the proven GPT-based peripheral power-up timing above, then
   * switch event-loop sleeps to a bounded delay that cannot deadlock input. */
  Timing::enterRuntime();
}

}
}

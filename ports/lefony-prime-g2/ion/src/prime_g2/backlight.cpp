#include "registers.h"
#include "backlight.h"

#include <ion/backlight.h>

namespace {
constexpr uintptr_t PWMCR = PrimeG2::PWM7 + 0x00;
constexpr uintptr_t PWMSAR = PrimeG2::PWM7 + 0x0C;
constexpr uintptr_t PWMPR = PrimeG2::PWM7 + 0x10;

/* Use a known 24 MHz PERCLK and divide by two to fit the requested 5 ms
 * period in the PWM's 16-bit counter. */
constexpr uint32_t PERIOD_CYCLES = 60000;
constexpr uint32_t PWMCR_PRESCALER_2 = 1u << 4;
constexpr uint32_t PWMCR_DOZEEN = 1u << 24;
constexpr uint32_t PWMCR_WAITEN = 1u << 23;
constexpr uint32_t PWMCR_DBGEN = 1u << 22;
constexpr uint32_t PWMCR_CLKSRC_IPG_HIGH = 2u << 16;
constexpr uint32_t PWMCR_EN = 1u;

uint8_t sBrightness = 192;
bool sInitialized = false;
bool sVisible = false;
bool sRevealDeferred = false;

void configureHardware() {
  /* Keep both externally-visible controls low until PWM is configured. */
  PrimeG2::mux(0x01D0, 0x045C, 5, 0x17059);
  PrimeG2::gpioDirection(PrimeG2::GPIO2, 21, true);
  PrimeG2::gpioWrite(PrimeG2::GPIO2, 21, false);

  /* CSI_VSYNC can also be GPIO4_IO19. Drive it low before handing the pad
   * back to PWM7 so a stale peripheral state cannot flash the backlight. */
  PrimeG2::mux(0x01DC, 0x0468, 5, 0x110B0);
  PrimeG2::gpioDirection(PrimeG2::GPIO4, 19, true);
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 19, false);

  /* CSI_VSYNC -> PWM7_OUT. */
  PrimeG2::mux(0x01DC, 0x0468, 6, 0x110B0);
  /* CCM_CSCMR1: select OSC for PERCLK and set its divider to one. */
  PrimeG2::updateBits(PrimeG2::CCM + 0x1C, (1u << 6) | 0x3Fu, 1u << 6);
  PrimeG2::gate(0x80, 30);

  PrimeG2::reg32(PWMCR) = 1u << 3; // software reset
  while (PrimeG2::reg32(PWMCR) & (1u << 3)) {
  }
  PrimeG2::reg32(PWMPR) = PERIOD_CYCLES - 2;
  PrimeG2::reg32(PWMSAR) = (PERIOD_CYCLES * sBrightness) / 255;
  PrimeG2::reg32(PWMCR) = PWMCR_PRESCALER_2 | PWMCR_DOZEEN |
    PWMCR_WAITEN | PWMCR_DBGEN | PWMCR_CLKSRC_IPG_HIGH | PWMCR_EN;
  PrimeG2::barrier();
  sInitialized = true;
  sVisible = false;
}
}

namespace PrimeG2 {
namespace Backlight {

void prepare() {
  /* AppsContainer::initialAppSnapshot() calls Ion::Backlight::init() again.
   * Keep this latch set across that redundant initialization so it cannot
   * bypass the first-frame gate. */
  sRevealDeferred = true;
  configureHardware();
}

void reveal() {
  if (!sInitialized || sVisible) {
    return;
  }
  /* SD1_DATA3 -> GPIO2_IO21, active-high backlight-driver enable. PWM is
   * already running, so enabling the driver cannot expose a stale high pad. */
  PrimeG2::gpioWrite(PrimeG2::GPIO2, 21, true);
  PrimeG2::barrier();
  sVisible = true;
  sRevealDeferred = false;
}

bool isVisible() {
  return sVisible;
}

void hide() {
  PrimeG2::gpioWrite(PrimeG2::GPIO2, 21, false);
  PrimeG2::barrier();
  sVisible = false;
}

}
}

namespace Ion {
namespace Backlight {

void setBrightness(uint8_t brightness) {
  sBrightness = brightness;
  if (!sInitialized) {
    return;
  }
  uint32_t duty = (PERIOD_CYCLES * brightness) / 255;
  PrimeG2::reg32(PWMSAR) = duty;
}

uint8_t brightness() {
  return sBrightness;
}

void init() {
  /* Upstream initializes the backlight again while choosing the first app.
   * Treat that as idempotent: reconfiguring the pad here would blank or flash
   * a splash that is already being scanned out. */
  if (sInitialized) {
    return;
  }
  configureHardware();
  if (!sRevealDeferred) {
    PrimeG2::Backlight::reveal();
  }
}

bool isInitialized() {
  return sInitialized;
}

void shutdown() {
  /* Remove optical output at both controls.  A zero PWM sample alone is not
   * sufficient: once PWM is disabled the muxed pad level is unspecified. */
  PrimeG2::reg32(PWMSAR) = 0;
  PrimeG2::barrier();
  PrimeG2::reg32(PWMCR) = 0;
  PrimeG2::barrier();
  PrimeG2::mux(0x01DC, 0x0468, 5, 0x110B0);
  PrimeG2::gpioDirection(PrimeG2::GPIO4, 19, true);
  PrimeG2::gpioWrite(PrimeG2::GPIO4, 19, false);
  PrimeG2::gpioWrite(PrimeG2::GPIO2, 21, false);
  PrimeG2::barrier();
  sInitialized = false;
  sVisible = false;
  sRevealDeferred = false;
}

}
}

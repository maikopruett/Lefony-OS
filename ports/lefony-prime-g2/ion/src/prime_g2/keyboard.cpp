#include "registers.h"
#include "emulator.h"
#include "services.h"
#include "interrupts.h"
#include "display.h"

#include <ion/keyboard.h>
#include <ion/timing.h>

namespace {
constexpr uintptr_t KPCR = PrimeG2::KPP + 0x00;
constexpr uintptr_t KPSR = PrimeG2::KPP + 0x02;
constexpr uintptr_t KDDR = PrimeG2::KPP + 0x04;
constexpr uintptr_t KPDR = PrimeG2::KPP + 0x06;
constexpr uint16_t ROWS = 0xFE;
constexpr uint16_t COLS = 0xFF;
#if !PRIME_G2_EMULATOR
/* The Prime routes KPP columns 0..7 to GPIO2_IO1,3,...,15 and rows 1..7
 * to GPIO2_IO2,4,...,14. Row 0 is not bonded into the calculator matrix.
 * Scanning these pads as GPIO avoids depending on the KPP state machine while
 * retaining the exact electrical matrix and key map. */
constexpr uint32_t GPIO_COLUMN_MASK = 0x0000AAAAu;

void settleGPIOMatrix() {
  /* Do not use GPT here. The physical trace currently stops inside the first
   * scan, so keep matrix settling independent of every timer and interrupt.
   * This conservative bounded loop is substantially longer than the 5 us
   * minimum used by the Linux KPP driver at the Prime's normal CPU clock. */
  for (volatile unsigned i = 0; i < 8192; i++) {
    __asm volatile("nop");
  }
}
#endif
volatile uint32_t sWakeInterrupts = 0;

void keypadInterrupt() {
  uint16_t status = PrimeG2::reg16(KPSR);
  PrimeG2::reg16(KPSR) = status | 0x0300;
  sWakeInterrupts++;
}

struct MatrixKey {
  uint8_t row;
  uint8_t col;
  Ion::Keyboard::Key key;
};

/* Matrix positions are from imx6ull-14x14-prime.dts. Physical meanings match
 * the existing Linux Prime port, so the physical and emulator backends expose
 * all 51 keys through one authoritative Lefony keyboard map. */
constexpr MatrixKey KeyMap[] = {
#define PRIME_G2_KEY(name, evdev, ion, row, column) \
  {row, column, Ion::Keyboard::Key::ion},
#include "keymap.inc"
#undef PRIME_G2_KEY
};

void scanMatrix(uint8_t state[8]) {
#if PRIME_G2_EMULATOR
  for (unsigned col = 0; col < 8; col++) {
    uint16_t value = PrimeG2::reg16(KPDR);
    PrimeG2::reg16(KPDR) = value | 0xFF00;
    PrimeG2::reg16(KPCR) &= ~(COLS << 8);
    Ion::Timing::usleep(2);
    PrimeG2::reg16(KPCR) |= COLS << 8;
    PrimeG2::reg16(KPDR) &= ~(1u << (8 + col));
    Ion::Timing::usleep(5);
    state[col] = static_cast<uint8_t>(~PrimeG2::reg16(KPDR)) & ROWS;
  }
  PrimeG2::reg16(KPDR) &= 0x00FF;
#else
  /* Keep every unselected column high-impedance. This prevents contention
   * for multi-key chords without needing the KPP controller's open-drain
   * mode. The selected column is driven low and the pulled-up rows are read
   * directly from GPIO2_PSR. */
  static bool firstPhysicalMatrixScan = true;
  PrimeG2::updateBits(PrimeG2::GPIO2 + 0x04, GPIO_COLUMN_MASK, 0);
  if (firstPhysicalMatrixScan) PrimeG2::Display::bootProgress(9);
  for (unsigned col = 0; col < 8; col++) {
    unsigned columnPin = 1 + 2 * col;
    PrimeG2::gpioWrite(PrimeG2::GPIO2, columnPin, false);
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(10);
    PrimeG2::updateBits(PrimeG2::GPIO2 + 0x04, GPIO_COLUMN_MASK,
                        1u << columnPin);
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(11);
    settleGPIOMatrix();
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(12);
    uint32_t pins = PrimeG2::reg32(PrimeG2::GPIO2 + 0x08);
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(13);
    uint8_t rows = 0;
    for (unsigned row = 1; row < 8; row++) {
      if ((pins & (1u << (2 * row))) == 0) rows |= 1u << row;
    }
    state[col] = rows;
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(14);
    PrimeG2::updateBits(PrimeG2::GPIO2 + 0x04, GPIO_COLUMN_MASK, 0);
    if (firstPhysicalMatrixScan && col == 0)
      PrimeG2::Display::bootProgress(15);
  }
  if (firstPhysicalMatrixScan) {
    PrimeG2::Display::bootProgress(16);
    firstPhysicalMatrixScan = false;
  }
#endif
}
}

namespace PrimeG2 {
namespace Keyboard {

void init() {
#if PRIME_G2_EMULATOR
  Emulator::init();
#else
  const uint32_t muxOffsets[] = {
    0x00CC, 0x00D4, 0x00DC, 0x00E4, 0x00EC, 0x00F4, 0x00FC,
    0x00C8, 0x00D0, 0x00D8, 0x00E0, 0x00E8, 0x00F0, 0x00F8, 0x0100
  };
  const uint32_t padOffsets[] = {
    0x0358, 0x0360, 0x0368, 0x0370, 0x0378, 0x0380, 0x0388,
    0x0354, 0x035C, 0x0364, 0x036C, 0x0374, 0x037C, 0x0384, 0x038C
  };
  for (unsigned i = 0; i < 7; i++) {
    mux(muxOffsets[i], padOffsets[i], 5, 0x1B010);
  }
  for (unsigned i = 7; i < 15; i++) {
    mux(muxOffsets[i], padOffsets[i], 5, 0x110B0);
  }
  updateBits(GPIO2 + 0x04, GPIO_COLUMN_MASK, 0);
  clearBits(GPIO2, GPIO_COLUMN_MASK);
#endif
#if PRIME_G2_EMULATOR
  reg16(KPCR) = ROWS | (COLS << 8);
  reg16(KPDR) &= 0x00FF;
  reg16(KDDR) = 0xFF00;
  reg16(KPSR) = 0x030F;
  if (Interrupts::registerHandler(Interrupts::KPP, keypadInterrupt, 0x60)) {
    Interrupts::enable(Interrupts::KPP);
  }
#else
  /* Physical input is synchronously polled through GPIO2. Do not touch KPP
   * MMIO here: the stage-8 hardware trace proved its first scan transaction
   * stops forward progress on this board. */
#endif
}

}
}

namespace Ion {
namespace Keyboard {

State scan() {
#if PRIME_G2_EMULATOR
  PrimeG2::Emulator::poll();
  /* Keyboard scanning is itself an event-loop heartbeat. Some upstream views
   * poll the matrix without asking getPlatformEvent(), so keep power and
   * watchdog servicing on this equally valid forward-progress path. */
  PrimeG2::Services::poll();
#endif
  static bool firstPhysicalScan = true;
#if !PRIME_G2_EMULATOR
  if (firstPhysicalScan) PrimeG2::Display::bootProgress(8);
#endif
  uint8_t matrix[8] = {};
  scanMatrix(matrix);
#if !PRIME_G2_EMULATOR
  if (firstPhysicalScan) PrimeG2::Display::bootProgress(17);
  else PrimeG2::Display::keypadMatrixDiagnostic(matrix);
#endif
  State result;
  for (const MatrixKey & entry : KeyMap) {
    if (entry.row < 8 && entry.col < 8 &&
        (matrix[entry.col] & (1u << entry.row))) {
      result.setKey(entry.key);
    }
  }
#if !PRIME_G2_EMULATOR
  if (firstPhysicalScan) PrimeG2::Display::bootProgress(18);
#endif
#if PRIME_G2_EMULATOR
  /* ON/OFF is a dedicated GPIO on the calculator, not part of KPP. */
  if (PrimeG2::Emulator::keyboardState().keyDown(Key::OnOff)) {
    result.setKey(Key::OnOff);
  }
#else
  if (PrimeG2::Services::onKeyPressed()) result.setKey(Key::OnOff);
  if (firstPhysicalScan) PrimeG2::Display::bootProgress(19);
#endif
#if !PRIME_G2_EMULATOR
  if (firstPhysicalScan) {
    PrimeG2::Display::bootProgress(20);
    firstPhysicalScan = false;
  }
#else
  (void)firstPhysicalScan;
#endif
  return result;
}

}
}

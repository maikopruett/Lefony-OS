#include "diagnostics.h"
#include "registers.h"
#include "services.h"
#include "display.h"

#include <ion/battery.h>
#include <ion/timing.h>

namespace {

PrimeG2::Diagnostics::Event sEvents[PrimeG2::Diagnostics::EventCapacity];
PrimeG2::Diagnostics::Snapshot sSnapshot;
uint32_t sNextSequence = 0;
uint32_t sLastLcdifFault = 0;

uint32_t timestamp() {
  return static_cast<uint32_t>(Ion::Timing::millis());
}

}

namespace PrimeG2 {
namespace Diagnostics {

void init() {
  sNextSequence = 0;
  sLastLcdifFault = 0;
  for (size_t i = 0; i < EventCapacity; i++) {
    sEvents[i] = {0, 0, 0, 0, 0, 0, 0};
  }
  record(BootStart, 0x82000000, 0x8F000000, ProtocolVersion);
}

void record(uint32_t code, uint32_t value0, uint32_t value1,
            uint32_t value2) {
  uint32_t sequence = sNextSequence++;
  Event &entry = sEvents[sequence % EventCapacity];
  entry.magic = EventMagic;
  entry.sequence = sequence;
  entry.timestamp = timestamp();
  entry.code = code;
  entry.value0 = value0;
  entry.value1 = value1;
  entry.value2 = value2;
  PrimeG2::barrier();
}

uint32_t firstSequence() {
  return sNextSequence > EventCapacity ? sNextSequence - EventCapacity : 0;
}

uint32_t nextSequence() {
  return sNextSequence;
}

bool event(uint32_t sequence, Event *result) {
  if (result == nullptr || sequence < firstSequence() ||
      sequence >= sNextSequence) {
    return false;
  }
  const Event &entry = sEvents[sequence % EventCapacity];
  if (entry.magic != EventMagic || entry.sequence != sequence) {
    return false;
  }
  *result = entry;
  return true;
}

void captureSnapshot() {
  uint32_t *w = sSnapshot.words;
  for (size_t i = 0; i < SnapshotWords; i++) w[i] = 0;

  w[0] = SnapshotMagic;
  w[1] = ProtocolVersion;
  w[2] = firstSequence();
  w[3] = nextSequence();

  // Clock tree and gates.
  w[4] = reg32(ANATOP + 0x10); // PLL_USB1
  w[5] = reg32(CCM + 0x18);    // CBCMR / LCDIF PODF
  w[6] = reg32(CCM + 0x38);    // CSCDR2 / LCDIF selectors
  w[7] = reg32(CCM + 0x70);    // CCGR2
  w[8] = reg32(CCM + 0x74);    // CCGR3 / LCDIF
  w[9] = reg32(CCM + 0x80);    // CCGR6 / USB

  // LCDIF registers.
  w[10] = reg32(LCDIF + 0x00);
  w[11] = reg32(LCDIF + 0x10);
  w[12] = reg32(LCDIF + 0x20);
  w[13] = reg32(LCDIF + 0x30);
  w[14] = reg32(LCDIF + 0x40);
  w[15] = reg32(LCDIF + 0x50);
  w[16] = reg32(LCDIF + 0x60);
  w[17] = reg32(LCDIF + 0x70);
  w[18] = reg32(LCDIF + 0x80);
  w[19] = reg32(LCDIF + 0x90);
  w[20] = reg32(LCDIF + 0xA0);
  w[21] = reg32(LCDIF + 0xB0);
  w[22] = reg32(LCDIF + 0x1D0); // DEBUG0

  // LCD and panel control mux/pad/GPIO state.
  w[23] = reg32(IOMUXC + 0x0104); // LCD_CLK mux
  w[24] = reg32(IOMUXC + 0x0114); // LCD_RESET mux
  w[25] = reg32(IOMUXC + 0x01E4); // panel SCK mux
  w[26] = reg32(IOMUXC + 0x01E8); // panel CS mux
  w[27] = reg32(IOMUXC + 0x01EC); // panel MOSI mux
  w[28] = reg32(GPIO3 + 0x00);     // reset output
  w[29] = reg32(GPIO3 + 0x04);     // reset direction
  w[30] = reg32(GPIO4 + 0x00);     // SPI outputs
  w[31] = reg32(GPIO4 + 0x04);     // SPI directions
  w[32] = reg32(PWM7 + 0x00);
  w[33] = reg32(PWM7 + 0x0C);
  w[34] = reg32(PWM7 + 0x10);

  // USB PHY, non-core, and ChipIdea operational state.
  w[35] = reg32(USBPHY1 + 0x00);
  w[36] = reg32(USBPHY1 + 0x10);
  w[37] = reg32(USBPHY1 + 0x30);
  w[38] = reg32(USBNC + 0x00);
  w[39] = reg32(USBNC + 0x18);
  w[40] = reg32(USBOTG1 + 0x140); // USBCMD
  w[41] = reg32(USBOTG1 + 0x144); // USBSTS
  w[42] = reg32(USBOTG1 + 0x148); // USBINTR
  w[43] = reg32(USBOTG1 + 0x154); // DEVICEADDR
  w[44] = reg32(USBOTG1 + 0x158); // ENDPTLISTADDR
  w[45] = reg32(USBOTG1 + 0x184); // PORTSC1
  w[46] = reg32(USBOTG1 + 0x1A4); // OTGSC
  w[47] = reg32(USBOTG1 + 0x1A8); // USBMODE
  w[48] = reg32(USBOTG1 + 0x1AC); // ENDPTSETUPSTAT
  w[49] = reg32(USBOTG1 + 0x1B0); // ENDPTPRIME
  w[50] = reg32(USBOTG1 + 0x1B4); // ENDPTFLUSH
  w[51] = reg32(USBOTG1 + 0x1B8); // ENDPTSTAT
  w[52] = reg32(USBOTG1 + 0x1BC); // ENDPTCOMPLETE
  w[53] = reg32(USBOTG1 + 0x1C0); // ENDPTCTRL0

  // The framebuffer's first pixels distinguish an untouched white clear from
  // a rendered Upsilon frame without transferring all 307,200 bytes.
  const uint32_t *framebuffer = Display::drawingBuffer();
  w[54] = framebuffer[0];
  w[55] = framebuffer[1];
  w[56] = framebuffer[320];
  w[57] = framebuffer[320 * 120 + 160];
  w[58] = framebuffer[320 * 239 + 319];

  // Battery/charger evidence is intentionally raw as well as interpreted.
  // This lets physical reports distinguish an ADC problem, a charger-mode
  // problem, and an ordinary charge-phase transition without a working UI.
  w[59] = Services::batteryRawADC() |
    (static_cast<uint32_t>(Services::vbusSense()) << 16) |
    (static_cast<uint32_t>(Services::chargerInterruptOK()) << 24);
  w[60] = Services::batteryMillivolts() |
    (static_cast<uint32_t>(Services::pmicAvailable()) << 30) |
    (static_cast<uint32_t>(Services::batteryTelemetryFresh()) << 31);
  w[61] = Services::batteryPercent() |
    (static_cast<uint32_t>(Services::chargerState() & 0x0F) << 8) |
    (static_cast<uint32_t>(Services::batterySenseState() & 0x07) << 12) |
    (static_cast<uint32_t>(Services::externalPowerPresent()) << 16) |
    (static_cast<uint32_t>(Ion::Battery::isCharging()) << 17) |
    (static_cast<uint32_t>(Services::batteryPresent()) << 18) |
    (static_cast<uint32_t>(Services::batteryFull()) << 19) |
    (static_cast<uint32_t>(Services::chargerFaultOrSuspended()) << 20) |
    (static_cast<uint32_t>(Services::batteryEstimateIsCalibrated()) << 21) |
    (static_cast<uint32_t>(Services::chargerConfigured()) << 22) |
    (static_cast<uint32_t>(Services::chargerOperation()) << 24);
  w[62] = reg32(0x02198000 + 0x14); // ADC1 CFG
  w[63] = reg32(0x02198000 + 0x18); // ADC1 GC
  PrimeG2::barrier();
}

const Snapshot &snapshot() {
  return sSnapshot;
}

void monitorDisplay() {
  uint32_t ctrl = reg32(LCDIF + 0x00);
  uint32_t ctrl1 = reg32(LCDIF + 0x10);
  uint32_t fault = ctrl1 & ((1u << 11) | (1u << 10));
  if (!(ctrl & 1u)) fault |= 1u << 31;
  if (fault != 0 && fault != sLastLcdifFault) {
    sLastLcdifFault = fault;
    record(LcdifFault, fault, ctrl, reg32(LCDIF + 0x1D0));
  }
}

}
}

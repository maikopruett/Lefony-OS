#include "battery_adc.h"

#include "registers.h"

namespace {

constexpr uintptr_t ADC1 = 0x02198000;
constexpr uintptr_t ADC_HC0 = ADC1 + 0x00;
constexpr uintptr_t ADC_HS = ADC1 + 0x08;
constexpr uintptr_t ADC_R0 = ADC1 + 0x0C;
constexpr uintptr_t ADC_CFG = ADC1 + 0x14;
constexpr uintptr_t ADC_GC = ADC1 + 0x18;
constexpr uintptr_t ADC_GS = ADC1 + 0x1C;
constexpr uintptr_t ADC_OFS = ADC1 + 0x24;

constexpr uint32_t ADCChannelBattery = 1;
constexpr uint32_t ADCConversionComplete = 1u;
constexpr uint32_t ADCCalibrate = 1u << 7;
constexpr uint32_t ADCCalibrationFailed = 1u << 1;
constexpr uint32_t ADCClockGate = 3u << 16;
constexpr unsigned ADCTimeout = 1000000;

bool sInitialized = false;
bool sConversionPending = false;

bool waitUntilClear(uintptr_t reg, uint32_t mask) {
  for (unsigned i = 0; i < ADCTimeout; i++) {
    if ((PrimeG2::reg32(reg) & mask) == 0) return true;
  }
  return false;
}

}

namespace PrimeG2 {
namespace BatteryADC {

bool init() {
  /* The shipping Prime G2 firmware routes GPIO1_IO01 to ADC1_IN1 using the
   * ordinary GPIO mux plus a high-impedance pad.  No output is ever driven. */
  mux(0x0060, 0x02EC, 5, 0x90);
  gpioDirection(GPIO1, 1, false);

  /* ADC1 is the CCGR1 gate at bits 17:16.  These register values mirror the
   * calibrated 12-bit, long-sample, hardware-average setup used by HP. */
  updateBits(CCM + 0x6C, ADCClockGate, ADCClockGate);
  reg32(ADC_CFG) = 0xC3F3;
  reg32(ADC_GC) = 0x20;
  reg32(ADC_OFS) = 0;
  reg32(ADC_GC) = reg32(ADC_GC) | ADCCalibrate;
  if (!waitUntilClear(ADC_GC, ADCCalibrate)) {
    sInitialized = false;
    sConversionPending = false;
    return false;
  }
  if (reg32(ADC_GS) & ADCCalibrationFailed) {
    reg32(ADC_GS) = ADCCalibrationFailed;
    sInitialized = false;
    sConversionPending = false;
    return false;
  }
  sInitialized = true;
  sConversionPending = false;
  return true;
}

bool readRaw(uint16_t *raw) {
  if (!sInitialized || raw == nullptr) return false;
  /* Starting a conversion and spinning for completion blocked the main event
   * loop on physical Prime G2 hardware long enough for the watchdog to reset
   * the calculator. Start it on one service poll and collect it on a later
   * poll instead. A missing completion bit now leaves battery telemetry stale
   * without ever stalling the UI or watchdog service. */
  if (!sConversionPending) {
    reg32(ADC_HC0) = ADCChannelBattery;
    sConversionPending = true;
    return false;
  }
  if ((reg32(ADC_HS) & ADCConversionComplete) == 0) return false;
  *raw = static_cast<uint16_t>(reg32(ADC_R0) & 0x0FFF);
  sConversionPending = false;
  return true;
}

uint16_t millivoltsForRaw(uint16_t raw) {
  /* Empirical Prime G2 divider calibration recovered from HP's G2 firmware.
   * The two offsets correct the slope discontinuity around ADC code 208. */
  uint32_t millivolts = ((0x5A3Cu * raw) / 5u) >> 8;
  millivolts += raw >= 0xD0 ? 0x2E : 0x16;
  return static_cast<uint16_t>(millivolts);
}

bool isInitialized() { return sInitialized; }
bool conversionPending() { return sConversionPending; }

}
}

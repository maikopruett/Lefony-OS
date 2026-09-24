#include "services.h"

#include "battery_adc.h"
#include "display.h"
#include "i2c.h"
#include "interrupts.h"
#include "persistence.h"
#include "registers.h"
#include "touch.h"
#include "timing.h"
#include "usb_diagnostics.h"
#include "development_update.h"
#include "watchdog.h"

#include <ion.h>
#include <ion/backlight.h>
#include <ion/led.h>
#include <ion/power.h>
#include <ion/timing.h>
#include <stddef.h>

extern "C" char _stack_bottom;
extern "C" char _stack_main_top;

namespace Ion { namespace Backlight { bool isInitialized(); } }

namespace {
constexpr uint32_t StackGuardValue = 0x51ACCA7E;
constexpr size_t StackGuardWords = 256;
constexpr uint8_t PF1550Address = 0x08;
constexpr uint8_t PFDeviceId = 0x00;
constexpr uint8_t PFOnKeySense = 0x26;
constexpr uint8_t PFOnKeyStatus = 0x24;
constexpr uint8_t PFOnKeyMask = 0x25;
constexpr uint8_t PFLdo1Voltage = 0x4C;
constexpr uint8_t PFLdo1Control = 0x4D;
constexpr uint8_t PFPwrCtrl1 = 0x59;
constexpr uint8_t PFPwrCtrl3 = 0x5B;
constexpr uint8_t PFChargerInterrupt = 0x80;
constexpr uint8_t PFChargerInterruptOK = 0x84;
constexpr uint8_t PFChargerSense = 0x87;
constexpr uint8_t PFBatterySense = 0x88;
constexpr uint8_t PFVbusSense = 0x86;
constexpr uint8_t PFChargerOperation = 0x89;
constexpr uint8_t PFChargerModeMask = 0x03;
constexpr uint8_t PFChargerBatteryOn = 0x02;
constexpr uint8_t PFVbusUndervoltage = 1u << 2;
constexpr uint8_t PFVbusIn2System = 1u << 3;
constexpr uint8_t PFVbusValid = 1u << 5;
constexpr uint8_t PFChargeEndOfCharge = 3;
constexpr uint8_t PFChargeDone = 4;
constexpr uint8_t PFChargeTimerFault = 6;
constexpr uint8_t PFChargeThermistorSuspend = 7;
constexpr uint8_t PFChargeBatteryOvervoltage = 9;
constexpr uint8_t PFChargeThermalShutdown = 10;
constexpr uint8_t PFChargeLinearOnly = 12;
constexpr uint8_t PFBatteryNotDetected = 6;
constexpr uintptr_t SNVSLPCR = PrimeG2::SNVS + 0x38;
constexpr uintptr_t SNVSHPSR = PrimeG2::SNVS + 0x14;
constexpr uintptr_t SNVSLPSR = PrimeG2::SNVS + 0x4C;
constexpr uintptr_t SNVSLPSRTCMR = PrimeG2::SNVS + 0x50;
constexpr uintptr_t SNVSLPSRTCLR = PrimeG2::SNVS + 0x54;
constexpr uint32_t SNVSRtcEnable = 1u;
constexpr uint32_t SNVSButton = 1u << 6;
constexpr uint32_t SNVSPowerOff = 1u << 6;
constexpr uint32_t SNVSDumbPMICEnable = 1u << 5;
constexpr uint32_t SNVSPowerButtonStatus = 1u << 18;
constexpr uint8_t PFOnKeyEvents = 0x3F;
constexpr uint8_t PFPwrOnResetEnable = 1u << 4;
constexpr uint8_t PFRestartEnable = 1u << 5;
constexpr uint8_t PFOnKeyResetEnable = 1u << 7;
constexpr uint8_t PFGotoCoreOff = 1u << 1;
constexpr uint8_t PFLdo1VoltageMask = 0x1F;
constexpr uint8_t PFLdo1Voltage3300mV = 0x1F;
constexpr uint8_t PFLdo1Enable = 1u << 0;
constexpr uint8_t PFLdo1StandbyEnable = 1u << 1;
constexpr uint8_t PFLdo1OperatingModeMask = 0x0F;
constexpr unsigned PFInterruptPin = 4;

Ion::Battery::Charge sBatteryLevel = Ion::Battery::Charge::SOMEWHERE_INBETWEEN;
uint16_t sBatteryMillivolts = 0;
uint16_t sBatteryRawADC = 0;
uint8_t sBatteryPercent = 50;
bool sBatteryCharging = false;
bool sBatteryCalibrated = false;
uint64_t sBatteryEstimateAt = 0;
uint8_t sChargerState = 8;
uint8_t sBatterySenseState = 0;
uint8_t sVbusSense = PFVbusUndervoltage | PFVbusIn2System;
uint8_t sChargerInterruptOK = 0;
bool sExternalPowerPresent = false;
bool sBatteryPresent = true;
bool sBatteryFull = false;
bool sChargerFaultOrSuspended = false;
bool sPMICAvailable = false;
bool sBatteryTelemetryFresh = false;
uint64_t sNextBatteryPoll = 0;
Ion::RTC::Mode sRTCMode = Ion::RTC::Mode::Disabled;
Ion::RTC::DateTime sEmulatedRTC = {0, 0, 12, 30, 8, 2026, 6};
uint64_t sRTCSetAt = 0;
bool sRTCUserSet = false;
KDColor sLEDColor = KDColorBlack;
uint16_t sLEDBlinkPeriod = 0;
uint8_t sLEDBlinkDutyPercent = 0;
bool sPowerSuspended = false;
bool sPowerOff = false;
uint32_t sSuspendCount = 0;
uintptr_t sStackPaintTop = 0;
uint64_t sIdleStartedAt = 0;
uint64_t sIdleTestOffset = 0;
uint8_t sIdleBrightness = 192;
bool sIdleDimmed = false;
volatile bool sPowerWakeRequested = false;
bool sPFPowerOffConfigured = false;
bool sLCDSupplyReady = false;
bool sChargerConfigured = false;
uint8_t sChargerOperation = 0;
uint16_t sBatterySamples[10] = {};
uint8_t sBatterySampleCount = 0;
uint8_t sBatterySampleIndex = 0;
uint64_t sNextBatterySample = 0;
uint64_t sNextBatteryPercentChange = 0;

constexpr uint32_t IdleDimMilliseconds = 45000;
constexpr uint32_t IdleSuspendMilliseconds = 55000;
constexpr uint32_t BatterySampleMilliseconds = 100;
constexpr uint32_t BatteryPercentHoldMilliseconds = 30000;
constexpr uint16_t BatteryCriticalMillivolts = 3551;

void snvsPowerKeyInterrupt() {
  uint32_t status = PrimeG2::reg32(SNVSLPSR);
  if (status & SNVSPowerButtonStatus) {
    PrimeG2::reg32(SNVSLPSR) = SNVSPowerButtonStatus;
    sPowerWakeRequested = true;
  }
}

void pf1550Interrupt() {
  /* The PF1550 IRQ is level-low until its I2C status is acknowledged.  Mask
   * the GPIO source immediately; status is read and acknowledged after WFI,
   * outside interrupt context. */
  PrimeG2::clearBits(PrimeG2::GPIO5 + 0x14, 1u << PFInterruptPin);
  PrimeG2::reg32(PrimeG2::GPIO5 + 0x18) = 1u << PFInterruptPin;
  sPowerWakeRequested = true;
}

bool updatePF1550(uint8_t reg, uint8_t mask, uint8_t value) {
  for (unsigned attempt = 0; attempt < 3; attempt++) {
    uint8_t before = 0;
    if (!PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address, reg, &before, 1))
      continue;
    uint8_t after = (before & ~mask) | (value & mask);
    if (!PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, reg, &after, 1))
      continue;
    uint8_t verified = 0;
    if (PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address, reg, &verified, 1) &&
        (verified & mask) == (after & mask)) return true;
  }
  return false;
}

bool configureLCDSupply() {
  /* The Prime DT connects lcd-supply to PF1550 LDO1 at 3.3 V. Linux's
   * regulator core programs this during probe; native firmware must not
   * inherit that state because a battery-cold PF1550 reloads its OTP state.
   * Program the voltage before enabling the rail, preserve the load-switch
   * selection bit, and keep the supply available through normal standby. */
  bool voltage = updatePF1550(PFLdo1Voltage, PFLdo1VoltageMask,
                              PFLdo1Voltage3300mV);
  bool control = updatePF1550(
    PFLdo1Control, PFLdo1OperatingModeMask,
    PFLdo1Enable | PFLdo1StandbyEnable);
  if (voltage && control) {
    /* Allow the panel rail to settle before reset, SPI or backlight activity. */
    Ion::Timing::msleep(10);
  }
  uint8_t verifiedVoltage = 0;
  uint8_t verifiedControl = 0;
  sLCDSupplyReady = voltage && control &&
    PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address, PFLdo1Voltage,
                        &verifiedVoltage, 1) &&
    PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address, PFLdo1Control,
                        &verifiedControl, 1) &&
    (verifiedVoltage & PFLdo1VoltageMask) == PFLdo1Voltage3300mV &&
    (verifiedControl & (PFLdo1Enable | PFLdo1StandbyEnable)) ==
      (PFLdo1Enable | PFLdo1StandbyEnable);
  return sLCDSupplyReady;
}

bool configurePF1550Charger() {
  /* PF1550 reset mode 1 powers the system from VBUS but deliberately leaves
   * cell charging disabled.  This is why merely classifying CHG_SNS could
   * never fix the battery-installed case.  Linux now writes mode 2 for
   * battery products; do the same direct register write while leaving HP's
   * OTP current, voltage, input-limit and thermal settings untouched. */
  for (unsigned attempt = 0; attempt < 3; attempt++) {
    uint8_t mode = PFChargerBatteryOn;
    if (!PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address,
                              PFChargerOperation, &mode, 1)) continue;
    uint8_t verified = 0;
    if (PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address,
                            PFChargerOperation, &verified, 1) &&
        (verified & PFChargerModeMask) == PFChargerBatteryOn) {
      sChargerOperation = verified;
      sChargerConfigured = true;
      return true;
    }
  }
  sChargerConfigured = false;
  return false;
}

bool configurePF1550ForPowerOff() {
  /* Preserve OTP-loaded fields. PWRCTRL1 makes both hardware long-press
   * escape paths valid; GOTO_CORE_OFF makes ONKEY a defined wake transition
   * after SNVS drops PMIC_ON_REQ. Never set GOTO_SHIP: that would require a
   * charger or battery reattach rather than the power button. */
  bool controls = updatePF1550(
    PFPwrCtrl1,
    PFPwrOnResetEnable | PFRestartEnable | PFOnKeyResetEnable,
    PFPwrOnResetEnable | PFRestartEnable | PFOnKeyResetEnable);
  bool coreOff = updatePF1550(PFPwrCtrl3, PFGotoCoreOff, PFGotoCoreOff);
  sPFPowerOffConfigured = controls && coreOff;
  return sPFPowerOffConfigured;
}

void acknowledgePF1550Interrupt(uint8_t reg) {
  uint8_t status = 0;
  if (PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address, reg, &status, 1) &&
      status != 0) {
    /* PF1550 interrupt status registers are write-one-to-clear. */
    PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, reg, &status, 1);
  }
}

void armPowerWakeSources() {
  sPowerWakeRequested = false;
  PrimeG2::reg32(SNVSLPSR) = SNVSPowerButtonStatus;

  uint8_t clear = PFOnKeyEvents;
  uint8_t unmask = 0;
  acknowledgePF1550Interrupt(PFChargerInterrupt);
  PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, PFOnKeyStatus, &clear, 1);
  PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, PFOnKeyMask, &unmask, 1);
  PrimeG2::reg32(PrimeG2::GPIO5 + 0x18) = 1u << PFInterruptPin;
  PrimeG2::setBits(PrimeG2::GPIO5 + 0x14, 1u << PFInterruptPin);
  PrimeG2::Interrupts::enable(PrimeG2::Interrupts::GPIO5Low);
}

void disarmPF1550Wake() {
  PrimeG2::Interrupts::disable(PrimeG2::Interrupts::GPIO5Low);
  PrimeG2::clearBits(PrimeG2::GPIO5 + 0x14, 1u << PFInterruptPin);
  acknowledgePF1550Interrupt(PFChargerInterrupt);
  uint8_t status = 0;
  uint8_t mask = PFOnKeyEvents;
  if (PrimeG2::I2C::read8(PrimeG2::I2C1, PF1550Address,
                          PFOnKeyStatus, &status, 1) && status)
    PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address,
                         PFOnKeyStatus, &status, 1);
  PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, PFOnKeyMask, &mask, 1);
  PrimeG2::reg32(PrimeG2::GPIO5 + 0x18) = 1u << PFInterruptPin;
}

uint64_t idleClock() {
  uint64_t now = Ion::Timing::millis();
#if PRIME_G2_EMULATOR
  /* TIME ADVANCE drives RTC, battery, and rollover tests.  Idle time has its
   * own offset so those unrelated tests do not manufacture user inactivity. */
  now -= PrimeG2::Timing::testOffset();
#endif
  return now + sIdleTestOffset;
}

uint64_t batteryClock() {
  return PrimeG2::Timing::elapsedMillis();
}

bool leapYear(int year) {
  return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}

int daysInMonth(int month, int year) {
  constexpr uint8_t Days[] = {31, 28, 31, 30, 31, 30,
                              31, 31, 30, 31, 30, 31};
  return Days[month - 1] + (month == 2 && leapYear(year));
}

bool validDateTime(const Ion::RTC::DateTime &value) {
  return value.tm_year >= 1970 && value.tm_year <= 2399 &&
    value.tm_mon >= 1 && value.tm_mon <= 12 && value.tm_mday >= 1 &&
    value.tm_mday <= daysInMonth(value.tm_mon, value.tm_year) &&
    value.tm_hour >= 0 && value.tm_hour < 24 && value.tm_min >= 0 &&
    value.tm_min < 60 && value.tm_sec >= 0 && value.tm_sec < 60 &&
    value.tm_wday >= 0 && value.tm_wday < 7;
}

/* Gregorian civil-date conversion, with day zero at 1970-01-01. */
int64_t daysFromCivil(int year, unsigned month, unsigned day) {
  year -= month <= 2;
  int era = (year >= 0 ? year : year - 399) / 400;
  unsigned yoe = static_cast<unsigned>(year - era * 400);
  unsigned adjustedMonth = month + (month > 2 ? -3 : 9);
  unsigned doy = (153 * adjustedMonth + 2) / 5 + day - 1;
  unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + static_cast<int>(doe) - 719468;
}

uint32_t secondsFromDateTime(const Ion::RTC::DateTime &value) {
  int64_t days = daysFromCivil(value.tm_year, value.tm_mon, value.tm_mday);
  return static_cast<uint32_t>(days * 86400 + value.tm_hour * 3600 +
                               value.tm_min * 60 + value.tm_sec);
}

Ion::RTC::DateTime dateTimeFromSeconds(uint32_t seconds) {
  uint32_t daySeconds = seconds % 86400;
  int64_t z = seconds / 86400;
  int weekday = static_cast<int>((z + 3) % 7); // Monday=0
  z += 719468;
  int era = (z >= 0 ? z : z - 146096) / 146097;
  unsigned doe = static_cast<unsigned>(z - era * 146097);
  unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  int year = static_cast<int>(yoe) + era * 400;
  unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  unsigned mp = (5 * doy + 2) / 153;
  unsigned day = doy - (153 * mp + 2) / 5 + 1;
  unsigned month = mp + (mp < 10 ? 3 : -9);
  year += month <= 2;
  return {static_cast<int>(daySeconds % 60),
          static_cast<int>((daySeconds / 60) % 60),
          static_cast<int>(daySeconds / 3600), static_cast<int>(day),
          static_cast<int>(month), year, weekday};
}

uint32_t readSNVSSeconds(bool *stable = nullptr) {
  if (stable) *stable = false;
  uint64_t first = 0;
  for (unsigned attempts = 0; attempts < 100; attempts++) {
    uint64_t high = PrimeG2::reg32(SNVSLPSRTCMR);
    uint64_t low = PrimeG2::reg32(SNVSLPSRTCLR);
    first = (high << 32) | low;
    uint64_t second =
      (static_cast<uint64_t>(PrimeG2::reg32(SNVSLPSRTCMR)) << 32) |
      PrimeG2::reg32(SNVSLPSRTCLR);
    if (first == second) { if (stable) *stable = true; break; }
  }
  return static_cast<uint32_t>(first >> 15);
}

void writeSNVSSeconds(uint32_t seconds) {
  PrimeG2::Timing::elapsedMillis(); // account for time before changing RTC
  PrimeG2::clearBits(SNVSLPCR, SNVSRtcEnable);
  uint64_t counter = static_cast<uint64_t>(seconds) << 15;
  PrimeG2::reg32(SNVSLPSRTCLR) = static_cast<uint32_t>(counter);
  PrimeG2::reg32(SNVSLPSRTCMR) = static_cast<uint32_t>(counter >> 32);
  PrimeG2::barrier();
  PrimeG2::Timing::calendarClockDidChange();
  PrimeG2::setBits(SNVSLPCR, SNVSRtcEnable);
}

Ion::RTC::DateTime emulatedDateTime() {
  uint32_t elapsed = static_cast<uint32_t>(
    (Ion::Timing::millis() - sRTCSetAt) / 1000);
  return dateTimeFromSeconds(secondsFromDateTime(sEmulatedRTC) + elapsed);
}

uint8_t primePercentForMillivolts(uint16_t millivolts) {
  /* These are the five calibrated groups used by the shipping Prime G2 OS.
   * Reporting only those groups is more honest than manufacturing precision
   * which a voltage-only gauge cannot provide under changing load. */
  if (millivolts < 3501) return 0;
  if (millivolts < 3664) return 25;
  if (millivolts < 3700) return 50;
  if (millivolts < 3863) return 75;
  return 100;
}

void sampleBatteryVoltage() {
  if (!sBatteryPresent) {
    sBatterySampleCount = 0;
    sBatterySampleIndex = 0;
    sBatteryCalibrated = false;
    return;
  }

  uint16_t raw = 0;
  if (!PrimeG2::BatteryADC::readRaw(&raw)) return;
  uint16_t millivolts = PrimeG2::BatteryADC::millivoltsForRaw(raw);
  if (raw < 128 || raw > 300 || millivolts < 2500 || millivolts > 5000) {
    /* A disconnected/floating divider must never become a plausible percent. */
    sBatteryCalibrated = false;
    return;
  }
  sBatteryRawADC = raw;

  sBatterySamples[sBatterySampleIndex] = millivolts;
  sBatterySampleIndex = (sBatterySampleIndex + 1) % 10;
  if (sBatterySampleCount < 10) sBatterySampleCount++;
  if (sBatterySampleCount < 10) return;

  uint32_t total = 0;
  uint16_t low = sBatterySamples[0];
  uint16_t high = sBatterySamples[0];
  for (unsigned i = 0; i < 10; i++) {
    uint16_t sample = sBatterySamples[i];
    total += sample;
    if (sample < low) low = sample;
    if (sample > high) high = sample;
  }
  sBatteryMillivolts = static_cast<uint16_t>((total - low - high) / 8);
  bool firstEstimate = !sBatteryCalibrated;
  sBatteryCalibrated = true;

  uint8_t nextPercent = primePercentForMillivolts(sBatteryMillivolts);
  uint64_t now = batteryClock();
  sBatteryEstimateAt = now;
  if (sBatteryFull) {
    nextPercent = 100;
  }
  if (firstEstimate || nextPercent == sBatteryPercent ||
      now >= sNextBatteryPercentChange) {
    if (nextPercent != sBatteryPercent)
      sNextBatteryPercentChange = now + BatteryPercentHoldMilliseconds;
    sBatteryPercent = nextPercent;
  }
  if (sBatteryPercent == 100) {
    sBatteryLevel = Ion::Battery::Charge::FULL;
  } else if (sBatteryMillivolts < BatteryCriticalMillivolts) {
    sBatteryLevel = Ion::Battery::Charge::LOW;
  } else {
    sBatteryLevel = Ion::Battery::Charge::SOMEWHERE_INBETWEEN;
  }
}

void revokeChargingTelemetry() {
  /* Charging is a live power-input claim, not a value that is safe to cache.
   * Revoke it before every poll so an unplug or a failed VBUS read cannot
   * leave the previous charging result visible indefinitely. */
  sPMICAvailable = false;
  sBatteryTelemetryFresh = false;
  sExternalPowerPresent = false;
  sBatteryCharging = false;
  sBatteryFull = false;
}

void refreshBattery() {
  revokeChargingTelemetry();
  if (!sChargerConfigured) configurePF1550Charger();
  uint8_t id = 0, charger = 0, battery = 0, vbus = 0, operation = 0;
  uint8_t interruptOK = 0;

  /* Read each dimension independently.  The former chained expression
   * stopped at the first error and retained every old result, including a
   * true charging flag.  VBUS goes first because it is the safety-critical
   * input for the title-bar charging symbol. */
  bool vbusRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFVbusSense, &vbus, 1);
  bool chargerRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFChargerSense, &charger, 1);
  bool batteryRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFBatterySense, &battery, 1);
  bool operationRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFChargerOperation, &operation, 1);
  bool interruptOKRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFChargerInterruptOK, &interruptOK, 1);
  bool idRead = PrimeG2::I2C::read8(
    PrimeG2::I2C1, PF1550Address, PFDeviceId, &id, 1);

  sPMICAvailable = vbusRead || chargerRead || batteryRead || operationRead ||
    interruptOKRead || idRead;
  if (vbusRead) {
    sVbusSense = vbus;
    sExternalPowerPresent = (vbus & PFVbusValid) != 0 &&
      (vbus & PFVbusUndervoltage) == 0;
  }
  if (chargerRead) {
    sChargerState = charger & 0x0F;
    sChargerFaultOrSuspended =
      sChargerState == PFChargeTimerFault ||
      sChargerState == PFChargeThermistorSuspend ||
      sChargerState == PFChargeBatteryOvervoltage ||
      sChargerState == PFChargeThermalShutdown ||
      sChargerState == PFChargeLinearOnly;
  } else {
    sChargerFaultOrSuspended = false;
  }
  if (batteryRead) {
    sBatterySenseState = battery & 0x07;
    sBatteryPresent = sBatterySenseState != PFBatteryNotDetected;
  }
  if (interruptOKRead) sChargerInterruptOK = interruptOK;
  if (operationRead) {
    sChargerOperation = operation;
    sChargerConfigured =
      (operation & PFChargerModeMask) == PFChargerBatteryOn;
    if (!sChargerConfigured) {
      /* Recover if the PMIC was reset independently while the CPU remained up. */
      configurePF1550Charger();
    }
  }

  sBatteryTelemetryFresh = vbusRead && chargerRead && batteryRead;
  sBatteryFull = chargerRead && batteryRead && sBatteryPresent &&
    sChargerState == PFChargeDone;

  /* CHG_SNS 0..3 are active charge phases, but state 0 is also what the
   * PF1550 reports while attempting to precharge an absent/zero-volt cell.
   * Require valid VBUS and a detected battery so an empty battery bay is not
   * presented as actively charging. */
  sBatteryCharging = sBatteryTelemetryFresh && sExternalPowerPresent &&
    sBatteryPresent && sChargerState <= PFChargeEndOfCharge;
  if (!chargerRead || !batteryRead) return;
  if (sBatteryFull) {
    sBatteryLevel = Ion::Battery::Charge::FULL;
    sBatteryPercent = 100;
  } else if (!sBatteryPresent) {
    sBatteryLevel = Ion::Battery::Charge::EMPTY;
    sBatteryPercent = 0;
    sBatteryCalibrated = false;
  } else if (!sBatteryCalibrated) {
    /* Charger status is only a startup fallback. Once the ADC estimate is
     * valid, preserve its icon and percentage between samples. In particular,
     * CHG_SNS=8 after unplug means charger off, not a half-full battery. */
    if (sBatterySenseState == 1) {
      sBatteryLevel = Ion::Battery::Charge::LOW;
      sBatteryPercent = 0;
    } else {
      sBatteryLevel = Ion::Battery::Charge::SOMEWHERE_INBETWEEN;
      sBatteryPercent = sChargerState == PFChargeEndOfCharge ? 90 : 50;
    }
  }
  (void)id;
  (void)PFOnKeySense;
}
}

extern "C" void prime_g2_stack_guard_init() {
  uint32_t *guard = reinterpret_cast<uint32_t *>(&_stack_bottom);
  uintptr_t stackPointer;
  __asm volatile("mov %0, sp" : "=r"(stackPointer));
  constexpr uintptr_t LiveFrameMargin = 4096;
  sStackPaintTop = (stackPointer - LiveFrameMargin) & ~uintptr_t(3);
  uint32_t *end = reinterpret_cast<uint32_t *>(sStackPaintTop);
  while (guard < end) *guard++ = StackGuardValue;
}

namespace PrimeG2 {
namespace Services {

void init() {
  setBits(SNVSLPCR, SNVSRtcEnable | SNVSDumbPMICEnable);
  reg32(SNVSLPSR) = SNVSPowerButtonStatus;
  if (Interrupts::registerHandler(Interrupts::SNVSPowerKey,
                                  snvsPowerKeyInterrupt, 0x20))
    Interrupts::enable(Interrupts::SNVSPowerKey);

  /* Captured Prime DT: SNVS_TAMPER4 -> GPIO5_IO04, falling-edge PF1550 IRQ. */
  mux(0x002C, 0x02B8, 5, 0x80000000);
  gpioDirection(GPIO5, PFInterruptPin, false);
  clearBits(GPIO5 + 0x1C, 1u << PFInterruptPin);
  updateBits(GPIO5 + 0x0C, 3u << (PFInterruptPin * 2),
             3u << (PFInterruptPin * 2));
  clearBits(GPIO5 + 0x14, 1u << PFInterruptPin);
  reg32(GPIO5 + 0x18) = 1u << PFInterruptPin;
  Interrupts::registerHandler(Interrupts::GPIO5Low, pf1550Interrupt, 0x20);
  configureLCDSupply();
  configurePF1550Charger();
  refreshBattery();
  PrimeG2::BatteryADC::init();
  sNextBatteryPoll = batteryClock() + 1000;
  sNextBatterySample = batteryClock();
  sIdleStartedAt = idleClock();
  sIdleTestOffset = 0;
  sIdleDimmed = false;
}

void poll() {
  if (USBDiagnostics::externalPowerConnected()) noteUserActivity();
  uint64_t batteryNow = batteryClock();
  if (batteryNow >= sNextBatterySample) {
    sampleBatteryVoltage();
    sNextBatterySample = batteryNow + BatterySampleMilliseconds;
  }
  if (batteryNow >= sNextBatteryPoll) {
    refreshBattery();
    sNextBatteryPoll = batteryNow + 1000;
  }
  if (!sPowerSuspended && !sPowerOff) {
    uint64_t idleNow = idleClock();
    uint64_t idleMilliseconds = idleNow - sIdleStartedAt;
    if (idleMilliseconds >= IdleSuspendMilliseconds) {
      Ion::Power::suspend(false);
    } else if (!sIdleDimmed && idleMilliseconds >= IdleDimMilliseconds) {
      sIdleBrightness = Ion::Backlight::brightness();
      Ion::Backlight::setBrightness(15);
      sIdleDimmed = true;
    }
  }
  Watchdog::poll(Display::guardsIntact() && Ion::stackSafe() &&
                 !Persistence::commitInProgress());
}

void noteVerificationProgress() {
  // Catalog authentication also runs during Board::init, before the regular
  // event loop exists. Only that loop may first arm the watchdog.
  if(Watchdog::enabled())
    Watchdog::poll(Display::guardsIntact() && Ion::stackSafe() &&
                   !Persistence::commitInProgress());
}

void noteUserActivity() {
  sIdleStartedAt = idleClock();
  if (sIdleDimmed && !sPowerSuspended && !sPowerOff) {
    Ion::Backlight::setBrightness(sIdleBrightness);
  }
  sIdleDimmed = false;
}

bool advanceIdleForTest(uint32_t milliseconds) {
#if PRIME_G2_EMULATOR
  if (milliseconds > 3600000) return false;
  sIdleTestOffset += milliseconds;
  poll();
  return true;
#else
  (void)milliseconds;
  return false;
#endif
}

bool onKeyPressed() { return (reg32(SNVSHPSR) & SNVSButton) != 0; }

bool setBatteryForTest(Ion::Battery::Charge level, uint16_t millivolts,
                       bool charging) {
#if PRIME_G2_EMULATOR
  if (static_cast<unsigned>(level) > 3 || millivolts < 2500 ||
      millivolts > 5000) return false;
  uint8_t state[] = {static_cast<uint8_t>(level),
                     static_cast<uint8_t>(millivolts),
                     static_cast<uint8_t>(millivolts >> 8),
                     static_cast<uint8_t>(charging)};
  if (!I2C::write8(I2C1, PF1550Address, 0xF0, state, sizeof(state)))
    return false;
  refreshBattery();
  sBatterySampleCount = 0;
  sBatterySampleIndex = 0;
  sBatteryCalibrated = false;
  /* readRaw() is deliberately two-phase: start, then collect. */
  for (unsigned i = 0; i < 20; i++) sampleBatteryVoltage();
  return true;
#else
  return false;
#endif
}

bool setChargerStateForTest(bool externalPower, uint8_t chargerState,
                            uint8_t batterySenseState) {
#if PRIME_G2_EMULATOR
  if (chargerState > 0x0F || batterySenseState > 0x07) return false;
  uint8_t vbus = externalPower ? PFVbusValid :
    PFVbusUndervoltage | PFVbusIn2System;
  if (!I2C::write8(I2C1, PF1550Address, PFVbusSense, &vbus, 1) ||
      !I2C::write8(I2C1, PF1550Address, PFChargerSense, &chargerState, 1) ||
      !I2C::write8(I2C1, PF1550Address, PFBatterySense,
                   &batterySenseState, 1)) return false;
  refreshBattery();
  return true;
#else
  (void)externalPower;
  (void)chargerState;
  (void)batterySenseState;
  return false;
#endif
}

bool failBatteryRefreshForTest() {
#if PRIME_G2_EMULATOR
  /* Exercise exactly the fail-closed transition used at the start of a real
   * refresh whose PF1550 reads do not complete. */
  revokeChargingTelemetry();
  return true;
#else
  return false;
#endif
}

uint16_t batteryMillivolts() { return sBatteryMillivolts; }
uint16_t batteryRawADC() { return sBatteryRawADC; }
uint8_t batteryPercent() { return sBatteryPercent; }
bool batteryEstimateIsCalibrated() { return sBatteryCalibrated; }
uint32_t batteryEstimateAgeMillis() {
  uint64_t now = batteryClock();
  if (!sBatteryCalibrated || !sBatteryPresent || now < sBatteryEstimateAt) return 0xffffffffu;
  uint64_t age = now - sBatteryEstimateAt;
  return age < 0xffffffffu ? static_cast<uint32_t>(age) : 0xffffffffu;
}
bool calendarSnapshot(Ion::RTC::DateTime *value, bool *setThisBoot) {
  if (!value || !setThisBoot) return false;
  *setThisBoot = false;
#if PRIME_G2_EMULATOR
  *value = emulatedDateTime();
#else
  bool stable = false;
  uint32_t seconds = readSNVSSeconds(&stable);
  if (!stable) return false;
  *value = dateTimeFromSeconds(seconds);
#endif
  if (!validDateTime(*value)) return false;
  *setThisBoot = sRTCUserSet;
  return true;
}
uint8_t chargerState() { return sChargerState; }
uint8_t batterySenseState() { return sBatterySenseState; }
uint8_t vbusSense() { return sVbusSense; }
uint8_t chargerInterruptOK() { return sChargerInterruptOK; }
uint8_t chargerOperation() { return sChargerOperation; }
bool chargerConfigured() { return sChargerConfigured; }
bool pmicAvailable() { return sPMICAvailable; }
bool batteryTelemetryFresh() { return sBatteryTelemetryFresh; }
bool externalPowerPresent() { return sExternalPowerPresent; }
bool batteryPresent() { return sBatteryPresent; }
bool batteryFull() { return sBatteryFull; }
bool chargerFaultOrSuspended() { return sChargerFaultOrSuspended; }

bool setRTCForTest(Ion::RTC::DateTime value) {
#if PRIME_G2_EMULATOR
  if (!validDateTime(value)) return false;
  sEmulatedRTC = value;
  sRTCSetAt = Ion::Timing::millis();
  sRTCUserSet = daysFromCivil(value.tm_year, value.tm_mon, value.tm_mday) * 86400 +
    value.tm_hour * 3600 + value.tm_min * 60 + value.tm_sec <= 0xffffffffu;
  return true;
#else
  (void)value;
  return false;
#endif
}

uint16_t ledColor() { return static_cast<uint16_t>(sLEDColor); }
uint16_t ledBlinkPeriod() { return sLEDBlinkPeriod; }
uint8_t ledBlinkDutyPercent() { return sLEDBlinkDutyPercent; }
bool powerSuspended() { return sPowerSuspended; }
bool powerOffForTest() { return sPowerOff; }
uint32_t suspendCount() { return sSuspendCount; }

uint32_t powerHardwareState() {
  return (Display::isInStandby() ? 1u : 0u) |
    (Ion::Backlight::isInitialized() ? 2u : 0u) |
    (sPFPowerOffConfigured ? 4u : 0u);
}

uint16_t pmicPowerControl() {
  uint8_t pwr1 = 0, pwr3 = 0;
  I2C::read8(I2C1, PF1550Address, PFPwrCtrl1, &pwr1, 1);
  I2C::read8(I2C1, PF1550Address, PFPwrCtrl3, &pwr3, 1);
  return static_cast<uint16_t>(pwr1) << 8 | pwr3;
}

uint16_t lcdSupplyControl() {
  uint8_t voltage = 0;
  uint8_t control = 0;
  if (!I2C::read8(I2C1, PF1550Address, PFLdo1Voltage, &voltage, 1) ||
      !I2C::read8(I2C1, PF1550Address, PFLdo1Control, &control, 1))
    return 0;
  return static_cast<uint16_t>(voltage) << 8 | control;
}

uint32_t stackHighWaterBytes() {
  const uint32_t *cursor = reinterpret_cast<const uint32_t *>(&_stack_bottom);
  const uint32_t *end = reinterpret_cast<const uint32_t *>(sStackPaintTop);
  while (cursor < end && *cursor == StackGuardValue) cursor++;
  uintptr_t lowWater = cursor == end ? sStackPaintTop :
    reinterpret_cast<uintptr_t>(cursor);
  return reinterpret_cast<uintptr_t>(&_stack_main_top) - lowWater;
}

uint32_t stackCapacityBytes() {
  return reinterpret_cast<uintptr_t>(&_stack_main_top) -
    reinterpret_cast<uintptr_t>(&_stack_bottom);
}

bool resumeForTest() {
#if PRIME_G2_EMULATOR
  if (sPowerOff) return false;
  if (!sPowerSuspended) return true;
  uint8_t powerState = 0;
  I2C::write8(I2C1, PF1550Address, 0xF4, &powerState, 1);
  Display::resume();
  Ion::Backlight::init();
  USBDiagnostics::init();
  Touch::init();
  sPowerSuspended = false;
  noteUserActivity();
  return true;
#else
  return false;
#endif
}

bool buttonForTest(uint32_t durationMilliseconds) {
#if PRIME_G2_EMULATOR
  if (durationMilliseconds == 0 || durationMilliseconds > 60000 || sPowerOff)
    return false;
  if (durationMilliseconds < 2000) {
    if (sPowerSuspended) return resumeForTest();
    Ion::Power::suspend(false);
    return true;
  }
  /* A 2 s hold is an orderly off; 8 s and longer models PF1550 forced-off.
   * The latter intentionally skips persistence, matching the hardware escape
   * hatch rather than pretending it is a clean shutdown. */
  if (durationMilliseconds < 8000) Persistence::commit();
  configurePF1550ForPowerOff();
  USBDiagnostics::shutdown();
  Ion::Backlight::shutdown();
  Display::shutdown();
  uint8_t powerState = 2;
  I2C::write8(I2C1, PF1550Address, 0xF4, &powerState, 1);
  sPowerSuspended = false;
  sPowerOff = true;
  return true;
#else
  (void)durationMilliseconds;
  return false;
#endif
}

void advancePowerForTest(uint32_t milliseconds) {
#if PRIME_G2_EMULATOR
  uint8_t value[] = {static_cast<uint8_t>(milliseconds),
                     static_cast<uint8_t>(milliseconds >> 8),
                     static_cast<uint8_t>(milliseconds >> 16),
                     static_cast<uint8_t>(milliseconds >> 24)};
  I2C::write8(I2C1, PF1550Address, 0xF5, value, sizeof(value));
  refreshBattery();
  for (unsigned i = 0; i < 10; i++) sampleBatteryVoltage();
#else
  (void)milliseconds;
#endif
}

[[noreturn]] void powerOff() {
  Persistence::commit();
  configurePF1550ForPowerOff();
  USBDiagnostics::shutdown();
  Ion::Backlight::shutdown();
  Display::shutdown();
  /* Preserve the OTP/security/RTC policy already present in LPCR. TOP is a
   * command bit, not a complete register value. A full-register 0x61 write
   * was the previous bug: it silently discarded every unrelated LPCR field. */
  setBits(SNVSLPCR, SNVSRtcEnable | SNVSDumbPMICEnable | SNVSPowerOff);
  barrier();
  while (true) __asm volatile("wfi");
}

}
}

extern "C" unsigned prime_g2_battery_percent() {
  return PrimeG2::Services::batteryPercent();
}

extern "C" bool prime_g2_battery_percent_calibrated() {
  return PrimeG2::Services::batteryEstimateIsCalibrated();
}

extern "C" bool prime_g2_external_power_present() {
  return PrimeG2::Services::externalPowerPresent();
}

extern "C" bool prime_g2_battery_present() {
  return PrimeG2::Services::batteryPresent();
}

extern "C" bool prime_g2_battery_full() {
  return PrimeG2::Services::batteryFull();
}

extern "C" bool prime_g2_charger_fault_or_suspended() {
  return PrimeG2::Services::chargerFaultOrSuspended();
}

namespace Ion {
namespace Battery {
bool isCharging() { return sBatteryCharging; }
Charge level() { return sBatteryLevel; }
float voltage() { return sBatteryMillivolts / 1000.0f; }
}

namespace RTC {
void setMode(Mode mode) {
  sRTCMode = mode;
#if !PRIME_G2_EMULATOR
  /* The Settings toggle controls clock visibility, not the shared hardware
   * timebase. Battery sampling must keep running with the clock hidden. */
  PrimeG2::setBits(SNVSLPCR, SNVSRtcEnable);
#endif
}
Mode mode() { return sRTCMode; }
void setDateTime(DateTime value) {
  if (!validDateTime(value)) return;
  // The existing calendar stores uint32 seconds. Do not call a wrapped date
  // trustworthy merely because its original civil fields passed validation.
  sRTCUserSet = daysFromCivil(value.tm_year, value.tm_mon, value.tm_mday) * 86400 +
    value.tm_hour * 3600 + value.tm_min * 60 + value.tm_sec <= 0xffffffffu;
#if PRIME_G2_EMULATOR
  sEmulatedRTC = value;
  sRTCSetAt = Timing::millis();
#else
  writeSNVSSeconds(secondsFromDateTime(value));
#endif
}
DateTime dateTime() {
#if PRIME_G2_EMULATOR
  return emulatedDateTime();
#else
  return dateTimeFromSeconds(readSNVSSeconds());
#endif
}
}

namespace LED {
KDColor getColor() { return sLEDColor; }
void setColor(KDColor color) { sLEDColor = color; }
void setBlinking(uint16_t period, float dutyCycle) {
  sLEDBlinkPeriod = period;
  if (dutyCycle < 0.0f) dutyCycle = 0.0f;
  if (dutyCycle > 1.0f) dutyCycle = 1.0f;
  sLEDBlinkDutyPercent = static_cast<uint8_t>(dutyCycle * 100.0f + 0.5f);
}
KDColor updateColorWithPlugAndCharge() {
  setColor(Battery::isCharging() ? KDColorOrange : KDColorGreen);
  return sLEDColor;
}
}

namespace Power {
void suspend(bool checkIfOnOffKeyReleased) {
  if (PrimeG2::USBDiagnostics::externalPowerConnected() ||
      PrimeG2::DevelopmentUpdate::busy()) return;
  if (sPowerSuspended || sPowerOff) return;
  PrimeG2::Persistence::commit();
  PrimeG2::USBDiagnostics::shutdown();
  Ion::Backlight::shutdown();
  PrimeG2::Display::shutdown();
  sPowerSuspended = true;
  sSuspendCount++;
#if PRIME_G2_EMULATOR
  (void)checkIfOnOffKeyReleased;
  uint8_t powerState = 1;
  PrimeG2::I2C::write8(PrimeG2::I2C1, PF1550Address, 0xF4,
                       &powerState, 1);
#else
  /* Consume the OFF release before arming either edge-sensitive source. */
  if (checkIfOnOffKeyReleased) {
    while (PrimeG2::Services::onKeyPressed()) {
      PrimeG2::Watchdog::poll(true);
      Ion::Timing::usleep(2000);
    }
  }

  PrimeG2::Watchdog::prepareForSuspend();
  armPowerWakeSources();
  PrimeG2::Interrupts::disable(PrimeG2::Interrupts::GPT1);
  PrimeG2::barrier();
  while (!sPowerWakeRequested) {
    /* IRQs remain enabled. SNVS SPI4 or the PF1550 GPIO5 falling edge is the
     * only enabled runtime wake source after GPT1 is masked. */
    __asm volatile("wfi" ::: "memory");
  }
  PrimeG2::Interrupts::enable(PrimeG2::Interrupts::GPT1);
  disarmPF1550Wake();

  /* Consume the wake release so the application never sees the same press as
   * a second OFF request. */
  while (PrimeG2::Services::onKeyPressed()) {
    PrimeG2::Watchdog::poll(true);
    Ion::Timing::usleep(2000);
  }

  PrimeG2::Display::resume();
  Ion::Backlight::init();
  PrimeG2::USBDiagnostics::init();
  PrimeG2::Touch::init();
  sPowerSuspended = false;
  PrimeG2::Services::noteUserActivity();
#endif
}
void standby() {
  /* Upsilon uses standby for the non-returning, reset-on-next-power-on path.
   * Normal OFF remains suspend(); do not collapse these two power states. */
  PrimeG2::Services::powerOff();
}
}

const char *serialNumber() { return "LEFONY-PRIME-G2"; }
const char *pcbVersion() { return "G2-UNVERIFIED"; }
const char *fccId() { return "UNAVAILABLE"; }
bool stackSafe() {
  uintptr_t stackPointer;
  __asm volatile("mov %0, sp" : "=r"(stackPointer));
  constexpr uintptr_t SafetyMargin = 4096;
  if (stackPointer < reinterpret_cast<uintptr_t>(&_stack_bottom) + SafetyMargin ||
      stackPointer > reinterpret_cast<uintptr_t>(&_stack_main_top)) return false;
  const uint32_t *guard = reinterpret_cast<const uint32_t *>(&_stack_bottom);
  for (size_t i = 0; i < StackGuardWords; i++) {
    if (guard[i] != StackGuardValue) return false;
  }
  return true;
}
}

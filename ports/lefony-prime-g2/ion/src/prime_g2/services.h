#ifndef ION_PRIME_G2_SERVICES_H
#define ION_PRIME_G2_SERVICES_H

#include <ion/battery.h>
#include <ion/rtc.h>
#include <stdint.h>

namespace PrimeG2 {
namespace Services {
void init();
void poll();
void noteUserActivity();
bool advanceIdleForTest(uint32_t milliseconds);
bool onKeyPressed();
bool setBatteryForTest(Ion::Battery::Charge level, uint16_t millivolts,
                       bool charging);
bool setChargerStateForTest(bool externalPower, uint8_t chargerState,
                            uint8_t batterySenseState);
bool failBatteryRefreshForTest();
uint16_t batteryMillivolts();
uint16_t batteryRawADC();
uint8_t batteryPercent();
bool batteryEstimateIsCalibrated();
uint8_t chargerState();
uint8_t batterySenseState();
uint8_t vbusSense();
uint8_t chargerInterruptOK();
uint8_t chargerOperation();
bool chargerConfigured();
bool pmicAvailable();
bool batteryTelemetryFresh();
bool externalPowerPresent();
bool batteryPresent();
bool batteryFull();
bool chargerFaultOrSuspended();
bool setRTCForTest(Ion::RTC::DateTime value);
uint16_t ledColor();
uint16_t ledBlinkPeriod();
uint8_t ledBlinkDutyPercent();
bool powerSuspended();
bool powerOffForTest();
uint32_t suspendCount();
uint32_t powerHardwareState();
uint16_t pmicPowerControl();
uint16_t lcdSupplyControl();
uint32_t stackHighWaterBytes();
uint32_t stackCapacityBytes();
bool resumeForTest();
bool buttonForTest(uint32_t durationMilliseconds);
void advancePowerForTest(uint32_t milliseconds);
[[noreturn]] void powerOff();
}
}

#endif

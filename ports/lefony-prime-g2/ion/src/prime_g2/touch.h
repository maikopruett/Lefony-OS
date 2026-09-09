#ifndef ION_PRIME_G2_TOUCH_H
#define ION_PRIME_G2_TOUCH_H

#include <ion/events.h>
#include <ion/touch.h>
#include <stdint.h>

namespace PrimeG2 {
namespace Touch {

void init();
const Ion::Touch::Event & currentEvent();
Ion::Events::Event pollEvent();
bool available();
uint16_t productId();
uint16_t lastX();
uint16_t lastY();
uint32_t lastDuration();
uint32_t sequence();
bool lastReportCancelled();
#if PRIME_G2_EMULATOR
bool injectForTest(uint16_t startX, uint16_t startY, uint16_t endX,
                   uint16_t endY, uint16_t durationMilliseconds = 50);
bool injectFrameForTest(const uint8_t * report);
bool setFaultForTest(uint8_t mode);
bool reinitializeForTest();
#endif

}
}

#endif

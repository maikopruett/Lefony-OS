#include "touch.h"
#include "touch_tracker.h"

#include "i2c.h"
#include "registers.h"

#include <ion/timing.h>
#include <string.h>

namespace {
constexpr uint8_t Address = 0x14;
constexpr uint16_t ProductIdRegister = 0x8140;
constexpr uint16_t CoordinateRegister = 0x814E;
constexpr uint16_t EmulatorIngress = 0x9000;
constexpr uint16_t EmulatorFault = 0x90F0;

bool sAvailable = false;
uint16_t sProductId = 0;
PrimeG2::TouchTracker sTracker;
uint32_t sStartAt = 0;
uint32_t sLastDuration = 0;
uint32_t sSequence = 0;
}

namespace PrimeG2 {
namespace Touch {

void init() {
  sTracker = TouchTracker();
  /* UART3_RX/TX pads are GPIO1_IO25 (INT) and GPIO1_IO24 (RESET) on the
   * captured board. The emulator control UART is internal and does not use
   * these external pads. Follow the Goodix address-select reset sequence. */
  mux(0x00A4, 0x0330, 5, 0x17059);
  mux(0x00A8, 0x0334, 5, 0x1B0B0);
  gpioDirection(GPIO1, 24, true);
  gpioDirection(GPIO1, 25, true);
  gpioWrite(GPIO1, 24, false);
  Ion::Timing::msleep(20);
  gpioWrite(GPIO1, 25, true); // selects 7-bit address 0x14
  Ion::Timing::usleep(200);
  gpioWrite(GPIO1, 24, true);
  Ion::Timing::msleep(7);
  gpioDirection(GPIO1, 24, false);
  gpioWrite(GPIO1, 25, false);
  Ion::Timing::msleep(50);
  gpioDirection(GPIO1, 25, false);

  uint8_t id[6] = {};
  sAvailable = I2C::read16(I2C2, Address, ProductIdRegister, id, sizeof(id));
  if (sAvailable && id[0] >= '0' && id[0] <= '9' &&
      id[1] >= '0' && id[1] <= '9' && id[2] >= '0' && id[2] <= '9' &&
      id[3] >= '0' && id[3] <= '9') {
    sProductId = static_cast<uint16_t>((id[0] - '0') * 1000 +
      (id[1] - '0') * 100 + (id[2] - '0') * 10 + id[3] - '0');
  } else {
    sAvailable = false;
  }
}

Ion::Events::Event pollEvent() {
  if (!sAvailable) return Ion::Events::None;
  uint8_t report[17] = {};
  if (!I2C::read16(I2C2, Address, CoordinateRegister, report, 9))
    return sTracker.cancel() ? Ion::Events::Touch : Ion::Events::None;
  if (!(report[0] & 0x80)) return Ion::Events::None;
  uint8_t contacts = report[0] & 0x0F;
  // Each Goodix contact occupies eight bytes. Read the second contact before
  // acknowledging the report so both coordinates belong to the same frame.
  if (contacts == 2 && !I2C::read16(I2C2, Address, CoordinateRegister + 9, report + 9, 8))
    return sTracker.cancel() ? Ion::Events::Touch : Ion::Events::None;
  uint16_t x = report[2] | static_cast<uint16_t>(report[3]) << 8;
  uint16_t y = report[4] | static_cast<uint16_t>(report[5]) << 8;
  uint8_t clear = 0;
  if (!I2C::write16(I2C2, Address, CoordinateRegister, &clear, 1))
    return sTracker.cancel() ? Ion::Events::Touch : Ion::Events::None;
  sSequence++;
  uint16_t x2 = report[10] | static_cast<uint16_t>(report[11]) << 8;
  uint16_t y2 = report[12] | static_cast<uint16_t>(report[13]) << 8;
  if (!sTracker.report(contacts, report[1] & 0x0F, x, y,
                       report[9] & 0x0F, x2, y2)) return Ion::Events::None;
  if (sTracker.event().phase == Ion::Touch::Phase::Down)
    sStartAt = static_cast<uint32_t>(Ion::Timing::millis());
  if (sTracker.event().phase == Ion::Touch::Phase::Up)
    sLastDuration = static_cast<uint32_t>(Ion::Timing::millis()) - sStartAt;
  return Ion::Events::Touch;
}

const Ion::Touch::Event & currentEvent() { return sTracker.event(); }
bool available() { return sAvailable; }
uint16_t productId() { return sProductId; }
uint16_t lastX() { return sTracker.event().x; }
uint16_t lastY() { return sTracker.event().y; }
uint32_t lastDuration() { return sLastDuration; }
uint32_t sequence() { return sSequence; }
bool lastReportCancelled() { return sTracker.cancelled(); }

#if PRIME_G2_EMULATOR
bool injectForTest(uint16_t startX, uint16_t startY, uint16_t endX,
                   uint16_t endY, uint16_t durationMilliseconds) {
  uint8_t payload[] = {
    static_cast<uint8_t>(startX), static_cast<uint8_t>(startX >> 8),
    static_cast<uint8_t>(startY), static_cast<uint8_t>(startY >> 8),
    static_cast<uint8_t>(endX), static_cast<uint8_t>(endX >> 8),
    static_cast<uint8_t>(endY), static_cast<uint8_t>(endY >> 8),
    static_cast<uint8_t>(durationMilliseconds),
    static_cast<uint8_t>(durationMilliseconds >> 8),
  };
  return I2C::write16(I2C2, Address, EmulatorIngress, payload,
                      sizeof(payload));
}

bool injectFrameForTest(const uint8_t * report) {
  return I2C::write16(I2C2, Address, 0x9020, report, 17);
}

bool setFaultForTest(uint8_t mode) {
  if (mode > 3) return false;
  return I2C::write16(I2C2, Address, EmulatorFault, &mode, 1);
}

bool reinitializeForTest() {
  init();
  return sAvailable;
}
#endif

}
}

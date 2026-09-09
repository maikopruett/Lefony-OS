#include "i2c.h"

#include "registers.h"

#include <ion/timing.h>

namespace {
constexpr uintptr_t IADR = 0x00;
constexpr uintptr_t IFDR = 0x04;
constexpr uintptr_t I2CR = 0x08;
constexpr uintptr_t I2SR = 0x0C;
constexpr uintptr_t I2DR = 0x10;

constexpr uint8_t IEN = 0x80;
constexpr uint8_t MSTA = 0x20;
constexpr uint8_t MTX = 0x10;
constexpr uint8_t TXAK = 0x08;
constexpr uint8_t RSTA = 0x04;
constexpr uint8_t IBB = 0x20;
constexpr uint8_t IAL = 0x10;
constexpr uint8_t IIF = 0x02;
constexpr uint8_t RXAK = 0x01;

volatile uint8_t &reg8(uintptr_t address) {
  return *reinterpret_cast<volatile uint8_t *>(address);
}

void reset(uintptr_t base) {
  reg8(base + I2CR) = 0;
  reg8(base + I2SR) = 0;
  /* 66 MHz IPG / 640 is approximately 103 kHz. */
  reg8(base + IFDR) = 0x15;
  reg8(base + I2CR) = IEN;
}

bool waitStatus(uintptr_t base, uint8_t mask, bool set,
                unsigned attempts = 2000) {
  while (attempts--) {
    if ((reg8(base + I2SR) & mask) == (set ? mask : 0)) return true;
    Ion::Timing::usleep(2);
  }
  return false;
}

void stop(uintptr_t base) {
  reg8(base + I2CR) = IEN;
  waitStatus(base, IBB, false);
  reg8(base + I2SR) = 0;
}

bool waitByte(uintptr_t base, bool requireAck = true) {
  if (!waitStatus(base, IIF, true)) return false;
  uint8_t status = reg8(base + I2SR);
  reg8(base + I2SR) = 0;
  if (status & IAL) return false;
  return !requireAck || !(status & RXAK);
}

bool begin(uintptr_t base, uint8_t address, bool read) {
  if (!waitStatus(base, IBB, false)) {
    reset(base);
    if (!waitStatus(base, IBB, false)) return false;
  }
  reg8(base + I2CR) = IEN | MSTA | MTX;
  if (!waitStatus(base, IBB, true)) return false;
  reg8(base + I2DR) = static_cast<uint8_t>((address << 1) | read);
  return waitByte(base);
}

bool restartRead(uintptr_t base, uint8_t address) {
  reg8(base + I2CR) = IEN | MSTA | MTX | RSTA;
  reg8(base + I2DR) = static_cast<uint8_t>((address << 1) | 1);
  return waitByte(base);
}

bool send(uintptr_t base, const uint8_t *data, size_t length) {
  for (size_t i = 0; i < length; i++) {
    reg8(base + I2DR) = data[i];
    if (!waitByte(base)) return false;
  }
  return true;
}

bool receive(uintptr_t base, uint8_t *data, size_t length) {
  if (length == 0) return true;
  reg8(base + I2CR) = IEN | MSTA | (length == 1 ? TXAK : 0);
  volatile uint8_t dummy = reg8(base + I2DR); // start first receive cycle
  (void)dummy;
  for (size_t i = 0; i < length; i++) {
    if (!waitByte(base, false)) return false;
    if (i + 2 == length) reg8(base + I2CR) = IEN | MSTA | TXAK;
    if (i + 1 == length) reg8(base + I2CR) = IEN;
    data[i] = reg8(base + I2DR);
  }
  if (!waitStatus(base, IBB, false)) return false;
  return true;
}

bool writeRegister(uintptr_t base, uint8_t address, const uint8_t *prefix,
                   size_t prefixLength, const uint8_t *data, size_t length) {
  if (!begin(base, address, false) || !send(base, prefix, prefixLength) ||
      !send(base, data, length)) {
    stop(base);
    return false;
  }
  stop(base);
  return true;
}

bool readRegister(uintptr_t base, uint8_t address, const uint8_t *prefix,
                  size_t prefixLength, uint8_t *data, size_t length) {
  if (!begin(base, address, false) || !send(base, prefix, prefixLength) ||
      !restartRead(base, address) || !receive(base, data, length)) {
    stop(base);
    return false;
  }
  return true;
}
}

namespace PrimeG2 {
namespace I2C {

void init() {
  /* UART4_TX/RX -> I2C1 and UART5_TX/RX -> I2C2. SION keeps the input path
   * enabled for open-drain arbitration, matching the captured device tree. */
  mux(0x00B4, 0x0340, 0x12, 0x1B8B0);
  mux(0x00B8, 0x0344, 0x12, 0x1B8B0);
  reg32(IOMUXC + 0x05A4) = 1;
  reg32(IOMUXC + 0x05A8) = 2;
  mux(0x00BC, 0x0348, 0x12, 0x1B8B0);
  mux(0x00C0, 0x034C, 0x12, 0x1B8B0);
  reg32(IOMUXC + 0x05AC) = 2;
  reg32(IOMUXC + 0x05B0) = 2;
  gate(0x70, 6);
  gate(0x70, 8);
  reset(I2C1);
  reset(I2C2);
}

bool read8(uintptr_t base, uint8_t address, uint8_t reg, uint8_t *data,
           size_t length) {
  return readRegister(base, address, &reg, 1, data, length);
}

bool write8(uintptr_t base, uint8_t address, uint8_t reg,
            const uint8_t *data, size_t length) {
  return writeRegister(base, address, &reg, 1, data, length);
}

bool read16(uintptr_t base, uint8_t address, uint16_t reg, uint8_t *data,
            size_t length) {
  uint8_t prefix[] = {static_cast<uint8_t>(reg >> 8),
                      static_cast<uint8_t>(reg)};
  return readRegister(base, address, prefix, sizeof(prefix), data, length);
}

bool write16(uintptr_t base, uint8_t address, uint16_t reg,
             const uint8_t *data, size_t length) {
  uint8_t prefix[] = {static_cast<uint8_t>(reg >> 8),
                      static_cast<uint8_t>(reg)};
  return writeRegister(base, address, prefix, sizeof(prefix), data, length);
}

}
}

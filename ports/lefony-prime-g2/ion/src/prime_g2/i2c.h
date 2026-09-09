#ifndef ION_PRIME_G2_I2C_H
#define ION_PRIME_G2_I2C_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace I2C {

void init();
bool read8(uintptr_t controller, uint8_t address, uint8_t reg,
           uint8_t *data, size_t length);
bool write8(uintptr_t controller, uint8_t address, uint8_t reg,
            const uint8_t *data, size_t length);
bool read16(uintptr_t controller, uint8_t address, uint16_t reg,
            uint8_t *data, size_t length);
bool write16(uintptr_t controller, uint8_t address, uint16_t reg,
             const uint8_t *data, size_t length);

}
}

#endif

#ifndef ION_PRIME_G2_UART_H
#define ION_PRIME_G2_UART_H

#include <stdint.h>

namespace PrimeG2 {
namespace UART {

void init(uintptr_t base, uint32_t gateOffset, unsigned gateBit);
bool available(uintptr_t base);
uint8_t read(uintptr_t base);
void write(uintptr_t base, uint8_t byte);
bool transmissionDone(uintptr_t base);

}
}

#endif

#ifndef ION_PRIME_G2_INTERRUPTS_H
#define ION_PRIME_G2_INTERRUPTS_H

#include <stdint.h>

namespace PrimeG2 {
namespace Interrupts {

using Handler = void (*)();

constexpr unsigned GPT1 = 32 + 55;
constexpr unsigned KPP = 32 + 82;
constexpr unsigned SNVSPowerKey = 32 + 4;
constexpr unsigned GPIO5Low = 32 + 74;
constexpr unsigned Maximum = 160;

void init();
bool registerHandler(unsigned interrupt, Handler handler, uint8_t priority = 0x80);
void enable(unsigned interrupt);
void disable(unsigned interrupt);
void setPending(unsigned interrupt);
uint32_t handledCount(unsigned interrupt);
uint32_t unhandledCount();
uint32_t spuriousCount();
uint32_t maximumLatencyMicroseconds();
bool selfTest();

}
}

extern "C" void prime_g2_irq_dispatch();

#endif

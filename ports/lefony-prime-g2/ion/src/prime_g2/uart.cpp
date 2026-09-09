#include "uart.h"

#include "registers.h"

namespace {
constexpr uint32_t UCR1_UARTEN = 1u << 0;
constexpr uint32_t UCR2_IRTS = 1u << 14;
constexpr uint32_t UCR2_WS = 1u << 5;
constexpr uint32_t UCR2_TXEN = 1u << 2;
constexpr uint32_t UCR2_RXEN = 1u << 1;
constexpr uint32_t UCR2_SRST = 1u << 0;
constexpr uint32_t UCR3_RXDMUXSEL = 1u << 2;
constexpr uint32_t UTS_TXFULL = 1u << 4;
constexpr uint32_t UTS_RXEMPTY = 1u << 5;
constexpr uint32_t USR2_TXDC = 1u << 3;
}

namespace PrimeG2 {
namespace UART {

void init(uintptr_t base, uint32_t gateOffset, unsigned gateBit) {
  /* Use the 24 MHz oscillator with a divide-by-one UART PODF. This makes the
   * baud calculation independent of U-Boot and matches QEMU's clock model. */
  updateBits(CCM + 0x24, (1u << 6) | 0x3Fu, 1u << 6);
  gate(gateOffset, gateBit);

  reg32(base + 0x80) = 0;
  reg32(base + 0x84) = 0;
  for (unsigned timeout = 0;
       timeout < 10000 && !(reg32(base + 0x84) & UCR2_SRST); timeout++) {
    __asm volatile("nop");
  }
  reg32(base + 0x88) = UCR3_RXDMUXSEL;
  reg32(base + 0x8C) = 0;
  reg32(base + 0x90) = (5u << 7) | (2u << 10) | 1u;
  /* 24 MHz * 96 / (16 * 1250) = 115200 baud. */
  reg32(base + 0xA4) = 95;
  reg32(base + 0xA8) = 1249;
  reg32(base + 0xB0) = 24000;
  reg32(base + 0x84) = UCR2_IRTS | UCR2_WS | UCR2_TXEN | UCR2_RXEN |
    UCR2_SRST;
  reg32(base + 0x80) = UCR1_UARTEN;
}

bool available(uintptr_t base) {
  return !(reg32(base + 0xB4) & UTS_RXEMPTY);
}

uint8_t read(uintptr_t base) {
  return static_cast<uint8_t>(reg32(base + 0x00));
}

void write(uintptr_t base, uint8_t byte) {
  while (reg32(base + 0xB4) & UTS_TXFULL) {
  }
  reg32(base + 0x40) = byte;
}

bool transmissionDone(uintptr_t base) {
  return reg32(base + 0x98) & USR2_TXDC;
}

}
}

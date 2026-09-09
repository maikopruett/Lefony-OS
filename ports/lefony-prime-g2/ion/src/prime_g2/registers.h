#ifndef ION_PRIME_G2_REGISTERS_H
#define ION_PRIME_G2_REGISTERS_H

#include <stdint.h>

namespace PrimeG2 {

inline volatile uint32_t & reg32(uintptr_t address) {
  return *reinterpret_cast<volatile uint32_t *>(address);
}

inline volatile uint16_t & reg16(uintptr_t address) {
  return *reinterpret_cast<volatile uint16_t *>(address);
}

inline void barrier() {
  __asm volatile("dsb sy" ::: "memory");
}

constexpr uintptr_t CCM = 0x020C4000;
constexpr uintptr_t ANATOP = 0x020C8000;
constexpr uintptr_t SRC = 0x020D8000;
constexpr uintptr_t IOMUXC = 0x020E0000;
constexpr uintptr_t GPIO1 = 0x0209C000;
constexpr uintptr_t GPIO2 = 0x020A0000;
constexpr uintptr_t GPIO3 = 0x020A4000;
constexpr uintptr_t GPIO4 = 0x020A8000;
constexpr uintptr_t GPIO5 = 0x020AC000;
constexpr uintptr_t GPT1 = 0x02098000;
constexpr uintptr_t KPP = 0x020B8000;
constexpr uintptr_t PWM7 = 0x020F8000;
constexpr uintptr_t WDOG1 = 0x020BC000;
constexpr uintptr_t UART1 = 0x02020000;
constexpr uintptr_t UART3 = 0x021EC000;
constexpr uintptr_t LCDIF = 0x021C8000;
constexpr uintptr_t USBPHY1 = 0x020C9000;
constexpr uintptr_t USBOTG1 = 0x02184000;
constexpr uintptr_t USBNC = 0x02184800;
constexpr uintptr_t I2C1 = 0x021A0000;
constexpr uintptr_t I2C2 = 0x021A4000;
constexpr uintptr_t SNVS = 0x020CC000;
constexpr uintptr_t GPMI = 0x01806000;
constexpr uintptr_t BCH = 0x01808000;

inline void setBits(uintptr_t address, uint32_t mask) {
  reg32(address) = reg32(address) | mask;
}

inline void clearBits(uintptr_t address, uint32_t mask) {
  reg32(address) = reg32(address) & ~mask;
}

inline void updateBits(uintptr_t address, uint32_t mask, uint32_t value) {
  reg32(address) = (reg32(address) & ~mask) | (value & mask);
}

inline void gpioDirection(uintptr_t gpio, unsigned pin, bool output) {
  updateBits(gpio + 0x4, 1u << pin, output ? 1u << pin : 0u);
}

inline void gpioWrite(uintptr_t gpio, unsigned pin, bool high) {
  updateBits(gpio + 0x0, 1u << pin, high ? 1u << pin : 0u);
}

void mux(uint32_t muxOffset, uint32_t padOffset, uint32_t mode,
         uint32_t padControl);
void gate(uint32_t ccgrOffset, unsigned bit);

}

#endif

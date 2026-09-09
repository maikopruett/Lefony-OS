#include "interrupts.h"

#include "diagnostics.h"
#include "registers.h"

namespace {
constexpr uintptr_t GIC = 0x00A00000;
constexpr uintptr_t Distributor = GIC + 0x1000;
constexpr uintptr_t CPU = GIC + 0x2000;
constexpr uintptr_t GICD_CTLR = Distributor + 0x000;
constexpr uintptr_t GICD_TYPER = Distributor + 0x004;
constexpr uintptr_t GICD_ISENABLER = Distributor + 0x100;
constexpr uintptr_t GICD_ICENABLER = Distributor + 0x180;
constexpr uintptr_t GICD_ISPENDR = Distributor + 0x200;
constexpr uintptr_t GICD_ICPENDR = Distributor + 0x280;
constexpr uintptr_t GICD_IPRIORITYR = Distributor + 0x400;
constexpr uintptr_t GICD_ITARGETSR = Distributor + 0x800;
constexpr uintptr_t GICC_CTLR = CPU + 0x000;
constexpr uintptr_t GICC_PMR = CPU + 0x004;
constexpr uintptr_t GICC_BPR = CPU + 0x008;
constexpr uintptr_t GICC_IAR = CPU + 0x00C;
constexpr uintptr_t GICC_EOIR = CPU + 0x010;

PrimeG2::Interrupts::Handler sHandlers[PrimeG2::Interrupts::Maximum] = {};
volatile uint32_t sHandled[PrimeG2::Interrupts::Maximum] = {};
volatile uint32_t sUnhandled = 0;
volatile uint32_t sSpurious = 0;
volatile uint32_t sMaximumLatency = 0;

uint32_t cycleCounter() {
  uint32_t value;
  __asm volatile("mrc p15, 0, %0, c9, c13, 0" : "=r"(value));
  return value;
}
}

namespace PrimeG2 {
namespace Interrupts {

void init() {
  __asm volatile("cpsid i" ::: "memory");
  reg32(GICD_CTLR) = 0;
  reg32(GICC_CTLR) = 0;
  barrier();

  unsigned count = 32 * ((reg32(GICD_TYPER) & 0x1Fu) + 1);
  if (count > Maximum) count = Maximum;
  for (unsigned i = 0; i < count; i += 32) {
    reg32(GICD_ICENABLER + i / 8) = 0xFFFFFFFFu;
    reg32(GICD_ICPENDR + i / 8) = 0xFFFFFFFFu;
  }
  for (unsigned i = 0; i < count; i += 4) {
    reg32(GICD_IPRIORITYR + i) = 0xA0A0A0A0u;
    if (i >= 32) reg32(GICD_ITARGETSR + i) = 0x01010101u;
  }

  /* Enable the PMU cycle counter for bounded IRQ-latency measurements. */
  uint32_t one = 1;
  uint32_t cycle = 1u << 31;
  __asm volatile("mcr p15, 0, %0, c9, c12, 0\n"
                 "mcr p15, 0, %1, c9, c12, 1\n"
                 "mcr p15, 0, %1, c9, c12, 2"
                 :: "r"(one), "r"(cycle) : "memory");

  reg32(GICC_PMR) = 0xFF;
  reg32(GICC_BPR) = 0;
  reg32(GICC_CTLR) = 1;
  reg32(GICD_CTLR) = 1;
  barrier();
  __asm volatile("cpsie i" ::: "memory");
}

bool registerHandler(unsigned interrupt, Handler handler, uint8_t priority) {
  if (interrupt < 16 || interrupt >= Maximum || handler == nullptr) return false;
  disable(interrupt);
  sHandlers[interrupt] = handler;
  uintptr_t priorityWord = GICD_IPRIORITYR + (interrupt & ~3u);
  unsigned shift = (interrupt & 3u) * 8;
  updateBits(priorityWord, 0xFFu << shift,
             static_cast<uint32_t>(priority) << shift);
  if (interrupt >= 32) {
    uintptr_t targetWord = GICD_ITARGETSR + (interrupt & ~3u);
    shift = (interrupt & 3u) * 8;
    updateBits(targetWord, 0xFFu << shift, 1u << shift);
  }
  reg32(GICD_ICPENDR + (interrupt / 32) * 4) = 1u << (interrupt & 31);
  barrier();
  return true;
}

void enable(unsigned interrupt) {
  if (interrupt < Maximum)
    reg32(GICD_ISENABLER + (interrupt / 32) * 4) = 1u << (interrupt & 31);
}

void disable(unsigned interrupt) {
  if (interrupt < Maximum)
    reg32(GICD_ICENABLER + (interrupt / 32) * 4) = 1u << (interrupt & 31);
}

void setPending(unsigned interrupt) {
  if (interrupt < Maximum)
    reg32(GICD_ISPENDR + (interrupt / 32) * 4) = 1u << (interrupt & 31);
}

uint32_t handledCount(unsigned interrupt) {
  return interrupt < Maximum ? sHandled[interrupt] : 0;
}
uint32_t unhandledCount() { return sUnhandled; }
uint32_t spuriousCount() { return sSpurious; }
uint32_t maximumLatencyMicroseconds() { return sMaximumLatency; }

bool selfTest() {
  return (reg32(GICD_CTLR) & 1u) && (reg32(GICC_CTLR) & 1u) &&
    reg32(GICC_PMR) == 0xFF;
}

}
}

extern "C" void prime_g2_irq_dispatch() {
  uint32_t entered = cycleCounter();
  uint32_t acknowledge = PrimeG2::reg32(GICC_IAR);
  unsigned interrupt = acknowledge & 0x3FFu;
  if (interrupt >= 1020) {
    sSpurious++;
    return;
  }
  if (interrupt < PrimeG2::Interrupts::Maximum && sHandlers[interrupt]) {
    sHandlers[interrupt]();
    sHandled[interrupt]++;
  } else {
    sUnhandled++;
    PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::FatalException,
                                 0x495251u, interrupt, sUnhandled);
    if (interrupt < PrimeG2::Interrupts::Maximum)
      PrimeG2::Interrupts::disable(interrupt);
  }
  PrimeG2::reg32(GICC_EOIR) = acknowledge;
  PrimeG2::barrier();
  /* Cortex-A7 PMCCNTR normally runs at CPU/64. The metric is deliberately a
   * conservative upper bound until the physical CPU clock is captured. */
  uint32_t elapsed = cycleCounter() - entered;
  uint32_t microseconds = (elapsed * 64u + 395u) / 396u;
  if (microseconds > sMaximumLatency) sMaximumLatency = microseconds;
}

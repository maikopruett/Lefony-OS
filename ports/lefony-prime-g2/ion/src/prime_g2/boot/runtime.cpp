#include "../board.h"
#include "../display.h"
#include "../registers.h"
#include "../uart.h"
#include "../diagnostics.h"
#include "../usb_diagnostics.h"
#include "../system.h"
#include "../watchdog.h"

#include <ion.h>
#include <ion/display.h>
#include <stddef.h>
#include <string.h>

using Constructor = void (*)();

extern "C" {
extern char _bss_start;
extern char _bss_end;
extern Constructor _init_array_start;
extern Constructor _init_array_end;
void prime_g2_stack_guard_init();
}

namespace {
volatile bool sReportingException = false;

void write(const char *text) {
  while (*text) PrimeG2::UART::write(PrimeG2::UART1, *text++);
}

void writeHex(const char *label, uint32_t value) {
  constexpr char Digits[] = "0123456789ABCDEF";
  write(label);
  write("0x");
  for (int shift = 28; shift >= 0; shift -= 4) {
    PrimeG2::UART::write(PrimeG2::UART1, Digits[(value >> shift) & 0xF]);
  }
  PrimeG2::UART::write(PrimeG2::UART1, '\n');
}

uint32_t faultRegister(unsigned coprocessorRegister) {
  uint32_t result = 0;
  switch (coprocessorRegister) {
    case 0: __asm volatile("mrc p15, 0, %0, c5, c0, 0" : "=r"(result)); break;
    case 1: __asm volatile("mrc p15, 0, %0, c6, c0, 0" : "=r"(result)); break;
    case 2: __asm volatile("mrc p15, 0, %0, c5, c0, 1" : "=r"(result)); break;
    case 3: __asm volatile("mrc p15, 0, %0, c6, c0, 2" : "=r"(result)); break;
  }
  return result;
}

[[noreturn]] void diagnosticHalt() {
  // USB is deliberately polled here instead of sleeping: exception entry may
  // have masked IRQ/FIQ and WFE would then make a fatal report unreachable.
  while (true) {
    /* In physical observation builds this services only a watchdog inherited
     * from U-Boot; it never arms a new one. Keep the fault screen and register
     * snapshot stable instead of rebooting away the evidence. */
    PrimeG2::Watchdog::poll(true);
    PrimeG2::USBDiagnostics::poll();
    __asm volatile("nop");
  }
}
}

extern "C" [[noreturn]] void prime_g2_exception_report(
    unsigned type, const uint32_t *registers, uint32_t link,
    uint32_t savedProgramStatus) {
  if (sReportingException) {
    write("Lefony OS fatal: recursive exception\n");
    diagnosticHalt();
  }
  sReportingException = true;
  constexpr const char *Names[] = {
    "invalid", "undefined", "svc", "prefetch-abort", "data-abort",
    "reserved", "irq", "fiq"
  };
  unsigned safeType = type < sizeof(Names) / sizeof(Names[0]) ? type : 0;
  uint32_t adjustment = type == 4 ? 8 : 4;
  uint32_t faultStatus = faultRegister(type == 3 ? 2 : 0);
  uint32_t faultAddress = faultRegister(type == 3 ? 3 : 1);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::FatalException,
                               type, link - adjustment, savedProgramStatus);
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::FatalFaultRegisters,
                               faultStatus, faultAddress, link);
  PrimeG2::Diagnostics::captureSnapshot();
  write("Lefony OS fatal exception: ");
  write(Names[safeType]);
  write("\n");
  writeHex("PC=", link - adjustment);
  writeHex("LR=", link);
  writeHex("SP=", reinterpret_cast<uintptr_t>(registers + 14));
  writeHex("CPSR=", savedProgramStatus);
  for (unsigned i = 0; i < 13; i++) {
    char label[] = {'R', static_cast<char>('0' + i / 10),
                    static_cast<char>('0' + i % 10), '=', 0};
    writeHex(label, registers[i]);
  }
  writeHex("DFSR=", faultRegister(0));
  writeHex("DFAR=", faultRegister(1));
  writeHex("IFSR=", faultRegister(2));
  writeHex("IFAR=", faultRegister(3));
  PrimeG2::Display::cancelFrame();
  Ion::Display::pushRectUniform(
    KDRect(0, 0, Ion::Display::Width, Ion::Display::Height), KDColorRed);
  Ion::Display::pushRectUniform(KDRect(8, 8, Ion::Display::Width - 16, 24),
                                KDColorBlack);
  diagnosticHalt();
}

extern "C" [[noreturn]] void prime_g2_runtime_start() {
  memset(&_bss_start, 0, &_bss_end - &_bss_start);
  prime_g2_stack_guard_init();

  for (Constructor * constructor = &_init_array_start;
       constructor < &_init_array_end; constructor++) {
    (*constructor)();
  }

  PrimeG2::System::initMemory();

  PrimeG2::Board::init();
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::IonMainEntry);
  PrimeG2::Display::bootProgress(4);
  Ion::Console::writeLine("Lefony OS: entering calculator runtime");
  ion_main(0, nullptr);

  Ion::Console::writeLine("Lefony OS: calculator runtime returned");
  while (true) {
    __asm volatile("wfe");
  }
}

extern "C" [[noreturn]] void abort() {
  Ion::Console::writeLine("Lefony OS: abort");
  PrimeG2::Diagnostics::record(PrimeG2::Diagnostics::FatalAbort);
  PrimeG2::Diagnostics::captureSnapshot();
  /* Assertions call abort(). Make that state unambiguous even when UART and
   * native USB are unavailable: red field plus one black block. */
  PrimeG2::Display::cancelFrame();
  Ion::Display::pushRectUniform(
    KDRect(0, 0, Ion::Display::Width, Ion::Display::Height), KDColorRed);
  Ion::Display::pushRectUniform(KDRect(8, Ion::Display::Height - 32, 64, 24),
                                KDColorBlack);
  diagnosticHalt();
}

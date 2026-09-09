#include "registers.h"
#include "uart.h"

#include <ion/console.h>

namespace PrimeG2 {
namespace Console {
void init() {
  UART::init(UART1, 0x7C, 24);
}
}
}

namespace Ion {
namespace Console {

void writeChar(char c) {
  PrimeG2::UART::write(PrimeG2::UART1, static_cast<uint8_t>(c));
}

char readChar() {
  return PrimeG2::UART::available(PrimeG2::UART1) ?
    static_cast<char>(PrimeG2::UART::read(PrimeG2::UART1)) : 0;
}

bool transmissionDone() {
  return PrimeG2::UART::transmissionDone(PrimeG2::UART1);
}

}
}

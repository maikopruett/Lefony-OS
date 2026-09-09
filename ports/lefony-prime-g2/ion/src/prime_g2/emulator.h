#ifndef ION_PRIME_G2_EMULATOR_H
#define ION_PRIME_G2_EMULATOR_H

#include <ion/events.h>
#include <ion/keyboard.h>

namespace PrimeG2 {
namespace Emulator {

void init();
void poll();
Ion::Keyboard::State keyboardState();
Ion::Events::Event popEvent();
const char *eventText();

}
}

#endif

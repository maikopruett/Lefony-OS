#ifndef ION_PRIME_G2_PERSISTENCE_H
#define ION_PRIME_G2_PERSISTENCE_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace Persistence {

enum class State : uint8_t {
  Unavailable,
  Empty,
  Loaded,
  Recovered,
  Error
};

void init();
void poll();
bool commit();
bool commitInProgress();
bool factoryReset();
State state();
uint64_t generation();
#if PRIME_G2_EMULATOR
bool corruptActiveHeaderForTest();
bool simulateInterruptedCommitForTest(unsigned phase);
bool setCompatibleFieldForTest(unsigned index, uint32_t value);
bool getCompatibleFieldForTest(unsigned index, uint32_t *value);
bool validatePayloadForTest(const uint8_t *data, size_t size);
#endif

}
}

#endif

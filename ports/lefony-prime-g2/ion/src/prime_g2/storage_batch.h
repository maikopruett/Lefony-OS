// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef ION_PRIME_G2_STORAGE_BATCH_H
#define ION_PRIME_G2_STORAGE_BATCH_H
#include <stdint.h>
namespace PrimeG2 { namespace StorageBatch {
// GPT runs at 3 MHz. Return to normal input/services after 16 ms or 64
// existing bounded steps, including when the timer stalls. An individual
// storage operation retains its own timeout and may exceed this budget.
template<class Clock,class Pending,class Poll>
void run(Clock clock,Pending pending,Poll poll) {
  uint32_t start=clock();
  for(unsigned steps=0;steps<64;steps++) {
    poll();
    if(!pending() || uint32_t(clock()-start)>=48000) break;
  }
}
} }
#endif

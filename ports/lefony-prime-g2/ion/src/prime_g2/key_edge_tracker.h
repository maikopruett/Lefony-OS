// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef PRIME_G2_KEY_EDGE_TRACKER_H
#define PRIME_G2_KEY_EDGE_TRACKER_H
#include <stdint.h>
namespace PrimeG2 {
class KeyEdgeTracker {
public:
  uint64_t update(uint64_t down) {
    mReleased |= ~down;
    uint64_t pressed=mReleased&down;
    // Consume the whole chord, matching the event loop's existing choice of
    // one key per chord. Held keys require an observed release before reuse.
    mReleased &= ~down;
    return pressed;
  }
private:
  uint64_t mReleased=0;
};
}
#endif

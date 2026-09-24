// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_INPUT_H
#define LEFONY_INPUT_H
#include "app.h"
#include "input_wire.h"
namespace Lefony {
inline int32_t readInput(InputSnapshot &snapshot) { return service(8,&snapshot); }
struct NavigationRequest { uint32_t size,version,reserved,depth; };
// Request Back delivery while an app-owned screen/modal stack is nonempty.
// At depth zero Back exits normally. Home, Apps and power remain OS-owned.
inline int32_t navigationDepth(uint32_t depth) {
  NavigationRequest request{sizeof(NavigationRequest),1,0,depth};return service(9,&request);
}
}
#endif

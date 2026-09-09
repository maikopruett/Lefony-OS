#pragma once
#include <stdint.h>

namespace Ion { namespace Touch {
enum class Phase { Down, Move, Up, Cancel };
struct Event {
  Event(Phase p = Phase::Cancel, int px = 0, int py = 0,
        int sx = 0, int sy = 0, bool drag = false) :
    phase(p), x(px), y(py), startX(sx), startY(sy), dragging(drag) {}
  Phase phase;
  int x, y, startX, startY;
  bool dragging;
  unsigned contacts = 1;
  int x2 = 0, y2 = 0;
  // Rebase gesture geometry when a finger joins or leaves the contact set.
  bool contactsChanged = false;
};
const Event & currentEvent();
}}

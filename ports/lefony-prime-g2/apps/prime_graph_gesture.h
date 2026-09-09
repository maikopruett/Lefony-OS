#pragma once
#include <ion/touch.h>
#include <cmath>

namespace PrimeG2 {
// Pixel-space gesture geometry, independent of graph models and UI focus.
class GraphGesture {
public:
  struct Delta { float ratio = 1.f, fromX = 0.f, fromY = 0.f, toX = 0.f, toY = 0.f; };
  bool update(const Ion::Touch::Event & t, Delta * d) {
    float x = t.contacts == 2 ? (t.x + t.x2) * .5f : t.x;
    float y = t.contacts == 2 ? (t.y + t.y2) * .5f : t.y;
    float dx = t.x2 - t.x, dy = t.y2 - t.y;
    float span = t.contacts == 2 ? std::sqrt(dx * dx + dy * dy) : 0.f;
    if (t.phase == Ion::Touch::Phase::Cancel || t.phase == Ion::Touch::Phase::Up) {
      m_active = false;
      return false;
    }
    bool move = m_active && !t.contactsChanged && t.dragging;
    if (move) {
      d->fromX = m_x; d->fromY = m_y; d->toX = x; d->toY = y;
      // Near-coincident fingers have no reliable scale; rebase until separated.
      d->ratio = span >= 8.f && m_span >= 8.f ? m_span / span : 1.f;
    }
    if (!m_active || t.contactsChanged || t.dragging) {
      m_x = x; m_y = y; m_span = span;
    }
    m_active = true;
    return move;
  }
private:
  bool m_active = false;
  float m_x = 0.f, m_y = 0.f, m_span = 0.f;
};
}

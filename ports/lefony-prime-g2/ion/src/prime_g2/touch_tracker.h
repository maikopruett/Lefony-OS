#pragma once
#include <ion/touch.h>

namespace PrimeG2 {
/* Hardware-independent tracking of up to two stable Goodix contact IDs.
 * Malformed streams remain quarantined until every finger lifts. */
class TouchTracker {
public:
  const Ion::Touch::Event & event() const { return m_event; }
  bool cancelled() const { return m_cancelled; }
  bool cancel() {
    bool active = m_active;
    m_active = false;
    m_blocked = true;
    m_cancelled = true;
    m_event.phase = Ion::Touch::Phase::Cancel;
    return active;
  }
  bool report(unsigned contacts, unsigned id, unsigned x, unsigned y,
              unsigned id2 = 0, unsigned x2 = 320, unsigned y2 = 240) {
    using Ion::Touch::Phase;
    if (contacts == 0) {
      m_blocked = false;
      if (!m_active) return false;
      m_active = false;
      m_event.phase = Phase::Up;
      return true; // Release bytes are not valid coordinates.
    }
    if (contacts > 2 || x >= 320 || y >= 240 ||
        (contacts == 2 && (x2 >= 320 || y2 >= 240 || id == id2))) return cancel();
    if (m_blocked) return false;
    // Normalize report ordering; Goodix can reorder contact records.
    if (contacts == 2 && id > id2) {
      swap(id, id2); swap(x, x2); swap(y, y2);
    }
    bool changed = m_active && contacts != m_event.contacts;
    if (m_active) {
      if (!changed && (id != m_id || (contacts == 2 && id2 != m_id2))) return cancel();
      if (changed && !(id == m_id || (contacts == 2 && id2 == m_id) ||
                      (m_event.contacts == 2 && id == m_id2))) return cancel();
    }
    m_cancelled = false;
    if (!m_active) {
      m_active = true;
      m_event = {Phase::Down, int(x), int(y), int(x), int(y), contacts == 2};
    } else {
      if (!changed && m_event.x == int(x) && m_event.y == int(y) &&
          (contacts == 1 || (m_event.x2 == int(x2) && m_event.y2 == int(y2)))) return false;
      m_event.phase = Phase::Move;
      m_event.x = x; m_event.y = y;
      int dx = int(x) - m_event.startX, dy = int(y) - m_event.startY;
      m_event.dragging |= contacts == 2 || changed || dx * dx + dy * dy >= 100;
    }
    m_id = id; m_id2 = id2;
    m_event.id = id; m_event.id2 = id2;
    m_event.contacts = contacts;
    m_event.x2 = x2; m_event.y2 = y2;
    m_event.contactsChanged = changed;
    return true;
  }
private:
  static void swap(unsigned & a, unsigned & b) { unsigned t = a; a = b; b = t; }
  Ion::Touch::Event m_event;
  unsigned m_id = 0, m_id2 = 0;
  bool m_active = false, m_blocked = false, m_cancelled = false;
};
}

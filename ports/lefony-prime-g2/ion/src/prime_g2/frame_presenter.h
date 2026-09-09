#ifndef PRIME_G2_FRAME_PRESENTER_H
#define PRIME_G2_FRAME_PRESENTER_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {

/* Rendering never touches either DMA buffer. A pending NEXT buffer is owned
 * by LCDIF even before it becomes CUR, and cannot be reused on a timeout. */
template<size_t Pixels> class FramePresenter {
public:
  void changed() { m_dirty = true; }
  void reset() { m_pending = nullptr; m_dirty = true; }
  uint32_t timeouts() const { return m_timeouts; }
  uint32_t frames() const { return m_frames; }

  template<class Hardware>
  bool present(const uint32_t * source, uint32_t * a, uint32_t * b,
               Hardware & hardware) {
    if (!complete(hardware)) return false;
    if (!m_dirty) return true;
    const uint32_t * current = hardware.current();
    if (current != a && current != b) return false;
    uint32_t * next = current == a ? b : a;
    for (size_t i = 0; i < Pixels; i++) next[i] = source[i];
    hardware.publish(next, Pixels * sizeof(uint32_t));
    m_pending = next;
    m_dirty = false;
    hardware.queue(next);
    return complete(hardware);
  }

private:
  template<class Hardware> bool complete(Hardware & hardware) {
    if (!m_pending) return true;
    // A fixed iteration limit also works when the system timer has stopped.
    for (unsigned attempts = 0; attempts < 500; attempts++) {
      if (hardware.current() == m_pending) {
        m_pending = nullptr;
        m_frames++;
        return true;
      }
      hardware.pause();
    }
    m_timeouts++;
    return false; // Keep both DMA buffers untouched until ownership is known.
  }
  uint32_t * m_pending = nullptr;
  bool m_dirty = true;
  uint32_t m_timeouts = 0;
  uint32_t m_frames = 0;
};
}
#endif

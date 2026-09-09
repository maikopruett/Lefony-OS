#ifndef PRIME_REFRESH_TRIAL_H
#define PRIME_REFRESH_TRIAL_H
#include <stdint.h>
namespace PrimeG2 {
class RefreshTrial {
public:
  void start(uint64_t now) { m_deadline = now + 15000; m_active = true; }
  bool expired(uint64_t now) const { return m_active && now >= m_deadline; }
  bool active() const { return m_active; }
  bool confirm(uint64_t now) {
    if (!m_active || expired(now)) return false;
    m_active = false; return true;
  }
  void cancel() { m_active = false; }
private:
  uint64_t m_deadline = 0;
  bool m_active = false;
};
}
#endif

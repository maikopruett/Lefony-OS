// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef ION_PRIME_G2_STORAGE_PROFILE_H
#define ION_PRIME_G2_STORAGE_PROFILE_H
#include <stdint.h>
namespace PrimeG2 { namespace StorageProfile {
// Cumulative read-only counters. Nested categories must not be added together.
enum class Metric : uint32_t { Read, Program, Erase, Usable, RawRead,
  ProgramWait, EraseWait, OtherReady, CommandDMA, Count };
struct Counter {
  uint64_t calls, bytes, ticks;
  uint32_t minimum, maximum, failures, reserved;
};
struct Report {
  uint32_t magic, version, bytes, tickHz, count, now, physical, reserved;
  Counter counters[static_cast<unsigned>(Metric::Count)];
};
static_assert(sizeof(Counter)==40 && sizeof(Report)==392,"storage timing wire layout");
uint32_t ticks();
void record(Metric, uint32_t bytes, uint32_t duration, bool success);
Report snapshot();
class Scope {
 public:
  Scope(Metric metric,uint32_t bytes=0):m_metric(metric),m_bytes(bytes),m_start(ticks()),m_success(false) {}
  ~Scope() { record(m_metric,m_bytes,ticks()-m_start,m_success); }
  bool result(bool success) { m_success=success;return success; }
 private:
  Metric m_metric;uint32_t m_bytes,m_start;bool m_success;
};
template<typename F> bool measure(Metric metric,uint32_t bytes,F operation) {
  Scope scope(metric,bytes);return scope.result(operation());
}
} }
#endif

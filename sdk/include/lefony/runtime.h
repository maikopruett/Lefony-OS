// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_RUNTIME_H
#define LEFONY_RUNTIME_H
#include <stdint.h>
#include <stddef.h>
namespace Lefony {
// App-owned monotonic arena. No throwing allocation, destructors, or hidden OS
// memory. reset invalidates ALL returned pointers. Alignment is at most 16.
template<size_t Capacity> class Arena {
  static_assert(Capacity > 0, "arena must have capacity");
public:
  constexpr Arena() : m_bytes{},m_used(0),m_peak(0),m_failures(0) {}
  void *allocate(size_t bytes,size_t alignment=8) {
    if(!bytes || !alignment || alignment>16 || (alignment&(alignment-1))) { m_failures++;return nullptr; }
    size_t padding=(alignment-(m_used&(alignment-1)))&(alignment-1);
    if(padding>Capacity-m_used || bytes>Capacity-m_used-padding) { m_failures++;return nullptr; }
    size_t offset=m_used+padding;m_used=offset+bytes;
    if(m_used>m_peak) m_peak=m_used;
    return m_bytes+offset;
  }
  void reset() { m_used=0; }
  size_t used() const { return m_used; }
  size_t peak() const { return m_peak; }
  size_t remaining() const { return Capacity-m_used; }
  size_t failures() const { return m_failures; }
  static constexpr size_t capacity() { return Capacity; }
private:
  alignas(16) unsigned char m_bytes[Capacity];size_t m_used,m_peak,m_failures;
};
template<typename T,size_t Capacity> class Vector {
  static_assert(Capacity>0,"vector must have capacity");
public:
  constexpr Vector() : m_values{},m_count(0) {}
  bool push(const T &value) { if(m_count==Capacity) return false;m_values[m_count++]=value;return true; }
  bool pop() { if(!m_count) return false;--m_count;return true; }
  T *at(size_t index) { return index<m_count?m_values+index:nullptr; }
  const T *at(size_t index) const { return index<m_count?m_values+index:nullptr; }
  size_t size() const { return m_count; }
  void clear() { m_count=0; }
private:
  T m_values[Capacity];size_t m_count;
};
struct Task {
  uint32_t completed=0,total=0;bool cancelled=false;
  void cancel() { cancelled=true; }
  bool done() const { return cancelled || completed>=total; }
  // Work is called at most budget times; each unit must itself be bounded.
  template<typename Work> void step(uint32_t budget,Work work) {
    while(budget-- && !done()) { if(!work(completed)) { cancelled=true;break; }completed++; }
  }
};
// millis is uint32_t; elapsed comparisons remain valid across one wrap.
inline uint32_t elapsed(uint32_t now,uint32_t start) { return now-start; }
}
#endif

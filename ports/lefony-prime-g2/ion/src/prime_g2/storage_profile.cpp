// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "storage_profile.h"
#include "registers.h"
namespace PrimeG2 { namespace StorageProfile {
namespace { Counter counters[static_cast<unsigned>(Metric::Count)]={}; }
// Timing::init owns this free-running 3 MHz GPT counter. An individual bounded
// NAND operation is shorter than its 23-minute wrap interval.
uint32_t ticks() { return reg32(GPT1+0x24); }
void record(Metric metric,uint32_t bytes,uint32_t duration,bool success) {
  unsigned index=static_cast<unsigned>(metric);
  if(index>=static_cast<unsigned>(Metric::Count)) return;
  auto &c=counters[index];
  if(!c.calls || duration<c.minimum) c.minimum=duration;
  if(duration>c.maximum) c.maximum=duration;
  c.calls++;c.ticks+=duration;
  if(success) c.bytes+=bytes;else c.failures++;
}
Report snapshot() {
#if PRIME_G2_EMULATOR
  constexpr uint32_t physical=0;
#else
  constexpr uint32_t physical=1;
#endif
  Report report={0x3150464c,1,sizeof(Report),3000000,
    static_cast<unsigned>(Metric::Count),ticks(),physical,0,{}};
  for(unsigned i=0;i<report.count;i++) report.counters[i]=counters[i];
  return report;
}
} }

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef ION_PRIME_G2_DUAL_BOOT_GUARD_H
#define ION_PRIME_G2_DUAL_BOOT_GUARD_H
#include <stdint.h>
#include <stddef.h>
#include "dual_boot_build.h"
namespace PrimeG2 { namespace DualBoot {
constexpr bool Enabled = LEFONY_DUAL_BOOT_CANDIDATE;
inline uint32_t word(const uint8_t *p) {
  return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
inline bool validHandoff(const uint8_t *p) {
  if(!p || word(p)!=0x3548464c || !word(p+36)) return false;
  for(unsigned i=0;i<32;i++) if(p[4+i]!=LefonyDualLayoutSHA[i]) return false;
  for(unsigned i=40;i<60;i++) if(p[i]) return false;
  uint32_t crc=0xffffffffu;
  for(unsigned i=0;i<60;i++) {
    crc^=p[i];
    for(unsigned bit=0;bit<8;bit++) crc=(crc>>1)^((0u-(crc&1))&0xedb88320u);
  }
  return word(p+60)==(crc^0xffffffffu);
}
inline bool storageAllowed() {
  return !Enabled || validHandoff(reinterpret_cast<const uint8_t *>(0x87ffd000));
}
// Candidate OS writes are mediated by recovery. In particular no legacy
// development or LFU1 A/B update may reach HP's low NAND region.
inline bool legacyUpdateAllowed() { return !Enabled; }
} }
#endif

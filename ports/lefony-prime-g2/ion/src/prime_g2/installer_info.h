// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef ION_PRIME_G2_INSTALLER_INFO_H
#define ION_PRIME_G2_INSTALLER_INFO_H
#include "dual_boot_guard.h"
namespace PrimeG2 { namespace DualBoot {
// Read-only firmware identity. A legacy response does not attest NAND layout.
inline void installerInfo(uint32_t *out, const uint8_t *handoff) {
  for (unsigned i=0;i<16;i++) out[i]=0;
  const bool valid=Enabled && validHandoff(handoff);
  out[0]=0x3649464c; out[1]=1; out[2]=0x32475048;
  out[3]=Enabled ? 5 : 0;
  out[4]=(Enabled ? 1u : 0u) | (valid ? 2u : 0u);
  out[5]=valid ? word(handoff+36) : 0;
  out[6]=4096; out[7]=131072;
  if (Enabled) for (unsigned i=0;i<8;i++) out[8+i]=word(LefonyDualLayoutSHA+4*i);
}
} }
#endif

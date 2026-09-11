// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_TRUST_ROOTS_H
#define LEFONY_APP_TRUST_ROOTS_H
#include <stdint.h>
// Fail closed. Replaced only in the generated build by explicitly supplied
// PUBLIC app keys. Firmware update keys and test keys are never used implicitly.
struct LefonyAppTrustRoot { uint8_t id[32], modulus[256]; };
constexpr unsigned LefonyAppTrustRootCount=0;
constexpr LefonyAppTrustRoot LefonyAppTrustRoots[1]={};
#endif

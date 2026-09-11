// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef PRIME_G2_NATIVE_APP_H
#define PRIME_G2_NATIVE_APP_H
#include <stddef.h>
#include <stdint.h>
namespace PrimeG2 { namespace NativeApp {
// Unsigned developer packages are only accepted by the VM target.
constexpr uintptr_t StagingAddress = 0x86000000;
constexpr size_t MaximumPackage = 352 + 64 + 4096 + 2 * 1024 * 1024;
bool load(const uint8_t *package, size_t size);
int invoke(uint32_t event, uint32_t first = 0, uint32_t second = 0);
int lastResult();
void unload();
uint32_t diagnostic(unsigned index);
const void *pixels();
}}
extern "C" int prime_app_fault(unsigned kind, const uint32_t *, uint32_t, uint32_t psr);
extern "C" int prime_app_svc(uint32_t *registers, uint32_t psr);
extern "C" int prime_app_irq_expired(uint32_t psr,uint32_t pc);
#endif

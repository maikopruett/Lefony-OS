// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef PRIME_G2_NATIVE_APP_H
#define PRIME_G2_NATIVE_APP_H
#include <stddef.h>
#include <stdint.h>
#include "native_app_input_wire.h"
namespace PrimeG2 {
namespace NativeAppManifest { struct Manifest; }
namespace NativeApp {
// Unsigned developer packages are only accepted by the VM target.
constexpr uintptr_t StagingAddress = 0x86000000;
constexpr size_t MaximumPackage = 352 + 64 + 4096 + 2 * 1024 * 1024;
// Return authenticated metadata only after the complete executable is accepted.
// This is a per-load result, never a verification cache or a bypass option.
bool load(const uint8_t *package, size_t size, NativeAppManifest::Manifest *manifest = nullptr);
int invoke(uint32_t event, uint32_t first = 0, uint32_t second = 0);
// Internal foreground scheduling. Resume events never replace the last input
// snapshot, and cannot execute a loaded app outside its active OS container.
void setForeground(bool active);
bool resumable();
bool resumePending();
bool resumeForeground(); // True when the container needs to redraw.
void noteUITimer();
void prepareInput(const Lefony::InputSnapshot &input);
// Called only from the normal OS event scan, in physical key positions.
void observeKeyboard(uint64_t physicalKeys,uint32_t modifiers);
uint32_t navigationDepth();
int lastResult();
bool saveDataOnClose();
void unload();
uint32_t diagnostic(unsigned index);
// Read-only USB timing snapshot. No memory addresses, input injection or app
// control; measures foreground entry through the first public pixel frame.
struct RuntimeReport { uint32_t words[16]; };
RuntimeReport runtimeReport();
#if PRIME_G2_EMULATOR
// Private VM diagnostics, not an app ABI or a physical-device control.
struct ResourceProfile {
  uint32_t version,bytes,flags,loads,finishedLoads,entries,samples;
  uint32_t stackPointerBytes,stackWrittenBytes,stackCapacity,heapReservedPeak;
  uint32_t services,frames,maxSliceMillis,faults,failureResult,codeBytes,staticBytes;
  uint32_t faultPC,faultEvent;
  uint8_t packageHash[32]; // SHA-256 of the complete inner LFAPP0 package.
};
static_assert(sizeof(ResourceProfile)==112,"VM resource snapshot layout");
bool armResourceProfile(const uint8_t hash[32]);
const ResourceProfile &resourceProfile();
struct HeapResourceProfile {
  uint32_t version,bytes,flags,samples,allocatedBytes,allocatedPeak,arenaBytes,arenaPeak;
  uint32_t observations,loads,address,reserved;
  uint8_t packageHash[32];
};
static_assert(sizeof(HeapResourceProfile)==80,"VM heap snapshot layout");
bool configureHeapResourceProfile(uint32_t address);
const HeapResourceProfile &heapResourceProfile();
#endif
const void *pixels();
}}
extern "C" int prime_app_fault(unsigned kind, const uint32_t *, uint32_t, uint32_t psr);
extern "C" int prime_app_svc(uint32_t *registers, uint32_t psr);
extern "C" int prime_app_irq_expired(uint32_t psr,uint32_t pc);
#endif

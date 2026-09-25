#ifndef ION_PRIME_G2_SYSTEM_H
#define ION_PRIME_G2_SYSTEM_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace System {

enum class MemoryType : uint8_t {
  Fault,
  CodeReadOnly,
  DataReadWrite,
  Device,
  Framebuffer
};

void initMemory();
uint32_t bootloaderRecoveryVersion();
bool validBootloaderRAMCapsule(const void *image, size_t length);
[[noreturn]] void launchBootloaderRAM(const void *image, size_t length);
void mapNativeApp(void *code, void *data);
void mapNativeAppHeap(void *heap);
void cleanDataCacheRange(const void *address, size_t length);
void invalidateDataCacheRange(const void *address, size_t length);
void cleanInvalidateDataCacheRange(const void *address, size_t length);
void dataSyncBarrier();
void instructionSyncBarrier();
uint32_t controlRegister();
MemoryType memoryType(uintptr_t address);
bool selfTest();
uint32_t codeSize();
uint32_t dataSize();
uint32_t heapSize();
uint32_t stackSize();
uint32_t framebufferSize();

}
}

#endif

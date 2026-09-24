#include "system.h"

#include <stdint.h>

extern "C" {
extern char _text_start;
extern char _text_end;
extern char _data_start;
extern char _data_end;
extern char _bss_end;
extern char _stack_top;
extern char _stack_bottom;
extern char _framebuffer_start;
extern char _framebuffer_end;
extern char _heap_start;
extern char _heap_end;
}

namespace {

/* ARMv7 short-descriptor table. One section descriptor covers 1 MiB and the
 * 4096-entry table therefore describes the complete 32-bit address space. */
alignas(16384) uint32_t sTranslationTable[4096];
alignas(1024) uint32_t sAppCodePages[256];
alignas(1024) uint32_t sAppDataPages[256];
alignas(1024) uint32_t sAppHeapPages[8][256];

constexpr uint32_t Section = 2u;
constexpr uint32_t Bufferable = 1u << 2;
constexpr uint32_t Cacheable = 1u << 3;
constexpr uint32_t ExecuteNever = 1u << 4;
constexpr uint32_t AccessPrivRW = 1u << 10;
constexpr uint32_t Tex1 = 1u << 12;
constexpr uint32_t AccessReadOnly = 1u << 15;
constexpr uint32_t Shareable = 1u << 16;
constexpr uint32_t SectionAddress = 0xFFF00000u;

constexpr uint32_t NormalRW = Section | Tex1 | Cacheable | Bufferable |
  Shareable | AccessPrivRW | ExecuteNever;
constexpr uint32_t NormalROCode = Section | Tex1 | Cacheable | Bufferable |
  Shareable | AccessPrivRW | AccessReadOnly;
constexpr uint32_t DeviceRW = Section | Bufferable | Shareable |
  AccessPrivRW | ExecuteNever;
constexpr uint32_t FramebufferRW = Section | Tex1 | Shareable |
  AccessPrivRW | ExecuteNever;

void mapSections(uintptr_t first, uintptr_t last, uint32_t attributes) {
  first &= SectionAddress;
  last = (last + 0xFFFFFu) & SectionAddress;
  for (uintptr_t address = first; address < last; address += 0x100000u) {
    sTranslationTable[address >> 20] =
      static_cast<uint32_t>(address) | attributes;
  }
}

void cacheOperation(const void *address, size_t length, unsigned operation) {
  if (length == 0) return;
  uintptr_t first = reinterpret_cast<uintptr_t>(address) & ~uintptr_t(31);
  uintptr_t last = (reinterpret_cast<uintptr_t>(address) + length + 31) &
    ~uintptr_t(31);
  for (uintptr_t line = first; line < last; line += 32) {
    if (operation == 0) {
      __asm volatile("mcr p15, 0, %0, c7, c10, 1" :: "r"(line) : "memory");
    } else if (operation == 1) {
      __asm volatile("mcr p15, 0, %0, c7, c6, 1" :: "r"(line) : "memory");
    } else {
      __asm volatile("mcr p15, 0, %0, c7, c14, 1" :: "r"(line) : "memory");
    }
  }
  __asm volatile("dsb sy" ::: "memory");
}

}

namespace PrimeG2 {
namespace System {

void initMemory() {
  for (uint32_t &entry : sTranslationTable) entry = 0;

  /* i.MX6UL peripheral and private-peripheral windows. Everything not listed
   * remains a translation fault, catching null and wild-pointer accesses. */
  mapSections(0x00100000u, 0x04000000u, DeviceRW);
  mapSections(0x80000000u, 0x90000000u, NormalRW);
  mapSections(reinterpret_cast<uintptr_t>(&_text_start),
              reinterpret_cast<uintptr_t>(&_text_end), NormalROCode);
  mapSections(reinterpret_cast<uintptr_t>(&_data_start),
              reinterpret_cast<uintptr_t>(&_stack_top), NormalRW);
  mapSections(reinterpret_cast<uintptr_t>(&_framebuffer_start),
              reinterpret_cast<uintptr_t>(&_framebuffer_end), FramebufferRW);

  uint32_t zero = 0;
  uint32_t table = reinterpret_cast<uintptr_t>(sTranslationTable) |
    (1u << 6) | (1u << 3) | (1u << 0); // WBWA table walk, inner shareable
  __asm volatile("dsb sy\n"
                 "mcr p15, 0, %0, c8, c7, 0\n"  // invalidate unified TLB
                 "mcr p15, 0, %0, c7, c5, 0\n"  // invalidate I-cache
                 "mcr p15, 0, %0, c2, c0, 2\n"  // TTBCR: TTBR0 only
                 "mcr p15, 0, %1, c2, c0, 0\n"  // TTBR0
                 "mcr p15, 0, %2, c3, c0, 0\n"  // domain 0 client
                 "dsb sy\n"
                 "isb"
                 :: "r"(zero), "r"(table), "r"(1u) : "memory");

  uint32_t sctlr;
  __asm volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(sctlr));
  sctlr |= (1u << 0) | (1u << 2) | (1u << 11) | (1u << 12);
  __asm volatile("mcr p15, 0, %0, c1, c0, 0\n"
                 "isb" :: "r"(sctlr) : "memory");
}

void cleanDataCacheRange(const void *address, size_t length) {
  cacheOperation(address, length, 0);
}

void mapNativeApp(void *code, void *data) {
  // ARMv7 short-descriptor small pages: user AP=11; APX protects code,
  // small-page bit 0 is XN. Normal WBWA, shareable, non-global mappings.
  constexpr uint32_t RW = 3u | (3u<<4) | (1u<<6) | (1u<<10) | (1u<<11) | 12u;
  constexpr uint32_t RX = 2u | (3u<<4) | (1u<<6) | (1u<<9) | (1u<<10) | (1u<<11) | 12u;
  for (unsigned i=0;i<256;i++) {
    sAppCodePages[i] = code ? (reinterpret_cast<uintptr_t>(code)+i*4096)|RX : 0;
    sAppDataPages[i] = data && i!=0 && i!=239 ? (reinterpret_cast<uintptr_t>(data)+i*4096)|RW : 0;
  }
  sTranslationTable[0x100] = code ? reinterpret_cast<uintptr_t>(sAppCodePages)|1u : 0;
  sTranslationTable[0x102] = data ? reinterpret_cast<uintptr_t>(sAppDataPages)|1u : 0;
  cleanDataCacheRange(sAppCodePages,sizeof(sAppCodePages));
  cleanDataCacheRange(sAppDataPages,sizeof(sAppDataPages));
  cleanDataCacheRange(sTranslationTable,sizeof(sTranslationTable));
  uint32_t zero=0;
  __asm volatile("dsb sy\n mcr p15,0,%0,c8,c7,0\n mcr p15,0,%0,c7,c5,0\n dsb sy\n isb" :: "r"(zero) : "memory");
}

void invalidateDataCacheRange(const void *address, size_t length) {
  cacheOperation(address, length, 1);
}

void mapNativeAppHeap(void *heap) {
  // Negotiated foreground profile: eight MiB with first/last-page guards.
  // Identical user RW+XN small-page attributes to the legacy app data pages.
  constexpr uint32_t RW = 3u | (3u<<4) | (1u<<6) | (1u<<10) | (1u<<11) | 12u;
  for(unsigned section=0;section<8;section++) {
    for(unsigned page=0;page<256;page++) {
      unsigned index=section*256+page;
      sAppHeapPages[section][page]=heap && index && index!=2047 ?
        (reinterpret_cast<uintptr_t>(heap)+index*4096)|RW : 0;
    }
    sTranslationTable[0x110+section]=heap ? reinterpret_cast<uintptr_t>(sAppHeapPages[section])|1u : 0;
  }
  cleanDataCacheRange(sAppHeapPages,sizeof(sAppHeapPages));
  cleanDataCacheRange(sTranslationTable,sizeof(sTranslationTable));
  uint32_t zero=0;
  __asm volatile("dsb sy\n mcr p15,0,%0,c8,c7,0\n mcr p15,0,%0,c7,c5,0\n dsb sy\n isb" :: "r"(zero) : "memory");
}
void cleanInvalidateDataCacheRange(const void *address, size_t length) {
  cacheOperation(address, length, 2);
}

void dataSyncBarrier() { __asm volatile("dsb sy" ::: "memory"); }
void instructionSyncBarrier() { __asm volatile("isb" ::: "memory"); }

uint32_t controlRegister() {
  uint32_t value;
  __asm volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(value));
  return value;
}

MemoryType memoryType(uintptr_t address) {
  uint32_t descriptor = sTranslationTable[address >> 20];
  if ((descriptor & 3u) != Section) return MemoryType::Fault;
  if ((descriptor & ExecuteNever) == 0 && (descriptor & AccessReadOnly))
    return MemoryType::CodeReadOnly;
  if ((descriptor & Tex1) && !(descriptor & Cacheable) &&
      !(descriptor & Bufferable)) return MemoryType::Framebuffer;
  if (!(descriptor & Tex1)) return MemoryType::Device;
  return MemoryType::DataReadWrite;
}

bool selfTest() {
  constexpr uint32_t Required = (1u << 0) | (1u << 2) | (1u << 11) |
    (1u << 12);
  return (controlRegister() & Required) == Required &&
    memoryType(reinterpret_cast<uintptr_t>(&_text_start)) ==
      MemoryType::CodeReadOnly &&
    memoryType(reinterpret_cast<uintptr_t>(&_data_start)) ==
      MemoryType::DataReadWrite &&
    memoryType(0x02000000u) == MemoryType::Device &&
    memoryType(reinterpret_cast<uintptr_t>(&_framebuffer_start)) ==
      MemoryType::Framebuffer &&
    memoryType(0) == MemoryType::Fault;
}

uint32_t codeSize() { return &_text_end - &_text_start; }
/* Report the bytes occupied by mutable program state separately from the
 * reserved heap and stack.  _data_end is intentionally the end of the whole
 * writable MMU region, so it would double-count both reservations here. */
uint32_t dataSize() { return &_bss_end - &_data_start; }
uint32_t heapSize() { return &_heap_end - &_heap_start; }
uint32_t stackSize() { return &_stack_top - &_stack_bottom; }
uint32_t framebufferSize() { return &_framebuffer_end - &_framebuffer_start; }

}
}

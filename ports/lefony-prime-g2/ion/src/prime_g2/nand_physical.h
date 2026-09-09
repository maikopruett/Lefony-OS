#ifndef ION_PRIME_G2_NAND_PHYSICAL_H
#define ION_PRIME_G2_NAND_PHYSICAL_H
#include <stdint.h>

namespace PrimeG2 { namespace NANDPhysical {
// Read-only qualification of the real i.MX6ULL interface. Never an emulator
// synthetic NAND register access. No erase/program entry points are exposed.
enum class Error : uint32_t { None, ClockOrReset, Busy, Timeout, DMA, InvalidID,
  Geometry, Range, BCHTimeout, Uncorrectable };
struct PageReport { uint32_t magic, page, error, corrected, marker, ready; };
bool readPage(uint32_t page);
const PageReport &pageReport();
const uint8_t *pageData();
// Internal updater backend, strictly confined to existing mtd1.
bool blockUsable(uint32_t block);
bool eraseOSBlock(uint32_t block);
bool programOSPage(uint32_t page, const uint8_t *data);
struct Report {
  uint32_t magic, version, error, phase;
  uint32_t id[2];
  uint32_t apbhControl, apbhIRQ, apbhError, semaphore;
  uint32_t gpmiControl, gpmiControl1, gpmiTiming0, gpmiTiming1;
  uint32_t gpmiStatus, bchLayout0, bchLayout1, bchSelect;
};
bool probe();
const Report &report();
} }
#endif

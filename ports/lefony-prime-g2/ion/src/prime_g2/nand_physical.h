#ifndef ION_PRIME_G2_NAND_PHYSICAL_H
#define ION_PRIME_G2_NAND_PHYSICAL_H
#include <stdint.h>

namespace PrimeG2 { namespace NANDPhysical {
// Real i.MX6ULL interface. Firmware and app-volume write entry points have
// separate, fixed range checks; no arbitrary NAND write API is exposed.
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
// Profile-1 app partition only; caller owns NAND serialization. Raw backup
// includes all 2112 bytes. Destination must be DMA/cache-line aligned.
bool appBlockUsable(uint32_t block);
bool eraseAppBlock(uint32_t block);
bool programAppPage(uint32_t page,const uint8_t *data);
bool readAppPage(uint32_t page);
bool readRawAppPage(uint32_t page,uint8_t *destination);
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

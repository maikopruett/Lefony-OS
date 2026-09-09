#include "block_storage.h"

#include "registers.h"
#include "system.h"
#include "watchdog.h"

#include <ion/timing.h>

namespace {
constexpr uintptr_t USDHC = 0x02190000;
constexpr uintptr_t DSADDR = USDHC + 0x00;
constexpr uintptr_t BLKATTR = USDHC + 0x04;
constexpr uintptr_t CMDARG = USDHC + 0x08;
constexpr uintptr_t XFERTYP = USDHC + 0x0C;
constexpr uintptr_t PRSSTAT = USDHC + 0x24;
constexpr uintptr_t IRQSTAT = USDHC + 0x30;
constexpr uintptr_t MIXCTRL = USDHC + 0x48;

constexpr uint32_t PRSSTAT_DATA_LINE_ACTIVE = 1u << 2;
constexpr uint32_t PRSSTAT_CARD_INSERTED = 1u << 16;
constexpr uint32_t PRSSTAT_WRITE_ENABLED = 1u << 19;
constexpr uint32_t PRSSTAT_DATA0 = 1u << 24;
constexpr uint32_t PRSSTAT_INHIBIT = (1u << 0) | (1u << 1);

constexpr uint32_t IRQ_COMMAND_COMPLETE = 1u << 0;
constexpr uint32_t IRQ_TRANSFER_COMPLETE = 1u << 1;
constexpr uint32_t IRQ_ERROR_MASK = 0x117F0000;

constexpr uint32_t TRANSFER_DMA = 1u << 0;
constexpr uint32_t TRANSFER_READ = 1u << 4;
constexpr uint32_t COMMAND_RESPONSE_48 = 2u << 16;
constexpr uint32_t COMMAND_CRC_CHECK = 1u << 19;
constexpr uint32_t COMMAND_INDEX_CHECK = 1u << 20;
constexpr uint32_t COMMAND_DATA_PRESENT = 1u << 21;

#if PRIME_G2_EMULATOR
constexpr uint32_t MODE_BLOCK = PrimeG2::BlockStorage::PersistenceStartBlock +
  PrimeG2::BlockStorage::PersistenceBlockCount;
alignas(32) uint8_t sModeSector[PrimeG2::BlockStorage::BlockSize];
bool sReadOnlyRescue = false;
#endif

bool waitUntil(uintptr_t address, uint32_t mask, uint32_t expected,
               uint32_t timeoutMs) {
  uint64_t deadline = Ion::Timing::millis() + timeoutMs;
  while ((PrimeG2::reg32(address) & mask) != expected) {
    if (Ion::Timing::millis() >= deadline) {
      return false;
    }
  }
  return true;
}

bool transfer(bool write, uint32_t block, void *buffer) {
  using namespace PrimeG2;
  if (!waitUntil(PRSSTAT, PRSSTAT_INHIBIT | PRSSTAT_DATA_LINE_ACTIVE, 0,
                 1000)) {
    return false;
  }

  reg32(IRQSTAT) = 0xFFFFFFFF;
  if (write) {
    PrimeG2::System::cleanDataCacheRange(buffer,
      PrimeG2::BlockStorage::BlockSize);
  } else {
    PrimeG2::System::cleanInvalidateDataCacheRange(buffer,
      PrimeG2::BlockStorage::BlockSize);
  }
  reg32(DSADDR) = reinterpret_cast<uintptr_t>(buffer);
  reg32(BLKATTR) = (1u << 16) | BlockStorage::BlockSize;

  uint32_t transferMode = TRANSFER_DMA | (write ? 0 : TRANSFER_READ);
  reg32(MIXCTRL) = (reg32(MIXCTRL) & 0xFFFFFF80) | transferMode;

  /* The fixed 128 MiB QEMU card is SDSC, so command arguments are byte
   * addresses rather than SDHC sector numbers. */
  reg32(CMDARG) = block * BlockStorage::BlockSize;
  barrier();
  uint32_t command = write ? 24u : 17u;
  reg32(XFERTYP) = (command << 24) | COMMAND_DATA_PRESENT |
    COMMAND_INDEX_CHECK | COMMAND_CRC_CHECK | COMMAND_RESPONSE_48;

  uint64_t deadline = Ion::Timing::millis() + 2000;
  while (true) {
    uint32_t status = reg32(IRQSTAT);
    if (status & IRQ_ERROR_MASK) {
      reg32(IRQSTAT) = status;
      return false;
    }
    if ((status & (IRQ_COMMAND_COMPLETE | IRQ_TRANSFER_COMPLETE)) ==
        (IRQ_COMMAND_COMPLETE | IRQ_TRANSFER_COMPLETE)) {
      reg32(IRQSTAT) = status;
      barrier();
      if (!write) {
        PrimeG2::System::invalidateDataCacheRange(buffer,
          PrimeG2::BlockStorage::BlockSize);
      }
      PrimeG2::Watchdog::noteStorageProgress();
      return true;
    }
    if (Ion::Timing::millis() >= deadline) {
      return false;
    }
  }
}
}

namespace PrimeG2 {
namespace BlockStorage {

bool available() {
  return (reg32(PRSSTAT) & PRSSTAT_CARD_INSERTED) != 0;
}

void initializeMode() {
#if PRIME_G2_EMULATOR
  sReadOnlyRescue = false;
  if (!available() || !transfer(false, MODE_BLOCK, sModeSector)) {
    return;
  }
  sReadOnlyRescue = true;
  for (size_t i = 0; i < sizeof(sModeSector); i++) {
    if (sModeSector[i] != 0xA5) {
      sReadOnlyRescue = false;
      break;
    }
  }
#endif
}

bool writable() {
#if PRIME_G2_EMULATOR
  if (sReadOnlyRescue) {
    return false;
  }
#endif
  return available() && (reg32(PRSSTAT) & PRSSTAT_WRITE_ENABLED) != 0;
}

bool read(uint32_t block, void *buffer, size_t blockCount) {
  if (!available() || blockCount == 0 ||
      block < PersistenceStartBlock ||
      blockCount > PersistenceBlockCount ||
      block - PersistenceStartBlock > PersistenceBlockCount - blockCount) {
    return false;
  }
  uint8_t *cursor = static_cast<uint8_t *>(buffer);
  for (size_t i = 0; i < blockCount; i++) {
    if (!transfer(false, block + i, cursor + i * BlockSize)) {
      return false;
    }
  }
  return true;
}

bool write(uint32_t block, const void *buffer, size_t blockCount) {
  if (!writable() || blockCount == 0 ||
      block < PersistenceStartBlock ||
      blockCount > PersistenceBlockCount ||
      block - PersistenceStartBlock > PersistenceBlockCount - blockCount) {
    return false;
  }
  const uint8_t *cursor = static_cast<const uint8_t *>(buffer);
  for (size_t i = 0; i < blockCount; i++) {
    if (!transfer(true, block + i,
                  const_cast<uint8_t *>(cursor + i * BlockSize))) {
      return false;
    }
  }
  return flush();
}

bool flush() {
  barrier();
  return waitUntil(PRSSTAT, PRSSTAT_DATA_LINE_ACTIVE, 0, 2000) &&
    waitUntil(PRSSTAT, PRSSTAT_DATA0, PRSSTAT_DATA0, 2000);
}

}
}

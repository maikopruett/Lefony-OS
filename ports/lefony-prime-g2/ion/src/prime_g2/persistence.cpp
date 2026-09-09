#include "persistence.h"

#include "block_storage.h"

#include <ion.h>
#include <ion/internal_storage.h>
#include <ion/storage.h>
#include <ion/timing.h>
#include <stddef.h>
#include <string.h>

namespace Ion {
extern uint32_t staticStorageArea[];
}

extern "C" void prime_g2_preferences_factory_reset();
extern "C" void prime_g2_datasets_factory_reset();

namespace {
constexpr uint64_t Magic = 0x31524754534C484DULL; // "MHLSTGR1"
constexpr uint32_t Version = 1;
constexpr uint32_t Committed = 1;
constexpr uint32_t SlotBlocks = PrimeG2::BlockStorage::PersistenceBlockCount / 2;
constexpr size_t PayloadSize = Ion::InternalStorage::k_storageSize;
constexpr size_t PayloadBlocks = (PayloadSize + PrimeG2::BlockStorage::BlockSize - 1) /
  PrimeG2::BlockStorage::BlockSize;
constexpr size_t MaxRecords = 1024;
constexpr size_t MaxFullNameLength = 255;

struct Header {
  uint64_t magic;
  uint32_t version;
  uint32_t headerSize;
  uint64_t generation;
  uint32_t payloadLength;
  uint32_t payloadCRC;
  uint32_t headerCRC;
  uint32_t flags;
  uint32_t reserved[6];
};
static_assert(sizeof(Header) == 64, "Persistent storage header changed");
static_assert(PayloadBlocks + 1 < SlotBlocks, "Persistence slot is too small");

alignas(32) uint8_t sSector[PrimeG2::BlockStorage::BlockSize];
alignas(32) uint8_t sPayload[PayloadSize];
PrimeG2::Persistence::State sState = PrimeG2::Persistence::State::Unavailable;
int sActiveSlot = -1;
uint64_t sGeneration = 0;
uint32_t sLastCRC = 0;
uint32_t sObservedCRC = 0;
uint64_t sCommitAt = 0;
uint64_t sNextScanAt = 0;
uint32_t sCompatibleFields[6] = {};
bool sCommitInProgress = false;

uint8_t *storageBuffer() {
  return reinterpret_cast<uint8_t *>(Ion::staticStorageArea) + sizeof(uint32_t);
}

uint32_t slotStart(int slot) {
  return PrimeG2::BlockStorage::PersistenceStartBlock + slot * SlotBlocks;
}

uint32_t headerCRC(const Header &source) {
  Header copy = source;
  copy.headerCRC = 0;
  return Ion::crc32Byte(reinterpret_cast<const uint8_t *>(&copy), sizeof(copy));
}

uint16_t recordSizeAt(const uint8_t * payload, size_t offset) {
  return static_cast<uint16_t>(payload[offset]) |
    (static_cast<uint16_t>(payload[offset + 1]) << 8);
}

bool payloadFormatValid(const uint8_t * payload) {
  size_t offset = 0;
  size_t recordCount = 0;
  while (offset + sizeof(uint16_t) <= PayloadSize) {
    uint16_t recordSize = recordSizeAt(payload, offset);
    if (recordSize == 0) {
      return true;
    }
    if (++recordCount > MaxRecords || recordSize < sizeof(uint16_t) + 2 ||
        recordSize > PayloadSize - offset ||
        PayloadSize - offset - recordSize < sizeof(uint16_t)) {
      return false;
    }
    size_t nameStart = offset + sizeof(uint16_t);
    size_t nameLimit = offset + recordSize;
    size_t nameLength = 0;
    size_t dotCount = 0;
    while (nameStart + nameLength < nameLimit &&
           payload[nameStart + nameLength] != 0) {
      if (payload[nameStart + nameLength] == '.') {
        dotCount++;
      }
      nameLength++;
    }
    if (nameStart + nameLength == nameLimit ||
        nameLength > MaxFullNameLength || dotCount != 1) {
      return false;
    }
    offset += recordSize;
  }
  return false;
}

bool readHeader(int slot, Header *header) {
  if (!PrimeG2::BlockStorage::read(slotStart(slot), sSector)) {
    return false;
  }
  memcpy(header, sSector, sizeof(*header));
  return header->magic == Magic && header->version == Version &&
    header->headerSize == sizeof(Header) && header->flags == Committed &&
    header->payloadLength == PayloadSize &&
    header->headerCRC == headerCRC(*header);
}

bool loadPayload(int slot, const Header &header) {
  size_t remaining = PayloadSize;
  uint8_t *destination = sPayload;
  for (size_t i = 0; i < PayloadBlocks; i++) {
    if (!PrimeG2::BlockStorage::read(slotStart(slot) + 1 + i, sSector)) {
      return false;
    }
    size_t count = remaining < sizeof(sSector) ? remaining : sizeof(sSector);
    memcpy(destination, sSector, count);
    destination += count;
    remaining -= count;
  }
  return Ion::crc32Byte(sPayload, PayloadSize) == header.payloadCRC &&
    payloadFormatValid(sPayload);
}

bool writePayload(int slot) {
  size_t remaining = PayloadSize;
  const uint8_t *source = sPayload;
  for (size_t i = 0; i < PayloadBlocks; i++) {
    memset(sSector, 0, sizeof(sSector));
    size_t count = remaining < sizeof(sSector) ? remaining : sizeof(sSector);
    memcpy(sSector, source, count);
    if (!PrimeG2::BlockStorage::write(slotStart(slot) + 1 + i, sSector)) {
      return false;
    }
    source += count;
    remaining -= count;
  }
  return true;
}
}

namespace PrimeG2 {
namespace Persistence {

void init() {
#if PRIME_G2_EMULATOR
  BlockStorage::initializeMode();
  if (!BlockStorage::available()) {
    sState = State::Unavailable;
    Ion::Console::writeLine("Lefony storage: media unavailable");
    return;
  }

  Header headers[2] = {};
  bool valid[2] = {readHeader(0, &headers[0]), readHeader(1, &headers[1])};
  int first = valid[1] && (!valid[0] || headers[1].generation > headers[0].generation)
    ? 1 : 0;
  int second = 1 - first;

  if (valid[first] && loadPayload(first, headers[first])) {
    memcpy(storageBuffer(), sPayload, PayloadSize);
    sActiveSlot = first;
    sGeneration = headers[first].generation;
    sLastCRC = headers[first].payloadCRC;
    memcpy(sCompatibleFields, headers[first].reserved, sizeof(sCompatibleFields));
    sState = valid[second] ? State::Loaded : State::Recovered;
    Ion::Console::writeLine(sState == State::Loaded ?
      "Lefony storage: loaded" : "Lefony storage: recovered one valid slot");
  } else if (valid[second] && loadPayload(second, headers[second])) {
    memcpy(storageBuffer(), sPayload, PayloadSize);
    sActiveSlot = second;
    sGeneration = headers[second].generation;
    sLastCRC = headers[second].payloadCRC;
    memcpy(sCompatibleFields, headers[second].reserved, sizeof(sCompatibleFields));
    sState = State::Recovered;
    Ion::Console::writeLine("Lefony storage: recovered prior generation");
  } else {
    sState = State::Empty;
    memset(sCompatibleFields, 0, sizeof(sCompatibleFields));
    memset(storageBuffer(), 0, PayloadSize);
    sLastCRC = Ion::crc32Byte(storageBuffer(), PayloadSize);
    Ion::Console::writeLine("Lefony storage: initialized defaults");
  }
  sObservedCRC = sLastCRC;
  sCommitAt = 0;
  sNextScanAt = 0;
#else
  sState = State::Unavailable;
#endif
}

void poll() {
#if PRIME_G2_EMULATOR
  if (sState == State::Unavailable || sState == State::Error ||
      !BlockStorage::writable()) {
    return;
  }
  uint64_t now = Ion::Timing::millis();
  if (now < sNextScanAt) {
    return;
  }
  sNextScanAt = now + 100;
  uint32_t current = Ion::crc32Byte(storageBuffer(), PayloadSize);
  if (current != sObservedCRC) {
    sObservedCRC = current;
    sCommitAt = now + 1000;
    return;
  }
  if (current != sLastCRC && sCommitAt != 0 && now >= sCommitAt) {
    commit();
    sCommitAt = 0;
  }
#endif
}

bool commit() {
#if PRIME_G2_EMULATOR
  struct CommitScope {
    CommitScope() { sCommitInProgress = true; }
    ~CommitScope() { sCommitInProgress = false; }
  } scope;
  if (!BlockStorage::writable()) {
    return false;
  }
  memcpy(sPayload, storageBuffer(), PayloadSize);
  if (!payloadFormatValid(sPayload)) {
    sState = State::Error;
    Ion::Console::writeLine("Lefony storage: rejected invalid record metadata");
    return false;
  }
  uint32_t payloadCRC = Ion::crc32Byte(sPayload, PayloadSize);
  int target = sActiveSlot == 0 ? 1 : 0;

  memset(sSector, 0, sizeof(sSector));
  if (!BlockStorage::write(slotStart(target), sSector) ||
      !writePayload(target) || !BlockStorage::flush()) {
    sState = State::Error;
    return false;
  }

  Header header = {};
  header.magic = Magic;
  header.version = Version;
  header.headerSize = sizeof(Header);
  header.generation = sGeneration + 1;
  header.payloadLength = PayloadSize;
  header.payloadCRC = payloadCRC;
  header.flags = Committed;
  memcpy(header.reserved, sCompatibleFields, sizeof(header.reserved));
  header.headerCRC = headerCRC(header);
  memset(sSector, 0, sizeof(sSector));
  memcpy(sSector, &header, sizeof(header));
  if (!BlockStorage::write(slotStart(target), sSector) ||
      !BlockStorage::flush()) {
    sState = State::Error;
    return false;
  }

  sActiveSlot = target;
  sGeneration = header.generation;
  sLastCRC = payloadCRC;
  sObservedCRC = payloadCRC;
  sState = State::Loaded;
  return true;
#else
  return false;
#endif
}

bool commitInProgress() { return sCommitInProgress; }

bool factoryReset() {
#if PRIME_G2_EMULATOR
  Ion::Storage::sharedStorage()->destroyAllRecords();
  prime_g2_preferences_factory_reset();
  prime_g2_datasets_factory_reset();
  return commit() && commit();
#else
  return false;
#endif
}

#if PRIME_G2_EMULATOR
bool corruptActiveHeaderForTest() {
  if (sActiveSlot < 0) {
    return false;
  }
  memset(sSector, 0, sizeof(sSector));
  return BlockStorage::write(slotStart(sActiveSlot), sSector) &&
    BlockStorage::flush();
}

bool simulateInterruptedCommitForTest(unsigned phase) {
  if (phase > 3 || !BlockStorage::writable()) {
    return false;
  }
  memcpy(sPayload, storageBuffer(), PayloadSize);
  if (!payloadFormatValid(sPayload)) {
    return false;
  }
  uint32_t payloadCRC = Ion::crc32Byte(sPayload, PayloadSize);
  int target = sActiveSlot == 0 ? 1 : 0;

  memset(sSector, 0, sizeof(sSector));
  if (!BlockStorage::write(slotStart(target), sSector)) {
    return false;
  }
  if (phase == 0) {
    return BlockStorage::flush();
  }

  size_t stopBlock = phase == 1 ? PayloadBlocks / 2 : PayloadBlocks;
  size_t remaining = PayloadSize;
  const uint8_t *source = sPayload;
  for (size_t i = 0; i < stopBlock; i++) {
    memset(sSector, 0, sizeof(sSector));
    size_t count = remaining < sizeof(sSector) ? remaining : sizeof(sSector);
    memcpy(sSector, source, count);
    if (!BlockStorage::write(slotStart(target) + 1 + i, sSector)) {
      return false;
    }
    source += count;
    remaining -= count;
  }
  if (phase <= 2) {
    return BlockStorage::flush();
  }

  Header header = {};
  header.magic = Magic;
  header.version = Version;
  header.headerSize = sizeof(Header);
  header.generation = sGeneration + 1;
  header.payloadLength = PayloadSize;
  header.payloadCRC = payloadCRC;
  header.flags = Committed;
  memcpy(header.reserved, sCompatibleFields, sizeof(header.reserved));
  header.headerCRC = headerCRC(header);
  memset(sSector, 0, sizeof(sSector));
  memcpy(sSector, &header, sizeof(header));
  return BlockStorage::write(slotStart(target), sSector);
}

bool setCompatibleFieldForTest(unsigned index, uint32_t value) {
  if (index >= sizeof(sCompatibleFields) / sizeof(sCompatibleFields[0])) {
    return false;
  }
  sCompatibleFields[index] = value;
  return true;
}

bool getCompatibleFieldForTest(unsigned index, uint32_t *value) {
  if (index >= sizeof(sCompatibleFields) / sizeof(sCompatibleFields[0]) ||
      value == nullptr) {
    return false;
  }
  *value = sCompatibleFields[index];
  return true;
}

bool validatePayloadForTest(const uint8_t *data, size_t size) {
  if (data == nullptr || size > PayloadSize) {
    return false;
  }
  memset(sPayload, 0, sizeof(sPayload));
  memcpy(sPayload, data, size);
  return payloadFormatValid(sPayload);
}
#endif

State state() {
  return sState;
}

uint64_t generation() {
  return sGeneration;
}

}
}

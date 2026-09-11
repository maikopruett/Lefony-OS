// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_STORAGE_H
#define LEFONY_APP_STORAGE_H
#include <stdint.h>
#include <stddef.h>
namespace PrimeG2 { namespace AppStorage {
// Profile 1 intentionally retires stock UBI bytes [432 MiB,496 MiB).
// Never overlaps mtd1, A/B metadata, the reserved rescue area or Linux BBT.
constexpr uint32_t FirstBlock=3456, BlockCount=512, PageBytes=2048, PagesPerBlock=64;
constexpr unsigned Slots=8, BankBlocks=31;
constexpr uint32_t MaximumPackage=2101664, MaximumData=65536;
struct Backend {
  void *context;
  bool (*usable)(void *,uint32_t block);
  bool (*read)(void *,uint32_t page,uint8_t *data);
  bool (*erase)(void *,uint32_t block);
  bool (*program)(void *,uint32_t page,const uint8_t *data);
};
enum class State : uint32_t { Unprovisioned, Ready, Erasing, Writing, Verifying, Committing, Complete, Failed };
struct Entry { uint32_t generation, packageBytes, dataBytes; int bank; };
class Volume {
public:
  explicit Volume(Backend backend);
  bool mount();
  // Caller must independently establish a complete, durable raw backup and
  // compare its SHA-256 with the device's sequential backup receipt first.
  // This method only provisions a previously unprovisioned volume.
  bool provision(const uint8_t backupSHA256[32]);
  bool read(unsigned slot,uint8_t *package,size_t capacity,uint8_t *data,size_t dataCapacity);
  // Buffer ownership stays with the caller until Complete/Failed. Package and
  // data are committed together; packageBytes=0,dataBytes=0 is a tombstone.
  bool begin(unsigned slot,const uint8_t *package,uint32_t packageBytes,const uint8_t *data,uint32_t dataBytes);
  void step(); // at most one NAND erase/program/readback operation
  void cancel(); // never touches the active bank
  State state() const { return m_state; }
  const Entry &entry(unsigned slot) const { return m_entries[slot<Slots?slot:0]; }
  const uint8_t *identity() const { return m_identity; }
  uint32_t progress() const { return m_cursor; }
private:
  bool readHeader(unsigned slot,unsigned bank,uint8_t *header);
  bool checkPayload(const uint8_t *header,uint8_t *package=nullptr,uint8_t *data=nullptr);
  bool validMarker(const uint8_t *page) const;
  bool writeChecked(uint32_t page,const uint8_t *data);
  uint32_t payloadPage(const uint8_t *header,uint32_t index) const;
  void makePage(uint32_t index,uint8_t *out) const;
  Backend m_backend;
  State m_state;
  Entry m_entries[Slots];
  uint8_t m_identity[32],m_header[PageBytes],m_scratch[PageBytes];
  const uint8_t *m_package,*m_data;
  uint32_t m_cursor,m_pages,m_packageBytes,m_dataBytes;
  unsigned m_slot;
};
}}
#endif

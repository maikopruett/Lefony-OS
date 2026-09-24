#include "nand_physical.h"
#include "storage_profile.h"
#include "app_storage.h"
#include "registers.h"
#include "system.h"
#include <ion/timing.h>
#include <string.h>

namespace {
using namespace PrimeG2;
using NANDPhysical::Error;
// i.MX6 APBH channel 0, not the mx23 channel-4 layout. Register/descriptor
// contract cross-checked against the known-working c1f67 Prime U-Boot:
// drivers/mtd/nand/mxs_nand.c, drivers/dma/apbh_dma.c, regs-apbh.h.
constexpr uintptr_t APBH = 0x01804000;
constexpr uintptr_t Next = APBH + 0x110, Semaphore = APBH + 0x140;
struct alignas(64) Descriptor { uint32_t next, command, buffer, pio[6]; };
Descriptor sDescriptor;
Descriptor sChain[4];
alignas(64) uint8_t sPage[2048];
alignas(64) uint8_t sAux[64];
NANDPhysical::PageReport sPageReport = {};
alignas(64) uint8_t sCommand[64];
alignas(64) uint8_t sData[64];
NANDPhysical::Report sReport = {};

void snapshot() {
  sReport.apbhControl = reg32(APBH);
  sReport.apbhIRQ = reg32(APBH + 0x10);
  sReport.apbhError = reg32(APBH + 0x20);
  sReport.semaphore = reg32(Semaphore);
  sReport.gpmiControl = reg32(GPMI);
  sReport.gpmiControl1 = reg32(GPMI + 0x60);
  sReport.gpmiTiming0 = reg32(GPMI + 0x70);
  sReport.gpmiTiming1 = reg32(GPMI + 0x80);
  sReport.gpmiStatus = reg32(GPMI + 0xB0);
  sReport.bchLayout0 = reg32(BCH + 0x80);
  sReport.bchLayout1 = reg32(BCH + 0x90);
  sReport.bchSelect = reg32(BCH + 0x70);
}
bool fail(Error error) {
  sReport.error = static_cast<uint32_t>(error);
  snapshot();
  return false;
}
bool transfer(bool read, uint32_t commandLength = 2, uint8_t *destination = nullptr, uint32_t readLength = 8) {
  StorageProfile::Scope profile(StorageProfile::Metric::CommandDMA,read?readLength:commandLength);
  if (readLength > 2112) return false;
  memset(&sDescriptor, 0, sizeof(sDescriptor));
  const uint32_t length = read ? readLength : commandLength;
  uint8_t *readBuffer = destination ? destination : sData;
  // DMA_WRITE means peripheral -> memory in APBH terminology.
  sDescriptor.command = (read ? 1u : 2u) | (1u << 3) | (1u << 6) |
    (1u << 7) | ((read && !destination ? 1u : 3u) << 12) | (length << 16);
  sDescriptor.buffer = reinterpret_cast<uintptr_t>(read ? readBuffer : sCommand);
  sDescriptor.pio[0] = (read ? (1u << 24) : ((1u << 17) | (1u << 16))) |
    (1u << 23) | length;
  System::cleanInvalidateDataCacheRange(readBuffer, destination ? readLength : sizeof(sData));
  System::cleanDataCacheRange(sCommand, sizeof(sCommand));
  System::cleanDataCacheRange(&sDescriptor, sizeof(sDescriptor));
  reg32(APBH + 0x18) = 1; // acknowledge only channel 0
  reg32(APBH + 0x28) = 1;
  barrier();
  reg32(Next) = reinterpret_cast<uintptr_t>(&sDescriptor);
  reg32(Semaphore) = 1;
  reg32(APBH + 0x08) = 1; // ungate channel 0 only
  barrier();
  for (unsigned attempt = 0; attempt < 2000; ++attempt) {
    if (reg32(APBH + 0x20) & 1u) break;
    if ((reg32(APBH + 0x10) & 1u) && !(reg32(Semaphore) & 0xff0000u)) {
      System::invalidateDataCacheRange(readBuffer, destination ? readLength : sizeof(sData));
      return profile.result(true);
    }
    Ion::Timing::usleep(10);
  }
  Error error = (reg32(APBH + 0x20) & 1u) ? Error::DMA : Error::Timeout;
  fail(error); // capture before resetting the DMA channel, never the NAND
  reg32(APBH + 0x34) = 1u << 16;
  barrier();
  return false;
}
}

namespace PrimeG2 { namespace NANDPhysical {
bool probe() {
  sReport = {};
  sReport.magic = 0x31504e4c; // LNP1
  sReport.version = 1;
  snapshot();
  // Inherit known-good mux/timing/BCH setup from NAND boot. Do not guess a
  // new clock, pinmux or ECC layout. No peripheral-wide reset is performed.
  if ((sReport.apbhControl | sReport.gpmiControl) & 0xc0000000u)
    return fail(Error::ClockOrReset);
  if ((sReport.semaphore & 0xff0000u) || (sReport.gpmiControl & (1u << 29)))
    return fail(Error::Busy);
  memset(sData, 0, sizeof(sData));
  sCommand[0] = 0x90; // READID; page reads below use only READ0/READSTART
  sCommand[1] = 0;
  sReport.phase = 1;
  if (!transfer(false)) return false;
  sReport.phase = 2;
  if (!transfer(true)) return false;
  memcpy(sReport.id, sData, sizeof(sReport.id));
  if (sData[0] == 0 || sData[0] == 0xff) return fail(Error::InvalidID);
  sReport.phase = 3;
  snapshot();
  return true;
}
const Report &report() { return sReport; }
const PageReport &pageReport() { return sPageReport; }
const uint8_t *pageData() { return sPageReport.ready ? sPage : nullptr; }
namespace {
bool writableGeometry() {
  snapshot();
  return sReport.bchLayout0 == 0x030a0880 && sReport.bchLayout1 == 0x08400880 &&
    !(sReport.bchSelect & 3u) &&
    !((sReport.apbhControl | sReport.gpmiControl | reg32(BCH)) & 0xc0000000u) &&
    !(sReport.semaphore & 0xff0000u) && !(sReport.gpmiControl & (1u << 29));
}
bool readyStatus(StorageProfile::Metric metric=StorageProfile::Metric::OtherReady) {
  StorageProfile::Scope profile(metric);
  for (unsigned i = 0; i < 50000; ++i) {
    if (reg32(GPMI + 0xb0) & (1u << 24)) {
      sCommand[0] = 0x70; // READSTATUS, require READY and write-protect released
      return profile.result(transfer(false, 1) && transfer(true) && (sData[0] & 0xc1) == 0xc0);
    }
    Ion::Timing::usleep(10);
  }
  return false;
}
}
static bool appBlock(uint32_t block) { return block >= AppStorage::FirstBlock && block < AppStorage::FirstBlock + AppStorage::BlockCount; }
static bool usableInRange(uint32_t block, bool app) {
  if ((app ? !appBlock(block) : (block < 32 || block >= 96)) || !writableGeometry()) return false;
  for (uint32_t page = block * 64; page < block * 64 + 2; ++page) {
    sCommand[0] = 0x00; sCommand[1] = 0; sCommand[2] = 8; // raw OOB column 2048
    sCommand[3] = page; sCommand[4] = page >> 8; sCommand[5] = page >> 16;
    if (!transfer(false, 6)) return false;
    sCommand[0] = 0x30;
    if (!transfer(false, 1)) return false;
    bool ready = false;
    for (unsigned i = 0; i < 5000; ++i) {
      if (reg32(GPMI + 0xb0) & (1u << 24)) { ready = true; break; }
      Ion::Timing::usleep(10);
    }
    if (!ready || !transfer(true) || sData[0] != 0xff) return false;
  }
  return readyStatus();
}
static bool eraseInRange(uint32_t block, bool app) {
  if ((app ? !appBlock(block) : (block < 32 || block >= 96)) || !writableGeometry()) return false;
  uint32_t page = block * 64;
  sCommand[0] = 0x60; sCommand[1] = page;
  sCommand[2] = page >> 8; sCommand[3] = page >> 16;
  if (!transfer(false, 4)) return false;
  sCommand[0] = 0xd0;
  return transfer(false, 1) && readyStatus(StorageProfile::Metric::EraseWait);
}
static bool programInRange(uint32_t page, const uint8_t *data, bool app) {
  if ((app ? !appBlock(page / 64) : (page < 2048 || page >= 6144)) || !data || !writableGeometry()) return false;
  sCommand[0] = 0x80; sCommand[1] = sCommand[2] = 0;
  sCommand[3] = page; sCommand[4] = page >> 8; sCommand[5] = page >> 16;
  if (!transfer(false, 6)) return false;
  memcpy(sPage, data, sizeof(sPage));
  memset(sAux, 0xff, sizeof(sAux));
  uint16_t pair = uint16_t(sPage[2028]) | (uint16_t(sPage[2029]) << 8);
  sAux[0] = (pair >> 2) & 0xff;
  pair |= 0xffu << 2; // preserve the physical bad-block marker as erased
  sPage[2028] = pair; sPage[2029] = pair >> 8;
  memset(&sDescriptor, 0, sizeof(sDescriptor));
  sDescriptor.command = (1u << 3) | (1u << 6) | (1u << 7) | (6u << 12);
  sDescriptor.pio[0] = 1u << 23;
  sDescriptor.pio[2] = 0x31ff; // BCH encode
  sDescriptor.pio[3] = 2112;
  sDescriptor.pio[4] = reinterpret_cast<uintptr_t>(sPage);
  sDescriptor.pio[5] = reinterpret_cast<uintptr_t>(sAux);
  System::cleanDataCacheRange(sPage, sizeof(sPage));
  System::cleanDataCacheRange(sAux, sizeof(sAux));
  System::cleanDataCacheRange(&sDescriptor, sizeof(sDescriptor));
  reg32(BCH + 8) = 1;
  reg32(APBH + 0x18) = 1; reg32(APBH + 0x28) = 1;
  barrier();
  reg32(Next) = reinterpret_cast<uintptr_t>(&sDescriptor);
  reg32(Semaphore) = 1; reg32(APBH + 8) = 1;
  barrier();
  bool complete = false;
  for (unsigned i = 0; i < 5000; ++i) {
    if (reg32(APBH + 0x20) & 1u) break;
    if ((reg32(APBH + 0x10) & 1u) && !(reg32(Semaphore) & 0xff0000u) &&
        (reg32(BCH) & 1u)) { complete = true; break; }
    Ion::Timing::usleep(10);
  }
  if (!complete) {
    reg32(APBH + 0x34) = 1u << 16; barrier(); return false;
  }
  reg32(GPMI + 0x20) = 0; // disable ECC before command-mode traffic
  sCommand[0] = 0x10; // PAGEPROG
  return transfer(false, 1) && readyStatus(StorageProfile::Metric::ProgramWait);
}
static bool readInRange(uint32_t page, bool app) {
  sPageReport = {0x3152504c, page, 0, 0, 0, 0}; // LPR1
  auto reject = [](Error error) {
    sPageReport.error = static_cast<uint32_t>(error);
    return false;
  };
  // Qualification is restricted to the existing 4..12 MiB OS slot.
  if (app ? !appBlock(page / 64) : (page < 2048 || page >= 6144)) return reject(Error::Range);
  snapshot();
  // Exact physically captured BCH layout: four 512-byte GF13 chunks,
  // strength 2, ten metadata bytes, 2112 physical bytes. Never reconfigure
  // ECC based on a guessed geometry or use synthetic emulator NAND registers.
  if (sReport.bchLayout0 != 0x030a0880 || sReport.bchLayout1 != 0x08400880 ||
      (sReport.bchSelect & 3u)) return reject(Error::Geometry);
  if ((sReport.apbhControl | sReport.gpmiControl | reg32(BCH)) & 0xc0000000u)
    return reject(Error::ClockOrReset);
  if ((sReport.semaphore & 0xff0000u) || (sReport.gpmiControl & (1u << 29)))
    return reject(Error::Busy);
  sCommand[0] = 0x00; // READ0 + column zero + three row cycles
  sCommand[1] = sCommand[2] = 0;
  sCommand[3] = page; sCommand[4] = page >> 8; sCommand[5] = page >> 16;
  if (!transfer(false, 6)) return reject(static_cast<Error>(sReport.error));
  sCommand[0] = 0x30; // READSTART
  if (!transfer(false, 1)) return reject(static_cast<Error>(sReport.error));
  memset(sChain, 0, sizeof(sChain));
  memset(sPage, 0, sizeof(sPage));
  memset(sAux, 0xfe, sizeof(sAux)); // untouched status is failure, never success
  const uint32_t wait = (3u << 24) | (1u << 23);
  sChain[0].command = (1u << 2) | (1u << 5) | (1u << 7) | (1u << 12);
  sChain[0].pio[0] = wait;
  sChain[1].command = (1u << 2) | (1u << 7) | (6u << 12);
  sChain[1].pio[0] = (1u << 24) | (1u << 23) | 2112;
  sChain[1].pio[2] = 0x11ff; // BCH decode, all payload and auxiliary buffers
  sChain[1].pio[3] = 2112;
  sChain[1].pio[4] = reinterpret_cast<uintptr_t>(sPage);
  sChain[1].pio[5] = reinterpret_cast<uintptr_t>(sAux);
  sChain[2].command = (1u << 2) | (1u << 5) | (1u << 7) | (3u << 12);
  sChain[2].pio[0] = wait | 2112; // pio[2] clears ECC after transfer
  sChain[3].command = (1u << 3) | (1u << 6);
  for (unsigned i = 0; i < 3; ++i)
    sChain[i].next = reinterpret_cast<uintptr_t>(&sChain[i + 1]);
  System::cleanInvalidateDataCacheRange(sPage, sizeof(sPage));
  System::cleanInvalidateDataCacheRange(sAux, sizeof(sAux));
  System::cleanDataCacheRange(sChain, sizeof(sChain));
  reg32(BCH + 8) = 1; // clear stale BCH completion before starting
  reg32(APBH + 0x18) = 1; reg32(APBH + 0x28) = 1;
  barrier();
  reg32(Next) = reinterpret_cast<uintptr_t>(sChain);
  reg32(Semaphore) = 1; reg32(APBH + 8) = 1;
  barrier();
  bool dmaDone = false, bchDone = false;
  for (unsigned attempt = 0; attempt < 5000; ++attempt) {
    if (reg32(APBH + 0x20) & 1u) break;
    dmaDone = (reg32(APBH + 0x10) & 1u) && !(reg32(Semaphore) & 0xff0000u);
    bchDone = reg32(BCH) & 1u;
    if (dmaDone && bchDone) break;
    Ion::Timing::usleep(10);
  }
  if (!dmaDone || !bchDone || (reg32(APBH + 0x20) & 1u)) {
    Error error = (reg32(APBH + 0x20) & 1u) ? Error::DMA :
      (dmaDone ? Error::BCHTimeout : Error::Timeout);
    reg32(APBH + 0x34) = 1u << 16;
    barrier();
    return reject(error);
  }
  System::invalidateDataCacheRange(sPage, sizeof(sPage));
  System::invalidateDataCacheRange(sAux, sizeof(sAux));
  // Four status bytes at aligned metadata offset 12. Fail closed on erased
  // or uncorrectable chunks during installed-image qualification.
  for (unsigned i = 0; i < 4; ++i) {
    uint8_t status = sAux[12 + i];
    if (status > 2) return reject(Error::Uncorrectable);
    sPageReport.corrected += status;
  }
  // Undo GPMI block-marker swapping exactly as the existing U-Boot does.
  // (2048*8 - 10*8) - 3*(2*13) = 16226 bits => byte 2028, bit 2.
  uint16_t pair = uint16_t(sPage[2028]) | (uint16_t(sPage[2029]) << 8);
  sPageReport.marker = (pair >> 2) & 0xff;
  pair = (pair & ~(0xffu << 2)) | (uint16_t(sAux[0]) << 2);
  sPage[2028] = pair; sPage[2029] = pair >> 8;
  sPageReport.ready = 1;
  return true;
}
bool blockUsable(uint32_t block) { return StorageProfile::measure(StorageProfile::Metric::Usable,0,[&] {return usableInRange(block,false);}); }
bool eraseOSBlock(uint32_t block) { return StorageProfile::measure(StorageProfile::Metric::Erase,131072,[&] {return eraseInRange(block,false);}); }
bool programOSPage(uint32_t page,const uint8_t *data) { return StorageProfile::measure(StorageProfile::Metric::Program,2048,[&] {return programInRange(page,data,false);}); }
bool readPage(uint32_t page) { return StorageProfile::measure(StorageProfile::Metric::Read,2048,[&] {return readInRange(page,false);}); }
bool appBlockUsable(uint32_t block) { return StorageProfile::measure(StorageProfile::Metric::Usable,0,[&] {return usableInRange(block,true);}); }
bool eraseAppBlock(uint32_t block) { return StorageProfile::measure(StorageProfile::Metric::Erase,131072,[&] {return eraseInRange(block,true);}); }
bool programAppPage(uint32_t page,const uint8_t *data) { return StorageProfile::measure(StorageProfile::Metric::Program,2048,[&] {return programInRange(page,data,true);}); }
bool readAppPage(uint32_t page) { return StorageProfile::measure(StorageProfile::Metric::Read,2048,[&] {return readInRange(page,true);}); }
bool readRawAppPage(uint32_t page,uint8_t *destination) {
  StorageProfile::Scope profile(StorageProfile::Metric::RawRead,2112);
  if(!destination || !appBlock(page / 64) || !writableGeometry()) return false;
  sCommand[0]=0; sCommand[1]=sCommand[2]=0;
  sCommand[3]=page; sCommand[4]=page>>8; sCommand[5]=page>>16;
  if(!transfer(false,6)) return false;
  sCommand[0]=0x30;
  if(!transfer(false,1)) return false;
  for(unsigned i=0;i<5000;i++) {
    if(reg32(GPMI+0xb0)&(1u<<24)) return profile.result(transfer(true,2,destination,2112));
    Ion::Timing::usleep(10);
  }
  return false;
}
} }

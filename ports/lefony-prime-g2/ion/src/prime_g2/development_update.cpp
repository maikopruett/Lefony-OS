#include "development_update.h"
#include "nand_physical.h"
#include "watchdog.h"
#include <ion.h>
#include <string.h>
namespace PrimeG2 { namespace DevelopmentUpdate {
namespace {
Status s = {0x3155444c, 1, Idle, 0, 0, 0, 0, 0};
const uint8_t *sImage = nullptr;
uint32_t sBlocks = 0, sCursor = 0;
alignas(64) uint8_t sPage[2048];
void fail(uint32_t error) { s.error = error; s.state = Failed; }
}
const Status &status() { return s; }
bool busy() { return s.state >= Checking && s.state <= Verifying; }
void clearResult() { if (!busy()) s = {0x3155444c, 1, Idle, 0, 0, 0, 0, 0}; }
bool begin(const uint8_t *image, size_t length, uint32_t crc) {
  if (busy()) return false;
  if (!image || length < 0x30 || length > 8u*1024*1024) return false;
  uint32_t magic, bytes;
  memcpy(&magic, image+0x24, 4); memcpy(&bytes, image+0x2c, 4);
  if (magic != 0x016f2818 || bytes != length || Ion::crc32Byte(image,length) != crc)
    return false;
  s = {0x3155444c, 1, Checking, 0, uint32_t(length), 0, 0, crc};
  sImage = image; sCursor = 0; sBlocks = (length + 131071) / 131072;
  return true;
}
void poll() {
  if (!busy()) return;
  Watchdog::noteStorageProgress();
  if (s.state == Checking) {
    if (!NANDPhysical::blockUsable(32+sCursor)) { fail(1); return; }
    if (++sCursor == sBlocks) { sCursor=0; s.state=Erasing; }
  } else if (s.state == Erasing) {
    s.changed=1; // a failed command may still have changed NAND
    if (!NANDPhysical::eraseOSBlock(32+sCursor)) { fail(2); return; }
    if (++sCursor == sBlocks) { sCursor=0; s.state=Writing; s.done=0; }
  } else if (s.state == Writing) {
    uint32_t amount=s.total-sCursor;
    if (amount>2048) amount=2048;
    memset(sPage,0xff,sizeof(sPage)); memcpy(sPage,sImage+sCursor,amount);
    if (!NANDPhysical::programOSPage(2048+sCursor/2048,sPage)) { fail(3); return; }
    sCursor+=amount; s.done=sCursor;
    if (sCursor==s.total) { sCursor=0; s.done=0; s.state=Verifying; }
  } else if (s.state == Verifying) {
    uint32_t amount=s.total-sCursor;
    if (amount>2048) amount=2048;
    if (!NANDPhysical::readPage(2048+sCursor/2048) ||
        memcmp(NANDPhysical::pageData(),sImage+sCursor,amount)) { fail(4); return; }
    sCursor+=amount; s.done=sCursor;
    if (sCursor==s.total) s.state=Complete;
  }
  Watchdog::noteStorageProgress();
}
} }

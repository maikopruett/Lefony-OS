// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DEVELOPER_KEY_WIRE_H
#define LEFONY_APP_DEVELOPER_KEY_WIRE_H
#include <stdint.h>
namespace PrimeG2 { namespace AppDeveloperKeys {
// Additive host-only protocol. No app SVC or firmware-update authority.
enum class Operation : uint32_t { None=0, Enroll=1, Revoke=2, RecoverInstall=3, Remove=4, Repair=5,
  BackupUnreadable=6, RepairUnreadable=7 };
enum class State : uint32_t { Idle=0, AwaitAck=1, Preparing=2, AwaitUser=3, Working=4,
  Complete=5, Cancelled=6, Denied=7, Expired=8, Failed=9 };
enum class Error : uint32_t { None=0, Invalid=1, Stale=2, Full=3, Registry=4,
  Busy=5, ProtectedKey=6, Missing=7, Io=8, Uncertain=9, Overflow=10, Package=11, Ownership=12, KeyInUse=13, KeyActive=14, Readable=15 };
struct Request {
  uint32_t size,schema;Operation operation;uint32_t serial;
  uint8_t nonce[16],id[32],modulus[256];char label[32];uint32_t reserved[8];
};
struct Control { uint32_t size,schema,sequence,reserved;uint8_t nonce[16]; };
struct Status {
  uint32_t magic=0x534b464c,size=160,schema=1;State state=State::Idle;
  Operation operation=Operation::None;Error error=Error::None;uint32_t sequence=0,registry=0;
  uint32_t serial=0,count=0,maximum=8,unavailableApps=0;
  uint8_t nonce[16]{},id[32]{};char label[32]{};uint32_t reserved[8]{};
};
struct KeyInfo {
  uint32_t magic=0x494b464c,size=352,schema=1,index=0,serial=0,state=0,reserved[2]{};
  uint8_t id[32]{},modulus[256]{};char label[32]{};
};
// Request/Status reserved bytes hold the exact package SHA-256 only for
// RecoverInstall, the exact damaged-registry SHA-256 for Repair, or the complete
// partial-backup SHA-256 for RepairUnreadable. BackupUnreadable has zero id,
// modulus, label, serial and reserved bytes; it grants no key authority.
// All other operations still require these bytes to be zero.
struct RecoveryInfo {
  uint32_t magic=0x524b464c,size=192,schema=1,sequence=0,serial=0,generation=0,reserved[2]{};
  char appId[64]{},version[32]{};uint8_t oldSigner[32]{},packageHash[32]{};
};
struct DamageInfo {
  uint32_t magic=0x444b464c,size=64,schema=1,bytes=0,reserved[4]{};
  uint8_t hash[32]{};
};
struct UnreadableInfo {
  uint32_t magic=0x554b464c,size=96,schema=1,sequence=0;
  uint32_t originalBytes=0,bytes=0,readableBytes=0,unreadableChunks=0;
  uint8_t nonce[16]{},hash[32]{};uint32_t reserved[4]{};
};
static_assert(sizeof(Request)==384 && sizeof(Control)==32 && sizeof(Status)==160 && sizeof(KeyInfo)==352 && sizeof(RecoveryInfo)==192 && sizeof(DamageInfo)==64,"developer key wire contract");
static_assert(sizeof(UnreadableInfo)==96,"unreadable developer-key snapshot contract");
}}
#endif

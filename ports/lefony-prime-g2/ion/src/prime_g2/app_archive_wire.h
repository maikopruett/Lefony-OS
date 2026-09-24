// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_WIRE_H
#define LEFONY_APP_ARCHIVE_WIRE_H
#include <stdint.h>
namespace PrimeG2 { namespace AppArchive {
enum class Operation:uint32_t { Inspect=1,Export=2,Restore=3 };
enum class TransferState:uint32_t { Idle,Working,Readable,Writable,Ready,Complete,Failed,Cancelled,AwaitUser };
enum class TransferError:uint32_t { None,Invalid,Busy,Missing,Changed,Authority,Version,Quota,Space,Integrity,IO,Cancelled,Timeout,Uncertain,Exists,Schema,Denied };
enum:uint32_t { Replace=1,AllowRecoveryPair=2,RepairCode=4,InspectRoot=8,Committed=1,CommitUncertain=2,RecoveryPair=4,CodeRepair=8,
  Exists=1,IndexKnown=2,Pending=4,CodeUnavailable=8,Legacy=16,PrefixKnown=32,
  RootReplicated=64,RootPayloadValid=128,RootAttributeValid=256 };
// Root health bits are returned only for InspectRoot requests (hello 32768).
// Existing clients keep the original 192/256-byte records and flag meanings.
struct Request {
  uint32_t size,schema;Operation operation;uint32_t flags,generation,length,reserved[2];
  char id[64];uint8_t digest[32],nonce[16];
};
struct TransferStatus {
  uint32_t magic=0x5241464c,size=112,schema=1;TransferState state=TransferState::Idle;
  Operation operation=Operation::Inspect;TransferError error=TransferError::None;
  uint32_t sequence=0,offset=0,length=0,available=0,generation=0,flags=0,chunkBytes=488,reserved[3]{};
  uint8_t digest[32]{},nonce[16]{};
};
struct Info {
  uint32_t size=192,schema=1,flags=0,generation=0,version[3]{},appSchema=0,dataSchema=0;
  uint32_t highVersion[3]{},privateBytes=0,namedBytes=0,quota=0,packageBytes=0;
  uint8_t packageHash[32]{},signer[32]{};char id[64]{};
};
static_assert(sizeof(Request)==144 && sizeof(TransferStatus)==112 && sizeof(Info)==192,"archive host wire records");
// Only explicit repair inspection returns schema 2. Unknown signed metadata is
// zero, never inferred from the unsigned namespace record.
struct RepairInfo {
  Info info{};
  uint8_t legacyHash[32]{},prefixHash[32]{};
};
static_assert(sizeof(RepairInfo)==256,"archive repair information");
// Full verified identities shown by the OS before a fresh cross-signer restore.
struct ApprovalInfo {
  uint32_t size=216,schema=1,sequence=0,reserved=0,version[3]{},previousVersion[3]{};
  char id[64]{};
  uint8_t currentSigner[32]{},previousSigner[32]{},digest[32]{},nonce[16]{};
};
static_assert(sizeof(ApprovalInfo)==216,"archive approval record");
}}
#endif

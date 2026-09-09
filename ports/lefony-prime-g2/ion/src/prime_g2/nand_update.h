#ifndef ION_PRIME_G2_NAND_UPDATE_H
#define ION_PRIME_G2_NAND_UPDATE_H

#include <stddef.h>
#include <stdint.h>

namespace PrimeG2 {
namespace NANDUpdate {

constexpr uint32_t ManifestMagic = 0x3155464c;
constexpr uint32_t StatusMagic = 0x31554241;
constexpr size_t SignedPrefixBytes = 64;
constexpr size_t SignatureBytes = 256;
constexpr size_t ManifestBytes = SignedPrefixBytes + SignatureBytes;
constexpr uint32_t FlagManifestAuthenticated = 1u << 0;
constexpr uint32_t FlagPayloadAuthenticated = 1u << 1;
constexpr uint32_t FlagSlotCommitted = 1u << 2;
constexpr uint32_t FlagDirectInstall = 1u << 8;
constexpr uint32_t FlagRecoveryInstall = 1u << 9;

enum class State : uint32_t { Idle, ManifestReady, CapsuleReady, Installing,
                              PendingReboot, Confirmed, Error };
enum class Error : uint32_t {
  None, ManifestLength, ManifestFormat, WrongModel, VersionRejected,
  SignatureRejected, CapsuleMismatch, LayoutNotProvisioned, GeometryMismatch,
  NoMetadataBlock, SlotCapacity, EraseFailed, ProgramFailed, ReadbackFailed,
  MetadataCommitFailed, NoPendingSlot, PendingUpdateExists,
};

struct __attribute__((packed)) Manifest {
  uint32_t magic;
  uint16_t schema;
  uint16_t headerBytes;
  uint32_t model;
  uint32_t version[4];
  uint32_t payloadBytes;
  uint8_t payloadSHA256[32];
  uint8_t signature[SignatureBytes];
};
static_assert(sizeof(Manifest) == ManifestBytes, "signed update manifest changed");

struct Status {
  uint32_t magic, protocol, state, error, activeSlot, pendingSlot, attempts,
    bootLimit, version[4], totalBytes, writtenBytes, generation, flags;
};
static_assert(sizeof(Status) == 64, "USB A/B status must remain one EP0 page");

void init();
bool acceptManifest(const void *data, size_t length);
bool noteCapsuleReady(const uint8_t *payload, size_t length);
bool install(const uint8_t *payload, size_t length);
bool confirmBootIfReady();
bool confirmPending();
void abort();
const Status &status();

}
}

#endif

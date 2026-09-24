// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DEVELOPER_KEYS_H
#define LEFONY_APP_DEVELOPER_KEYS_H
#include "littlefs/lfs.h"
#include "native_app_digest.h"

namespace PrimeG2 { namespace AppDeveloperKeys {
class Snapshot;
constexpr unsigned MaximumKeys=8, LabelBytes=32;
constexpr unsigned HeaderBytes=64, RecordBytes=336, WireBytes=HeaderBytes+MaximumKeys*RecordBytes;
enum class KeyState : uint32_t { Active=1, Revoked=2 };
enum class Purpose { Execute, Inspect };
enum class Result { Ok, Missing, Unchanged, Stale, Full, Overflow, Invalid, Corrupt, Io, Busy, Cancelled, Active, Readable };
struct Key {
  KeyState state{};
  uint8_t id[32]{},modulus[256]{};
  char label[LabelBytes]{};
};
// SHA-256 of canonical RSA-2048/e65537 SubjectPublicKeyInfo, identical to LFAPP1.
bool fingerprint(const uint8_t modulus[256],uint8_t id[32]);
struct Table {
  uint32_t serial=0,count=0;
  Key keys[MaximumKeys]{};
  bool valid() const;
  // Inspect authenticates retained packages for catalog/export only. It does
  // not authorize installation, execution, an update or a recovery launch.
  const Key *find(const uint8_t id[32],Purpose) const;
  bool unwrap(const uint8_t *package,size_t bytes,Purpose,const uint8_t **payload,size_t *length,void (*progress)()=nullptr) const;
  // Pure proposals; neither mutates the source nor constitutes user approval.
  Result enroll(uint32_t expected,const uint8_t modulus[256],const char *label,size_t bytes,Table *out) const;
  Result revoke(uint32_t expected,const uint8_t id[32],Table *out) const;
  Result remove(uint32_t expected,const uint8_t id[32],Table *out) const;
};
bool encode(const Table &,uint8_t out[WireBytes]);
// Invalid input preserves out. Absent storage is handled separately by Store.
Result decode(const uint8_t *,size_t,Table *out);

// Internal OS storage only. The caller must own the mounted littlefs instance
// exclusively throughout a mutation and must obtain OS user approval BEFORE
// beginEnroll/beginRevoke. No USB command, app service or trust hook is exposed
// here. Never create a second Store over the same volume during an operation.
class Store {
public:
  static constexpr const char *Path="developer-keys";
  static constexpr const char *Pending=".developer-keys.pending";
  enum class State { Idle, Busy, Committing, Complete, Cancelled, Failed };
  explicit Store(lfs_t *);
  ~Store();
  Store(const Store &)=delete;
  Store &operator=(const Store &)=delete;
  Result load(); // Read-only. Missing != corrupt; never formats or resets.
  const Table *current() const { return m_loaded?&m_current:nullptr; }
  Result beginEnroll(uint32_t expected,const uint8_t modulus[256],const char *label,size_t bytes);
  Result beginRevoke(uint32_t expected,const uint8_t id[32]);
  // Removal additionally requires the controller's installed-package scan.
  Result beginRemove(uint32_t expected,const uint8_t id[32]);
  static constexpr uint32_t MaximumDamagedBytes=65536;
  Result damaged(uint8_t hash[32],uint32_t *bytes);
  int readDamaged(uint32_t offset,void *,uint32_t bytes);
  // The caller has exported the exact damaged bytes and obtained explicit OS
  // approval for this replacement key. Other app namespaces are never changed.
  Result beginRepair(const uint8_t hash[32],const uint8_t modulus[256],const char *label,size_t bytes);
  // Internal unreadable-media repair. The exclusive OS controller must capture
  // this snapshot again AFTER user approval, then supply its expected hash.
  Result beginRepairSnapshot(Snapshot &,const uint8_t hash[32],const uint8_t modulus[256],const char *label,size_t bytes);
  void step(); // One bounded chunk/phase, advanced by the OS owner.
  bool cancel(); // False from the start of rename; its outcome may be unknown.
  State state() const;
  Result result() const { return m_result; }
  bool commitStarted() const { return m_commitStarted; }
private:
  enum class Phase { Idle, Create, Write, CloseWrite, OpenVerify, Verify, CloseVerify,
                     Commit, OpenReadback, Readback, CloseReadback, Done, Cancelled, Failed };
  int open(const char *,int);
  int close();
  Result prepare(uint32_t expected);
  Result start(const Table &);
  void fail(Result);
  bool compareChunk();
  lfs_t *m_fs;
  lfs_file_t m_file{};
  lfs_file_config m_config{};
  uint8_t m_cache[2048]{},m_wire[WireBytes]{},m_scratch[512]{};
  Table m_current{};
  uint32_t m_cursor=0;
  Phase m_phase=Phase::Idle;
  Result m_result=Result::Missing;
  bool m_open=false,m_loaded=false,m_commitStarted=false;
};
}}
#endif

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DEVELOPER_KEY_SNAPSHOT_H
#define LEFONY_APP_DEVELOPER_KEY_SNAPSHOT_H
#include "app_developer_keys.h"
namespace PrimeG2 { namespace AppDeveloperKeys {
// An explicit partial backup of the registry, never a source of trusted keys.
// The caller owns the mounted volume exclusively while capturing or reading.
class Snapshot {
public:
  static constexpr unsigned ChunkBytes=512,HeaderBytes=32,RecordHeaderBytes=16;
  static constexpr unsigned MaximumChunks=Store::MaximumDamagedBytes/ChunkBytes;
  static constexpr unsigned MaximumBytes=HeaderBytes+MaximumChunks*RecordHeaderBytes+Store::MaximumDamagedBytes;
  enum class State { Idle, Running, Ready, Cancelled, Failed };
  struct Info {
    uint32_t originalBytes=0,bytes=0,readableBytes=0,unreadableChunks=0;
    uint8_t hash[32]{};
  };
  explicit Snapshot(lfs_t *);
  ~Snapshot();
  Snapshot(const Snapshot &)=delete;
  Snapshot &operator=(const Snapshot &)=delete;
  Result begin();
  void step(); // At most one 512-byte source chunk per call.
  void cancel();
  State state() const {return m_state;}
  Result result() const {return m_result;}
  bool info(Info *) const;
  // Serialized LFKREAD1 header/records; unreadable bytes are omitted, not zeroed.
  // A caller must verify the complete stream hash before publishing a backup.
  int read(uint32_t offset,void *,uint32_t bytes);
private:
  friend class Store;
  enum class Phase { Open, Read, Close };
  int open();
  int close();
  void fail(Result);
  void header(uint8_t out[HeaderBytes]) const;
  void record(unsigned chunk,uint8_t out[RecordHeaderBytes]) const;
  unsigned count() const {return (m_info.originalBytes+ChunkBytes-1)/ChunkBytes;}
  unsigned length(unsigned chunk) const;
  bool missing(unsigned chunk) const {return m_missing[chunk/8]&(1u<<(chunk%8));}
  lfs_t *m_fs;
  lfs_file_t m_file{};
  lfs_file_config m_config{};
  uint8_t m_cache[2048]{},m_scratch[ChunkBytes]{},m_missing[MaximumChunks/8]{};
  NativeAppHash::SHA256 m_hash{};
  Info m_info{};
  unsigned m_cursor=0;
  bool m_open=false;
  Phase m_phase=Phase::Open;
  State m_state=State::Idle;
  Result m_result=Result::Missing;
};
}}
#endif

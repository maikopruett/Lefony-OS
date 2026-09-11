// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_STORAGE_H
#define LEFONY_APP_STORAGE_H
#include "legacy_app_storage.h"
#include "littlefs/lfs.h"
#include "native_app_digest.h"
namespace PrimeG2 {
namespace AppStorage {
using LegacyAppStorage::Backend;
using LegacyAppStorage::BlockCount;
using LegacyAppStorage::FirstBlock;
using LegacyAppStorage::MaximumData;
using LegacyAppStorage::MaximumPackage;
using LegacyAppStorage::PageBytes;
using LegacyAppStorage::PagesPerBlock;
constexpr uint32_t BlockBytes = PageBytes * PagesPerBlock, ReserveBlocks = 24;
// Every package is larger than the inline limit and owns at least one flash
// block. This is a RAM bound derived from physical capacity, not app slots.
constexpr unsigned MaximumEntries = BlockCount;
enum class State : uint32_t {
  Unprovisioned,
  Ready,
  Erasing,
  Writing,
  Verifying,
  Committing,
  Complete,
  Failed,
  Migrating
};
struct Entry {
  uint32_t generation, packageBytes, dataBytes;
};
struct Space {
  uint32_t capacity, used, available, allocated, overhead;
};
using NameReader = bool (*)(const uint8_t *, size_t, char id[49]);
using Visitor = bool (*)(void *, const char *, const Entry &);
class Volume {
public:
  explicit Volume(Backend);
  ~Volume();
  Volume(const Volume &) = delete;
  Volume &operator=(const Volume &) = delete;
  bool mount(); // Read-only. Never formats a failed filesystem.
  bool initialize(uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity,
                  NameReader);
  bool provision(const uint8_t backup[32]); // Legacy explicit backup path only.
  bool list(Visitor, void *);
  bool entry(const char *id, Entry *, bool icon = false);
  bool read(const char *id, uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity, bool icon = false);
  bool begin(const char *id, const uint8_t *package, uint32_t packageBytes, const uint8_t *data,
             uint32_t dataBytes, bool icon = false);
  void step(); // One bounded filesystem operation/chunk; hardware I/O stays in Backend.
  void cancel();
  bool space(Space *);
  State state() const { return m_state; }
  uint32_t progress() const { return m_cursor; }

private:
  static int readBlock(const lfs_config *, lfs_block_t, lfs_off_t, void *, lfs_size_t);
  static int programBlock(const lfs_config *, lfs_block_t, lfs_off_t, const void *, lfs_size_t);
  static int eraseBlock(const lfs_config *, lfs_block_t);
  static int syncBlock(const lfs_config *);
  static int usedBlock(void *, lfs_block_t);
  bool validName(const char *) const;
  bool path(const char *, char out[64], bool icon = false) const;
  bool readHeader(const char *, uint8_t header[64]);
  bool openFile(const char *, int);
  bool closeFile();
  bool marker(const uint8_t *) const;
  bool readSmall(const char *, uint8_t *, size_t);
  bool writeSmall(const char *, const uint8_t *, size_t);
  bool finish();
  void fail();
  Backend m_backend;
  LegacyAppStorage::Volume m_legacy;
  lfs_t m_fs;
  lfs_config m_config;
  lfs_file_t m_file;
  lfs_file_config m_fileConfig;
  uint8_t m_readCache[PageBytes], m_writeCache[PageBytes], m_fileCache[PageBytes], m_lookahead[64],
      m_scratch[PageBytes];
  bool m_protected[BlockCount], m_used[BlockCount];
  uint8_t m_identity[32], m_header[64];
  char m_path[64];
  const uint8_t *m_package, *m_data;
  uint32_t m_packageBytes, m_dataBytes, m_cursor;
  NativeAppHash::SHA256 m_hash;
  State m_state;
  bool m_icon, m_mounted, m_open, m_legacyValid, m_finishedMigration;
};
} // namespace AppStorage
} // namespace PrimeG2
#endif

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_STORAGE_H
#define LEFONY_APP_STORAGE_H
#include "legacy_app_storage.h"
#include "littlefs/lfs.h"
#include "native_app_digest.h"
#include "app_document_store.h"
#include "app_file_store.h"
namespace PrimeG2 {
namespace AppDeveloperKeys { class Controller; }
namespace AppArchive { class Session; }
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
  explicit Volume(Backend,AppFileStore::ReadCache *cache=nullptr);
  ~Volume();
  Volume(const Volume &) = delete;
  Volume &operator=(const Volume &) = delete;
  bool mount(); // Read-only. Never formats a failed filesystem.
  bool initialize(uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity,
                  NameReader);
  bool provision(const uint8_t backup[32]); // Legacy explicit backup path only.
  bool list(Visitor, void *,bool includeUnreadable=false);
  // A damaged or unknown canonical file is still occupied. Negative means I/O
  // or invalid input, zero alone means absent. No data is parsed or exposed.
  int namespaceState(const char *id);
  bool entry(const char *id, Entry *, bool icon = false);
  bool read(const char *id, uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity, bool icon = false);
  bool begin(const char *id, const uint8_t *package, uint32_t packageBytes, const uint8_t *data,
             uint32_t dataBytes, bool icon = false);
  bool documentRoot(const char *id, AppDocumentRoot::Root *);
  // Internal launcher preference, atomically replaced by the same verified
  // writer. AppManagement owns the volume exclusively; no app or USB accessor.
  static constexpr uint32_t MaximumHomeOrder=27208;
  int readHomeOrder(uint8_t *,uint32_t capacity);
  bool beginHomeOrder(const uint8_t *,uint32_t bytes);
  bool beginCheckpoint(const char *id, const uint8_t *data, uint32_t bytes,
                       const uint32_t version[3], uint32_t dataSchema, bool acceptUpgrade=false);
  bool beginUpgrade(const char *id, const uint8_t *package, uint32_t bytes, const uint32_t version[3]);
  bool beginAccept(const char *id, uint32_t expectedSchema);
  bool beginRollback(const char *id);
  // Read only the retained immutable package for caller-side signature/schema
  // verification. The root still selects the target; the host supplies no blob.
  bool recoveryPackage(const char *id,uint8_t *package,size_t capacity,Entry *);
  bool beginFile(const char *id,const char *name,uint32_t bytes,bool patch=false,uint32_t offset=0);
  bool beginStream(const char *id,const char *name,AppFileStore::Store::StreamMode);
  bool changeFile(const char *id,const char *name,const char *destination=nullptr,bool directory=false);
  int fileInfo(const char *id,const char *name,uint32_t *kind,uint32_t *bytes);
  // Read-only committed metadata. Generation is in/out: zero selects the
  // current root, otherwise a changed root fails before exposing a new page.
  static constexpr int CatalogChanged=-2000;
  int listFiles(const char *id,const char *directory,uint32_t offset,uint32_t *generation,
                AppFileIndex::Entry *,uint32_t capacity,uint32_t *next);
  struct FileUsage {
    uint32_t generation,packageBytes;
    AppDocumentStore::Store::FileUsage data;
  };
  bool fileUsage(const char *id,FileUsage *);
  bool fileWritable() const { return m_fileOperation && m_files.state()==AppFileStore::Store::State::Writable; }
  int writeFile(const void *data,uint32_t bytes) { return m_fileOperation?m_files.write(data,bytes):-1; }
  bool commitFile() { return m_fileOperation && m_files.commit(); }
  bool openFile(const char *id,const char *name);
  int readFile(void *data,uint32_t bytes) { return m_fileOperation?m_files.read(data,bytes):-1; }
  bool seekFile(uint32_t offset) { return m_fileOperation && m_files.seek(offset); }
  bool closeReader();
  // Internal snapshot descriptors; the app facade must supply its authenticated
  // namespace. Tokens are owner-checked and never reused during a volume lifetime.
  static constexpr unsigned MaximumReaders=4;
  struct SnapshotInfo {
    uint32_t bytes,position,verifiedBytes;
    AppFileStore::Reader::State state;
  };
  uint32_t openSnapshot(const char *id,const char *name);
  int readSnapshot(const char *id,uint32_t token,void *,uint32_t);
  int readCachedSnapshot(const char *id,uint32_t token,void *,uint32_t);
  bool stepSnapshot(const char *id,uint32_t token);
  bool seekSnapshot(const char *id,uint32_t token,uint32_t offset);
  bool closeSnapshot(const char *id,uint32_t token);
  bool snapshotInfo(const char *id,uint32_t token,SnapshotInfo *) const;
  bool closeSnapshots(const char *id=nullptr);
  uint32_t filePosition() const { return m_files.position(); }
  uint32_t fileSize() const { return m_files.size(); }
  uint32_t fileObjectWrites() const { return m_files.objectWrites(); }
  int fileError() const { return m_files.error(); }
  uint32_t checkpointPackageWrites() const { return m_documents.packageWrites(); }
  uint32_t checkpointDataWrites() const { return m_documents.dataWrites(); }
  void step(); // One bounded filesystem operation/chunk; hardware I/O stays in Backend.
  void cancel();
  bool space(Space *);
  State state() const { return m_state; }
  uint32_t progress() const { return m_documentOperation?
    m_documents.packageWrites()+m_documents.dataWrites():m_cursor; }

private:
  // The OS key controller shares this mounted volume under AppManagement's
  // exclusive operation gate. No raw filesystem handle is exposed to apps.
  friend class PrimeG2::AppDeveloperKeys::Controller;
  friend class PrimeG2::AppArchive::Session;
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
  bool documentReady() const;
  bool documentSpace(uint32_t packageBytes,uint32_t dataBytes,bool conversion);
  bool pruneOrphans();
  bool nextFileRoot(const char *,AppDocumentRoot::Root *,AppDocumentRoot::Root *);
  static bool retainChunk(void *,const char *,uint32_t generation,uint32_t part);
  static bool admitChunk(void *,uint32_t bytes);
  bool hasSnapshots(const char *) const;
  int snapshotSlot(const char *,uint32_t) const;
  static int readMetadata(const lfs_config *,lfs_block_t,lfs_off_t,void *,lfs_size_t);
  void invalidateMetadata(uint32_t block);
  void refreshMetadata();
  static constexpr unsigned MetadataPages=128;
  struct MetadataPage { uint32_t tag=0;uint8_t data[PageBytes]; };
  MetadataPage m_metadata[MetadataPages]{};
  unsigned m_metadataNext=0;
  Backend m_backend;
  LegacyAppStorage::Volume m_legacy;
  lfs_t m_fs;
  AppDocumentStore::Store m_documents;
  AppFileStore::Store m_files;
  AppFileStore::Reader m_readers[MaximumReaders];
  uint32_t m_readerTokens[MaximumReaders]{},m_readerSerial=0;
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
  bool m_documentOperation=false;
  bool m_fileOperation=false;
  bool m_fileAdmission=false;
  uint32_t m_fileBudgetPackage=0,m_fileBudgetData=0;
};
} // namespace AppStorage
} // namespace PrimeG2
#endif

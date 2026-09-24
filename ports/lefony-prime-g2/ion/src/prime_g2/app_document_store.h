// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_DOCUMENT_STORE_H
#define LEFONY_APP_DOCUMENT_STORE_H
#include "app_document_root.h"
#include "app_file_index.h"
#include "littlefs/lfs.h"
namespace PrimeG2 { namespace AppDocumentStore {
// Uses the production volume and its NAND adapter. Objects are immutable after
// the root rename; the caller authenticates package metadata before starting.
class Store {
public:
  using Root = AppDocumentRoot::Root;
  enum class State { Idle, Busy, Committing, Complete, Failed };
  explicit Store(lfs_t *);
  bool root(const char *id, Root *);
  bool read(const char *id, uint8_t *package, size_t capacity, uint8_t *data, size_t dataCapacity);
  bool readRecoveryPackage(const char *id,uint8_t *package,size_t capacity);
  // Buffers remain owned by the caller and stable until completion/cancellation.
  // A null package/data preserves that object. copyLegacy copies package bytes
  // from the still-authoritative FILE2 file, without loading them into RAM.
  bool begin(const char *id, const Root &before, const Root &after,
             const uint8_t *package, const uint8_t *data, bool writeData, bool copyLegacy);
  // Archive restores stage immutable objects before selecting a new root.
  // Verify both incoming pairs without collecting replaced objects, then publish
  // with the ordinary atomic rename. This permits replacing damaged data while
  // preserving the old root and every old object until the commit boundary.
  // The exclusive volume owner authenticates the packages and binds before.
  bool publishStaged(const char *id,const Root &before,const Root &after);
  bool prune(const char *id); // Only a directory whose canonical app is absent.
  bool collect(const char *id,const Root &root);
  bool index(const char *id,const AppDocumentRoot::Pair &,AppFileIndex::Index *);
  bool privateBytes(const char *id,const AppDocumentRoot::Pair &,uint32_t *);
  int fileInfo(const char *id,const AppDocumentRoot::Pair &,const char *name,uint32_t *kind,uint32_t *bytes);
  struct FileUsage { uint32_t namedBytes,privateBytes,files,directories,extents; };
  bool fileUsage(const char *id,const AppDocumentRoot::Pair &,FileUsage *);
  int listFiles(const char *id,const AppDocumentRoot::Pair &,const char *directory,
                uint32_t offset,AppFileIndex::Entry *,uint32_t capacity,uint32_t *next);
  // Copy a validated named file's immutable extents into volume-owned memory.
  // Index loading is synchronous; callers must serialize it with transactions.
  bool snapshot(const char *id,const AppDocumentRoot::Pair &,const char *name,
                AppFileIndex::Extent *,uint32_t *count,uint32_t *bytes);
  using ChunkRetainer=bool (*)(void *,const char *id,uint32_t generation,uint32_t part);
  void setChunkRetainer(ChunkRetainer callback,void *context) {
    m_chunkRetainer=callback;m_retainerContext=context;
  }
  void step();
  void cancel();
  State state() const;
  uint32_t packageWrites() const { return m_packageWrites; }
  uint32_t dataWrites() const { return m_dataWrites; }
private:
  enum class Phase { Idle, LegacyCheck, CheckPackage, CheckData, CheckPreviousPackage, CheckPreviousData,
    CheckStagedPackage, CheckStagedData, CheckStagedPreviousPackage, CheckStagedPreviousData,
    CheckReferences, Directory, AppDirectory, CollectOpen, Collect, Package, VerifyPackage, Data, VerifyData,
    RootWrite, RootVerify, Commit, RemoveDirectory, Done, Failed };
  bool name(const char *);
  void object(char type, uint32_t generation, char out[80]) const;
  bool open(const char *, int);
  bool close();
  bool readObject(const char *, uint8_t *, uint32_t, const uint8_t hash[32]);
  void checkObject(char type, const AppDocumentRoot::Pair &, Phase next);
  void writeObject(char type, Phase next);
  void fail();
  bool retained(char type, uint32_t generation) const;
  bool references(const AppFileIndex::Index &);
  void checkReference();
  void extentPath(const AppFileIndex::Extent &,char out[80]) const;
  lfs_t *m_fs;
  lfs_file_t m_file{}, m_input{};
  lfs_file_config m_fileConfig{}, m_inputConfig{};
  lfs_dir_t m_dir{};
  uint8_t m_cache[2048]{}, m_inputCache[2048]{}, m_scratch[2048]{};
  char m_id[49]{}, m_path[64]{}, m_directory[64]{};
  Root m_before{}, m_after{};
  NativeAppHash::SHA256 m_hash{};
  const uint8_t *m_package=nullptr, *m_data=nullptr;
  uint32_t m_cursor=0, m_packageWrites=0, m_dataWrites=0, m_entries=0;
  uint32_t m_legacyBytes=0;
  uint8_t m_legacyHash[32]{};
  AppFileIndex::Index m_index{};
  uint8_t m_indexWire[AppFileIndex::MaximumBytes]{};
  AppFileIndex::Extent m_references[3*AppFileIndex::MaximumExtents]{};
  uint32_t m_referenceCount=0,m_referenceCursor=0;
  ChunkRetainer m_chunkRetainer=nullptr;
  void *m_retainerContext=nullptr;
  Phase m_phase=Phase::Idle;
  bool m_open=false, m_inputOpen=false, m_dirOpen=false, m_writeData=false, m_copyLegacy=false, m_prune=false,m_collectOnly=false,m_staged=false;
};
}}
#endif

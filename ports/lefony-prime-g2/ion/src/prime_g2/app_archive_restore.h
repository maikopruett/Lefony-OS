// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_RESTORE_H
#define LEFONY_APP_ARCHIVE_RESTORE_H
#include "app_archive_format.h"
#include "app_document_store.h"
namespace PrimeG2 { namespace AppArchive {
// Internal OS engine. The owner holds the volume exclusively, authenticates the
// installed namespace independently of its data, and supplies trust/version/
// schema policy. Neither the host nor an app can supply these callbacks.
class Restore {
public:
  enum class State { Idle, Receiving, Working, Ready, Committing, Complete, Cancelled, Failed };
  enum class Error { None, Format, Integrity, Authority, Changed, Space, IO, CommitUnknown };
  struct Hooks {
    void *context;
    bool (*authenticate)(void *,const Header &,const PairHeader &,unsigned,const uint8_t *);
    bool (*unchanged)(void *); // Canonical namespace/generation AND trust binding.
    bool (*admit)(void *,uint32_t); // Actual allocation, including commit reserve.
    bool (*privateVerified)(void *,const PairHeader &,unsigned,const uint8_t *);
    bool repairLegacy; // Validated FILE2 header; exact identity is proved by hooks.
  };
  Restore(lfs_t *,AppDocumentStore::Store *);
  // `before` is the installed root, or empty for FILE2/absent namespaces.
  // base is its authenticated generation (zero only for an absent namespace).
  // Scratch remains exclusively owned/stable through completion/cancellation.
  bool begin(const char *id,const AppDocumentRoot::Root &before,uint32_t base,
             uint32_t currentLimit,uint32_t bytes,const uint8_t digest[32],
             uint8_t *packageScratch,uint32_t capacity,Hooks);
  // Accept at most 2048 bytes, possibly only a prefix. -2 means step first.
  int write(const void *,uint32_t);
  void step();
  bool commit();
  bool cancel(); // False after the atomic commit boundary has been entered.
  State state() const;
  Error error() const { return m_error; }
  bool cleanupFailed() const { return m_cleanupFailed; }
  uint32_t received() const { return m_received; }
  uint32_t reusedBytes() const { return m_reused; }
  const AppDocumentRoot::Root &result() const { return m_after; }
private:
  enum class Phase { Idle,Header,Pair,Package,Authenticate,Directory,AppDirectory,
    OldCurrent,OldPrevious,WritePackage,Private,Entry,Content,FindReuse,CheckReuse,
    WriteChunk,Trailer,WriteIndex,Ready,Publish,Cleanup,Done,Cancelled,Failed };
  void frame(Phase);
  void parsed();
  void content();
  void finishContent();
  void nextEntry();
  void finishPair();
  void chunkDone(const AppFileIndex::Extent &);
  void findReuse();
  void checkReuse();
  void object(char,uint32_t,char out[80],uint32_t part=0) const;
  bool target(const char *,const AppDocumentRoot::Root &,uint32_t,bool);
  bool open(const char *,int);
  bool close();
  bool stage(char,const uint8_t *,uint32_t,uint32_t part=0);
  void fail(Error);
  void cleanup();
  AppFileIndex::Index &index() { return m_new[m_pairNumber]; }
  AppDocumentRoot::Pair &pair() { return m_pairNumber?m_after.previous:m_after.current; }
  uint32_t generation() const { return m_base+m_pairNumber+1; }
  lfs_t *m_fs;
  AppDocumentStore::Store *m_documents;
  Hooks m_hooks{};
  AppDocumentRoot::Root m_before{},m_after{};
  Header m_header{};
  PairHeader m_pair{};
  uint32_t m_currentVersion[3]{};
  AppFileIndex::Index m_new[2]{},m_old[2]{};
  AppFileIndex::Extent m_candidate{};
  lfs_file_t m_file{};
  lfs_file_config m_fileConfig{};
  NativeAppHash::SHA256 m_whole{},m_contentHash{},m_reuseHash{},m_packagePrivateHash{};
  uint8_t m_expected[32]{},m_digest[32]{},m_chunkHash[32]{};
  uint8_t m_frame[128]{},m_chunk[AppFileIndex::ChunkBytes]{},m_indexWire[AppFileIndex::MaximumBytes]{};
  uint8_t m_cache[2048]{},m_scratch[2048]{};
  uint8_t *m_package=nullptr;
  char m_id[49]{};
  uint32_t m_base=0,m_limit=0,m_total=0,m_received=0,m_pairNumber=0,m_cursor=0;
  uint32_t m_frameBytes=0,m_contentLeft=0,m_chunkFill=0,m_used=0,m_search=0,m_reused=0;
  uint32_t m_parts[2]{};
  bool m_packageStaged[2]{},m_indexStaged[2]{};
  bool m_open=false,m_cancelled=false,m_cleanupFailed=false,m_publisher=false,m_commitAttempted=false;
  bool m_directoryCreated=false,m_objectsCreated=false;
  Error m_error=Error::None;
  Phase m_phase=Phase::Idle;
};
}}
#endif

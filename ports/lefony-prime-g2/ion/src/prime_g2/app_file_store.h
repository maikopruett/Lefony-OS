// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_FILE_STORE_H
#define LEFONY_APP_FILE_STORE_H
#include "app_document_store.h"
namespace PrimeG2 { namespace AppFileStore {
// Logical mutable bytes in the current app root, including the private store.
// Retained roots/chunks and signed packages use separate physical admission.
constexpr uint32_t QuotaBytes=32u*1024u*1024u;
constexpr int QuotaExceeded=-2001;
class Reader;
// Privileged RAM copies of authenticated immutable chunks. Entries belong to
// one live snapshot, are never shared across opens, and are unpublished until
// their full digest matches. A cache hit returns these exact verified bytes.
class ReadCache {
public:
  static constexpr unsigned Slots=64;
  int find(const Reader *,uint32_t chunk);
  int reserve(const Reader *,uint32_t chunk);
  void publish(unsigned slot);
  void release(const Reader *);
  uint8_t *bytes(unsigned slot) { return m_entries[slot].bytes; }
private:
  struct Entry {
    const Reader *owner=nullptr;
    uint32_t chunk=0;
    uint64_t used=0;
    bool verified=false;
    uint8_t bytes[AppFileIndex::ChunkBytes];
  };
  Entry m_entries[Slots];
  uint64_t m_serial=0;
};
// Independent immutable reader. Verification advances at most 2048 content
// bytes per step. Pending reads retain no caller buffer or pointer.
class Reader {
public:
  Reader()=default;
  Reader(const Reader &)=delete;
  Reader &operator=(const Reader &)=delete;
  enum class State { Closed, Ready, Verifying, Failed };
  static constexpr int Pending=-2;
  bool open(lfs_t *,AppDocumentStore::Store *,const char *id,const char *name,
            const AppDocumentRoot::Root &);
  void setCache(ReadCache *cache) { m_contentCache=cache; }
  // Never touches the filesystem. Pending means that normal polling is needed.
  int readCached(void *,uint32_t);
  int read(void *,uint32_t);
  void step();
  bool seek(uint32_t);
  bool close();
  bool belongsTo(const char *) const;
  bool retains(const char *,uint32_t generation,uint32_t part) const;
  State state() const { return m_state; }
  uint32_t position() const { return m_position; }
  uint32_t size() const { return m_bytes; }
  uint32_t verifiedBytes() const { return m_cursor; }
private:
  bool closeObject();
  void fail();
  lfs_t *m_fs=nullptr;
  AppFileIndex::Extent m_extents[AppFileIndex::MaximumExtents]{};
  lfs_file_t m_file{};
  lfs_file_config m_config{};
  uint8_t m_cache[2048]{},m_scratch[2048]{};
  NativeAppHash::SHA256 m_hash{};
  char m_id[49]{};
  uint32_t m_count=0,m_bytes=0,m_position=0,m_cursor=0,m_chunk=AppFileIndex::MaximumExtents;
  State m_state=State::Closed;
  bool m_open=false;
  ReadCache *m_contentCache=nullptr;
  int m_cacheSlot=-1;
};
// One volume-owned stream. Application descriptors and scheduling wrap this
// engine; no application may select its filesystem or app namespace directly.
class Store {
public:
  using Root=AppDocumentRoot::Root;
  enum class State { Idle, Preparing, Writable, Reading, Working, Committing, Complete, Failed };
  enum class StreamMode { Truncate, Update, Append };
  static constexpr int Pending=-2;
  Store(lfs_t *,AppDocumentStore::Store *);
  bool begin(const char *id,const char *name,uint32_t bytes,const Root &before,const Root &after,
             bool patch=false,uint32_t offset=0,const uint8_t *automatic=nullptr,bool feed=false);
  bool beginStream(const char *id,const char *name,StreamMode,const Root &,const Root &);
  using ChunkAdmission=bool (*)(void *,uint32_t bytes);
  void setChunkAdmission(ChunkAdmission callback,void *context) {
    m_chunkAdmission=callback;m_admissionContext=context;
  }
  bool mutate(const char *id,const char *name,const char *destination,bool directory,const Root &,const Root &);
  int write(const void *,uint32_t);
  bool commit();
  void step();
  void cancel();
  bool openRead(const char *id,const char *name,const Root &);
  int read(void *,uint32_t);
  bool seek(uint32_t);
  bool closeRead();
  State state() const;
  bool prepared() const { return m_phase==Phase::PrepareChunk && !m_part && !m_written; }
  uint32_t position() const { return m_position; }
  uint32_t size() const { return m_index.entry[m_target].bytes; }
  uint32_t objectWrites() const { return m_objectWrites; }
  int error() const { return m_error; } // littlefs error code; 0 means no error.
private:
  enum class Phase { Idle, Preparing, PrepareChunk, Prefix, Writable, Suffix, Verify, Commit, Reading,
    StreamLoad, StreamLoading, StreamGap, StreamFlush, StreamWriting, StreamVerify, StreamCommit, Done, Failed };
  bool setup(const char *,const Root &,const Root &);
  bool resize(unsigned,uint32_t);
  bool open(const AppFileIndex::Extent &,int);
  bool close();
  void path(const AppFileIndex::Extent &,char out[80]) const;
  void fail(int error=LFS_ERR_IO);
  bool output(const uint8_t *,uint32_t);
  bool input(uint32_t,uint8_t *,uint32_t);
  void prepareChunk();
  void copyBoundary(uint32_t,Phase);
  bool verifyRead(const AppFileIndex::Extent &);
  bool extend(uint32_t);
  bool publishIndex();
  void requestChunk(uint32_t,Phase afterLoad);
  void stepStream();
  int writeStream(const void *,uint32_t);
  int readStream(void *,uint32_t);
  uint32_t streamLimit() const;
  uint32_t quotaLimit(unsigned target) const { return m_quotaCeiling-(m_usage-m_index.entry[target].bytes); }
  lfs_t *m_fs;
  AppDocumentStore::Store *m_documents;
  AppFileIndex::Index m_index{};
  // Publishing ends the stream: its verified chunk cache can then become the
  // immutable index wire buffer retained by the document transaction.
  uint8_t m_buffer[AppFileIndex::ChunkBytes]{};
  lfs_file_t m_file{},m_input{};
  lfs_file_config m_config{},m_inputConfig{};
  uint8_t m_cache[2048]{},m_inputCache[2048]{},m_scratch[2048]{};
  Root m_before{},m_after{};
  AppFileIndex::Extent m_old{},m_new{};
  NativeAppHash::SHA256 m_hash{};
  char m_directory[64]{},m_id[49]{};
  uint32_t m_target=0,m_expected=0,m_written=0,m_offset=0,m_chunk=0,m_cursor=0,m_chunkBytes=0;
  uint32_t m_payloadStart=0,m_payloadEnd=0,m_part=0,m_position=0,m_readExtent=0,m_objectWrites=0;
  const uint8_t *m_automatic=nullptr;
  ChunkAdmission m_chunkAdmission=nullptr;
  void *m_admissionContext=nullptr;
  uint32_t m_streamLoaded=AppFileIndex::MaximumExtents,m_streamRequested=0,m_gapEnd=0;
  uint32_t m_usage=0,m_quotaCeiling=QuotaBytes;
  Phase m_afterLoad=Phase::Writable,m_afterFlush=Phase::StreamLoad;
  int m_error=0;
  Phase m_phase=Phase::Idle;
  bool m_open=false,m_inputOpen=false,m_patch=false,m_feed=false,m_metadata=false;
  bool m_stream=false,m_streamDirty=false,m_append=false;
};
}}
#endif

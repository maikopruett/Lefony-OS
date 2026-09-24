// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_EXPORT_H
#define LEFONY_APP_ARCHIVE_EXPORT_H
#include "app_archive_source.h"
#include "app_file_store.h"
namespace PrimeG2 { namespace AppArchive {
struct PackageInfo { uint32_t version[3]{},schema=0; };
// Verifier checks the signed package/manifest, including the supplied app ID.
// Export uses retained-key inspection authority, never enrolls an archive key.
using Verify=bool (*)(void *,const char *,const uint8_t *,uint32_t,PackageInfo *);
class Export {
public:
  enum class State { Idle,Working,Readable,Complete,Cancelled,Failed };
  enum class Error { None,IO,Integrity,Format,Authority,Changed };
  Export(lfs_t *,AppDocumentStore::Store *);
  bool begin(const SourceInfo &,uint8_t *scratch,uint32_t capacity,Verify,void *);
  int read(void *,uint32_t); // At most 2048 bytes; -2 means step, 0 means complete.
  void step();
  void cancel();
  State state() const;
  Error error() const { return m_error; }
  uint32_t bytes() const { return m_header.bytes; }
  uint32_t position() const { return m_sent; }
  const uint8_t *digest() const { return m_digest; } // Only valid after Complete.
private:
  enum class Phase { Idle,PreparePackage,PrepareIndex,LegacyHash,Header,Pair,OpenPackage,
    Package,ClosePackage,OpenPrivate,Private,ClosePrivate,NextEntry,Entry,OpenFile,File,
    CloseFile,Trailer,FinishPair,Done,Cancelled,Failed };
  bool open(const char *,uint32_t size,uint32_t offset=0);
  bool close();
  void fail(Error);
  void preparePair();
  void frame(Phase,const void *,uint32_t);
  void nextFrame();
  void finishRaw(Phase,const uint8_t expected[32]);
  const AppDocumentRoot::Pair &pair() const { return m_number?m_source.root.previous:m_source.root.current; }
  lfs_t *m_fs;
  AppDocumentStore::Store *m_documents;
  Source m_inspector;
  SourceInfo m_source{};
  AppFileIndex::Index m_index[2]{};
  AppFileStore::Reader m_reader;
  Header m_header{};
  PairHeader m_pairs[2]{};
  Verify m_verify=nullptr;
  void *m_context=nullptr;
  uint8_t *m_package=nullptr;
  lfs_file_t m_file{};
  lfs_file_config m_config{};
  uint8_t m_cache[2048]{},m_scratch[2048]{},m_frame[128]{},m_digest[32]{};
  NativeAppHash::SHA256 m_whole{},m_content{},m_legacy{};
  uint32_t m_number=0,m_entry=0,m_sent=0,m_cursor=0,m_frameBytes=0,m_frameOffset=0;
  uint32_t m_contentBytes=0;
  bool m_open=false;
  Phase m_phase=Phase::Idle;
  Error m_error=Error::None;
};
}}
#endif

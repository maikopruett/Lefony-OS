// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_SOURCE_H
#define LEFONY_APP_ARCHIVE_SOURCE_H
#include "app_archive_format.h"
#include "app_document_store.h"
#include "app_root_record.h"
namespace PrimeG2 { namespace AppArchive {
// Canonical namespace metadata, independently readable when mutable data is
// damaged. None of these fields authenticates a publisher; verify the package.
struct SourceInfo {
  char id[49]{};
  AppDocumentRoot::Root root{};
  uint32_t generation=0,packageBytes=0,legacyPrivateBytes=0,canonicalBytes=0;
  uint8_t canonical[AppDocumentRoot::Bytes]{};
  bool legacy=false,repairInspection=false;
  AppRootRecord::Copies rootCopies=AppRootRecord::Copies::Legacy;
};
class Source {
public:
  enum class Result { Missing,Ok,Invalid,IO };
  explicit Source(lfs_t *fs):m_fs(fs) {m_config.buffer=m_cache;}
  Result inspect(const char *,SourceInfo *,bool repair=false);
  bool unchanged(const SourceInfo &);
  bool package(const SourceInfo &,unsigned pair,uint8_t *,uint32_t capacity);
  // Hash the exact LFAPP1 signed envelope, without reading damaged payload/data.
  bool legacyPrefix(const SourceInfo &,uint8_t digest[32]);
  static constexpr uint32_t SignedPrefixBytes=352;
  static bool name(const char *);
  static void canonicalPath(const char *,char out[64]);
  static void objectPath(const char *,char type,uint32_t generation,char out[80],uint32_t part=0);
private:
  lfs_t *m_fs;
  lfs_file_config m_config{};
  uint8_t m_cache[2048]{};
};
}}
#endif

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ROOT_RECORD_H
#define LEFONY_APP_ROOT_RECORD_H
#include "app_document_root.h"
#include "littlefs/lfs.h"
namespace PrimeG2 { namespace AppRootRecord {
// FILE5 wraps the existing logical FILE3/4 root. Its complete second copy is a
// littlefs custom attribute committed atomically with the file contents. The
// payload is deliberately larger than the production inline limit, so the
// copies occupy data and metadata blocks respectively. Package signatures must
// still authenticate every selected pair; a record digest grants no publisher.
constexpr unsigned Bytes=352;
constexpr uint8_t Attribute=0x52;
using Root=AppDocumentRoot::Root;
enum class Result { Ok,Missing,Invalid,Unsupported,IO,Conflict,WrongApp };
enum class Copies { Legacy, Both, Payload, Attribute };
struct Info { Root root{};Copies copies=Copies::Legacy; };
bool encode(const char *id,const Root &,uint8_t out[Bytes]);
Result decode(const char *id,const uint8_t *,unsigned bytes,Root *);
// The caller exclusively owns fs and supplies a cache of fs->cfg->cache_size
// bytes. Errors leave out unchanged. Different valid copies never select the
// larger serial or silently discard one side.
Result read(lfs_t *fs,const char *path,const char *id,void *cache,Info *out);
// Writes a pending file only. The caller verifies it and explicitly renames it
// over the canonical path after authenticating packages and the before state.
// The payload and attribute are committed together by lfs_file_close.
bool stage(lfs_t *fs,const char *path,const char *id,const Root &,void *cache);
}}
#endif

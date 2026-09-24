// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ARCHIVE_FORMAT_H
#define LEFONY_APP_ARCHIVE_FORMAT_H
#include <stdint.h>
#include <string.h>
#include "app_file_index.h"
namespace PrimeG2 { namespace AppArchive {
// Portable snapshot bytes: header, then each pair header/package/private bytes,
// followed by named entry headers, file contents and a 32-byte SHA-256 trailer
// for each file. Directories have no contents/trailer. No storage
// generation, device identifier, object address or trust grant is imported.
constexpr uint32_t MaximumPackage=2101664,MaximumData=64u*1024u*1024u;
constexpr uint32_t MaximumArchive=128+2*(128+MaximumPackage+MaximumData+127*144);
constexpr uint32_t PendingUpgrade=1;
struct Header {
  uint8_t magic[8];uint32_t schema,size,bytes,pairs,flags,reserved;
  uint32_t highVersion[3],reserved2[5];char id[64];
};
struct PairHeader {
  uint32_t size,schema,packageBytes,dataSchema,privateBytes,entries,version[3],reserved[7];
  uint8_t packageHash[32],privateHash[32];
};
struct EntryHeader { char name[96];uint32_t kind,bytes,reserved[2]; };
static_assert(sizeof(Header)==128 && sizeof(PairHeader)==128 && sizeof(EntryHeader)==112,"portable app archive layout");
inline bool zero(const void *p,uint32_t bytes) {
  const uint8_t *b=static_cast<const uint8_t *>(p);for(uint32_t i=0;i<bytes;i++) if(b[i]) return false;return true;
}
inline bool padded(const char *s,uint32_t capacity) {
  uint32_t n=0;while(n<capacity && s[n]) n++;return n<capacity && zero(s+n,capacity-n);
}
inline bool valid(const Header &h) {
  if(memcmp(h.magic,"LFARCH1\0",8) || h.schema!=1 || h.size!=sizeof(h) || h.bytes>MaximumArchive ||
     h.pairs<1 || h.pairs>2 || h.flags!=(h.pairs==2?PendingUpgrade:0) || h.reserved || !zero(h.reserved2,sizeof(h.reserved2)) ||
     h.bytes<sizeof(h)+h.pairs*(sizeof(PairHeader)+468) || !padded(h.id,sizeof(h.id)) || h.id[0]<'a' || h.id[0]>'z') return false;
  unsigned n=0;for(;h.id[n];n++) if(!((h.id[n]>='a' && h.id[n]<='z') || (h.id[n]>='0' && h.id[n]<='9') || h.id[n]=='-')) return false;
  if(n>48) return false;
  for(uint32_t part:h.highVersion) if(part>999999) return false;
  return true;
}
inline bool valid(const PairHeader &p) {
  if(p.size!=sizeof(p) || p.schema!=1 || p.packageBytes<468 || p.packageBytes>MaximumPackage ||
     p.privateBytes>65536 || p.entries>=AppFileIndex::MaximumEntries || !zero(p.reserved,sizeof(p.reserved))) return false;
  for(uint32_t part:p.version) if(part>999999) return false;
  return true;
}
inline bool valid(const EntryHeader &e) {
  return padded(e.name,sizeof(e.name)) && AppFileIndex::path(e.name) && !zero(e.name,1) && zero(e.reserved,sizeof(e.reserved)) &&
    ((e.kind==AppFileIndex::File && e.bytes<=MaximumData) ||
     (e.kind==AppFileIndex::Directory && !e.bytes));
}
inline int compare(const uint32_t a[3],const uint32_t b[3]) {
  for(unsigned i=0;i<3;i++) if(a[i]!=b[i]) return a[i]>b[i]?1:-1;
  return 0;
}
}}
#endif

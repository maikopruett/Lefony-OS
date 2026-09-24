// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_FILE_INDEX_H
#define LEFONY_APP_FILE_INDEX_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace PrimeG2 { namespace AppFileIndex {
constexpr uint32_t ChunkBytes=128*1024-128, MaximumEntries=128, MaximumExtents=512;
constexpr uint32_t HeaderBytes=32, EntryBytes=128, ExtentBytes=48;
constexpr uint32_t MaximumBytes=HeaderBytes+MaximumEntries*EntryBytes+MaximumExtents*ExtentBytes;
enum : uint32_t { File=1, Directory=2, PrivateBytes=3, DataObject=0, ChunkObject=1 };
struct Entry { char name[96]{};uint32_t kind=0,bytes=0,first=0,count=0; };
struct Extent { uint32_t generation=0,part=0,type=0,bytes=0;uint8_t hash[32]{}; };
struct Index {
  uint32_t entries=0,extents=0;
  Entry entry[MaximumEntries]{};
  Extent extent[MaximumExtents]{};
  void clear() { entries=1;extents=0;entry[0]={};entry[0].kind=PrivateBytes; }
  int find(const char *name) const {
    for(uint32_t i=1;i<entries;i++) if(!strcmp(entry[i].name,name)) return i;
    return -1;
  }
};
inline uint32_t get(const uint8_t *p) { return uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24; }
inline void put(uint8_t *p,uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=v>>(8*i); }
inline bool path(const char *name) {
  if(!name || !*name) return false;
  unsigned component=0,start=0,n=0;
  for(;n<96 && name[n];n++) {
    char c=name[n];
    if(c=='/') {
      if(!component || (component==1 && name[start]=='.') ||
         (component==2 && name[start]=='.' && name[start+1]=='.')) return false;
      component=0;start=n+1;
    } else {
      if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') ||
           c=='.' || c=='_' || c=='-' || c==' ') || ++component>48) return false;
    }
  }
  return n<96 && component && !(component==1 && name[start]=='.') &&
    !(component==2 && name[start]=='.' && name[start+1]=='.');
}
inline bool parent(const Index &index,const char *name) {
  const char *slash=nullptr;for(const char *p=name;*p;p++) if(*p=='/') slash=p;if(!slash) return true;
  char prefix[96];size_t n=slash-name;memcpy(prefix,name,n);prefix[n]=0;
  int p=index.find(prefix);return p>=0 && index.entry[p].kind==Directory;
}
inline bool valid(const Index &index,uint32_t serial) {
  if(!serial || !index.entries || index.entries>MaximumEntries || index.extents>MaximumExtents) return false;
  uint32_t cursor=0;
  for(uint32_t i=0;i<index.entries;i++) {
    const Entry &e=index.entry[i];
    if(!i) { if(e.kind!=PrivateBytes || e.name[0] || e.bytes>65536) return false; }
    else {
      if((e.kind!=File && e.kind!=Directory) || !path(e.name) || !parent(index,e.name)) return false;
      for(uint32_t j=1;j<i;j++) if(!strcmp(index.entry[j].name,e.name)) return false;
    }
    if(e.bytes>64*1024*1024 || e.first!=cursor || e.count>index.extents-cursor ||
       (e.kind==Directory && (e.bytes || e.count))) return false;
    if(e.count!=(e.bytes+ChunkBytes-1)/ChunkBytes) return false;
    uint32_t bytes=0;
    for(uint32_t j=0;j<e.count;j++) {
      const Extent &x=index.extent[cursor+j];
      uint32_t expected=e.bytes-bytes;if(expected>ChunkBytes) expected=ChunkBytes;
      if(!x.generation || x.generation>serial || x.bytes!=expected || x.type>ChunkObject ||
         (x.type==DataObject && (i || x.part)) ||
         (x.type==ChunkObject && (!x.part || x.part>MaximumExtents))) return false;
      for(uint32_t k=0;k<cursor+j;k++) {
        const Extent &old=index.extent[k];
        if(old.generation==x.generation && old.part==x.part && old.type==x.type) return false;
      }
      bytes+=x.bytes;
    }
    cursor+=e.count;
  }
  return cursor==index.extents;
}
inline size_t encodedBytes(const Index &index) { return HeaderBytes+index.entries*EntryBytes+index.extents*ExtentBytes; }
inline bool encode(const Index &index,uint32_t serial,uint8_t *out,size_t capacity) {
  if(!out || !valid(index,serial) || capacity<encodedBytes(index)) return false;
  memset(out,0,encodedBytes(index));memcpy(out,"LFAIDX1\0",8);put(out+8,1);put(out+12,index.entries);put(out+16,index.extents);
  for(uint32_t i=0;i<index.entries;i++) {
    uint8_t *p=out+HeaderBytes+i*EntryBytes;const Entry &e=index.entry[i];
    memcpy(p,e.name,strlen(e.name));put(p+96,e.kind);put(p+100,e.bytes);put(p+104,e.first);put(p+108,e.count);
  }
  for(uint32_t i=0;i<index.extents;i++) {
    uint8_t *p=out+HeaderBytes+index.entries*EntryBytes+i*ExtentBytes;const Extent &x=index.extent[i];
    put(p,x.generation);put(p+4,x.part);put(p+8,x.type);put(p+12,x.bytes);memcpy(p+16,x.hash,32);
  }
  return true;
}
// The caller owns a disposable candidate. Invalid input must not be published.
inline bool decode(const uint8_t *in,size_t bytes,uint32_t serial,Index *out) {
  if(!in || !out || bytes<HeaderBytes || memcmp(in,"LFAIDX1\0",8) || get(in+8)!=1 ||
     get(in+20) || get(in+24) || get(in+28)) return false;
  uint32_t entries=get(in+12),extents=get(in+16);
  if(!entries || entries>MaximumEntries || extents>MaximumExtents ||
     bytes!=HeaderBytes+entries*EntryBytes+extents*ExtentBytes) return false;
  out->entries=entries;out->extents=extents;
  for(uint32_t i=0;i<entries;i++) {
    const uint8_t *p=in+HeaderBytes+i*EntryBytes;Entry &e=out->entry[i];
    const uint8_t *end=p;while(end<p+96 && *end) end++;if(end==p+96) return false;
    for(const uint8_t *q=end;q<p+96;q++) if(*q) return false;
    for(unsigned j=112;j<EntryBytes;j++) if(p[j]) return false;
    memcpy(e.name,p,96);e.kind=get(p+96);e.bytes=get(p+100);e.first=get(p+104);e.count=get(p+108);
  }
  for(uint32_t i=0;i<extents;i++) {
    const uint8_t *p=in+HeaderBytes+entries*EntryBytes+i*ExtentBytes;Extent &x=out->extent[i];
    x.generation=get(p);x.part=get(p+4);x.type=get(p+8);x.bytes=get(p+12);memcpy(x.hash,p+16,32);
  }
  return valid(*out,serial);
}
inline void objectName(const Extent &extent,char out[19]) {
  const char *hex="0123456789abcdef";out[0]=extent.type==ChunkObject?'c':'d';
  for(unsigned i=0;i<8;i++) out[1+i]=hex[(extent.generation>>(28-4*i))&15];
  if(extent.type==DataObject) { out[9]=0;return; }
  out[9]='.';for(unsigned i=0;i<8;i++) out[10+i]=hex[(extent.part>>(28-4*i))&15];out[18]=0;
}
}}
#endif

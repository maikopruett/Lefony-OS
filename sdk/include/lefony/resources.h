// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_RESOURCES_H
#define LEFONY_RESOURCES_H
#include <stdint.h>
#include <stddef.h>
namespace Lefony { namespace Resources {
enum class Status { Ok,Invalid,Cancelled };
enum class Kind : uint32_t { Blob=1,RGB565=2 };
struct Resource {
  const uint8_t *data=nullptr;uint32_t bytes=0;
  Kind kind=Kind::Blob;
  uint32_t width=0,height=0,stride=0;bool transparent=false;uint16_t key=0;
};
namespace Detail {
inline uint32_t word(const uint8_t *p) { return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24; }
inline bool id(const uint8_t *p) {
  if(*p<'a' || *p>'z') return false;
  unsigned n=1;
  for(;n<24 && p[n];n++) if(!((p[n]>='a' && p[n]<='z') || (p[n]>='0' && p[n]<='9') || p[n]=='_' || p[n]=='-')) return false;
  if(n==24) return false;
  for(;n<24;n++) if(p[n]) return false;
  return true;
}
inline int compare(const uint8_t *a,const uint8_t *b) {
  for(unsigned i=0;i<24;i++) { if(a[i]!=b[i]) return a[i]<b[i]?-1:1;if(!a[i]) return 0; }
  return 0;
}
}
// Immutable borrowed storage. open() validates the complete table and CRC before
// replacing a previously valid view. No allocation, decoding or OS calls.
class Bundle {
public:
  constexpr Bundle() : m_data(nullptr),m_count(0) {}
  template<typename Cancel> Status open(const uint8_t *data,uint32_t bytes,Cancel cancel) {
    if(!data || bytes<32 || bytes>524288) return Status::Invalid;
    const uint8_t magic[]={'L','F','R','S','R','C','1',0};
    for(unsigned i=0;i<8;i++) if(data[i]!=magic[i]) return Status::Invalid;
    using Detail::word;
    uint32_t count=word(data+12),offset=word(data+24);
    if(word(data+8)!=1 || !count || count>32 || word(data+16)!=bytes || word(data+20)!=32 || offset!=32+64*count || offset>bytes) return Status::Invalid;
    for(uint32_t i=0;i<count;i++) {
      if(cancel()) return Status::Cancelled;
      const uint8_t *e=data+32+64*i;
      uint32_t kind=word(e+24),length=word(e+32),width=word(e+36),height=word(e+40),stride=word(e+44),flags=word(e+48),key=word(e+52);
      if(!Detail::id(e) || (i && Detail::compare(e-64,e)>=0) || word(e+28)!=offset || !length || length>bytes-offset || word(e+56) || word(e+60)) return Status::Invalid;
      if(kind==1) { if(length>65536 || width || height || stride || flags || key) return Status::Invalid; }
      else if(kind==2) {
        if(!width || width>320 || !height || height>240 || stride!=width*2 || length!=stride*height || flags>1 || key>65535 || (!flags && key)) return Status::Invalid;
      } else return Status::Invalid;
      offset+=length;
    }
    if(offset!=bytes) return Status::Invalid;
    uint32_t crc=0xffffffffu;
    for(uint32_t i=32;i<bytes;i++) {
      if(!(i%1024) && cancel()) return Status::Cancelled;
      crc^=data[i];
      for(unsigned bit=0;bit<8;bit++) crc=(crc>>1)^((crc&1)?0xedb88320u:0);
    }
    if((crc^0xffffffffu)!=word(data+28)) return Status::Invalid;
    m_data=data;m_count=count;return Status::Ok;
  }
  Status open(const uint8_t *data,uint32_t bytes) { return open(data,bytes,[](){return false;}); }
  uint32_t count() const { return m_count; }
  bool at(uint32_t index,Resource &out) const {
    if(!m_data || index>=m_count) return false;
    using Detail::word;const uint8_t *e=m_data+32+64*index;
    out={m_data+word(e+28),word(e+32),static_cast<Kind>(word(e+24)),word(e+36),word(e+40),word(e+44),word(e+48)!=0,static_cast<uint16_t>(word(e+52))};
    return true;
  }
  const char *name(uint32_t index) const { return m_data && index<m_count?reinterpret_cast<const char *>(m_data+32+64*index):nullptr; }
  bool find(const char *id,Resource &out) const {
    if(!id) return false;
    uint8_t key[24]={};unsigned n=0;
    for(;n<24 && id[n];n++) key[n]=static_cast<uint8_t>(id[n]);
    if(n==24 || !Detail::id(key)) return false;
    for(unsigned i=0;i<m_count;i++) if(!Detail::compare(m_data+32+64*i,key)) return at(i,out);
    return false;
  }
private:
  const uint8_t *m_data;uint32_t m_count;
};
// Defined by the local build only when assets.json is present. Applications call
// Bundle::open explicitly (normally Start), not during global initialization.
extern const uint8_t embedded[];
extern const uint32_t embeddedBytes;
}}
#endif

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LINK_GALLERY_CACHE_H
#define LINK_GALLERY_CACHE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
namespace GalleryCache {
constexpr unsigned Width=288,Height=128,Pixels=Width*Height,Bytes=32+Pixels*2;
inline uint32_t word(const uint8_t *bytes) {return uint32_t(bytes[0])|(uint32_t(bytes[1])<<8)|(uint32_t(bytes[2])<<16)|(uint32_t(bytes[3])<<24);}
inline uint32_t checksum(const uint8_t *bytes,unsigned size) {
  uint32_t value=2166136261u;for(unsigned i=0;i<size;i++) value=(value^bytes[i])*16777619u;return value;
}
inline bool headerValid(const uint8_t *header) {
  return !memcmp(header,"LFGAL1\r\n",8) && word(header+8)==Width && word(header+12)==Height &&
    word(header+16)==Pixels*2 && !word(header+24) && !word(header+28);
}
// Validate while streaming. The candidate owns a separate bounded pixel buffer;
// no file is committed and no displayed allocation is changed by append().
class Candidate {
public:
  Candidate()=default;
  Candidate(const Candidate &)=delete;
  Candidate &operator=(const Candidate &)=delete;
  ~Candidate() {reset();}
  void reset() {free(m_pixels);m_pixels=nullptr;m_bytes=0;m_hash=2166136261u;m_failed=false;}
  bool append(const void *input,unsigned size) {
    if(m_failed || (size && !input) || size>Bytes-m_bytes) {m_failed=true;return false;}
    const auto *bytes=static_cast<const uint8_t *>(input);unsigned at=0;
    while(at<size && m_bytes<32) m_header[m_bytes++]=bytes[at++];
    if(m_bytes==32 && !m_pixels) {
      if(!headerValid(m_header)) {m_failed=true;return false;}
      m_pixels=static_cast<uint16_t *>(malloc(Pixels*2));
      if(!m_pixels) {m_failed=true;return false;}
    }
    if(at<size) {
      unsigned count=size-at;memcpy(reinterpret_cast<uint8_t *>(m_pixels)+m_bytes-32,bytes+at,count);
      for(unsigned i=at;i<size;i++) m_hash=(m_hash^bytes[i])*16777619u;
      m_bytes+=count;
    }
    return true;
  }
  bool complete() const {return !m_failed && m_pixels && m_bytes==Bytes && m_hash==word(m_header+20);}
  uint16_t *take() {
    if(!complete()) return nullptr;
    auto *result=m_pixels;m_pixels=nullptr;m_failed=true;return result;
  }
private:
  uint8_t m_header[32]{};uint16_t *m_pixels=nullptr;
  unsigned m_bytes=0;uint32_t m_hash=2166136261u;bool m_failed=false;
};
// Own the returned allocation; failure never overwrites the displayed cache.
inline uint16_t *read(const char *name) {
  FILE *file=fopen(name,"rb");if(!file) return nullptr;
  uint8_t header[32];uint16_t *pixels=nullptr;
  bool valid=fread(header,1,32,file)==32 && headerValid(header);
  if(valid) {
    pixels=static_cast<uint16_t *>(malloc(Pixels*2));valid=pixels && fread(pixels,1,Pixels*2,file)==Pixels*2;
    if(valid) valid=fgetc(file)==EOF && !ferror(file) && checksum(reinterpret_cast<uint8_t *>(pixels),Pixels*2)==word(header+20);
  }
  if(fclose(file)!=0) valid=false;
  if(!valid) {free(pixels);return nullptr;}return pixels;
}
}
#endif

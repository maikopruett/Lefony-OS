// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Format-3 root codec used by the production document transaction engine.
#ifndef LEFONY_APP_DOCUMENT_ROOT_H
#define LEFONY_APP_DOCUMENT_ROOT_H
#include "native_app_digest.h"
#include "legacy_app_storage.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace PrimeG2 { namespace AppDocumentRoot {
constexpr unsigned Bytes=240;
constexpr uint32_t PendingUpgrade=1;
constexpr uint32_t ByteStore=0, FileIndex=1;
struct Pair {
  uint32_t package=0,data=0,packageBytes=0,dataBytes=0,dataSchema=0,dataKind=ByteStore;
  uint8_t packageHash[32]={},dataHash[32]={};
};
struct Root {
  uint32_t serial=0,flags=0,highVersion[3]={},format=3;
  Pair current,previous;
};
enum class Result { Ok,Invalid,Unsupported };
namespace Detail {
inline uint32_t get(const uint8_t *p) { return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24; }
inline void put(uint8_t *p,uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=static_cast<uint8_t>(v>>(8*i)); }
inline bool valid(const Pair &p,uint32_t serial) {
  return p.package && p.data && p.package<=serial && p.data<=serial && p.packageBytes>=468 &&
    p.packageBytes<=LegacyAppStorage::MaximumPackage && p.dataBytes<=LegacyAppStorage::MaximumData && p.dataKind<=FileIndex;
}
inline bool empty(const Pair &p) {
  if(p.package || p.data || p.packageBytes || p.dataBytes || p.dataSchema || p.dataKind) return false;
  for(unsigned i=0;i<32;i++) if(p.packageHash[i] || p.dataHash[i]) return false;
  return true;
}
inline void encodePair(uint8_t *out,const Pair &p) {
  put(out,p.package);put(out+4,p.data);put(out+8,p.packageBytes);put(out+12,p.dataBytes);put(out+16,p.dataSchema);
  put(out+20,p.dataKind);memcpy(out+24,p.packageHash,32);memcpy(out+56,p.dataHash,32);
}
inline bool decodePair(const uint8_t *in,Pair &p) {
  p.dataKind=get(in+20);if(p.dataKind>FileIndex) return false;
  p.package=get(in);p.data=get(in+4);p.packageBytes=get(in+8);p.dataBytes=get(in+12);p.dataSchema=get(in+16);
  memcpy(p.packageHash,in+24,32);memcpy(p.dataHash,in+56,32);return true;
}
}
inline bool valid(const Root &r) {
  if((r.format!=3 && r.format!=4) || (r.format==3 && (r.current.dataKind || r.previous.dataKind)) ||
     !r.serial || r.flags&~PendingUpgrade || !Detail::valid(r.current,r.serial)) return false;
  for(auto part:r.highVersion) if(part>999999) return false;
  bool previous=Detail::valid(r.previous,r.serial);
  if(!previous && !Detail::empty(r.previous)) return false;
  if(r.flags&PendingUpgrade && (!previous || r.current.package==r.previous.package)) return false;
  if(previous && r.current.package==r.previous.package && (r.current.packageBytes!=r.previous.packageBytes ||
     memcmp(r.current.packageHash,r.previous.packageHash,32))) return false;
  if(previous && r.current.data==r.previous.data && (r.current.dataBytes!=r.previous.dataBytes ||
     r.current.dataSchema!=r.previous.dataSchema || r.current.dataKind!=r.previous.dataKind ||
     memcmp(r.current.dataHash,r.previous.dataHash,32))) return false;
  return true;
}
// Caller provides an exact 240-byte output buffer. Invalid input preserves it.
inline bool encode(const Root &r,uint8_t *out) {
  if(!out || !valid(r)) return false;
  uint8_t wire[Bytes]={};memcpy(wire,r.format==3?"LFAFILE3":"LFAFILE4",8);Detail::put(wire+8,r.format);Detail::put(wire+12,r.serial);Detail::put(wire+16,r.flags);
  for(unsigned i=0;i<3;i++) Detail::put(wire+20+4*i,r.highVersion[i]);
  Detail::encodePair(wire+32,r.current);Detail::encodePair(wire+120,r.previous);
  NativeAppHash::sha256(wire,Bytes-32,wire+Bytes-32);memcpy(out,wire,Bytes);return true;
}
// A valid hash authenticates no publisher. The storage reader must still hash
// referenced blobs and authenticate the signed package before accepting a pair.
inline Result decode(const uint8_t *wire,size_t size,Root *out) {
  if(!wire || !out || size!=Bytes) return Result::Invalid;
  uint32_t format=Detail::get(wire+8);
  if((format!=3 && format!=4) || memcmp(wire,format==3?"LFAFILE3":"LFAFILE4",8)) return Result::Unsupported;
  uint8_t hash[32];NativeAppHash::sha256(wire,Bytes-32,hash);
  if(memcmp(hash,wire+Bytes-32,32)) return Result::Invalid;
  Root r;r.format=format;r.serial=Detail::get(wire+12);r.flags=Detail::get(wire+16);
  for(unsigned i=0;i<3;i++) r.highVersion[i]=Detail::get(wire+20+4*i);
  if(!Detail::decodePair(wire+32,r.current) || !Detail::decodePair(wire+120,r.previous) || !valid(r)) return Result::Invalid;
  *out=r;return Result::Ok;
}
}}
#endif

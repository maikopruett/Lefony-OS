// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// RSA verification derived from nand_update.cpp, with a separate app key ring.
#ifndef LEFONY_NATIVE_APP_SIGNATURE_H
#define LEFONY_NATIVE_APP_SIGNATURE_H
#include "native_app_digest.h"
#include "app_trust_roots.h"
#if PRIME_G2_EMULATOR
#include "app_emulator_trust_root.h"
#endif
namespace PrimeG2 { namespace NativeAppSignature {
constexpr size_t RSAWords=64;typedef uint32_t BigInt[RSAWords];
// The OS may check its health after completed, bounded verification work.
// This callback must not dispatch events or mutate the package/key buffers.
using Progress = void (*)();
inline void hash(const uint8_t *data,size_t size,uint8_t digest[32],Progress progress) {
  NativeAppHash::SHA256 state;NativeAppHash::shaInit(&state);
  while(size) {
    size_t chunk=size<4096?size:4096;
    NativeAppHash::shaUpdate(&state,data,chunk);data+=chunk;size-=chunk;
    if(progress) progress();
  }
  NativeAppHash::shaFinal(&state,digest);
}
inline void fromWire(BigInt v,const uint8_t*w){for(size_t i=0;i<RSAWords;i++){size_t o=256-(i+1)*4;v[i]=NativeAppHash::be32(w+o);}}
inline int compare(const BigInt a,const BigInt b){for(size_t i=RSAWords;i-->0;)if(a[i]!=b[i])return a[i]<b[i]?-1:1;return 0;}
inline void subtract(BigInt a,const BigInt b){uint64_t borrow=0;for(size_t i=0;i<RSAWords;i++){uint64_t s=uint64_t(b[i])+borrow,v=a[i];a[i]=uint32_t(v-s);borrow=v<s;}}
inline void addMod(BigInt o,const BigInt a,const BigInt b,const BigInt m){uint64_t c=0;for(size_t i=0;i<RSAWords;i++){uint64_t s=uint64_t(a[i])+b[i]+c;o[i]=uint32_t(s);c=s>>32;}if(c||compare(o,m)>=0)subtract(o,m);}
inline void multiplyMod(BigInt o,const BigInt a,const BigInt b,const BigInt m,Progress progress=nullptr){BigInt r={},x,t;memcpy(x,a,sizeof(x));for(size_t bit=0;bit<2048;bit++){if((b[bit/32]>>(bit&31))&1){addMod(t,r,x,m);memcpy(r,t,sizeof(r));}addMod(t,x,x,m);memcpy(x,t,sizeof(x));if(progress && (bit+1)%64==0) progress();}memcpy(o,r,sizeof(r));}
inline bool verifySignature(const uint8_t *prefix,size_t size,const uint8_t *signature,const uint8_t *modulus,Progress progress=nullptr){
  BigInt n,b,r,t;fromWire(n,modulus);fromWire(b,signature);if(compare(b,n)>=0)return false;memcpy(r,b,sizeof(r));for(unsigned i=0;i<16;i++){multiplyMod(t,r,r,n,progress);memcpy(r,t,sizeof(r));}multiplyMod(t,r,b,n,progress);memcpy(r,t,sizeof(r));
  uint8_t em[256];for(size_t i=0;i<RSAWords;i++){uint32_t w=r[i];size_t o=256-(i+1)*4;em[o]=w>>24;em[o+1]=w>>16;em[o+2]=w>>8;em[o+3]=w;}
  uint8_t digest[32];hash(prefix,size,digest,progress);
  const uint8_t der[]={0x30,0x31,0x30,0x0d,0x06,0x09,0x60,0x86,0x48,0x01,0x65,0x03,0x04,0x02,0x01,0x05,0x00,0x04,0x20};
  if(em[0]||em[1]!=1)return false;
  size_t d=2;
  while(d<sizeof(em)&&em[d]==0xff)d++;
  if(d<10||d>=sizeof(em)||em[d++]!=0||
      sizeof(em)-d!=sizeof(der)+sizeof(digest))return false;
  return !memcmp(em+d,der,sizeof(der))&&
    !memcmp(em+d+sizeof(der),digest,sizeof(digest));
}
// The caller selects an already-authorized public key for this operation.
// Selecting that key does not skip any LFAPP1 envelope or signature checks.
// The inner container/ELF must still be validated by the normal loader.
inline bool unwrapWithKey(const uint8_t *package,size_t size,const uint8_t id[32],const uint8_t modulus[256],
                          const uint8_t **payload,size_t *length,Progress progress=nullptr) {
  if (!package || !payload || !length || !id || !modulus || !(modulus[0]&128) || !(modulus[255]&1) ||
      size<468 || size>2101664 ||
      memcmp(package,"LFAPP1\0\0",8)) return false;
  auto word=[](const uint8_t *p) { uint32_t v;memcpy(&v,p,4);return v; };
  if (word(package+8)!=1 || word(package+12)!=size-352 || word(package+16)>1 ||
      word(package+20) || word(package+88) || word(package+92) || memcmp(package+24,id,32)) return false;
  uint8_t digest[32]; hash(package+352,size-352,digest,progress);
  if (memcmp(digest,package+56,32) || !verifySignature(package,96,package+96,modulus,progress)) return false;
  *payload=package+352; *length=size-352;
  return true;
}
// Existing callers retain compiled app trust only. Adding a registry does not
// enroll any key or change the physical/emulator policy of this entry point.
inline bool unwrap(const uint8_t *package,size_t size,const uint8_t **payload,size_t *length,Progress progress=nullptr) {
  if (!package || size<468 || size>2101664) return false;
  const LefonyAppTrustRoot *key=nullptr;
  for (unsigned i=0;i!=LefonyAppTrustRootCount;i++)
    if (!memcmp(package+24,LefonyAppTrustRoots[i].id,32)) key=&LefonyAppTrustRoots[i];
#if PRIME_G2_EMULATOR
  if (!memcmp(package+24,LefonyEmulatorAppKey.id,32)) key=&LefonyEmulatorAppKey;
#endif
  if (!key) return false;
  return unwrapWithKey(package,size,key->id,key->modulus,payload,length,progress);
}
}}
#endif

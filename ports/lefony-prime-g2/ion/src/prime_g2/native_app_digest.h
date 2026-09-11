// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// SHA-256 implementation shared by provenance with nand_update.cpp; no keys.
#ifndef PRIME_NATIVE_APP_DIGEST_H
#define PRIME_NATIVE_APP_DIGEST_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
namespace PrimeG2 { namespace NativeAppHash {
struct SHA256 { uint32_t state[8]; uint64_t bytes; uint8_t buffer[64]; size_t buffered; };
constexpr uint32_t K[64]={
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
inline uint32_t rr(uint32_t v,unsigned n){return(v>>n)|(v<<(32-n));}
inline uint32_t be32(const uint8_t*p){return(uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];}
inline void shaTransform(SHA256*c,const uint8_t*b){
  uint32_t w[64];for(unsigned i=0;i<16;i++)w[i]=be32(b+i*4);
  for(unsigned i=16;i<64;i++){uint32_t a=w[i-15],d=w[i-2];w[i]=w[i-16]+(rr(a,7)^rr(a,18)^(a>>3))+w[i-7]+(rr(d,17)^rr(d,19)^(d>>10));}
  uint32_t a=c->state[0],b0=c->state[1],cc=c->state[2],d=c->state[3],e=c->state[4],f=c->state[5],g=c->state[6],h=c->state[7];
  for(unsigned i=0;i<64;i++){uint32_t t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+K[i]+w[i];uint32_t t2=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b0)^(a&cc)^(b0&cc));h=g;g=f;f=e;e=d+t1;d=cc;cc=b0;b0=a;a=t1+t2;}
  c->state[0]+=a;c->state[1]+=b0;c->state[2]+=cc;c->state[3]+=d;c->state[4]+=e;c->state[5]+=f;c->state[6]+=g;c->state[7]+=h;
}
inline void shaInit(SHA256*c){const uint32_t v[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};memcpy(c->state,v,sizeof(v));c->bytes=0;c->buffered=0;}
inline void shaUpdate(SHA256*c,const uint8_t*p,size_t n){c->bytes+=n;while(n){size_t a=64-c->buffered;if(a>n)a=n;memcpy(c->buffer+c->buffered,p,a);c->buffered+=a;p+=a;n-=a;if(c->buffered==64){shaTransform(c,c->buffer);c->buffered=0;}}}
inline void shaFinal(SHA256*c,uint8_t out[32]){uint64_t bits=c->bytes*8;c->buffer[c->buffered++]=0x80;if(c->buffered>56){memset(c->buffer+c->buffered,0,64-c->buffered);shaTransform(c,c->buffer);c->buffered=0;}memset(c->buffer+c->buffered,0,56-c->buffered);for(unsigned i=0;i<8;i++)c->buffer[63-i]=bits>>(i*8);shaTransform(c,c->buffer);for(unsigned i=0;i<8;i++){out[i*4]=c->state[i]>>24;out[i*4+1]=c->state[i]>>16;out[i*4+2]=c->state[i]>>8;out[i*4+3]=c->state[i];}}
inline void sha256(const uint8_t*p,size_t n,uint8_t out[32]){SHA256 c;shaInit(&c);shaUpdate(&c,p,n);shaFinal(&c,out);}

}}
#endif

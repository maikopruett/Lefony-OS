// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Small app-local memory routines required by freestanding compiler output.
#include <stddef.h>
#include <stdint.h>
extern "C" void *memcpy(void *destination,const void *source,size_t size) {
  auto *out=static_cast<volatile unsigned char *>(destination);
  const auto *in=static_cast<const volatile unsigned char *>(source);
  for(size_t i=0;i<size;i++) out[i]=in[i];
  return destination;
}
extern "C" void *memset(void *destination,int value,size_t size) {
  auto *out=static_cast<volatile unsigned char *>(destination);
  for(size_t i=0;i<size;i++) out[i]=static_cast<unsigned char>(value);
  return destination;
}
extern "C" void *memmove(void *destination,const void *source,size_t size) {
  auto *out=static_cast<volatile unsigned char *>(destination);
  const auto *in=static_cast<const volatile unsigned char *>(source);
  if(reinterpret_cast<uintptr_t>(destination)<reinterpret_cast<uintptr_t>(source)) {
    for(size_t i=0;i<size;i++) out[i]=in[i];
  } else { while(size) { --size;out[size]=in[size]; } }
  return destination;
}
extern "C" int memcmp(const void *a,const void *b,size_t size) {
  const auto *left=static_cast<const unsigned char *>(a),*right=static_cast<const unsigned char *>(b);
  for(size_t i=0;i<size;i++) { if(left[i]!=right[i]) return left[i]<right[i]?-1:1; }return 0;
}

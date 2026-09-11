// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_ICON_H
#define LEFONY_APP_ICON_H
#include "native_app_signature.h"
#include <string.h>
namespace PrimeG2 { namespace AppIcon {
constexpr unsigned Width = 55, Height = 56, PixelBytes = Width * Height * 2;
constexpr unsigned PackageBytes = 352 + 64 + PixelBytes;
constexpr unsigned CompressedBytes = 1 + (PixelBytes - 15) / 255 + 1 + PixelBytes;
// A distinct signed payload domain: never interpreted as executable app bytes.
inline const uint8_t *pixels(const uint8_t *package, size_t size, const uint8_t hash[32]) {
  const uint8_t *payload; size_t bytes;
  if (size != PackageBytes || !NativeAppSignature::unwrap(package,size,&payload,&bytes) ||
      bytes != 64 + PixelBytes || memcmp(payload,"LFICON1\0",8) ||
      (hash && memcmp(payload+8,hash,32))) return nullptr;
  const uint8_t dimensions[8] = {Width,0,0,0,Height,0,0,0};
  if (memcmp(payload+40,dimensions,8)) return nullptr;
  for (unsigned i=48;i<64;i++) if (payload[i]) return nullptr;
  return payload+64;
}
inline void compress(const uint8_t *pixels, uint8_t output[CompressedBytes]) {
  // A single LZ4 literal sequence: fixed size, no untrusted compressed input.
  output[0]=0xf0; unsigned cursor=1, remaining=PixelBytes-15;
  while (remaining>=255) { output[cursor++]=255; remaining-=255; }
  output[cursor++]=remaining; memcpy(output+cursor,pixels,PixelBytes);
}
}}
#endif

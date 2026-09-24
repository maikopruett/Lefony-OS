// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_TEXT_H
#define LEFONY_APP_TEXT_H
#include "lefony/text_wire.h"
namespace PrimeG2 { namespace AppText {
// Validate complete scalars before invoking the firmware UTF-8 decoder. A
// malformed or unsupported string must never partially alter the surface.
inline bool validText(const char *text,uint32_t length) {
  if(length>LEFONY_TEXT_MAXIMUM || (length && !text)) return false;
  for(uint32_t i=0;i<length;) {
    uint32_t start=i;
    uint32_t c=static_cast<uint8_t>(text[i++]),extra=0,minimum=0;
    if(c<128) {if(c<32 || c==127) return false;continue;}
    if(c>=0xc2 && c<=0xdf) {c&=31;extra=1;minimum=0x80;}
    else if(c>=0xe0 && c<=0xef) {c&=15;extra=2;minimum=0x800;}
    else if(c>=0xf0 && c<=0xf4) {c&=7;extra=3;minimum=0x10000;}
    else return false;
    if(extra>length-i) return false;
    while(extra--) {uint32_t b=static_cast<uint8_t>(text[i++]);if((b&0xc0)!=0x80) return false;c=(c<<6)|(b&63);}
    if(c<minimum || c>0x10ffff || (c>=0xd800 && c<=0xdfff) || (c>=0x80 && c<=0x9f)) return false;
    // Pinned Ion CodePoint::isCombining uses U+0300..U+036F. Kandinsky
    // requires a base before this range, including when the string is clipped.
    if(!start && c>=0x300 && c<=0x36f) return false;
  }
  return true;
}
inline bool validRequest(const LefonyTextRequest &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || r.font>3 || r.textBytes>LEFONY_TEXT_MAXIMUM ||
     r.width || r.height || r.glyphWidth || r.glyphHeight || r.flags || r.reserved ||
     r.foreground>65535 || r.background>65535) return false;
  if(r.operation==LEFONY_TEXT_MEASURE)
    return !r.x && !r.y && !r.clipX && !r.clipY && !r.clipWidth && !r.clipHeight && !r.foreground && !r.background;
  return r.operation==LEFONY_TEXT_DRAW && r.x>=-4096 && r.x<=4096 && r.y>=-4096 && r.y<=4096 &&
    r.clipX>=0 && r.clipX<=320 && r.clipY>=0 && r.clipY<=240 && r.clipWidth>=0 && r.clipWidth<=320-r.clipX &&
    r.clipHeight>=0 && r.clipHeight<=240-r.clipY;
}
}}
#endif

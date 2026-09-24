// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_TYPOGRAPHY_H
#define LEFONY_TYPOGRAPHY_H
#include "text.h"
#include "ui_model.h"
namespace Lefony { namespace UI {
struct TextMetrics { uint32_t width,height,glyphWidth,glyphHeight;int32_t error; };
inline TextMetrics measure(const char *text,unsigned bytes,uint32_t font=LEFONY_FONT_SMALL) {
  auto r=lefony_text_request(LEFONY_TEXT_MEASURE,font,text,bytes);
  int32_t error=lefony_typography(&r);return {r.width,r.height,r.glyphWidth,r.glyphHeight,error};
}
inline int32_t drawText(Box clip,int x,int y,const char *text,unsigned bytes,
                        uint16_t ink,uint16_t paper,uint32_t font=LEFONY_FONT_SMALL) {
  clip=intersect(clip,{0,0,320,240});
  if(!clip.width || !clip.height) return 0;
  auto r=lefony_text_request(LEFONY_TEXT_DRAW,font,text,bytes);
  r.x=x;r.y=y;r.clipX=clip.x;r.clipY=clip.y;r.clipWidth=clip.width;r.clipHeight=clip.height;
  r.foreground=ink;r.background=paper;return lefony_typography(&r);
}
// Only use after UTF-8 validation (for example TextBuffer). Keep combining marks
// with their base when dividing text into measured or rendered cells. Validate
// each resulting chunk with measure before drawing; font support is separate.
inline unsigned nextTextCell(const char *text,unsigned bytes,unsigned at) {
  if(at>=bytes) return bytes;
  at++;while(at<bytes && (static_cast<uint8_t>(text[at])&0xc0)==0x80) at++;
  while(at+1<bytes && (static_cast<uint8_t>(text[at])==0xcc ||
         (static_cast<uint8_t>(text[at])==0xcd && static_cast<uint8_t>(text[at+1])<=0xaf))) at+=2;
  return at;
}
}}
#endif

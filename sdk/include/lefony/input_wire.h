// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_INPUT_WIRE_H
#define LEFONY_INPUT_WIRE_H
#include <stdint.h>
namespace Lefony {
// Experimental copied input snapshot, service 8, discovery bit 2. The original
// ABI 1 callback/event structures remain unchanged. Fixed-width wire types only.
enum class InputKey : uint32_t {
  Unknown=0,Left=1,Right=2,Up=3,Down=4,Confirm=5,Delete=6,
  Digit0=16,Decimal=26,Minus=27,Plus=28,Multiply=29,Divide=30,Power=31,
  LeftParenthesis=32,RightParenthesis=33,Square=34,Sqrt=35,Ln=36,Log=37,
  Sin=38,Cos=39,Tan=40,Exponent=41,Shift=42,Alpha=43,XNT=44,Variable=45,
  Toolbox=46,Comma=47,Back=48,Asin=49,Acos=50,Atan=51,Pi=52,Exp=53,
  Copy=54,Paste=55,Cut=56
};
enum InputModifier : uint32_t { InputShift=1,InputAlpha=2,InputAlphaLock=4 };
enum InputFlag : uint32_t { ContactsChanged=1,TextUnavailable=2 };
struct InputContact {
  constexpr InputContact(uint32_t identifier=0,int32_t px=0,int32_t py=0) : id(identifier),x(px),y(py) {}
  uint32_t id;int32_t x,y;
};
struct InputSnapshot {
  uint32_t size=sizeof(InputSnapshot),version=1,reserved=0;
  uint32_t sequence=0,millis=0,event=0;
  InputKey key=InputKey::Unknown;
  // Native KPP row*8+column (see contracts/keys.json); 255 means unavailable.
  uint32_t physicalKey=255,modifiers=0,repeatFactor=0;
  uint32_t touchPhase=3,contactCount=0,flags=0,textBytes=0;
  InputContact contacts[2]{};
  char text[32]{};
  uint32_t reservedOutput[4]{};
};
static_assert(sizeof(InputContact)==12,"input contact wire size");
static_assert(sizeof(InputSnapshot)==128,"input snapshot wire size");
// Bounded UTF-8 text payload validator; excludes C0/C1 controls, overlong
// encodings, surrogates and values above Unicode's maximum scalar value.
inline bool validInputText(const char *text,uint32_t length) {
  if(length>32 || (length && !text)) return false;
  for(uint32_t i=0;i<length;) {
    uint32_t c=static_cast<uint8_t>(text[i++]),extra=0,minimum=0;
    if(c<128) { if(c<32 || c==127) return false;continue; }
    if(c>=0xc2 && c<=0xdf) { c&=31;extra=1;minimum=0x80; }
    else if(c>=0xe0 && c<=0xef) { c&=15;extra=2;minimum=0x800; }
    else if(c>=0xf0 && c<=0xf4) { c&=7;extra=3;minimum=0x10000; }
    else return false;
    if(extra>length-i) return false;
    while(extra--) { uint32_t byte=static_cast<uint8_t>(text[i++]);if((byte&0xc0)!=0x80) return false;c=(c<<6)|(byte&63); }
    if(c<minimum || c>0x10ffff || (c>=0xd800 && c<=0xdfff) || (c>=0x80 && c<=0x9f)) return false;
  }
  return true;
}
}
#endif

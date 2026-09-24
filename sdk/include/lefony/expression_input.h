// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_EXPRESSION_INPUT_H
#define LEFONY_EXPRESSION_INPUT_H
#include "input_wire.h"
#include "ui_model.h"
namespace Lefony { namespace Expression {
enum class TextStatus { Ok, Full, Unsupported };
// Atomic one-line insertion. Normalize the OS's common serialized math symbols
// into the public scalar grammar; unsupported Unicode and line breaks are errors.
template<unsigned Capacity> TextStatus insertText(UI::TextBuffer<Capacity> &buffer,const char *text,unsigned bytes) {
  if(bytes>1024) return TextStatus::Full;
  if(bytes && !text) return TextStatus::Unsupported;
  struct Mapping {const char *utf8;unsigned bytes;const char *plain;};
  static const Mapping mappings[]={
    {"\xcf\x80",2,"pi"},{"\xc3\x97",2,"*"},{"\xc3\xb7",2,"/"},{"\xc2\xb7",2,"*"},
    {"\xe2\x88\x92",3,"-"},{"\xe1\xb4\x87",3,"e"},{"\xe2\x84\xaf",3,"e"},
    {"\xe2\x88\x9a",3,"sqrt"},{"\xc2\xb2",2,"^2"}};
  UI::TextBuffer<Capacity> next=buffer;
  for(unsigned at=0;at<bytes;) {
    unsigned length=1;const char *plain=text+at;unsigned output=1;
    if(static_cast<uint8_t>(text[at])>=128) {
      bool found=false;
      for(const auto &map:mappings) if(map.bytes<=bytes-at) {
        unsigned matched=0;
        while(matched<map.bytes && text[at+matched]==map.utf8[matched]) matched++;
        if(matched!=map.bytes) continue;
        plain=map.plain;length=map.bytes;output=0;
        while(plain[output]) output++;
        found=true;break;
      }
      if(!found) return TextStatus::Unsupported;
    } else if(text[at]<32 || text[at]==127) return TextStatus::Unsupported;
    if(!next.insert(plain,output)) return TextStatus::Full;
    at+=length;
  }
  buffer=next;return TextStatus::Ok;
}
// Compose the documented scalar grammar from normalized Prime keys. This is
// plain-text editing, not a two-dimensional expression layout. Function tokens
// insert their opening parenthesis; the caller/user supplies the closing one.
template<unsigned Capacity> bool edit(UI::TextBuffer<Capacity> &buffer,const InputSnapshot &input) {
  if(input.event!=1) return false;
  if(input.key==InputKey::Left || input.key==InputKey::Right)
    return buffer.move(input.key==InputKey::Left?-1:1,(input.modifiers&InputShift)!=0);
  if(input.key==InputKey::Delete) return buffer.erase();
  const char *token=nullptr;
  if(!(input.modifiers&InputAlpha)) switch(input.key) {
    case InputKey::Plus:token="+";break;case InputKey::Minus:token="-";break;
    case InputKey::Multiply:token="*";break;case InputKey::Divide:token="/";break;
    case InputKey::Power:token="^";break;case InputKey::LeftParenthesis:token="(";break;
    case InputKey::RightParenthesis:token=")";break;case InputKey::Square:token="^2";break;
    case InputKey::Sqrt:token="sqrt(";break;case InputKey::Exponent:token="e";break;
    case InputKey::Ln:token="ln(";break;case InputKey::Log:token="log10(";break;
    case InputKey::Sin:token="sin(";break;case InputKey::Cos:token="cos(";break;
    case InputKey::Tan:token="tan(";break;case InputKey::Asin:token="asin(";break;
    case InputKey::Acos:token="acos(";break;case InputKey::Atan:token="atan(";break;
    case InputKey::Pi:token="pi";break;case InputKey::Exp:token="exp(";break;
    case InputKey::XNT:token="x";break;
    default:break;
  }
  if(token) { unsigned size=0;while(token[size]) size++;return buffer.insert(token,size); }
  return input.textBytes && insertText(buffer,input.text,input.textBytes)==TextStatus::Ok;
}
}}
#endif

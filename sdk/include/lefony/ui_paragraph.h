// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_PARAGRAPH_H
#define LEFONY_UI_PARAGRAPH_H
#include "typography.h"
namespace Lefony { namespace UI {
struct ParagraphLine { unsigned offset=0,bytes=0,cells=0; };
struct ParagraphMetrics { unsigned lines=0,height=0;bool clipped=false;int32_t error=0; };
// Allocation-free wrapping for the fixed-cell OS fonts. Input must outlive the
// iterator. Plain ASCII spaces separate words; LF and CRLF preserve blank lines.
// Long words break only between a base and its complete combining-mark group.
class ParagraphLayout {
public:
  static constexpr unsigned MaximumBytes=1024;
  ParagraphLayout(const char *text,unsigned bytes,unsigned columns)
    : m_text(text),m_bytes(bytes),m_columns(columns),m_valid(validate(text,bytes) && columns>0),m_done(!bytes) {}
  bool valid() const {return m_valid;}
  bool next(ParagraphLine &line) {
    if(!m_valid || m_done) return false;
    unsigned at=m_at;
    while(plainSpace(at)) at++;
    unsigned start=at,end=at,cells=0,used=0,breakEnd=at,breakNext=at,breakCells=0;
    bool canBreak=false;
    while(at<m_bytes && m_text[at]!='\n' && m_text[at]!='\r') {
      if(cells==m_columns) {
        if(plainSpace(at)) {
          while(plainSpace(at)) at++;
          line={start,end-start,used};
          if(at==m_bytes) {m_done=true;m_at=at;}
          else m_at=at+(m_text[at]=='\r'?2:m_text[at]=='\n'?1:0);
          return true;
        }
        if(canBreak) {end=breakEnd;used=breakCells;at=breakNext;}
        line={start,end-start,used};m_at=at;return true;
      }
      unsigned next=nextTextCell(m_text,m_bytes,at);
      if(plainSpace(at)) {canBreak=true;breakEnd=end;breakNext=next;breakCells=used;}
      else {end=next;used=cells+1;}
      cells++;at=next;
    }
    line={start,end-start,used};
    if(at==m_bytes) {m_done=true;m_at=at;}
    else m_at=at+(m_text[at]=='\r'?2:1);
    return true;
  }
private:
  static bool combining(const char *text,unsigned bytes,unsigned at) {
    return at+1<bytes && (static_cast<uint8_t>(text[at])==0xcc ||
      (static_cast<uint8_t>(text[at])==0xcd && static_cast<uint8_t>(text[at+1])<=0xaf));
  }
  static bool validate(const char *text,unsigned bytes) {
    if(bytes>MaximumBytes || (bytes && !text)) return false;
    bool base=false;
    for(unsigned at=0;at<bytes;) {
      if(text[at]=='\n') {at++;base=false;continue;}
      if(text[at]=='\r') {
        if(at+1==bytes || text[at+1]!='\n') return false;
        at+=2;base=false;continue;
      }
      unsigned end=at+1;
      while(end<bytes && (static_cast<uint8_t>(text[end])&0xc0)==0x80) end++;
      if(!validInputText(text+at,end-at) || (!base && combining(text,bytes,at))) return false;
      at=end;base=true;
    }
    return true;
  }
  bool plainSpace(unsigned at) const {
    return at<m_bytes && m_text[at]==' ' && !combining(m_text,m_bytes,at+1);
  }
  const char *m_text;unsigned m_bytes,m_columns,m_at=0;bool m_valid,m_done;
};
}}
#endif

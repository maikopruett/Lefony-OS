// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_CONTROLS_H
#define LEFONY_UI_CONTROLS_H
#include "ui.h"
#include "ui_model.h"
#include "input.h"
namespace Lefony { namespace UI {
namespace Theme {
constexpr uint16_t Paper=0xf7be,Ink=0x1947,Muted=0x6b6d,Accent=0x2528,Selected=0xdedb,Disabled=0xe71c;
constexpr int GlyphWidth=7,GlyphHeight=14,Gap=6,ControlHeight=32;
}
inline unsigned nextGlyph(const char *text,unsigned length,unsigned index) {
  if(index>=length) return length;
  index++;while(index<length && (static_cast<uint8_t>(text[index])&0xc0)==0x80) index++;return index;
}
inline unsigned glyphCount(const char *text,unsigned length) {
  unsigned count=0;for(unsigned i=0;i<length;i=nextGlyph(text,length,i)) count++;return count;
}
class Canvas {
public:
  explicit Canvas(Box clip={0,0,320,240}) : m_clip(intersect(clip,{0,0,320,240})),m_error(0) {}
  void fill(Box box,uint16_t color) {
    box=intersect(box,m_clip);if(!box.width || !box.height) return;
    int32_t result=Lefony::fill({box.x,box.y,box.width,box.height,color});if(result<0) m_error=result;
  }
  void outline(Box box,uint16_t color,int width=1) {
    if(width<=0 || box.width<width || box.height<width) return;
    // Clip each original edge, so a partially visible control does not acquire
    // a false border at the viewport edge. Widen before coordinate arithmetic.
    auto edge=[&](int64_t x,int64_t y,int64_t w,int64_t h) {
      int64_t right=x+w,bottom=y+h;
      if(x<m_clip.x) x=m_clip.x;
      if(y<m_clip.y) y=m_clip.y;
      if(right>int64_t(m_clip.x)+m_clip.width) right=int64_t(m_clip.x)+m_clip.width;
      if(bottom>int64_t(m_clip.y)+m_clip.height) bottom=int64_t(m_clip.y)+m_clip.height;
      if(right>x && bottom>y) fill({static_cast<int32_t>(x),static_cast<int32_t>(y),static_cast<int32_t>(right-x),static_cast<int32_t>(bottom-y)},color);
    };
    edge(box.x,box.y,box.width,width);edge(box.x,int64_t(box.y)+box.height-width,box.width,width);
    edge(box.x,box.y,width,box.height);edge(int64_t(box.x)+box.width-width,box.y,width,box.height);
  }
  void glyph(int x,int y,char value,uint16_t color,uint16_t background) {
    if(!m_clip.contains(x,y) || int64_t(x)+Theme::GlyphWidth>int64_t(m_clip.x)+m_clip.width ||
       int64_t(y)+Theme::GlyphHeight>int64_t(m_clip.y)+m_clip.height) return;
    if(value<32 || value>126) value='?';
    int32_t result=Lefony::text({x,y,color,background,&value,1});if(result<0) m_error=result;
  }
  void text(Box box,const char *value,unsigned length,uint16_t color=Theme::Ink,uint16_t background=Theme::Paper) {
    if(!value || length>1024 || box.width<Theme::GlyphWidth || box.height<Theme::GlyphHeight) return;
    Box area=intersect(box,m_clip);
    for(unsigned i=0,column=0;i<length && column<46;i=nextGlyph(value,length,i),column++) {
      int64_t x=int64_t(box.x)+column*Theme::GlyphWidth;
      if(x+Theme::GlyphWidth>int64_t(box.x)+box.width) break;
      if(x<area.x || x+Theme::GlyphWidth>int64_t(area.x)+area.width || box.y<area.y || int64_t(box.y)+Theme::GlyphHeight>int64_t(area.y)+area.height) continue;
      glyph(static_cast<int>(x),box.y,static_cast<uint8_t>(value[i])<128?value[i]:'?',color,background);
    }
  }
  int32_t error() const { return m_error; }
private:
  Box m_clip;int32_t m_error;
};
inline void button(Canvas &canvas,Box box,const char *title,bool focused=false,bool pressed=false,bool enabled=true) {
  if(!title) return;
  box=intersect(box,{0,0,320,240});if(box.width<12 || box.height<20) return;
  uint16_t background=enabled?(pressed?Theme::Ink:Theme::Accent):Theme::Disabled;
  canvas.fill(box,background);canvas.outline(box,focused?Theme::Ink:background,focused?2:1);
  unsigned length=Lefony::length(title,128),width=glyphCount(title,length)*Theme::GlyphWidth;
  int offset=width<static_cast<unsigned>(box.width-12)?(box.width-static_cast<int>(width))/2:6;
  canvas.text({box.x+offset,box.y+(box.height-Theme::GlyphHeight)/2,box.width-offset-6,Theme::GlyphHeight},title,length,
              enabled?Lefony::White:Theme::Muted,background);
}
inline void toggle(Canvas &canvas,Box box,const char *title,bool value,bool focused=false,bool enabled=true) {
  if(!title) return;
  box=intersect(box,{0,0,320,240});if(box.width<50 || box.height<20) return;
  uint16_t background=enabled?Lefony::White:Theme::Disabled;
  canvas.fill(box,background);canvas.outline(box,focused?Theme::Accent:Theme::Muted,focused?2:1);
  const char *state=value?"[x]":"[ ]";
  int y=box.y+(box.height-14)/2;
  canvas.text({box.x+6,y,28,14},state,3,Theme::Ink,background);
  canvas.text({box.x+38,y,box.width-44,14},title,Lefony::length(title),enabled?Theme::Ink:Theme::Muted,background);
}
inline void progress(Canvas &canvas,Box box,uint32_t completed,uint32_t total) {
  box=intersect(box,{0,0,320,240});canvas.fill(box,Theme::Disabled);
  if(!total || box.width<=0) return;
  if(completed>total) completed=total;
  canvas.fill({box.x,box.y,static_cast<int32_t>(uint64_t(box.width)*completed/total),box.height},Theme::Accent);
}
template<unsigned Capacity> void field(Canvas &canvas,Box box,const TextBuffer<Capacity> &value,bool focused,bool enabled=true) {
  box=intersect(box,{0,0,320,240});if(box.width<20 || box.height<22) return;
  uint16_t background=enabled?Lefony::White:Theme::Disabled;
  canvas.fill(box,background);canvas.outline(box,focused?Theme::Accent:Theme::Muted,focused?2:1);
  unsigned visible=static_cast<unsigned>(box.width-12)/Theme::GlyphWidth;
  unsigned caret=glyphCount(value.text(),value.caret()),scroll=caret>visible?caret-visible:0;
  unsigned column=0;
  for(unsigned i=0;i<value.size();i=nextGlyph(value.text(),value.size(),i),column++) {
    if(column<scroll) continue;
    if(column-scroll>=visible) break;
    uint16_t cell=focused && i>=value.selectionStart() && i<value.selectionEnd()?Theme::Selected:background;
    canvas.glyph(box.x+6+static_cast<int>(column-scroll)*Theme::GlyphWidth,box.y+(box.height-14)/2,
                 static_cast<uint8_t>(value.text()[i])<128?value.text()[i]:'?',enabled?Theme::Ink:Theme::Muted,cell);
  }
  if(focused && enabled) canvas.fill({box.x+6+static_cast<int>(caret-scroll)*Theme::GlyphWidth,box.y+(box.height-16)/2,1,16},Theme::Ink);
}
template<unsigned Capacity> bool edit(TextBuffer<Capacity> &buffer,const InputSnapshot &input) {
  if(input.event!=1) return false;
  bool extend=(input.modifiers&InputShift)!=0;
  if(input.key==InputKey::Left || input.key==InputKey::Right) return buffer.move(input.key==InputKey::Left?-1:1,extend);
  if(input.key==InputKey::Delete) return buffer.erase();
  return input.textBytes && buffer.insert(input.text,input.textBytes);
}
inline bool read(Input legacy,InputSnapshot &snapshot) {
  int32_t result=Lefony::readInput(snapshot);
  if(result==0) return true;
  if(result!=-3) return false;
  snapshot=InputSnapshot{};snapshot.event=static_cast<uint32_t>(legacy.event);snapshot.millis=Lefony::millis();
  if(legacy.event==Event::Key) {
    snapshot.key=static_cast<InputKey>(legacy.first);
    if(legacy.first>=16 && legacy.first<=25) { snapshot.text[0]=static_cast<char>('0'+legacy.first-16);snapshot.textBytes=1; }
    if(legacy.first==26 || legacy.first==27) { snapshot.text[0]=legacy.first==26?'.':'-';snapshot.textBytes=1; }
  }
  if(legacy.event==Event::Touch) {
    snapshot.touchPhase=static_cast<uint32_t>(legacy.phase());
    snapshot.contactCount=snapshot.touchPhase<2?legacy.second>>8:0;
    snapshot.contacts[0]={0,legacy.x(),legacy.y()};
  }
  return true;
}
template<unsigned Capacity=8> class Navigation {
  static_assert(Capacity>0 && Capacity<=8,"navigation capacity must be 1..8");
public:
  struct Restored { bool ok;uint32_t screen,focus; };
  constexpr Navigation(uint32_t initial=1) : m_entries{},m_count(0),m_screen(initial),m_hardwareBack(false) {}
  bool push(uint32_t next,uint32_t currentFocus) {
    if(!next || m_count==Capacity) return false;
    int32_t result=Lefony::navigationDepth(m_count+1);if(result<0 && result!=-3) return false;
    m_hardwareBack=result==0;m_entries[m_count++]={m_screen,currentFocus};m_screen=next;return true;
  }
  Restored pop() {
    if(!m_count) return {false,m_screen,0};
    int32_t result=Lefony::navigationDepth(m_count-1);if(result<0 && result!=-3) return {false,m_screen,0};
    m_hardwareBack=result==0;Entry entry=m_entries[--m_count];m_screen=entry.screen;return {true,entry.screen,entry.focus};
  }
  unsigned depth() const { return m_count; }
  uint32_t screen() const { return m_screen; }
  bool hardwareBack() const { return m_hardwareBack; }
private:
  struct Entry { uint32_t screen,focus; };
  Entry m_entries[Capacity];unsigned m_count;uint32_t m_screen;bool m_hardwareBack;
};
}}
#endif

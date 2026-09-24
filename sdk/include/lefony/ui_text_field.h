// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_TEXT_FIELD_H
#define LEFONY_UI_TEXT_FIELD_H
#include "typography.h"
namespace Lefony { namespace UI {
struct TextFieldView {unsigned caret,cells,visible,scroll;};
// The same cell boundaries and viewport are used for painting and hit testing.
// UINT32_MAX retains the older stateless, caret-at-right scrolling behavior.
template<unsigned Capacity> TextFieldView textFieldView(const TextBuffer<Capacity> &text,
    int32_t width,unsigned glyphWidth,unsigned preferred=UINT32_MAX) {
  TextFieldView view{};
  for(unsigned at=0;at<text.size();at=nextTextCell(text.text(),text.size(),at)) {
    if(at<text.caret()) view.caret++;
    view.cells++;
  }
  view.visible=width>14 && glyphWidth?static_cast<unsigned>(width-14)/glyphWidth:0;
  unsigned maximum=view.cells>view.visible?view.cells-view.visible:0;
  view.scroll=preferred==UINT32_MAX?maximum:preferred>maximum?maximum:preferred;
  if(view.caret<view.scroll) view.scroll=view.caret;
  if(view.caret-view.scroll>view.visible) view.scroll=view.caret-view.visible;
  if(preferred==UINT32_MAX) view.scroll=view.caret>view.visible?view.caret-view.visible:0;
  return view;
}

// Optional state for Widgets::field. A tap places the caret; a captured drag
// selects whole rendered cells. This model never changes text or saves it.
class TextFieldModel {
public:
  bool captured() const {return m_captured;}
  bool contains(int32_t x,int32_t y) const {return m_ready && m_clip.contains(x,y);}
  void disable() {m_ready=m_captured=false;}
  template<unsigned Capacity> TextFieldView view(const TextBuffer<Capacity> &text,Box box,
      Box clip,unsigned glyphWidth,bool enabled=true) {
    auto result=textFieldView(text,box.width,glyphWidth,m_scroll);
    clip=intersect(box,clip);
    if(!same(box,m_box) || !same(clip,m_clip) || glyphWidth!=m_glyphWidth) m_captured=false;
    m_box=box;m_clip=clip;m_glyphWidth=glyphWidth;m_visible=result.visible;m_scroll=result.scroll;
    m_ready=enabled && box.width>=20 && box.height>=22 && m_visible && clip.width>0 && clip.height>0;
    if(!m_ready) m_captured=false;
    return result;
  }
  // Call before keyboard/programmatic edits, navigation, disabling or resizing.
  // Restore a cancelled gesture's original selection and viewport, never bytes.
  template<unsigned Capacity> bool cancel(TextBuffer<Capacity> &text) {
    if(!m_captured) return false;
    bool changed=text.caret()!=m_initialCaret || text.anchor()!=m_initialAnchor;
    text.select(m_initialCaret,m_initialAnchor);m_scroll=m_initialScroll;m_captured=false;return changed;
  }
  template<unsigned Capacity> bool touch(TextBuffer<Capacity> &text,const InputSnapshot &input) {
    if(input.event!=3) return false;
    unsigned phase=input.touchPhase,contacts=input.contactCount;
    const auto &contact=input.contacts[0];
    if(!m_ready || phase>2 || contacts>1 || (input.flags&ContactsChanged) || !contains(contact.x,contact.y)) return cancel(text);
    if(phase==0) {
      cancel(text);if(contacts!=1) return false;
      m_initialCaret=text.caret();m_initialAnchor=text.anchor();m_initialScroll=m_scroll;
      m_contact=contact.id;m_captured=true;m_anchor=hit(text,contact.x);
      bool changed=text.caret()!=m_anchor || text.anchor()!=m_anchor;
      text.select(m_anchor,m_anchor);return changed;
    }
    if(!m_captured) return false;
    if((phase==1 && contacts!=1) || (phase==2 && contacts!=0) || contact.id!=m_contact) return cancel(text);
    // A move in the horizontal inset reveals one more cell. Holding a finger
    // still has no timer-driven scrolling; keyboard navigation remains available.
    if(phase==1) {
      auto view=textFieldView(text,m_box.width,m_glyphWidth,m_scroll);
      unsigned maximum=view.cells>m_visible?view.cells-m_visible:0;
      if(int64_t(contact.x)<int64_t(m_box.x)+6 && m_scroll) m_scroll--;
      else if(int64_t(contact.x)>=int64_t(m_box.x)+6+int64_t(m_visible)*m_glyphWidth && m_scroll<maximum) m_scroll++;
    }
    unsigned caret=hit(text,contact.x);
    bool changed=text.caret()!=caret || text.anchor()!=m_anchor;
    text.select(caret,m_anchor);if(phase==2) m_captured=false;return changed;
  }
private:
  static bool same(Box a,Box b) {return a.x==b.x && a.y==b.y && a.width==b.width && a.height==b.height;}
  template<unsigned Capacity> unsigned hit(const TextBuffer<Capacity> &text,int32_t x) const {
    int64_t position=int64_t(x)-m_box.x-6;
    unsigned column=position<=0?0:static_cast<unsigned>((position+m_glyphWidth/2)/m_glyphWidth);
    if(column>m_visible) column=m_visible;
    column+=m_scroll;unsigned at=0;
    while(column-- && at<text.size()) at=nextTextCell(text.text(),text.size(),at);
    return at;
  }
  Box m_box{},m_clip{};
  unsigned m_glyphWidth=0,m_visible=0,m_scroll=0,m_initialCaret=0,m_initialAnchor=0,m_initialScroll=0,m_anchor=0;
  uint32_t m_contact=0;bool m_ready=false,m_captured=false;
};
}}
#endif

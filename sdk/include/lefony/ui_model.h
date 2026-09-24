// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_MODEL_H
#define LEFONY_UI_MODEL_H
#include <stdint.h>
#include <stddef.h>
#include "input_wire.h"
namespace Lefony { namespace UI {
struct Box {
  int32_t x,y,width,height;
  bool contains(int32_t px,int32_t py) const {
    return width>0 && height>0 && px>=x && py>=y && int64_t(px)-x<width && int64_t(py)-y<height;
  }
};
inline Box intersect(Box a,Box b) {
  int64_t left=a.x>b.x?a.x:b.x,top=a.y>b.y?a.y:b.y;
  int64_t ar=int64_t(a.x)+(a.width>0?a.width:0),br=int64_t(b.x)+(b.width>0?b.width:0);
  int64_t ab=int64_t(a.y)+(a.height>0?a.height:0),bb=int64_t(b.y)+(b.height>0?b.height:0);
  int64_t right=ar<br?ar:br,bottom=ab<bb?ab:bb;
  // The intersection cannot be wider/taller than either input's int32 extent.
  return {static_cast<int32_t>(left),static_cast<int32_t>(top),
    static_cast<int32_t>(right>left?right-left:0),static_cast<int32_t>(bottom>top?bottom-top:0)};
}
class Column {
public:
  constexpr Column(Box bounds,int32_t gap=6) : m_bounds(bounds),m_gap(gap>=0?gap:0),m_used(0) {}
  Box take(int32_t height) {
    if(height<=0 || m_bounds.height<0 || m_used>=m_bounds.height) return {m_bounds.x,m_bounds.y,0,0};
    int32_t available=m_bounds.height-m_used;if(height>available) height=available;
    int64_t y=int64_t(m_bounds.y)+m_used;
    if(y>INT32_MAX || y<INT32_MIN) return {m_bounds.x,m_bounds.y,0,0};
    Box result{m_bounds.x,static_cast<int32_t>(y),m_bounds.width>0?m_bounds.width:0,height};
    int64_t used=int64_t(m_used)+height+m_gap;m_used=used<m_bounds.height?static_cast<int32_t>(used):m_bounds.height;
    return result;
  }
private:
  Box m_bounds;int32_t m_gap,m_used;
};
class Row {
public:
  constexpr Row(Box bounds,int32_t gap=6) : m_column({bounds.y,bounds.x,bounds.height,bounds.width},gap) {}
  Box take(int32_t width) { Box box=m_column.take(width);return {box.y,box.x,box.height,box.width}; }
private:
  Column m_column;
};
// Focus/capture state is independent of rendering. IDs are app-supplied stable
// nonzero values. Rebuilding a screen never retains pointers to its old nodes.
template<unsigned Capacity=32> class Focus {
  static_assert(Capacity>0 && Capacity<=64,"focus capacity must be 1..64");
public:
  constexpr Focus() : m_items{},m_size(0),m_focused(0),m_pressed(0),m_blocked(false) {}
  void clear() { m_size=0;m_focused=0;cancel(); }
  bool add(uint32_t id,Box bounds,bool enabled=true) {
    if(!id || m_size==Capacity || bounds.width<=0 || bounds.height<=0) return false;
    for(unsigned i=0;i<m_size;i++) if(m_items[i].id==id) return false;
    m_items[m_size++]={id,bounds,enabled};if(!m_focused && enabled) m_focused=id;return true;
  }
  bool select(uint32_t id) {
    cancel();for(unsigned i=0;i<m_size;i++) if(m_items[i].id==id && m_items[i].enabled) { m_focused=id;return true; }return false;
  }
  bool enable(uint32_t id,bool enabled) {
    for(unsigned i=0;i<m_size;i++) if(m_items[i].id==id) {
      m_items[i].enabled=enabled;
      if(m_pressed==id) cancel();
      if(!enabled && m_focused==id) { m_focused=0;move(1); }
      if(enabled && !m_focused) m_focused=id;
      return true;
    }
    return false;
  }
  uint32_t focused() const { return m_focused; }
  uint32_t pressed() const { return m_pressed; }
  void cancel() { m_pressed=0;m_blocked=true; }
  bool move(int direction) {
    cancel();if(!m_size || !direction) return false;
    int start=direction>0?-1:0;
    for(unsigned i=0;i<m_size;i++) if(m_items[i].id==m_focused) start=static_cast<int>(i);
    for(unsigned step=1;step<=m_size;step++) {
      int next=(start+(direction>0?static_cast<int>(step):-static_cast<int>(step))+static_cast<int>(m_size)*2)%static_cast<int>(m_size);
      if(m_items[next].enabled) { m_focused=m_items[next].id;return true; }
    }
    return false;
  }
  uint32_t confirm() { cancel();return m_focused; }
  // Down begins capture. Moving outside, multi-touch, changed contact sets or
  // cancellation prevent activation until a fresh single-finger Down.
  uint32_t touch(uint32_t phase,uint32_t contacts,int32_t x,int32_t y,bool changed=false) {
    if(phase==3 || contacts>1 || changed) { cancel();return 0; }
    if(phase==0) {
      m_blocked=false;m_pressed=0;
      if(contacts!=1) { cancel();return 0; }
      for(unsigned i=m_size;i>0;i--) {
        const Item &item=m_items[i-1];
        if(item.bounds.contains(x,y)) { if(item.enabled) { m_focused=item.id;m_pressed=item.id; }break; }
      }
      return 0;
    }
    if(m_blocked || !m_pressed) return 0;
    bool inside=false;
    for(unsigned i=0;i<m_size;i++) if(m_items[i].id==m_pressed) inside=m_items[i].enabled && m_items[i].bounds.contains(x,y);
    if(!inside) { cancel();return 0; }
    if(phase==2) { uint32_t activated=m_pressed;cancel();return activated; }
    if(phase!=1 || contacts!=1) cancel();
    return 0;
  }
private:
  struct Item { uint32_t id;Box bounds;bool enabled; };
  Item m_items[Capacity];unsigned m_size;uint32_t m_focused,m_pressed;bool m_blocked;
};
template<unsigned Capacity=128> class TextBuffer {
  static_assert(Capacity>=2 && Capacity<=1024,"text capacity must be 2..1024 including NUL");
public:
  constexpr TextBuffer() : m_text{},m_size(0),m_caret(0),m_anchor(0) {}
  const char *text() const { return m_text; }
  unsigned size() const { return m_size; }
  unsigned caret() const { return m_caret; }
  unsigned anchor() const { return m_anchor; }
  unsigned selectionStart() const { return m_caret<m_anchor?m_caret:m_anchor; }
  unsigned selectionEnd() const { return m_caret>m_anchor?m_caret:m_anchor; }
  void clear() { m_size=m_caret=m_anchor=0;m_text[0]=0; }
  void selectAll() { m_anchor=0;m_caret=m_size; }
  // Byte offsets must be UTF-8 code-point boundaries. Invalid selections leave
  // both endpoints untouched; text-field hit testing supplies whole-cell ends.
  bool select(unsigned caret,unsigned anchor) {
    if(caret>m_size || anchor>m_size || continuation(m_text[caret]) || continuation(m_text[anchor])) return false;
    m_caret=caret;m_anchor=anchor;return true;
  }
  bool set(const char *text,unsigned size) {
    if(size>=Capacity || (size && !text)) return false;
    TextBuffer next;
    for(unsigned at=0;at<size;) {
      unsigned end=size-at>32?at+32:size;
      while(end<size && end>at && continuation(text[end])) end--;
      if(end==at || !next.insert(text+at,end-at)) return false;
      at=end;
    }
    *this=next;return true;
  }
  bool insert(const char *text,unsigned size) {
    // Public input chunks are <=32 bytes. Larger text may be inserted in
    // explicitly checked chunks; no silent UTF-8 truncation takes place.
    if(!validInputText(text,size)) return false;
    unsigned start=selectionStart(),end=selectionEnd(),remaining=m_size-(end-start);
    if(size>Capacity-1-remaining) return false;
    // Copy first: callers may insert a range of this buffer into itself.
    char copy[32];for(unsigned i=0;i<size;i++) copy[i]=text[i];
    if(size>=end-start) {
      for(unsigned i=m_size+1;i>end;i--) m_text[i-1-(end-start)+size]=m_text[i-1];
    } else {
      for(unsigned i=end;i<=m_size;i++) m_text[i-(end-start)+size]=m_text[i];
    }
    for(unsigned i=0;i<size;i++) m_text[start+i]=copy[i];
    m_size=remaining+size;m_caret=m_anchor=start+size;return true;
  }
  // Atomically replace the selection with a larger complete UTF-8 payload.
  // Clipboard callers can validate/insert once without exposing partial edits.
  bool insertText(const char *text,unsigned size) {
    unsigned remaining=m_size-(selectionEnd()-selectionStart());
    if(size>Capacity-1-remaining || (size && !text)) return false;
    TextBuffer next=*this;
    if(!size) return insert(nullptr,0);
    for(unsigned at=0;at<size;) {
      unsigned end=size-at>32?at+32:size;
      while(end<size && end>at && continuation(text[end])) end--;
      if(end==at || !next.insert(text+at,end-at)) return false;
      at=end;
    }
    *this=next;return true;
  }
  bool erase() {
    if(m_caret==m_anchor) { if(!m_caret) return false;m_anchor=previous(m_caret); }
    return insert(nullptr,0);
  }
  bool move(int direction,bool extend=false) {
    if(!direction) return false;
    unsigned next;
    if(!extend && m_caret!=m_anchor) next=direction<0?selectionStart():selectionEnd();
    else next=direction<0?previous(m_caret):following(m_caret);
    bool changed=next!=m_caret || (!extend && m_anchor!=next);
    m_caret=next;if(!extend) m_anchor=next;return changed;
  }
private:
  static bool continuation(char c) { return (static_cast<uint8_t>(c)&0xc0)==0x80; }
  unsigned previous(unsigned offset) const { if(!offset) return 0;offset--;while(offset && continuation(m_text[offset])) offset--;return offset; }
  unsigned following(unsigned offset) const { if(offset==m_size) return offset;offset++;while(offset<m_size && continuation(m_text[offset])) offset++;return offset; }
  char m_text[Capacity];unsigned m_size,m_caret,m_anchor;
};
// Bounded slider interaction, independent of drawing. A cancelled/outside or
// multi-contact drag restores its starting value; callers decide when to save.
class SliderModel {
public:
  SliderModel(unsigned minimum=0,unsigned maximum=100,unsigned value=0)
    : m_min(minimum),m_max(maximum<minimum?minimum:maximum),m_value(value),m_initial(value),m_dragging(false) {set(value);}
  unsigned value() const {return m_value;}
  bool dragging() const {return m_dragging;}
  void set(unsigned value) {cancel();m_value=value<m_min?m_min:value>m_max?m_max:value;}
  bool move(int direction) {
    cancel();unsigned next=direction<0?(m_value>m_min?m_value-1:m_value):direction>0?(m_value<m_max?m_value+1:m_value):m_value;
    bool changed=next!=m_value;m_value=next;return changed;
  }
  bool cancel() {bool changed=m_dragging && m_value!=m_initial;if(m_dragging) m_value=m_initial;m_dragging=false;return changed;}
  bool touch(Box box,uint32_t phase,uint32_t contacts,int32_t x,int32_t y,bool changed=false) {
    if(phase==3 || contacts>1 || changed || !box.contains(x,y) || box.width<21) return cancel();
    if(phase==0) {if(contacts!=1) return cancel();cancel();m_initial=m_value;m_dragging=true;}
    if(!m_dragging) return false;
    if((phase==1 && contacts!=1) || (phase!=0 && phase!=1 && phase!=2)) return cancel();
    // Match Widgets::slider's thumb centers, ten pixels inside each edge.
    int64_t position=int64_t(x)-box.x-10;unsigned span=box.width-20;
    if(position<0) position=0;
    if(position>span) position=span;
    unsigned next=m_min+static_cast<unsigned>((uint64_t(position)*(m_max-m_min)+span/2)/span);
    bool updated=next!=m_value;m_value=next;if(phase==2) m_dragging=false;return updated;
  }
private:
  unsigned m_min,m_max,m_value,m_initial;bool m_dragging;
};
// Selection uses absolute row indices. The default retains whole-row paging;
// layout() enables a pixel viewport with clipped rows and captured touch drags.
class ListModel {
public:
  constexpr explicit ListModel(unsigned page=3) : m_height(page?page:1) {}
  bool layout(Box bounds,unsigned stride,unsigned gap=0) {
    if(bounds.width<=0 || bounds.height<=0 || bounds.width>32767 || bounds.height>32767 ||
       !stride || stride>32767 || gap>=stride || int64_t(bounds.x)+bounds.width>INT32_MAX ||
       int64_t(bounds.y)+bounds.height>INT32_MAX) return false;
    if(m_bounds.x==bounds.x && m_bounds.y==bounds.y && m_bounds.width==bounds.width &&
       m_bounds.height==bounds.height && m_stride==stride && m_gap==gap) return true;
    cancel();m_offset=m_offset/m_stride*stride;m_bounds=bounds;m_height=bounds.height;m_stride=stride;m_gap=gap;
    reveal();return true;
  }
  void count(unsigned count) {
    if(m_count==count) return;
    cancel();m_count=count;if(m_selected>=count) m_selected=count?count-1:0;reveal();
  }
  bool select(unsigned index) {if(index>=m_count) return false;cancel();m_selected=index;reveal();return true;}
  bool move(int direction) {
    cancel();if(!m_count || !direction) return false;
    unsigned next=direction<0?(m_selected?m_selected-1:0):(m_selected+1<m_count?m_selected+1:m_selected);
    if(next==m_selected) {reveal();return false;}
    return select(next);
  }
  unsigned selected() const {return m_selected;}
  unsigned first() const {
    uint64_t row=m_offset/m_stride;
    if(m_offset%m_stride>=m_stride-m_gap) row++;
    return static_cast<unsigned>(row<m_count?row:m_count);
  }
  unsigned visible() const {
    uint64_t end=(m_offset+m_height+m_stride-1)/m_stride;
    if(end>m_count) end=m_count;
    unsigned begin=first();return end>begin?static_cast<unsigned>(end-begin):0;
  }
  uint64_t offset() const {return m_offset;}
  uint64_t extent() const {return m_count?uint64_t(m_count)*m_stride-m_gap:0;}
  uint64_t maximumOffset() const {return extent()>m_height?extent()-m_height:0;}
  unsigned viewportHeight() const {return m_height;}
  Box bounds() const {return m_bounds;}
  // Only visible rows have drawable bounds. Use the original row rectangle for
  // painting and its intersection with bounds() for focus/hit geometry.
  Box row(unsigned index) const {
    if(index<first() || uint64_t(index)>=uint64_t(first())+visible()) return {0,0,0,0};
    int64_t y=int64_t(m_bounds.y)+int64_t(uint64_t(index)*m_stride)-int64_t(m_offset);
    if(y<INT32_MIN || y>INT32_MAX) return {0,0,0,0};
    return {m_bounds.x,static_cast<int32_t>(y),m_bounds.width,static_cast<int32_t>(m_stride-m_gap)};
  }
  bool captured() const {return m_captured;}
  bool dragging() const {return m_dragging;}
  unsigned pressed() const {return m_captured && !m_dragging?m_pressed:0;}
  void cancel() {m_captured=m_dragging=false;m_pressed=0;}
  // Returns row index + 1 only for a completed tap (zero otherwise). Motion is
  // clamped in pixels, without inertia. Cancel preserves the visible offset but
  // prevents activation; a fresh single-contact Down is required afterward.
  unsigned touch(const InputSnapshot &input) {
    if(input.event!=3) return 0;
    uint32_t phase=input.touchPhase,contacts=input.contactCount;
    if(phase>2 || contacts>1 || (input.flags&ContactsChanged)) {cancel();return 0;}
    const auto &contact=input.contacts[0];
    if(phase==0) {
      cancel();if(contacts!=1 || !m_bounds.contains(contact.x,contact.y)) return 0;
      m_captured=true;m_contact=contact.id;m_x=contact.x;m_y=contact.y;m_start=m_offset;
      m_pressed=hit(contact.x,contact.y);if(m_pressed) m_selected=m_pressed-1;return 0;
    }
    if(!m_captured) return 0;
    if((phase==1 && contacts!=1) || (phase==2 && contacts!=0) || contact.id!=m_contact ||
       contact.x<m_bounds.x || int64_t(contact.x)>=int64_t(m_bounds.x)+m_bounds.width) {cancel();return 0;}
    int64_t dx=int64_t(contact.x)-m_x,dy=int64_t(contact.y)-m_y;
    int64_t ax=dx<0?-dx:dx,ay=dy<0?-dy:dy;
    if(!m_dragging && ax>=6 && ax>ay) {cancel();return 0;}
    if(!m_dragging && ay>=6) {m_dragging=true;m_pressed=0;}
    if(m_dragging) {
      int64_t wanted=int64_t(m_start)-dy;
      m_offset=wanted<0?0:uint64_t(wanted)>maximumOffset()?maximumOffset():static_cast<uint64_t>(wanted);
      // Keep keyboard continuation on a visible row without snapping the drag.
      unsigned begin=first(),count=visible();
      if(count && (m_selected<begin || m_selected-begin>=count)) m_selected=m_selected<begin?begin:begin+count-1;
    }
    if(phase!=2) return 0;
    unsigned action=!m_dragging && m_pressed==hit(contact.x,contact.y)?m_pressed:0;
    cancel();return action;
  }
private:
  unsigned hit(int32_t x,int32_t y) const {
    if(!m_bounds.contains(x,y)) return 0;
    uint64_t index=(m_offset+uint64_t(int64_t(y)-m_bounds.y))/m_stride;
    return index<m_count && row(static_cast<unsigned>(index)).contains(x,y)?static_cast<unsigned>(index)+1:0;
  }
  void reveal() {
    uint64_t top=uint64_t(m_selected)*m_stride,bottom=top+m_stride-m_gap;
    if(top<m_offset || m_stride-m_gap>m_height) m_offset=top;
    else if(bottom>m_offset+m_height) m_offset=bottom-m_height;
    if(m_offset>maximumOffset()) m_offset=maximumOffset();
  }
  Box m_bounds{};
  unsigned m_count=0,m_selected=0,m_height,m_stride=1,m_gap=0,m_pressed=0;
  uint64_t m_offset=0,m_start=0;
  uint32_t m_contact=0;int32_t m_x=0,m_y=0;
  bool m_captured=false,m_dragging=false;
};

}}
#endif

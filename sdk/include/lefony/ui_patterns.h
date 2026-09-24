// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_PATTERNS_H
#define LEFONY_UI_PATTERNS_H
#include "ui_model.h"
namespace Lefony { namespace UI {
namespace Detail {
// Exact floor(span*value/maximum). Avoid overflow for large offscreen tracks.
inline uint32_t scale(uint32_t span,uint64_t value,uint64_t maximum) {
  if(!maximum || !value) return 0;
  if(value>=maximum) return span;
  if(span<=UINT64_MAX/value) return static_cast<uint32_t>(uint64_t(span)*value/maximum);
  uint64_t whole=0,remainder=0;
  for(int bit=31;bit>=0;bit--) {
    whole*=2;
    if(remainder>=maximum-remainder) {remainder-=maximum-remainder;whole++;}else remainder+=remainder;
    if(span&(uint32_t(1)<<bit)) {
      if(remainder>=maximum-value) {remainder-=maximum-value;whole++;}else remainder+=value;
    }
  }
  return static_cast<uint32_t>(whole);
}
}

// A two-action confirmation layout. The app owns navigation and action handlers;
// opening the dialog replaces focus so controls behind it cannot receive input.
struct DialogLayout {
  Box panel,title,primary,secondary;
  explicit DialogLayout(Box bounds={12,60,296,126}) : panel(bounds),title{},primary{},secondary{} {
    if(bounds.width<64 || bounds.height<100 || int64_t(bounds.x)+bounds.width>INT32_MAX ||
       int64_t(bounds.y)+bounds.height>INT32_MAX) {panel={};return;}
    int width=(bounds.width-40)/2,y=bounds.y+bounds.height-46;
    title={bounds.x+14,bounds.y+22,bounds.width-28,18};
    primary={bounds.x+14,y,width,32};
    secondary={bounds.x+26+width,y,bounds.width-40-width,32};
  }
  bool valid() const {return panel.width>0;}
  template<unsigned Capacity> bool open(Focus<Capacity> &focus,uint32_t primaryId,uint32_t cancelId,bool enabled=true) const {
    if(!valid()) return false;
    Focus<Capacity> next;
    if(!next.add(primaryId,intersect(primary,{0,0,320,240}),enabled) ||
       !next.add(cancelId,intersect(secondary,{0,0,320,240}))) return false;
    next.select(cancelId);focus=next;return true;
  }
};

// Owned labels and stable action IDs; no pointers to old screens are retained.
// All gestures use ListModel's normal contact identity/cancellation rules.
template<unsigned Capacity=8> class MenuModel {
  static_assert(Capacity>0 && Capacity<=32,"menu capacity must be 1..32");
public:
  bool layout(Box bounds,unsigned rowHeight=30) {return m_list.layout(bounds,rowHeight);}
  void clear() {m_list.cancel();m_count=0;m_selected=Capacity;m_list.count(0);}
  bool add(uint32_t id,const char *title,bool enabled=true) {
    if(!id || !title || m_count==Capacity) return false;
    for(unsigned i=0;i<m_count;i++) if(m_items[i].id==id) return false;
    unsigned size=0;while(size<96 && title[size]) size++;
    TextBuffer<96> text;if(!size || !text.set(title,size)) return false;
    auto &item=m_items[m_count];item.id=id;item.enabled=enabled;
    for(unsigned i=0;i<=size;i++) item.title[i]=text.text()[i];
    m_count++;m_list.count(m_count);
    if(m_selected==Capacity && enabled) {m_selected=m_count-1;m_list.select(m_selected);}
    return true;
  }
  bool enable(uint32_t id,bool value) {
    for(unsigned i=0;i<m_count;i++) if(m_items[i].id==id) {
      if(m_items[i].enabled==value) return true;
      m_list.cancel();m_items[i].enabled=value;
      if(!value && m_selected==i) move(1);
      else if(value && m_selected==Capacity) select(id);
      return true;
    }
    return false;
  }
  bool select(uint32_t id) {
    m_list.cancel();for(unsigned i=0;i<m_count;i++) if(m_items[i].id==id && m_items[i].enabled) {
      m_selected=i;m_list.select(i);return true;
    }
    return false;
  }
  bool move(int direction) {
    m_list.cancel();if(!direction || !m_count) return false;
    int start=m_selected<m_count?static_cast<int>(m_selected):direction>0?-1:0;
    for(unsigned step=1;step<=m_count;step++) {
      unsigned next=(start+(direction>0?static_cast<int>(step):-static_cast<int>(step))+2*static_cast<int>(m_count))%m_count;
      if(m_items[next].enabled) {bool changed=m_selected!=next;m_selected=next;m_list.select(next);return changed;}
    }
    m_selected=Capacity;return false;
  }
  uint32_t confirm() {m_list.cancel();return focused();}
  void cancel() {m_list.cancel();}
  uint32_t touch(const InputSnapshot &input) {
    unsigned action=m_list.touch(input),selected=m_list.selected();
    if(selected<m_count && m_items[selected].enabled) m_selected=selected;
    return action && m_items[action-1].enabled?m_items[action-1].id:0;
  }
  uint32_t input(const InputSnapshot &input) {
    if(input.event==3) return touch(input);
    if(input.event!=1) return 0;
    cancel();
    if(input.key==InputKey::Up || input.key==InputKey::Down) move(input.key==InputKey::Up?-1:1);
    else if(input.key==InputKey::Confirm) return confirm();
    return 0;
  }
  unsigned count() const {return m_count;}
  uint32_t id(unsigned index) const {return index<m_count?m_items[index].id:0;}
  const char *title(unsigned index) const {return index<m_count?m_items[index].title:"";}
  bool enabled(unsigned index) const {return index<m_count && m_items[index].enabled;}
  uint32_t focused() const {return enabled(m_selected)?m_items[m_selected].id:0;}
  uint32_t pressed() const {unsigned i=m_list.pressed();return i && enabled(i-1)?m_items[i-1].id:0;}
  const ListModel &list() const {return m_list;}
private:
  struct Item {uint32_t id;bool enabled;char title[96];};
  Item m_items[Capacity]{};unsigned m_count=0,m_selected=Capacity;ListModel m_list;
};
}}
#endif

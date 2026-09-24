// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_GESTURES_H
#define LEFONY_GESTURES_H
#include "input_wire.h"
#include "ui_model.h"
#include "math.h"
namespace Lefony { namespace UI {
enum class GestureKind { None, Begin, Pan, Pinch, Tap, LongPress, End, Cancel };
struct Gesture { GestureKind kind=GestureKind::None;double dx=0,dy=0,scale=1,x=0,y=0; };
// Viewport gestures; controls should continue to use Focus for button capture.
// Starts inside bounds, retains capture until release/cancel, and reports
// incremental deltas. Modal/key/focus loss must call cancel(). A changed ID set
// cancels except adding/removing a second finger that retains an existing ID.
class Gestures {
public:
  constexpr explicit Gestures(Box bounds) : m_bounds(bounds),m_count(0),m_ids{},m_x(0),m_y(0),m_startX(0),m_startY(0),
    m_distance(0),m_started(0),m_moved(false),m_longPress(false) {}
  void cancel() { m_count=0;m_moved=false;m_longPress=false; }
  Gesture update(const InputSnapshot &input) {
    if(input.event==4 || input.event==0 || input.event==1) { bool active=m_count;cancel();return {active?GestureKind::Cancel:GestureKind::None}; }
    if(input.event==2) {
      if(m_count==1 && !m_moved && !m_longPress && uint32_t(input.millis-m_started)>=500) {
        m_longPress=true;return {GestureKind::LongPress,0,0,1,m_x,m_y};
      }
      return {};
    }
    if(input.event!=3) return {};
    auto abort=[&]() { bool active=m_count;cancel();return Gesture{active?GestureKind::Cancel:GestureKind::None}; };
    if(input.touchPhase==3) return abort();
    if(input.touchPhase==2) {
      if(!m_count) return {};
      if(input.contactCount) return abort();
      if(m_count==1) {
        const auto &point=input.contacts[0];
        if(point.id!=m_ids[0] || point.x<0 || point.x>319 || point.y<0 || point.y>239) return abort();
        if(Math::hypot(point.x-m_startX,point.y-m_startY)>=5) m_moved=true;
        m_x=point.x;m_y=point.y;
      }
      Gesture result{m_count==1 && !m_moved && !m_longPress && uint32_t(input.millis-m_started)<500?GestureKind::Tap:GestureKind::End,
                     0,0,1,m_x,m_y};cancel();return result;
    }
    if(input.touchPhase>1 || !input.contactCount || input.contactCount>2) return abort();
    for(unsigned i=0;i<input.contactCount;i++)
      if(input.contacts[i].id>15 || input.contacts[i].x<0 || input.contacts[i].x>319 || input.contacts[i].y<0 || input.contacts[i].y>239) return abort();
    if(input.contactCount==2 && input.contacts[0].id==input.contacts[1].id) return abort();
    double x=input.contacts[0].x,y=input.contacts[0].y,distance=0;
    if(input.contactCount==2) {
      x=(x+input.contacts[1].x)/2;y=(y+input.contacts[1].y)/2;
      distance=Math::hypot(input.contacts[0].x-input.contacts[1].x,input.contacts[0].y-input.contacts[1].y);
    }
    if(input.touchPhase==0) {
      cancel();
      for(unsigned i=0;i<input.contactCount;i++) if(!m_bounds.contains(input.contacts[i].x,input.contacts[i].y)) return {};
      baseline(input,x,y,distance);m_startX=x;m_startY=y;m_started=input.millis;m_moved=m_count==2;
      return {GestureKind::Begin,0,0,1,x,y};
    }
    if(!m_count) return {};
    bool same=input.contactCount==m_count;
    if(same) for(unsigned i=0;i<m_count;i++) {
      bool found=false;for(unsigned j=0;j<m_count;j++) if(m_ids[i]==input.contacts[j].id) found=true;
      same=same && found;
    }
    if(!same) {
      bool retained=false;for(unsigned i=0;i<m_count;i++) for(unsigned j=0;j<input.contactCount;j++)
        if(m_ids[i]==input.contacts[j].id) retained=true;
      if(input.contactCount==m_count || !retained) return abort();
      baseline(input,x,y,distance);m_moved=true;return {GestureKind::Begin,0,0,1,x,y};
    }
    if(input.flags&ContactsChanged) return abort();
    if(!m_moved && Math::hypot(x-m_startX,y-m_startY)<5) return {};
    m_moved=true;
    Gesture result{m_count==2?GestureKind::Pinch:GestureKind::Pan,x-m_x,y-m_y,1,x,y};
    if(m_count==2 && m_distance>=8 && distance>=8) result.scale=m_distance/distance;
    baseline(input,x,y,distance);return result;
  }
private:
  void baseline(const InputSnapshot &input,double x,double y,double distance) {
    m_count=input.contactCount;for(unsigned i=0;i<m_count;i++) m_ids[i]=input.contacts[i].id;
    m_x=x;m_y=y;m_distance=distance;
  }
  Box m_bounds;unsigned m_count;uint32_t m_ids[2];double m_x,m_y,m_startX,m_startY,m_distance;
  uint32_t m_started;bool m_moved,m_longPress;
};
}}
#endif

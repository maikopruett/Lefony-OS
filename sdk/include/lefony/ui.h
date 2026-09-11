// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_UI_H
#define LEFONY_UI_H
#include "app.h"
namespace Lefony {
inline uint32_t length(const char *s,uint32_t limit=128) { uint32_t n=0; while(n<limit && s[n]) n++; return n; }
inline void label(int x,int y,const char *value,uint32_t color=Black,uint32_t background=White) {
  text({x,y,color,background,value,length(value)});
}
inline void number(char *out,uint32_t value) {
  char reverse[10]; unsigned n=0;
  do { reverse[n++]=static_cast<char>('0'+value%10); value/=10; } while(value);
  for(unsigned i=0;i<n;i++) out[i]=reverse[n-i-1];
  out[n]=0;
}
class Button {
public:
  constexpr Button(Rect bounds,const char *title) : m_bounds(bounds),m_title(title),m_down(false) {}
  void draw() const { fill(m_bounds); label(m_bounds.x+8,m_bounds.y+8,m_title,White,m_bounds.color); }
  bool handle(Input input) {
    if(input.event!=Event::Touch) return false;
    bool inside=input.x()>=m_bounds.x && input.y()>=m_bounds.y &&
      input.x()<m_bounds.x+m_bounds.width && input.y()<m_bounds.y+m_bounds.height;
    if(input.phase()==TouchPhase::Down) m_down=inside;
    if(input.phase()==TouchPhase::Cancel || (input.second>>8)>1) m_down=false;
    if(input.phase()==TouchPhase::Up) { bool clicked=m_down && inside; m_down=false; return clicked; }
    return false;
  }
private:
  Rect m_bounds; const char *m_title; bool m_down;
};
template<unsigned Capacity=16> class NumberField {
public:
  constexpr NumberField() : m_text{},m_size(0) {}
  bool handle(Input input) {
    if(input.event!=Event::Key) return false;
    if(input.first==static_cast<unsigned>(Key::Delete) && m_size) { m_text[--m_size]=0; return true; }
    if(input.first>=16 && input.first<=25 && m_size+1<Capacity) {
      m_text[m_size++]=static_cast<char>('0'+input.first-16); m_text[m_size]=0; return true;
    }
    return false;
  }
  void draw(int x,int y) const { fill({x,y,200,28,0xef7d}); label(x+5,y+6,m_text,Black,0xef7d); }
  const char *value() const { return m_text; }
private:
  char m_text[Capacity]; unsigned m_size;
};
inline void plotQuadratic(int centerX,int centerY,unsigned scale) {
  for(int x=0;x<320;x++) {
    int dx=x-centerX;
    int y=centerY-(dx*dx)/static_cast<int>(scale?scale:1);
    if(y>=0 && y<240) fill({x,y,1,1,Green});
  }
}
}
#endif

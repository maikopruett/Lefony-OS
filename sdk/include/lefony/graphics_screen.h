// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_GRAPHICS_SCREEN_H
#define LEFONY_GRAPHICS_SCREEN_H
#include "extensions.h"
#include "graphics.h"
namespace Lefony { namespace Graphics {
// Explicit flush: destruction performs no drawing. Consecutive collinear spans
// are coalesced; every syscall remains within the rectangle/pixel quota. Older
// firmware's -3 result permanently selects original fills for this instance.
class Screen {
public:
  constexpr Screen() : m_rects{},m_count(0),m_area(0),m_error(0),m_legacy(false),m_calls(0),m_pixels(0) {}
  bool span(int x,int y,int width,uint16_t color) {
    if(m_error) return false;
    if(x<0 || x>=320 || y<0 || y>=240 || width<1 || width>320-x) { m_error=-1;return false; }
    if(m_area+static_cast<unsigned>(width)>76800 && !flush()) return false;
    if(m_count) {
      Rect &last=m_rects[m_count-1];
      if(last.color==color) {
        if(last.y==y && last.height==1 && (last.x+last.width==x || x+width==last.x)) {
          last.x=x<last.x?x:last.x;last.width+=width;m_area+=width;m_pixels+=width;return true;
        }
        if(last.x==x && last.width==width && (last.y+last.height==y || y+1==last.y)) {
          last.y=y<last.y?y:last.y;last.height++;m_area+=width;m_pixels+=width;return true;
        }
      }
    }
    if(m_count==64 && !flush()) return false;
    m_rects[m_count++]={x,y,width,1,color};m_area+=width;m_pixels+=width;return true;
  }
  bool flush() {
    if(m_error) return false;
    if(!m_count) return true;
    int32_t result=-3;
    if(!m_legacy) { result=Lefony::batch(m_rects,m_count);m_calls++; }
    if(result==-3) {
      m_legacy=true;
      for(unsigned i=0;i<m_count;i++) { result=Lefony::fill(m_rects[i]);m_calls++;if(result<0) break; }
    }
    m_count=0;m_area=0;
    if(result<0) { m_error=result;return false; }return true;
  }
  int32_t error() const { return m_error; }
  uint32_t calls() const { return m_calls; }
  uint64_t pixels() const { return m_pixels; }
private:
  Rect m_rects[64];uint32_t m_count,m_area;int32_t m_error;bool m_legacy;uint32_t m_calls;uint64_t m_pixels;
};
}}
#endif

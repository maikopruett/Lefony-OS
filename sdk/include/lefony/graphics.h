// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_GRAPHICS_H
#define LEFONY_GRAPHICS_H
#include "ui_model.h"
#include "numeric.h"
namespace Lefony { namespace Graphics {
using UI::Box;
struct Point { double x,y; };
enum class Status { Ok, Invalid, OutputFailed };
// Raster primitives only call sink(x,y,width,color) with in-clip horizontal
// spans. A false result aborts immediately. Clip is restricted to the display.
// No anti-aliasing, allocations, platform objects or privileged drawing here.
inline Box clip(Box box) { return UI::intersect(box,{0,0,320,240}); }
inline bool coordinate(double x) { return Numeric::finite(x) && x>=-1e9 && x<=1e9; }
inline int roundPixel(double value,int low,int high) {
  if(value<=low) return low;
  if(value>=high) return high;
  return static_cast<int>(value+0.5);
}
template<typename Sink> Status line(Box region,Point a,Point b,uint16_t color,Sink sink) {
  if(!coordinate(a.x) || !coordinate(a.y) || !coordinate(b.x) || !coordinate(b.y)) return Status::Invalid;
  region=clip(region);if(!region.width || !region.height) return Status::Ok;
  const int right=region.x+region.width-1,bottom=region.y+region.height-1;
  double dx=b.x-a.x,dy=b.y-a.y,enter=0,leave=1;
  const double p[4]={-dx,dx,-dy,dy},q[4]={a.x-region.x,right-a.x,a.y-region.y,bottom-a.y};
  for(unsigned i=0;i<4;i++) {
    if(p[i]==0) { if(q[i]<0) return Status::Ok;continue; }
    double t=q[i]/p[i];
    if(p[i]<0) { if(t>leave) return Status::Ok;if(t>enter) enter=t; }
    else { if(t<enter) return Status::Ok;if(t<leave) leave=t; }
  }
  int x=roundPixel(a.x+enter*dx,region.x,right),y=roundPixel(a.y+enter*dy,region.y,bottom);
  int endX=roundPixel(a.x+leave*dx,region.x,right),endY=roundPixel(a.y+leave*dy,region.y,bottom);
  int distanceX=endX>x?endX-x:x-endX,stepX=x<endX?1:-1;
  int distanceY=-(endY>y?endY-y:y-endY),stepY=y<endY?1:-1,error=distanceX+distanceY;
  for(unsigned count=0;count<320;count++) {
    if(!sink(x,y,1,color)) return Status::OutputFailed;
    if(x==endX && y==endY) return Status::Ok;
    int twice=2*error;
    if(twice>=distanceY) { error+=distanceY;x+=stepX; }
    if(twice<=distanceX) { error+=distanceX;y+=stepY; }
  }
  return Status::Invalid; // Unreachable for a segment clipped to 320x240.
}
template<typename Sink> Status circle(Box region,int x,int y,unsigned radius,uint16_t color,Sink sink,bool filled=false) {
  if(radius>512 || x < -1024 || x>1344 || y < -1024 || y>1264) return Status::Invalid;
  region=clip(region);if(!region.width || !region.height) return Status::Ok;
  auto span=[&](int left,int row,int width) {
    if(row<region.y || row>=region.y+region.height) return true;
    int right=left+width;if(left<region.x) left=region.x;
    if(right>region.x+region.width) right=region.x+region.width;
    return left>=right || sink(left,row,right-left,color);
  };
  int a=static_cast<int>(radius),b=0,error=1-a;
  do {
    if(filled) {
      if(!span(x-a,y+b,2*a+1) || !span(x-a,y-b,2*a+1) || !span(x-b,y+a,2*b+1) || !span(x-b,y-a,2*b+1)) return Status::OutputFailed;
    } else {
      if(!span(x+a,y+b,1) || !span(x-a,y+b,1) || !span(x+a,y-b,1) || !span(x-a,y-b,1) ||
         !span(x+b,y+a,1) || !span(x-b,y+a,1) || !span(x+b,y-a,1) || !span(x-b,y-a,1)) return Status::OutputFailed;
    }
    b++;if(error<0) error+=2*b+1;else { a--;error+=2*(b-a)+1; }
  } while(a>=b);
  return Status::Ok;
}
// RGB565 little-endian bytes, nearest-neighbor 1x only. Transparent color is
// optional. Validate the entire description before emitting any span. Input
// memory remains caller-owned and must stay readable during the operation.
template<typename Sink> Status image(Box region,int x,int y,unsigned width,unsigned height,unsigned stride,
                                     const uint8_t *pixels,unsigned bytes,Sink sink,bool transparent=false,uint16_t key=0) {
  if(!pixels || !width || width>320 || !height || height>240 || stride<width*2 || stride>640 ||
     bytes>153600 || uint64_t(height-1)*stride+width*2>bytes) return Status::Invalid;
  region=clip(UI::intersect(region,{x,y,static_cast<int32_t>(width),static_cast<int32_t>(height)}));
  if(!region.width || !region.height) return Status::Ok;
  for(int row=region.y;row<region.y+region.height;row++) {
    unsigned offset=static_cast<unsigned>(int64_t(row)-y)*stride+static_cast<unsigned>(int64_t(region.x)-x)*2;
    int end=region.x+region.width;
    for(int column=region.x;column<end;) {
      uint16_t color=static_cast<uint16_t>(pixels[offset] | uint16_t(pixels[offset+1])<<8);int start=column;
      do { column++;offset+=2; }
      while(column<end && color==static_cast<uint16_t>(pixels[offset] | uint16_t(pixels[offset+1])<<8));
      if(!(transparent && color==key) && !sink(start,row,column-start,color)) return Status::OutputFailed;
    }
  }
  return Status::Ok;
}
}}
#endif

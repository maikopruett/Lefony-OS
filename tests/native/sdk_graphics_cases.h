// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef SDK_GRAPHICS_CASES_H
#define SDK_GRAPHICS_CASES_H
#include <lefony/graphics.h>
namespace GraphicsTests {
using namespace Lefony::Graphics;
inline bool test() {
  unsigned emitted=0;bool valid=true;
  auto sink=[&](int x,int y,int width,uint16_t) {
    valid=valid && x>=0 && x+width<=320 && y>=0 && y<240 && width>0;
    emitted+=width;return true;
  };
  if(line({0,0,320,240},{-100,10},{400,10},1,sink)!=Status::Ok || emitted!=320 || !valid) return false;
  emitted=0;
  if(line({0,0,320,240},{10,300},{10,-200},1,sink)!=Status::Ok || emitted!=240) return false;
  emitted=0;
  if(line({0,0,320,240},{0,0},{319,239},1,sink)!=Status::Ok || emitted!=320) return false;
  emitted=0;
  if(line({0,0,320,240},{-1,0},{-1,239},1,sink)!=Status::Ok || emitted) return false;
  auto reject=[&](int,int,int,uint16_t) { emitted++;return false; };
  if(line({0,0,320,240},{0,0},{319,239},1,reject)!=Status::OutputFailed || emitted!=1) return false;
  emitted=0;
  if(line({0,0,320,240},{__builtin_nan(""),0},{0,0},1,sink)!=Status::Invalid || emitted) return false;
  if(line({0,0,320,240},{1e20,0},{0,0},1,sink)!=Status::Invalid || emitted) return false;
  bool center=false,east=false,north=false;
  auto circleSink=[&](int x,int y,int width,uint16_t c) {
    if(y==10 && x<=10 && x+width>10) center=true;
    if(y==10 && x<=20 && x+width>20) east=true;
    if(y==0 && x<=10 && x+width>10) north=true;
    return sink(x,y,width,c);
  };
  if(circle({0,0,320,240},10,10,10,1,circleSink)!=Status::Ok || center || !east || !north) return false;
  if(circle({0,0,320,240},10,10,10,1,circleSink,true)!=Status::Ok || !center) return false;
  emitted=0;if(circle({0,0,320,240},INT32_MAX,0,10,1,sink)!=Status::Invalid || emitted) return false;
  if(circle({0,0,320,240},0,0,513,1,sink)!=Status::Invalid || emitted) return false;
  uint8_t pixels[]={1,0,2,0,3,0,4,0};uint16_t last=0;
  auto imageSink=[&](int x,int y,int width,uint16_t c) { last=c;return sink(x,y,width,c); };
  if(image({0,0,320,240},-1,-1,2,2,4,pixels,8,imageSink)!=Status::Ok || emitted!=1 || last!=4) return false;
  emitted=0;
  if(image({0,0,320,240},0,0,2,2,4,pixels,8,imageSink,true,2)!=Status::Ok || emitted!=3) return false;
  emitted=0;
  if(image({0,0,320,240},0,0,2,2,4,pixels,7,imageSink)!=Status::Invalid || emitted) return false;
  if(image({0,0,320,240},0,0,2,2,2,pixels,8,imageSink)!=Status::Invalid || emitted) return false;
  if(image({0,0,320,240},INT32_MAX,INT32_MIN,2,2,4,pixels,8,imageSink)!=Status::Ok || emitted) return false;
  uint32_t random=19333;
  for(unsigned trial=0;trial<2000;trial++) {
    double coordinates[4];for(double &value:coordinates) { random=random*1664525+1013904223;value=static_cast<int>(random%10000)-5000; }
    emitted=0;
    auto clippedSink=[&](int x,int y,int width,uint16_t c) {
      valid=valid && x>=37 && x+width<=137 && y>=25 && y<115;return sink(x,y,width,c);
    };
    if(line({37,25,100,90},{coordinates[0],coordinates[1]},{coordinates[2],coordinates[3]},1,clippedSink)!=Status::Ok || !valid || emitted>100) return false;
  }
  return valid;
}
}
#endif

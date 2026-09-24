// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_text.h"
#include <lefony/ui_model.h>
#include <lefony/ui_inspection.h>
#include <cassert>
#include <cstring>
int main() {
  using PrimeG2::AppText::validText;
  assert(validText(nullptr,0));assert(!validText(nullptr,1));
  assert(validText("e\xcc\x81",3));assert(validText("\xcf\x80",2));assert(!validText("\xcc\x81",2));
  const char *invalid[]={"\xc0\x80","\xed\xa0\x80","\xf4\x90\x80\x80","\xe2\x82","\x80","\xc2\x9f","\n","\t"};
  for(auto text:invalid) assert(!validText(text,strlen(text)));
  char text[257];memset(text,'A',sizeof(text));assert(validText(text,256));assert(!validText(text,257));
  LefonyTextRequest r{};r.size=80;r.schema=1;r.operation=1;
  assert(PrimeG2::AppText::validRequest(r));r.operation=2;r.x=-4096;r.y=4096;r.clipWidth=320;r.clipHeight=240;
  assert(PrimeG2::AppText::validRequest(r));
  for(unsigned at:{0u,1u,2u,3u,8u,9u,10u,11u,13u,14u,15u,16u,17u,18u,19u}) {
    auto bad=r;uint32_t fields[20];memcpy(fields,&bad,80);fields[at]=UINT32_MAX;memcpy(&bad,fields,80);
    assert(!PrimeG2::AppText::validRequest(bad));
  }
  using namespace Lefony::UI;
  TextBuffer<128> buffer;assert(buffer.set(text,100));assert(buffer.size()==100);
  assert(buffer.set(buffer.text()+1,99));assert(buffer.size()==99);
  assert(!buffer.set("\xff",1));assert(buffer.size()==99);assert(buffer.set(nullptr,0));
  char unicode[40];memset(unicode,'a',30);memcpy(unicode+30,"\xf0\x9f\x98\x80",4);
  assert(buffer.set(unicode,34));assert(buffer.size()==34);assert(!buffer.set(text,128));assert(buffer.size()==34);
  ListModel list(3);assert(!list.move(1));list.count(12);
  for(unsigned i=1;i<12;i++) {assert(list.move(1));assert(list.selected()==i);assert(list.first()+list.visible()<=12);}
  assert(list.first()==9 && !list.move(1));list.count(2);assert(list.first()==0 && list.selected()==1);
  list.count(0);assert(list.visible()==0 && list.first()==0 && !list.select(0));
  inspectionBegin();inspectNode(1,Button,{1,2,3,4},{0,0,320,240},Enabled,"Save",{"src/main.cpp",42});inspectionEnd();
#if LEFONY_SDK_DEBUG
  assert(lefony_ui_debug.count==1 && lefony_ui_debug.nodes[0].line==42 && !(lefony_ui_debug.sequence&1));
  assert(lefony_ui_debug.schema==2 && lefony_ui_debug.inputReady==1);
#endif
  inspectionBegin();inspectionEnd(false);
#if LEFONY_SDK_DEBUG
  assert(!(lefony_ui_debug.sequence&1) && lefony_ui_debug.inputReady==0);
#endif
  inspectionBegin();inspectionEnd();
#if LEFONY_SDK_DEBUG
  assert(lefony_ui_debug.inputReady==1);
#endif
}

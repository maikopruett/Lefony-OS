// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_model.h>
#include <cassert>
#include <cstdio>
using namespace Lefony;
using namespace Lefony::UI;
static InputSnapshot touch(unsigned phase,int x,int y,unsigned id=7,unsigned count=UINT32_MAX,unsigned flags=0) {
  InputSnapshot input;input.event=3;input.touchPhase=phase;input.contactCount=count==UINT32_MAX?(phase>=2?0:1):count;
  input.contacts[0]={id,x,y};input.flags=flags;return input;
}
int main() {
  ListModel list;assert(list.layout({10,20,100,116},40,4));list.count(12);
  assert(list.offset()==0 && list.extent()==476 && list.maximumOffset()==360 && list.first()==0 && list.visible()==3);
  assert(!list.touch(touch(0,50,90)) && list.pressed()==2 && list.selected()==1);
  assert(!list.touch(touch(1,52,93)) && !list.dragging());assert(list.touch(touch(2,52,93))==2);
  assert(!list.captured() && !list.pressed());
  list.select(0);list.touch(touch(0,50,110));list.touch(touch(1,50,87));
  assert(list.captured() && list.dragging() && !list.pressed() && list.offset()==23 && list.visible()==4);
  Box row=list.row(0),clip=intersect(row,list.bounds());assert(row.y==-3 && row.height==36 && clip.y==20 && clip.height==13);
  list.count(12);assert(list.captured() && list.offset()==23);assert(list.layout({10,20,100,116},40,4) && list.captured());
  assert(!list.touch(touch(2,50,87)) && list.offset()==23 && !list.captured());
  assert(list.move(1) && list.selected()==3 && list.offset()==40);
  // Gaps do not activate, and a drag never becomes a tap on its release row.
  list.select(0);list.touch(touch(0,50,57));assert(!list.pressed() && !list.touch(touch(2,50,57)));
  list.touch(touch(0,50,100));list.touch(touch(1,50,77));assert(!list.touch(touch(2,50,77)));
  for(unsigned kind=0;kind<6;kind++) {
    list.select(0);list.touch(touch(0,50,100));list.touch(touch(1,50,70));assert(list.offset()==30);
    if(kind==0) list.touch(touch(3,50,70));
    if(kind==1) list.touch(touch(1,50,70,7,2));
    if(kind==2) list.touch(touch(1,50,70,8));
    if(kind==3) list.touch(touch(1,50,70,7,1,ContactsChanged));
    if(kind==4) list.touch(touch(1,110,70));
    if(kind==5) list.cancel();
    assert(!list.captured() && list.offset()==30 && !list.touch(touch(2,50,70)));
    list.touch(touch(0,50,90));assert(list.touch(touch(2,50,90))==3);
  }
  list.select(0);list.touch(touch(0,50,100));list.touch(touch(1,57,101));
  assert(!list.captured() && !list.touch(touch(2,50,100)) && !list.offset());
  // Vertical capture continues beyond the viewport, clamped at either end.
  list.touch(touch(0,50,100));list.touch(touch(1,50,INT32_MIN));assert(list.offset()==360 && list.first()==9);
  assert(!list.touch(touch(2,50,INT32_MIN)) && list.selected()>=9);
  list.touch(touch(0,50,100));list.touch(touch(1,50,INT32_MAX));assert(list.offset()==0);
  assert(!list.touch(touch(2,50,INT32_MAX)));
  list.touch(touch(0,50,100));list.touch(touch(1,50,61));assert(list.offset()==39 && list.first()==1 && list.row(0).height==0);
  list.count(2);assert(!list.captured() && list.offset()==0 && list.visible()==2 && list.selected()<2);
  list.count(0);assert(list.visible()==0 && !list.maximumOffset() && !list.move(1));
  list.touch(touch(0,50,100));assert(!list.touch(touch(2,50,100)));
  list.count(12);assert(list.select(11));assert(list.offset()==360);
  assert(!list.layout({0,0,1,1},0) && list.offset()==360);
  assert(!list.layout({0,0,1,1},40,40) && list.offset()==360);
  assert(!list.layout({INT32_MAX,0,2,1},1) && list.offset()==360);
  assert(!list.layout({0,0,1,-1},1));
  // No allocation or multiplication overflow for very large virtual lists.
  assert(list.layout({0,0,320,240},32767,4));list.count(UINT32_MAX);assert(list.select(UINT32_MAX-1));
  assert(list.offset()<=list.maximumOffset() && list.row(UINT32_MAX-1).y==0);
  list.touch(touch(0,20,20));assert(list.touch(touch(2,20,20))==UINT32_MAX);
  unsigned cases=0;uint32_t random=123;
  assert(list.layout({10,20,100,116},40,4));list.count(12);
  for(unsigned i=0;i<100000;i++) {
    random=random*1664525+1013904223;
    switch(random%6) {
      case 0:list.count((random>>8)%128);break;
      case 1:list.select((random>>8)%128);break;
      case 2:list.move(random&256?1:-1);break;
      case 3:list.cancel();break;
      default:list.touch(touch((random>>8)%4,int((random>>12)%160),int((random>>20)%240),(random>>9)%2));break;
    }
    assert(list.offset()<=list.maximumOffset() && uint64_t(list.first())+list.visible()<=128);
    if(!list.extent()) assert(!list.visible() && !list.offset());
    for(unsigned j=0;j<list.visible();j++) {
      auto box=intersect(list.row(list.first()+j),list.bounds());assert(box.width==100 && box.height>0 && box.height<=36);
    }
    cases++;
  }
  printf("{\"adversarial_steps\":%u,\"model_bytes\":%zu}\n",cases,sizeof(list));
}

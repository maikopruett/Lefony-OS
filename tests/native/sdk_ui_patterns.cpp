// SPDX-License-Identifier: GPL-3.0-or-later
#include <lefony/ui_patterns.h>
#include <cassert>
#include <cstdio>
#include <cstring>
using namespace Lefony;
using namespace Lefony::UI;
InputSnapshot touch(unsigned phase,unsigned contacts,int x,int y,unsigned id=1,unsigned flags=0) {
  InputSnapshot input{};input.event=3;input.touchPhase=phase;input.contactCount=contacts;
  input.contacts[0]={id,x,y};input.flags=flags;return input;
}
int main() {
  DialogLayout dialog;Focus<4> focus;focus.add(99,{0,0,320,240});
  assert(dialog.valid() && dialog.primary.x==26 && dialog.primary.y==140 && dialog.primary.width==128);
  assert(dialog.secondary.x==166 && dialog.title.y==82);
  assert(dialog.open(focus,20,21) && focus.focused()==21);
  focus.touch(0,1,2,2);assert(!focus.touch(2,0,2,2));
  assert(focus.move(-1) && focus.confirm()==20);
  assert(!dialog.open(focus,20,20) && focus.focused()==20);
  assert(dialog.open(focus,20,21,false) && focus.focused()==21);
  focus.touch(0,1,30,150);assert(!focus.touch(2,0,30,150) && focus.focused()==21);
  assert(!focus.select(20));
  Focus<1> small;small.add(5,{1,1,5,5});assert(!dialog.open(small,20,21) && small.focused()==5);
  assert(!DialogLayout({INT32_MAX,0,100,120}).valid());
  assert(!DialogLayout({0,INT32_MAX,100,120}).valid());
  assert(!DialogLayout({0,0,63,120}).valid());
  assert(DialogLayout({INT32_MIN,INT32_MIN,INT32_MAX,INT32_MAX}).valid());
  MenuModel<6> menu;assert(menu.layout({10,30,240,90}));assert(!menu.confirm() && !menu.move(1));
  char title[]="First";assert(menu.add(10,title));title[0]='X';assert(!strcmp(menu.title(0),"First"));
  assert(menu.add(20,"Disabled",false));assert(menu.add(30,"Third"));assert(menu.add(40,"Fourth"));
  assert(menu.add(50,"Fifth"));assert(menu.add(60,"Sixth"));assert(!menu.add(70,"Full"));
  assert(menu.focused()==10 && menu.move(1) && menu.focused()==30);
  assert(menu.move(-1) && menu.focused()==10);assert(menu.move(-1) && menu.focused()==60 && menu.list().offset()==90);
  assert(!menu.select(20) && menu.focused()==60);assert(menu.select(10) && menu.list().offset()==0);
  assert(!menu.touch(touch(0,1,20,40)) && menu.pressed()==10);
  assert(menu.touch(touch(2,0,20,40))==10);
  menu.touch(touch(0,1,20,70));assert(!menu.pressed());assert(!menu.touch(touch(2,0,20,70)) && menu.focused()==10);
  menu.touch(touch(0,1,20,40));menu.touch(touch(1,2,20,40));assert(!menu.touch(touch(2,0,20,40)));
  menu.touch(touch(0,1,20,40));assert(!menu.touch(touch(2,0,20,40,2)));
  menu.touch(touch(0,1,20,40));assert(!menu.touch(touch(2,0,20,40,1,ContactsChanged)));
  menu.touch(touch(0,1,20,100));menu.touch(touch(1,1,20,40));assert(menu.list().offset()==60);
  assert(!menu.touch(touch(2,0,20,40)) && !menu.pressed());
  assert(menu.select(10));menu.touch(touch(0,1,20,40));menu.enable(10,false);assert(!menu.touch(touch(2,0,20,40)) && menu.focused()==30);
  for(unsigned id=30;id<=60;id+=10) assert(menu.enable(id,false));
  assert(!menu.focused() && !menu.confirm() && !menu.move(1));assert(menu.enable(20,true) && menu.focused()==20);
  menu.clear();assert(!menu.count() && !menu.focused() && !menu.list().maximumOffset());
  assert(!menu.add(0,"Zero") && !menu.add(1,"") && !menu.add(1,nullptr));
  assert(!menu.add(1,"\xc3"));char longText[97];memset(longText,'a',96);longText[96]=0;
  assert(!menu.add(1,longText));assert(menu.add(1,"Cafe\xcc\x81"));assert(!menu.add(1,"Duplicate"));
  InputSnapshot key{};key.event=1;key.key=InputKey::Confirm;
  assert(menu.input(key)==1);
  // Independent widened oracle exercises products beyond 64-bit capacity.
  uint64_t random=0x927583412a7ef10ULL;unsigned vectors=20000;
  auto next=[&]() {random^=random<<13;random^=random>>7;random^=random<<17;return random;};
  for(unsigned i=0;i<vectors;i++) {
    uint32_t span=next();uint64_t value=next(),maximum=next();
    uint32_t expected=!maximum?0:value>=maximum?span:static_cast<uint32_t>(static_cast<__uint128_t>(span)*value/maximum);
    assert(Detail::scale(span,value,maximum)==expected);
  }
  assert(Detail::scale(UINT32_MAX,UINT64_MAX-1,UINT64_MAX)==UINT32_MAX-1);
  std::printf("{\"menu_bytes\":%zu,\"scale_vectors\":%u}\n",sizeof(MenuModel<8>),vectors);
}

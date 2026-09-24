// SPDX-License-Identifier: GPL-3.0-or-later
#include <lefony/ui_text_field.h>
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
  TextBuffer<1024> text;TextFieldModel model;const Box box{12,65,296,32};
  assert(text.set("Cafe\xcc\x81 \xcf\x80",9));
  assert(!text.select(5,0) && !text.select(8,0) && !text.select(10,0));
  assert(text.caret()==9 && text.anchor()==9);
  auto view=model.view(text,box,box,7);assert(view.cells==6 && view.caret==6 && view.visible==40);
  assert(model.touch(text,touch(0,1,39,80))); // Before the whole e + accent cell.
  assert(text.caret()==3 && text.anchor()==3);
  model.view(text,box,box,7);model.touch(text,touch(1,1,46,80));
  assert(text.caret()==6 && text.selectionStart()==3 && text.selectionEnd()==6);
  model.touch(text,touch(2,0,46,80));assert(!model.captured());
  assert(text.insert("E",1) && !strcmp(text.text(),"CafE \xcf\x80"));
  assert(text.set("0123456789",10));assert(text.select(7,3));
  auto prepare=[&]() {model.view(text,box,box,7);model.touch(text,touch(0,1,25,80));assert(model.captured());};
  auto unchanged=[&]() {assert(!model.captured() && text.caret()==7 && text.anchor()==3 && !strcmp(text.text(),"0123456789"));};
  prepare();model.touch(text,touch(1,1,40,100));unchanged(); // Outside vertical bounds.
  model.touch(text,touch(2,0,40,80));unchanged(); // Cannot revive cancelled capture.
  prepare();model.touch(text,touch(1,2,40,80));unchanged();
  prepare();model.touch(text,touch(1,1,40,80,2));unchanged();
  prepare();model.touch(text,touch(2,1,40,80));unchanged();
  prepare();model.touch(text,touch(1,1,40,80,1,ContactsChanged));unchanged();
  prepare();model.touch(text,touch(3,0,40,80));unchanged();
  prepare();model.cancel(text);unchanged();
  model.view(text,box,box,7,false);assert(!model.contains(25,80));
  assert(!model.touch(text,touch(0,1,25,80)) && text.caret()==7);
  const Box clipped{100,65,50,32};model.view(text,box,clipped,7);
  assert(!model.contains(25,80) && model.contains(120,80));
  assert(!model.touch(text,touch(0,1,25,80)) && !model.captured());
  char maximum[1024];memset(maximum,'a',1023);maximum[1023]=0;assert(text.set(maximum,1023));
  view=model.view(text,box,box,7);assert(view.scroll==983 && view.caret==1023);
  model.touch(text,touch(0,1,53,80));assert(text.caret()==988);
  view=model.view(text,box,box,7);assert(view.scroll==983); // Tapping never jumps the viewport.
  model.touch(text,touch(1,1,13,80));assert(text.caret()==982 && text.anchor()==988);
  view=model.view(text,box,box,7);assert(view.scroll==982);
  model.touch(text,touch(1,1,13,80));assert(text.caret()==981);
  model.cancel(text);assert(text.caret()==1023 && text.anchor()==1023);
  assert(model.view(text,box,box,7).scroll==983);
  text.select(0,0);view=model.view(text,box,box,7);assert(view.scroll==0);
  model.touch(text,touch(0,1,291,80));assert(text.caret()==39);
  model.touch(text,touch(1,1,306,80));assert(text.caret()==41 && text.anchor()==39);
  model.view(text,box,box,7);model.touch(text,touch(2,0,306,80));assert(text.caret()==41);
  assert(text.insert("9",1));assert(text.size()==1022 && text.text()[39]=='9');
  // Extreme signed coordinates and unsigned font metrics are harmless.
  model.view(text,{INT32_MIN,INT32_MIN,INT32_MAX,INT32_MAX},{INT32_MIN,INT32_MIN,INT32_MAX,INT32_MAX},7);
  model.touch(text,touch(0,1,INT32_MIN,INT32_MIN));model.touch(text,touch(1,1,-2,-2));model.cancel(text);
  model.view(text,box,box,0);assert(!model.contains(25,80));
  model.view(text,box,box,UINT32_MAX);assert(!model.contains(25,80));
  text.clear();model.view(text,box,box,7);model.touch(text,touch(0,1,300,80));model.touch(text,touch(2,0,300,80));
  assert(!text.size() && !text.caret() && !text.anchor());
  // Adversarial normal/cancelled contact streams never edit bytes or split UTF-8.
  const char *unicode="a\xc3\xa9" "e\xcc\x81" "\xcf\x80" "\xf0\x9f\x98\x80";
  assert(text.set(unicode,strlen(unicode)));uint32_t random=0x96184523;
  auto next=[&]() {random^=random<<13;random^=random>>17;random^=random<<5;return random;};
  for(unsigned i=0;i<20000;i++) {
    model.view(text,box,box,7);
    auto input=touch(next()%5,next()%3,static_cast<int>(next()%360)-20,static_cast<int>(next()%80)+40,next()%3,next()%8==0?ContactsChanged:0);
    model.touch(text,input);
    assert(!strcmp(text.text(),unicode) && text.caret()<=text.size() && text.anchor()<=text.size());
    for(unsigned offset:{text.caret(),text.anchor()}) assert((static_cast<unsigned char>(text.text()[offset])&0xc0)!=0x80);
  }
  printf("{\"adversarial_steps\":20000,\"model_bytes\":%zu}\n",sizeof(model));
}

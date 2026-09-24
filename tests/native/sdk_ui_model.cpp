// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/ui_model.h>
#include <lefony/expression_input.h>
#include <cassert>
#include <cstring>
using namespace Lefony::UI;
int main() {
  Box large{INT32_MIN,INT32_MIN,INT32_MAX,INT32_MAX};
  assert(large.contains(-2,-2) && !large.contains(0,0));
  Box clipped=intersect({-10,-10,30,30},{0,0,320,240});
  assert(clipped.x==0 && clipped.y==0 && clipped.width==20 && clipped.height==20);
  assert(intersect({INT32_MAX,0,INT32_MAX,5},{0,0,320,240}).width==0);
  Column column({10,10,100,40},6);
  Box first=column.take(20),second=column.take(20),empty=column.take(1);
  assert(first.y==10 && first.height==20 && second.y==36 && second.height==14 && empty.height==0);
  Row row({10,20,40,30},6);first=row.take(20);second=row.take(20);
  assert(first.x==10 && first.width==20 && first.height==30 && second.x==36 && second.width==14);
  Focus<4> focus;
  assert(focus.add(1,{0,0,20,20}));assert(focus.add(2,{25,0,20,20},false));
  assert(focus.add(3,{50,0,20,20}));assert(!focus.add(1,{0,0,1,1}));
  assert(focus.focused()==1);assert(focus.move(1) && focus.focused()==3);
  assert(focus.move(1) && focus.focused()==1);assert(focus.move(-1) && focus.focused()==3);
  assert(!focus.select(2));assert(focus.confirm()==3);
  assert(focus.touch(0,1,1,1)==0 && focus.pressed()==1);
  assert(focus.touch(1,1,22,1)==0);assert(focus.touch(2,0,1,1)==0);
  focus.touch(0,1,1,1);assert(focus.touch(2,0,1,1)==1);
  focus.touch(0,1,1,1);focus.touch(1,2,1,1);assert(focus.touch(2,0,1,1)==0);
  focus.touch(0,1,1,1);focus.cancel();assert(focus.touch(2,0,1,1)==0);
  focus.touch(0,1,1,1);focus.enable(1,false);assert(focus.touch(2,0,1,1)==0 && focus.focused()==3);
  focus.enable(3,false);assert(focus.focused()==0 && focus.confirm()==0);
  focus.enable(2,true);assert(focus.focused()==2);
  // Disabled overlapping controls do not let touches activate a control behind.
  focus.add(4,{25,0,20,20},false);focus.touch(0,1,26,1);assert(focus.touch(2,0,26,1)==0);
  focus.clear();assert(!focus.focused() && !focus.pressed() && !focus.move(1));
  TextBuffer<16> text;
  assert(text.insert("abcdef",6));
  text.move(-1);text.move(-1);text.move(-1,true);text.move(-1,true);
  assert(text.selectionStart()==2 && text.selectionEnd()==4);
  assert(text.insert("X",1) && !strcmp(text.text(),"abXef"));
  assert(text.erase() && !strcmp(text.text(),"abef"));
  assert(text.insert(text.text(),2) && !strcmp(text.text(),"ababef"));
  text.selectAll();assert(text.insert("\xc3\xa9\xe2\x88\x9a",5));
  assert(text.size()==5 && text.caret()==5);
  assert(text.move(-1) && text.caret()==2);assert(text.move(-1,true) && text.selectionEnd()==2);
  assert(text.erase() && text.size()==3 && !strcmp(text.text(),"\xe2\x88\x9a"));
  text.move(1);assert(text.erase() && text.size()==0 && !text.erase());
  assert(text.insert("012345678901234",15));assert(!text.insert("X",1));
  assert(!strcmp(text.text(),"012345678901234") && text.caret()==15);
  text.selectAll();assert(!text.insert("\xc3",1) && text.selectionEnd()==15);
  assert(text.insert(nullptr,0) && text.size()==0 && !text.text()[0]);
  Lefony::InputSnapshot input;input.event=1;
  struct Composition { Lefony::InputKey key;const char *text; };
  const Composition compositions[]={
    {Lefony::InputKey::Sin,"sin("},{Lefony::InputKey::Cos,"cos("},{Lefony::InputKey::Tan,"tan("},
    {Lefony::InputKey::Asin,"asin("},{Lefony::InputKey::Acos,"acos("},{Lefony::InputKey::Atan,"atan("},
    {Lefony::InputKey::Ln,"ln("},{Lefony::InputKey::Log,"log10("},{Lefony::InputKey::Exp,"exp("},
    {Lefony::InputKey::Pi,"pi"},{Lefony::InputKey::Sqrt,"sqrt("},{Lefony::InputKey::Square,"^2"},
    {Lefony::InputKey::Multiply,"*"},{Lefony::InputKey::Divide,"/"},{Lefony::InputKey::Exponent,"e"}};
  for(const auto &composition:compositions) {
    text.clear();input.key=composition.key;
    assert(Lefony::Expression::edit(text,input) && !strcmp(text.text(),composition.text));
  }
  input.modifiers=Lefony::InputAlpha;input.textBytes=1;input.text[0]='q';text.clear();
  assert(Lefony::Expression::edit(text,input) && !strcmp(text.text(),"q"));
  input.key=Lefony::InputKey::Left;input.modifiers=Lefony::InputShift;
  assert(Lefony::Expression::edit(text,input) && text.selectionEnd()==1);
  input.key=Lefony::InputKey::Delete;
  assert(Lefony::Expression::edit(text,input) && text.size()==0);
  input.event=2;assert(!Lefony::Expression::edit(text,input));
  uint32_t random=123;
  for(unsigned i=0;i<100000;i++) {
    random=random*1664525+1013904223;
    switch(random%7) {
      case 0:text.insert("a",1);break;
      case 1:text.insert("\xc3\xa9",2);break;
      case 2:text.move(-1,random&256);break;
      case 3:text.move(1,random&512);break;
      case 4:text.erase();break;
      case 5:text.selectAll();break;
      case 6:text.insert(nullptr,0);break;
    }
    assert(text.size()<16 && strlen(text.text())==text.size() && text.caret()<=text.size());
    assert(Lefony::validInputText(text.text(),text.size()));
  }
}

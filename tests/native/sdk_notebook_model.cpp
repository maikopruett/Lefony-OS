// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include <lefony/expression_input.h>
#include "document.h"
#include <cassert>
#include <cstring>
using namespace Lefony::UI;
int main() {
  TextBuffer<96> text;assert(text.set("abcdef",6));text.move(-1);text.move(-1,true);
  assert(text.insertText("1234567890123456789012345678901234567890",40));
  assert(text.size()==45 && text.caret()==44 && text.text()[44]=='f');
  auto before=text;
  assert(!text.insertText("abcdefghijk\xff",12) && !strcmp(text.text(),before.text()) && text.caret()==before.caret());
  text.selectAll();assert(text.insertText(text.text(),text.size()) && !strcmp(text.text(),before.text()));
  assert(text.set("\xcf\x80",2));text.selectAll();
  const char *symbols="\xcf\x80\xc3\x97" "2\xc3\xb7" "3\xe2\x88\x92" "4";
  assert(Lefony::Expression::insertText(text,symbols,strlen(symbols))==Lefony::Expression::TextStatus::Ok);
  assert(!strcmp(text.text(),"pi*2/3-4"));
  const char *functions="\xe2\x88\x9a(2)+\xe2\x84\xaf^2+1\xe1\xb4\x87-3";
  text.selectAll();assert(Lefony::Expression::insertText(text,functions,strlen(functions))==Lefony::Expression::TextStatus::Ok);
  assert(!strcmp(text.text(),"sqrt(2)+e^2+1e-3"));
  before=text;
  const char *bad[]={"two\nlines","tab\ttext","\xf0\x9f\x98\x80","\xc0\x80","\xcf","a\x11"};
  for(auto value:bad) {assert(Lefony::Expression::insertText(text,value,strlen(value))==Lefony::Expression::TextStatus::Unsupported);assert(!strcmp(text.text(),before.text()));}
  char huge[96];memset(huge,'1',sizeof(huge));assert(!text.insertText(huge,96));assert(!strcmp(text.text(),before.text()));
  SliderModel slider(1,14,9);Box track{12,154,296,28};
  assert(slider.touch(track,0,1,22,165) && slider.value()==1);
  assert(slider.touch(track,1,1,298,165) && slider.value()==14);
  assert(slider.touch(track,3,0,298,165) && slider.value()==9 && !slider.dragging());
  slider.touch(track,0,1,22,165);slider.touch(track,2,0,22,165);assert(slider.value()==1 && !slider.dragging());
  assert(!slider.move(-1));assert(slider.move(1) && slider.value()==2);
  slider.touch(track,0,1,298,165);slider.touch(track,1,2,298,165);assert(slider.value()==2);
  slider.touch(track,0,1,298,165);slider.touch(track,1,1,310,165);assert(slider.value()==2);
  Document doc;assert(doc.decode("LFNOTE1\nsin(30)\n",16));assert(doc.angle==1 && doc.digits==9 && doc.format==0 && doc.migrated);
  assert(doc.decode("LFNOTE2\nD\n1+2\n",14));assert(doc.dark && doc.angle==1 && doc.digits==9 && doc.migrated);
  doc.angle=2;doc.format=2;doc.digits=14;char bytes[Document::MaximumBytes];unsigned size=doc.encode(bytes);
  Document restored;assert(restored.decode(bytes,size));assert(restored.angle==2 && restored.format==2 && restored.digits==14 && !restored.migrated);
  const char *invalid[]={"LFNOTE3\nL\n3 0 09\n","LFNOTE3\nL\n0 3 09\n","LFNOTE3\nL\n0 0 00\n","LFNOTE3\nL\n0 0 15\n","LFNOTE3\nL\n0 0 9\n","LFNOTE4\n"};
  for(auto input:invalid) {assert(!restored.decode(input,strlen(input)));assert(restored.angle==2 && restored.count==1);}
  memset(bytes,'X',sizeof(bytes));assert(!doc.encode(bytes,3) && bytes[0]=='X');
  doc.count=Document::Capacity+1;assert(!doc.encode(bytes));
}

// SPDX-License-Identifier: GPL-3.0-or-later
#include <lefony/ui_paragraph.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>
using namespace Lefony::UI;
static unsigned cases;
static void expect(const char *text,unsigned columns,std::initializer_list<const char *> wanted) {
  ParagraphLayout layout(text,strlen(text),columns);assert(layout.valid());ParagraphLine line;
  for(auto value:wanted) {
    assert(layout.next(line));assert(std::string(text+line.offset,line.bytes)==value);
    assert(line.cells<=columns && line.offset+line.bytes<=strlen(text));
  }
  assert(!layout.next(line));cases++;
}
int main() {
  expect("",4,{});expect("one two three",7,{"one two","three"});
  expect("one two three",6,{"one","two","three"});
  expect("  one  two  ",7,{"one","two"});expect("12345   ",5,{"12345"});
  expect("12345   \n",5,{"12345",""});expect("a\n\nb\r\nc\n",10,{"a","","b","c",""});
  expect("abcde",1,{"a","b","c","d","e"});
  expect("abcde fghijkl",4,{"abcd","e","fghi","jkl"});
  expect("Cafe\xcc\x81 \xcf\x80",4,{"Cafe\xcc\x81","\xcf\x80"});
  expect("e\xcc\x81\xcc\x82x",1,{"e\xcc\x81\xcc\x82","x"});
  expect(" \xcc\x81x",1,{" \xcc\x81","x"});
  for(auto invalid:{"\r","\rX","\t","\x7f","\xc0\x80","\xed\xa0\x80","\xf4\x90\x80\x80","\xe2\x82","\x80","\xc2\x9f","\xcc\x81","x\n\xcc\x81"}) {
    ParagraphLayout layout(invalid,strlen(invalid),40);ParagraphLine line{1,2,3};
    assert(!layout.valid() && !layout.next(line) && line.offset==1 && line.bytes==2 && line.cells==3);cases++;
  }
  ParagraphLine line;assert(!ParagraphLayout(nullptr,1,10).valid());
  assert(ParagraphLayout(nullptr,0,10).valid());assert(!ParagraphLayout("a",1,0).valid());
  std::string limit(1024,'a');ParagraphLayout allowed(limit.data(),limit.size(),1);
  for(unsigned i=0;i<1024;i++) {assert(allowed.next(line));assert(line.offset==i && line.bytes==1 && line.cells==1);}
  assert(!allowed.next(line));limit+='a';assert(!ParagraphLayout(limit.data(),limit.size(),80).valid());
  const char embedded[]={'a',0,'b'};assert(!ParagraphLayout(embedded,sizeof(embedded),80).valid());
  // Independent greedy ASCII word oracle, including long words and exact fits.
  unsigned seed=17,vectors=0;
  for(unsigned trial=0;trial<5000;trial++) {
    auto random=[&]() {seed=seed*1664525u+1013904223u;return seed;};
    unsigned columns=1+random()%43;std::string text;std::vector<std::string> words;
    for(unsigned n=1+random()%12;n;n--) {
      std::string word(1+random()%55,char('a'+random()%26));words.push_back(word);
      if(!text.empty()) text+=' ';text+=word;
    }
    std::vector<std::string> expected;std::string pending;
    for(auto word:words) {
      if(!pending.empty() && pending.size()+1+word.size()<=columns) {pending+=' ';pending+=word;continue;}
      if(!pending.empty()) {expected.push_back(pending);pending.clear();}
      while(word.size()>columns) {expected.push_back(word.substr(0,columns));word.erase(0,columns);}
      pending=word;
    }
    if(!pending.empty()) expected.push_back(pending);
    ParagraphLayout layout(text.data(),text.size(),columns);assert(layout.valid());
    for(const auto &value:expected) {assert(layout.next(line));assert(text.substr(line.offset,line.bytes)==value);}
    assert(!layout.next(line));vectors++;
  }
  printf("{\"cases\":%u,\"word_vectors\":%u}\n",cases,vectors);
}

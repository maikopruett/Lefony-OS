// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_input_stream.h"
#include <cassert>
#include <cstring>
#include <random>
using PrimeG2::AppInputStream;
static uint64_t mask(const uint32_t value[2]) { return value[0]|(uint64_t(value[1])<<32); }
static LefonyInputStream read(AppInputStream &stream,uint32_t now) {
  LefonyInputStream out;memset(&out,255,sizeof(out));stream.read(out,now);
  assert(out.size==480 && out.version==1 && !out.reserved && out.millis==now);
  for(auto reserved:out.reservedOutput) assert(!reserved);
  for(unsigned i=out.count;i<LEFONY_INPUT_STREAM_EVENTS;i++) {
    LefonyStreamEvent zero={};assert(!memcmp(&out.events[i],&zero,sizeof(zero)));
  }
  return out;
}
int main() {
  AppInputStream input;
  constexpr uint64_t left=UINT64_C(1)<<15,right=UINT64_C(1)<<57,shift=UINT64_C(1)<<30;
  input.observe(left,0,0);input.observe(left,10,0);input.focus(true);
  auto s=read(input,10);assert(s.flags==LEFONY_INPUT_FOCUS_RESET && !s.count && !mask(s.held));
  uint32_t generation=s.generation;
  input.observe(left,100,0);assert(!read(input,100).count); // Held launcher key stays suppressed.
  input.observe(0,101,0);input.observe(0,111,0);
  input.observe(left|right,112,0);input.observe(left|right,121,0);assert(!read(input,121).count);
  input.observe(left|right,122,0);s=read(input,122);
  assert(s.count==1 && mask(s.held)==(left|right));
  assert(mask(s.events[0].data.keys.down)==(left|right) && !mask(s.events[0].data.keys.up));
  assert(s.events[0].sequence==1 && s.events[0].millis==122);
  input.observe(left|right,500,0);assert(!read(input,500).count); // No synthetic repeat edges.
  input.observe(left,501,0);input.observe(left|right,506,0);input.observe(left|right,516,0);
  assert(!read(input,516).count); // Short release bounce is not a new press.
  input.observe(shift,520,1);input.observe(shift,530,1);s=read(input,530);
  assert(s.count==1 && mask(s.events[0].data.keys.up)==(left|right));
  assert(mask(s.events[0].data.keys.down)==shift && s.modifiers==1);
  // Back becomes visible only after release/repress when navigation opts in.
  input.observe(AppInputStream::Back,540,0);input.observe(AppInputStream::Back,550,0);
  s=read(input,550);assert(mask(s.held)==0 && s.count==1);
  input.backAllowed(true,550);assert(!read(input,550).count);
  input.observe(0,560,0);input.observe(0,570,0);
  input.observe(AppInputStream::Back,580,0);input.observe(AppInputStream::Back,590,0);
  s=read(input,590);assert(mask(s.held)==AppInputStream::Back && s.count==1);
  input.backAllowed(false,600);s=read(input,600);
  assert(!mask(s.held) && mask(s.events[0].data.keys.up)==AppInputStream::Back);
  // Touch is ordered with keys and stays current across subsequent key events.
  LefonyContactTransition touch={0,2,{{2,90,110},{7,200,120}}};input.touch(touch,1,610);
  input.observe(left,620,0);input.observe(left,630,0);s=read(input,630);
  assert(s.count==2 && s.events[0].kind==LEFONY_INPUT_CONTACTS && s.events[1].kind==LEFONY_INPUT_KEYS);
  assert(s.contactCount==2 && s.contacts[1].id==7);
  touch.phase=2;touch.count=0;input.touch(touch,0,640);s=read(input,640);
  assert(s.contactCount==0 && s.contacts[0].id==0 && s.events[0].data.touch.contacts[0].id==2);
  // Partial reads preserve order. Overflow discards the unusable backlog once.
  for(unsigned i=0;i<20;i++) { touch.phase=i%4;input.touch(touch,0,650+i); }
  s=read(input,700);assert(s.count==8 && s.pending==12);
  uint32_t last=s.events[7].sequence;s=read(input,701);
  assert(s.count==8 && s.pending==4 && s.events[0].sequence==last+1);
  s=read(input,702);assert(s.count==4 && !s.pending);
  for(unsigned i=0;i<45;i++) input.touch(touch,0,710+i);
  s=read(input,800);assert(s.flags==LEFONY_INPUT_OVERFLOW && !s.count && !s.pending && s.dropped==45);
  s=read(input,801);assert(!s.flags && !s.count && !s.dropped);
  input.focus(false);input.touch(touch,0,802);input.observe(shift,802,7);input.observe(shift,812,7);
  input.focus(true);s=read(input,813);
  assert(s.generation!=generation && s.flags==LEFONY_INPUT_FOCUS_RESET && !s.count);
  assert(!mask(s.held) && s.touchPhase==3 && !s.contactCount);
  // Exercise arbitrary chords, both 32-bit words, wrapping clocks and a simple
  // independent state model. Each input remains stable for the required 10 ms.
  AppInputStream random;random.focus(true);read(random,0);uint64_t previous=0;
  uint32_t now=UINT32_MAX-500;std::mt19937_64 rng(451);
  for(unsigned i=0;i<5000;i++) {
    uint64_t down=rng()&~AppInputStream::Back;
    random.observe(down,now,0);random.observe(down,now+10,0);s=read(random,now+10);
    assert(mask(s.held)==down && s.count==(down!=previous));
    if(s.count) {
      assert(mask(s.events[0].data.keys.down)==(down&~previous));
      assert(mask(s.events[0].data.keys.up)==(previous&~down));
    }
    previous=down;now+=20;
  }
}

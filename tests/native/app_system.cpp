// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_system.h"
#include <cassert>
#include <cstring>
using namespace PrimeG2::AppSystem;
int main() {
  Session s;
  assert(!s.permits(false,1,100));
  s.input(1,LEFONY_CLIPBOARD_COPY,7,100);
  assert(s.permits(true,7,100) && !s.permits(false,7,100) && !s.permits(true,8,100));
  assert(!s.live(99) && s.live(2099) && !s.live(2100));
  s.input(2,0,8,200);assert(s.permits(true,7,200)); // timer must not steal input
  s.revoke();assert(!s.live(200));
  s.input(1,LEFONY_CLIPBOARD_PASTE,9,300);assert(s.permits(false,9,300) && !s.permits(true,9,300));
  s.input(3,0,10,301);assert(!s.live(301));
  s.input(1,LEFONY_CLIPBOARD_CUT,11,400);assert(s.permits(true,11,400));
  s.input(1,0,12,401);assert(!s.live(401));
  s.input(1,4,13,402);assert(!s.live(402));
  s.input(1,1,0,402);assert(!s.live(402));
  s.brightness(240,100);s.brightness(100,120);assert(s.restoreBrightness(120)==240);
  assert(s.restoreBrightness(120)==120);
  s.brightness(240,100);assert(s.restoreBrightness(170)==170); // outside OS change wins
  s.brightness(240,100);s.brightness(170,110);assert(s.restoreBrightness(110)==170);
  s.brightness(200,0);assert(s.restoreBrightness(0)==200);
  assert(validClipboard(nullptr,0) && !validClipboard(nullptr,1));
  const char *good[]={"abc", "\tline\n", "\xcc\x81", "\xf0\x9f\x98\x80", "\xf4\x8f\xbf\xbf"};
  for(auto text:good) assert(validClipboard(text,strlen(text)));
  const char *bad[]={"\xc0\x80", "\xed\xa0\x80", "\xf4\x90\x80\x80", "\xe2\x82", "\x80", "\xc2\x80", "\x11", "\x7f", "\r"};
  for(auto text:bad) assert(!validClipboard(text,strlen(text)));
  assert(!validClipboard("a\0b",3));
  char maximum[220];memset(maximum,'x',sizeof(maximum));
  assert(validClipboard(maximum,219) && !validClipboard(maximum,220));
  maximum[218]=char(0xc2);assert(!validClipboard(maximum,219));
  LefonySystemRequest r={48,1,LEFONY_SYSTEM_INFO,0,0,0,0x10201000,160,0,{0,0,0}};
  assert(validRequest(r));
  for(unsigned i=0;i<12;i++) {
    auto badRequest=r;reinterpret_cast<uint32_t *>(&badRequest)[i]=UINT32_MAX;
    if(i!=6) assert(!validRequest(badRequest));
  }
  r={48,1,LEFONY_SYSTEM_CLIPBOARD_WRITE,0,0,1,0,0,0,{0,0,0}};
  assert(validRequest(r));r.capacity=1;assert(!validRequest(r));
  r.buffer=0x10201000;r.capacity=219;assert(validRequest(r));r.capacity=220;assert(!validRequest(r));
  r.operation=LEFONY_SYSTEM_CLIPBOARD_READ;assert(validRequest(r));r.capacity=0;assert(!validRequest(r));
}

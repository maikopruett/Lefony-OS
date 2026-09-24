/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Uses only ordinary app drawing/input plus the VM-only execution experiment. */
#include <lefony/app_c.h>

static unsigned launches;
static void check(int ok) { if(!ok) __asm__ volatile("udf #0"); }
static void mark(unsigned x,unsigned y) {
  check(lefony_fill((lefony_rect_t){x,y,10,10,LEFONY_GREEN})==0);
}
static void bits(uint32_t value,unsigned y) {
  for(unsigned bit=0;bit<32;bit++)
    check(lefony_fill((lefony_rect_t){bit*5,y,5,8,(value&(1u<<bit))?LEFONY_GREEN:LEFONY_WHITE})==0);
}
static void input(uint32_t out[32]) {
  out[0]=128;out[1]=1;out[2]=0;
  check(lefony_service(8,out)==0);
}
static void yield(void) { check(lefony_service(0x7fff0002u,0)==0); }

int main(void) {
  check(lefony_service(0x7fff0001u,0)==0);
  uint32_t started=lefony_millis(),last=started,maximum=0;
  for(unsigned i=0;i<32;i++) {
    yield();
    uint32_t now=lefony_millis(),gap=now-last;
    if(gap>maximum) maximum=gap;
    last=now;
  }
  bits(last-started,0);bits(maximum,12);mark(200,0);
  uint32_t seen=0,deletes=0,rights=0;
  for(;;) {
    uint32_t snapshot[32];input(snapshot);
    if(snapshot[3]!=seen) {
      seen=snapshot[3];
      if(snapshot[5]==LEFONY_KEY) {
        if(snapshot[6]==LEFONY_KEY_CONFIRM) {
          // Autonomous resumes and UI ticks must preserve the last real input,
          // even when a library doesn't read it until several waits later.
          uint32_t since=lefony_millis(),after[32];
          do { yield(); } while(lefony_millis()-since<650);
          input(after);check(after[3]==seen && after[5]==LEFONY_KEY && after[6]==LEFONY_KEY_CONFIRM);
          mark(200,30);
        }
        if(snapshot[6]==LEFONY_KEY_DELETE && ++deletes>=3) mark(220,30);
        if(snapshot[6]==LEFONY_KEY_RIGHT) {
          rights++;bits(rights,54);
        }
      }
      if(snapshot[5]==LEFONY_TOUCH && snapshot[10]==0 && snapshot[11]==1 &&
         snapshot[14]==7 && snapshot[15]==90 && snapshot[16]==110) mark(240,30);
    }
    // Voluntary waits plus involuntary preemptions both use normal OS dispatch.
    yield();
  }
}

void lefony_event(lefony_event_t event,uint32_t first,uint32_t second) {
  (void)first;(void)second;check(event==LEFONY_START && ++launches==1);
  check(main()==0);
}

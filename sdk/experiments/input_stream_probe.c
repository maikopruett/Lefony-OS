/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Ordinary C consumer of negotiated input; no emulator or firmware hooks. */
#include <lefony/input_stream.h>
#include <lefony/foreground.h>
#include <stdint.h>
#include <string.h>
static uint16_t pixels[320*160];
static uint32_t values[15];
static void check(int okay) { if(!okay) __asm__ volatile("udf #0"); }
#ifndef INPUT_STREAM_UNDECLARED
static uint32_t lastSequence;
static int key(const uint32_t mask[2],uint32_t position) { return lefony_input_key_held(mask,position); }
#endif
static void draw(void) {
  for(unsigned i=0;i<320*160;i++) pixels[i]=LEFONY_WHITE;
  for(unsigned row=0;row<15;row++) for(unsigned bit=0;bit<32;bit++)
    for(unsigned y=0;y<6;y++) for(unsigned x=0;x<4;x++)
      pixels[(row*10+y)*320+bit*5+x]=(values[row]&(1u<<bit))?LEFONY_GREEN:LEFONY_BLACK;
  check(lefony_present(pixels,0,0,320,160,320)==0);
}
int main(void) {
  LefonyInputStream s={0};s.size=sizeof(s);s.version=1;
#ifdef INPUT_STREAM_UNDECLARED
  check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,&s)==-3);
  values[0]=0x123456;draw();return 0;
#else
  check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,(void *)0)==-4);
  check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,(void *)0x10000000)==-4);
  check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,(void *)0x102eef00)==-4);
  s.size--;check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,&s)==-4);s.size++;
  s.version=2;check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,&s)==-4);s.version=1;
  s.reserved=1;check(lefony_service(LEFONY_INPUT_STREAM_SERVICE,&s)==-4);s.reserved=0;
  check(lefony_read_input_stream(&s)==0 && s.flags==LEFONY_INPUT_FOCUS_RESET);
  check(!s.count && !s.held[0] && !s.held[1] && !s.contactCount);
  uint32_t navigation[]={16,1,0,1};check(lefony_service(9,navigation)==0);
  values[0]=0x123456;
  for(;;) {
    check(lefony_read_input_stream(&s)==0);
    check(s.size==480 && s.version==1 && !s.reserved && s.count<=8 && s.pending<=32);
    check(!key(s.held,LEFONY_PHYSICAL_HOME) && !key(s.held,LEFONY_PHYSICAL_APPS));
    for(unsigned i=0;i<3;i++) check(!s.reservedOutput[i]);
    if(s.flags&LEFONY_INPUT_OVERFLOW) {
      check(!s.count && !s.pending && s.dropped>32);values[9]|=32;values[10]=s.dropped;
      lastSequence=s.sequence;
    }
    values[1]=s.held[0];values[2]=s.held[1];values[11]=s.generation;
    values[12]=s.touchPhase|(s.contactCount<<8);values[14]=s.modifiers;
    if(key(s.held,LEFONY_PHYSICAL_LEFT) && key(s.held,LEFONY_PHYSICAL_RIGHT)) values[9]|=1;
    if(key(s.held,LEFONY_PHYSICAL_LEFT) && key(s.held,LEFONY_PHYSICAL_SHIFT)) values[9]|=2;
    int pause=0;
    for(unsigned i=0;i<s.count;i++) {
      LefonyStreamEvent *e=&s.events[i];check(e->sequence==lastSequence+1);lastSequence=e->sequence;
      if(e->kind==LEFONY_INPUT_KEYS) {
        check(!e->data.keys.reserved);values[7]++;
        values[3]+=key(e->data.keys.down,LEFONY_PHYSICAL_LEFT);
        values[4]+=key(e->data.keys.up,LEFONY_PHYSICAL_LEFT);
        values[5]+=key(e->data.keys.down,LEFONY_PHYSICAL_RIGHT);
        values[6]+=key(e->data.keys.up,LEFONY_PHYSICAL_RIGHT);
        if(key(e->data.keys.down,LEFONY_PHYSICAL_BACK)) values[9]|=64;
        if(key(e->data.keys.down,LEFONY_PHYSICAL_TWO)) pause=1;
      } else {
        check(e->kind==LEFONY_INPUT_CONTACTS);values[8]++;
        if(e->data.touch.count==2) {
          check(e->data.touch.contacts[0].id==2 && e->data.touch.contacts[1].id==7);values[9]|=4;
        }
        if(e->data.touch.phase==2) { check(!e->data.touch.count);values[9]|=8; }
        if(e->data.touch.phase==3) { check(!e->data.touch.count);values[9]|=16; }
      }
    }
    if(pause) {
      values[13]=1;draw();check(lefony_program_sleep(10000)==0);values[13]=0;
    }
    draw();check(lefony_program_sleep(5)==0);
  }
#endif
}

/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Real ARM public foreground contract, including libc and OS interruption. */
#include <lefony/foreground.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
extern int foreground_registers(unsigned yield);
static unsigned starts;
#define check(ok) do { if(!(ok)) __asm__ volatile("udf %0" :: "i"(__LINE__)); } while(0)
static void nested(unsigned depth) {
  volatile uint32_t canary[24];
  for(unsigned i=0;i<24;i++) canary[i]=0x10203040u+depth*24+i;
  if(depth) nested(depth-1);
  else { check(foreground_registers(0)==1);check(foreground_registers(1)==1); }
  for(unsigned i=0;i<24;i++) check(canary[i]==0x10203040u+depth*24+i);
}
int main(void) {
#ifdef FOREGROUND_UNNEGOTIATED
  *(volatile uint32_t *)0x11001000=123;
#endif
  LefonyProgramRequest info;
  check(lefony_program_info(&info)==-4);
  LefonyProgramRequest bad=lefony_program_request(LEFONY_PROGRAM_ENTER);
  bad.profile=2;check(lefony_service(11,&bad)==-4);
  bad.profile=1;bad.reserved[0]=1;check(lefony_service(11,&bad)==-4);
  bad.reserved[0]=0;bad.size--;check(lefony_service(11,&bad)==-4);
  check(lefony_service(11,(void *)0x10000000)==-4);
  check(lefony_service(11,(void *)0x102ffffc)==-4);
  check(lefony_program_enter()==0);
  check(lefony_program_enter()==-4);
  check(lefony_program_info(&info)==0);
  check(info.profile==1 && info.heap==0x11001000 && info.heapBytes==8*1024*1024-8192 &&
        info.stackBytes==65536 && info.sliceMillis==10);
#ifdef FOREGROUND_LOW_GUARD
  *(volatile uint32_t *)(uintptr_t)(info.heap-4)=123;
#endif
#ifdef FOREGROUND_HIGH_GUARD
  *(volatile uint32_t *)(uintptr_t)(info.heap+info.heapBytes)=123;
#endif
#ifdef FOREGROUND_EXECUTE
  ((void (*)(void))(uintptr_t)info.heap)();
#endif
  check(lefony_fill((lefony_rect_t){0,0,320,240,31})==0);
  check(lefony_program_yield()==0);
#ifdef FOREGROUND_SPIN
  for(;;) __asm__ volatile("" ::: "memory");
#endif
#ifdef FOREGROUND_LONG_SLEEP
  check(lefony_program_sleep(60000)==0);check(0);
#endif
  uint32_t before=lefony_millis();
  check(lefony_program_sleep(500)==0);
  check((uint32_t)(lefony_millis()-before)>=500);
  check(lefony_program_sleep(60001)==-4);
  bad=lefony_program_request(LEFONY_PROGRAM_SLEEP);bad.argument=-1;
  check(lefony_service(11,&bad)==-4);
  unsigned char *zone=calloc(6*1024*1024,1);check(zone && !((uintptr_t)zone&7));
  for(unsigned i=0;i<6*1024*1024;i+=4096) { check(!zone[i]);zone[i]=0xa5; }
  errno=0;check(!realloc(zone,info.heapBytes+1) && errno==ENOMEM && zone[0]==0xa5);
  nested(8);
  uint16_t *pixels=malloc(320*240*2);check(pixels!=0);
  for(unsigned y=0;y<240;y++) for(unsigned x=0;x<320;x++)
    pixels[y*320+x]=(x<160)==(y<120)?LEFONY_GREEN:LEFONY_WHITE;
  uint32_t frames=info.frames;
  check(lefony_present(pixels,0,0,320,240,320)==0);
  memset(pixels,0,320*240*2); // OS owns its copy after presentation.
  check(lefony_program_info(&info)==0 && info.frames>frames);
  check(lefony_present(pixels,0,0,321,240,320)==-4);
  LefonyPixelRequest draw={40,1,0,0,0,320,240,320,info.heap+info.heapBytes-2,320*240*2};
  check(lefony_service(12,&draw)==-4);
  draw.buffer=(uint32_t)(uintptr_t)pixels;draw.stride=319;check(lefony_service(12,&draw)==-4);
  draw.stride=320;draw.bytes--;check(lefony_service(12,&draw)==-4);
  draw.bytes++;draw.flags=1;check(lefony_service(12,&draw)==-4);
  free(pixels);free(zone);return 0;
}
void lefony_event(lefony_event_t event,uint32_t first,uint32_t second) {
  (void)first;(void)second;if(event) return;check(++starts==1);
#ifdef FOREGROUND_UNDECLARED
  check(lefony_program_enter()==-3);
  check(lefony_service(12,0)==-3);
  check(lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN})==0);
#else
  exit(main());
#endif
}

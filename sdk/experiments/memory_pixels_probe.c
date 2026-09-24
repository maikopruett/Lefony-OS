/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* R0 protected allocation and software pixels under resumable ARM execution. */
#include <lefony/app_c.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern size_t lefony_experiment_heap_peak(void);
static void check(int good) { if(!good) __asm__ volatile("udf #0"); }

int main(void) {
#ifdef HEAP_UNNEGOTIATED
  *(volatile uint32_t *)0x11001000=123;
#endif
  check(lefony_service(0x7fff0001u,0)==0);
  uint32_t memory[6]={24,1,0,0,0,0};
  check(lefony_service(0x7fff0003u,memory)==0);
  check(memory[2]==0x11001000 && memory[3]==8*1024*1024-8192 && memory[4]>8*1024*1024 && memory[5]==65536);
  for(uint32_t i=0;i<memory[3];i+=4096) check(((volatile unsigned char *)(uintptr_t)memory[2])[i]==0);
#ifdef HEAP_LOW_GUARD
  *(volatile uint32_t *)(uintptr_t)(memory[2]-4)=123;
#endif
#ifdef HEAP_HIGH_GUARD
  *(volatile uint32_t *)(uintptr_t)(memory[2]+memory[3])=123;
#endif
#ifdef HEAP_EXECUTE
  ((void (*)(void))(uintptr_t)memory[2])();
#endif
  /* This is Doom's default zone size, in addition to the pixel allocation. */
  const size_t zone_size=6*1024*1024;
  unsigned char *zone=calloc(zone_size,1);
  check(zone && !((uintptr_t)zone&7));
  for(size_t i=0;i<zone_size;i+=4096) { check(zone[i]==0);zone[i]=(unsigned char)(i/4096); }
  zone[zone_size-1]=91;
  check(lefony_service(0x7fff0003u,memory)==0); // Querying again cannot erase live allocations.
  check(zone[zone_size-1]==91);
  check(lefony_service(0x7fff0002u,0)==0);
  for(size_t i=0;i<zone_size;i+=4096) check(zone[i]==(unsigned char)(i/4096));
  errno=0;check(realloc(zone,memory[3]+1)==0 && errno==ENOMEM && zone[zone_size-1]==91);
  uint16_t *pixels=malloc(320*240*2);
  check(pixels!=0);
  for(unsigned y=0;y<240;y++) for(unsigned x=0;x<320;x++)
    pixels[y*320+x]=(x<160)==(y<120)?LEFONY_GREEN:LEFONY_WHITE;
  uint32_t draw[10]={40,1,0,0,0,320,240,320,(uint32_t)(uintptr_t)pixels,320*240*2};
  check(lefony_service(0x7fff0004u,draw)==0);
  check(lefony_service(0x7fff0002u,0)==0);
  // Rejected requests cannot partially draw over the successfully copied frame.
  memset(pixels,0,320*240*2);
  draw[5]=UINT32_MAX;check(lefony_service(0x7fff0004u,draw)==-4);draw[5]=320;
  draw[7]=319;check(lefony_service(0x7fff0004u,draw)==-4);draw[7]=320;
  draw[9]--;check(lefony_service(0x7fff0004u,draw)==-4);draw[9]++;
  draw[8]=memory[2]+memory[3]-2;check(lefony_service(0x7fff0004u,draw)==-4);
  draw[8]=0x82000000;check(lefony_service(0x7fff0004u,draw)==-4);
  draw[8]=(uint32_t)(uintptr_t)pixels;
  draw[2]=1;check(lefony_service(0x7fff0004u,draw)==-4);
  // Legacy checked transfer services may use this explicitly negotiated heap.
  uint32_t *record=(uint32_t *)pixels;
  int prior=lefony_read_data(0,record,8);
  check(prior==-1 || (prior==8 && record[0]==0x4d454d31));
  check(lefony_fill((lefony_rect_t){0,0,8,8,prior==8?LEFONY_GREEN:LEFONY_WHITE})==0);
  record[0]=0x4d454d31;record[1]=(uint32_t)lefony_experiment_heap_peak();
  check(record[1]>=zone_size+320*240*2 && record[1]<memory[3]);
  check(lefony_write_data(0,record,8)==8);
  free(pixels);free(zone);
  return 0;
}

void lefony_event(lefony_event_t event,uint32_t first,uint32_t second) {
  (void)event;(void)first;(void)second;check(main()==0);
}

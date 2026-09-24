/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Real newlib allocation transitions, including temporary realloc overlap. */
#include <lefony/foreground.h>
#include <errno.h>
#include <malloc.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
extern volatile LefonyHeapProfile lefony_heap_profile;
volatile unsigned heap_stage;
static void *fragments[128];
int main(void) {
  (void)mallinfo();
  unsigned base=lefony_heap_profile.allocatedBytes;
  errno=EDOM;
  unsigned char *p=malloc(1024),*guard=malloc(64);
  if(!p || !guard || errno!=EDOM) return 10;
  memset(p,0x65,1024);memset(guard,0x38,64);
  if(lefony_heap_profile.allocatedBytes<base+1088) return 11;
  unsigned char *larger=realloc(p,8192);
  if(!larger || larger==p || memcmp(larger,guard,64)==0) return 12;
  for(unsigned i=0;i<1024;i++) if(larger[i]!=0x65) return 13;
  if(lefony_heap_profile.allocatedPeak<base+1024+64+8192) return 14;
  unsigned before=lefony_heap_profile.allocatedBytes;
  volatile size_t impossible=SIZE_MAX;
  errno=0;
  if(malloc(impossible)!=NULL || errno!=ENOMEM || lefony_heap_profile.allocatedBytes!=before) return 15;
  free(larger);free(guard);
  if(lefony_heap_profile.allocatedBytes!=base) return 16;
  unsigned *zeroed=calloc(128,sizeof(*zeroed));
  if(!zeroed) return 17;
  for(unsigned i=0;i<128;i++) if(zeroed[i]) return 18;
  free(zeroed);
  void *aligned=memalign(4096,12345);
  if(!aligned || (uintptr_t)aligned%4096) return 19;
  free(aligned);
  for(unsigned i=0;i<128;i++) {
    fragments[i]=malloc(16+i*31);
    if(!fragments[i]) return 20;
  }
  for(unsigned i=0;i<128;i+=2) {free(fragments[i]);fragments[i]=NULL;}
  p=malloc(512*1024);
  if(!p || lefony_heap_profile.allocatedPeak<512*1024) return 21;
  memset(p,0xa7,512*1024);free(p);
  for(unsigned i=1;i<128;i+=2) free(fragments[i]);
  if(lefony_heap_profile.allocatedBytes!=base || lefony_heap_profile.flags!=LEFONY_HEAP_PROFILE_OBSERVED) return 22;
  heap_stage=1;
  lefony_program_sleep(50);
  return 0;
}

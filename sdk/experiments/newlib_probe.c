/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* R0 libc probe only. No production file adapter or conventional main yet. */
#include <lefony/app_c.h>
#include <errno.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

extern size_t lefony_experiment_heap_used(void);
extern size_t lefony_experiment_heap_capacity(void);

static void check(int condition) {
  if (!condition) __asm__ volatile("udf #0");
}
static int compare(const void *a, const void *b) {
  int x=*(const int *)a, y=*(const int *)b;
  return (x>y)-(x<y);
}
void lefony_event(lefony_event_t event, uint32_t first, uint32_t second) {
  (void)first; (void)second;
  if (event != LEFONY_START) return;
  for (unsigned round=0; round<32; round++) {
    unsigned char *bytes=calloc(257,1);
    check(bytes && ((uintptr_t)bytes % 8) == 0);
    for (unsigned i=0;i<257;i++) check(bytes[i]==0);
    memset(bytes,0x5a,257);
    unsigned char *grown=realloc(bytes,8192);
    check(grown!=NULL);
    for (unsigned i=0;i<257;i++) check(grown[i]==0x5a);
    free(grown);
  }
  volatile size_t overflow=SIZE_MAX;
  errno=0;
  check(calloc(overflow,2)==NULL && errno==ENOMEM);
  unsigned char *retained=malloc(64);
  check(retained!=NULL);
  retained[0]=91;
  errno=0;
  check(realloc(retained,1024*1024)==NULL && errno==ENOMEM && retained[0]==91);
  free(retained);
  char text[96];
  check(snprintf(text,sizeof(text),"%d %.3f %s",-27,1.25,"ARM")==13);
  check(strcmp(text,"-27 1.250 ARM")==0);
  char short_text[4];
  check(snprintf(short_text,sizeof(short_text),"%s","abcdef")==6);
  check(strcmp(short_text,"abc")==0);
  char *end=NULL;
  check(strtol("-123tail",&end,10)==-123 && strcmp(end,"tail")==0);
  check(strtod("1.25e2!",&end)==125 && *end=='!');
  int integer=0; double real=0;
  check(sscanf("42 2.5","%d %lf",&integer,&real)==2 && integer==42 && real==2.5);
  int values[]={5,-2,19,0};
  qsort(values,4,sizeof(int),compare);
  check(values[0]==-2 && values[3]==19);
  int key=5;
  check(bsearch(&key,values,4,sizeof(int),compare)==values+2);
  volatile double number=2.0;
  check(fabs(sqrt(number)*sqrt(number)-2.0)<1e-12);
  errno=0;
  check(fopen("unavailable","rb")==NULL && errno==ENOSYS);
  check(lefony_experiment_heap_used()<lefony_experiment_heap_capacity());
  lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN});
}

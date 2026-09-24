/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
// Assertion failures use a different exception from the intentional UDF case.
static void check(int value) { if(!value) *(volatile uint32_t *)0x82000000=0; }
int main(void) {
  struct stat st;
  if(stat("keep",&st)==0) {
    char bytes[8]={0};FILE *f=fopen("keep","rb");check(f && fread(bytes,1,5,f)==5 && !memcmp(bytes,"prior",5) && fclose(f)==0);
    int found=stat("partial",&st);uint32_t record=0;int saved=lefony_read_data(0,&record,4);
#if defined(FILES_CLEAN_EXIT) || defined(FILES_FAIL_EXIT)
    check(found==0 && st.st_size==270336);
#else
    check(found==-1 && errno==ENOENT);
#endif
#ifdef FILES_CLEAN_EXIT
    check(saved==4 && record==77);
#else
    check(saved==-1);
#endif
    lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN});return 0;
  }
  check(errno==ENOENT);FILE *f=fopen("keep","wb");check(f && fwrite("prior",1,5,f)==5 && fclose(f)==0);
  f=fopen("partial","wb");check(f!=NULL);unsigned char buffer[2048];memset(buffer,0x55,sizeof(buffer));
  for(unsigned i=0;i<132;i++) check(fwrite(buffer,1,sizeof(buffer),f)==sizeof(buffer));
  check(fflush(f)==0);uint32_t record=77;check(lefony_write_data(0,&record,4)==4);
  lefony_fill((lefony_rect_t){0,0,320,240,0x001f});lefony_service(0x7fff0002u,0);
#ifdef FILES_FAULT
  __asm__ volatile("udf #0");
#elif defined(FILES_FAIL_EXIT)
  exit(7);
#elif defined(FILES_CLEAN_EXIT)
  return 0;
#endif
  for(;;) __asm__ volatile("nop");
}
void lefony_event(uint32_t event,uint32_t a,uint32_t b) {
  (void)a;(void)b;if(event) return;check(lefony_program_enter()==0);exit(main());
}

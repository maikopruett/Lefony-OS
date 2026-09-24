/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Ordinary main/stdio proof. All file writes use the public installed app API. */
#define _POSIX_C_SOURCE 200809L
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static void check(int condition) { if(!condition) __asm__ volatile("udf #0"); }
static unsigned char bytes[8197];
int main(int argc,char **argv) {
  check(argc==2);
  if(!strcmp(argv[1],"denied")) {
    FILE *f=fopen("checkpoint","wb");check(f!=NULL);
    errno=0;check(fsync(fileno(f))==-1 && errno==EACCES);
    _exit(0);
  }
  if(!strcmp(argv[1],"unsupported")) {
    errno=0;check(fsync(3)==-1 && errno==ENOSYS);return 0;
  }
  for(unsigned i=0;i<sizeof(bytes);i++) bytes[i]=(i*131u+(i>>8))^0x5d;
  FILE *saved=fopen("checkpoint","rb");
  if(saved) {
    memcpy(bytes,"SAVE",4);
    for(unsigned i=0;i<sizeof(bytes);i++) check(fgetc(saved)==bytes[i]);
    check(fgetc(saved)==EOF && feof(saved) && !ferror(saved));
    check(fsync(fileno(saved))==0 && fclose(saved)==0);return 0;
  }
  check(errno==ENOENT);
  errno=0;check(fsync(-1)==-1 && errno==EBADF);
  FILE *f=fopen("checkpoint","w+b");check(f!=NULL);
  check(fwrite(bytes,1,sizeof(bytes),f)==sizeof(bytes));
  check(fflush(f)==0 && fsync(fileno(f))==0);
  check(ftell(f)==(long)sizeof(bytes));
  FILE *old=fopen("checkpoint","rb");check(old!=NULL);
  check(fseek(f,0,SEEK_SET)==0 && fwrite("SAVE",1,4,f)==4);
  check(fflush(f)==0 && fsync(fileno(f))==0 && ftell(f)==4);
  check(fsync(fileno(f))==0 && ftell(f)==4);
  for(unsigned i=0;i<sizeof(bytes);i++) check(fgetc(old)==bytes[i]);
  check(fclose(old)==0);
  // These later bytes reach OS staging, but Home/fault/_exit must preserve SAVE.
  check(fseek(f,0,SEEK_SET)==0 && fwrite("EDIT",1,4,f)==4 && fflush(f)==0);
  if(!strcmp(argv[1],"fault")) __asm__ volatile(
    ".global lefony_sync_expected_fault\nlefony_sync_expected_fault:\nudf #0");
  if(!strcmp(argv[1],"exit")) _exit(7);
  check(lefony_fill((lefony_rect_t){0,0,320,240,0x001f})==0);
  for(;;) check(lefony_program_yield()==0);
}

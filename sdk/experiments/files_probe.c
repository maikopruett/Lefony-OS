/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define INPUT_BYTES (2u*(128u*1024u-128u)+37u)
static void fail(unsigned line) {
  lefony_fill((lefony_rect_t){0,0,320,240,0xf800});
  for(unsigned i=0;i<16;i++) if(line&(1u<<i)) lefony_fill((lefony_rect_t){(int32_t)(i*10),0,8,8,0xffff});
  lefony_program_yield();__asm__ volatile("udf #0");
}
#define CHECK(c) do { if(!(c)) fail(__LINE__); } while(0)
static unsigned char pattern(unsigned i) { return (i*131u+(i>>8))^0x5d; }
static void ready(int cold) {
  lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN});
  lefony_fill((lefony_rect_t){0,0,16,16,cold?LEFONY_WHITE:0});
}
int main(void) {
  CHECK(lefony_service(10,(const void *)0x82000000)==-LEFONY_FILE_INVALID);
  LefonyFileRequest malformed=lefony_file_request(LEFONY_FILE_OPEN);
  malformed.path=0xffffffffu;malformed.pathBytes=2;malformed.flags=1;
  CHECK(lefony_files(&malformed)==-LEFONY_FILE_INVALID);
  malformed.path=0;malformed.pathBytes=96;
  CHECK(lefony_files(&malformed)==-LEFONY_FILE_INVALID);
  unsigned char in[2048],out[4096];struct stat st;
#ifdef LEFONY_STANDARD_MAIN
  // The ordinary adapter accepts root-relative ./ names without weakening
  // parent/absolute-path rejection or silently dropping a file's trailing /.
  CHECK(mkdir("././paths/",0700)==0 || errno==EEXIST);
  FILE *relative=fopen("././paths/check","wb");CHECK(relative);
  CHECK(fwrite("path",1,4,relative)==4 && fclose(relative)==0);
  CHECK(stat("./paths/check",&st)==0 && st.st_size==4);
  CHECK(rename("./paths/check","././paths/moved")==0);
  CHECK(fopen("./../paths/moved","rb")==NULL && errno==EINVAL);
  CHECK(fopen("/paths/moved","rb")==NULL && errno==EINVAL);
  CHECK(fopen("./paths/moved/","wb")==NULL && errno==EINVAL);
  CHECK(stat("paths/moved",&st)==0 && st.st_size==4);
  CHECK(unlink("./paths/moved")==0);
#endif
  if(stat("output",&st)==0) {
    CHECK(st.st_size>65536);FILE *f=fopen("output","rb");CHECK(f);
    unsigned char header[8];CHECK(fread(header,1,8,f)==8 && !memcmp(header,"LFW1",4));
    unsigned position=0;
    for(unsigned i=0;i<INPUT_BYTES;i++) {
      unsigned char value=pattern(i);if(!(value&1)) continue;
      CHECK(fgetc(f)==value && fgetc(f)==(value^0xa5));position+=2;
    }
    CHECK(fgetc(f)==EOF && feof(f) && !ferror(f));
    unsigned bytes;memcpy(&bytes,header+4,4);CHECK(bytes==position && bytes+8==(unsigned)st.st_size);
    CHECK(fclose(f)==0);ready(1);return 0;
  }
  CHECK(errno==ENOENT);
  FILE *f=fopen("input","wb");CHECK(f);
  for(unsigned pos=0;pos<INPUT_BYTES;) {
    unsigned n=INPUT_BYTES-pos;if(n>sizeof(in)) n=sizeof(in);
    for(unsigned i=0;i<n;i++) in[i]=pattern(pos+i);
    CHECK(fwrite(in,1,n,f)==n);pos+=n;
  }
  CHECK(fclose(f)==0);
  FILE *input=fopen("input","rb"),*output=fopen("temporary","wb+");CHECK(input && output);
  unsigned char header[8]={'L','F','W','1',0,0,0,0};CHECK(fwrite(header,1,8,output)==8);
  unsigned total=0;
  for(;;) {
    size_t n=fread(in,1,sizeof(in),input);CHECK(!ferror(input));if(!n) break;
    unsigned used=0;
    for(unsigned i=0;i<n;i++) if(in[i]&1) { out[used++]=in[i];out[used++]=in[i]^0xa5; }
    CHECK(fwrite(out,1,used,output)==used);total+=used;
  }
  CHECK(feof(input));CHECK(fclose(input)==0);
  CHECK(fseek(output,4,SEEK_SET)==0 && ftell(output)==4);
  CHECK(fwrite(&total,1,4,output)==4 && fflush(output)==0);
  CHECK(fseek(output,0,SEEK_SET)==0 && fread(header,1,8,output)==8 && !memcmp(header,"LFW1",4));
  CHECK(fclose(output)==0);
  // Replace an already committed destination through the real rename adapter.
  output=fopen("output","wb");CHECK(output && fwrite("old",1,3,output)==3 && fclose(output)==0);
  CHECK(rename("temporary","output")==0);
  CHECK(stat("output",&st)==0 && (unsigned)st.st_size==total+8);
  CHECK(fopen("temporary","rb")==NULL && errno==ENOENT);
  CHECK(unlink("input")==0);
  // errno and handle errors are real OS responses, not successful placeholders.
  CHECK(close(999999)==-1 && errno==EBADF);
  ready(0);return 0;
}
#ifndef LEFONY_STANDARD_MAIN
void lefony_event(uint32_t event,uint32_t first,uint32_t second) {
  (void)first;(void)second;if(event) return;
  CHECK(lefony_program_enter()==0);
  exit(main());
}
#endif

/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#define check(yes) do {if(!(yes)) __asm__ volatile("udf %0" :: "I"(__LINE__));} while(0)
static inline __attribute__((always_inline)) void value(const char *expected) {
  char content[16]={0};int fd=open("value",O_RDONLY);check(fd>=0);
  int n=read(fd,content,sizeof(content));
  check(n==(int)strlen(expected));
  check(close(fd)==0);
  check(!strcmp(content,expected));
}
static void copied_reply(void) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_QUOTA);check(lefony_files(&r)==1);uint32_t token=r.token;
  const uint32_t forbidden[]={0x82000000u,0x10000000u};
  for(unsigned i=0;i<2;i++) {
    r=lefony_file_request(LEFONY_FILE_POLL);r.token=token;r.buffer=forbidden[i];r.capacity=48;
    check(lefony_files(&r)==-LEFONY_FILE_INVALID);
  }
  LefonyFileQuota q;int status=1;
  for(unsigned i=0;i<1000 && status==1;i++) {
    check(lefony_program_yield()==0);r=lefony_file_request(LEFONY_FILE_POLL);r.token=token;
    r.buffer=(uint32_t)(uintptr_t)&q;r.capacity=sizeof(q);status=lefony_files(&r);
  }
  check(status==0 && !r.error && r.length==48 && q.committedBytes==9);
}
int main(int argc,char **argv) {
  check(argc==2);LefonyFileQuota q;
  if(strcmp(argv[1],"normal")) {
    int expected=!strcmp(argv[1],"denied")?EACCES:ENOSYS;
    check(lefony_file_quota(&q)==-1 && errno==expected);return 0;
  }
  check(lefony_file_quota(&q)==0 && q.size==48 && q.schema==1 && q.limitBytes==32u*1024u*1024u);
  check(!q.reserved[0] && !q.reserved[1] && !q.reserved[2] && !q.flags);
  if(!q.committedBytes) return 0; /* First installed launch; host seeds synthetic assets afterward. */
  if(q.committedBytes==9) {value("01234567X");copied_reply();return 0;}
  check(q.committedBytes==q.limitBytes && q.projectedBytes==q.limitBytes && !q.remainingBytes);
  value("01234567");int fd=open("value",O_RDWR);check(fd>=0 && lseek(fd,6,SEEK_SET)==6);
  check(write(fd,"FAIL",4)==2);errno=0;check(write(fd,"x",1)==-1 && errno==EDQUOT);
  check(lefony_file_quota(&q)==0 && q.flags==(LEFONY_FILE_QUOTA_WRITER_OPEN|LEFONY_FILE_QUOTA_WRITER_FAILED));
  errno=0;check(close(fd)==-1 && errno==EDQUOT);value("01234567");
  /* Truncate exposes projected headroom, but any failure still preserves the old file. */
  fd=open("value",O_WRONLY|O_TRUNC);check(fd>=0);
  check(lefony_file_quota(&q)==0 && q.remainingBytes==8 && q.projectedBytes==q.limitBytes-8);
  check(lseek(fd,8,SEEK_SET)==8);errno=0;check(write(fd,"x",1)==-1 && errno==EDQUOT);
  check(close(fd)==-1);value("01234567");
  check(unlink("filler")==0 && lefony_file_quota(&q)==0 && q.committedBytes==8 && q.remainingBytes==q.limitBytes-8);
  fd=open("value",O_WRONLY|O_APPEND);check(fd>=0 && write(fd,"X",1)==1);
  check(lefony_file_quota(&q)==0 && q.committedBytes==8 && q.projectedBytes==9);
  check(fsync(fd)==0 && lefony_file_quota(&q)==0 && q.committedBytes==9 && q.projectedBytes==9);
  check(close(fd)==0);value("01234567X");copied_reply();return 0;
}

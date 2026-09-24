/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
static void check(int condition) { if(!condition) __asm__ volatile("udf #0"); }
static void create(const char *name,const char *text) {
  FILE *f=fopen(name,"wb");check(f!=NULL);
  check(fwrite(text,1,strlen(text),f)==strlen(text) && fclose(f)==0);
}
static unsigned enumerate(void) {
  LefonyDirectoryPage page;unsigned count=0;uint32_t next=0,generation=0;
  do {
    check(lefony_file_list(".",next,generation,&page)==0);
    check(page.size==sizeof(page) && page.schema==1 && page.generation && page.count<=16);
    generation=page.generation;next=page.next;
    for(unsigned i=0;i<page.count;i++) {
      check(memchr(page.entries[i].path,0,sizeof(page.entries[i].path))!=NULL);
      check(strchr(page.entries[i].path,'/')==NULL);count++;
    }
  } while(next);
  return count;
}
static void copied_reply(void) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_LIST);
  check(lefony_files(&r)==1 && r.token);uint32_t token=r.token;
  const uint32_t forbidden[]={0x82000000u,0x10000000u};
  for(unsigned i=0;i<sizeof(forbidden)/sizeof(*forbidden);i++) {
    r=lefony_file_request(LEFONY_FILE_POLL);r.token=token;
    r.buffer=forbidden[i];r.capacity=sizeof(LefonyDirectoryPage);
    check(lefony_files(&r)==-LEFONY_FILE_INVALID);
  }
  LefonyDirectoryPage page;int status=1;
  for(unsigned i=0;i<1000 && status==1;i++) {
    check(lefony_program_yield()==0);r=lefony_file_request(LEFONY_FILE_POLL);r.token=token;
    r.buffer=(uint32_t)(uintptr_t)&page;r.capacity=sizeof(page);status=lefony_files(&r);
  }
  check(status==0 && !r.error && r.length==sizeof(page) && page.count==16);
  r=lefony_file_request(LEFONY_FILE_LIST);r.path=0x82000000u;r.pathBytes=3;
  check(lefony_files(&r)==-LEFONY_FILE_INVALID);
}
int main(int argc,char **argv) {
  check(argc==2);LefonyFileSpace usage;LefonyDirectoryPage page;
  if(strcmp(argv[1],"normal")) {
    int expected=!strcmp(argv[1],"denied")?EACCES:ENOSYS;
    errno=0;check(lefony_file_space(&usage)==-1 && errno==expected);
    errno=0;check(lefony_file_list("",0,0,&page)==-1 && errno==expected);return 0;
  }
  check(lefony_file_space(&usage)==0 && usage.size==sizeof(usage) && usage.schema==1);
  if(usage.files) {
    check(usage.files==22 && usage.directories==1 && usage.fileBytes==77);
    check(!usage.flags && !usage.writerBytes && !usage.writerCommittedBytes && enumerate()==22);
    check(lefony_file_list("folder/",0,0,&page)==0 && page.count==1 && !page.next);
    check(!strcmp(page.entries[0].path,"folder/value") && page.entries[0].bytes==13);return 0;
  }
  check(!usage.fileBytes && !usage.directories && !usage.privateBytes && !usage.flags);
  check(usage.capacityBytes+usage.reservedBytes==64u*1024u*1024u);
  check(usage.availableBytes==usage.capacityBytes-usage.allocatedBytes);
  check(lefony_file_list("",0,0,&page)==0 && !page.count && !page.next);
  check(mkdir("folder",0700)==0);
  for(unsigned i=0;i<20;i++) { char name[16];snprintf(name,sizeof(name),"file%02u",i);create(name,"abc"); }
  create("folder/value","nested record");
  check(lefony_file_list("././",0,0,&page)==0 && page.count==16 && page.next);
  uint32_t next=page.next,generation=page.generation;
  FILE *writer=fopen("last","wb");check(writer!=NULL);
  check(fwrite("done",1,4,writer)==4 && fflush(writer)==0);
  check(lefony_file_space(&usage)==0 && usage.files==21 && usage.fileBytes==73 &&
    usage.flags==LEFONY_FILE_SPACE_WRITER_OPEN && usage.writerBytes==4 && !usage.writerCommittedBytes);
  check(lefony_file_list("",next,generation,&page)==0);
  check(fclose(writer)==0);
  errno=0;check(lefony_file_list("",next,generation,&page)==-1 && errno==ESTALE);
  check(enumerate()==22);
  copied_reply();
  errno=0;check(lefony_file_list("file00",0,0,&page)==-1 && errno==ENOTDIR);
  errno=0;check(lefony_file_list("missing",0,0,&page)==-1 && errno==ENOENT);
  const char *invalid[]={"/",".//","../escape","folder//"};
  for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++) {
    errno=0;check(lefony_file_list(invalid[i],0,0,&page)==-1 && errno==EINVAL);
  }
  check(lefony_file_space(&usage)==0 && usage.files==22 && usage.directories==1 && usage.fileBytes==77);
  return 0;
}

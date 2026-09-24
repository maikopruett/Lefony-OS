/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/data.h>
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void fail(unsigned line) {
  char text[64];int n=snprintf(text,sizeof(text),"Data checkpoint failed at %u",line);
  lefony_text((lefony_text_t){4,4,LEFONY_WHITE,LEFONY_BLACK,text,(uint32_t)n});exit(line);
}
#define CHECK(value) do { if(!(value)) fail(__LINE__); } while(0)
static LefonyDataRequest wait(uint32_t token) {
  uint32_t start=lefony_millis();
  for(;;) {
    LefonyDataRequest r=lefony_data_request(LEFONY_DATA_POLL);r.token=token;
    int result=lefony_data(&r);CHECK(result==0 || result==1);
    if(!result) return r;
    CHECK((uint32_t)(lefony_millis()-start)<120000);CHECK(!lefony_program_yield());
  }
}
static LefonyDataRequest operation(uint32_t op,uint32_t generation,uint32_t schema,uint32_t bytes) {
  LefonyDataRequest r=lefony_data_request(op);r.generation=generation;r.dataSchema=schema;r.bytes=bytes;
  CHECK(lefony_data(&r)==1);r=wait(r.token);CHECK(!r.error && r.state==LEFONY_DATA_COMPLETE);return r;
}
static LefonyDataRequest info(void) {return operation(LEFONY_DATA_INSPECT,0,0,0);}
__attribute__((noinline,noreturn)) static void expected_fault(void) {
  __asm__ volatile(".global lefony_data_expected_fault\nlefony_data_expected_fault:\n udf #0");
  __builtin_unreachable();
}
static void named(const char *text) {
  FILE *f=fopen("document.txt","wb");CHECK(f!=NULL);
  CHECK(fwrite(text,1,strlen(text),f)==strlen(text));CHECK(!fclose(f));
}
static void verify_named(const char *text) {
  char out[64]={0};FILE *f=fopen("document.txt","rb");CHECK(f!=NULL);
  CHECK(fread(out,1,sizeof(out),f)==strlen(text));CHECK(!strcmp(out,text));CHECK(!fclose(f));
}
int main(int argc,char **argv) {
  CHECK(argc==2);
  if(!strcmp(argv[1],"denied")) {
    LefonyDataRequest r=lefony_data_request(LEFONY_DATA_INSPECT);
    CHECK(lefony_data(&r)==-LEFONY_FILE_DENIED);return 0;
  }
  if(!strcmp(argv[1],"unsupported")) {
    LefonyDataRequest r=lefony_data_request(LEFONY_DATA_INSPECT);
    CHECK(lefony_data(&r)==-3);return 0;
  }
  // The kernel rejects privileged/code output destinations before reading or
  // consuming a data request, and the ordinary stack destination still works.
  CHECK(lefony_data((LefonyDataRequest *)(uintptr_t)0x80000000)==-LEFONY_FILE_INVALID);
  CHECK(lefony_data((LefonyDataRequest *)(uintptr_t)0x10000000)==-LEFONY_FILE_INVALID);
  LefonyDataRequest state=info();uint32_t value=0;
  int present=lefony_read_data(0,&value,sizeof(value));
  if(!strcmp(argv[1],"migration")) {
    if(state.appSchema==0) {
      CHECK(present<0);value=111;CHECK(lefony_write_data(0,&value,4)==4);
      state=operation(LEFONY_DATA_CHECKPOINT,state.generation,0,4);
      CHECK(state.flags==LEFONY_DATA_COMMITTED);named("old document");return 0;
    }
    CHECK(state.flags&LEFONY_DATA_PENDING_UPGRADE);
    if(state.dataSchema==0) {
      CHECK(present==4 && value==111);verify_named("old document");
      value=222;CHECK(lefony_write_data(0,&value,4)==-1);
      state=operation(LEFONY_DATA_BEGIN_MIGRATION,state.generation,1,0);
      CHECK(state.flags&LEFONY_DATA_MIGRATING);CHECK(lefony_write_data(0,&value,4)==4);
      named("migrated document");state=info();
      state=operation(LEFONY_DATA_CHECKPOINT,state.generation,1,4);
      CHECK(state.dataSchema==1 && (state.flags&LEFONY_DATA_PENDING_UPGRADE));
      return 0; // Explicit data users keep the recovery pair across normal Close.
    }
    CHECK(present==4 && value==222);verify_named("migrated document");
    state=operation(LEFONY_DATA_ACCEPT,state.generation,1,0);
    CHECK(state.flags==LEFONY_DATA_COMMITTED);return 0;
  }
  if(present==4) {
    CHECK(value==(!strcmp(argv[1],"normal")?55u:44u));
    value=66;CHECK(lefony_write_data(0,&value,4)==4);
    state=operation(LEFONY_DATA_CHECKPOINT,state.generation,0,4);
    CHECK(state.flags==LEFONY_DATA_COMMITTED && !state.error);return 0;
  }
  CHECK(present<0);value=44;CHECK(lefony_write_data(0,&value,4)==4);
  LefonyDataRequest save=lefony_data_request(LEFONY_DATA_CHECKPOINT);
  save.generation=state.generation;save.bytes=4;CHECK(lefony_data(&save)==1);
  value=55;CHECK(lefony_write_data(0,&value,4)==4);
  state=wait(save.token);
  CHECK(!state.error && (state.flags&LEFONY_DATA_COMMITTED) && (state.flags&LEFONY_DATA_DIRTY));
  CHECK(state.editRevision!=state.snapshotRevision);
  CHECK(lefony_read_data(0,&value,4)==4 && value==55);
  if(!strcmp(argv[1],"normal")) return 0;
  if(!strcmp(argv[1],"fault")) expected_fault();
  CHECK(!strcmp(argv[1],"home"));lefony_fill((lefony_rect_t){0,0,320,240,0x001f});
  for(;;) CHECK(!lefony_program_yield());
}

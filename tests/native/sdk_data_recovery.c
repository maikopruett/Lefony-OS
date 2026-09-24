/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/data.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void fail(unsigned line) {
  char text[64];int n=snprintf(text,sizeof(text),"Data recovery failed at %u",line);
  lefony_text((lefony_text_t){4,4,LEFONY_WHITE,LEFONY_BLACK,text,(uint32_t)n});exit(line);
}
#define CHECK(value) do { if(!(value)) fail(__LINE__); } while(0)
static LefonyDataRequest operation(uint32_t op,uint32_t generation,uint32_t schema,uint32_t bytes) {
  LefonyDataRequest r=lefony_data_request(op);r.generation=generation;r.dataSchema=schema;r.bytes=bytes;
  CHECK(lefony_data(&r)==1);uint32_t token=r.token,start=lefony_millis();
  do {
    r=lefony_data_request(LEFONY_DATA_POLL);r.token=token;
    int status=lefony_data(&r);CHECK(status==0 || status==1);
    if(!status) {CHECK(!r.error && r.state==LEFONY_DATA_COMPLETE);return r;}
    CHECK((uint32_t)(lefony_millis()-start)<120000);CHECK(!lefony_program_yield());
  } while(1);
}
static void named(const char *text) {
  FILE *f=fopen("document.txt","wb");CHECK(f!=NULL);
  CHECK(fwrite(text,1,strlen(text),f)==strlen(text));CHECK(!fclose(f));
}
static void verify_named(const char *text) {
  char out[64]={0};FILE *f=fopen("document.txt","rb");CHECK(f!=NULL);
  CHECK(fread(out,1,sizeof(out),f)==strlen(text));CHECK(!strcmp(out,text));CHECK(!fclose(f));
}
int main(void) {
  LefonyDataRequest state=operation(LEFONY_DATA_INSPECT,0,0,0);uint32_t value=0;
  int present=lefony_read_data(0,&value,4);
  if(!state.appSchema) {
    if(present<0) {
      value=111;CHECK(lefony_write_data(0,&value,4)==4);
      operation(LEFONY_DATA_CHECKPOINT,state.generation,0,4);named("old document");
    } else {
      if(state.bytes==65536) {
        unsigned char block[4096];
        for(unsigned offset=0;offset<65536;offset+=sizeof(block)) {
          CHECK(lefony_read_data(offset,block,sizeof(block))==sizeof(block));
          for(unsigned i=0;i<sizeof(block);i++) CHECK(block[i]==(unsigned char)((offset+i)*13u));
        }
      } else CHECK(present==4 && value==111 && state.bytes==4);
      verify_named("old document");
    }
  } else {
    CHECK(state.flags&LEFONY_DATA_PENDING_UPGRADE);
    if(!state.dataSchema) {
      CHECK(present==4 && value==111);verify_named("old document");
      state=operation(LEFONY_DATA_BEGIN_MIGRATION,state.generation,1,0);
      value=222;CHECK(lefony_write_data(0,&value,4)==4);named("migrated document");
      state=operation(LEFONY_DATA_INSPECT,0,0,0);
      state=operation(LEFONY_DATA_CHECKPOINT,state.generation,1,4);
      CHECK(state.flags&LEFONY_DATA_PENDING_UPGRADE);
    } else {CHECK(present==4 && value==222);verify_named("migrated document");}
    // Leave the retained pair available for the explicit host rollback command.
  }
  lefony_fill((lefony_rect_t){0,0,320,240,LEFONY_GREEN});return 0;
}

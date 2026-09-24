/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#include <lefony/data.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EDIT_MARK 1
#define EXIT_CODE 0
#define CHECK(x) do { if(!(x)) return __LINE__; } while(0)
static LefonyDataRequest operation(unsigned op,unsigned generation,unsigned schema,unsigned bytes) {
  LefonyDataRequest r=lefony_data_request(op);r.generation=generation;r.dataSchema=schema;r.bytes=bytes;
  if(lefony_data(&r)!=1) exit(100);
  unsigned token=r.token,start=lefony_millis();
  for(;;) {
    r=lefony_data_request(LEFONY_DATA_POLL);r.token=token;int result=lefony_data(&r);
    if(result==0 && r.state==LEFONY_DATA_COMPLETE && !r.error) return r;
    if(result!=1 || (unsigned)(lefony_millis()-start)>120000) exit(101);
    lefony_program_yield();
  }
}
int main(void) {
  LefonyDataRequest state=operation(LEFONY_DATA_INSPECT,0,0,0);unsigned count=0;
  if(state.bytes) CHECK(state.bytes==4 && lefony_read_data(0,&count,4)==4);
  if(state.dataSchema!=state.appSchema) {
    CHECK(state.flags&LEFONY_DATA_PENDING_UPGRADE);
    CHECK(state.dataSchema==0 && state.appSchema==1 && count>0);
    state=operation(LEFONY_DATA_BEGIN_MIGRATION,state.generation,1,0);
  }
  FILE *input=fopen("nested/input.txt","rb");CHECK(input);
  char text[32]={0};size_t length=fread(text,1,sizeof(text)-1,input);CHECK(length>0 && !ferror(input) && !fclose(input));
  CHECK(!strcmp(text,"initial") || !strcmp(text,"reseeded"));
  FILE *output=fopen("nested/output.bin","ab");CHECK(output);count++;
  CHECK(fwrite(&count,1,4,output)==4 && !fclose(output));
  CHECK(lefony_write_data(0,&count,4)==4);
  state=operation(LEFONY_DATA_INSPECT,0,0,0);
  state=operation(LEFONY_DATA_CHECKPOINT,state.generation,state.appSchema,4);
  if(state.flags&LEFONY_DATA_PENDING_UPGRADE) operation(LEFONY_DATA_ACCEPT,state.generation,state.appSchema,0);
  lefony_fill((lefony_rect_t){0,0,320,240,EDIT_MARK==1?LEFONY_GREEN:LEFONY_WHITE});
  char message[80];int bytes=snprintf(message,sizeof(message),"Saved visit %u / edit %u / %s",count,EDIT_MARK,text);
  lefony_text((lefony_text_t){4,4,LEFONY_BLACK,LEFONY_WHITE,message,(unsigned)bytes});
  return EXIT_CODE;
}

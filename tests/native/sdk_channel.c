/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <lefony/channel.h>
#include <lefony/foreground.h>
#include <lefony/input_stream.h>
#include <string.h>
#define check(x) do {if(!(x)) lefony_program_exit(__LINE__);} while(0)
static LefonyChannelInfo info(void) {
  LefonyChannelInfo value;check(lefony_channel_info(&value)==0);return value;
}
static void text(const char *value) {
  check(lefony_text((lefony_text_t){8,25,0,0xffff,value,(uint32_t)strlen(value)})==0);
}
static void rejected(LefonyChannelRequest *r,int expected) {
  static unsigned probe=0;probe++;LefonyChannelRequest before=*r;int status=lefony_channel(r);
  if(status!=expected) lefony_program_exit(10000+probe*100-status);
  check(!memcmp(r,&before,sizeof(*r)));
}
int main(int argc,char **argv) {
  check(argc==2);const char *mode=argv[1];uint32_t session=0xabcdef01;
  if(!strcmp(mode,"denied") || !strcmp(mode,"unsupported")) {
    check(lefony_channel_open(&session)==(!strcmp(mode,"denied")?-5:-3));check(session==0xabcdef01);return 0;
  }
  LefonyChannelInfo snapshot;memset(&snapshot,0x75,sizeof(snapshot));
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_INFO);
  r.buffer=(uint32_t)(uintptr_t)&snapshot;r.capacity=sizeof(snapshot);
  for(unsigned i=0;i<16;i++) {LefonyChannelRequest bad=r;((uint32_t *)&bad)[i]=UINT32_MAX;rejected(&bad,-4);}
  r.buffer=(uint32_t)(uintptr_t)&r;rejected(&r,-4);
  r.buffer=0x82000000;rejected(&r,-4);r.buffer=0x10000000;rejected(&r,-4);
  check(lefony_channel(NULL)==-4);check(lefony_service(17,(void *)0x82000000)==-4);
  check(lefony_channel_open(&session)==0 && session);uint32_t old=session;
  check(lefony_channel_open(&old)==-6 && old==session);
  check(lefony_channel_send(session,1,"x",1)==-6);
  check(lefony_fill((lefony_rect_t){0,0,320,240,0xffff})==0);
  text("Channel Lab: waiting for host");
  for(;;) {
    snapshot=info();
    if(snapshot.state==LEFONY_CHANNEL_ENDED) {
      check(!strcmp(mode,"userdeny") || !strcmp(mode,"pair-timeout"));
      check(snapshot.error==(!strcmp(mode,"userdeny")?LEFONY_CHANNEL_DENIED:LEFONY_CHANNEL_TIMEOUT));return 0;
    }
    if(snapshot.state==LEFONY_CHANNEL_CONNECTED) break;
    lefony_program_sleep(5);
  }
  check(!strcmp(snapshot.appId,"channel-lab") && snapshot.nonce[0]+snapshot.nonce[1]+snapshot.nonce[2]+snapshot.nonce[3]);
  check(lefony_fill((lefony_rect_t){0,0,320,240,0xffff})==0);
  text("Connected through public USB");
  uint8_t data[448];
  for(unsigned i=0;i<4;i++) {data[0]=(uint8_t)i;check(lefony_channel_send(session,1,data,1)==0);data[0]=99;}
  check(lefony_channel_send(session,1,data,1)==-LEFONY_CHANNEL_AGAIN);
  uint32_t total=0,checksum=0;int sawOne=0;unsigned number=0;
  for(;;) {
    LefonyInputStream input;check(lefony_read_input_stream(&input)==0);
    check(!lefony_input_key_held(input.held,LEFONY_PHYSICAL_OK));
    for(unsigned i=0;i<input.count;i++) if(input.events[i].kind==LEFONY_INPUT_KEYS) {
      check(!lefony_input_key_held(input.events[i].data.keys.down,LEFONY_PHYSICAL_OK));
      if(lefony_input_key_held(input.events[i].data.keys.down,LEFONY_PHYSICAL_ONE)) sawOne=1;
    }
    snapshot=info();
    if(snapshot.state==LEFONY_CHANNEL_ENDED) {
      check(!strcmp(mode,"hostclose") || !strcmp(mode,"lease") || !strcmp(mode,"reset"));
      check(snapshot.error==(!strcmp(mode,"lease")?LEFONY_CHANNEL_TIMEOUT:LEFONY_CHANNEL_DISCONNECTED));
      check(lefony_channel_send(session,1,NULL,0)==-(int)snapshot.error);return 0;
    }
    LefonyChannelRequest result;memset(&result,0x71,sizeof(result));
    if(snapshot.nextReceiveBytes>1) {
      LefonyChannelRequest before=result;data[0]=99;
      check(lefony_channel_receive(session,data,1,&result)==-LEFONY_CHANNEL_TOO_SMALL);
      check(!memcmp(&before,&result,sizeof(result)) && data[0]==99);
    }
    int status=lefony_channel_receive(session,data,sizeof(data),&result);
    if(status==-LEFONY_CHANNEL_AGAIN) {lefony_program_sleep(1);continue;}
    check(status==0 && result.sequence==++number);
    if(result.kind==2) {
      check(result.length<=448);
      for(unsigned i=0;i<result.length;i++) {check(data[i]==(uint8_t)((total+i)*37+11));checksum+=data[i];data[i]^=0xa5;}
      total+=result.length;
      do {status=lefony_channel_send(session,2,data,result.length);if(status==-6) lefony_program_sleep(1);} while(status==-6);
      check(status==0);
    } else if(result.kind==3) {
      check(!result.length && total==70017 && sawOne);
      uint32_t summary[3]={total,checksum,(uint32_t)sawOne};
      do {status=lefony_channel_send(session,3,summary,sizeof(summary));if(status==-6) lefony_program_sleep(1);} while(status==-6);
      check(status==0);
    } else if(result.kind==4) {
      check(!result.length);
      if(!strcmp(mode,"fault")) {*(volatile uint32_t *)0x82000000=1;return 99;}
      return 0;
    } else if(result.kind==5) {
      check(lefony_channel_close(session)==0);check(lefony_channel_open(&old)==0 && old>session);
      check(lefony_channel_send(session,1,NULL,0)==-LEFONY_CHANNEL_STALE);session=old;number=0;
      while(info().state!=LEFONY_CHANNEL_CONNECTED) lefony_program_sleep(5);
      check(lefony_channel_send(session,5,"fresh",5)==0);
    } else check(0);
  }
}

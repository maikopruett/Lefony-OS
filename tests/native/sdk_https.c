/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include <lefony/https.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#define check(x) do {if(!(x)) lefony_program_exit(__LINE__);} while(0)
static void send_metadata(uint32_t session,uint32_t kind,const char *text) {
  uint32_t length=(uint32_t)strlen(text),offset=0;
  while(offset<length) {
    uint32_t size=length-offset;if(size>440) size=440;
    int status=lefony_https_metadata(session,kind,1,offset,text+offset,size);
    if(status==-6) {lefony_program_sleep(1);continue;}
    check(status==0);offset+=size;
  }
}
int main(int argc,char **argv) {
  check(argc==3);const char *url=argv[1],*mode=argv[2];uint32_t session=0;
  check(lefony_fill((lefony_rect_t){0,0,320,240,0xffff})==0);
  const char *title="HTTPS Lab: waiting for companion";
  check(lefony_text((lefony_text_t){8,25,0,0xffff,title,(uint32_t)strlen(title)})==0);
  check(lefony_channel_open(&session)==0);
  LefonyChannelInfo info;
  do {check(lefony_channel_info(&info)==0);check(info.state!=LEFONY_CHANNEL_ENDED);lefony_program_sleep(5);} while(info.state!=LEFONY_CHANNEL_CONNECTED);
  int post=!strcmp(mode,"post") || !strcmp(mode,"chunked-post");
  int expected_error=!strcmp(mode,"policy")?1:!strcmp(mode,"tls")?3:!strcmp(mode,"timeout")?5:!strcmp(mode,"cancel")?6:!strcmp(mode,"truncated")?2:0;
  uint32_t expected=post?70017:131073;
  const char *headers="Accept: application/octet-stream\n";
  LefonyHTTPSBegin begin={1,1,post?LEFONY_HTTPS_POST:LEFONY_HTTPS_GET,
    !strcmp(mode,"chunked-post")?LEFONY_HTTPS_UNKNOWN:post?expected:0,
    200000,!strcmp(mode,"timeout")?2000:120000,(uint32_t)strlen(url),(uint32_t)strlen(headers)};
  check(lefony_https_begin(session,&begin)==0);send_metadata(session,LEFONY_HTTPS_URL,url);send_metadata(session,LEFONY_HTTPS_HEADERS,headers);
  uint32_t buffer[112],received=0,header_length=0,header_received=0,uploaded=0;int response=0,cancelled=0;
  FILE *file=NULL;
  for(;;) {
    LefonyChannelRequest result={0};int status=lefony_channel_receive(session,buffer,sizeof(buffer),&result);
    if(status==-6) {lefony_program_sleep(1);continue;}
    if(!strcmp(mode,"disconnect") && status==-LEFONY_CHANNEL_DISCONNECTED) {if(file) fclose(file);unlink("download.part");return 0;}
    check(status==0 && result.length>=4);
    if(result.kind==LEFONY_HTTPS_CREDIT) {
      check(post && result.length==12);LefonyHTTPSCredit credit;memcpy(&credit,buffer,sizeof(credit));
      check(credit.id==1 && credit.offset==uploaded && credit.maximum<=436);
      unsigned bytes=expected-uploaded;if(bytes>credit.maximum) bytes=credit.maximum;
      uint8_t data[436];for(unsigned i=0;i<bytes;i++) data[i]=(uint8_t)((uploaded+i)*13+7);
      do {status=lefony_https_upload(session,1,uploaded,data,bytes,uploaded+bytes==expected);if(status==-6) lefony_program_sleep(1);} while(status==-6);
      check(status==0);uploaded+=bytes;
    } else if(result.kind==LEFONY_HTTPS_RESPONSE) {
      check(!response && result.length==32);LefonyHTTPSResponse start;memcpy(&start,buffer,sizeof(start));
      check(start.schema==1 && start.id==1 && start.status==(post?201u:200u) && !start.flags && !start.reserved);
      check(start.headerBytes<=8192 && (start.responseBytes==expected || start.responseBytes==LEFONY_HTTPS_UNKNOWN));
      header_length=start.headerBytes;response=1;file=fopen("download.part","wb");check(file);
    } else if(result.kind==LEFONY_HTTPS_HEADER) {
      check(response && buffer[0]==1 && buffer[1]==header_received && result.length>8);
      header_received+=result.length-8;check(header_received<=header_length);
    } else if(result.kind==LEFONY_HTTPS_DATA) {
      check(response && header_received==header_length && buffer[0]==1 && buffer[1]==received && result.length>8);
      unsigned bytes=result.length-8;check(received+bytes<=expected);uint8_t *data=(uint8_t *)(buffer+2);
      for(unsigned i=0;i<bytes;i++) check(data[i]==(uint8_t)((received+i)*13+7));
      check(fwrite(data,1,bytes,file)==bytes);received+=bytes;
      if(!strcmp(mode,"cancel") && !cancelled) {check(lefony_https_cancel(session,1)==0);cancelled=1;}
    } else if(result.kind==LEFONY_HTTPS_DONE) {
      check(!expected_error && result.length==16 && buffer[0]==1 && buffer[1]==uploaded && buffer[2]==received && !buffer[3]);
      check(file && received==expected && fflush(file)==0 && fsync(fileno(file))==0);
      check(fclose(file)==0);check(rename("download.part","cache.bin")==0);return 0;
    } else if(result.kind==LEFONY_HTTPS_ERROR) {
      check(result.length==24 && buffer[0]==1 && (int)buffer[1]==expected_error && !buffer[2] && !buffer[5]);
      if(file) {check(fclose(file)==0);check(unlink("download.part")==0);}
      return 0;
    } else check(result.kind==LEFONY_HTTPS_PROGRESS && result.length==16 && buffer[0]==1);
  }
}

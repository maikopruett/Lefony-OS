/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Deliver trailing fragments after ERROR and DONE through a real companion.
 * These deliberate late sends reproduce the host-visible delivery ordering;
 * they do not claim to measure physical USB latency. */
#define _POSIX_C_SOURCE 200809L
#include <lefony/https.h>
#include <lefony/foreground.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#define check(x) do {if (!(x)) lefony_program_exit(__LINE__);} while (0)
#define send(x) do {int status; do {status=(x); if (status==-6) lefony_program_sleep(1);} while (status==-6); check(status==0);} while (0)

static void trailing(uint32_t session, uint32_t id, const char *url) {
  const char header[]="Accept: application/octet-stream\n";
  send(lefony_https_metadata(session,LEFONY_HTTPS_URL,id,0,url,strlen(url)));
  send(lefony_https_metadata(session,LEFONY_HTTPS_HEADERS,id,0,header,sizeof(header)-1));
  send(lefony_https_upload(session,id,0,"x",1,1));
  send(lefony_https_cancel(session,id));
}

int main(int argc, char **argv) {
  check(argc==3 && !strcmp(argv[2],"terminal"));
  const char *url=argv[1];check(strlen(url)<=440);
  uint32_t session=0;check(lefony_channel_open(&session)==0);
  LefonyChannelInfo info;
  do {
    check(lefony_channel_info(&info)==0 && info.state!=LEFONY_CHANNEL_ENDED);
    lefony_program_sleep(5);
  } while (info.state!=LEFONY_CHANNEL_CONNECTED);
  const uint32_t expected=131073;
  for (uint32_t id=1; id<=3; ++id) {
    LefonyHTTPSBegin begin={1,id,LEFONY_HTTPS_GET,0,id==1?32u*1024*1024:200000,
                           120000,(uint32_t)strlen(url),0};
    send(lefony_https_begin(session,&begin));
    /* Request 1 exceeds the companion's grant before any URL is delivered. */
    if (id!=1) send(lefony_https_metadata(session,LEFONY_HTTPS_URL,id,0,url,strlen(url)));
    uint32_t buffer[112],received=0,header_bytes=0,headers_received=0;
    FILE *file=NULL;
    for (;;) {
      LefonyChannelRequest result={0};
      int status=lefony_channel_receive(session,buffer,sizeof(buffer),&result);
      if (status==-6) {lefony_program_sleep(1);continue;}
      check(status==0 && result.length>=4);
      check(result.kind==LEFONY_HTTPS_RESPONSE || buffer[0]==id);
      if (result.kind==LEFONY_HTTPS_ERROR) {
        check(id==1 && result.length==24 && buffer[1]==LEFONY_HTTPS_POLICY);
        check(!buffer[2] && !buffer[3] && !buffer[4] && !buffer[5]);
        break;
      } else if (result.kind==LEFONY_HTTPS_RESPONSE) {
        /* RESPONSE starts with schema, followed by the request ID. */
        check(id!=1 && !file && result.length==32);
        LefonyHTTPSResponse response;memcpy(&response,buffer,sizeof(response));
        check(response.schema==1 && response.id==id && response.status==200);
        check(response.responseBytes==expected && !response.uploadBytes && !response.flags && !response.reserved);
        header_bytes=response.headerBytes;check(header_bytes<=8192);
        file=fopen("download.part","wb");check(file);
      } else if (result.kind==LEFONY_HTTPS_HEADER) {
        check(file && result.length>8 && buffer[1]==headers_received);
        headers_received+=result.length-8;check(headers_received<=header_bytes);
      } else if (result.kind==LEFONY_HTTPS_DATA) {
        check(file && headers_received==header_bytes && result.length>8 && buffer[1]==received);
        uint32_t count=result.length-8;check(received+count<=expected);
        unsigned char *data=(unsigned char *)(buffer+2);
        for (uint32_t i=0;i<count;++i) check(data[i]==(unsigned char)((received+i)*13+7));
        check(fwrite(data,1,count,file)==count);received+=count;
      } else if (result.kind==LEFONY_HTTPS_DONE) {
        check(id!=1 && result.length==16 && !buffer[1] && buffer[2]==expected && !buffer[3]);
        check(file && received==expected && fflush(file)==0 && fsync(fileno(file))==0);
        check(fclose(file)==0 && rename("download.part","cache.bin")==0);
        break;
      } else check(result.kind==LEFONY_HTTPS_PROGRESS && result.length==16);
    }
    /* FIFO delivery makes the next BEGIN follow all four trailing fragments. */
    if (id<3) trailing(session,id,url);
  }
  return 0;
}

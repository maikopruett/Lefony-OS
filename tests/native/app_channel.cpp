// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_channel.h"
#include <cassert>
#include <cstring>
using namespace PrimeG2::AppChannel;
static LefonyChannelRequest request(unsigned operation,unsigned session=0) {
  LefonyChannelRequest r={};r.size=sizeof(r);r.schema=1;r.operation=operation;r.session=session;return r;
}
static LefonyChannelAttach attach(unsigned session) {
  LefonyChannelAttach a={};a.size=sizeof(a);a.schema=1;a.session=session;a.nonce[0]=123456;a.nonce[3]=0xaabbccdd;
  memcpy(a.label,"SDK test",9);return a;
}
static LefonyChannelControl control(const LefonyChannelInfo &info,unsigned sequence=0) {
  LefonyChannelControl c={};c.size=sizeof(c);c.schema=1;c.session=info.session;c.sequence=sequence;memcpy(c.nonce,info.nonce,16);return c;
}
int main() {
  Session s;char id[49]="a",name[81]="First app";uint8_t hash[32]={1},signer[32]={2};
  s.owner(id,name,hash,signer);assert(!s.active() && s.info().packageHash[0]==1);
  auto a=attach(1);assert(!s.attach(a,0));
  auto r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,100) && r.session==1 && r.state==LEFONY_CHANNEL_WAIT_HOST);
  auto open=r;r=request(LEFONY_CHANNEL_OPEN);assert(s.request(r,nullptr,101)==-LEFONY_CHANNEL_AGAIN && !r.session);
  a=attach(open.session);auto bad=a;bad.label[31]='X';assert(!s.attach(bad,102));
  bad=a;bad.nonce[0]=bad.nonce[3]=0;assert(!s.attach(bad,102));
  assert(s.attach(a,103) && s.pairing());assert(s.attach(a,104));
  bad=a;bad.nonce[1]=1;assert(!s.attach(bad,105));
  r=request(LEFONY_CHANNEL_SEND,1);r.kind=10;r.length=r.capacity=3;r.buffer=1;
  auto before=r;assert(s.request(r,(void*)"abc",106)==-LEFONY_CHANNEL_AGAIN && !memcmp(&r,&before,sizeof(r)));
  s.consent(true,107);assert(s.info().state==LEFONY_CHANNEL_CONNECTED);
  for(unsigned i=1;i<=4;i++) {r=before;assert(!s.request(r,(void*)"abc",108) && r.sequence==i && r.transferred==3);}
  r=before;assert(s.request(r,(void*)"abc",109)==-LEFONY_CHANNEL_AGAIN && !memcmp(&r,&before,sizeof(r)));
  LefonyChannelFrame f={},again={};unsigned bytes=99;memset(&f,0x7a,sizeof(f));
  assert(!s.read(2,&f,sizeof(f),&bytes,110) && bytes==99 && f.size==0x7a7a7a7a);
  assert(!s.read(1,&f,66,&bytes,110) && bytes==99 && f.size==0x7a7a7a7a);
  assert(s.read(1,&f,sizeof(f),&bytes,110) && bytes==67 && f.sequence==1 && !memcmp(f.data,"abc",3));
  assert(s.read(1,&again,sizeof(again),&bytes,111) && !memcmp(&f,&again,67));
  auto c=control(s.info(),2);assert(!s.control(0x7c,c,112));
  c.sequence=1;assert(s.control(0x7c,c,113));assert(s.control(0x7c,c,114));assert(s.info().sendQueued==3);
  c.nonce[0]++;assert(!s.control(0x7c,c,114));c.nonce[0]--;
  assert(s.attach(a,115) && s.info().sendQueued==3); // attach retry cannot reset
  f={};f.size=67;f.schema=1;f.session=1;f.sequence=1;f.kind=77;f.length=3;
  memcpy(f.nonce,a.nonce,16);memcpy(f.data,"xyz",3);
  assert(!s.receive(f,66,120));f.reserved[5]=1;assert(!s.receive(f,67,120));f.reserved[5]=0;
  assert(s.receive(f,67,121));assert(s.receive(f,67,122) && s.info().receiveQueued==1);
  f.data[0]='a';assert(!s.receive(f,67,123));f.data[0]='x';
  for(unsigned i=2;i<=4;i++) {f.sequence=i;assert(s.receive(f,67,124));}
  f.sequence=5;assert(!s.receive(f,67,125));assert(s.info().receiveSequence==5);
  char destination[5]="KEEP";r=request(LEFONY_CHANNEL_RECEIVE,1);r.buffer=1;r.capacity=2;before=r;
  assert(s.request(r,destination,126)==-LEFONY_CHANNEL_TOO_SMALL && !memcmp(&r,&before,sizeof(r)) && !strcmp(destination,"KEEP"));
  for(unsigned i=1;i<=4;i++) {r=request(LEFONY_CHANNEL_RECEIVE,1);r.buffer=1;r.capacity=3;
    assert(!s.request(r,destination,127) && r.kind==77 && r.sequence==i && r.length==3 && !memcmp(destination,"xyz",3));}
  assert(s.receive(f,67,128));r=request(LEFONY_CHANNEL_RECEIVE,1);r.buffer=1;r.capacity=3;assert(!s.request(r,destination,129));
  r=request(LEFONY_CHANNEL_RECEIVE,1);before=r;assert(s.request(r,nullptr,129)==-LEFONY_CHANNEL_AGAIN && !memcmp(&r,&before,sizeof(r)));
  c=control(s.info());assert(s.control(0x7d,c,1000));s.poll(5999);assert(s.active());s.poll(6000);
  assert(s.info().state==LEFONY_CHANNEL_ENDED && s.info().error==LEFONY_CHANNEL_TIMEOUT && !s.info().sendQueued);
  assert(!s.receive(f,67,6001));r=request(LEFONY_CHANNEL_SEND,1);r.kind=1;assert(s.request(r,nullptr,6001)==-LEFONY_CHANNEL_TIMEOUT);
  r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,7000) && r.session==2);
  assert(!s.attach(a,7001));a=attach(2);assert(s.attach(a,7002));
  c=control(s.info());assert(s.control(0x7e,c,7003) && !s.pairing());
  r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,8000));a=attach(r.session);assert(s.attach(a,8001));
  s.consent(false,8002);assert(s.info().error==LEFONY_CHANNEL_DENIED);
  r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,9000));a=attach(r.session);assert(s.attach(a,10000));
  assert(s.attach(a,38999));s.consent(true,39000);assert(s.info().error==LEFONY_CHANNEL_TIMEOUT); // no lease extension by reattach
  unsigned old=r.session;s.owner(id,name,hash,signer);r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,40000) && r.session>old);
  a=attach(r.session);assert(s.attach(a,40001));s.consent(true,40002);
  r=request(LEFONY_CHANNEL_SEND,old);r.kind=1;assert(s.request(r,nullptr,40003)==-LEFONY_CHANNEL_STALE);
  s.finish();assert(!s.info().receiveQueued && s.info().error==LEFONY_CHANNEL_DISCONNECTED);
  r=request(LEFONY_CHANNEL_OPEN);assert(!s.request(r,nullptr,50000));s.poll(49999);assert(s.info().error==LEFONY_CHANNEL_TIMEOUT);
  r=request(LEFONY_CHANNEL_OPEN);r.reserved[2]=1;before=r;assert(s.request(r,nullptr,60000)==-LEFONY_CHANNEL_INVALID && !memcmp(&r,&before,sizeof(r)));
}

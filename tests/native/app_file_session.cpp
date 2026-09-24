// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_file_session.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <vector>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
#include "app_storage_fixture.h"
using PrimeG2::AppFiles::Session;
static uint32_t version[3]={1,0,0},privateValue=42;
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete;i++) { assert(v.state()!=State::Failed);v.step(); }
  assert(v.state()==State::Complete);
}
static LefonyFileRequest request(unsigned op,uint32_t handle=0,const char *path=nullptr,uint32_t flags=0) {
  LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.handle=handle;r.flags=flags;
  if(path) { r.path=1;r.pathBytes=strlen(path); }return r;
}
static LefonyFileRequest exchange(Session &s,LefonyFileRequest r,const char *path=nullptr,
                                 const void *input=nullptr,void *output=nullptr,const char *destination=nullptr) {
  assert(s.exchange(r,path,destination,input,nullptr)==1);
  LefonyFileRequest p=request(LEFONY_FILE_POLL);p.token=r.token;
  if(output) { p.buffer=1;p.capacity=2048; }
  for(unsigned i=0;i<200000;i++) {
    s.poll();int n=s.exchange(p,nullptr,nullptr,nullptr,output);
    assert(n==0 || n==1);if(n==0) return p;
  }
  assert(false);return p;
}
static uint32_t open(Session &s,const char *path,uint32_t flags) {
  auto p=exchange(s,request(LEFONY_FILE_OPEN,0,path,flags),path);
  if(p.error) fprintf(stderr,"open %s error %u\n",path,p.error);
  assert(!p.error && p.result>2);return p.result;
}
static void close(Session &s,uint32_t h) { auto p=exchange(s,request(LEFONY_FILE_CLOSE,h));assert(!p.error && !p.result); }
static void sync(Session &s,uint32_t h) { auto p=exchange(s,request(LEFONY_FILE_SYNC,h));assert(!p.error && !p.result); }
static void write(Session &s,uint32_t h,const std::vector<uint8_t> &bytes) {
  for(unsigned at=0;at<bytes.size();) {
    auto r=request(LEFONY_FILE_WRITE,h);r.length=bytes.size()-at;if(r.length>2048) r.length=2048;r.buffer=1;
    auto p=exchange(s,r,nullptr,bytes.data()+at);assert(!p.error && p.result>0);at+=p.result;
  }
}
static std::vector<uint8_t> read(Session &s,uint32_t h) {
  uint8_t buffer[2048];std::vector<uint8_t> result;
  for(;;) {
    auto r=request(LEFONY_FILE_READ,h);r.length=2048;
    auto p=exchange(s,r,nullptr,nullptr,buffer);assert(!p.error && p.result>=0);
    if(!p.result) return result;result.insert(result.end(),buffer,buffer+p.result);
  }
}
static void detach(Session &s) { s.detach();for(unsigned i=0;i<200000 && s.active();i++) s.poll();assert(!s.active() && !s.busy()); }
static unsigned syncCuts(const Flash &base) {
  const std::vector<uint8_t> before={1,2,3},after(8197,0xa5);
  auto save=[&](Flash &flash,bool &synced) {
    auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());
    Session s(*v);assert(s.attach("files",version,0,0,nullptr,0));
    uint32_t h=open(s,"checkpoint",14);write(s,h,after);sync(s,h);synced=true;
    // A successful sync must survive even if later staging is abandoned.
    write(s,h,before);detach(s);
  };
  bool synced=false;Flash full=base;save(full,synced);assert(synced);
  int mutations=full.writes-base.writes;assert(mutations>0);
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash trial=base;trial.cut=trial.writes+cut;trial.torn=torn;
    synced=false;try { save(trial,synced); } catch(PowerCut &) {}
    trial.cut=-1;
    auto recovered=std::make_unique<Volume>(trial.backend());assert(recovered->mount());
    Session s(*recovered);assert(s.attach("files",version,0,0,nullptr,0));
    uint32_t h=open(s,"checkpoint",1);auto bytes=read(s,h);
    assert(bytes==after || (!synced && bytes==before));close(s,h);detach(s);
  }
  return 2*(mutations+1);
}
static void failedSync(const Flash &base) {
  struct FailingFlash:Flash {
    bool reject=false;
    static bool eraseGuard(void *p,uint32_t b) {
      return !static_cast<FailingFlash *>(p)->reject && Flash::erase(p,b);
    }
    static bool programGuard(void *p,uint32_t page,const uint8_t *data) {
      return !static_cast<FailingFlash *>(p)->reject && Flash::program(p,page,data);
    }
  } flash;
  static_cast<Flash &>(flash)=base;
  Backend backend{&flash,Flash::usable,Flash::read,FailingFlash::eraseGuard,FailingFlash::programGuard};
  {
    auto v=std::make_unique<Volume>(backend);assert(v->mount());
    Session s(*v);assert(s.attach("files",version,0,0,nullptr,0));
    uint32_t h=open(s,"checkpoint",14);write(s,h,{9,9,9});flash.reject=true;
    auto result=exchange(s,request(LEFONY_FILE_SYNC,h));
    assert(result.result==-1 && result.error==LEFONY_FILE_IO);
    flash.reject=false;
    assert(exchange(s,request(LEFONY_FILE_CLOSE,h)).error==LEFONY_FILE_BAD_HANDLE);detach(s);
  }
  auto recovered=std::make_unique<Volume>(backend);assert(recovered->mount());
  Session s(*recovered);assert(s.attach("files",version,0,0,nullptr,0));
  auto h=open(s,"checkpoint",1);assert((read(s,h)==std::vector<uint8_t>{1,2,3}));close(s,h);detach(s);
}
static void abortWriterCases(Session &s,Volume &volume) {
  const std::vector<uint8_t> original={2,4,6},saved={8,10};
  uint32_t h=open(s,"abort-target",14);write(s,h,original);close(s,h);
  uint32_t reader=open(s,"abort-target",1);h=open(s,"abort-target",14);write(s,h,saved);
  assert(exchange(s,request(LEFONY_FILE_ABORT,reader)).error==LEFONY_FILE_BAD_HANDLE);
  auto invalid=request(LEFONY_FILE_ABORT,h);invalid.flags=1;
  assert(s.exchange(invalid,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  Volume::FileUsage before{},after{};assert(volume.fileUsage("files",&before));
  auto abort=request(LEFONY_FILE_ABORT,h);assert(s.exchange(abort,nullptr,nullptr,nullptr,nullptr)==1);
  assert(s.exchange(invalid,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_BUSY);
  for(unsigned i=0;i<1000 && s.needsPolling();i++) s.poll();
  auto poll=request(LEFONY_FILE_POLL);poll.token=abort.token;poll.flags=1;
  assert(s.exchange(poll,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  poll.flags=0;assert(s.exchange(poll,nullptr,nullptr,nullptr,nullptr)==0 && !poll.error && !poll.result);
  assert(s.exchange(poll,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  assert(volume.fileUsage("files",&after) && before.generation==after.generation);
  assert(read(s,reader)==original);close(s,reader);
  reader=open(s,"abort-target",1);assert(read(s,reader)==original);close(s,reader);
  assert(exchange(s,request(LEFONY_FILE_CLOSE,h)).error==LEFONY_FILE_BAD_HANDLE);
  uint32_t stale=h;h=open(s,"abort-target",14);write(s,h,saved);sync(s,h);
  reader=open(s,"abort-target",1);write(s,h,original);
  assert(exchange(s,request(LEFONY_FILE_ABORT,stale)).error==LEFONY_FILE_BAD_HANDLE);
  assert(!exchange(s,request(LEFONY_FILE_ABORT,h)).error);
  assert(read(s,reader)==saved);close(s,reader);
  reader=open(s,"abort-target",1);assert(read(s,reader)==saved);close(s,reader);
  h=open(s,"abort-target",14);auto seek=request(LEFONY_FILE_SEEK,h);seek.offset=32u*1024u*1024u;
  assert(!exchange(s,seek).error);auto writeTooMuch=request(LEFONY_FILE_WRITE,h);writeTooMuch.length=1;writeTooMuch.buffer=1;
  assert(exchange(s,writeTooMuch,nullptr,original.data()).error==LEFONY_FILE_QUOTA_EXCEEDED);
  assert(!exchange(s,request(LEFONY_FILE_ABORT,h)).error);
  reader=open(s,"abort-target",1);assert(read(s,reader)==saved);close(s,reader);
  for(unsigned i=0;i<8;i++) {
    h=open(s,"never-published",14);write(s,h,original);
    assert(!exchange(s,request(LEFONY_FILE_ABORT,h)).error);
    assert(exchange(s,request(LEFONY_FILE_OPEN,0,"never-published",1),"never-published").error==LEFONY_FILE_NOT_FOUND);
  }
  h=open(s,"abort-target",14);write(s,h,original);close(s,h);
  reader=open(s,"abort-target",1);assert(read(s,reader)==original);close(s,reader);
  puts("PASS: explicit writer abort, copied completion, stale handles, reader preservation, post-sync rollback, failed writer and fresh retries");
}
int main() {
  Flash flash;auto v=std::make_unique<Volume>(flash.backend());
  std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  assert(v->initialize(package.data(),package.size(),data.data(),data.size(),
    [](const uint8_t *,size_t,char id[49]) { strcpy(id,"files");return true; }));
  uint8_t app[468];memset(app,0x56,sizeof(app));
  for(const char *id:{"files","other"}) { assert(v->begin(id,app,sizeof(app),reinterpret_cast<uint8_t *>(&privateValue),4));finish(*v); }
  Session s(*v);assert(s.attach("files",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  assert(!s.busy() && !s.needsPolling());
  auto missing=exchange(s,request(LEFONY_FILE_OPEN,0,"missing",1),"missing");assert(missing.error==LEFONY_FILE_NOT_FOUND);
  PrimeG2::AppDocumentRoot::Root root;assert(!v->documentRoot("files",&root));
  auto bad=request(LEFONY_FILE_OPEN,0,"../escape",7);assert(s.exchange(bad,"../escape",nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  std::vector<uint8_t> input(2*PrimeG2::AppFileIndex::ChunkBytes+37);
  for(unsigned i=0;i<input.size();i++) input[i]=(i*131u+(i>>8))^0x5d;
  uint32_t writer=open(s,"input",14);write(s,writer,input);close(s,writer);
  uint32_t reader=open(s,"input",1);writer=open(s,"output",15);
  auto stale=request(LEFONY_FILE_READ,writer+100);stale.length=1;
  assert(exchange(s,stale).error==LEFONY_FILE_BAD_HANDLE);
  uint8_t buffer[2048];unsigned consumed=0;
  while(consumed<input.size()) {
    auto r=request(LEFONY_FILE_READ,reader);r.length=2048;
    auto p=exchange(s,r,nullptr,nullptr,buffer);assert(!p.error && p.result>0);
    std::vector<uint8_t> part(buffer,buffer+p.result);write(s,writer,part);consumed+=p.result;
  }
  auto seek=request(LEFONY_FILE_SEEK,writer);seek.offset=7;assert(exchange(s,seek).result==7);
  std::vector<uint8_t> patch(37,0xa7);write(s,writer,patch);close(s,writer);close(s,reader);
  std::copy(patch.begin(),patch.end(),input.begin()+7);
  reader=open(s,"output",1);assert(read(s,reader)==input);close(s,reader);
  // Copy request data before returning to user mode; bad completion buffers may
  // be corrected without replaying the write or losing its result.
  writer=open(s,"scratch",14);uint8_t original[3]={7,8,9};
  auto wr=request(LEFONY_FILE_WRITE,writer);wr.length=3;wr.buffer=1;
  assert(s.exchange(wr,nullptr,nullptr,original,nullptr)==1);memset(original,0,3);
  assert(s.needsPolling());
  for(unsigned i=0;i<1000;i++) s.poll();
  assert(s.busy() && !s.needsPolling()); // Pending app acknowledgement must not spin the OS.
  auto p=request(LEFONY_FILE_POLL);p.token=wr.token;
  assert(s.exchange(p,nullptr,nullptr,nullptr,nullptr)==0 && p.result==3);close(s,writer);
  reader=open(s,"scratch",1);auto rr=request(LEFONY_FILE_READ,reader);rr.length=3;
  assert(s.exchange(rr,nullptr,nullptr,nullptr,nullptr)==1);
  for(unsigned i=0;i<1000;i++) s.poll();
  p=request(LEFONY_FILE_POLL);p.token=rr.token;
  assert(s.exchange(p,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  p.buffer=1;p.capacity=2048;assert(s.exchange(p,nullptr,nullptr,nullptr,buffer)==0 && p.result==3);
  assert(!s.busy() && !s.needsPolling());
  assert(buffer[0]==7 && buffer[1]==8 && buffer[2]==9);close(s,reader);
  // Replacing an existing name keeps old reader contents immutable.
  reader=open(s,"input",1);auto rename=request(LEFONY_FILE_RENAME,0,"output");rename.destination=1;rename.destinationBytes=5;
  assert(!exchange(s,rename,"output",nullptr,nullptr,"input").error);
  auto old=read(s,reader);assert(old.size()==input.size() && old[7]!=0xa7);close(s,reader);
  reader=open(s,"input",1);assert(read(s,reader)==input);close(s,reader);
  // Sync publishes without closing, preserves position/flags and immutable
  // reader snapshots, and does not reuse another request's path.
  writer=open(s,"checkpoint",15);write(s,writer,{1,2,3});sync(s,writer);
  reader=open(s,"checkpoint",1);sync(s,reader);
  uint32_t other=open(s,"scratch",1);close(s,other);
  seek=request(LEFONY_FILE_SEEK,writer);seek.offset=1;assert(exchange(s,seek).result==1);
  write(s,writer,{8});sync(s,writer);sync(s,writer);
  LefonyFileInfo info{};auto stat=exchange(s,request(LEFONY_FILE_STAT,writer),nullptr,nullptr,buffer);
  memcpy(&info,buffer,sizeof(info));assert(!stat.error && info.position==2 && info.bytes==3);
  assert((read(s,reader)==std::vector<uint8_t>{1,2,3}));close(s,reader);
  reader=open(s,"checkpoint",1);assert((read(s,reader)==std::vector<uint8_t>{1,8,3}));close(s,reader);
  write(s,writer,{9});detach(s);
  assert(s.attach("files",version,0,0,nullptr,0));
  reader=open(s,"checkpoint",1);assert((read(s,reader)==std::vector<uint8_t>{1,8,3}));close(s,reader);
  writer=open(s,"checkpoint",19);seek=request(LEFONY_FILE_SEEK,writer);seek.offset=0;
  assert(exchange(s,seek).result==0);sync(s,writer);write(s,writer,{4});sync(s,writer);close(s,writer);
  reader=open(s,"checkpoint",1);assert((read(s,reader)==std::vector<uint8_t>{1,8,3,4}));close(s,reader);
  assert(exchange(s,request(LEFONY_FILE_SYNC,writer)).error==LEFONY_FILE_BAD_HANDLE);
  auto invalid=request(LEFONY_FILE_SYNC,reader);invalid.flags=1;
  assert(s.exchange(invalid,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  writer=open(s,"checkpoint",14);write(s,writer,{1,2,3});close(s,writer);
  unsigned cuts=syncCuts(flash);assert(cuts>20);failedSync(flash);
  writer=open(s,"gap",15);seek=request(LEFONY_FILE_SEEK,writer);seek.offset=9;
  assert(exchange(s,seek).result==9);sync(s,writer);
  stat=exchange(s,request(LEFONY_FILE_STAT,writer),nullptr,nullptr,buffer);
  memcpy(&info,buffer,sizeof(info));assert(!stat.error && info.position==9 && info.bytes==0);
  write(s,writer,{5});sync(s,writer);close(s,writer);
  reader=open(s,"gap",1);std::vector<uint8_t> gap(10);gap[9]=5;assert(read(s,reader)==gap);close(s,reader);
  writer=open(s,"large-sync",15);write(s,writer,input);sync(s,writer);
  reader=open(s,"large-sync",1);
  seek=request(LEFONY_FILE_SEEK,writer);seek.offset=PrimeG2::AppFileIndex::ChunkBytes-3;
  assert(exchange(s,seek).result==static_cast<int>(seek.offset));write(s,writer,patch);sync(s,writer);
  assert(read(s,reader)==input);close(s,reader);close(s,writer);
  auto edited=input;std::copy(patch.begin(),patch.end(),edited.begin()+seek.offset);
  reader=open(s,"large-sync",1);assert(read(s,reader)==edited);close(s,reader);
  abortWriterCases(s,*v);
  writer=open(s,"aborted",14);write(s,writer,patch);detach(s);
  assert(s.attach("other",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  assert(exchange(s,request(LEFONY_FILE_CLOSE,writer)).error==LEFONY_FILE_BAD_HANDLE);detach(s);
  assert(s.attach("files",version,1,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  assert(exchange(s,request(LEFONY_FILE_OPEN,0,"denied",14),"denied").error==LEFONY_FILE_SCHEMA);detach(s);
  assert(s.attach("files",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  assert(exchange(s,request(LEFONY_FILE_OPEN,0,"aborted",1),"aborted").error==LEFONY_FILE_NOT_FOUND);detach(s);
  v.reset();v=std::make_unique<Volume>(flash.backend());assert(v->mount());
  Session cold(*v);assert(cold.attach("files",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  reader=open(cold,"input",1);assert(read(cold,reader)==input);close(cold,reader);detach(cold);
  printf("PASS: sessions, streams, backpatch, copied requests, completion retry, atomic replacement, live sync/append/snapshot/gap/exit, I/O failure and %u sync power-cut cases\n",cuts);
}

// SPDX-License-Identifier: GPL-3.0-or-later
// Reuse the real NAND fixture and snapshot helpers, without running its matrix.
#define main uncached_file_matrix
#include "app_files.cpp"
#undef main
#include "app_file_session.h"
int main() {
  using PrimeG2::AppFileStore::ReadCache;
  Flash flash=baseline();auto cache=std::make_unique<ReadCache>();
  auto v=std::make_unique<Volume>(flash.backend(),cache.get());assert(initialize(*v));
  const uint32_t size=(ReadCache::Slots+1)*Chunk+31;
  assert(v->beginFile("files","data.bin",size));feed(*v,size);
  uint32_t first=v->openSnapshot("files","data.bin"),second=v->openSnapshot("files","data.bin");assert(first && second);
  uint8_t byte=0xab;uint64_t reads=flash.reads;
  assert(v->readCachedSnapshot("files",first,&byte,1)==Pending && byte==0xab && flash.reads==reads);
  assert(v->readSnapshot("files",first,&byte,1)==Pending && byte==0xab);
  for(unsigned i=0;i<10;i++) {assert(v->stepSnapshot("files",first));assert(v->readCachedSnapshot("files",first,&byte,1)==Pending && byte==0xab);}
  Volume::SnapshotInfo info;
  do {assert(v->stepSnapshot("files",first));assert(v->snapshotInfo("files",first,&info));} while(info.state==ReaderState::Verifying);
  assert(v->readCachedSnapshot("files",first,&byte,1)==1 && byte==pattern(0));
  snapshotPattern(*v,first,Chunk+19,1);
  reads=flash.reads;
  for(unsigned i=0;i<50;i++) {snapshotPattern(*v,first,19,1);snapshotPattern(*v,first,Chunk+19,1);}
  assert(flash.reads==reads); // Random revisits return authenticated RAM bytes.
  assert(v->readCachedSnapshot("other",first,&byte,1)==-1);
  assert(v->readCachedSnapshot("files",second,&byte,1)==Pending); // Separate snapshot ownership.
  // LRU eviction never drops an unfinished verification owned by another reader.
  assert(v->readSnapshot("files",second,&byte,1)==Pending);assert(v->stepSnapshot("files",second));
  for(unsigned i=2;i<=ReadCache::Slots;i++) snapshotPattern(*v,first,i*Chunk+17,1);
  do {assert(v->stepSnapshot("files",second));assert(v->snapshotInfo("files",second,&info));} while(info.state==ReaderState::Verifying);
  snapshotPattern(*v,second,0,1);
  assert(v->seekSnapshot("files",first,0));reads=flash.reads;
  assert(v->readCachedSnapshot("files",first,&byte,1)==Pending && flash.reads==reads);
  snapshotPattern(*v,first,0,1);assert(flash.reads>reads);
  // Cached content remains exactly the verified snapshot across a replacement.
  assert(v->beginFile("files","data.bin",73));feed(*v,73,true);
  uint32_t fresh=v->openSnapshot("files","data.bin");assert(fresh);
  snapshotPattern(*v,fresh,0,73,true);snapshotPattern(*v,first,0,73);
  assert(v->closeSnapshot("files",fresh));
  // Errors on an uncached chunk expose nothing and make the reader terminal.
  for(uint32_t block=FirstBlock;block<FirstBlock+BlockCount;block++) flash.bad.insert(block);
  reads=flash.reads;snapshotPattern(*v,first,0,73);assert(flash.reads==reads);
  assert(v->seekSnapshot("files",first,Chunk));byte=0xab;
  int n=v->readSnapshot("files",first,&byte,1);
  while(n==Pending) {assert(v->stepSnapshot("files",first));n=v->readSnapshot("files",first,&byte,1);}
  assert(n==-1 && byte==0xab);flash.bad.clear();assert(v->closeSnapshot("files",first));
  assert(v->closeSnapshot("files",second));
  fresh=v->openSnapshot("files","data.bin");assert(fresh);
  assert(v->readCachedSnapshot("files",fresh,&byte,1)==Pending); // Close discarded prior bytes.
  snapshotPattern(*v,fresh,0,73,true);assert(v->closeSnapshot("files",fresh));
  // Session fast completion uses the ordinary one-shot token and preserves a
  // completion if the caller supplies an undersized output buffer.
  PrimeG2::AppFiles::Session session(*v);uint32_t version[3]={1,0,0},privateValue=42;
  assert(session.attach("files",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  auto req=[](unsigned op) {LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;return r;};
  auto complete=[&](LefonyFileRequest r,void *out,uint32_t capacity,bool immediate=false) {
    auto p=req(LEFONY_FILE_POLL);p.token=r.token;p.buffer=out?1:0;p.capacity=capacity;
    for(unsigned i=0;i<1000;i++) {int rc=session.exchange(p,nullptr,nullptr,nullptr,out);if(!rc) return p;assert(rc==1 && !immediate);session.poll();}
    assert(false);return p;
  };
  auto r=req(LEFONY_FILE_OPEN);r.path=1;r.pathBytes=8;r.flags=LEFONY_FILE_READABLE;
  assert(session.exchange(r,"data.bin",nullptr,nullptr,nullptr)==1);auto p=complete(r,nullptr,0);assert(!p.error);uint32_t handle=p.result;
  r=req(LEFONY_FILE_READ);r.handle=handle;r.length=1;assert(session.exchange(r,nullptr,nullptr,nullptr,nullptr)==1);
  p=complete(r,&byte,1);assert(!p.error && byte==0xa7);
  r=req(LEFONY_FILE_SEEK);r.handle=handle;r.offset=0;reads=flash.reads;assert(session.exchange(r,nullptr,nullptr,nullptr,nullptr)==1);p=complete(r,nullptr,0,true);assert(!p.error);
  r=req(LEFONY_FILE_READ);r.handle=handle;r.length=1;assert(session.exchange(r,nullptr,nullptr,nullptr,nullptr)==1);
  auto shortPoll=req(LEFONY_FILE_POLL);shortPoll.token=r.token;assert(session.exchange(shortPoll,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  p=complete(r,&byte,1,true);assert(!p.error && byte==0xa7 && flash.reads==reads);
  assert(session.exchange(p,nullptr,nullptr,nullptr,&byte)==-LEFONY_FILE_INVALID);
  session.detach();for(unsigned i=0;i<1000 && session.active();i++) session.poll();assert(!session.active());
  // Cold corruption is rejected even after the same cache was used successfully.
  Root root;assert(v->documentRoot("files",&root));v.reset();
  char path[80];snprintf(path,sizeof(path),"objects/files/c%08x.00000001",root.current.data);
  {Raw raw(flash);raw.corrupt(path);}
  v=std::make_unique<Volume>(flash.backend(),cache.get());assert(initialize(*v));fresh=v->openSnapshot("files","data.bin");assert(fresh);byte=0xab;
  assert(snapshotRead(*v,fresh,&byte,1)==-1 && byte==0xab);
  puts("verified cache: bounded fill, RAM hits, LRU, owner isolation, replacement, media faults, close, cold corruption, fast tokens passed");
}

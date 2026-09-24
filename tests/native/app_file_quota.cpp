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
using Root=PrimeG2::AppDocumentRoot::Root;
#include "app_raw_fixture.h"
using PrimeG2::AppFiles::Session;
constexpr uint32_t Limit=32u*1024u*1024u;
static uint32_t version[3]={1,0,0},privateValue=42;
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
static LefonyFileRequest request(unsigned op,const char *path=nullptr,uint32_t handle=0) {
  LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.handle=handle;
  if(path) {r.path=1;r.pathBytes=strlen(path);}return r;
}
static LefonyFileRequest call(Session &s,LefonyFileRequest r,void *out=nullptr,const char *path=nullptr,const void *in=nullptr) {
  assert(s.exchange(r,path,nullptr,in,nullptr)==1);
  auto p=request(LEFONY_FILE_POLL);p.token=r.token;if(out) {p.buffer=1;p.capacity=2048;}
  for(unsigned i=0;i<200000;i++) {s.poll();int rc=s.exchange(p,nullptr,nullptr,nullptr,out);assert(rc==0 || rc==1);if(!rc) return p;}
  assert(false);return p;
}
static uint32_t open(Session &s,const char *path,uint32_t flags) {
  auto r=request(LEFONY_FILE_OPEN,path);r.flags=flags;auto p=call(s,r,nullptr,path);assert(!p.error && p.result>0);return p.result;
}
static void close(Session &s,uint32_t h,uint32_t error=0) {assert(call(s,request(LEFONY_FILE_CLOSE,nullptr,h)).error==error);}
static void seek(Session &s,uint32_t h,uint32_t offset) {
  auto r=request(LEFONY_FILE_SEEK,nullptr,h);r.offset=offset;assert(!call(s,r).error);
}
static LefonyFileRequest write(Session &s,uint32_t h,uint32_t n) {
  uint8_t bytes[2048];memset(bytes,0x37,sizeof(bytes));auto r=request(LEFONY_FILE_WRITE,nullptr,h);r.buffer=1;r.length=n;
  return call(s,r,nullptr,nullptr,bytes);
}
static LefonyFileQuota quota(Session &s) {
  LefonyFileQuota q{};auto p=call(s,request(LEFONY_FILE_QUOTA),&q);assert(!p.error && p.length==sizeof(q));
  assert(q.size==48 && q.schema==1 && q.generation && q.limitBytes==Limit && !q.reserved[0] && !q.reserved[1] && !q.reserved[2]);
  assert(q.projectedBytes<=q.ceilingBytes && q.remainingBytes==q.ceilingBytes-q.projectedBytes);return q;
}
static void detach(Session &s) {s.detach();for(unsigned i=0;i<200000 && s.active();i++) s.poll();assert(!s.active());}
// Encode an authentic older FILE4 root using the lower-level immutable-object
// transaction, before any app-facing quota policy. No fake sizes or missing
// chunks: every seeded byte is hashed and present in the production filesystem.
static void seed(Flash &flash,const char *name,uint32_t bytes) {
  using namespace PrimeG2::AppFileIndex;
  Raw raw(flash);auto docs=std::make_unique<PrimeG2::AppDocumentStore::Store>(&raw.fs);
  Root before;assert(docs->root("files",&before));Root after=before;after.serial++;
  auto index=std::make_unique<Index>();assert(docs->index("files",before.current,index.get()));
  auto &e=index->entry[index->entries++];strcpy(e.name,name);e.kind=File;e.bytes=bytes;e.first=index->extents;
  e.count=(bytes+ChunkBytes-1)/ChunkBytes;std::vector<uint8_t> content(ChunkBytes,0xa7);
  for(uint32_t i=0;i<e.count;i++) {
    auto &x=index->extent[index->extents++];x.generation=after.serial;x.part=i+1;x.type=ChunkObject;
    x.bytes=bytes-i*ChunkBytes;if(x.bytes>ChunkBytes) x.bytes=ChunkBytes;
    PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);
    PrimeG2::NativeAppHash::shaUpdate(&hash,content.data(),x.bytes);PrimeG2::NativeAppHash::shaFinal(&hash,x.hash);
    char path[80]="objects/files/";objectName(x,path+14);lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_EXCL,&cfg));
    assert(lfs_file_write(&raw.fs,&file,content.data(),x.bytes)==static_cast<int>(x.bytes));assert(!lfs_file_close(&raw.fs,&file));
  }
  std::vector<uint8_t> encoded(MaximumBytes);after.format=4;after.previous=before.current;
  after.current.dataKind=PrimeG2::AppDocumentRoot::FileIndex;after.current.data=after.serial;
  assert(encode(*index,after.serial,encoded.data(),encoded.size()));
  after.current.dataBytes=encodedBytes(*index);
  assert(docs->begin("files",before,after,nullptr,encoded.data(),true,false));
  for(unsigned i=0;i<200000 && docs->state()!=PrimeG2::AppDocumentStore::Store::State::Complete;i++) {
    assert(docs->state()!=PrimeG2::AppDocumentStore::Store::State::Failed);docs->step();
  }
  assert(docs->state()==PrimeG2::AppDocumentStore::Store::State::Complete);
}
static uint8_t tail(Volume &v,uint32_t offset) {
  uint32_t h=v.openSnapshot("files","large");assert(h && v.seekSnapshot("files",h,offset));uint8_t byte=0;
  int n;unsigned steps=0;while((n=v.readSnapshot("files",h,&byte,1))==-2) {assert(++steps<100);v.stepSnapshot("files",h);}
  assert(n==1 && v.closeSnapshot("files",h));return byte;
}
int main() {
  Flash base;auto v=std::make_unique<Volume>(base.backend());std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  assert(v->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char id[49]){strcpy(id,"files");return true;}));
  uint8_t app[468]{};
  for(const char *id:{"files","other"}) {assert(v->begin(id,app,sizeof(app),reinterpret_cast<uint8_t *>(&privateValue),4));finish(*v);}
  {Session s(*v);assert(s.attach("files",version,0,0,nullptr,0));int writes=base.writes;auto q=quota(s);
    assert(q.committedBytes==4 && q.remainingBytes==Limit-4 && !q.flags && writes==base.writes);
    Root root;assert(!v->documentRoot("files",&root));detach(s);}
  assert(v->beginCheckpoint("files",reinterpret_cast<uint8_t *>(&privateValue),4,version,0));finish(*v);
  int writes=base.writes;assert(!v->beginFile("files","too-large",Limit));
  assert(v->fileError()==PrimeG2::AppFileStore::QuotaExceeded && base.writes==writes);v.reset();
  Flash full=base;seed(full,"large",Limit-4);
  {auto volume=std::make_unique<Volume>(full.backend());assert(volume->mount());Session s(*volume);assert(s.attach("files",version,0,0,nullptr,0));
    auto q=quota(s);assert(q.committedBytes==Limit && !q.remainingBytes && !q.flags);
    uint32_t h=open(s,"large",3);seek(s,h,Limit-6);auto p=write(s,h,4);assert(!p.error && p.result==2);
    assert(write(s,h,1).error==LEFONY_FILE_QUOTA_EXCEEDED);
    q=quota(s);assert(q.flags==(LEFONY_FILE_QUOTA_WRITER_OPEN|LEFONY_FILE_QUOTA_WRITER_FAILED) && q.projectedBytes==Limit);
    close(s,h,LEFONY_FILE_QUOTA_EXCEEDED);assert(tail(*volume,Limit-5)==0xa7);
    uint32_t reader=open(s,"large",1);seek(s,reader,Limit-5);
    auto read=request(LEFONY_FILE_READ,nullptr,reader);read.length=1;uint8_t byte=0;
    p=call(s,read,&byte);assert(!p.error && p.result==1 && byte==0xa7);close(s,reader);
    h=open(s,"large",3);seek(s,h,Limit-5);assert(!write(s,h,1).error);
    assert(!call(s,request(LEFONY_FILE_SYNC,nullptr,h)).error);assert(!quota(s).remainingBytes);close(s,h);
    assert(tail(*volume,Limit-5)==0x37);
    uint8_t priv[5]{};writes=full.writes;assert(!volume->beginCheckpoint("files",priv,5,nullptr,0));
    assert(volume->fileError()==PrimeG2::AppFileStore::QuotaExceeded && full.writes==writes);
    h=open(s,"large",14);q=quota(s);assert(q.projectedBytes==4 && q.remainingBytes==Limit-4);
    seek(s,h,Limit-4);writes=full.writes;assert(write(s,h,1).error==LEFONY_FILE_QUOTA_EXCEEDED && full.writes==writes);
    close(s,h,LEFONY_FILE_QUOTA_EXCEEDED);assert(quota(s).committedBytes==Limit);
    // Free two private bytes, then actually grow the named file to the limit.
    assert(volume->beginCheckpoint("files",priv,2,nullptr,0));finish(*volume);
    assert(quota(s).remainingBytes==2);h=open(s,"large",18);
    p=write(s,h,4);assert(!p.error && p.result==2 && !quota(s).remainingBytes);
    assert(write(s,h,1).error==LEFONY_FILE_QUOTA_EXCEEDED);close(s,h,LEFONY_FILE_QUOTA_EXCEEDED);
    assert(quota(s).remainingBytes==2);h=open(s,"large",18);assert(write(s,h,2).result==2);
    assert(!call(s,request(LEFONY_FILE_SYNC,nullptr,h)).error);
    assert(quota(s).committedBytes==Limit && !quota(s).remainingBytes);close(s,h);
    detach(s);assert(s.attach("other",version,0,0,nullptr,0));q=quota(s);assert(q.committedBytes==4 && q.remainingBytes==Limit-4);detach(s);
  }
  // Pre-policy oversized roots get no growth allowance, and retain their exact
  // bytes through cold mount, in-place edits, aborted truncation and later shrink.
  Flash old=base;seed(old,"large",Limit+17);
  {auto volume=std::make_unique<Volume>(old.backend());assert(volume->mount());Session s(*volume);assert(s.attach("files",version,0,0,nullptr,0));
    auto q=quota(s);assert(q.committedBytes==Limit+21 && q.ceilingBytes==Limit+21 && !q.remainingBytes && q.flags==LEFONY_FILE_QUOTA_OVER_LIMIT);
    assert(tail(*volume,Limit+16)==0xa7);uint32_t h=open(s,"large",18);
    assert(write(s,h,1).error==LEFONY_FILE_QUOTA_EXCEEDED);close(s,h,LEFONY_FILE_QUOTA_EXCEEDED);
    h=open(s,"large",3);seek(s,h,Limit+16);assert(!write(s,h,1).error);close(s,h);assert(tail(*volume,Limit+16)==0x37);
    h=open(s,"large",14);assert(quota(s).remainingBytes==Limit+17);assert(!write(s,h,9).error);
    assert(!call(s,request(LEFONY_FILE_SYNC,nullptr,h)).error);q=quota(s);assert(q.committedBytes==13 && q.ceilingBytes==Limit && !(q.flags&LEFONY_FILE_QUOTA_OVER_LIMIT));
    close(s,h);detach(s);
  }
  {auto volume=std::make_unique<Volume>(old.backend());assert(volume->mount());Session s(*volume);assert(s.attach("files",version,1,0,nullptr,0));
    auto q=quota(s);assert(q.committedBytes==13 && !q.flags);detach(s);}
  puts("PASS: exact quota boundary, private-byte accounting, partial write and aborted replacement, live sync, sparse-gap refusal, app isolation, older oversized FILE4 roots, cold edits/shrink and schema-mismatch inspection");
}

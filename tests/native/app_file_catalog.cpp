// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_file_session.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
#include "app_storage_fixture.h"
using PrimeG2::AppFiles::Session;
static uint32_t version[3]={1,0,0},privateValue=42;
static LefonyFileRequest request(unsigned op,const char *path=nullptr,uint32_t handle=0) {
  LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.handle=handle;
  if(path && *path) { r.path=1;r.pathBytes=strlen(path); }return r;
}
static LefonyFileRequest call(Session &s,LefonyFileRequest r,void *output=nullptr,const char *path=nullptr,const void *input=nullptr) {
  assert(s.exchange(r,path,nullptr,input,nullptr)==1);
  LefonyFileRequest p=request(LEFONY_FILE_POLL);p.token=r.token;
  if(output) { p.buffer=1;p.capacity=2048; }
  for(unsigned i=0;i<200000;i++) { s.poll();int result=s.exchange(p,nullptr,nullptr,nullptr,output);
    assert(result==0 || result==1);if(!result) return p; }
  assert(false);return p;
}
static uint32_t open(Session &s,const char *path,uint32_t flags=14) {
  auto r=request(LEFONY_FILE_OPEN,path);r.flags=flags;
  auto p=call(s,r,nullptr,path);assert(!p.error && p.result>2);return p.result;
}
static void write(Session &s,uint32_t h,unsigned size) {
  std::vector<uint8_t> content(size,0xa7);auto r=request(LEFONY_FILE_WRITE,nullptr,h);
  r.length=size;r.buffer=1;auto p=call(s,r,nullptr,nullptr,content.data());
  assert(!p.error && p.result==static_cast<int>(size));
}
static void close(Session &s,uint32_t h) { auto p=call(s,request(LEFONY_FILE_CLOSE,nullptr,h));assert(!p.error); }
static void mkdir(Session &s,const char *path) { auto p=call(s,request(LEFONY_FILE_MKDIR,path),nullptr,path);assert(!p.error); }
static LefonyDirectoryPage list(Session &s,const char *path="",uint32_t offset=0,uint32_t generation=0) {
  LefonyDirectoryPage page{};auto r=request(LEFONY_FILE_LIST,path);r.offset=offset;r.flags=generation;
  auto p=call(s,r,&page,path);assert(!p.error && !p.result && p.length==sizeof(page));
  assert(page.size==sizeof(page) && page.schema==1 && page.generation && !page.reserved && page.count<=16);
  const LefonyDirectoryEntry empty{};
  for(unsigned i=page.count;i<16;i++) assert(!memcmp(&page.entries[i],&empty,sizeof(empty)));
  return page;
}
static LefonyFileSpace space(Session &s) {
  LefonyFileSpace info{};auto p=call(s,request(LEFONY_FILE_SPACE),&info);
  assert(!p.error && !p.result && p.length==sizeof(info));
  assert(info.size==sizeof(info) && info.schema==1 && info.generation);
  assert(info.capacityBytes+info.reservedBytes==BlockCount*BlockBytes);
  assert(info.availableBytes==(info.capacityBytes>info.allocatedBytes?info.capacityBytes-info.allocatedBytes:0));
  return info;
}
using Names=std::map<std::string,std::pair<uint32_t,uint32_t>>;
static Names all(Session &s,const char *path="") {
  Names names;uint32_t offset=0,generation=0;
  do {
    auto page=list(s,path,offset,generation);generation=page.generation;
    assert(!page.next || page.next>offset);offset=page.next;
    for(unsigned i=0;i<page.count;i++) {
      auto &e=page.entries[i];assert(memchr(e.path,0,sizeof(e.path)));
      assert(names.emplace(e.path,std::make_pair(e.kind,e.bytes)).second);
    }
  } while(offset);
  return names;
}
static void detach(Session &s) { s.detach();for(unsigned i=0;i<200000 && s.active();i++) s.poll();assert(!s.active()); }
int main() {
  Flash flash;auto v=std::make_unique<Volume>(flash.backend());
  std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  assert(v->initialize(package.data(),package.size(),data.data(),data.size(),
    [](const uint8_t *,size_t,char id[49]) { strcpy(id,"files");return true; }));
  uint8_t app[468];memset(app,0x56,sizeof(app));
  for(const char *id:{"files","other"}) {
    assert(v->begin(id,app,sizeof(app),reinterpret_cast<uint8_t *>(&privateValue),4));
    for(unsigned i=0;i<200000 && v->state()!=State::Complete;i++) {assert(v->state()!=State::Failed);v->step();}
    assert(v->state()==State::Complete);
  }
  Session s(*v);assert(s.attach("files",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  int writes=flash.writes;auto first=list(s);auto usage=space(s);
  assert(first.count==0 && first.next==0 && !usage.fileBytes && !usage.files && !usage.directories);
  assert(usage.privateBytes==4 && usage.packageBytes==sizeof(app) && !usage.flags && !usage.writerBytes);
  PrimeG2::AppDocumentRoot::Root root;assert(!v->documentRoot("files",&root) && writes==flash.writes);
  Names expected;uint32_t bytes=0;
  for(unsigned i=0;i<25;i++) {
    char name[16];snprintf(name,sizeof(name),"file%02u",i);auto h=open(s,name);write(s,h,i*7);close(s,h);
    expected[name]={1,i*7};bytes+=i*7;
  }
  mkdir(s,"notes");mkdir(s,"notes/sub");mkdir(s,"noteworthy");
  expected["notes"]={2,0};expected["noteworthy"]={2,0};
  for(const char *name:{"notes/a","notes/sub/deep","noteworthy/b"}) {
    auto h=open(s,name);write(s,h,17);close(s,h);bytes+=17;
  }
  writes=flash.writes;assert(all(s)==expected);
  assert((all(s,"notes")==Names{{"notes/a",{1,17}},{"notes/sub",{2,0}}}));
  assert((all(s,"notes/sub")==Names{{"notes/sub/deep",{1,17}}}));
  usage=space(s);assert(usage.fileBytes==bytes && usage.files==28 && usage.directories==3 && usage.privateBytes==4);
  assert(usage.extents==28 && writes==flash.writes);
  auto page=list(s);assert(page.count==16 && page.next);
  uint32_t writer=open(s,"pending");write(s,writer,21);
  usage=space(s);assert(usage.flags==LEFONY_FILE_SPACE_WRITER_OPEN && usage.writerBytes==21 &&
    !usage.writerCommittedBytes && usage.fileBytes==bytes && usage.generation==page.generation);
  assert(list(s,"",page.next,page.generation).generation==page.generation);
  close(s,writer);auto stale=request(LEFONY_FILE_LIST);stale.offset=page.next;stale.flags=page.generation;
  LefonyDirectoryPage failed;memset(&failed,0xa5,sizeof(failed));
  auto p=call(s,stale,&failed);assert(p.error==LEFONY_FILE_CHANGED && p.length==0 && failed.size==0xa5a5a5a5);
  auto invalid=request(LEFONY_FILE_LIST);invalid.offset=1;
  assert(s.exchange(invalid,nullptr,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  for(const char *name:{"../escape","/absolute","notes/","a//b"}) {
    invalid=request(LEFONY_FILE_LIST,name);assert(s.exchange(invalid,name,nullptr,nullptr,nullptr)==-LEFONY_FILE_INVALID);
  }
  p=call(s,request(LEFONY_FILE_LIST,"file00"),&failed,"file00");assert(p.error==LEFONY_FILE_NOT_DIRECTORY);
  p=call(s,request(LEFONY_FILE_LIST,"missing"),&failed,"missing");assert(p.error==LEFONY_FILE_NOT_FOUND);
  invalid=request(LEFONY_FILE_LIST);invalid.offset=0xffffffffu;invalid.flags=space(s).generation;
  assert(call(s,invalid,&failed).error==LEFONY_FILE_INVALID);
  writer=open(s,"file01");write(s,writer,19);usage=space(s);
  assert(usage.writerBytes==19 && usage.writerCommittedBytes==7 && usage.fileBytes==bytes+21);
  // Failed poll validation retains this exact page despite later caller edits.
  auto pending=request(LEFONY_FILE_LIST);assert(s.exchange(pending,nullptr,nullptr,nullptr,nullptr)==1);
  s.poll();auto poll=request(LEFONY_FILE_POLL);poll.token=pending.token;poll.capacity=4;poll.buffer=1;
  assert(s.exchange(poll,nullptr,nullptr,nullptr,&failed)==-LEFONY_FILE_INVALID);
  poll.capacity=sizeof(failed);assert(s.exchange(poll,nullptr,nullptr,nullptr,&failed)==0);
  assert(failed.count==16 && failed.entries[1].bytes==7);detach(s);
  assert(s.attach("other",version,0,0,reinterpret_cast<uint8_t *>(&privateValue),4));
  assert(all(s).empty() && !space(s).fileBytes);detach(s);
  v.reset();v=std::make_unique<Volume>(flash.backend());assert(v->mount());
  Session cold(*v);assert(cold.attach("files",version,1,0,nullptr,0)); // Read-only schema mismatch remains inspectable.
  expected["pending"]={1,21};assert(all(cold)==expected && space(cold).fileBytes==bytes+21);detach(cold);
  puts("PASS: legacy read-only inspection, paged/nested listing, committed/staged/shared usage, changed-root rejection, invalid requests, completion retry, app isolation and cold/schema-mismatch inspection");
}

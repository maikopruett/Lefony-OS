// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_root_record.h"
#include "app_storage.h"
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
#include "app_key_fault_fixture.h"
namespace R=PrimeG2::AppRootRecord;
struct Media:KeyFlash {std::set<uint32_t> unreadable;unsigned failures=0;};
struct Mount:Mounted {
  explicit Mount(Media &f):Mounted(f) {
    c.read=[](const lfs_config *cfg,lfs_block_t block,lfs_off_t off,void *out,lfs_size_t size) {
      auto &flash=*static_cast<Media *>(static_cast<KeyFlash *>(cfg->context));
      for(unsigned i=0;i<size;i+=PageBytes) {
        unsigned page=(FirstBlock+2+block)*PagesPerBlock+(off+i)/PageBytes;
        if(flash.unreadable.count(page)) {memset(static_cast<uint8_t *>(out)+i,0xa5,PageBytes/2);flash.failures++;return int(LFS_ERR_IO);}
        if(!KeyFlash::read(&flash,page,static_cast<uint8_t *>(out)+i))return int(LFS_ERR_IO);
      }
      return 0;
    };
  }
};
static std::array<uint8_t,240> bytes(const Root &root) {
  std::array<uint8_t,240> result;assert(PrimeG2::AppDocumentRoot::encode(root,result.data()));return result;
}
static bool same(const Root &a,const Root &b) {return bytes(a)==bytes(b);}
static void legacy(lfs_t &fs,const char *path,const Root &root,void *cache) {
  lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=cache;
  assert(!lfs_file_opencfg(&fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC,&cfg));
  auto wire=bytes(root);assert(lfs_file_write(&fs,&file,wire.data(),wire.size())==int(wire.size()));assert(!lfs_file_close(&fs,&file));
  int rc=lfs_removeattr(&fs,path,R::Attribute);assert(!rc || rc==LFS_ERR_NOATTR);
}
static bool publish(Mount &raw,const char *id,const Root &root) {
  if(!R::stage(&raw.fs,"apps/.root-pending",id,root,raw.cache))return false;
  R::Info info;if(R::read(&raw.fs,"apps/.root-pending",id,raw.cache,&info)!=R::Result::Ok || info.copies!=R::Copies::Both || !same(root,info.root))return false;
  char path[64];snprintf(path,sizeof(path),"apps/%s.app",id);
  return !lfs_rename(&raw.fs,"apps/.root-pending",path);
}
static void done(Volume &v) {
  for(unsigned i=0;i<10000 && v.state()!=State::Complete;i++)v.step();assert(v.state()==State::Complete);
}
static uint32_t page(Media &f) {
  Mount raw(f);lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,"apps/document.app",LFS_O_RDONLY,&cfg));assert(!(file.flags&LFS_F_INLINE));
  unsigned result=(FirstBlock+2+file.ctz.head)*PagesPerBlock;assert(!lfs_file_close(&raw.fs,&file));return result;
}
int main() {
  Media base;Root before;
  {auto v=std::make_unique<Volume>(base.backend());std::vector<uint8_t> p(MaximumPackage),d(MaximumData);
    assert(v->initialize(p.data(),p.size(),d.data(),d.size(),[](const uint8_t *,size_t,char id[49]) {strcpy(id,"unused");return true;}));
    memset(p.data(),0x42,468);memset(d.data(),0x37,123);assert(v->begin("document",p.data(),468,d.data(),123));done(*v);
    uint32_t version[3]={1,0,0};assert(v->beginCheckpoint("document",d.data(),123,version,0));done(*v);assert(v->documentRoot("document",&before));
  }
  // Keep the conversion input genuinely historical after production begins
  // writing replicated records on every successful document commit.
  {Mount raw(base);legacy(raw.fs,"apps/document.app",before,raw.cache);}
  Root after=before;after.serial++;after.highVersion[0]=99;
  unsigned cuts=0,mediaCases=0;
  Media sealed=base;{Mount raw(sealed);assert(publish(raw,"document",after));}
  for(bool conversion:{true,false}) {
    Media initial=conversion?base:sealed;Root old=conversion?before:after,next=old;next.serial++;next.highVersion[1]=17;
    Media completed=initial;{Mount raw(completed);assert(publish(raw,"document",next));}
    unsigned writes=completed.writes-initial.writes;assert(writes>0);
    for(bool torn:{false,true})for(unsigned cut=0;cut<=writes;cut++) {
      Media trial=initial;trial.cut=trial.writes+cut;trial.torn=torn;
      try {Mount raw(trial);publish(raw,"document",next);}catch(PowerCut &) {}
      trial.reboot();Mount raw(trial);R::Info result;
      assert(R::read(&raw.fs,"apps/document.app","document",raw.cache,&result)==R::Result::Ok);
      assert(same(result.root,old) || same(result.root,next));
      assert(result.copies==(conversion && same(result.root,old)?R::Copies::Legacy:R::Copies::Both));cuts++;
    }
  }
  unsigned primary=page(sealed);
  for(unsigned mode=0;mode<11;mode++) {
    Media trial=sealed;
    if(mode==1 || mode==9)trial.unreadable.insert(primary);
    if(mode==2 || mode==10)trial.pages.at(primary)[81]^=1;
    if(mode==7) {
      auto &wire=trial.pages.at(primary);wire[8]=6;PrimeG2::NativeAppHash::sha256(wire.data(),R::Bytes-32,wire.data()+R::Bytes-32);
    }
    Mount raw(trial);
    if(mode==4)assert(!lfs_removeattr(&raw.fs,"apps/document.app",R::Attribute));
    if(mode==3 || mode==5 || mode==6 || mode==8 || mode==9 || mode==10) {
      uint8_t wire[R::Bytes];Root altered=after;if(mode==5)altered.serial++;
      assert(R::encode(mode==6?"other":"document",altered,wire));
      if(mode==3 || mode==9 || mode==10)wire[81]^=1;
      if(mode==8) {wire[8]=6;PrimeG2::NativeAppHash::sha256(wire,R::Bytes-32,wire+R::Bytes-32);}
      assert(!lfs_setattr(&raw.fs,"apps/document.app",R::Attribute,wire,R::Bytes));
    }
    R::Info result;result.root=before;auto expected=mode==5?R::Result::Conflict:mode==6?R::Result::WrongApp:
      (mode==7 || mode==8)?R::Result::Unsupported:mode==9?R::Result::IO:mode==10?R::Result::Invalid:R::Result::Ok;
    auto savedPages=trial.pages;int writes=trial.writes;
    assert(R::read(&raw.fs,"apps/document.app","document",raw.cache,&result)==expected);
    assert(trial.pages==savedPages && trial.writes==writes);
    if(expected==R::Result::Ok) {
      assert(same(result.root,after) && result.root.highVersion[0]==99);
      assert(result.copies==(mode==1 || mode==2?R::Copies::Attribute:mode==3 || mode==4?R::Copies::Payload:R::Copies::Both));
    } else assert(same(result.root,before));
    if(mode==1)assert(trial.failures);mediaCases++;
  }
  printf("{\"status\":\"passed\",\"interruption_cases\":%u,\"media_cases\":%u,\"allocation\":[",cuts,mediaCases);
  bool first=true;
  for(unsigned count:{1u,8u,32u,64u})for(bool protect:{false,true}) {
    Media trial=base;uint64_t programmed=trial.programmed;int writes=trial.writes;Mount raw(trial);
    int initial=lfs_fs_size(&raw.fs);assert(initial>0);
    for(unsigned i=0;i<count;i++) {
      char id[49],path[64];snprintf(id,sizeof(id),"root-%u",i);snprintf(path,sizeof(path),"apps/%s.app",id);
      if(protect)assert(publish(raw,id,after));else legacy(raw.fs,path,after,raw.cache);
    }
    int allocated=lfs_fs_size(&raw.fs);assert(allocated>=initial);
    auto added=uint32_t(allocated-initial)*BlockBytes;
    printf("%s{\"roots\":%u,\"protected\":%s,\"allocated_bytes\":%u,\"programmed_bytes\":%llu,\"erase_program_calls\":%d}",
      first?"":",",count,protect?"true":"false",added,static_cast<unsigned long long>(trial.programmed-programmed),trial.writes-writes);first=false;
  }
  puts("]}");
}

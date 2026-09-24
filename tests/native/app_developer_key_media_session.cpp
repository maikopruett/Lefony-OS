// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_developer_key_session.h"
#include "update_trust_root.h"
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
namespace K=PrimeG2::AppDeveloperKeys;
struct Media:Flash {
  std::set<uint32_t> unreadable;unsigned failures=0;
  static bool read(void *context,uint32_t page,uint8_t *out) {
    auto &f=*static_cast<Media *>(context);
    if(f.unreadable.count(page)) {memset(out,0xa5,PageBytes/2);f.failures++;return false;}
    return Flash::read(context,page,out);
  }
  Backend backend() {return {this,usable,read,erase,program};}
};
static std::vector<uint8_t> contents(Flash &f,const char *path) {
  Raw raw(f);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&config));
  int size=lfs_file_size(&raw.fs,&file);assert(size>=0);std::vector<uint8_t> out(size);
  assert(lfs_file_read(&raw.fs,&file,out.data(),size)==size && !lfs_file_close(&raw.fs,&file));return out;
}
static K::Request request(unsigned nonce,K::Operation operation,unsigned key=4,unsigned serial=0) {
  K::Request r{};r.size=sizeof(r);r.schema=1;r.operation=operation;r.serial=serial;memcpy(r.nonce,&nonce,4);
  if(operation!=K::Operation::BackupUnreadable) {
    uint8_t modulus[256];memcpy(modulus,PrimeG2UpdateModulus,256);modulus[7]^=key;
    assert(K::fingerprint(modulus,r.id));
    if(operation!=K::Operation::Revoke) {memcpy(r.modulus,modulus,256);strcpy(r.label,"Recovered");}
  }
  return r;
}
static void poll(K::Controller &c) {
  for(unsigned i=0;i<200 && c.needsPolling();i++) c.poll(10+i);
  assert(!c.needsPolling());
}
static void start(K::Controller &c,const K::Request &r) {
  assert(c.request(r,0));c.acknowledge();poll(c);
}
static void approve(K::Controller &c) {
  assert(c.needsPresentation() && !c.approve(300) && c.present());
  c.observeKeyboard(0);c.observeKeyboard(uint64_t(1)<<56);assert(!c.approve(300));
  c.rendered();assert(!c.approve(300)); // A held key predating the rendered screen is insufficient.
  c.observeKeyboard(0);c.observeKeyboard(2|(uint64_t(1)<<56));assert(!c.approve(300));
  c.observeKeyboard(uint64_t(1)<<56);assert(c.approve(300));
}
static K::UnreadableInfo backup(K::Controller &c,Media &flash) {
  int writes=flash.writes;auto r=request(10,K::Operation::BackupUnreadable);
  assert(K::Controller::valid(r));
  for(unsigned offset:{0u,4u,12u,32u,64u,320u,352u}) {
    auto bad=r;reinterpret_cast<uint8_t *>(&bad)[offset]^=128;assert(!K::Controller::valid(bad));
  }
  start(c,r);assert(c.status().state==K::State::Complete && !c.needsPresentation() && !c.present());
  if(c.table() || c.status().registry!=4 || !flash.failures || flash.writes!=writes)
    fprintf(stderr,"backup table=%d registry=%u failures=%u writes=%d/%d\n",bool(c.table()),c.status().registry,flash.failures,flash.writes,writes);
  assert(!c.table() && c.status().registry==4 && flash.failures && flash.writes==writes);
  K::UnreadableInfo info;assert(c.unreadableInfo(&info) && info.originalBytes==K::WireBytes);
  assert(info.readableBytes==704 && info.unreadableChunks==4 && info.sequence==c.status().sequence && !memcmp(info.nonce,r.nonce,16));
  std::vector<uint8_t> bytes(info.bytes);for(unsigned offset=0;offset<info.bytes;) {
    unsigned n=info.bytes-offset;if(n>511)n=511;
    assert(c.unreadableBytes(offset,bytes.data()+offset,n)==int(n));offset+=n;
  }
  uint8_t hash[32];PrimeG2::NativeAppHash::sha256(bytes.data(),bytes.size(),hash);assert(!memcmp(hash,info.hash,32));
  assert(flash.writes==writes && c.request(r,0) && c.status().state==K::State::Complete);
  assert(!c.unreadableInfo(nullptr) && c.unreadableBytes(info.bytes,bytes.data(),1)<0);
  return info;
}
int main() {
  Media base;
  {auto v=std::make_unique<Volume>(base.backend());std::vector<uint8_t> p(MaximumPackage),d(MaximumData);
    assert(v->initialize(p.data(),p.size(),d.data(),d.size(),[](const uint8_t *,size_t,char id[49]) {strcpy(id,"unused");return true;}));
    memset(p.data(),0x42,468);memset(d.data(),0x67,123);assert(v->begin("unrelated",p.data(),468,d.data(),123));
    for(unsigned i=0;i<10000 && v->state()!=State::Complete;i++)v->step();assert(v->state()==State::Complete);
    K::Controller c(*v);c.initialize();
    for(unsigned key:{4u,8u}) {start(c,request(key,K::Operation::Enroll,key,key==4?0:1));approve(c);poll(c);assert(c.status().state==K::State::Complete);c.dismiss();}
    start(c,request(9,K::Operation::Revoke,8,2));approve(c);poll(c);assert(c.status().serial==3);c.dismiss();
  }
  uint32_t page,metadata[2];
  {Raw raw(base);lfs_file_t f{};lfs_file_config cfg{};cfg.buffer=raw.cache;
    assert(!lfs_file_opencfg(&raw.fs,&f,K::Store::Path,LFS_O_RDONLY,&cfg));
    assert(!(f.flags&LFS_F_INLINE) && f.ctz.size==K::WireBytes);page=(FirstBlock+2+f.ctz.head)*PagesPerBlock;
    for(unsigned i=0;i<2;i++)metadata[i]=FirstBlock+2+f.m.pair[i];
    assert(!lfs_file_close(&raw.fs,&f));
  }
  auto app=contents(base,"apps/unrelated.app"),original=contents(base,K::Store::Path);
  unsigned cases=0,cancellations=0;
  for(unsigned mode=0;mode<9;mode++) {
    Media flash=base;auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());K::Controller c(*v);c.initialize();
    assert(c.status().registry==2 && c.status().serial==3);flash.unreadable.insert(page);
    int writes=flash.writes;auto info=backup(c,flash);
    auto r=request(11,K::Operation::RepairUnreadable,16);memcpy(r.reserved,info.hash,32);
    if(mode==1)r.reserved[0]^=1; // Changed proposal before the UI.
    if(mode==2) {memcpy(r.modulus,PrimeG2UpdateModulus,256);assert(K::fingerprint(r.modulus,r.id));}
    start(c,r);
    if(mode==1 || mode==2) {
      assert(c.status().state==K::State::Failed && c.status().error==(mode==1?K::Error::Stale:K::Error::ProtectedKey));
      assert(!c.needsPresentation());
    } else {
      assert(c.status().state==K::State::AwaitUser && flash.writes==writes);
      assert(!c.unreadableInfo(&info));
      if(mode==3)c.disconnect();
      else if(mode==4)c.deny();
      else if(mode==5)c.poll(120000);
      else {
        if(mode==6) {flash.unreadable.clear();flash.unreadable.insert(page+1);}
        if(mode==7)flash.unreadable.clear();
        if(mode==8)flash.pages.at(page+1)[31]^=1; // A formerly readable fragment changed during consent.
        approve(c);assert(flash.writes==writes);poll(c);
        if(mode==0) {
          assert(c.status().state==K::State::Complete && c.status().serial==1 && c.status().count==1);
          assert(c.table()->find(r.id,K::Purpose::Execute));
          for(unsigned key:{4u,8u}) {auto old=request(1,K::Operation::Enroll,key);assert(!c.table()->find(old.id,K::Purpose::Inspect));}
        } else assert(c.status().state==K::State::Failed && c.status().error==(mode==7?K::Error::Readable:K::Error::Stale));
      }
    }
    if(mode!=0)assert(flash.writes==writes);
    c.dismiss();assert(c.request(r,0) && !c.busy()); // Exact replay never creates fresh authority.
    assert(contents(flash,"apps/unrelated.app")==app);
    if(mode!=0 && mode!=8)assert(contents(flash,K::Store::Path)==original);
    cases++;
  }
  for(bool afterApproval:{false,true})for(unsigned stop=0;stop<10;stop++) {
    Media flash=base;auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());K::Controller c(*v);c.initialize();flash.unreadable.insert(page);
    int writes=flash.writes;auto info=backup(c,flash);
    auto r=request(11,afterApproval?K::Operation::RepairUnreadable:K::Operation::BackupUnreadable,16);
    if(afterApproval) {memcpy(r.reserved,info.hash,32);start(c,r);approve(c);}
    else {assert(c.request(r,0));c.acknowledge();}
    for(unsigned i=0;i<stop;i++)c.poll(400+i);
    K::Control cancel{32,1,c.status().sequence,0,{}};memcpy(cancel.nonce,r.nonce,16);
    auto bad=cancel;bad.nonce[0]^=1;assert(!c.cancel(bad));assert(c.cancel(cancel));
    assert(c.status().state==K::State::Cancelled && flash.writes==writes && flash.pages==base.pages);cancellations++;
  }
  for(unsigned mode=0;mode<4;mode++) {
    Media flash=base;
    if(mode==1) {Raw raw(flash);raw.corrupt(K::Store::Path);}
    if(mode==2) {Raw raw(flash);raw.remove(K::Store::Path);}
    auto before=flash.pages;int writes=flash.writes;auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());K::Controller c(*v);c.initialize();
    if(mode==3)for(unsigned block:metadata)for(unsigned i=0;i<PagesPerBlock;i++)flash.unreadable.insert(block*PagesPerBlock+i);
    start(c,request(10,K::Operation::BackupUnreadable));
    assert(c.status().state==K::State::Failed && c.status().error==(mode==3?K::Error::Io:mode==2?K::Error::Missing:K::Error::Readable));
    assert(!c.needsPresentation() && flash.pages==before && flash.writes==writes);cases++;
  }
  printf("{\"cases\":%u,\"precommit_cancellations\":%u}\n",cases,cancellations);
}

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_developer_keys.h"
#include "native_app_signature.h"
#include "app_storage.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
using namespace PrimeG2::AppStorage;
using Page=std::array<uint8_t,PageBytes>;
#include "app_storage_fixture.h"
using Root=PrimeG2::AppDocumentRoot::Root;
#include "app_raw_fixture.h"
namespace Keys=PrimeG2::AppDeveloperKeys;
using Keys::Table;
using Keys::Result;
using KeyStore=Keys::Store;

// Preserve the production NAND geometry/program-once fixture. A power cut
// makes every later callback fail, including destructor cleanup during unwind.
struct KeyFlash:Flash {
  bool offline=false;
  int reads=0,readFault=-1;
  static bool read(void *p,uint32_t page,uint8_t *out) {
    auto &f=*static_cast<KeyFlash *>(p);
    if(f.offline) return false;
    if(f.reads++==f.readFault) return false;
    return Flash::read(p,page,out);
  }
  static bool program(void *p,uint32_t page,const uint8_t *in) {
    auto &f=*static_cast<KeyFlash *>(p);if(f.offline) return false;
    try { return Flash::program(p,page,in); } catch(PowerCut &) { f.offline=true;throw; }
  }
  static bool erase(void *p,uint32_t block) {
    auto &f=*static_cast<KeyFlash *>(p);if(f.offline) return false;
    try { return Flash::erase(p,block); } catch(PowerCut &) { f.offline=true;throw; }
  }
  Backend backend() { return {this,usable,read,erase,program}; }
  void reboot() { offline=false;cut=-1;readFault=-1; }
};
struct Mounted:Raw {
  explicit Mounted(KeyFlash &flash):Raw(flash) {
    c.context=&flash;
    c.read=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,void *out,lfs_size_t n) {
      assert(off%PageBytes==0 && n%PageBytes==0 && off+n<=BlockBytes);
      for(unsigned i=0;i<n;i+=PageBytes) if(!KeyFlash::read(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,
          static_cast<uint8_t *>(out)+i)) return int(LFS_ERR_IO);
      return 0;
    };
    c.prog=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,const void *in,lfs_size_t n) {
      assert(off%PageBytes==0 && n%PageBytes==0 && off+n<=BlockBytes);
      for(unsigned i=0;i<n;i+=PageBytes) if(!KeyFlash::program(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,
          static_cast<const uint8_t *>(in)+i)) return int(LFS_ERR_IO);
      return 0;
    };
    c.erase=[](const lfs_config *cfg,lfs_block_t b) { return KeyFlash::erase(cfg->context,FirstBlock+2+b)?0:int(LFS_ERR_IO); };
  }
  void write(const char *path,const std::vector<uint8_t> &bytes) {
    lfs_file_t file{};lfs_file_config config{};config.buffer=cache;
    assert(!lfs_file_opencfg(&fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC,&config));
    assert(lfs_file_write(&fs,&file,bytes.data(),bytes.size())==int(bytes.size()));
    assert(!lfs_file_close(&fs,&file));
  }
};
static void finish(KeyStore &store) {
  for(unsigned step=0;step<64 && (store.state()==KeyStore::State::Busy || store.state()==KeyStore::State::Committing);step++) store.step();
  assert(store.state()==KeyStore::State::Complete && store.result()==Result::Ok && store.current());
}
static bool same(const Table &a,const Table &b) {
  if(!a.serial || !b.serial) return !a.serial && !b.serial && a.valid() && b.valid();
  uint8_t x[Keys::WireBytes],y[Keys::WireBytes];
  assert(Keys::encode(a,x) && Keys::encode(b,y));return !memcmp(x,y,sizeof(x));
}
static std::vector<uint8_t> registryBytes(KeyFlash &flash) {
  Mounted raw(flash);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,KeyStore::Path,LFS_O_RDONLY,&config));
  auto n=lfs_file_size(&raw.fs,&file);assert(n>=0 && n<=int(KeyStore::MaximumDamagedBytes+1));
  std::vector<uint8_t> result(n);assert(lfs_file_read(&raw.fs,&file,result.data(),n)==n);assert(!lfs_file_close(&raw.fs,&file));return result;
}
static Table snapshot(KeyFlash &flash) {
  Mounted raw(flash);KeyStore store(&raw.fs);Result r=store.load();
  assert(r==Result::Ok || r==Result::Missing);assert(store.current());return *store.current();
}
static void appsPreserved(KeyFlash &flash) {
  auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());
  unsigned count=0;
  assert(v->list([](void *ctx,const char *name,const Entry &) { assert(!strcmp(name,"unrelated"));++*static_cast<unsigned *>(ctx);return true; },&count));
  assert(count==1);Entry entry{};assert(v->entry("unrelated",&entry));
  assert(entry.packageBytes==468 && entry.dataBytes==123);
  uint8_t package[468],data[123];assert(v->read("unrelated",package,sizeof(package),data,sizeof(data)));
  for(auto b:package) assert(b==0x42);
  for(auto b:data) assert(b==0x67);
}
using Action=std::function<Result(KeyStore &)>;
static unsigned interruptions(const KeyFlash &baseline,const Action &action) {
  KeyFlash completed=baseline;Table before=snapshot(completed);int writes=completed.writes;
  { Mounted raw(completed);KeyStore store(&raw.fs);assert(action(store)==Result::Busy);finish(store); }
  Table after=snapshot(completed);writes=completed.writes-writes;assert(writes>0 && !same(before,after));
  for(bool torn:{false,true}) for(int cut=0;cut<=writes;cut++) {
    KeyFlash trial=baseline;trial.cut=trial.writes+cut;trial.torn=torn;
    try { Mounted raw(trial);KeyStore store(&raw.fs);assert(action(store)==Result::Busy);finish(store); }
    catch(PowerCut &) {}
    trial.reboot();Table recovered=snapshot(trial);
    assert(same(recovered,before) || same(recovered,after));appsPreserved(trial);
    // Retry only after observing which atomic registry actually survived.
    Mounted raw(trial);KeyStore store(&raw.fs);
    if(same(recovered,before)) { assert(action(store)==Result::Busy);finish(store); }
    else assert(action(store)==Result::Stale);
  }
  return 2*(writes+1);
}
static void codec(const uint8_t modulus[256],const char *output) {
  Table empty,active,revoked,again,sentinel;
  assert(empty.valid() && !empty.find(nullptr,Keys::Purpose::Execute));
  assert(empty.enroll(0,modulus,"Development",11,&active)==Result::Ok);
  assert(active.serial==1 && active.count==1 && active.valid());
  assert(active.find(active.keys[0].id,Keys::Purpose::Execute));
  assert(active.enroll(1,modulus,"Development",11,&sentinel)==Result::Unchanged);
  assert(active.revoke(0,active.keys[0].id,&sentinel)==Result::Stale);
  assert(active.revoke(1,active.keys[0].id,&revoked)==Result::Ok);
  assert(!revoked.find(active.keys[0].id,Keys::Purpose::Execute));
  const auto *retained=revoked.find(active.keys[0].id,Keys::Purpose::Inspect);
  assert(retained && !memcmp(retained->modulus,modulus,256));
  assert(revoked.revoke(2,retained->id,&sentinel)==Result::Unchanged);
  assert(revoked.enroll(2,modulus,"Restored",8,&again)==Result::Ok && again.count==1 && again.serial==3);
  assert(again.find(active.keys[0].id,Keys::Purpose::Execute));
  assert(!again.find(active.keys[0].id,Keys::Purpose(99)));
  uint8_t wire[Keys::WireBytes],other[Keys::WireBytes];
  assert(Keys::encode(revoked,wire) && Keys::decode(wire,sizeof(wire),&again)==Result::Ok && same(again,revoked));
  FILE *f=fopen(output,"wb");assert(f && fwrite(wire,1,sizeof(wire),f)==sizeof(wire) && !fclose(f));
  // Every byte, truncation, field/reserved check is exercised independently of
  // signature verification. Hash recomputation does not make invalid keys valid.
  for(unsigned i=0;i<Keys::WireBytes;i++) {
    memcpy(other,wire,sizeof(wire));other[i]^=0x80;sentinel=active;
    assert(Keys::decode(other,sizeof(other),&sentinel)==Result::Corrupt && same(sentinel,active));
    assert(Keys::decode(wire,i,&sentinel)==Result::Corrupt && same(sentinel,active));
  }
  for(unsigned index:{8u,12u,16u,20u,24u,64u,68u,80u,112u,367u,368u,399u,400u}) {
    memcpy(other,wire,sizeof(wire));other[index]^=0x80;
    PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);
    PrimeG2::NativeAppHash::shaUpdate(&hash,other,32);
    PrimeG2::NativeAppHash::shaUpdate(&hash,other+64,sizeof(other)-64);
    PrimeG2::NativeAppHash::shaFinal(&hash,other+32);
    // Serial high bit is valid and is not a reserved-field test.
    if(index==16) assert(Keys::decode(other,sizeof(other),&sentinel)==Result::Ok);
    else assert(Keys::decode(other,sizeof(other),&sentinel)==Result::Corrupt);
  }
  assert(Keys::decode(nullptr,sizeof(wire),&sentinel)==Result::Corrupt);
  assert(Keys::decode(wire,sizeof(wire)+1,&sentinel)==Result::Corrupt);
  assert(Keys::decode(wire,sizeof(wire),nullptr)==Result::Corrupt);
  memset(other,0xa5,sizeof(other));assert(!Keys::encode(empty,other));for(auto b:other) assert(b==0xa5);
  for(const char *label:{"", " leading", "trailing ", "line\n", "bad\x7f", "1234567890123456789012345678901234"})
    assert(empty.enroll(0,modulus,label,strlen(label),&sentinel)==Result::Invalid);
  assert(empty.enroll(0,modulus,nullptr,1,&sentinel)==Result::Invalid);
  assert(empty.enroll(0,modulus,"ok",2,&empty)==Result::Invalid);
  assert(empty.enroll(0,nullptr,"ok",2,&sentinel)==Result::Invalid);
  uint8_t bad[256];memcpy(bad,modulus,256);bad[0]&=127;
  assert(empty.enroll(0,bad,"ok",2,&sentinel)==Result::Invalid);
  memcpy(bad,modulus,256);bad[255]&=254;assert(!Keys::fingerprint(bad,other));
  again=active;again.count=2;again.serial=2;again.keys[1]=again.keys[0];assert(!again.valid());
  again=active;again.keys[1]=again.keys[0];assert(!again.valid());
  again=active;again.keys[0].label[31]='x';assert(!again.valid());
  again=active;again.serial=UINT32_MAX;
  assert(again.revoke(again.serial,again.keys[0].id,&sentinel)==Result::Overflow);
  assert(again.enroll(again.serial,modulus,"new",3,&sentinel)==Result::Overflow);
  assert(again.enroll(again.serial,modulus,"Development",11,&sentinel)==Result::Unchanged);
  again=active;
  for(unsigned i=1;i<Keys::MaximumKeys;i++) {
    memcpy(bad,modulus,256);bad[1]^=i;
    assert(again.enroll(again.serial,bad,"more",4,&sentinel)==Result::Ok);again=sentinel;
  }
  memcpy(bad,modulus,256);bad[1]^=Keys::MaximumKeys;
  assert(again.enroll(again.serial,bad,"full",4,&sentinel)==Result::Full);
  assert(again.revoke(again.serial,again.keys[0].id,&sentinel)==Result::Ok);again=sentinel;
  assert(again.enroll(again.serial,modulus,"reactivated",11,&sentinel)==Result::Ok && sentinel.count==Keys::MaximumKeys);
  // Removing a revoked identity frees a full slot without reusing its serial.
  assert(again.remove(again.serial,again.keys[0].id,&sentinel)==Result::Ok);
  assert(sentinel.count==Keys::MaximumKeys-1 && sentinel.serial==again.serial+1 && !sentinel.find(active.keys[0].id,Keys::Purpose::Inspect));
  assert(sentinel.enroll(sentinel.serial,bad,"new slot",8,&again)==Result::Ok && again.count==Keys::MaximumKeys);
  assert(active.remove(1,active.keys[0].id,&again)==Result::Active);
  assert(revoked.remove(1,retained->id,&again)==Result::Stale);
  assert(revoked.remove(2,retained->id,&again)==Result::Ok && again.count==0 && again.serial==3 && again.valid());
  assert(Keys::encode(again,other) && Keys::decode(other,sizeof(other),&sentinel)==Result::Ok && sentinel.serial==3 && !sentinel.count);
  assert(sentinel.enroll(0,modulus,"stale",5,&again)==Result::Stale);
  // Version 1 remains readable; only its stored-empty representation is invalid.
  memcpy(other,wire,sizeof(wire));other[8]=1;
  PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);
  PrimeG2::NativeAppHash::shaUpdate(&hash,other,32);PrimeG2::NativeAppHash::shaUpdate(&hash,other+64,sizeof(other)-64);
  PrimeG2::NativeAppHash::shaFinal(&hash,other+32);
  assert(Keys::decode(other,sizeof(other),&again)==Result::Ok && same(again,revoked));
}
static unsigned repairMatrix(const KeyFlash &active,const uint8_t modulus[256]) {
  KeyFlash damaged=active;{Mounted raw(damaged);raw.corrupt(KeyStore::Path);}
  auto before=registryBytes(damaged);uint8_t hash[32];PrimeG2::NativeAppHash::sha256(before.data(),before.size(),hash);
  KeyFlash completed=damaged;int writes=completed.writes;
  { Mounted raw(completed);KeyStore s(&raw.fs);uint8_t observed[32],copy[512];uint32_t bytes;
    assert(s.damaged(observed,&bytes)==Result::Ok && bytes==before.size() && !memcmp(hash,observed,32) && !s.current());
    assert(s.readDamaged(1,copy,512)==512 && !memcmp(copy,before.data()+1,512));
    assert(s.readDamaged(bytes,copy,1)<0 && s.readDamaged(0,copy,513)<0);
    observed[0]^=1;assert(s.beginRepair(observed,modulus,"Repair",6)==Result::Stale && completed.writes==writes);
    assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Busy);finish(s);assert(s.current()->serial==1);
  }
  writes=completed.writes-writes;auto after=registryBytes(completed);assert(before!=after);
  for(bool torn:{false,true}) for(int cut=0;cut<=writes;cut++) {
    KeyFlash trial=damaged;trial.cut=trial.writes+cut;trial.torn=torn;
    try {Mounted raw(trial);KeyStore s(&raw.fs);assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Busy);finish(s);} catch(PowerCut &) {}
    trial.reboot();auto selected=registryBytes(trial);assert(selected==before || selected==after);appsPreserved(trial);
    {Mounted raw(trial);KeyStore s(&raw.fs);
      if(selected==before) {assert(!s.current() && s.load()==Result::Corrupt);assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Busy);finish(s);}
      else assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Invalid);
    }
  }
  for(unsigned steps=0;steps<34;steps++) {
    KeyFlash trial=damaged;
    {Mounted raw(trial);KeyStore s(&raw.fs);assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Busy);
      for(unsigned n=0;n<steps;n++) s.step();
      if(s.state()==KeyStore::State::Busy) {assert(s.cancel() && !s.current());}
      else {assert(s.commitStarted() && !s.cancel());if(s.state()!=KeyStore::State::Complete) finish(s);}
    }
    auto selected=registryBytes(trial);assert(selected==before || selected==after);appsPreserved(trial);
  }
  for(unsigned size:{0u,3u,Keys::WireBytes+3,KeyStore::MaximumDamagedBytes,KeyStore::MaximumDamagedBytes+1}) {
    KeyFlash trial=active;Mounted raw(trial);std::vector<uint8_t> data(size,0x7a);raw.write(KeyStore::Path,data);
    KeyStore s(&raw.fs);uint32_t bytes=0;int writes=trial.writes;Result result=s.damaged(hash,&bytes);
    assert(trial.writes==writes && !s.current());
    if(size>KeyStore::MaximumDamagedBytes) assert(result==Result::Invalid);
    else {assert(result==Result::Ok && bytes==size);assert(s.beginRepair(hash,modulus,"Repair",6)==Result::Busy);finish(s);}
  }
  return 2*(writes+1);
}
static void signatures(const uint8_t modulus[256],const char *path) {
  std::vector<uint8_t> package(2101665);
  FILE *f=fopen(path,"rb");assert(f);size_t bytes=fread(package.data(),1,package.size(),f);assert(!fclose(f));package.resize(bytes);
  Table empty,active,revoked;assert(empty.enroll(0,modulus,"Signing",7,&active)==Result::Ok);
  assert(active.revoke(1,active.keys[0].id,&revoked)==Result::Ok);
  const uint8_t *payload=nullptr;size_t length=0;
  // Compiled-only trust must not gain this public emulator fixture key merely
  // because a developer Table exists. Host compilation is the physical policy.
  assert(!PrimeG2::NativeAppSignature::unwrap(package.data(),bytes,&payload,&length));
  assert(!empty.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length));
  assert(active.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length));
  assert(payload==package.data()+352 && length==bytes-352);
  static unsigned progressCalls=0;
  auto progress=+[]{progressCalls++;};
  assert(active.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length,progress));
  assert(progressCalls>0 && payload==package.data()+352 && length==bytes-352);
  progressCalls=0;payload=nullptr;length=17;
  assert(!revoked.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length,progress));
  assert(progressCalls==0 && !payload && length==17);
  assert(revoked.unwrap(package.data(),bytes,Keys::Purpose::Inspect,&payload,&length,progress));
  assert(progressCalls>0);
  package[200]^=1;progressCalls=0;payload=nullptr;length=17;
  assert(!active.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length,progress));
  assert(progressCalls>0 && !payload && length==17);package[200]^=1;
  payload=nullptr;length=17;
  assert(!revoked.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length) && !payload && length==17);
  assert(revoked.unwrap(package.data(),bytes,Keys::Purpose::Inspect,&payload,&length));
  for(unsigned offset:{0u,8u,12u,16u,20u,24u,56u,88u,92u,96u,200u,351u,352u,unsigned(bytes-1)}) {
    package[offset]^=1;payload=nullptr;length=17;
    assert(!active.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,&length));
    assert(!revoked.unwrap(package.data(),bytes,Keys::Purpose::Inspect,&payload,&length));
    assert(!payload && length==17);package[offset]^=1;
  }
  // A recomputed content digest still cannot authenticate a forged envelope.
  auto changed=package;changed.back()^=1;PrimeG2::NativeAppHash::sha256(changed.data()+352,bytes-352,changed.data()+56);
  assert(!revoked.unwrap(changed.data(),bytes,Keys::Purpose::Inspect,&payload,&length));
  assert(!active.unwrap(package.data(),bytes-1,Keys::Purpose::Execute,&payload,&length));
  assert(!active.unwrap(package.data(),32,Keys::Purpose::Execute,&payload,&length));
  assert(!active.unwrap(nullptr,bytes,Keys::Purpose::Execute,&payload,&length));
  assert(!active.unwrap(package.data(),bytes,Keys::Purpose::Execute,nullptr,&length));
  assert(!active.unwrap(package.data(),bytes,Keys::Purpose::Execute,&payload,nullptr));
  assert(!active.unwrap(package.data(),bytes,Keys::Purpose(99),&payload,&length));
}
int main(int argc,char **argv) {
  assert(argc==4);uint8_t modulus[256],id[32];
  FILE *input=fopen(argv[1],"rb");assert(input && fread(modulus,1,256,input)==256 && !fclose(input));
  assert(Keys::fingerprint(modulus,id));codec(modulus,argv[2]);
  signatures(modulus,argv[3]);
  KeyFlash baseline;
  { auto v=std::make_unique<Volume>(baseline.backend());std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
    assert(v->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char out[49]) { strcpy(out,"unused");return true; }));
    memset(package.data(),0x42,468);memset(data.data(),0x67,123);
    assert(v->begin("unrelated",package.data(),468,data.data(),123));
    for(unsigned i=0;i<10000 && v->state()!=State::Complete;i++) v->step();
    assert(v->state()==State::Complete);
  }
  Action enroll=[&](KeyStore &s) { return s.beginEnroll(0,modulus,"Development",11); };
  unsigned cuts=interruptions(baseline,enroll);
  KeyFlash active=baseline;
  { Mounted raw(active);KeyStore s(&raw.fs);int writes=active.writes;
    assert(!s.current() && s.load()==Result::Missing && s.current()->serial==0 && active.writes==writes);
    assert(enroll(s)==Result::Busy && s.current()->serial==0);
    assert(s.load()==Result::Busy && s.beginRevoke(0,id)==Result::Busy);finish(s);
    writes=active.writes;assert(s.beginEnroll(1,modulus,"Development",11)==Result::Unchanged && active.writes==writes);
    assert(s.beginRevoke(0,id)==Result::Stale && active.writes==writes);
  }
  Action revoke=[&](KeyStore &s) { return s.beginRevoke(1,id); };
  cuts+=interruptions(active,revoke);KeyFlash revoked=active;
  { Mounted raw(revoked);KeyStore s(&raw.fs);assert(s.load()==Result::Ok);
    assert(s.beginRevoke(1,s.current()->keys[0].id)==Result::Busy);finish(s);
    assert(!s.current()->find(id,Keys::Purpose::Execute) && s.current()->find(id,Keys::Purpose::Inspect));
  }
  Action restore=[&](KeyStore &s) { return s.beginEnroll(2,modulus,"Recovered",9); };
  cuts+=interruptions(revoked,restore);
  cuts+=interruptions(revoked,[&](KeyStore &s) {return s.beginRemove(2,id);});
  unsigned repairCuts=repairMatrix(active,modulus);
  uint8_t second[256];memcpy(second,modulus,256);second[1]^=17;
  cuts+=interruptions(active,[&](KeyStore &s) { return s.beginEnroll(1,second,"Second",6); });
  // Repeated approval/revocation cycles cross littlefs metadata compactions;
  // power cuts must still preserve a complete old or new authority table.
  KeyFlash aged=active;
  { Mounted raw(aged);KeyStore s(&raw.fs);
    for(unsigned i=0;i<40;i++) {
      assert(s.beginRevoke(1+2*i,id)==Result::Busy);finish(s);
      assert(s.beginEnroll(2+2*i,modulus,"Development",11)==Result::Busy);finish(s);
    }
    assert(s.current()->serial==81 && s.current()->count==1);
  }
  cuts+=interruptions(aged,[&](KeyStore &s) { return s.beginRevoke(81,id); });
  // Cancel at every public polling boundary. Once rename starts, cancellation
  // cannot claim rollback; finish/readback reports the canonical new table.
  unsigned cancellations=0;
  for(unsigned steps=0;steps<34;steps++) {
    KeyFlash trial=active;Table before=snapshot(trial);
    { Mounted raw(trial);KeyStore s(&raw.fs);assert(revoke(s)==Result::Busy);
      for(unsigned n=0;n<steps;n++) s.step();
      if(s.state()==KeyStore::State::Busy) { assert(s.cancel());cancellations++;assert(same(*s.current(),before)); }
      else { assert(s.commitStarted() && !s.cancel());if(s.state()!=KeyStore::State::Complete) finish(s); }
    }
    Table after=snapshot(trial);assert(same(after,before) || after.serial==2);appsPreserved(trial);
  }
  // Stale partial files are never a source of trust and can be replaced by an
  // approved retry. A corrupt canonical registry cannot be reset by enrollment.
  { KeyFlash trial=active;Mounted raw(trial);raw.write(KeyStore::Pending,{1,2,3});KeyStore s(&raw.fs);
    assert(s.load()==Result::Ok && s.current()->serial==1);assert(revoke(s)==Result::Busy);finish(s);
    raw.corrupt(KeyStore::Path);int writes=trial.writes;
    assert(s.load()==Result::Corrupt && !s.current());
    assert(s.beginEnroll(0,modulus,"Reset",5)==Result::Corrupt && !s.current() && trial.writes==writes);
  }
  { KeyFlash trial=baseline;Mounted raw(trial);raw.write(KeyStore::Pending,std::vector<uint8_t>(Keys::WireBytes,0));
    KeyStore s(&raw.fs);int writes=trial.writes;
    assert(s.load()==Result::Missing && !s.current()->count && trial.writes==writes);
    assert(enroll(s)==Result::Busy);finish(s);
  }
  // Inject actual backend read failures throughout initial authentication,
  // pending verification, rename and canonical readback. Never retain authority
  // after an uncertain commit; reload after transient failures determines it.
  unsigned ioCases=0,loadFailures=0,preCommitFailures=0,postCommitFailures=0;int reads=0;
  { KeyFlash trial=active;Mounted raw(trial);KeyStore s(&raw.fs);reads=trial.reads;
    assert(revoke(s)==Result::Busy);finish(s);reads=trial.reads-reads;
  }
  for(int fault=0;fault<reads;fault++) {
    KeyFlash trial=active;
    { Mounted raw(trial);KeyStore s(&raw.fs);assert(s.load()==Result::Ok);
      // Use the same fresh-mount read pattern as the measurement.
    }
    { Mounted raw(trial);KeyStore s(&raw.fs);trial.readFault=trial.reads+fault;
      Result result=revoke(s);
      if(result==Result::Busy) {
        for(unsigned i=0;i<64 && (s.state()==KeyStore::State::Busy || s.state()==KeyStore::State::Committing);i++) s.step();
        if(s.state()==KeyStore::State::Failed) {
          if(s.commitStarted()) { assert(!s.current());postCommitFailures++; }
          else { assert(s.current() && s.current()->serial==1);preCommitFailures++; }
        }
      } else { assert(result==Result::Io || result==Result::Corrupt);assert(!s.current());loadFailures++; }
      trial.readFault=-1;
    }
    trial.reboot();Table recovered=snapshot(trial);
    assert(recovered.serial==1 || recovered.serial==2);appsPreserved(trial);ioCases++;
  }
  assert(loadFailures && preCommitFailures && postCommitFailures);
  // Removal of all remaining flash capacity is not successful enrollment or
  // revocation. Existing app bytes and the previous registry remain readable.
  { KeyFlash trial=active;
    { Mounted raw(trial);raw.fill();KeyStore s(&raw.fs);assert(revoke(s)==Result::Busy);
      for(unsigned i=0;i<64 && s.state()==KeyStore::State::Busy;i++) s.step();
      assert(s.state()==KeyStore::State::Failed);
    }
    assert(snapshot(trial).serial==1);appsPreserved(trial);
  }
  appsPreserved(active);appsPreserved(revoked);
  // The real startup migration/pruning path preserves the independent root.
  Table beforeBoot=snapshot(aged);
  { auto v=std::make_unique<Volume>(aged.backend());std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
    assert(v->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char out[49]) { strcpy(out,"unused");return true; }));
  }
  assert(same(snapshot(aged),beforeBoot));appsPreserved(aged);
  printf("{\"status\":\"passed\",\"wire_bytes\":%u,\"table_bytes\":%zu,\"store_bytes\":%zu,\"interruption_cases\":%u,\"repair_interruption_cases\":%u,\"cancellation_cases\":%u,\"read_fault_cases\":%u,\"load_failures\":%u,\"precommit_failures\":%u,\"postcommit_failures\":%u,\"physical\":\"not_tested\"}\n",
    Keys::WireBytes,sizeof(Table),sizeof(KeyStore),cuts,repairCuts,cancellations,ioCases,loadFailures,preCommitFailures,postCommitFailures);
}

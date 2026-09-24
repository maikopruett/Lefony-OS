// SPDX-License-Identifier: GPL-3.0-or-later
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
static std::vector<uint8_t> scratchPackage(MaximumPackage),scratchData(MaximumData);
static void finish(Volume &v) {
  unsigned steps=0;
  while(v.state()!=State::Complete && v.state()!=State::Failed && steps++<10000) v.step();
  assert(v.state()==State::Complete);
}
static bool initialize(Volume &v) {
  return v.initialize(scratchPackage.data(),scratchPackage.size(),scratchData.data(),scratchData.size(),
    [](const uint8_t *,size_t,char id[49]) { strcpy(id,"unused");return true; });
}
struct Snapshot {
  uint32_t generation;
  std::vector<uint8_t> package,data,root;
  bool operator==(const Snapshot &b) const {
    return generation==b.generation && package==b.package && data==b.data && root==b.root;
  }
};
static Snapshot snapshot(Volume &v,const char *id="document") {
  Entry e;assert(v.entry(id,&e));
  Snapshot s;s.generation=e.generation;s.package.resize(e.packageBytes);s.data.resize(e.dataBytes);
  assert(v.read(id,s.package.data(),s.package.size(),s.data.data(),s.data.size()));
  Root root;
  if(v.documentRoot(id,&root)) { s.root.resize(240);assert(PrimeG2::AppDocumentRoot::encode(root,s.root.data())); }
  return s;
}
static Snapshot snapshot(Flash &flash,const char *id="document") {
  auto vOwner=std::make_unique<Volume>(flash.backend());Volume &v=*vOwner;assert(initialize(v));return snapshot(v,id);
}
using Action=std::function<bool(Volume &)>;
static unsigned matrix(const Flash &baseline,const Action &action,bool removal=false) {
  Flash completed=baseline;Snapshot before,after,other;
  { auto vOwner=std::make_unique<Volume>(completed.backend());Volume &v=*vOwner;assert(initialize(v));before=snapshot(v);other=snapshot(v,"other"); }
  int mutations=completed.writes;
  { auto vOwner=std::make_unique<Volume>(completed.backend());Volume &v=*vOwner;assert(initialize(v));assert(action(v));finish(v);if(!removal) after=snapshot(v); }
  mutations=completed.writes-mutations;assert(mutations>0);
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash trial=baseline;trial.cut=trial.writes+cut;trial.torn=torn;
    try { auto vOwner=std::make_unique<Volume>(trial.backend());Volume &v=*vOwner;assert(initialize(v));assert(action(v));finish(v); } catch(PowerCut &) {}
    trial.cut=-1;
    auto recoveredOwner=std::make_unique<Volume>(trial.backend());Volume &recovered=*recoveredOwner;assert(initialize(recovered));
    Entry e;
    if(!recovered.entry("document",&e)) assert(removal);
    else { auto current=snapshot(recovered);assert(current==before || (!removal && current==after)); }
    assert(snapshot(recovered,"other")==other);
  }
  return 2*(mutations+1);
}
// Independently mount the production geometry for corruption/full-media input.
// The production class, its private members and parser are not modified.
struct Raw {
  lfs_t fs{};lfs_config c{};
  uint8_t read[2048]{},prog[2048]{},look[64]{},cache[2048]{};
  explicit Raw(Flash &flash) {
    c.context=&flash;
    c.read=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,void *out,lfs_size_t n) {
      for(unsigned i=0;i<n;i+=PageBytes) {
        if(!Flash::read(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,
          static_cast<uint8_t *>(out)+i)) return int(LFS_ERR_IO);
      }
      return 0; };
    c.prog=[](const lfs_config *cfg,lfs_block_t b,lfs_off_t off,const void *in,lfs_size_t n) {
      for(unsigned i=0;i<n;i+=PageBytes) {
        if(!Flash::program(cfg->context,(FirstBlock+2+b)*PagesPerBlock+(off+i)/PageBytes,
          static_cast<const uint8_t *>(in)+i)) return int(LFS_ERR_IO);
      }
      return 0; };
    c.erase=[](const lfs_config *cfg,lfs_block_t b) { return Flash::erase(cfg->context,FirstBlock+2+b)?0:int(LFS_ERR_IO); };
    c.sync=[](const lfs_config *) { return 0; };
    c.read_size=c.prog_size=c.cache_size=PageBytes;c.block_size=BlockBytes;c.block_count=BlockCount-2;
    c.block_cycles=100;c.lookahead_size=64;c.read_buffer=read;c.prog_buffer=prog;c.lookahead_buffer=look;
    c.name_max=53;c.file_max=MaximumPackage+MaximumData+64;c.metadata_max=8192;c.inline_max=256;
    assert(!lfs_mount(&fs,&c));
  }
  ~Raw() { lfs_unmount(&fs); }
  void corrupt(const char *path) {
    lfs_file_t file{};lfs_file_config config{};config.buffer=cache;
    assert(!lfs_file_opencfg(&fs,&file,path,LFS_O_WRONLY,&config));
    uint8_t bad=0;assert(lfs_file_write(&fs,&file,&bad,1)==1);assert(!lfs_file_close(&fs,&file));
  }
  void corruptRoot(const char *path) {
    // Deliberately lose both FILE5 copies, retaining the occupied namespace.
    // corrupt() alone is a recoverable payload failure for replicated roots.
    corrupt(path);int rc=lfs_removeattr(&fs,path,0x52);assert(!rc || rc==LFS_ERR_NOATTR);
  }
  void remove(const char *path) { assert(!lfs_remove(&fs,path)); }
  bool exists(const char *path) { lfs_info info;int rc=lfs_stat(&fs,path,&info);assert(!rc || rc==LFS_ERR_NOENT);return !rc; }
  void root(const Root &root) {
    // Explicit historical FILE3/4 fixture, including after a FILE5 save.
    uint8_t wire[240];assert(PrimeG2::AppDocumentRoot::encode(root,wire));
    lfs_file_t file{};lfs_file_config config{};config.buffer=cache;
    assert(!lfs_file_opencfg(&fs,&file,"apps/document.app",LFS_O_WRONLY|LFS_O_TRUNC,&config));
    assert(lfs_file_write(&fs,&file,wire,sizeof(wire))==sizeof(wire));assert(!lfs_file_close(&fs,&file));
    int rc=lfs_removeattr(&fs,"apps/document.app",0x52);assert(!rc || rc==LFS_ERR_NOATTR);
  }
  void fill() {
    uint8_t data[2048]{};
    for(unsigned i=0;i<1024;i++) {
      lfs_file_t file{};lfs_file_config config{};config.buffer=cache;char path[32];snprintf(path,sizeof(path),"filler%u",i);
      if(lfs_file_opencfg(&fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT,&config)) break;
      bool full=false;
      for(unsigned j=0;j<512;j++) if(lfs_file_write(&fs,&file,data,sizeof(data))!=sizeof(data)) { full=true;break; }
      lfs_file_close(&fs,&file);if(full) break;
    }
    // A failed large uncommitted file can leave several blocks free. Fill the
    // remainder with single-block files before asserting a full-media failure.
    for(unsigned i=0;i<1024;i++) {
      lfs_file_t file{};lfs_file_config config{};config.buffer=cache;char path[32];snprintf(path,sizeof(path),"smallfill%u",i);
      if(lfs_file_opencfg(&fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT,&config)) break;
      int written=lfs_file_write(&fs,&file,data,sizeof(data));int closed=lfs_file_close(&fs,&file);
      if(written!=sizeof(data) || closed) break;
    }
  }
};
int main() {
  std::vector<uint8_t> package(131333,0x35),nextPackage(195001,0x79),first(64,0x12),next(65,0x23),migrated(65536,0x34);
  uint32_t version[3]={1,0,0},upgradeVersion[3]={2,0,0},laterVersion[3]={3,0,0};
  Flash baseline;
  { auto vOwner=std::make_unique<Volume>(baseline.backend());Volume &v=*vOwner;assert(initialize(v));
    assert(v.begin("document",package.data(),package.size(),first.data(),first.size()));finish(v);
    assert(v.begin("other",package.data(),468,first.data(),first.size()));finish(v);
    assert(!v.beginCheckpoint("missing",nullptr,0,version,0));
    assert(!v.beginCheckpoint("document",nullptr,1,version,0));
  }
  Action convert=[&](Volume &v) { return v.beginCheckpoint("document",next.data(),next.size(),version,0); };
  unsigned cases=matrix(baseline,convert);
  Flash converted=baseline;
  { auto vOwner=std::make_unique<Volume>(converted.backend());Volume &v=*vOwner;assert(initialize(v));assert(convert(v));finish(v);
    assert(v.checkpointPackageWrites()==package.size());
    auto s=snapshot(v);assert(s.package==package && s.data==next && s.root.size()==240);
    assert(!v.begin("document",package.data(),package.size(),first.data(),first.size()));
  }
  Action save=[&](Volume &v) { return v.beginCheckpoint("document",first.data(),first.size(),nullptr,0); };
  cases+=matrix(converted,save);
  Flash saved=converted;uint64_t programmed=saved.programmed;
  { auto vOwner=std::make_unique<Volume>(saved.backend());Volume &v=*vOwner;assert(initialize(v));Root old;assert(v.documentRoot("document",&old));
    assert(save(v));finish(v);assert(v.checkpointPackageWrites()==0 && v.checkpointDataWrites()==first.size());
    Root now;assert(v.documentRoot("document",&now));assert(now.current.package==old.current.package && now.current.data!=old.current.data);
  }
  programmed=saved.programmed-programmed;assert(programmed<package.size()/2);
  Action upgrade=[&](Volume &v) { return v.beginUpgrade("document",nextPackage.data(),nextPackage.size(),upgradeVersion); };
  cases+=matrix(saved,upgrade);
  Flash upgraded=saved;
  { auto vOwner=std::make_unique<Volume>(upgraded.backend());Volume &v=*vOwner;assert(initialize(v));assert(upgrade(v));finish(v);
    assert(v.checkpointDataWrites()==0);
    assert(!v.beginUpgrade("document",package.data(),package.size(),laterVersion));
    assert(!v.beginAccept("document",99));
  }
  Action migrate=[&](Volume &v) { return v.beginCheckpoint("document",migrated.data(),migrated.size(),nullptr,1); };
  cases+=matrix(upgraded,migrate);
  Flash migratedFlash=upgraded;
  { auto vOwner=std::make_unique<Volume>(migratedFlash.backend());Volume &v=*vOwner;assert(initialize(v));assert(migrate(v));finish(v); }
  cases+=matrix(migratedFlash,[](Volume &v) { return v.beginRollback("document"); });
  cases+=matrix(migratedFlash,[](Volume &v) { return v.beginAccept("document",1); });
  { Flash rolled=migratedFlash;auto vOwner=std::make_unique<Volume>(rolled.backend());Volume &v=*vOwner;assert(initialize(v));assert(v.beginRollback("document"));finish(v);
    auto s=snapshot(v);assert(s.package==package && s.data==first);
    Root root;assert(v.documentRoot("document",&root));assert(root.highVersion[0]==2 && !root.flags);
    assert(!v.beginUpgrade("document",nextPackage.data(),nextPackage.size(),upgradeVersion));
    assert(v.beginUpgrade("document",nextPackage.data(),nextPackage.size(),laterVersion));finish(v);
  }
  cases+=matrix(migratedFlash,[](Volume &v) { return v.begin("document",nullptr,0,nullptr,0); },true);
  // Cancellation must not publish a partial object, and a retry may safely use
  // the unpublished serial after collecting its incomplete objects.
  { Flash f=baseline;auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));auto before=snapshot(v);
    assert(convert(v));while(v.checkpointPackageWrites()<4096) v.step();v.cancel();assert(snapshot(v)==before);
    assert(convert(v));finish(v);assert(save(v));while(v.state()!=State::Committing) v.step();
    v.cancel();assert(v.state()==State::Committing);finish(v);
  }
  // Repeated checkpoints reclaim unreferenced objects; retained package bytes
  // remain unchanged and allocation does not grow once the two pairs stabilize.
  { Flash f=saved;auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));Space initial;assert(v.space(&initial));
    for(unsigned i=0;i<100;i++) { assert(save(v));finish(v);assert(!v.checkpointPackageWrites()); }
    Space end;assert(v.space(&end));assert(end.allocated<=initial.allocated+4*BlockBytes);
    assert(snapshot(v).package==package);
  }
  // Unknown roots and corrupt immutable objects cannot be rewritten as FILE2.
  { Flash f=converted;auto before=snapshot(f);{Raw raw(f);raw.corrupt("apps/document.app");}
    int writes=f.writes;assert(snapshot(f)==before && f.writes==writes);
    auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));
    assert(save(v));finish(v);assert(snapshot(v).package==package && snapshot(v).data==first);
  }
  { Flash f=converted;{Raw raw(f);raw.corruptRoot("apps/document.app");}
    int writes=f.writes;auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));Entry e;assert(!v.entry("document",&e));
    assert(!v.begin("document",package.data(),package.size(),first.data(),first.size()));assert(!convert(v));assert(f.writes==writes);
  }
  { Flash f=converted;Root root;{auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(v.documentRoot("document",&root));}
    char path[80];snprintf(path,sizeof(path),"objects/document/p%08x",root.current.package);
    { Raw raw(f);raw.corrupt(path); }
    int writes=f.writes;auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(save(v));
    while(v.state()!=State::Failed && v.state()!=State::Complete) v.step();assert(v.state()==State::Failed && f.writes==writes);
  }
  { Flash f=saved;auto before=snapshot(f);{Raw raw(f);raw.fill();}
    auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(!v.beginCheckpoint("document",migrated.data(),migrated.size(),nullptr,0));
    assert(snapshot(v)==before);
  }
  // The maximum app ID is legal, and empty data is a real hashed object.
  { Flash f=baseline;auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));std::string id(48,'a');
    assert(v.begin(id.c_str(),package.data(),468,nullptr,0));finish(v);
    assert(v.beginCheckpoint(id.c_str(),nullptr,0,version,0));finish(v);assert(snapshot(v,id.c_str()).data.empty());
  }
  // Exhaustion cannot wrap an object ID, but uninstall still reclaims it.
  { Flash f=converted;Root root;{auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(v.documentRoot("document",&root));}
    root.serial=0xffffffffu;{Raw raw(f);raw.root(root);}
    auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));int writes=f.writes;
    assert(!save(v) && !upgrade(v) && !v.beginRollback("document") && !v.beginAccept("document",0));assert(f.writes==writes);
    assert(v.begin("document",nullptr,0,nullptr,0));finish(v);Entry e;assert(!v.entry("document",&e));
  }
  // Startup finishes multiple interrupted uninstalls without skipping a sibling
  // when littlefs adjusts the live directory iterator after removal.
  { Flash f=converted;
    { auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));
      for(const char *id:{"aardvark","zebra"}) {
        assert(v.begin(id,package.data(),468,nullptr,0));finish(v);
        assert(v.beginCheckpoint(id,nullptr,0,version,0));finish(v);
      }
    }
    auto before=snapshot(f);
    {Raw raw(f);raw.remove("apps/aardvark.app");raw.remove("apps/zebra.app");}
    {auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(snapshot(v)==before);}
    {Raw raw(f);assert(!raw.exists("objects/aardvark") && !raw.exists("objects/zebra") && raw.exists("objects/document"));}
  }
  // Uninstall is already committed when object pruning starts. Cancellation
  // cannot report an aborted operation after the canonical root disappeared.
  { Flash f=converted;
    { auto vOwner=std::make_unique<Volume>(f.backend());Volume &v=*vOwner;assert(initialize(v));assert(v.begin("document",nullptr,0,nullptr,0));
      v.step();assert(v.state()==State::Committing);v.cancel();assert(v.state()==State::Committing);finish(v);
      Entry e;assert(!v.entry("document",&e));
    }
    {Raw raw(f);assert(!raw.exists("apps/document.app") && !raw.exists("objects/document"));}
  }
  printf("{\"status\":\"passed\",\"interruption_cases\":%u,\"checkpoint_programmed_bytes\":%llu,\"package_bytes\":%zu,\"checkpoint_package_writes\":0,\"store_object_bytes\":%zu,\"physical\":\"not_tested\"}\n",
    cases,static_cast<unsigned long long>(programmed),package.size(),sizeof(Volume));
}

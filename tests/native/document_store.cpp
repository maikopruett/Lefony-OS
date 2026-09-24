// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "document_store.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <functional>
#include <map>
#include <set>
#include <vector>
using namespace DocumentStoreExperiment;
struct PowerCut {};
struct Flash {
  using Page=std::array<uint8_t,2048>;
  std::map<uint32_t,Page> pages;
  std::set<uint32_t> bad;
  int writes=0,cut=-1;
  uint64_t programmed=0;
  bool torn=false;
  static int read(const lfs_config *c,lfs_block_t b,lfs_off_t o,void *data,lfs_size_t n) {
    assert(b<c->block_count && o%2048==0 && n%2048==0 && o+n<=131072);
    auto &f=*static_cast<Flash *>(c->context);
    if(f.bad.count(b)) return LFS_ERR_CORRUPT;
    for(unsigned i=0;i<n;i+=2048) {
      auto it=f.pages.find(b*64+(o+i)/2048);
      if(it==f.pages.end()) memset(static_cast<uint8_t *>(data)+i,255,2048);
      else memcpy(static_cast<uint8_t *>(data)+i,it->second.data(),2048);
    }
    return 0;
  }
  static int program(const lfs_config *c,lfs_block_t b,lfs_off_t o,const void *data,lfs_size_t n) {
    assert(b<c->block_count && o%2048==0 && n%2048==0 && o+n<=131072);
    auto &f=*static_cast<Flash *>(c->context);
    if(f.bad.count(b)) return LFS_ERR_CORRUPT;
    for(unsigned i=0;i<n;i+=2048) {
      uint32_t page=b*64+(o+i)/2048;
      assert(!f.pages.count(page));
      auto next=f.pages.lower_bound(page);
      assert(next==f.pages.end() || next->first/64!=b);
      bool cut=f.writes++==f.cut;
      if(cut && !f.torn) throw PowerCut{};
      Page bytes;bytes.fill(255);memcpy(bytes.data(),static_cast<const uint8_t *>(data)+i,cut?37:2048);
      f.pages.emplace(page,bytes);f.programmed+=cut?37:2048;
      if(cut) throw PowerCut{};
    }
    return 0;
  }
  static int erase(const lfs_config *c,lfs_block_t b) {
    assert(b<c->block_count);auto &f=*static_cast<Flash *>(c->context);
    if(f.bad.count(b)) return LFS_ERR_CORRUPT;
    bool cut=f.writes++==f.cut;
    if(cut && !f.torn) throw PowerCut{};
    for(unsigned i=0;i<(cut?7u:64u);i++) f.pages.erase(b*64+i);
    if(cut) throw PowerCut{};
    return 0;
  }
  static int sync(const lfs_config *) { return 0; }
};
struct Mounted {
  lfs_t fs{};lfs_config config{};
  uint8_t readCache[2048]{},writeCache[2048]{},lookahead[64]{};
  explicit Mounted(Flash &flash,bool format=false) {
    config.context=&flash;config.read=Flash::read;config.prog=Flash::program;config.erase=Flash::erase;config.sync=Flash::sync;
    config.read_size=2048;config.prog_size=2048;config.block_size=131072;config.block_count=510;
    config.block_cycles=100;config.cache_size=2048;config.lookahead_size=64;config.name_max=53;
    config.file_max=Store::MaximumPackage+Store::MaximumData+64;config.metadata_max=8192;config.inline_max=256;
    config.read_buffer=readCache;config.prog_buffer=writeCache;config.lookahead_buffer=lookahead;
    if(format) assert(lfs_format(&fs,&config)==0);
    assert(lfs_mount(&fs,&config)==0);
  }
  ~Mounted() { lfs_unmount(&fs); }
};
using Action=std::function<Result(Store &)>;
static unsigned interruptionMatrix(const Flash &baseline,const Action &action,const Root &before,const Root &after) {
  Flash complete=baseline;int writes=complete.writes;
  { Mounted volume(complete);Store store(&volume.fs);assert(action(store)==Result::Ok); }
  writes=complete.writes-writes;
  assert(writes>0);
  for(bool torn:{false,true}) for(int cut=0;cut<=writes;cut++) {
    Flash candidate=baseline;candidate.cut=candidate.writes+cut;candidate.torn=torn;
    try { Mounted volume(candidate);Store store(&volume.fs);assert(action(store)==Result::Ok); }
    catch(PowerCut &) {}
    candidate.cut=-1;
    Mounted volume(candidate);Store store(&volume.fs);Root root{};
    assert(store.read(root)==Result::Ok);
    if(root.serial==before.serial) assert(!memcmp(&root,&before,sizeof(Root)));
    else assert(!memcmp(&root,&after,sizeof(Root)));
  }
  return 2*(writes+1);
}
static Root snapshot(Flash &flash) {
  Mounted volume(flash);Store store(&volume.fs);Root root{};assert(store.read(root)==Result::Ok);return root;
}
int main() {
  Flash baseline;std::vector<uint8_t> package(700000,0x35),nextPackage(810000,0x79);
  std::vector<uint8_t> first(64,0x12),next(65,0x23),migrated(128,0x34);
  { Mounted volume(baseline,true);Store store(&volume.fs);
    assert(store.commit(nullptr,0,first.data(),first.size())==Result::Missing);
    assert(store.commit(package.data(),package.size(),first.data(),first.size())==Result::Ok);
    assert(store.accept()==Result::Missing); }
  Root before=snapshot(baseline);
  Flash checkpoint=baseline;uint64_t checkpointPrograms=checkpoint.programmed;
  Action save=[&](Store &store){ return store.commit(nullptr,0,next.data(),next.size()); };
  { Mounted volume(checkpoint);Store store(&volume.fs);assert(save(store)==Result::Ok);
    assert(store.packageWrites()==0 && store.dataWrites()==next.size()); }
  checkpointPrograms=checkpoint.programmed-checkpointPrograms;
  Root saved=snapshot(checkpoint);
  assert(saved.current.package==before.current.package && saved.current.data!=before.current.data);
  unsigned cases=interruptionMatrix(baseline,save,before,saved);
  Flash upgrade=checkpoint;
  Action update=[&](Store &store){return store.commit(nextPackage.data(),nextPackage.size(),migrated.data(),migrated.size());};
  { Mounted volume(upgrade);Store store(&volume.fs);assert(update(store)==Result::Ok);
    assert(store.packageWrites()==nextPackage.size()); }
  Root updated=snapshot(upgrade);
  assert(!memcmp(&updated.previous,&saved.current,sizeof(Pair)));
  cases+=interruptionMatrix(checkpoint,update,saved,updated);
  Flash rollback=upgrade;
  { Mounted volume(rollback);Store store(&volume.fs);assert(store.rollback()==Result::Ok); }
  Root rolledBack=snapshot(rollback);assert(!memcmp(&rolledBack.current,&saved.current,sizeof(Pair)));
  cases+=interruptionMatrix(upgrade,[](Store &s){return s.rollback();},updated,rolledBack);
  Flash accepted=upgrade;
  { Mounted volume(accepted);Store store(&volume.fs);assert(store.accept()==Result::Ok); }
  Root acceptedRoot=snapshot(accepted);
  cases+=interruptionMatrix(upgrade,[](Store &s){return s.accept();},updated,acceptedRoot);
  { Mounted volume(upgrade);Store store(&volume.fs);
    assert(update(store)==Result::Limit);
    assert(save(store)==Result::Ok);Root root{};assert(store.read(root)==Result::Ok);
    assert(!memcmp(&root.previous,&saved.current,sizeof(Pair)));
    assert(store.rollback()==Result::Ok);
    uint8_t data[128]{};uint32_t size=0;assert(store.data(data,sizeof(data),size)==Result::Ok);
    assert(size==next.size() && !memcmp(data,next.data(),size));
    assert(store.commit(nullptr,0,nullptr,Store::MaximumData+1)==Result::Invalid);
    assert(store.commit(nullptr,0,nullptr,0)==Result::Ok);
    assert(store.data(nullptr,0,size)==Result::Ok && size==0);
  }
  // Many saves reclaim only unreferenced blobs; the package stays immutable.
  { Mounted volume(checkpoint);Store store(&volume.fs);
    for(unsigned i=0;i<100;i++) assert(save(store)==Result::Ok);
    assert(store.packageWrites()==0); }
  // Errors, unknown formats and damaged data must fail closed, without a format.
  { Flash corrupt=baseline;Mounted volume(corrupt);Store store(&volume.fs);
    uint8_t cache[2048]{};lfs_file_config config{};config.buffer=cache;lfs_file_t file{};
    assert(lfs_file_opencfg(&volume.fs,&file,"x/active",LFS_O_WRONLY,&config)==0);
    const uint8_t invalid=0;assert(lfs_file_write(&volume.fs,&file,&invalid,1)==1);
    assert(lfs_file_close(&volume.fs,&file)==0);int writes=corrupt.writes;
    assert(save(store)==Result::Corrupt && corrupt.writes==writes); }
  // Capacity exhaustion: keep all published roots unchanged after failure.
  { Flash full=baseline;Mounted volume(full);Store store(&volume.fs);
    uint8_t cache[2048]{},payload[2048]{};lfs_file_config config{};config.buffer=cache;
    for(unsigned i=0;i<1024;i++) {
      char name[24];snprintf(name,sizeof(name),"filler%u",i);lfs_file_t file{};
      int rc=lfs_file_opencfg(&volume.fs,&file,name,LFS_O_WRONLY|LFS_O_CREAT,&config);
      if(rc<0) break;
      bool filled=false;
      for(unsigned j=0;j<32;j++) if(lfs_file_write(&volume.fs,&file,payload,sizeof(payload))!=sizeof(payload)) { filled=true;break; }
      lfs_file_close(&volume.fs,&file);if(filled) break;
    }
    assert(update(store)!=Result::Ok);Root root{};assert(store.read(root)==Result::Ok);
    assert(!memcmp(&root,&before,sizeof(Root))); }
  printf("{\"status\":\"passed\",\"interruption_cases\":%u,\"package_bytes\":%zu,\"checkpoint_data_bytes\":%zu,\"checkpoint_package_writes\":0,\"checkpoint_programmed_bytes\":%llu,\"store_object_bytes\":%zu,\"root_bytes\":%u,\"physical\":\"not_tested\"}\n",
         cases,package.size(),next.size(),static_cast<unsigned long long>(checkpointPrograms),sizeof(Store),Store::RootBytes);
}

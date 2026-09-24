// SPDX-License-Identifier: GPL-3.0-or-later
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
static void finish(Volume &v) {
  for(unsigned n=0;n<20000 && v.state()!=State::Complete && v.state()!=State::Failed;n++)v.step();
  assert(v.state()==State::Complete);
}
int main() {
  Flash base;std::vector<uint8_t> package(MaximumPackage,0x42),data(MaximumData,0x37);Root original;
  {auto v=std::make_unique<Volume>(base.backend());
    assert(v->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char id[49]){strcpy(id,"unused");return true;}));
    assert(v->begin("document",package.data(),468,data.data(),123));finish(*v);uint32_t version[3]={1,0,0};
    assert(v->beginCheckpoint("document",data.data(),123,version,0));finish(*v);assert(v->documentRoot("document",&original));
  }
  // Consume real blocks using unrelated files. Leave exactly the requested
  // space above the protected 24-block reserve, without changing any counters.
  unsigned files=0;
  {Raw raw(base);uint8_t content[2048]{};constexpr unsigned target=BlockCount-2-ReserveBlocks-3;
    while(unsigned(lfs_fs_size(&raw.fs))<target) {
      assert(files<512);char name[32];snprintf(name,sizeof(name),"headroom-%u",files++);
      lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
      assert(!lfs_file_opencfg(&raw.fs,&file,name,LFS_O_CREAT|LFS_O_WRONLY,&cfg));
      assert(lfs_file_write(&raw.fs,&file,content,sizeof(content))==sizeof(content));assert(!lfs_file_close(&raw.fs,&file));
    }
    while(unsigned(lfs_fs_size(&raw.fs))>target) {
      assert(files);char name[32];snprintf(name,sizeof(name),"headroom-%u",--files);raw.remove(name);
    }
    assert(unsigned(lfs_fs_size(&raw.fs))==target);
  }
  for(unsigned available:{3u,4u}) {
    Flash f=base;
    if(available==4) {Raw raw(f);char name[32];snprintf(name,sizeof(name),"headroom-%u",files-1);raw.remove(name);}
    auto v=std::make_unique<Volume>(f.backend());assert(v->mount());Space space;assert(v->space(&space));
    assert(space.available==available*BlockBytes);
    assert(v->beginStream("document","empty",PrimeG2::AppFileStore::Store::StreamMode::Truncate));
    for(unsigned n=0;n<20000 && !v->fileWritable() && v->state()!=State::Failed;n++)v->step();assert(v->fileWritable());
    int writes=f.writes;assert(v->commitFile());
    for(unsigned n=0;n<20000 && v->state()!=State::Complete && v->state()!=State::Failed;n++)v->step();
    Root after;assert(v->documentRoot("document",&after));
    if(available==3) {
      if(v->state()!=State::Failed)fprintf(stderr,"stream commit accepted without the FILE5 payload reserve\n");
      assert(v->state()==State::Failed && v->fileError()==LFS_ERR_NOSPC && f.writes==writes && after.serial==original.serial);
    } else {
      assert(v->state()==State::Complete && after.serial==original.serial+1);
      assert(v->space(&space) && space.allocated<=space.capacity);
    }
    assert(v->read("document",package.data(),package.size(),data.data(),data.size()));
    for(unsigned n=0;n<123;n++)assert(data[n]==0x37);
  }
  puts("{\"status\":\"passed\",\"boundary_cases\":2,\"reserved_blocks\":24}");
}

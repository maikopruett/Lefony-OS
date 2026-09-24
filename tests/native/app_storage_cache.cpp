// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_storage.h"
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
using Root=PrimeG2::AppDocumentRoot::Root;
#include "app_raw_fixture.h"
int main() {
  Flash flash;
  std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  {auto volume=std::make_unique<Volume>(flash.backend());
   assert(volume->initialize(package.data(),package.size(),data.data(),data.size(),
     [](const uint8_t *,size_t,char id[49]) {strcpy(id,"cache");return true;}));}
  uint64_t oldReads=0;
  {Raw raw(flash);assert(!lfs_mkdir(&raw.fs,"cache"));
   uint8_t payload[2048]{};
   for(unsigned i=0;i<180;i++) {
     char path[64];snprintf(path,sizeof(path),"cache/c%08x.00000001",i+1);
     lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
     assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_EXCL,&config));
     assert(lfs_file_write(&raw.fs,&file,payload,sizeof(payload))==sizeof(payload));
     assert(!lfs_file_close(&raw.fs,&file));
   }}
  int writes=flash.writes;
  {Raw raw(flash);flash.reads=0;
   assert(!lfs_fs_traverse(&raw.fs,[](void *,lfs_block_t){return 0;},nullptr));oldReads=flash.reads;}
  uint64_t newReads=0;
  {auto volume=std::make_unique<Volume>(flash.backend());assert(volume->mount());flash.reads=0;
   Space space;assert(volume->space(&space));newReads=flash.reads;
   assert(space.allocated>=180*BlockBytes);}
  assert(flash.writes==writes); // Same existing filesystem, with no migration.
  printf("{\"old_page_reads\":%llu,\"new_page_reads\":%llu}\n",
    (unsigned long long)oldReads,(unsigned long long)newReads);fflush(stdout);
  assert(newReads*2<oldReads);
}

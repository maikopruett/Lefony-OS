// SPDX-License-Identifier: GPL-3.0-or-later
// Failed page reads must never populate a reusable littlefs cache entry.
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

struct ReadFailure:Flash {
  uint32_t page=UINT32_MAX;
  int error=LFS_ERR_IO,failed=0;
  bool poison=false;
};

int main() {
  ReadFailure baseline;
  {Volume volume(baseline.backend());std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
    assert(volume.initialize(package.data(),package.size(),data.data(),data.size(),
      [](const uint8_t *,size_t,char id[49]) {strcpy(id,"unused");return true;}));
  }
  std::vector<uint8_t> content(2*PageBytes);
  for(unsigned i=0;i<content.size();i++) content[i]=uint8_t((i*131+(i>>8))^0x5d);
  {Raw raw(baseline);lfs_file_t file{};lfs_file_config config{};uint8_t cache[PageBytes];config.buffer=cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,"read-errors",LFS_O_WRONLY|LFS_O_CREAT|LFS_O_EXCL,&config));
    assert(lfs_file_write(&raw.fs,&file,content.data(),content.size())==int(content.size()));
    assert(!lfs_file_close(&raw.fs,&file));
  }
  unsigned cases=0;
  for(int error:{LFS_ERR_IO,LFS_ERR_CORRUPT}) for(bool poison:{false,true}) for(unsigned offset:{0u,PageBytes+17u}) {
    ReadFailure flash=baseline;int writes=flash.writes;
    {Raw raw(flash);raw.c.read=[](const lfs_config *cfg,lfs_block_t block,lfs_off_t off,void *out,lfs_size_t bytes) {
        auto &f=*static_cast<ReadFailure *>(cfg->context);
        assert(off%PageBytes==0 && bytes%PageBytes==0);
        for(unsigned i=0;i<bytes;i+=PageBytes) {
          uint32_t page=(FirstBlock+2+block)*PagesPerBlock+(off+i)/PageBytes;
          if(page==f.page) {
            // Both untouched and partially overwritten failure buffers are
            // legal backend outcomes; neither carries readable file bytes.
            if(f.poison) memset(static_cast<uint8_t *>(out)+i,0xa5,PageBytes/2);
            f.failed++;return f.error;
          }
          if(!Flash::read(&f,page,static_cast<uint8_t *>(out)+i)) return int(LFS_ERR_IO);
        }
        return 0;
      };
      lfs_file_t file{};lfs_file_config config{};uint8_t cache[PageBytes],got[64];config.buffer=cache;
      memset(cache,0x37,sizeof(cache));
      assert(!lfs_file_opencfg(&raw.fs,&file,"read-errors",LFS_O_RDONLY,&config));
      assert(!(file.flags&LFS_F_INLINE) && file.ctz.size<BlockBytes);
      assert(lfs_file_seek(&raw.fs,&file,offset,LFS_SEEK_SET)==int(offset));
      flash.page=(FirstBlock+2+file.ctz.head)*PagesPerBlock+offset/PageBytes;
      flash.error=error;flash.poison=poison;
      for(unsigned attempt=0;attempt<3;attempt++) {
        memset(got,0xc7,sizeof(got));int reads=flash.failed;
        int result=lfs_file_read(&raw.fs,&file,got,sizeof(got));
        if(result!=error) fprintf(stderr,"failed cache read returned %d, expected %d, attempt %u\n",result,error,attempt);
        assert(result==error && flash.failed>reads);
        assert(lfs_file_tell(&raw.fs,&file)==int(offset));
        for(auto byte:got) assert(byte==0xc7);
      }
      flash.page=UINT32_MAX;
      assert(lfs_file_read(&raw.fs,&file,got,sizeof(got))==sizeof(got));
      assert(!memcmp(got,content.data()+offset,sizeof(got)));
      assert(!lfs_file_close(&raw.fs,&file));
    }
    assert(flash.writes==writes && flash.pages==baseline.pages);cases++;
  }
  printf("{\"retry_cases\":%u,\"status\":\"passed\"}\n",cases);
}

// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_developer_key_snapshot.h"
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
namespace Keys=PrimeG2::AppDeveloperKeys;
using Keys::Result;
using KeyStore=Keys::Store;
#include "app_key_fault_fixture.h"
using Capture=Keys::Snapshot;

struct MediaFlash:KeyFlash {std::set<uint32_t> unreadable;unsigned failedReads=0;};
struct MediaMounted:Mounted {
  explicit MediaMounted(MediaFlash &flash):Mounted(flash) {
    c.read=[](const lfs_config *cfg,lfs_block_t block,lfs_off_t off,void *out,lfs_size_t bytes) {
      auto &f=*static_cast<MediaFlash *>(static_cast<KeyFlash *>(cfg->context));
      assert(off%PageBytes==0 && bytes%PageBytes==0);
      for(unsigned i=0;i<bytes;i+=PageBytes) {
        uint32_t page=(FirstBlock+2+block)*PagesPerBlock+(off+i)/PageBytes;
        if(f.unreadable.count(page)) {
          memset(static_cast<uint8_t *>(out)+i,0xa5,PageBytes/2);f.failedReads++;return int(LFS_ERR_IO);
        }
        if(!KeyFlash::read(&f,page,static_cast<uint8_t *>(out)+i)) return int(LFS_ERR_IO);
      }
      return 0;
    };
  }
};
static void capture(Capture &s) {
  assert(s.begin()==Result::Busy);
  for(unsigned i=0;i<Capture::MaximumChunks+4 && s.state()==Capture::State::Running;i++) s.step();
}
static std::vector<uint8_t> fileBytes(MediaFlash &flash,const char *path) {
  MediaMounted raw(flash);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&config));
  int size=lfs_file_size(&raw.fs,&file);assert(size>=0);std::vector<uint8_t> data(size);
  assert(lfs_file_read(&raw.fs,&file,data.data(),size)==size && !lfs_file_close(&raw.fs,&file));return data;
}
static uint32_t firstPage(MediaFlash &flash) {
  MediaMounted raw(flash);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,KeyStore::Path,LFS_O_RDONLY,&config));
  assert(!(file.flags&LFS_F_INLINE) && file.ctz.size<BlockBytes);
  uint32_t page=(FirstBlock+2+file.ctz.head)*PagesPerBlock;
  assert(!lfs_file_close(&raw.fs,&file));return page;
}
static std::vector<uint8_t> exported(Capture &s,unsigned width) {
  Capture::Info info;assert(s.info(&info));std::vector<uint8_t> result(info.bytes);
  for(unsigned offset=0;offset<result.size();) {
    unsigned n=result.size()-offset;if(n>width) n=width;
    assert(s.read(offset,result.data()+offset,n)==int(n));offset+=n;
  }
  uint8_t hash[32];PrimeG2::NativeAppHash::sha256(result.data(),result.size(),hash);
  assert(!memcmp(hash,info.hash,32));return result;
}
int main(int argc,char **argv) {
  assert(argc==3);uint8_t modulus[256];FILE *input=fopen(argv[1],"rb");
  assert(input && fread(modulus,1,256,input)==256 && !fclose(input));
  MediaFlash base;
  {auto volume=std::make_unique<Volume>(base.backend());std::vector<uint8_t> p(MaximumPackage),d(MaximumData);
    assert(volume->initialize(p.data(),p.size(),d.data(),d.size(),[](const uint8_t *,size_t,char id[49]) {strcpy(id,"unused");return true;}));
    memset(p.data(),0x42,468);memset(d.data(),0x67,123);
    assert(volume->begin("unrelated",p.data(),468,d.data(),123));
    for(unsigned i=0;i<10000 && volume->state()!=State::Complete;i++) volume->step();
    assert(volume->state()==State::Complete);
  }
  {MediaMounted raw(base);KeyStore keys(&raw.fs);assert(keys.beginEnroll(0,modulus,"Original",8)==Result::Busy);finish(keys);}
  auto original=fileBytes(base,KeyStore::Path),app=fileBytes(base,"apps/unrelated.app");uint32_t page=firstPage(base);
  char originalPath[512];snprintf(originalPath,sizeof(originalPath),"%s/registry-original.keys",argv[2]);
  FILE *originalOut=fopen(originalPath,"wb");
  assert(originalOut && fwrite(original.data(),1,original.size(),originalOut)==original.size() && !fclose(originalOut));
  unsigned captures=0,cuts=0,cancellations=0;
  for(unsigned mask:{1u,2u,3u}) {
    MediaFlash damaged=base;for(unsigned bit=0;bit<2;bit++) if(mask&(1u<<bit)) damaged.unreadable.insert(page+bit);
    int writes=damaged.writes;MediaFlash completed=damaged;
    {MediaMounted raw(completed);KeyStore keys(&raw.fs);assert(keys.load()==Result::Io && !keys.current());
      Capture s(&raw.fs);capture(s);Capture::Info info;
      assert(s.state()==Capture::State::Ready && s.info(&info) && info.originalBytes==Keys::WireBytes);
      assert(info.unreadableChunks==(mask==1?4u:mask==2?2u:6u));
      assert(info.readableBytes==(mask==1?Keys::WireBytes-PageBytes:mask==2?PageBytes:0u));
      assert(completed.writes==writes && completed.pages==base.pages);
      auto bytes=exported(s,512);assert(exported(s,1)==bytes && exported(s,511)==bytes);
      char path[512];snprintf(path,sizeof(path),"%s/snapshot-%u.keys",argv[2],mask);
      FILE *out=fopen(path,"wb");assert(out && fwrite(bytes.data(),1,bytes.size(),out)==bytes.size() && !fclose(out));
      uint8_t expected[32];memcpy(expected,info.hash,32);expected[0]^=1;
      assert(keys.beginRepairSnapshot(s,expected,modulus,"Recovered",9)==Result::Stale && completed.writes==writes);
      expected[0]^=1;assert(keys.beginRepairSnapshot(s,expected,modulus,"Recovered",9)==Result::Busy);
      assert(!s.info(&info));finish(keys);
      assert(keys.current()->serial==1 && keys.current()->count==1 && !strcmp(keys.current()->keys[0].label,"Recovered"));
      assert(keys.beginRepairSnapshot(s,expected,modulus,"Again",5)==Result::Invalid);
    }
    int changed=completed.writes-writes;assert(changed>0);completed.unreadable.clear();
    auto repaired=fileBytes(completed,KeyStore::Path);assert(repaired!=original && fileBytes(completed,"apps/unrelated.app")==app);
    for(bool torn:{false,true}) for(int cut=0;cut<=changed;cut++) {
      MediaFlash trial=damaged;trial.cut=trial.writes+cut;trial.torn=torn;
      try {MediaMounted raw(trial);Capture s(&raw.fs);capture(s);Capture::Info info;assert(s.info(&info));
        KeyStore keys(&raw.fs);assert(keys.beginRepairSnapshot(s,info.hash,modulus,"Recovered",9)==Result::Busy);finish(keys);
      } catch(PowerCut &) {}
      trial.reboot();trial.unreadable.clear();auto selected=fileBytes(trial,KeyStore::Path);
      assert(selected==original || selected==repaired);assert(fileBytes(trial,"apps/unrelated.app")==app);cuts++;
    }
    for(unsigned stop=0;stop<12;stop++) {
      MediaFlash trial=damaged;MediaMounted raw(trial);Capture s(&raw.fs);assert(s.begin()==Result::Busy);
      for(unsigned i=0;i<stop && s.state()==Capture::State::Running;i++) s.step();
      if(s.state()==Capture::State::Running) {s.cancel();assert(s.state()==Capture::State::Cancelled);}
      Capture::Info info;if(s.info(&info)) {
        KeyStore keys(&raw.fs);assert(keys.beginRepairSnapshot(s,info.hash,modulus,"Recovered",9)==Result::Busy);
        assert(keys.cancel());
      }
      assert(trial.writes==writes && trial.pages==base.pages);cancellations++;
    }
    captures++;
  }
  {MediaFlash changed=base;changed.unreadable.insert(page);MediaMounted raw(changed);Capture s(&raw.fs);capture(s);
    Capture::Info before;assert(s.info(&before));changed.unreadable.clear();capture(s);
    assert(s.state()==Capture::State::Failed && s.result()==Result::Readable); // readable again: no blind reset
    changed.unreadable.insert(page+1);capture(s);Capture::Info after;assert(s.info(&after));
    assert(memcmp(before.hash,after.hash,32));KeyStore keys(&raw.fs);
    assert(keys.beginRepairSnapshot(s,before.hash,modulus,"Recovered",9)==Result::Stale && changed.writes==base.writes);
  }
  unsigned boundaries=0;
  for(unsigned size:{0u,1u,256u,257u,512u,513u,65536u,65537u}) {
    MediaFlash flash=base;
    {MediaMounted raw(flash);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
      assert(!lfs_file_opencfg(&raw.fs,&file,KeyStore::Path,LFS_O_WRONLY|LFS_O_TRUNC,&config));
      std::vector<uint8_t> data(size,0x39);assert(lfs_file_write(&raw.fs,&file,data.data(),size)==int(size));
      assert(!lfs_file_close(&raw.fs,&file));
    }
    int writes=flash.writes;
    {MediaMounted raw(flash);Capture s(&raw.fs);capture(s);
      assert(s.state()==Capture::State::Failed && s.result()==(size>65536?Result::Invalid:Result::Readable));
      assert(flash.writes==writes);
    }
    if(size>256 && size<=65536) {
      uint32_t first=firstPage(flash);flash.unreadable.insert(first);
      MediaMounted raw(flash);Capture s(&raw.fs);assert(s.begin()==Result::Busy && s.begin()==Result::Busy);
      // A second begin cannot erase the active capture's progress.
      while(s.state()==Capture::State::Running)s.step();Capture::Info info;assert(s.info(&info));
      assert(info.originalBytes==size && info.readableBytes==(size>PageBytes?size-PageBytes:0u));
      auto bytes=exported(s,511);assert(bytes.size()==info.bytes && flash.writes==writes);
      KeyStore other(nullptr);assert(other.beginRepairSnapshot(s,info.hash,modulus,"Recovered",9)==Result::Invalid);
      if(size==65536) {
        flash.unreadable.insert(first+1);std::vector<uint8_t> block(512);
        // The first readable record follows four omitted 512-byte regions.
        assert(s.read(Capture::HeaderBytes+5*Capture::RecordHeaderBytes,block.data(),512)<0);
      }
    }
    boundaries++;
  }
  {MediaFlash flash=base;MediaMounted raw(flash);assert(!lfs_remove(&raw.fs,KeyStore::Path));
    int writes=flash.writes;Capture s(&raw.fs);capture(s);
    assert(s.result()==Result::Missing && flash.writes==writes);boundaries++;
  }
  {Capture s(nullptr);capture(s);assert(s.result()==Result::Io);boundaries++;}
  printf("{\"captures\":%u,\"interruption_cases\":%u,\"cancellation_cases\":%u,\"boundary_cases\":%u,\"snapshot_bytes\":%zu}\n",captures,cuts,cancellations,boundaries,sizeof(Capture));
}

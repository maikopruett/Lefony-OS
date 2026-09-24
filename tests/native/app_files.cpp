// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_storage.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
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
constexpr uint32_t Chunk=PrimeG2::AppFileIndex::ChunkBytes;
static std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
static bool initialize(Volume &v) {
  return v.initialize(package.data(),package.size(),data.data(),data.size(),
    [](const uint8_t *,size_t,char id[49]) { strcpy(id,"files");return true; });
}
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
static void writable(Volume &v) {
  for(unsigned i=0;i<200000 && !v.fileWritable() && v.state()!=State::Failed;i++) v.step();
  assert(v.fileWritable());
}
static uint8_t pattern(uint32_t offset) { return (offset*131u+(offset>>8))^0x5d; }
static void feed(Volume &v,uint32_t bytes,bool patch=false) {
  uint8_t buffer[2048];uint32_t offset=0;
  while(offset<bytes) {
    writable(v);uint32_t n=bytes-offset;if(n>sizeof(buffer)) n=sizeof(buffer);
    for(unsigned i=0;i<n;i++) buffer[i]=patch?0xa7:pattern(offset+i);
    int used=v.writeFile(buffer,n);assert(used>0);offset+=used;
  }
  writable(v);assert(v.commitFile());finish(v);
}
static Flash baseline() {
  Flash flash;auto v=std::make_unique<Volume>(flash.backend());assert(initialize(*v));
  uint8_t app[468];memset(app,0x56,sizeof(app));uint32_t value=42,version[3]={1,0,0};
  for(const char *id: {"files","other"}) {
    assert(v->begin(id,app,sizeof(app),reinterpret_cast<uint8_t *>(&value),4));finish(*v);
  }
  assert(v->beginCheckpoint("files",reinterpret_cast<uint8_t *>(&value),4,version,0));finish(*v);
  return flash;
}
static std::string hashFile(Volume &v,const char *name="data.bin") {
  if(!v.openFile("files",name)) return "absent";
  PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);uint8_t bytes[2048];
  for(;;) { int n=v.readFile(bytes,sizeof(bytes));assert(n>=0);if(!n) break;PrimeG2::NativeAppHash::shaUpdate(&hash,bytes,n); }
  assert(v.closeReader());uint8_t digest[32];PrimeG2::NativeAppHash::shaFinal(&hash,digest);
  char hex[65];for(unsigned i=0;i<32;i++) snprintf(hex+2*i,3,"%02x",digest[i]);return hex;
}
static std::vector<uint8_t> rootBytes(Volume &v) {
  Root root;if(!v.documentRoot("files",&root)) return {};std::vector<uint8_t> bytes(240);
  assert(PrimeG2::AppDocumentRoot::encode(root,bytes.data()));return bytes;
}
static void privateData(Volume &v,uint32_t expected=42,const char *id="files") {
  Entry entry;assert(v.entry(id,&entry) && entry.dataBytes==4 && entry.packageBytes==468);
  assert(v.read(id,package.data(),package.size(),data.data(),data.size()));
  uint32_t value;memcpy(&value,data.data(),4);assert(value==expected);
  for(unsigned i=0;i<468;i++) assert(package[i]==0x56);
}
using Action=std::function<void(Volume &)>;
using ReaderState=PrimeG2::AppFileStore::Reader::State;
using StreamMode=PrimeG2::AppFileStore::Store::StreamMode;
static constexpr int Pending=PrimeG2::AppFileStore::Store::Pending;
static unsigned verificationSteps=0;
static uint32_t growingInputBytes=0,growingOutputBytes=0,fullAcceptedBytes=0;
static std::string growingOutputHash;
static int snapshotRead(Volume &v,uint32_t token,void *out,uint32_t count,const char *id="files") {
  int n=v.readSnapshot(id,token,out,count);
  if(n==PrimeG2::AppFileStore::Reader::Pending) {
    Volume::SnapshotInfo info;assert(v.snapshotInfo(id,token,&info) && info.verifiedBytes==0);
    unsigned steps=0;
    while(info.state==ReaderState::Verifying) {
      uint32_t before=info.verifiedBytes;assert(v.stepSnapshot(id,token));
      assert(v.snapshotInfo(id,token,&info) && info.verifiedBytes>=before && info.verifiedBytes-before<=2048);
      assert(++steps<=66);verificationSteps++;
    }
    n=v.readSnapshot(id,token,out,count);
  }
  return n;
}
static void snapshotPattern(Volume &v,uint32_t token,uint32_t offset,uint32_t count,bool changed=false) {
  assert(v.seekSnapshot("files",token,offset));uint8_t buffer[2048];uint32_t read=0;
  while(read<count) {
    uint32_t n=count-read;if(n>sizeof(buffer)) n=sizeof(buffer);
    int got=snapshotRead(v,token,buffer,n);assert(got>0);
    for(int i=0;i<got;i++) assert(buffer[i]==(changed?0xa7:pattern(offset+read+i)));
    read+=got;
  }
}
static void snapshots(const Flash &saved,uint32_t bytes) {
  Flash trial=saved;std::string oldPath;
  {
    auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));Root root;
    assert(v->documentRoot("files",&root));char path[80];
    snprintf(path,sizeof(path),"objects/files/c%08x.00000001",root.current.data);oldPath=path;
    uint32_t old=v->openSnapshot("files","data.bin"),second=v->openSnapshot("files","data.bin");assert(old && second);
    uint32_t third=v->openSnapshot("files","data.bin"),fourth=v->openSnapshot("files","data.bin");assert(third && fourth);
    assert(!v->openSnapshot("files","data.bin"));uint8_t byte=0x6b;Volume::SnapshotInfo info;
    assert(v->readSnapshot("other",old,&byte,1)==-1 && byte==0x6b);
    assert(!v->seekSnapshot("other",old,0) && !v->stepSnapshot("other",old) && !v->closeSnapshot("other",old));
    assert(!v->snapshotInfo("other",old,&info) && v->readSnapshot("files",0,&byte,1)==-1);
    assert(v->closeSnapshot("files",third));uint32_t replacement=v->openSnapshot("files","data.bin");
    assert(replacement && replacement!=third && !v->closeSnapshot("files",third));
    assert(v->readSnapshot("files",third,&byte,1)==-1 && !v->stepSnapshot("files",third));
    assert(v->closeSnapshot("files",replacement) && v->closeSnapshot("files",fourth));
    // No output is exposed while the first chunk is still being verified.
    assert(v->readSnapshot("files",old,&byte,1)==PrimeG2::AppFileStore::Reader::Pending && byte==0x6b);
    assert(!v->seekSnapshot("files",old,19));
    assert(v->snapshotInfo("files",old,&info) && info.position==0 && info.verifiedBytes==0);
    // Advance one independent reader while the writer prepares and verifies.
    assert(v->beginFile("files","copy.bin",bytes));assert(!v->openSnapshot("files","data.bin"));
    while(!v->fileWritable()) {v->step();assert(v->stepSnapshot("files",old));assert(v->state()!=State::Failed);}
    assert(v->snapshotInfo("files",old,&info) && info.state==ReaderState::Ready);
    uint32_t during=v->openSnapshot("files","data.bin");assert(during);
    assert(v->readSnapshot("files",during,&byte,1)==PrimeG2::AppFileStore::Reader::Pending);
    assert(v->stepSnapshot("files",during));
    assert(v->snapshotInfo("files",during,&info) && info.verifiedBytes==2048);
    assert(v->closeSnapshot("files",during));uint8_t buffer[2048];uint32_t copied=0;
    while(copied<bytes) {
      int n=snapshotRead(*v,old,buffer,sizeof(buffer));assert(n>0);
      for(int i=0;i<n;i++) { assert(buffer[i]==pattern(copied+i));buffer[i]^=0x3c; }
      uint32_t written=0;
      while(written<static_cast<uint32_t>(n)) {
        writable(*v);int used=v->writeFile(buffer+written,n-written);assert(used>0);written+=used;
      }
      copied+=n;
    }
    writable(*v);assert(v->commitFile());finish(*v);assert(!v->checkpointPackageWrites());
    assert(v->snapshotInfo("files",second,&info) && info.position==0);
    assert(v->readSnapshot("files",old,buffer,1)==0 && v->readSnapshot("files",old,nullptr,0)==0);
    assert(v->readSnapshot("files",old,nullptr,1)==-1 && v->readSnapshot("files",old,buffer,2049)==-1);
    assert(v->seekSnapshot("files",old,bytes+1) && v->readSnapshot("files",old,buffer,1)==0);
    assert(!v->seekSnapshot("files",old,64*1024*1024+1));
    // Old readers survive replacement, rename, unlink and several more commits.
    assert(v->beginFile("files","data.bin",bytes));feed(*v,bytes,true);
    uint32_t fresh=v->openSnapshot("files","data.bin");assert(fresh);
    snapshotPattern(*v,fresh,Chunk-9,33,true);assert(v->closeSnapshot("files",fresh));
    assert(v->changeFile("files","data.bin","renamed.bin"));finish(*v);
    assert(!v->openSnapshot("files","data.bin"));
    assert(v->changeFile("files","renamed.bin"));finish(*v);
    assert(!v->openSnapshot("files","renamed.bin"));
    for(unsigned i=0;i<3;i++) { assert(v->beginFile("files","scratch.bin",11));feed(*v,11,true); }
    snapshotPattern(*v,old,0,bytes);snapshotPattern(*v,second,Chunk+17,41);
    assert(!v->begin("files",nullptr,0,nullptr,0));privateData(*v);privateData(*v,42,"other");
    // A cold reader must observe the independently transformed output.
    assert(v->closeSnapshots("files"));assert(!v->snapshotInfo("files",old,&info));
  }
  { Raw raw(trial);assert(raw.exists(oldPath.c_str())); }
  {
    auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));
    uint32_t token=v->openSnapshot("files","copy.bin");assert(token);uint8_t buffer[2048];uint32_t offset=0;
    for(;;) { int n=snapshotRead(*v,token,buffer,sizeof(buffer));assert(n>=0);if(!n) break;
      for(int i=0;i<n;i++) assert(buffer[i]==(pattern(offset+i)^0x3c));offset+=n;
    }
    assert(offset==bytes);assert(v->mount());assert(v->readSnapshot("files",token,buffer,1)==-1);
    uint32_t next=v->openSnapshot("files","copy.bin");assert(next && next!=token);
    assert(v->closeSnapshot("files",next));
    assert(v->beginFile("files","scratch.bin",11));feed(*v,11,true);
  }
  { Raw raw(trial);assert(!raw.exists(oldPath.c_str())); }
  // Corruption in an untouched later chunk must fail before returning any bytes
  // from it. The failed reader remains closable and cannot poison another one.
  trial=saved;
  { Root root;{auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));assert(v->documentRoot("files",&root));}
    char path[80];snprintf(path,sizeof(path),"objects/files/c%08x.00000002",root.current.data);
    Raw raw(trial);raw.corrupt(path);
  }
  { auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));
    uint32_t token=v->openSnapshot("files","data.bin");assert(token);snapshotPattern(*v,token,0,29);
    assert(v->seekSnapshot("files",token,Chunk));uint8_t byte=0x6b;
    assert(snapshotRead(*v,token,&byte,1)==-1 && byte==0x6b);
    Volume::SnapshotInfo info;assert(v->snapshotInfo("files",token,&info) && info.state==ReaderState::Failed && info.position==Chunk);
    assert(!v->seekSnapshot("files",token,0));assert(v->closeSnapshot("files",token));privateData(*v);
    token=v->openSnapshot("files","data.bin");assert(token);snapshotPattern(*v,token,0,29);
    assert(v->closeSnapshots());
  }
}
static unsigned matrix(const Flash &base,const Action &action) {
  Flash full=base;auto v=std::make_unique<Volume>(full.backend());assert(initialize(*v));
  auto before=rootBytes(*v);auto beforeHash=hashFile(*v);int start=full.writes;
  action(*v);auto after=rootBytes(*v);auto afterHash=hashFile(*v);int mutations=full.writes-start;v.reset();
  assert(mutations>0);
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash trial=base;trial.cut=trial.writes+cut;trial.torn=torn;
    try { auto active=std::make_unique<Volume>(trial.backend());assert(initialize(*active));action(*active); } catch(PowerCut &) {}
    trial.cut=-1;auto recovered=std::make_unique<Volume>(trial.backend());assert(initialize(*recovered));
    auto root=rootBytes(*recovered);auto hash=hashFile(*recovered);
    assert((root==before && hash==beforeHash) || (root==after && hash==afterHash));
    if(!root.empty()) privateData(*recovered);privateData(*recovered,42,"other");
  }
  return 2*(mutations+1);
}
static void streamWrite(Volume &v,const uint8_t *data,uint32_t bytes) {
  for(uint32_t offset=0;offset<bytes;) {
    uint32_t n=bytes-offset;if(n>2048) n=2048;
    int used=v.writeFile(data+offset,n);
    if(used==Pending) { writable(v);continue; }
    assert(used>0);offset+=used;
  }
}
static int streamRead(Volume &v,void *out,uint32_t bytes) {
  int n=v.readFile(out,bytes);
  while(n==Pending) {writable(v);n=v.readFile(out,bytes);}
  return n;
}
static void streamCommit(Volume &v) {writable(v);assert(v.commitFile());finish(v);}
static void checkBytes(Volume &v,const char *name,const std::vector<uint8_t> &expected) {
  uint32_t token=v.openSnapshot("files",name);assert(token);uint8_t buffer[2048];size_t offset=0;
  for(;;) { int n=snapshotRead(v,token,buffer,sizeof(buffer));assert(n>=0);if(!n) break;
    assert(offset+n<=expected.size() && !memcmp(buffer,expected.data()+offset,n));offset+=n;
  }
  assert(offset==expected.size() && v.closeSnapshot("files",token));
}
static unsigned growing(const Flash &base,const Flash &saved,uint32_t bytes) {
  std::vector<uint8_t> content(bytes+13),header={0x4c,0x46,0x57,0x31,0x95,0x04,0,0};
  for(uint32_t i=0;i<content.size();i++) content[i]=pattern(i)^0x3c;
  Action create=[&](Volume &v) {
    assert(v.beginStream("files","data.bin",StreamMode::Truncate));writable(v);
    streamWrite(v,content.data(),content.size());assert(v.fileSize()==content.size());
    assert(v.seekFile(0));streamWrite(v,header.data(),header.size());
    uint8_t got[8]{};assert(v.seekFile(0) && streamRead(v,got,sizeof(got))==8 && !memcmp(got,header.data(),8));
    streamCommit(v);assert(!v.checkpointPackageWrites());
  };
  unsigned cases=matrix(base,create);
  Action extend=[&](Volume &v) {
    uint32_t old=v.openSnapshot("files","data.bin");assert(old);
    assert(v.beginStream("files","data.bin",StreamMode::Update));writable(v);
    assert(v.seekFile(Chunk-3));streamWrite(v,header.data(),header.size());
    assert(v.seekFile(bytes+29));streamWrite(v,header.data(),3);streamCommit(v);
    snapshotPattern(v,old,0,bytes);assert(v.closeSnapshot("files",old));
  };
  cases+=matrix(saved,extend);
  Flash trial=saved;std::vector<uint8_t> expected(bytes+32);
  for(uint32_t i=0;i<bytes;i++) expected[i]=pattern(i);
  memcpy(expected.data()+Chunk-3,header.data(),header.size());memcpy(expected.data()+bytes+29,header.data(),3);
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));extend(*v);}
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));checkBytes(*v,"data.bin",expected);
    assert(!v->beginStream("files","missing.bin",StreamMode::Update) && v->fileError()==LFS_ERR_NOENT);
    assert(!v->beginStream("files","../bad",StreamMode::Truncate) && v->fileError()==LFS_ERR_INVAL);
    assert(v->changeFile("files","folder",nullptr,true));finish(*v);
    assert(!v->beginStream("files","folder",StreamMode::Truncate) && v->fileError()==LFS_ERR_ISDIR);
    assert(v->beginStream("files","data.bin",StreamMode::Append));writable(*v);
    assert(v->seekFile(0));streamWrite(*v,header.data(),header.size());
    expected.insert(expected.end(),header.begin(),header.end());assert(v->filePosition()==expected.size());
    assert(v->seekFile(0));uint8_t got[8];assert(streamRead(*v,got,8)==8);
    assert(!memcmp(got,expected.data(),8));streamCommit(*v);checkBytes(*v,"data.bin",expected);
    // Seeking alone never changes length; a later write materializes zeros.
    assert(v->beginStream("files","gap.bin",StreamMode::Truncate));writable(*v);
    assert(v->seekFile(2*Chunk+7) && v->fileSize()==0 && v->readFile(got,1)==0);
    assert(v->writeFile(nullptr,0)==0 && v->fileSize()==0);
    streamWrite(*v,header.data(),header.size());assert(v->filePosition()==2*Chunk+15);
    assert(v->seekFile(64*1024*1024) && v->writeFile(header.data(),1)==-1 && v->fileError()==LFS_ERR_FBIG);
    assert(!v->seekFile(64*1024*1024+1));streamCommit(*v);
    std::vector<uint8_t> gap(2*Chunk+15);memcpy(gap.data()+2*Chunk+7,header.data(),8);checkBytes(*v,"gap.bin",gap);
    assert(v->beginStream("files","empty.bin",StreamMode::Append));writable(*v);streamCommit(*v);checkBytes(*v,"empty.bin",{});
    privateData(*v);privateData(*v,42,"other");
  }
  // Read the original file while creating a transformed, growing output. No
  // final length is given to the writer; a header is backpatched at the end.
  trial=saved;std::vector<uint8_t> transformed(8);
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));uint32_t input=v->openSnapshot("files","data.bin");assert(input);
    assert(v->beginStream("files","output.bin",StreamMode::Truncate));writable(*v);
    streamWrite(*v,transformed.data(),8);uint8_t buffer[2048];
    for(;;) {int n=snapshotRead(*v,input,buffer,sizeof(buffer));assert(n>=0);if(!n) break;
      // Variable-length records make output size a result of processing.
      for(int i=0;i<n;i++) if(buffer[i]&1) {
        uint8_t record[2]={buffer[i],uint8_t(buffer[i]^0xa5)};streamWrite(*v,record,2);
        transformed.insert(transformed.end(),record,record+2);
      }
    }
    uint32_t resultBytes=transformed.size()-8;memcpy(transformed.data(),header.data(),4);
    for(unsigned i=0;i<4;i++) transformed[4+i]=resultBytes>>(8*i);
    assert(v->seekFile(0));streamWrite(*v,transformed.data(),8);streamCommit(*v);
    assert(v->closeSnapshot("files",input));
  }
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));checkBytes(*v,"output.bin",transformed);
    growingOutputHash=hashFile(*v,"output.bin");growingInputBytes=bytes;growingOutputBytes=transformed.size();
  }
  // Rewriting one staged chunk more than the extent-count bound must neither
  // exhaust generation parts nor mutate a committed snapshot.
  trial=saved;
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));uint32_t token=v->openSnapshot("files","data.bin");assert(token);
    assert(v->beginStream("files","data.bin",StreamMode::Update));writable(*v);
    for(unsigned i=0;i<520;i++) {
      uint8_t b=i;assert(v->seekFile(2*Chunk));streamWrite(*v,&b,1);
      assert(v->seekFile(0));assert(streamRead(*v,&b,1)==1 && b==pattern(0));
    }
    assert(v->fileObjectWrites()==520*37);streamCommit(*v);snapshotPattern(*v,token,2*Chunk,37);
    assert(v->closeSnapshot("files",token));
  }
  // No caller buffer is retained or consumed while loading a chunk. Cancelling
  // after a staged flush discards the whole writer and leaves the old root.
  trial=saved;
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));auto root=rootBytes(*v);
    assert(v->beginStream("files","data.bin",StreamMode::Truncate));writable(*v);uint8_t byte=0x6b;
    assert(v->writeFile(&byte,1)==Pending);byte=0x39;writable(*v);streamWrite(*v,&byte,1);
    assert(v->seekFile(0) && streamRead(*v,&byte,1)==1 && byte==0x39);
    assert(v->seekFile(Chunk+3));streamWrite(*v,&byte,1);assert(v->fileObjectWrites()>=Chunk);v->cancel();
    assert(rootBytes(*v)==root);uint32_t token=v->openSnapshot("files","data.bin");assert(token);
    snapshotPattern(*v,token,0,bytes);assert(v->closeSnapshot("files",token));
    create(*v);auto want=content;memcpy(want.data(),header.data(),8);checkBytes(*v,"data.bin",want);
  }
  // Fill media with an uncommitted output, preserving metadata headroom and the
  // last committed file. The next attempt must collect abandoned chunks first.
  trial=saved;
  {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));auto root=rootBytes(*v);
    uint32_t value=42,version[3]={1,0,0};
    assert(v->beginCheckpoint("other",reinterpret_cast<uint8_t *>(&value),4,version,0));finish(*v);
    assert(v->beginFile("other","occupied.bin",30*1024*1024));feed(*v,30*1024*1024);
    assert(v->beginStream("files","full.bin",StreamMode::Truncate));writable(*v);uint8_t buffer[2048]{};uint32_t written=0;
    for(unsigned guard=0;guard<200000 && v->state()!=State::Failed;guard++) {
      int n=v->writeFile(buffer,sizeof(buffer));
      if(n==Pending) {
        for(unsigned i=0;i<10000 && !v->fileWritable() && v->state()!=State::Failed;i++) v->step();
      } else if(n>0) written+=n;
      else {v->step();assert(v->state()==State::Failed);}
    }
    assert(written>20*1024*1024 && written<32*1024*1024 && v->state()==State::Failed && v->fileError()==LFS_ERR_NOSPC);
    fullAcceptedBytes=written;
    v->cancel();assert(rootBytes(*v)==root);assert(!v->openSnapshot("files","full.bin"));
    Space usage;assert(v->space(&usage) && usage.allocated<=usage.capacity);
    // Even before abandoned output is reclaimed, the reserved maintenance
    // blocks admit a maximum-size package upgrade and a compatible rollback.
    std::vector<uint8_t> upgrade(MaximumPackage,0x59);uint32_t upgradeVersion[3]={2,0,0};
    assert(v->beginUpgrade("files",upgrade.data(),upgrade.size(),upgradeVersion));finish(*v);
    assert(v->beginRollback("files"));finish(*v);privateData(*v);
    assert(v->beginStream("files","full.bin",StreamMode::Truncate));writable(*v);streamWrite(*v,header.data(),8);streamCommit(*v);
    checkBytes(*v,"full.bin",header);privateData(*v);privateData(*v,42,"other");
  }
  return cases;
}
static void large(const char *path) {
  std::ifstream input(path,std::ios::binary|std::ios::ate);assert(input);
  auto size=input.tellg();assert(size>0 && size<=64*1024*1024);input.seekg(0);
  Flash flash=baseline();std::string actual,patched;uint32_t written=0;uint64_t patchPrograms=0;
  { auto v=std::make_unique<Volume>(flash.backend());assert(initialize(*v));
    assert(v->beginStream("files","data.bin",StreamMode::Truncate));
    uint8_t buffer[2048];
    while(written<static_cast<uint32_t>(size)) {
      writable(*v);uint32_t n=static_cast<uint32_t>(size)-written;if(n>sizeof(buffer)) n=sizeof(buffer);
      input.seekg(written);assert(input.read(reinterpret_cast<char *>(buffer),n));
      int used=v->writeFile(buffer,n);if(used==Pending) continue;assert(used>0);written+=used;
    }
    writable(*v);assert(v->commitFile());finish(*v);assert(!v->checkpointPackageWrites());privateData(*v);
  }
  { auto v=std::make_unique<Volume>(flash.backend());assert(initialize(*v));actual=hashFile(*v);
    uint32_t token=v->openSnapshot("files","data.bin");assert(token);uint8_t buffer[2048],digest[32];
    PrimeG2::NativeAppHash::SHA256 hash;PrimeG2::NativeAppHash::shaInit(&hash);
    for(;;) {int n=snapshotRead(*v,token,buffer,sizeof(buffer));assert(n>=0);if(!n) break;
      PrimeG2::NativeAppHash::shaUpdate(&hash,buffer,n);
    }
    PrimeG2::NativeAppHash::shaFinal(&hash,digest);char hex[65];
    for(unsigned i=0;i<32;i++) snprintf(hex+2*i,3,"%02x",digest[i]);assert(actual==hex);
    assert(v->closeSnapshot("files",token));
    assert(v->openFile("files","data.bin"));assert(v->fileSize()==static_cast<uint32_t>(size));
    uint8_t got[31],expected[31];
    for(uint32_t offset: {0u,Chunk-9,Chunk+3,static_cast<uint32_t>(size)-31}) {
      assert(v->seekFile(offset));int n=v->readFile(got,sizeof(got));assert(n>0);
      input.seekg(offset);assert(input.read(reinterpret_cast<char *>(expected),n));assert(!memcmp(got,expected,n));
    }
    assert(v->closeReader());patchPrograms=flash.programmed;
    assert(v->beginFile("files","data.bin",37,true,Chunk+7));feed(*v,37,true);
    assert(v->fileObjectWrites()==Chunk);patchPrograms=flash.programmed-patchPrograms;
    assert(patchPrograms<512*1024 && !v->checkpointPackageWrites());
  }
  { auto v=std::make_unique<Volume>(flash.backend());assert(initialize(*v));assert(v->openFile("files","data.bin"));
    assert(v->seekFile(Chunk+7));uint8_t patch[37];assert(v->readFile(patch,sizeof(patch))==sizeof(patch));
    for(auto b:patch) assert(b==0xa7);assert(v->closeReader());privateData(*v);patched=hashFile(*v);
  }
  printf("{\"status\":\"passed\",\"writer\":\"growing-no-declared-size\",\"input_bytes\":%u,\"read_sha256\":\"%s\",\"snapshot_sha256\":\"%s\",\"snapshot_verification_steps\":%u,\"patched_sha256\":\"%s\",\"stream_buffer_bytes\":2048,\"patch_programmed_bytes\":%llu,\"volume_bytes\":%zu,\"physical\":\"not_tested\"}\n",
    written,actual.c_str(),actual.c_str(),verificationSteps,patched.c_str(),static_cast<unsigned long long>(patchPrograms),sizeof(Volume));
}
int main(int argc,char **argv) {
  if(argc==2) { large(argv[1]);return 0; }assert(argc==1);
  Flash base=baseline();constexpr uint32_t bytes=2*Chunk+37;
  Action create=[](Volume &v) { assert(v.beginFile("files","data.bin",bytes));feed(v,bytes); };
  unsigned cases=matrix(base,create);Flash saved=base;
  {auto v=std::make_unique<Volume>(saved.backend());assert(initialize(*v));create(*v);privateData(*v);}
  snapshots(saved,bytes);
  unsigned growingCases=growing(base,saved,bytes);
  Action patch=[](Volume &v) {
    uint32_t token=v.openSnapshot("files","data.bin");assert(token);
    assert(v.beginFile("files","data.bin",38,true,Chunk-11));feed(v,38,true);assert(v.fileObjectWrites()==2*Chunk);
    snapshotPattern(v,token,Chunk-11,38);assert(v.closeSnapshot("files",token));
  };
  cases+=matrix(saved,patch);
  { Flash trial=saved;auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));patch(*v);
    assert(v->openFile("files","data.bin"));uint8_t buffer[2048];uint32_t offset=0;
    for(;;) {
      int n=v->readFile(buffer,sizeof(buffer));assert(n>=0);if(!n) break;
      for(int i=0;i<n;i++) { uint32_t p=offset+i;assert(buffer[i]==(p>=Chunk-11 && p<Chunk+27?0xa7:pattern(p))); }
      offset+=n;
    }
    assert(offset==bytes && v->closeReader());
  }
  cases+=matrix(saved,[](Volume &v) { assert(v.changeFile("files","data.bin","moved.bin"));finish(v); });
  Flash replacement=saved;
  { auto v=std::make_unique<Volume>(replacement.backend());assert(initialize(*v));
    assert(v->beginStream("files","temporary",StreamMode::Truncate));writable(*v);
    uint8_t content[37];memset(content,0xa7,sizeof(content));streamWrite(*v,content,sizeof(content));streamCommit(*v);
  }
  unsigned replacementCases=matrix(replacement,[](Volume &v) {
    uint32_t old=v.openSnapshot("files","data.bin");assert(old);
    assert(v.changeFile("files","temporary","data.bin"));finish(v);
    snapshotPattern(v,old,0,37);assert(v.closeSnapshot("files",old));
  });
  cases+=replacementCases;
  cases+=matrix(saved,[](Volume &v) { assert(v.changeFile("files","data.bin"));finish(v); });
  cases+=matrix(saved,[](Volume &v) { assert(v.begin("files",nullptr,0,nullptr,0));finish(v); });
  { Flash trial=saved;auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));std::string before=hashFile(*v);
    uint8_t next[468];memset(next,0x99,sizeof(next));uint32_t upgradeVersion[3]={2,0,0};
    assert(v->beginUpgrade("files",next,sizeof(next),upgradeVersion));finish(*v);patch(*v);
    assert(hashFile(*v)!=before);assert(v->beginRollback("files"));finish(*v);
    assert(hashFile(*v)==before);privateData(*v);Root root;assert(v->documentRoot("files",&root));
    assert(root.highVersion[0]==2 && !root.flags && !v->beginUpgrade("files",next,sizeof(next),upgradeVersion));
  }
  { Flash trial=saved;auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));auto before=rootBytes(*v);
    assert(v->beginFile("files","data.bin",100));writable(*v);uint8_t buffer[100]{};assert(v->writeFile(buffer,100)==100);
    v->cancel();assert(rootBytes(*v)==before);create(*v);
    assert(v->openFile("files","data.bin"));assert(!v->beginFile("files","other.bin",1));
    assert(v->seekFile(bytes+1));assert(v->readFile(buffer,1)==0);assert(!v->seekFile(64*1024*1024+1));assert(v->closeReader());
    assert(!v->beginFile("other","../files/data.bin",0));
    assert(!v->beginFile("files","missing/data.bin",0));
    assert(v->changeFile("files","folder",nullptr,true));finish(*v);
    assert(v->beginFile("files","folder/empty.bin",0));writable(*v);assert(v->commitFile());finish(*v);
    assert(v->openFile("files","folder/empty.bin"));assert(v->readFile(buffer,1)==0);assert(v->closeReader());
    assert(!v->changeFile("files","folder"));assert(!v->changeFile("files","folder","folder/child"));
    assert(v->changeFile("files","folder","renamed"));finish(*v);
    assert(!v->openFile("files","folder/empty.bin"));assert(v->openFile("files","renamed/empty.bin"));assert(v->closeReader());
    uint32_t value=73;assert(v->beginCheckpoint("files",reinterpret_cast<uint8_t *>(&value),4,nullptr,0));finish(*v);
    privateData(*v,73);assert(hashFile(*v)!="absent");
    assert(v->changeFile("files","renamed/empty.bin"));finish(*v);assert(v->changeFile("files","renamed"));finish(*v);
  }
  { Flash trial=saved;std::vector<uint8_t> before;std::string hash;
    {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));before=rootBytes(*v);hash=hashFile(*v);}
    {Raw raw(trial);raw.fill();}
    auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));
    uint32_t token=v->openSnapshot("files","data.bin");assert(token);
    assert(v->beginFile("files","extra.bin",1024*1024));
    for(unsigned i=0;i<200000 && !v->fileWritable() && v->state()!=State::Failed;i++) v->step();
    assert(v->state()==State::Failed);v->cancel();assert(rootBytes(*v)==before && hashFile(*v)==hash);
    snapshotPattern(*v,token,Chunk-9,33);assert(v->closeSnapshot("files",token));
  }
  { Flash trial=saved;Root root;
    {auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));assert(v->documentRoot("files",&root));}
    char path[80];snprintf(path,sizeof(path),"objects/files/c%08x.00000001",root.current.data);
    {Raw raw(trial);raw.corrupt(path);}
    int writes=trial.writes;auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));
    assert(v->openFile("files","data.bin"));uint8_t byte;assert(v->readFile(&byte,1)==-1);v->cancel();privateData(*v);
    assert(v->beginFile("files","data.bin",1,true,0));
    for(unsigned i=0;i<200000 && v->state()!=State::Failed;i++) v->step();
    assert(v->state()==State::Failed && trial.writes==writes);
  }
  { Flash trial=base;
    for(uint32_t block=FirstBlock+2;block<FirstBlock+BlockCount;block++) {
      auto first=trial.pages.lower_bound(block*PagesPerBlock);
      if(first==trial.pages.end() || first->first/PagesPerBlock!=block) {trial.bad.insert(block);break;}
    }
    auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));create(*v);privateData(*v);
  }
  // Reclaim interrupted large streams before admission. Otherwise their orphan
  // chunks can prevent a retry even though none belongs to a committed root.
  { Flash trial=base;auto v=std::make_unique<Volume>(trial.backend());assert(initialize(*v));
    assert(v->beginFile("files","large.bin",30*1024*1024));uint8_t buffer[2048]{};uint32_t written=0;
    while(written<28*1024*1024) {writable(*v);int n=v->writeFile(buffer,sizeof(buffer));assert(n>0);written+=n;}
    v->cancel();assert(v->beginFile("files","large.bin",30*1024*1024));writable(*v);v->cancel();privateData(*v);
  }
  printf("{\"status\":\"passed\",\"interruption_cases\":%u,\"replacement_interruption_cases\":%u,\"growing_interruption_cases\":%u,\"growing_input_bytes\":%u,\"growing_output_bytes\":%u,\"growing_output_sha256\":\"%s\",\"full_accepted_bytes_before_abort\":%u,\"snapshot_readers\":%u,\"snapshot_verification_steps\":%u,\"reader_bytes\":%zu,\"stream_buffer_bytes\":2048,\"writer_chunk_buffer_bytes\":%u,\"volume_bytes\":%zu,\"physical\":\"not_tested\"}\n",
    cases,replacementCases,growingCases,growingInputBytes,growingOutputBytes,growingOutputHash.c_str(),fullAcceptedBytes,Volume::MaximumReaders,verificationSteps,sizeof(PrimeG2::AppFileStore::Reader),Chunk,sizeof(Volume));
  return 0;
}

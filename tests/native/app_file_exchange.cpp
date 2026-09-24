// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_file_exchange.h"
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
namespace X=PrimeG2::AppFileExchange;
static uint32_t now=0,privateValue=42,version[3]={1,0,0};
static void finish(Volume &v) {for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();assert(v.state()==State::Complete);}
static X::Identity identity(Volume &v,const char *name="files") {
  Volume::FileUsage usage{};assert(v.fileUsage(name,&usage));X::Identity id{};strcpy(id.id,name);memcpy(id.version,version,12);
  static uint8_t package[MaximumPackage],saved[MaximumData];Entry entry;
  assert(v.entry(name,&entry) && v.read(name,package,sizeof(package),saved,sizeof(saved)));
  id.generation=usage.generation;id.privateBytes=entry.dataBytes;id.privateData=saved;
  id.appSchema=version[0]==2?1:0;
  PrimeG2::NativeAppHash::sha256(package,entry.packageBytes,id.dataInfo.packageHash);
  PrimeG2::AppDocumentRoot::Root root;
  if(v.documentRoot(name,&root)) {
    id.dataSchema=root.current.dataSchema;id.pendingUpgrade=root.flags&PrimeG2::AppDocumentRoot::PendingUpgrade;
    memcpy(id.dataInfo.highVersion,root.highVersion,12);
    if(id.pendingUpgrade) {
      // This core fixture supplies trusted identity; the ARM manager tests
      // exercise the actual signature/schema decision before setting this bit.
      id.dataInfo.flags=X::PendingUpgrade|X::RecoveryTrusted;id.dataInfo.previousPackage=root.previous.package;
      id.dataInfo.previousSchema=root.previous.dataSchema;id.dataInfo.previousVersion[0]=1;
      memcpy(id.dataInfo.previousPackageHash,root.previous.packageHash,32);
    }
  } else memcpy(id.dataInfo.highVersion,version,12);
  return id;
}
static X::Request request(Volume &v,unsigned op,const char *path="",const char *id="files") {
  X::Request r{};r.size=sizeof(r);r.schema=1;r.operation=op;strcpy(r.id,id);strcpy(r.path,path);
  if(op!=X::Inspect && op!=X::InspectData) {
    auto current=identity(v,id);r.generation=current.generation;r.dataSchema=current.dataSchema;
  }
  return r;
}
static X::Status status(X::Session &s) {
  X::Status r{};size_t n=0;assert(s.response(0x70,0,reinterpret_cast<uint8_t *>(&r),sizeof(r),&n));
  assert(n==sizeof(r) && r.magic==0x5841464c && r.schema==1 && r.chunkBytes==512);return r;
}
static X::Status wait(X::Session &s) {
  for(unsigned i=0;i<200000;i++) {s.poll(now);auto r=status(s);if(r.state!=X::Working) return r;}
  assert(false);return {};
}
static void start(X::Session &s,Volume &v,const X::Request &r) {assert(s.begin(r,identity(v,r.id),now));}
static void acknowledge(X::Session &s) {s.acknowledge();}
static void abort(X::Session &s) {
  assert(s.request(0x75,status(s).sequence,nullptr,0));acknowledge(s);
  assert(wait(s).state==X::Cancelled && !s.busy());
}
static std::vector<uint8_t> download(X::Session &s) {
  std::vector<uint8_t> bytes;
  for(;;) {
    auto r=wait(s);if(r.state==X::Complete) {
      uint8_t digest[32];PrimeG2::NativeAppHash::sha256(bytes.data(),bytes.size(),digest);assert(!memcmp(digest,r.digest,32));return bytes;
    }
    assert(r.state==X::Readable && r.available && r.available<=512);uint8_t block[512]{};size_t n=0;
    assert(s.response(0x72,r.sequence,block,r.available,&n) && n==r.available);
    // Reading alone does not consume output, even if a host retries its IN.
    uint8_t repeated[512];assert(s.response(0x72,r.sequence,repeated,r.available,&n) && !memcmp(block,repeated,n));
    bytes.insert(bytes.end(),block,block+n);uint32_t ack[2]={r.sequence,r.offset+r.available};
    assert(s.request(0x73,0,reinterpret_cast<uint8_t *>(ack),sizeof(ack)));acknowledge(s);
  }
}
static X::Status upload(X::Session &s,const std::vector<uint8_t> &bytes,bool commit=true) {
  uint32_t offset=0;
  while(offset<bytes.size()) {
    auto r=wait(s);assert(r.state==X::Writable && r.offset==offset);uint32_t n=bytes.size()-offset;if(n>504) n=504;
    uint8_t frame[512];memcpy(frame,&r.sequence,4);memcpy(frame+4,&offset,4);memcpy(frame+8,bytes.data()+offset,n);
    assert(s.request(0x72,0,frame,n+8));
    // No write is allowed until the successful USB OUT status acknowledgement.
    s.poll(now);assert(status(s).offset==offset);acknowledge(s);offset+=n;
  }
  auto r=wait(s);assert(r.state==X::Writable && r.offset==bytes.size());
  if(!commit) return r;
  assert(s.request(0x74,r.sequence,nullptr,0));acknowledge(s);return wait(s);
}
static void interruptionCases(const Flash &baseline,unsigned operation,const std::vector<uint8_t> &payload) {
  using Root=PrimeG2::AppDocumentRoot::Root;
  auto run=[&](Flash &flash) {
    auto volume=std::make_unique<Volume>(flash.backend());assert(volume->mount());
    auto session=std::make_unique<X::Session>(*volume);auto r=request(*volume,operation,operation==X::Import?"document.bin":"");
    if(operation==X::Import) r.flags=X::Replace;
    if(operation==X::Rollback) r.cursor=identity(*volume).dataInfo.previousPackage;
    else {r.length=payload.size();PrimeG2::NativeAppHash::sha256(payload.data(),payload.size(),r.digest);}
    start(*session,*volume,r);auto done=upload(*session,payload);
    assert(done.state==X::Complete && done.flags==X::Committed);
  };
  auto inspect=[&](Flash &flash,std::vector<uint8_t> &privateData,std::vector<uint8_t> &app) {
    auto volume=std::make_unique<Volume>(flash.backend());assert(volume->mount());Entry entry;
    assert(volume->entry("files",&entry));privateData.resize(entry.dataBytes);app.resize(entry.packageBytes);
    assert(volume->read("files",app.data(),app.size(),privateData.data(),privateData.size()));
    Root root;assert(volume->documentRoot("files",&root));
    std::array<uint8_t,PrimeG2::AppDocumentRoot::Bytes> wire{};
    assert(PrimeG2::AppDocumentRoot::encode(root,wire.data()));
    if(operation==X::Import) {
      auto session=std::make_unique<X::Session>(*volume);
      start(*session,*volume,request(*volume,X::Export,"document.bin"));
      auto contents=download(*session);privateData.insert(privateData.end(),contents.begin(),contents.end());
    }
    return wire;
  };
  Flash finished=baseline;std::vector<uint8_t> oldData,oldApp,newData,newApp;
  const auto before=inspect(finished,oldData,oldApp);run(finished);
  const auto after=inspect(finished,newData,newApp);int mutations=finished.writes-baseline.writes;
  assert(mutations>0);
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash interrupted=baseline;interrupted.cut=baseline.writes+cut;interrupted.torn=torn;
    try {run(interrupted);} catch(const PowerCut &) {}
    interrupted.cut=-1;std::vector<uint8_t> actualData,actualApp;
    auto actual=inspect(interrupted,actualData,actualApp);
    assert(actual==before || actual==after);
    assert(actualData==(actual==before?oldData:newData));assert(actualApp==(actual==before?oldApp:newApp));
  }
  printf("PASS: operation %u, %u clean/torn commit interruption cases\n",operation,2*(mutations+1));
}
int main() {
  Flash flash;auto v=std::make_unique<Volume>(flash.backend());std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  assert(v->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char id[49]){strcpy(id,"files");return true;}));
  uint8_t app[468]{};for(const char *id:{"files","other"}) {assert(v->begin(id,app,sizeof(app),reinterpret_cast<uint8_t *>(&privateValue),4));finish(*v);}
  X::Session s(*v);int writes=flash.writes;start(s,*v,request(*v,X::Inspect));auto bytes=download(s);
  X::Info info;assert(bytes.size()==sizeof(info));memcpy(&info,bytes.data(),bytes.size());
  assert(info.space.privateBytes==4 && info.quota.committedBytes==4 && flash.writes==writes);
  std::vector<uint8_t> input(PrimeG2::AppFileIndex::ChunkBytes+719);for(unsigned i=0;i<input.size();i++) input[i]=i*37;
  auto r=request(*v,X::Import,"document.bin");r.length=input.size();PrimeG2::NativeAppHash::sha256(input.data(),input.size(),r.digest);
  auto stale=r;stale.generation++;start(s,*v,stale);assert(status(s).error==LEFONY_FILE_CHANGED && flash.writes==writes);
  auto invalid=r;strcpy(invalid.path,"../escape");assert(!X::Session::valid(invalid));invalid=r;invalid.id[63]='x';assert(!X::Session::valid(invalid));
  auto mismatch=identity(*v);mismatch.appSchema=1;assert(s.begin(r,mismatch,now));assert(status(s).error==LEFONY_FILE_SCHEMA && flash.writes==writes);
  start(s,*v,r);assert(upload(s,input).flags==X::Committed && !s.busy());
  start(s,*v,request(*v,X::Export,"document.bin"));assert(download(s)==input);
  start(s,*v,request(*v,X::List));bytes=download(s);LefonyDirectoryPage page;memcpy(&page,bytes.data(),sizeof(page));
  assert(bytes.size()==sizeof(page) && page.count==1 && !strcmp(page.entries[0].path,"document.bin"));
  // Both clean and torn NAND writes retain exactly the old or new named file.
  interruptionCases(flash,X::Import,{9,8,7,6,5});
  // Bad length/hash, cancellation, wrong offsets/tokens and abandoned OUT
  // frames never publish a replacement or alter another app's saved data.
  r=request(*v,X::Import,"document.bin");r.flags=X::Replace;r.length=3;
  start(s,*v,r);assert(upload(s,{1,2,3}).error==X::DigestMismatch);
  start(s,*v,request(*v,X::Export,"document.bin"));assert(download(s)==input);
  start(s,*v,r);auto st=wait(s);assert(st.state==X::Writable);
  uint32_t bad[3]={st.sequence+1,0,0};assert(!s.request(0x72,0,reinterpret_cast<uint8_t *>(bad),9));
  bad[0]=st.sequence;bad[1]=1;assert(!s.request(0x72,0,reinterpret_cast<uint8_t *>(bad),9));
  bad[1]=0;assert(s.request(0x72,0,reinterpret_cast<uint8_t *>(bad),9));s.abandonSetup();s.poll(now);assert(status(s).offset==0);
  upload(s,{1,2,3},false);abort(s);
  start(s,*v,request(*v,X::Export,"document.bin"));assert(download(s)==input);
  start(s,*v,r);wait(s);now+=30000;s.poll(now);assert(wait(s).error==X::Timeout && !s.busy());
  start(s,*v,r);wait(s);s.disconnect();assert(wait(s).error==X::CancelledError);
  start(s,*v,request(*v,X::Inspect,"","other"));bytes=download(s);memcpy(&info,bytes.data(),sizeof(info));assert(info.quota.committedBytes==4);
  r=request(*v,X::Import,"too-large");r.length=32u*1024u*1024u;writes=flash.writes;start(s,*v,r);
  assert(wait(s).error==LEFONY_FILE_QUOTA_EXCEEDED && flash.writes==writes);
  r=request(*v,X::Import,"empty");PrimeG2::NativeAppHash::sha256(nullptr,0,r.digest);start(s,*v,r);assert(upload(s,{}).flags==X::Committed);
  start(s,*v,request(*v,X::Export,"empty"));assert(download(s).empty());
  v.reset();v=std::make_unique<Volume>(flash.backend());assert(v->mount());X::Session cold(*v);
  start(cold,*v,request(*v,X::Export,"document.bin"));assert(download(cold)==input);
  // Private data never aliases the public file path grammar. A complete
  // pre-commit upload remains RAM staging, including maximum-length restores.
  writes=flash.writes;start(cold,*v,request(*v,X::InspectData));bytes=download(cold);
  X::DataInfo dataInfo;assert(bytes.size()==sizeof(dataInfo));memcpy(&dataInfo,bytes.data(),sizeof(dataInfo));
  assert(dataInfo.privateBytes==4 && !dataInfo.flags && flash.writes==writes);
  start(cold,*v,request(*v,X::ExportData));bytes=download(cold);
  assert(bytes.size()==4 && !memcmp(bytes.data(),&privateValue,4));
  std::vector<uint8_t> restore(MaximumData);for(unsigned i=0;i<restore.size();i++) restore[i]=i*13;
  r=request(*v,X::ImportData);r.length=restore.size();PrimeG2::NativeAppHash::sha256(restore.data(),restore.size(),r.digest);
  auto over=r;over.length++;assert(!X::Session::valid(over));over=r;strcpy(over.path,"named");assert(!X::Session::valid(over));
  writes=flash.writes;start(cold,*v,r);upload(cold,restore,false);assert(flash.writes==writes);abort(cold);
  assert(flash.writes==writes);start(cold,*v,request(*v,X::ExportData));assert(download(cold)==bytes);
  start(cold,*v,r);auto prepared=upload(cold,restore,false);
  assert(cold.request(0x74,prepared.sequence,nullptr,0));acknowledge(cold);
  // A status-ACKed COMMIT owns the outcome even before the next OS poll.
  // Reset or expiration at that boundary must not turn it into cancellation.
  cold.disconnect();now+=30000;auto restored=wait(cold);
  assert(restored.state==X::Complete && restored.flags==X::Committed);
  start(cold,*v,request(*v,X::ExportData));assert(download(cold)==restore);
  start(cold,*v,request(*v,X::Export,"document.bin"));assert(download(cold)==input);
  start(cold,*v,request(*v,X::ExportData,"","other"));assert(download(cold)==bytes);
  interruptionCases(flash,X::ImportData,std::vector<uint8_t>(19,0x93));
  r=request(*v,X::ImportData);r.length=3;writes=flash.writes;start(cold,*v,r);
  assert(upload(cold,{1,2,3}).error==X::DigestMismatch && flash.writes==writes);
  r=request(*v,X::ImportData);PrimeG2::NativeAppHash::sha256(nullptr,0,r.digest);start(cold,*v,r);
  assert(upload(cold,{}).flags==X::Committed);start(cold,*v,request(*v,X::ExportData));assert(download(cold).empty());
  // Bulk staging uses the same file transaction; RAM reception alone cannot
  // commit a file, and a stale token or inconsistent length cannot attach.
  std::vector<uint8_t> bulk(8193);for(size_t i=0;i<bulk.size();i++) bulk[i]=i%251;
  r=request(*v,X::Import,"bulk.bin");r.length=bulk.size();
  PrimeG2::NativeAppHash::sha256(bulk.data(),bulk.size(),r.digest);
  start(cold,*v,r);st=wait(cold);assert(st.state==X::Writable);
  assert(!cold.stage(st.sequence+1,bulk.data(),bulk.size()));
  assert(!cold.stage(st.sequence,bulk.data(),bulk.size()-1));
  assert(cold.stage(st.sequence,bulk.data(),bulk.size()));
  assert(!cold.request(0x74,st.sequence,nullptr,0));
  for(unsigned i=0;i<200000 && status(cold).offset<bulk.size();i++) cold.poll(now);
  st=wait(cold);assert(st.state==X::Writable && st.offset==bulk.size() && !st.flags);
  assert(cold.request(0x74,st.sequence,nullptr,0));acknowledge(cold);
  assert(wait(cold).flags==X::Committed);
  start(cold,*v,request(*v,X::Export,"bulk.bin"));st=wait(cold);
  std::vector<uint8_t> received(bulk.size());
  assert(!cold.stageExport(st.sequence+1,received.data(),received.size()));
  assert(cold.stageExport(st.sequence,received.data(),received.size()));
  for(unsigned i=0;i<200000 && cold.busy();i++) cold.poll(now);
  st=status(cold);assert(st.state==X::Complete && received==bulk && !memcmp(st.digest,r.digest,32));
  // Interrupted replacement leaves the committed file intact.
  r=request(*v,X::Import,"bulk.bin");r.flags=X::Replace;r.length=bulk.size();
  start(cold,*v,r);st=wait(cold);assert(cold.stage(st.sequence,bulk.data(),bulk.size()));
  cold.poll(now);cold.disconnect();assert(wait(cold).error==X::CancelledError);
  start(cold,*v,request(*v,X::Export,"bulk.bin"));assert(download(cold)==bulk);
  // All bytes may reach RAM/storage, but a wrong digest still denies commit.
  start(cold,*v,r);st=wait(cold);assert(cold.stage(st.sequence,bulk.data(),bulk.size()));
  for(unsigned i=0;i<200000 && status(cold).offset<bulk.size();i++) cold.poll(now);
  st=wait(cold);assert(cold.request(0x74,st.sequence,nullptr,0));acknowledge(cold);
  assert(wait(cold).error==X::DigestMismatch);
  start(cold,*v,request(*v,X::Export,"bulk.bin"));assert(download(cold)==bulk);
  // The controller cannot choose arbitrary old packages or skip the trusted
  // recovery decision. Rollback restores both package and data, preserving the
  // highest installed version across a cold mount.
  auto before=identity(*v);uint8_t upgraded[468]={1};version[0]=2;
  assert(v->beginUpgrade("files",upgraded,sizeof(upgraded),version));finish(*v);
  uint32_t changed=99;assert(v->beginCheckpoint("files",reinterpret_cast<uint8_t *>(&changed),4,nullptr,1,false));finish(*v);
  auto pending=identity(*v);assert(pending.pendingUpgrade);
  r=request(*v,X::ImportData);start(cold,*v,r);assert(status(cold).error==LEFONY_FILE_SCHEMA);
  r=request(*v,X::Rollback);r.cursor=pending.dataInfo.previousPackage;
  auto denied=pending;denied.dataInfo.flags&=~X::RecoveryTrusted;writes=flash.writes;
  assert(cold.begin(r,denied,now));assert(status(cold).error==LEFONY_FILE_DENIED && flash.writes==writes);
  auto wrong=r;wrong.cursor++;start(cold,*v,wrong);assert(status(cold).error==LEFONY_FILE_DENIED);
  start(cold,*v,r);abort(cold);assert(identity(*v).pendingUpgrade && flash.writes==writes);
  interruptionCases(flash,X::Rollback,{});
  start(cold,*v,r);assert(upload(cold,{}).flags==X::Committed);version[0]=1;
  auto rolled=identity(*v);assert(!rolled.pendingUpgrade && rolled.dataInfo.highVersion[0]==2);
  assert(!memcmp(rolled.dataInfo.packageHash,before.dataInfo.packageHash,32) && !rolled.privateBytes);
  start(cold,*v,request(*v,X::Export,"document.bin"));assert(download(cold)==input);
  version[0]=2;assert(!v->beginUpgrade("files",upgraded,sizeof(upgraded),version));version[0]=1;
  v.reset();v=std::make_unique<Volume>(flash.backend());assert(v->mount());rolled=identity(*v);
  assert(!rolled.pendingUpgrade && !rolled.privateBytes && rolled.dataInfo.highVersion[0]==2);
  puts("PASS: file/private-byte transfer, maximum restore staging without NAND writes, digest before commit, exact empty data, cancellation, schema/identity/target denial, app isolation, named-file preservation, retained-pair rollback and cold anti-downgrade retention");
}

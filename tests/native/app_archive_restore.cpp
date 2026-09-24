// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_archive_restore.h"
#include "app_archive_export.h"
#include "app_storage.h"
#include "native_app_signature.h"
#include "native_app_manifest.h"
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
namespace Archive=PrimeG2::AppArchive;
namespace Hash=PrimeG2::NativeAppHash;
namespace Index=PrimeG2::AppFileIndex;
using Restore=Archive::Restore;
using Store=PrimeG2::AppDocumentStore::Store;
using RState=Restore::State;
using Bytes=std::vector<uint8_t>;
static Bytes scratchPackage(MaximumPackage),scratchData(MaximumData),modulus;
static uint8_t keyId[32];
static Bytes load(const std::string &path) {
  FILE *file=fopen(path.c_str(),"rb");assert(file);assert(!fseek(file,0,SEEK_END));long n=ftell(file);assert(n>=0);rewind(file);
  Bytes out(n);assert(fread(out.data(),1,out.size(),file)==out.size());assert(!fclose(file));return out;
}
static void save(const std::string &path,const Bytes &bytes) {
  FILE *file=fopen(path.c_str(),"wb");assert(file && fwrite(bytes.data(),1,bytes.size(),file)==bytes.size() && !fclose(file));
}
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
static bool initialize(Volume &v) {
  return v.initialize(scratchPackage.data(),scratchPackage.size(),scratchData.data(),scratchData.size(),
    [](const uint8_t *,size_t,char id[49]) { strcpy(id,"unused");return true; });
}
static Bytes readRaw(Raw &raw,const char *name) {
  lfs_info info;int rc=lfs_stat(&raw.fs,name,&info);if(rc==LFS_ERR_NOENT) return {};
  assert(!rc && info.type==LFS_TYPE_REG);Bytes out(info.size);
  lfs_file_t file{};lfs_file_config config{};uint8_t cache[2048];config.buffer=cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,name,LFS_O_RDONLY,&config));
  assert(lfs_file_read(&raw.fs,&file,out.data(),out.size())==int(out.size()));assert(!lfs_file_close(&raw.fs,&file));return out;
}
static Bytes canonical(Flash &flash,const char *name="apps/document.app") { Raw raw(flash);return readRaw(raw,name); }
static void object(char type,uint32_t gen,char out[80],uint32_t part=0) {
  if(type=='c') snprintf(out,80,"objects/document/c%08x.%08x",gen,part);
  else snprintf(out,80,"objects/document/%c%08x",type,gen);
}
static Flash baseline(const Bytes &package,const Bytes &file,bool converted=true) {
  Flash flash;auto v=std::make_unique<Volume>(flash.backend());assert(initialize(*v));
  for(const char *id:{"document","other"}) {
    assert(v->begin(id,package.data(),package.size(),reinterpret_cast<const uint8_t *>("old"),3));finish(*v);
  }
  if(!converted) return flash;
  uint32_t version[3]={1,0,0};assert(v->beginCheckpoint("document",reinterpret_cast<const uint8_t *>("old"),3,version,0));finish(*v);
  assert(v->changeFile("document","docs",nullptr,true));finish(*v);
  assert(v->beginFile("document","docs/note.bin",file.size()));
  unsigned offset=0;
  while(offset<file.size()) {
    for(unsigned step=0;step<200000 && !v->fileWritable() && v->state()!=State::Failed;step++) v->step();
    assert(v->fileWritable());int n=v->writeFile(file.data()+offset,std::min(size_t(2048),file.size()-offset));assert(n>0);offset+=n;
  }
  while(!v->fileWritable() && v->state()!=State::Failed) v->step();
  assert(v->commitFile());finish(*v);return flash;
}
struct Context {
  Raw *raw;
  Bytes before;
  bool changed=false,deny=false;
  int admissions=-1;
  unsigned authentications=0;
  static bool authenticate(void *opaque,const Archive::Header &h,const Archive::PairHeader &p,unsigned number,const uint8_t *package) {
    auto &self=*static_cast<Context *>(opaque);self.authentications++;
    if(self.deny) return false;
    const uint8_t *payload=nullptr;size_t length=0;
    if(!PrimeG2::NativeAppSignature::unwrapWithKey(package,p.packageBytes,keyId,modulus.data(),&payload,&length)) return false;
    using Index::get;
    if(length<64 || get(payload+12)>length-64) return false;
    PrimeG2::NativeAppManifest::Manifest metadata;
    if(!PrimeG2::NativeAppManifest::parse(payload+64,get(payload+12),get(payload+8),get(payload+20),&metadata) ||
       !PrimeG2::NativeAppManifest::supported(metadata) || metadata.abi!=1 || strcmp(metadata.id,h.id)) return false;
    uint32_t version[3];assert(sscanf(metadata.version,"%u.%u.%u",&version[0],&version[1],&version[2])==3);
    return !Archive::compare(version,p.version) && ((!number && h.pairs==2) || metadata.dataSchema==p.dataSchema);
  }
  static bool unchanged(void *opaque) {
    auto &self=*static_cast<Context *>(opaque);return !self.changed && readRaw(*self.raw,"apps/document.app")==self.before;
  }
  static bool admit(void *opaque,uint32_t bytes) {
    auto &self=*static_cast<Context *>(opaque);assert(bytes<=Archive::MaximumPackage);
    if(!self.admissions) return false;
    if(self.admissions>0) self.admissions--;
    lfs_ssize_t blocks=lfs_fs_size(&self.raw->fs);assert(blocks>=0);
    return uint32_t(blocks)+6+(bytes+BlockBytes-1)/BlockBytes<=BlockCount-2-ReserveBlocks;
  }
};
struct Options {
  int cancel=-1,admissions=-1;
  uint32_t limit=32u*1024*1024;
  bool changed=false,deny=false,corrupt=false,digest=false,commitIO=false;
};
struct Outcome { RState state;Restore::Error error;unsigned steps,reused,authentications;Root after; };
static Outcome restore(Flash &flash,const Bytes &bytes,Options options={}) {
  Raw raw(flash);auto documents=std::make_unique<Store>(&raw.fs);auto engine=std::make_unique<Restore>(&raw.fs,documents.get());
  Context context{&raw,readRaw(raw,"apps/document.app")};context.deny=options.deny;context.admissions=options.admissions;
  Root before;uint32_t base=0;
  if(documents->root("document",&before)) base=before.serial;
  else if(!context.before.empty()) { assert(!memcmp(context.before.data(),"LFAFILE2",8));base=Index::get(context.before.data()+12); }
  uint8_t digest[32];Hash::sha256(bytes.data(),bytes.size(),digest);if(options.digest) digest[0]^=1;
  assert(engine->begin("document",before,base,options.limit,bytes.size(),digest,scratchPackage.data(),scratchPackage.size(),
    {&context,Context::authenticate,Context::unchanged,Context::admit,nullptr,false}));
  unsigned steps=0,offset=0;
  for(;steps<200000;steps++) {
    RState s=engine->state();if(s==RState::Complete || s==RState::Failed || s==RState::Cancelled) break;
    if(int(steps)==options.cancel && s!=RState::Committing) { assert(engine->cancel());continue; }
    if(s==RState::Receiving) {
      assert(offset<bytes.size());unsigned n=std::min(size_t(1+steps%997),bytes.size()-offset);
      int got=engine->write(bytes.data()+offset,n);
      if(got<0) assert(engine->state()==RState::Working);else { assert(got>0 && unsigned(got)<=n);offset+=got; }
    } else if(s==RState::Ready) {
      context.changed=options.changed;
      if(options.corrupt) { char path[80];object('d',engine->result().current.data,path);raw.corrupt(path); }
      bool accepted=engine->commit();assert(accepted || options.changed || options.admissions>=0);
    } else {
      if(s==RState::Committing) {
        assert(!engine->cancel());
        if(options.commitIO) raw.c.prog=[](const lfs_config *,lfs_block_t,lfs_off_t,const void *,lfs_size_t) { return int(LFS_ERR_IO); };
      }
      engine->step();
    }
  }
  assert(steps<200000 && !engine->cleanupFailed());
  if(engine->state()==RState::Complete) assert(offset==bytes.size() && !engine->cancel());
  if(engine->state()!=RState::Complete && engine->error()!=Restore::Error::CommitUnknown) {
    assert(readRaw(raw,"apps/document.app")==context.before);
    char path[80];
    for(unsigned i=1;i<=2;i++) {
      object('p',base+i,path);assert(!raw.exists(path));object('d',base+i,path);assert(!raw.exists(path));
      for(unsigned part=1;part<=Index::MaximumExtents;part++) { object('c',base+i,path,part);assert(!raw.exists(path)); }
    }
  }
  return {engine->state(),engine->error(),steps,engine->reusedBytes(),context.authentications,engine->result()};
}
static void rejectedTarget(Flash &flash,const Bytes &archive,const Root &before,uint32_t base) {
  int writes=flash.writes;Raw raw(flash);auto docs=std::make_unique<Store>(&raw.fs);auto engine=std::make_unique<Restore>(&raw.fs,docs.get());
  Context context{&raw,readRaw(raw,"apps/document.app")};uint8_t digest[32];Hash::sha256(archive.data(),archive.size(),digest);
  assert(!engine->begin("document",before,base,32u*1024*1024,archive.size(),digest,scratchPackage.data(),scratchPackage.size(),
    {&context,Context::authenticate,Context::unchanged,Context::admit,nullptr,false}));
  assert(flash.writes==writes && !context.authentications);
}
static bool exportVerify(void *deny,const char *id,const uint8_t *package,uint32_t bytes,Archive::PackageInfo *out) {
  if(deny) return false;
  const uint8_t *payload;size_t length;
  if(!PrimeG2::NativeAppSignature::unwrapWithKey(package,bytes,keyId,modulus.data(),&payload,&length) || length<64) return false;
  PrimeG2::NativeAppManifest::Manifest m;
  if(!PrimeG2::NativeAppManifest::parse(payload+64,Index::get(payload+12),Index::get(payload+8),Index::get(payload+20),&m) || strcmp(m.id,id) || m.abi!=1) return false;
  assert(sscanf(m.version,"%u.%u.%u",&out->version[0],&out->version[1],&out->version[2])==3);out->schema=m.dataSchema;return true;
}
struct Exported {Bytes bytes;Archive::Export::State state;unsigned steps;};
static Exported exportArchive(Flash &flash,int cancel=-1,bool deny=false) {
  int writes=flash.writes;Raw raw(flash);Archive::Source source(&raw.fs);Archive::SourceInfo info;
  assert(source.inspect("document",&info)==Archive::Source::Result::Ok);
  auto docs=std::make_unique<Store>(&raw.fs);auto engine=std::make_unique<Archive::Export>(&raw.fs,docs.get());
  assert(engine->begin(info,scratchPackage.data(),scratchPackage.size(),exportVerify,deny?&deny:nullptr));
  Bytes out;unsigned steps=0;using S=Archive::Export::State;
  for(;steps<20000;steps++) {
    S s=engine->state();if(s==S::Complete || s==S::Cancelled || s==S::Failed) break;
    if(int(steps)==cancel) {engine->cancel();continue;}
    if(s==S::Working) engine->step();
    else {
      uint8_t data[2048];int n=engine->read(data,1+steps%sizeof(data));
      if(n==-2) continue;
      if(n<0) assert(engine->state()==S::Failed);else {assert(n>0);out.insert(out.end(),data,data+n);}
    }
  }
  assert(steps<20000 && flash.writes==writes);
  if(engine->state()==S::Complete) {
    uint8_t digest[32];Hash::sha256(out.data(),out.size(),digest);
    assert(out.size()==engine->bytes() && engine->position()==out.size() && !memcmp(digest,engine->digest(),32));
  }
  return {out,engine->state(),steps};
}
static Bytes named(Raw &raw,Store &documents,const Root &root,const char *name) {
  auto reader=std::make_unique<PrimeG2::AppFileStore::Reader>();assert(reader->open(&raw.fs,&documents,"document",name,root));
  Bytes out;uint8_t data[2048];unsigned steps=0;
  while(++steps<10000) {
    int got=reader->read(data,sizeof(data));
    if(got==-2) { reader->step();continue; }assert(got>=0);if(!got) break;out.insert(out.end(),data,data+got);
  }
  assert(steps<10000 && reader->close());return out;
}
static void verify(Flash &flash,const Bytes &package,const Bytes &file,bool pending=false) {
  auto v=std::make_unique<Volume>(flash.backend());assert(v->mount());Entry entry;
  assert(v->entry("document",&entry));assert(entry.packageBytes==package.size() && entry.dataBytes==5);
  assert(v->read("document",scratchPackage.data(),scratchPackage.size(),scratchData.data(),scratchData.size()));
  assert(!memcmp(package.data(),scratchPackage.data(),package.size()) && !memcmp(scratchData.data(),"saved",5));v.reset();
  Raw raw(flash);auto docs=std::make_unique<Store>(&raw.fs);Root root;assert(docs->root("document",&root));
  assert(root.flags==(pending?1u:0u));assert(named(raw,*docs,root,"docs/note.bin")==file);
  assert(named(raw,*docs,root,"empty").empty());
  if(pending) {
    root.current=root.previous;root.previous={};root.flags=0;
    assert(named(raw,*docs,root,"docs/note.bin")==file);
  }
}
int main(int argc,char **argv) {
  assert(argc==2);std::string directory=argv[1];
  auto archive=load(directory+"/current.arc"),pending=load(directory+"/pending.arc"),small=load(directory+"/small.arc"),same=load(directory+"/same.arc");
  auto currentPackage=load(directory+"/current.pkg"),oldPackage=load(directory+"/old.pkg"),file=load(directory+"/file.bin");
  modulus=load(directory+"/modulus.bin");auto identity=load(directory+"/identity.bin");assert(modulus.size()==256 && identity.size()==32);memcpy(keyId,identity.data(),32);
  Flash old=baseline(oldPackage,file),completed=old;auto oldRoot=canonical(old),other=canonical(old,"apps/other.app");
  Root originalRoot;{Raw raw(old);Store documents(&raw.fs);assert(documents.root("document",&originalRoot));}
  unsigned namespaceCases=0;
  for(unsigned kind=0;kind<8;kind++) {
    Flash trial=old;Root supplied=originalRoot;uint32_t base=supplied.serial;
    if(kind==0) { supplied={};base=0; }
    if(kind==1) supplied={};
    if(kind==2) { supplied.serial++;base=supplied.serial; }
    if(kind==3) supplied.current.dataHash[0]^=1;
    if(kind==4) { Raw raw(trial);raw.remove("apps/document.app"); }
    if(kind==5 || kind==6) {
      Raw raw(trial);lfs_file_t file{};lfs_file_config config{};config.buffer=raw.cache;
      assert(!lfs_file_opencfg(&raw.fs,&file,"apps/document.app",LFS_O_WRONLY|LFS_O_TRUNC,&config));
      if(kind==6) { uint8_t unknown[64]{};assert(lfs_file_write(&raw.fs,&file,unknown,sizeof(unknown))==sizeof(unknown)); }
      assert(!lfs_file_close(&raw.fs,&file));supplied={};base=kind==5?0:1;
    }
    if(kind==7) { Raw raw(trial);raw.corruptRoot("apps/document.app"); }
    rejectedTarget(trial,archive,supplied,base);namespaceCases++;
  }
  int start=completed.writes;auto result=restore(completed,archive);int mutations=completed.writes-start;
  assert(result.state==RState::Complete && result.reused==file.size());verify(completed,currentPackage,file);
  auto newRoot=canonical(completed);assert(newRoot!=oldRoot && canonical(completed,"apps/other.app")==other);
  auto exported=exportArchive(completed);assert(exported.state==Archive::Export::State::Complete && exported.bytes==archive);
  save(directory+"/export-current.arc",exported.bytes);
  unsigned exportCancellations=0;
  for(unsigned step=0;step<exported.steps;step+=23) {
    auto cancelled=exportArchive(completed,step);assert(cancelled.state==Archive::Export::State::Cancelled);exportCancellations++;
  }
  assert(exportArchive(completed,-1,true).state==Archive::Export::State::Failed);
  unsigned cuts=0;
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash trial=old;trial.torn=torn;trial.cut=trial.writes+cut;
    try { restore(trial,archive); } catch(PowerCut &) {}
    trial.cut=-1;auto recovered=canonical(trial);assert(recovered==oldRoot || recovered==newRoot);
    if(recovered==newRoot) verify(trial,currentPackage,file);
    else { auto v=std::make_unique<Volume>(trial.backend());assert(v->mount());assert(v->read("document",scratchPackage.data(),scratchPackage.size(),scratchData.data(),scratchData.size()));assert(!memcmp(scratchData.data(),"old",3)); }
    assert(canonical(trial,"apps/other.app")==other);cuts++;
  }
  unsigned cancellations=0;
  for(unsigned step=0;step<result.steps;step+=11) {
    Flash trial=old;Options options;options.cancel=step;auto cancelled=restore(trial,archive,options);
    assert(cancelled.state==RState::Cancelled || cancelled.state==RState::Complete);
    if(cancelled.state==RState::Cancelled) { assert(canonical(trial)==oldRoot);cancellations++; }
  }
  unsigned corruptionCases=0;
  for(unsigned kind=0;kind<3;kind++) {
    Flash trial=old;
    { Raw raw(trial);auto docs=std::make_unique<Store>(&raw.fs);Root root;assert(docs->root("document",&root));char path[80];
      if(!kind) object('d',root.current.data,path);
      else { auto index=std::make_unique<Index::Index>();assert(docs->index("document",root.current,index.get()));
        const auto &extent=index->extent[kind==1?0:index->entry[index->find("docs/note.bin")].first];
        object(extent.type==Index::ChunkObject?'c':'d',extent.generation,path,extent.part);
      }
      raw.corrupt(path);
    }
    { Raw raw(trial);Archive::Source source(&raw.fs);Archive::SourceInfo info;Archive::PackageInfo parsed;
      assert(source.inspect("document",&info)==Archive::Source::Result::Ok && source.package(info,0,scratchPackage.data(),scratchPackage.size()));
      assert(exportVerify(nullptr,"document",scratchPackage.data(),info.packageBytes,&parsed));
    }
    assert(exportArchive(trial).state==Archive::Export::State::Failed);
    auto repaired=restore(trial,archive);assert(repaired.state==RState::Complete);
    if(kind==2) assert(repaired.reused<file.size());
    verify(trial,currentPackage,file);corruptionCases++;
  }
  Flash legacy=baseline(oldPackage,file,false);
  auto legacyExport=exportArchive(legacy);assert(legacyExport.state==Archive::Export::State::Complete);save(directory+"/export-legacy.arc",legacyExport.bytes);
  assert(restore(legacy,archive).state==RState::Complete);verify(legacy,currentPackage,file);
  Flash absent=old;
  { auto v=std::make_unique<Volume>(absent.backend());assert(v->mount());assert(v->begin("document",nullptr,0,nullptr,0));finish(*v); }
  Flash emptyNamespace=absent;
  auto absentResult=restore(absent,pending);assert(absentResult.state==RState::Complete && absentResult.authentications==2 && absentResult.reused>=file.size());verify(absent,currentPackage,file,true);
  auto pendingExport=exportArchive(absent);assert(pendingExport.state==Archive::Export::State::Complete && pendingExport.bytes==pending);
  save(directory+"/export-pending.arc",pendingExport.bytes);
  // Include every flash mutation while writing entirely new chunks and two
  // compatible pairs, rather than qualifying only reuse of existing chunks.
  for(unsigned scenario=0;scenario<2;scenario++) {
    Flash source=scenario?emptyNamespace:baseline(oldPackage,file,false),done=source;
    const Bytes &input=scenario?pending:archive;auto before=canonical(source);int writes=done.writes;
    auto successful=restore(done,input);assert(successful.state==RState::Complete);
    auto after=canonical(done);writes=done.writes-writes;
    for(bool torn:{false,true}) for(int cut=0;cut<=writes;cut++) {
      Flash trial=source;trial.torn=torn;trial.cut=trial.writes+cut;
      try { restore(trial,input); } catch(PowerCut &) {}
      trial.cut=-1;auto recovered=canonical(trial);assert(recovered==before || recovered==after);
      if(recovered==after) verify(trial,currentPackage,file,scenario);
      assert(canonical(trial,"apps/other.app")==other);cuts++;
    }
    for(unsigned step=0;step<successful.steps;step+=19) {
      Flash trial=source;Options options;options.cancel=step;auto cancelled=restore(trial,input,options);
      assert(cancelled.state==RState::Cancelled || cancelled.state==RState::Complete);
      if(cancelled.state==RState::Cancelled) { assert(canonical(trial)==before);cancellations++; }
    }
  }
  unsigned rejectionCases=0;
  { Flash trial=old;Options options;options.commitIO=true;auto uncertain=restore(trial,archive,options);
    assert(uncertain.state==RState::Failed && uncertain.error==Restore::Error::CommitUnknown);
    auto recovered=canonical(trial);assert(recovered==oldRoot || recovered==newRoot);
    Raw raw(trial);char path[80];object('p',uncertain.after.current.package,path);assert(raw.exists(path));
    object('d',uncertain.after.current.data,path);assert(raw.exists(path));
    assert(canonical(trial,"apps/other.app")==other);
  }
  for(unsigned kind=0;kind<7;kind++) {
    Flash trial=old;Options options;
    if(kind==0) options.deny=true;
    if(kind==1) options.digest=true;
    if(kind==2) options.changed=true;
    if(kind==3) options.corrupt=true;
    if(kind==4) options.limit=10;
    if(kind==5) options.admissions=1;
    if(kind==6) options.admissions=0;
    auto rejected=restore(trial,archive,options);assert(rejected.state==RState::Failed);assert(canonical(trial)==oldRoot);rejectionCases++;
  }
  // Corrupt transport/header/file bytes while recomputing the outer transfer
  // hash: the device must independently reject the embedded inconsistency.
  const unsigned offsets[]={8,24,28,44,128,164,200,256,256+96,unsigned(256+currentPackage.size()),unsigned(archive.size()-1)};
  for(unsigned offset:offsets) {
    Flash trial=old;Bytes broken=archive;broken[offset]^=0x80;
    assert(restore(trial,broken).state==RState::Failed);rejectionCases++;
  }
  // Every declared truncation at structural/content boundaries fails without
  // waiting forever for bytes outside the transfer's declared length.
  for(unsigned length:{unsigned(256+currentPackage.size()),unsigned(archive.size()-1),unsigned(archive.size()-33)}) {
    Flash trial=old;Bytes truncated(archive.begin(),archive.begin()+length);Index::put(truncated.data()+16,length);
    assert(restore(trial,truncated).state==RState::Failed);rejectionCases++;
  }
  // The version high-water mark survives restoring data to the exact same
  // signed package after rollback. This grants no below-watermark code update.
  Flash watermark=old;
  { Raw raw(watermark);auto docs=std::make_unique<Store>(&raw.fs);Root root;assert(docs->root("document",&root));root.highVersion[0]=9;raw.root(root); }
  assert(restore(watermark,same).state==RState::Complete);
  verify(watermark,oldPackage,file);
  { Raw raw(watermark);auto docs=std::make_unique<Store>(&raw.fs);Root root;assert(docs->root("document",&root));assert(root.highVersion[0]==9); }
  // Actual full media, even for a tiny valid archive, preserves both apps.
  Flash full=old;{ Raw raw(full);raw.fill(); }
  assert(restore(full,small).state==RState::Failed);assert(canonical(full)==oldRoot && canonical(full,"apps/other.app")==other);
  printf("{\"interruption_cases\":%u,\"cancellation_cases\":%u,\"damaged_data_cases\":%u,\"rejection_cases\":%u,\"namespace_cases\":%u,\"uncertain_commit_cases\":1,\"reused_bytes\":%u,\"engine_bytes\":%zu,\"export_engine_bytes\":%zu,\"export_cancellations\":%u,\"steps\":%u}\n",
    cuts,cancellations,corruptionCases,rejectionCases,namespaceCases,result.reused,sizeof(Restore),sizeof(Archive::Export),exportCancellations,result.steps);
}

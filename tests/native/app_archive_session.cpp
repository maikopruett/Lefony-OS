// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_archive_session.h"
#include "native_app_manifest.h"
#include "native_app_signature.h"
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
namespace A=PrimeG2::AppArchive;
namespace H=PrimeG2::NativeAppHash;
using TS=A::TransferState;
using TE=A::TransferError;
using Bytes=std::vector<uint8_t>;
static Bytes upload(MaximumPackage),inspection(MaximumPackage),privateScratch(MaximumData),modulus,secondModulus;
static uint8_t keyId[32],secondId[32];
static Bytes load(const std::string &path) {
  FILE *f=fopen(path.c_str(),"rb");assert(f && !fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=0);rewind(f);
  Bytes out(n);assert(fread(out.data(),1,out.size(),f)==out.size() && !fclose(f));return out;
}
static void finish(Volume &v) {
  unsigned n=0;while(v.state()!=State::Complete && v.state()!=State::Failed && ++n<200000) v.step();
  assert(v.state()==State::Complete);
}
static Flash baseline(const Bytes &pkg,bool existing=true) {
  Flash f;auto v=std::make_unique<Volume>(f.backend());
  assert(v->initialize(upload.data(),upload.size(),privateScratch.data(),privateScratch.size(),
    [](const uint8_t *,size_t,char out[49]) {strcpy(out,"unused");return true;}));
  for(const char *id:{"other","document"}) {
    if(!existing && !strcmp(id,"document")) continue;
    assert(v->begin(id,pkg.data(),pkg.size(),reinterpret_cast<const uint8_t *>("old"),3));finish(*v);
  }
  return f;
}
struct Authority {
  uint32_t revision=1;bool revoked=false,unknownPrevious=false;
  unsigned inspected=0,executed=0,protectedSigner=0;
  static bool verify(void *ctx,const char *id,const uint8_t *package,uint32_t size,bool inspect,bool supported,A::PackageInfo *out) {
    auto &self=*static_cast<Authority *>(ctx);if(inspect) self.inspected++;else self.executed++;
    if(!inspect && self.revoked) return false;
    const uint8_t *payload;size_t bytes;
    bool second=size>=56 && !memcmp(package+24,secondId,32);
    if(second && self.unknownPrevious) return false;
    if(!PrimeG2::NativeAppSignature::unwrapWithKey(package,size,second?secondId:keyId,second?secondModulus.data():modulus.data(),&payload,&bytes) || bytes<64) return false;
    PrimeG2::NativeAppManifest::Manifest m;using PrimeG2::AppFileIndex::get;
    if(!PrimeG2::NativeAppManifest::parse(payload+64,get(payload+12),get(payload+8),get(payload+20),&m) ||
       m.abi!=1 || strcmp(m.id,id) || (supported && !PrimeG2::NativeAppManifest::supported(m))) return false;
    assert(sscanf(m.version,"%u.%u.%u",out->version,out->version+1,out->version+2)==3);out->schema=m.dataSchema;return true;
  }
  static bool same(void *,const uint8_t *a,const uint8_t *b) {return !memcmp(a,b,32);}
  static bool developer(void *ctx,const uint8_t *id) {
    unsigned protectedSigner=static_cast<Authority *>(ctx)->protectedSigner;
    return !(protectedSigner==1 && !memcmp(id,keyId,32)) && !(protectedSigner==2 && !memcmp(id,secondId,32));
  }
  static uint32_t serial(void *ctx) {return static_cast<Authority *>(ctx)->revision;}
};
struct Harness {
  std::unique_ptr<Volume> volume;
  Authority authority;
  std::unique_ptr<A::Session> session;
  uint32_t now=100;
  explicit Harness(Flash &f,Backend backend={}):volume(new Volume(backend.context?backend:f.backend())) {
    assert(volume->mount());session.reset(new A::Session(*volume,upload.data(),inspection.data(),upload.size(),
      {&authority,Authority::verify,Authority::same,Authority::serial,Authority::developer}));
  }
  A::TransferStatus status() {return session->status();}
  void settle() {
    unsigned i=0;while(session->needsPolling(now) && ++i<200000) session->poll(now++);
    assert(i<200000 && status().state!=TS::Working);
  }
  A::Request request(A::Operation op,const Bytes &bytes={},bool replace=true,uint32_t generation=0) {
    A::Request r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.generation=generation;strcpy(r.id,"document");
    r.nonce[0]=uint8_t(status().sequence+1);r.nonce[1]=42;
    if(op==A::Operation::Restore) {r.length=bytes.size();r.flags=replace?A::Replace:0;H::sha256(bytes.data(),bytes.size(),r.digest);}
    return r;
  }
  void begin(const A::Request &r,bool ack=true) {
    assert(session->request(0x91,0,reinterpret_cast<const uint8_t *>(&r),sizeof(r)));
    if(ack) {session->acknowledge();settle();}
  }
  void command(uint8_t cmd,const void *data,size_t bytes,uint32_t arg=0) {
    assert(session->request(cmd,arg,static_cast<const uint8_t *>(data),bytes));session->acknowledge();settle();
  }
  Bytes download() {
    Bytes out;
    while(status().state==TS::Readable) {
      auto s=status();uint8_t bytes[512];size_t count=0;
      assert(session->response(0x92,s.sequence,bytes,s.available,&count) && count==s.available);
      uint8_t again[512];assert(session->response(0x92,s.sequence,again,s.available,&count) && !memcmp(bytes,again,count));
      out.insert(out.end(),bytes,bytes+count);uint8_t ack[24];memcpy(ack,&s.sequence,4);uint32_t end=s.offset+count;
      memcpy(ack+4,&end,4);memcpy(ack+8,s.nonce,16);command(0x93,ack,sizeof(ack));
    }
    if(status().state==TS::Complete) {
      uint8_t hash[32];H::sha256(out.data(),out.size(),hash);assert(status().offset==out.size() && !memcmp(status().digest,hash,32));
    }
    return out;
  }
  A::Info info(bool health=false) {
    auto r=request(A::Operation::Inspect);if(health)r.flags=A::InspectRoot;
    begin(r);auto bytes=download();assert(status().state==TS::Complete && bytes.size()==sizeof(A::Info));
    A::Info out;memcpy(&out,bytes.data(),sizeof(out));return out;
  }
  A::RepairInfo repairInfo() {
    auto r=request(A::Operation::Inspect);r.flags=A::RepairCode;begin(r);auto bytes=download();
    assert(status().state==TS::Complete && bytes.size()==sizeof(A::RepairInfo));
    A::RepairInfo out;memcpy(&out,bytes.data(),sizeof(out));assert(out.info.size==256 && out.info.schema==2);return out;
  }
  void send(const Bytes &bytes,size_t limit=~size_t(0)) {
    while(status().offset<bytes.size() && status().offset<limit && status().state==TS::Writable) {
      auto s=status();uint8_t packet[512];memcpy(packet,&s.sequence,4);memcpy(packet+4,&s.offset,4);memcpy(packet+8,s.nonce,16);
      size_t n=std::min(size_t(488),std::min(bytes.size()-s.offset,limit-s.offset));memcpy(packet+24,bytes.data()+s.offset,n);
      command(0x92,packet,n+24);
    }
  }
  void commit() {auto s=status();assert(s.state==TS::Ready);command(0x94,s.nonce,16,s.sequence);}
};
static Bytes canonical(Flash &f,const char *id="document") {
  Raw raw(f);char path[64];snprintf(path,sizeof(path),"apps/%s.app",id);lfs_info info;
  int rc=lfs_stat(&raw.fs,path,&info);if(rc==LFS_ERR_NOENT) return {};assert(!rc);
  Bytes data(info.size);lfs_file_t file{};lfs_file_config cfg{};uint8_t cache[2048];cfg.buffer=cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDONLY,&cfg));
  assert(lfs_file_read(&raw.fs,&file,data.data(),data.size())==int(data.size()) && !lfs_file_close(&raw.fs,&file));return data;
}
struct RootFlash:Flash {
  std::set<uint32_t> unreadable;unsigned readFailures=0;
  Backend backend() {
    auto b=Flash::backend();b.read=[](void *ctx,uint32_t page,uint8_t *out) {
      auto &f=*static_cast<RootFlash *>(ctx);
      if(f.unreadable.count(page)) {memset(out,0xa5,PageBytes/2);f.readFailures++;return false;}
      return Flash::read(ctx,page,out);
    };return b;
  }
};
static void damage(Flash &f,bool legacy,unsigned mode) {
  char path[80];
  if(legacy) A::Source::canonicalPath("document",path);
  else {
    Root root;{auto v=std::make_unique<Volume>(f.backend());assert(v->mount() && v->documentRoot("document",&root));}
    A::Source::objectPath("document",'p',root.current.package,path);
  }
  Raw raw(f);
  if(!legacy && mode==1) {raw.remove(path);return;}
  lfs_file_t file{};lfs_file_config cfg{};uint8_t cache[2048];cfg.buffer=cache;
  assert(!lfs_file_opencfg(&raw.fs,&file,path,LFS_O_RDWR,&cfg));
  if(mode==2 || mode==3) assert(!lfs_file_truncate(&raw.fs,&file,legacy?(mode==2?64:64+352):17));
  else if(mode==4) {
    uint8_t extra=42;assert(lfs_file_seek(&raw.fs,&file,0,LFS_SEEK_END)>0);
    assert(lfs_file_write(&raw.fs,&file,&extra,1)==1);
  } else {
    unsigned offset=(legacy?64:0)+(mode==0?352:96);uint8_t byte;
    assert(lfs_file_seek(&raw.fs,&file,offset,LFS_SEEK_SET)==int(offset) && lfs_file_read(&raw.fs,&file,&byte,1)==1);
    byte^=128;assert(lfs_file_seek(&raw.fs,&file,offset,LFS_SEEK_SET)==int(offset) && lfs_file_write(&raw.fs,&file,&byte,1)==1);
  }
  assert(!lfs_file_close(&raw.fs,&file));
}
int main(int argc,char **argv) {
  assert(argc==2);std::string dir=argv[1];modulus=load(dir+"/modulus.bin");auto key=load(dir+"/identity.bin");memcpy(keyId,key.data(),32);
  secondModulus=load(dir+"/second-modulus.bin");auto second=load(dir+"/second-identity.bin");memcpy(secondId,second.data(),32);
  auto cross=load(dir+"/cross.arc");
  auto old=load(dir+"/old.pkg"),arc=load(dir+"/current.arc"),pending=load(dir+"/pending.arc"),same=load(dir+"/same.arc");
  Flash base=baseline(old);unsigned cases=0;
  for(bool existing:{false,true}) for(const auto *bytes:{&arc,&pending}) {
    Flash f=existing?base:baseline(old,false);auto other=canonical(f,"other");
    { Harness h(f);auto info=h.info();assert(bool(info.flags&A::Exists)==existing);
      h.begin(h.request(A::Operation::Restore,*bytes,true,info.generation));h.send(*bytes);h.commit();
      assert(h.status().state==TS::Complete && h.status().flags==A::Committed && h.authority.executed==1);
      info=h.info();assert(info.flags&A::IndexKnown);assert(bool(info.flags&A::Pending)==(bytes==&pending));
      h.begin(h.request(A::Operation::Export,{},false,info.generation));assert(h.download()==*bytes && h.status().state==TS::Complete);
    }
    assert(canonical(f,"other")==other);{Harness h(f);assert(h.info().version[0]==2);}cases++;
  }
  for(unsigned mode=0;mode<9;mode++) {
    Flash f=base;auto before=canonical(f);Harness h(f);auto info=h.info();auto r=h.request(A::Operation::Restore,arc,true,info.generation);
    if(mode==0) r.generation++;
    if(mode==1) r.flags=0;
    if(mode==2) r.digest[0]^=1;
    if(mode==3) h.authority.revoked=true;
    h.begin(r);h.send(arc);
    if(mode==4) {assert(h.status().state==TS::Ready);h.authority.revision++;h.commit();}
    else if(mode==5) {assert(h.status().state==TS::Ready);h.session->disconnect();h.settle();}
    else if(mode==6) {h.now+=30001;h.settle();}
    else if(mode==7 || mode==8) {
      auto s=h.status();assert(s.state==TS::Ready && h.session->request(0x94,s.sequence,s.nonce,16));
      if(mode==8) h.session->acknowledge();
      h.session->disconnect();h.session->abandonSetup();h.settle();
    }
    if(mode==8) assert(h.status().state==TS::Complete && h.status().flags==A::Committed);
    else assert(h.status().state==TS::Failed || h.status().state==TS::Cancelled);
    if(mode==0) assert(h.status().error==TE::Changed);
    if(mode==1) assert(h.status().error==TE::Exists);
    if(mode==2) assert(h.status().error==TE::Integrity);
    if(mode==3) assert(h.status().error==TE::Authority);
    if(mode==4) assert(h.status().error==TE::Changed);
    if(mode==6) assert(h.status().error==TE::Timeout);
    assert((canonical(f)==before)==(mode!=8));cases++;
  }
  for(auto op:{A::Operation::Inspect,A::Operation::Export,A::Operation::Restore}) for(bool ack:{false,true}) {
    Flash f=base;int writes=f.writes;Harness h(f);auto r=h.request(op,op==A::Operation::Restore?arc:Bytes{},true,op==A::Operation::Inspect?0:1);
    h.begin(r,ack);
    if(!ack) {assert(!h.session->needsPolling(h.now));h.session->abandonSetup();}
    else h.now+=30001;
    h.settle();assert(!h.session->busy() && h.status().state==TS::Cancelled && f.writes==writes);cases++;
  }
  { Flash f=base;Harness h(f);auto r=h.request(A::Operation::Restore,arc,true,1);h.begin(r);auto s=h.status();
    uint8_t packet[512]{};memcpy(packet,&s.sequence,4);memcpy(packet+8,s.nonce,16);memcpy(packet+24,arc.data(),488);
    packet[8]^=1;assert(!h.session->request(0x92,0,packet,sizeof(packet)));packet[8]^=1;
    packet[4]=1;assert(!h.session->request(0x92,0,packet,sizeof(packet)));packet[4]=0;
    assert(h.session->request(0x92,0,packet,sizeof(packet)));h.session->abandonSetup();assert(h.status().offset==0);
    h.send(arc,600);assert(h.status().offset==600);
    uint8_t wrong[16]{};assert(!h.session->request(0x95,s.sequence,wrong,16));
    h.command(0x95,s.nonce,16,s.sequence);assert(h.status().state==TS::Cancelled);
    uint32_t seq=h.status().sequence;assert(h.session->request(0x91,0,reinterpret_cast<uint8_t *>(&r),sizeof(r)));
    assert(!h.session->busy() && h.status().sequence==seq);cases++;
  }
  { Flash f=base;Harness h(f);auto info=h.info();h.begin(h.request(A::Operation::Restore,same,true,info.generation));h.send(same);h.commit();
    assert(h.status().state==TS::Complete);info=h.info();assert(info.version[0]==1);cases++;
  }
  for(const auto &invalid:{same,load(dir+"/changed.arc")}) {
    Flash f=base;Harness h(f);h.begin(h.request(A::Operation::Restore,arc,true,1));h.send(arc);h.commit();
    assert(h.status().state==TS::Complete);auto info=h.info();auto before=canonical(f);
    h.begin(h.request(A::Operation::Restore,invalid,true,info.generation));h.send(invalid);
    assert(h.status().state==TS::Failed && h.status().error==TE::Version && canonical(f)==before);cases++;
  }
  { Flash f=base;Harness h(f);h.authority.revoked=true;
    auto info=h.info();h.begin(h.request(A::Operation::Export,{},false,info.generation));auto bytes=h.download();
    assert(h.status().state==TS::Complete && !bytes.empty() && h.authority.inspected>=3 && !h.authority.executed);cases++;
  }
  // A corrupt index cannot hide an occupied namespace or prevent inspection of
  // independently signed code. Restore repairs it without reading old data.
  { Flash f=base;
    {Harness h(f);h.begin(h.request(A::Operation::Restore,arc,true,1));h.send(arc);h.commit();}
    Root root;{auto v=std::make_unique<Volume>(f.backend());assert(v->mount() && v->documentRoot("document",&root));}
    {Raw raw(f);char path[80];A::Source::objectPath("document",'d',root.current.data,path);raw.corrupt(path);}
    { Harness h(f);unsigned names=0;
      assert(h.volume->namespaceState("document")==1 && !h.volume->namespaceState("absent"));
      assert(h.volume->list([](void *ctx,const char *,const Entry &) {++*static_cast<unsigned *>(ctx);return true;},&names,true) && names==2);
      auto info=h.info();assert(info.flags&A::Exists);assert(!(info.flags&A::IndexKnown));
      h.begin(h.request(A::Operation::Restore,arc,true,info.generation));h.send(arc);h.commit();assert(h.status().state==TS::Complete);
      info=h.info();assert(info.flags&A::IndexKnown);
    }cases++;
  }
  // Cross-signer fresh restore is deliberately unavailable without an explicit
  // option, valid signatures, complete hash verification and rendered OS input.
  for(unsigned mode=0;mode<16;mode++) {
    Flash f=baseline(old,false);auto other=canonical(f,"other");Harness h(f);
    auto r=h.request(A::Operation::Restore,cross,false,0);
    if(mode!=0) r.flags=A::AllowRecoveryPair;
    if(mode==1) h.authority.unknownPrevious=true;
    if(mode==2) h.authority.revoked=true;
    if(mode==3) r.digest[0]^=1;
    h.begin(r);h.send(cross);
    if(mode<=3) {
      assert(h.status().state==TS::Failed && !h.session->needsPresentation());
      assert(h.status().error==(mode==3?TE::Integrity:TE::Authority));
    } else {
      auto waiting=h.status();assert(waiting.state==TS::AwaitUser && h.session->needsPresentation());
      assert(waiting.offset==cross.size() && !memcmp(waiting.digest,r.digest,32));
      assert(!h.session->request(0x94,waiting.sequence,waiting.nonce,16));
      A::ApprovalInfo info;size_t bytes;
      assert(!h.session->response(0x96,waiting.sequence+1,reinterpret_cast<uint8_t *>(&info),sizeof(info),&bytes));
      assert(h.session->response(0x96,waiting.sequence,reinterpret_cast<uint8_t *>(&info),sizeof(info),&bytes));
      assert(bytes==216 && info.sequence==waiting.sequence && !strcmp(info.id,"document") &&
        info.version[0]==2 && info.previousVersion[0]==1 && !memcmp(info.currentSigner,keyId,32) &&
        !memcmp(info.previousSigner,secondId,32) && !memcmp(info.digest,r.digest,32) && !memcmp(info.nonce,r.nonce,16));
      h.session->observeKeyboard(uint64_t(1)<<56);assert(!h.session->approve(h.now));
      assert(h.session->present() && !h.session->present());assert(!h.session->approve(h.now));
      h.session->rendered();assert(!h.session->approve(h.now));
      h.session->observeKeyboard(0);h.session->observeKeyboard((uint64_t(1)<<56)|1);assert(!h.session->approve(h.now));
      h.session->observeKeyboard(uint64_t(1)<<56);
      if(mode==4) h.session->dismiss();
      else if(mode==5) h.session->disconnect();
      else if(mode==6) h.session->deny();
      else if(mode==7) h.now+=120001;
      else if(mode==8) {h.authority.revision++;assert(h.session->approve(h.now));}
      else if(mode==9) {h.now+=120001;assert(!h.session->approve(h.now));}
      else {
        assert(h.session->approve(h.now) && h.status().state==TS::Ready);
        assert(!h.session->approve(h.now));
        if(mode==10) {h.authority.revision++;h.commit();}
        else if(mode==11) {h.session->dismiss();}
        else if(mode==12) {h.now+=30001;}
        else if(mode==13) h.commit();
        else {
          auto ready=h.status();assert(h.session->request(0x94,ready.sequence,ready.nonce,16));
          if(mode==15) h.session->acknowledge();
          h.session->dismiss();h.session->disconnect();h.session->abandonSetup();
        }
      }
      h.settle();
      if(mode==13 || mode==15) {
        assert(h.status().state==TS::Complete && h.status().flags==(A::Committed|A::RecoveryPair));
        auto restored=h.info();assert(restored.flags&A::Pending);
        h.begin(h.request(A::Operation::Export,{},false,restored.generation));assert(h.download()==cross);
        // This calculator now owns the exact retained recovery pair; ordinary
        // replacement of its archive does not ask for another trust grant.
        h.begin(h.request(A::Operation::Restore,cross,true,restored.generation));h.send(cross);h.commit();
        assert(h.status().state==TS::Complete);
      } else {
        assert(h.status().state==TS::Failed || h.status().state==TS::Cancelled);
        if(mode==6) assert(h.status().error==TE::Denied);
        if(mode==7 || mode==9 || mode==12) assert(h.status().error==TE::Timeout);
        if(mode==8 || mode==10) assert(h.status().error==TE::Changed);
      }
    }
    assert(canonical(f,"other")==other);
    assert(canonical(f).empty()==(mode!=13 && mode!=15));cases++;
  }
  {Flash f=base;Harness h(f);auto before=canonical(f);auto r=h.request(A::Operation::Restore,cross,true,1);
    r.flags|=A::AllowRecoveryPair;h.begin(r);assert(h.status().state==TS::Failed && h.status().error==TE::Exists);
    assert(canonical(f)==before);cases++;
  }
  for(unsigned protectedSigner:{1u,2u}) {
    Flash f=baseline(old,false);Harness h(f);h.authority.protectedSigner=protectedSigner;
    auto r=h.request(A::Operation::Restore,cross,false,0);r.flags=A::AllowRecoveryPair;
    h.begin(r);h.send(cross);assert(h.status().state==TS::Failed && h.status().error==TE::Authority);
    assert(!h.session->needsPresentation() && canonical(f).empty());cases++;
  }
  unsigned repairCases=0;
  auto original=load(dir+"/original.arc"),wrongPrivate=load(dir+"/wrong-private.arc");
  for(bool legacy:{false,true}) for(unsigned mode=0;mode<5;mode++) {
    Flash f=base;
    if(!legacy) {Harness h(f);h.begin(h.request(A::Operation::Restore,pending,true,1));h.send(pending);h.commit();}
    if(!legacy) {Raw raw(f);A::Source source(&raw.fs);A::SourceInfo before;assert(source.inspect("document",&before)==A::Source::Result::Ok);
      auto root=before.root;root.highVersion[0]=9;raw.root(root);}
    damage(f,legacy,mode);auto before=canonical(f),other=canonical(f,"other");
    {Harness h(f);h.begin(h.request(A::Operation::Inspect));assert(h.status().state==TS::Failed);
      auto info=h.repairInfo();assert(info.info.flags&A::CodeUnavailable);
      assert(bool(info.info.flags&A::Legacy)==legacy && !memcmp(info.info.signer,Bytes(32).data(),32));
      assert(!info.info.version[0] && !info.info.appSchema);
      if(legacy) assert(!memcmp(info.legacyHash,before.data()+24,32));
      else assert(info.info.highVersion[0]==9 && (info.info.flags&A::Pending));
      const auto &archive=legacy?original:pending;
      auto r=h.request(A::Operation::Restore,archive,true,info.info.generation);r.flags|=A::RepairCode;
      h.begin(r);h.send(archive);assert(h.status().state==TS::Ready && h.status().flags==A::CodeRepair);h.commit();
      assert(h.status().state==TS::Complete && h.status().flags==(A::Committed|A::CodeRepair));
      auto restored=h.info();assert(restored.flags&A::IndexKnown);
      if(!legacy) assert(restored.highVersion[0]==9 && (restored.flags&A::Pending));
    }
    {Harness h(f);assert(h.info().version[0]==(legacy?1u:2u));}
    assert(canonical(f)!=before && canonical(f,"other")==other);repairCases++;
  }
  // A readable signed prefix proves code identity even for a different private
  // backup. A damaged prefix requires the exact combined FILE2 snapshot.
  for(unsigned mode=0;mode<3;mode++) {
    Flash f=base;damage(f,true,mode);auto before=canonical(f);
    Harness h(f);auto info=h.repairInfo();auto r=h.request(A::Operation::Restore,wrongPrivate,true,info.info.generation);r.flags|=A::RepairCode;
    h.begin(r);h.send(wrongPrivate);
    if(mode==0) {h.commit();assert(h.status().state==TS::Complete);}
    else assert(h.status().state==TS::Failed && h.status().error==TE::Authority && canonical(f)==before);
    repairCases++;
  }
  // Exact code, enrolled/active trust, retained authority and generation still
  // bind repair. Exercise failures during and after streaming and cancellation.
  for(unsigned mode=0;mode<9;mode++) {
    Flash f=base;{Harness h(f);h.begin(h.request(A::Operation::Restore,pending,true,1));h.send(pending);h.commit();}
    damage(f,false,1);auto before=canonical(f);Harness h(f);auto info=h.repairInfo();
    const auto &archive=mode==0?same:mode==1?cross:pending;
    auto r=h.request(A::Operation::Restore,archive,true,info.info.generation);r.flags|=A::RepairCode;
    if(mode==2) h.authority.revoked=true;
    if(mode==3) r.generation++;
    if(mode==4) r.digest[0]^=1;
    h.begin(r);h.send(archive);
    if(mode>=5) {
      assert(h.status().state==TS::Ready);
      if(mode==5) {h.authority.revision++;h.commit();}
      if(mode==6) {h.session->disconnect();h.settle();}
      if(mode==7) {h.now+=30001;h.settle();}
      if(mode==8) {Raw raw(f);A::Source source(&raw.fs);A::SourceInfo changed;assert(source.inspect("document",&changed)==A::Source::Result::Ok);
        auto root=changed.root;root.highVersion[0]=7;raw.root(root);before=canonical(f);h.commit();}
    }
    assert((h.status().state==TS::Failed || h.status().state==TS::Cancelled) && canonical(f)==before);repairCases++;
  }
  for(unsigned mode=0;mode<3;mode++) {
    Flash f=baseline(old,mode!=0);
    if(mode==2) {Raw raw(f);raw.corruptRoot("apps/document.app");}
    auto before=canonical(f);int writes=f.writes;Harness h(f);
    auto r=h.request(A::Operation::Restore,original,true,mode?1:0);r.flags|=A::RepairCode;h.begin(r);
    assert(h.status().state==TS::Failed && canonical(f)==before && f.writes==writes);repairCases++;
  }
  for(auto flags:{uint32_t(A::RepairCode),A::RepairCode|A::AllowRecoveryPair,A::Replace|A::RepairCode|A::AllowRecoveryPair}) {
    Flash f=base;Harness h(f);auto r=h.request(A::Operation::Restore,original,true,1);r.flags=flags;
    assert(!A::Session::valid(r));repairCases++;
  }
  unsigned repairCuts=0;
  for(bool legacy:{false,true}) {
    Flash source=base;
    if(!legacy) {
      auto v=std::make_unique<Volume>(source.backend());assert(v->mount());uint32_t version[3]={1,0,0};
      assert(v->beginCheckpoint("document",reinterpret_cast<const uint8_t *>("old"),3,version,0));finish(*v);
    }
    damage(source,legacy,legacy?2:1);auto before=canonical(source),other=canonical(source,"other");
    auto apply=[&](Flash &f) {
      Harness h(f);auto info=h.repairInfo();auto r=h.request(A::Operation::Restore,original,true,info.info.generation);r.flags|=A::RepairCode;
      h.begin(r);h.send(original);h.commit();assert(h.status().state==TS::Complete);
    };
    Flash done=source;int writes=done.writes;apply(done);writes=done.writes-writes;auto after=canonical(done);
    for(bool torn:{false,true}) for(int cut=0;cut<=writes;cut++) {
      Flash trial=source;trial.torn=torn;trial.cut=trial.writes+cut;
      try {apply(trial);} catch(PowerCut &) {}
      trial.cut=-1;auto root=canonical(trial);assert(root==before || root==after);
      if(root==after) {Harness h(trial);assert(h.info().version[0]==1);}
      assert(canonical(trial,"other")==other);repairCuts++;
    }
  }
  unsigned unreadableMediaCases=0;
  for(bool legacy:{false,true}) {
    Flash source=base;
    if(!legacy) {
      auto v=std::make_unique<Volume>(source.backend());assert(v->mount());uint32_t version[3]={1,0,0};
      assert(v->beginCheckpoint("document",reinterpret_cast<const uint8_t *>("old"),3,version,0));finish(*v);
      Root historical;assert(v->documentRoot("document",&historical));v.reset();Raw raw(source);raw.root(historical);
    }
    auto original=canonical(source),other=canonical(source,"other");std::set<uint32_t> unavailable;
    {Raw raw(source);lfs_file_t file{};lfs_file_config cfg{};uint8_t cache[2048];cfg.buffer=cache;
      assert(!lfs_file_opencfg(&raw.fs,&file,"apps/document.app",LFS_O_RDONLY,&cfg));
      if(legacy) {
        assert(!(file.flags&LFS_F_INLINE));unavailable.insert(FirstBlock+2+file.ctz.head);
      } else {
        assert(file.flags&LFS_F_INLINE);
        // Lose both metadata copies for the inline canonical root. This can
        // make sibling entries temporarily unreadable too; nothing may write.
        for(auto block:file.m.pair) unavailable.insert(FirstBlock+2+block);
      }
      assert(!lfs_file_close(&raw.fs,&file));
    }
    for(unsigned operation=0;operation<4;operation++) {
      Flash f=source;int writes=f.writes;
      {Harness h(f);f.bad=unavailable;
        auto r=h.request(operation<2?A::Operation::Inspect:operation==2?A::Operation::Restore:A::Operation::Export,
          operation==2?arc:Bytes{});
        if(operation==1 || operation==2) r.flags|=A::RepairCode;
        h.begin(r);
        if(h.status().error!=TE::IO) fprintf(stderr,"unreadable legacy=%u operation=%u returned error=%u\n",legacy,operation,unsigned(h.status().error));
        assert(h.status().state==TS::Failed && h.status().error==TE::IO && !h.session->busy());
      }
      assert(f.writes==writes && f.pages==source.pages);
      f.bad.clear();assert(canonical(f)==original && canonical(f,"other")==other);
      {Harness h(f);assert(h.info().flags&A::Exists);}
      unreadableMediaCases++;
    }
  }
  // Recover the actual signed pending pair from one surviving root copy. The
  // high-water mark deliberately exceeds both signed versions; a root hash
  // must never let recovery forget that history or grant another signer.
  Flash protectedBase=base;Root protectedRoot;Bytes expectedArchive;
  {Harness h(protectedBase);h.begin(h.request(A::Operation::Restore,pending,true,1));h.send(pending);h.commit();assert(h.status().state==TS::Complete);}
  {Raw raw(protectedBase);PrimeG2::AppDocumentStore::Store docs(&raw.fs);assert(docs.root("document",&protectedRoot));
    protectedRoot.highVersion[0]=9;raw.root(protectedRoot);}
  {Harness h(protectedBase);auto info=h.info(true);assert(!(info.flags&A::RootReplicated));
    h.begin(h.request(A::Operation::Restore,pending,true,info.generation));h.send(pending);h.commit();assert(h.status().state==TS::Complete);
    info=h.info(true);assert(info.highVersion[0]==9 && info.flags&A::Pending);
    h.begin(h.request(A::Operation::Export,{},false,info.generation));expectedArchive=h.download();assert(h.status().state==TS::Complete);}
  unsigned primary;
  {Raw raw(protectedBase);PrimeG2::AppDocumentStore::Store docs(&raw.fs);assert(docs.root("document",&protectedRoot));
    lfs_file_t file{};lfs_file_config cfg{};cfg.buffer=raw.cache;
    assert(!lfs_file_opencfg(&raw.fs,&file,"apps/document.app",LFS_O_RDONLY,&cfg));
    assert(!(file.flags&LFS_F_INLINE) && lfs_file_size(&raw.fs,&file)==PrimeG2::AppRootRecord::Bytes);
    primary=(FirstBlock+2+file.ctz.head)*PagesPerBlock;assert(!lfs_file_close(&raw.fs,&file));}
  const auto downgrade=load(dir+"/downgrade.arc"),outsider=load(dir+"/wrong-owner.arc");
  unsigned rootCases=0,rootRefusals=0;
  for(unsigned mode=0;mode<10;mode++) {
    namespace R=PrimeG2::AppRootRecord;
    RootFlash f;static_cast<Flash &>(f)=protectedBase;
    if(mode==1 || mode==9)f.unreadable.insert(primary);
    if(mode==2 || mode==8)f.pages.at(primary)[81]^=1;
    {Raw raw(f);
      if(mode==3)assert(!lfs_removeattr(&raw.fs,"apps/document.app",R::Attribute));
      if(mode>=4) {
        uint8_t wire[R::Bytes];Root altered=protectedRoot;if(mode==5)altered.serial++;
        assert(R::encode(mode==6?"other":"document",altered,wire));
        if(mode==4 || mode==8 || mode==9)wire[81]^=1;
        if(mode==7) {wire[8]=6;H::sha256(wire,R::Bytes-32,wire+R::Bytes-32);}
        assert(!lfs_setattr(&raw.fs,"apps/document.app",R::Attribute,wire,R::Bytes));
      }
    }
    auto before=canonical(f);auto pages=f.pages;int writes=f.writes;
    {Harness h(f,f.backend());
      if(mode>=5) {
        for(auto op:{A::Operation::Inspect,A::Operation::Export,A::Operation::Restore}) {
          auto r=h.request(op,op==A::Operation::Restore?pending:Bytes{},true,op==A::Operation::Inspect?0:protectedRoot.serial);
          h.begin(r);assert(h.status().state==TS::Failed && h.status().error==(mode==9?TE::IO:TE::Integrity));
          assert(f.pages==pages && f.writes==writes);rootRefusals++;
        }
      } else {
        auto oldInfo=h.info();assert(!(oldInfo.flags&(A::RootReplicated|A::RootPayloadValid|A::RootAttributeValid)));
        auto info=h.info(true);assert(info.highVersion[0]==9 && info.flags&A::Pending && !memcmp(info.signer,keyId,32));
        unsigned copies=mode==1 || mode==2?A::RootAttributeValid:mode==3 || mode==4?A::RootPayloadValid:(A::RootPayloadValid|A::RootAttributeValid);
        assert((info.flags&448)==(A::RootReplicated|copies));
        h.begin(h.request(A::Operation::Export,{},false,info.generation));assert(h.download()==expectedArchive && h.status().state==TS::Complete);
        assert(f.pages==pages && f.writes==writes);
        for(unsigned refused=0;refused<3;refused++) {
          h.authority.revoked=refused==2;
          const auto &bad=refused==0?downgrade:refused==1?outsider:expectedArchive;
          h.begin(h.request(A::Operation::Restore,bad,true,info.generation));h.send(bad);
          assert(h.status().state==TS::Failed && h.status().error==(refused==0?TE::Version:TE::Authority));
          assert(canonical(f)==before);rootRefusals++;
        }
        h.authority.revoked=false;
        h.begin(h.request(A::Operation::Restore,expectedArchive,true,info.generation));h.send(expectedArchive);h.commit();assert(h.status().state==TS::Complete);
        auto restored=h.info(true);assert((restored.flags&448)==448 && restored.highVersion[0]==9 && restored.flags&A::Pending);
        h.begin(h.request(A::Operation::Export,{},false,restored.generation));assert(h.download()==expectedArchive && h.status().state==TS::Complete);
      }
    }
    if(mode==1 || mode==9)assert(f.readFailures);
    f.unreadable.clear();assert(canonical(f,"other")==canonical(protectedBase,"other"));
    if(mode<5) {Harness cold(f,f.backend());auto info=cold.info(true);assert((info.flags&448)==448 && info.highVersion[0]==9 && info.flags&A::Pending);}
    rootCases++;
  }
  printf("{\"cases\":%u,\"repair_cases\":%u,\"repair_interruption_cases\":%u,\"unreadable_media_cases\":%u,\"root_recovery_cases\":%u,\"root_authority_refusals\":%u,\"session_bytes\":%zu}\n",
    cases,repairCases,repairCuts,unreadableMediaCases,rootCases,rootRefusals,sizeof(A::Session));
}

// SPDX-License-Identifier: GPL-3.0-or-later
#include "app_data_session.h"
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
using Data=PrimeG2::AppData::Session;
using Files=PrimeG2::AppFiles::Session;
static uint32_t version[3]={1,0,0};
static std::vector<uint8_t> package(MaximumPackage),scratch(MaximumData);
struct Probe {
  Flash &flash;bool forbidden=false;
  Backend backend() {
    return {this,
      [](void *p,uint32_t b){auto &x=*static_cast<Probe *>(p);assert(!x.forbidden);return Flash::usable(&x.flash,b);},
      [](void *p,uint32_t n,uint8_t *out){auto &x=*static_cast<Probe *>(p);assert(!x.forbidden);return Flash::read(&x.flash,n,out);},
      [](void *p,uint32_t b){auto &x=*static_cast<Probe *>(p);assert(!x.forbidden);return Flash::erase(&x.flash,b);},
      [](void *p,uint32_t n,const uint8_t *in){auto &x=*static_cast<Probe *>(p);assert(!x.forbidden);return Flash::program(&x.flash,n,in);}};
  }
};
static void finish(Volume &v) {
  for(unsigned i=0;i<200000 && v.state()!=State::Complete && v.state()!=State::Failed;i++) v.step();
  assert(v.state()==State::Complete);
}
static void initialize(Volume &v) {
  assert(v.initialize(package.data(),package.size(),scratch.data(),scratch.size(),
    [](const uint8_t *,size_t,char id[49]){strcpy(id,"data-app");return true;}));
}
static LefonyDataRequest request(uint32_t op,uint32_t generation=0,uint32_t schema=0,uint32_t bytes=0) {
  LefonyDataRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.generation=generation;r.dataSchema=schema;r.bytes=bytes;return r;
}
static LefonyDataRequest wait(Data &s,uint32_t token) {
  for(unsigned i=0;i<200000;i++) {
    s.poll();auto r=request(LEFONY_DATA_POLL);r.token=token;
    int n=s.request(r);assert(n==0 || n==1);if(!n) return r;
  }
  assert(false);return {};
}
static LefonyDataRequest call(Data &s,LefonyDataRequest r) {assert(s.request(r)==1);return wait(s,r.token);}
static LefonyDataRequest info(Data &s) {auto r=call(s,request(LEFONY_DATA_INSPECT));assert(!r.error);return r;}
static void attach(Data &data,Files &files,uint8_t *committed,uint32_t bytes,uint32_t appSchema=0,uint32_t savedSchema=0) {
  assert(data.attach("data-app",version,appSchema,savedSchema,committed,bytes));
  assert(files.attach("data-app",version,appSchema,savedSchema,committed,bytes));
}
static void detach(Data &data,Files &files) {
  data.finish(true);
  for(unsigned i=0;i<200000 && data.needsPolling();i++) data.poll();
  assert(data.reset());files.detach();
  for(unsigned i=0;i<200000 && files.active();i++) files.poll();
  assert(!files.active());
}
static std::vector<uint8_t> saved(Volume &v,const char *id="data-app") {
  Entry e;assert(v.entry(id,&e));
  assert(v.read(id,package.data(),package.size(),scratch.data(),scratch.size()));
  return {scratch.begin(),scratch.begin()+e.dataBytes};
}
static LefonyFileRequest fileCall(Files &files,uint32_t op,const char *path=nullptr,uint32_t handle=0,
                                 const void *input=nullptr,uint32_t bytes=0,uint32_t flags=0) {
  LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=op;r.handle=handle;r.flags=flags;
  if(path) {r.path=1;r.pathBytes=strlen(path);}if(input) {r.buffer=1;r.length=bytes;}
  assert(files.exchange(r,path,nullptr,input,nullptr)==1);
  for(unsigned i=0;i<200000;i++) {
    files.poll();LefonyFileRequest p{};p.size=sizeof(p);p.schema=1;p.operation=LEFONY_FILE_POLL;p.token=r.token;
    int n=files.exchange(p,nullptr,nullptr,nullptr,nullptr);assert(n==0 || n==1);if(!n) return p;
  }
  assert(false);return {};
}
static void writeFile(Files &files,const char *path,const char *text) {
  auto r=fileCall(files,LEFONY_FILE_OPEN,path,0,nullptr,0,LEFONY_FILE_WRITABLE|LEFONY_FILE_CREATE|LEFONY_FILE_TRUNCATE);
  assert(!r.error && r.result>0);uint32_t handle=r.result;
  assert(!fileCall(files,LEFONY_FILE_WRITE,nullptr,handle,text,strlen(text)).error);
  assert(!fileCall(files,LEFONY_FILE_CLOSE,nullptr,handle).error);
}
static std::vector<uint8_t> file(Volume &v,const char *path) {
  uint32_t token=v.openSnapshot("data-app",path);assert(token);std::vector<uint8_t> data;uint8_t out[2048];
  for(unsigned i=0;i<200000;i++) {
    int n=v.readSnapshot("data-app",token,out,sizeof(out));
    if(n==-2) {assert(v.stepSnapshot("data-app",token));continue;}
    assert(n>=0);if(!n) {assert(v.closeSnapshot("data-app",token));return data;}
    data.insert(data.end(),out,out+n);
  }
  assert(false);return {};
}
int main() {
  Flash base;Probe probe{base};auto v=std::make_unique<Volume>(probe.backend());initialize(*v);
  uint8_t app[468]{},initial[4]={1,2,3,4};
  for(const char *id:{"data-app","other"}) {assert(v->begin(id,app,sizeof(app),initial,4));finish(*v);}
  uint8_t committed[MaximumData];memcpy(committed,initial,4);
  Files files(*v);auto data=std::make_unique<Data>(*v,files);attach(*data,files,committed,4);
  int writes=base.writes;auto state=info(*data);assert(base.writes==writes && !state.flags && state.bytes==4);
  auto pending=request(LEFONY_DATA_CHECKPOINT,state.generation,0,4);
  const uint8_t first[4]={5,6,7,8},later[4]={9,10,11,12};
  probe.forbidden=true;
  assert(data->write(0,first,4)==4);assert(data->request(pending)==1);
  auto poll=request(LEFONY_DATA_POLL);poll.token=pending.token;assert(data->request(poll)==1);
  // Change the app's live bytes after submission. The durable snapshot must
  // retain 'first', and the later revision must still be dirty on completion.
  assert(data->write(0,later,4)==4);probe.forbidden=false;
  state=wait(*data,pending.token);
  assert(!state.error && state.flags==(LEFONY_DATA_DIRTY|LEFONY_DATA_COMMITTED));
  assert(state.editRevision!=state.snapshotRevision && !memcmp(committed,first,4));
  assert(saved(*v)==std::vector<uint8_t>(first,first+4));
  uint8_t actual[4];assert(data->read(0,actual,4)==4 && !memcmp(actual,later,4));
  auto replay=request(LEFONY_DATA_POLL);replay.token=pending.token;assert(data->request(replay)==-LEFONY_FILE_INVALID);
  state=call(*data,request(LEFONY_DATA_CHECKPOINT,state.generation,0,4));
  assert(!state.error && state.flags==LEFONY_DATA_COMMITTED && !data->dirty());
  assert(saved(*v)==std::vector<uint8_t>(later,later+4));
  assert(v->checkpointPackageWrites()==0);
  writes=base.writes;
  auto stale=call(*data,request(LEFONY_DATA_CHECKPOINT,state.generation-1,0,4));
  assert(stale.error==LEFONY_FILE_CHANGED && writes==base.writes);
  pending=request(LEFONY_DATA_CHECKPOINT,state.generation,0,0);probe.forbidden=true;
  assert(data->request(pending)==1);auto cancel=request(LEFONY_DATA_CANCEL);cancel.token=pending.token;
  assert(!data->request(cancel));probe.forbidden=false;
  assert(wait(*data,pending.token).state==LEFONY_DATA_CANCELLED && base.writes==writes && data->bytes()==4);
  state=call(*data,request(LEFONY_DATA_CHECKPOINT,state.generation,0,0));
  assert(!state.error && state.bytes==0 && data->bytes()==0 && saved(*v).empty());
  // Open descriptors block checkpoint/migration rather than being invalidated.
  writeFile(files,"document.bin","old document");
  auto reader=fileCall(files,LEFONY_FILE_OPEN,"document.bin",0,nullptr,0,LEFONY_FILE_READABLE);
  assert(!reader.error);auto busy=request(LEFONY_DATA_INSPECT);assert(data->request(busy)==-LEFONY_FILE_BUSY);
  assert(!fileCall(files,LEFONY_FILE_CLOSE,nullptr,reader.result).error);
  state=info(*data);assert(data->write(0,first,4)==4);
  state=call(*data,request(LEFONY_DATA_CHECKPOINT,state.generation,0,4));assert(!state.error);
  assert(file(*v,"document.bin")==std::vector<uint8_t>({'o','l','d',' ','d','o','c','u','m','e','n','t'}));
  detach(*data,files);v.reset();

  // Every programmed/erased interruption boundary in a FILE4 private-byte
  // checkpoint cold-recovers to exact old or new bytes, retaining named files
  // and the other app. Both torn and clean interruption models are exercised.
  Flash baseline=base,completed=base;
  unsigned cancelledCases=0,committedAfterCancel=0;
  auto checkpoint=[&](Flash &flash,int cancelAtStep=-1) {
    auto volume=std::make_unique<Volume>(flash.backend());assert(volume->mount());
    auto bytes=saved(*volume);uint8_t snapshot[MaximumData];memcpy(snapshot,bytes.data(),bytes.size());
    Files f(*volume);auto d=std::make_unique<Data>(*volume,f);attach(*d,f,snapshot,bytes.size());
    auto infoBefore=info(*d);assert(d->write(0,later,4)==4);
    auto r=request(LEFONY_DATA_CHECKPOINT,infoBefore.generation,0,4);assert(d->request(r)==1);
    unsigned steps=0;LefonyDataRequest result{};
    for(;steps<200000;steps++) {
      if(static_cast<int>(steps)==cancelAtStep) {
        auto c=request(LEFONY_DATA_CANCEL);c.token=r.token;assert(!d->request(c));
      }
      d->poll();result=request(LEFONY_DATA_POLL);result.token=r.token;
      int n=d->request(result);assert(n==0 || n==1);if(!n) break;
    }
    assert(steps<200000);
    if(result.state==LEFONY_DATA_CANCELLED) {
      assert(cancelAtStep>=0 && !(result.flags&LEFONY_DATA_COMMITTED));
      assert(saved(*volume)==bytes);cancelledCases++;
    } else {
      assert(!result.error && (result.flags&LEFONY_DATA_COMMITTED));
      assert(saved(*volume)==std::vector<uint8_t>(later,later+4));
      if(cancelAtStep>=0) committedAfterCancel++;
    }
    detach(*d,f);return steps+1;
  };
  int beforeWrites=completed.writes;unsigned pollingSteps=checkpoint(completed);int mutations=completed.writes-beforeWrites;
  unsigned cuts=0;
  for(bool torn:{false,true}) for(int cut=0;cut<=mutations;cut++) {
    Flash trial=baseline;trial.cut=trial.writes+cut;trial.torn=torn;
    try {checkpoint(trial);} catch(PowerCut &) {}
    trial.cut=-1;auto recovered=std::make_unique<Volume>(trial.backend());assert(recovered->mount());
    auto result=saved(*recovered);assert(result==std::vector<uint8_t>(first,first+4) || result==std::vector<uint8_t>(later,later+4));
    assert(saved(*recovered,"other")==std::vector<uint8_t>(initial,initial+4));
    assert(file(*recovered,"document.bin")==std::vector<uint8_t>({'o','l','d',' ','d','o','c','u','m','e','n','t'}));cuts++;
  }
  // The volume's coarse Committing state includes index preparation. Cancel
  // at every actual controller step and verify the root/result relationship,
  // including the later point after which cancellation must drain the commit.
  for(unsigned step=0;step<pollingSteps;step++) {Flash trial=baseline;checkpoint(trial,step);}
  assert(cancelledCases && committedAfterCancel);

  for(bool save:{false,true}) {
    Flash trial=baseline;auto volume=std::make_unique<Volume>(trial.backend());assert(volume->mount());
    auto before=saved(*volume);uint8_t snapshot[MaximumData];memcpy(snapshot,before.data(),before.size());
    Files f(*volume);auto d=std::make_unique<Data>(*volume,f);attach(*d,f,snapshot,before.size());
    auto state=info(*d);assert(d->write(0,later,4)==4);
    auto r=request(LEFONY_DATA_CHECKPOINT,state.generation,0,4);assert(d->request(r)==1);
    d->poll();assert(d->needsPolling());d->finish(save);
    assert(d->write(0,first,4)==-1);
    for(unsigned i=0;i<200000 && d->needsPolling();i++) d->poll();
    assert(!d->needsPolling());
    assert(saved(*volume)==(save?std::vector<uint8_t>(later,later+4):before));
    detach(*d,f);
  }

  // An upgraded app explicitly enters migration, changes a named document and
  // checkpoints new private bytes/schema. The old complete pair remains until
  // acceptance, and rollback still preserves the highest installed version.
  auto migrate=[&](Flash &flash,bool accept) {
    auto volume=std::make_unique<Volume>(flash.backend());assert(volume->mount());
    uint32_t nextVersion[3]={2,0,0};uint8_t nextApp[468];memset(nextApp,0x45,sizeof(nextApp));
    assert(volume->beginUpgrade("data-app",nextApp,sizeof(nextApp),nextVersion));finish(*volume);
    auto old=saved(*volume);uint8_t snap[MaximumData];memcpy(snap,old.data(),old.size());
    Files f(*volume);auto d=std::make_unique<Data>(*volume,f);
    assert(d->attach("data-app",nextVersion,1,0,snap,old.size()));
    assert(f.attach("data-app",nextVersion,1,0,snap,old.size()));
    assert(d->write(0,later,4)==-1);
    assert(fileCall(f,LEFONY_FILE_OPEN,"document.bin",0,nullptr,0,LEFONY_FILE_WRITABLE).error==LEFONY_FILE_SCHEMA);
    auto s=info(*d);assert(s.flags&LEFONY_DATA_PENDING_UPGRADE);
    auto r=call(*d,request(LEFONY_DATA_BEGIN_MIGRATION,s.generation,1));assert(!r.error && d->migrating());
    assert(d->write(0,later,4)==4);writeFile(f,"document.bin","migrated document");
    s=info(*d);r=call(*d,request(LEFONY_DATA_CHECKPOINT,s.generation,1,4));
    assert(!r.error && r.dataSchema==1 && (r.flags&LEFONY_DATA_PENDING_UPGRADE));
    Root root;assert(volume->documentRoot("data-app",&root));assert(root.previous.dataSchema==0);
    if(accept) {
      assert(d->write(0,later,4)==4);
      assert(call(*d,request(LEFONY_DATA_ACCEPT,r.generation,1)).error==LEFONY_FILE_BUSY);
      r=call(*d,request(LEFONY_DATA_CHECKPOINT,r.generation,1,4));assert(!r.error);
      r=call(*d,request(LEFONY_DATA_ACCEPT,r.generation,1));assert(!r.error && r.flags==LEFONY_DATA_COMMITTED);
      assert(!d->migrating());
    }
    detach(*d,f);
    if(!accept) {assert(volume->beginRollback("data-app"));finish(*volume);}
    assert(volume->documentRoot("data-app",&root));assert(!root.flags && root.highVersion[0]==2);
    assert(saved(*volume)==(accept?std::vector<uint8_t>(later,later+4):old));
    auto bytes=file(*volume,"document.bin");const char *expected=accept?"migrated document":"old document";
    assert(bytes==std::vector<uint8_t>(expected,expected+strlen(expected)));
    assert(!volume->beginUpgrade("data-app",nextApp,sizeof(nextApp),nextVersion));
  };
  Flash rollback=baseline,accepted=baseline;migrate(rollback,false);migrate(accepted,true);
  printf("{\"status\":\"passed\",\"checkpoint_interruption_cases\":%u,\"cancelled_cases\":%u,\"committed_after_cancel\":%u,\"migration_rollback\":true,\"explicit_acceptance\":true,\"physical\":\"not_tested\"}\n",cuts,cancelledCases,committedAfterCancel);
}

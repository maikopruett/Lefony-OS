// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_developer_key_session.h"
#include "update_trust_root.h"
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
namespace K=PrimeG2::AppDeveloperKeys;
static unsigned starts=0,steps=0,finishes=0;
static bool committed=false;
static K::Error removal=K::Error::None;
static K::Error removable(const uint8_t *,const K::Table &) {return removal;}
static K::Error preparation=K::Error::None,beginError=K::Error::None;
static K::Error prepare(const K::Request &r,const K::Table &,K::RecoveryInfo *info) {
  *info=K::RecoveryInfo{};info->generation=7;strcpy(info->appId,"private-app");strcpy(info->version,"1.2.0");
  memset(info->oldSigner,1,32);memcpy(info->packageHash,r.reserved,32);return preparation;
}
static K::Error begin(const K::Request &r,const K::Table &t,const K::RecoveryInfo &info) {
  assert(t.serial==r.serial && info.serial==t.serial && info.sequence && info.generation==7 && !memcmp(info.packageHash,r.reserved,32));
  starts++;return beginError;
}
static K::State step(K::Error *) {steps++;return committed?K::State::Complete:K::State::Working;}
static bool cancel() {return !committed;}
static void finish(K::State) {finishes++;}
static K::Request request(uint32_t nonce,uint32_t serial=0,K::Operation operation=K::Operation::Enroll) {
  K::Request r{};r.size=sizeof(r);r.schema=1;r.operation=operation;r.serial=serial;
  memcpy(r.nonce,&nonce,4);uint8_t modulus[256];memcpy(modulus,PrimeG2UpdateModulus,256);modulus[7]^=4;
  assert(K::fingerprint(modulus,r.id));
  if(operation==K::Operation::Enroll || operation==K::Operation::Repair) {memcpy(r.modulus,modulus,256);memcpy(r.label,"Developer",9);}
  return r;
}
static void done(K::Controller &c) {
  for(unsigned i=0;i<64 && c.busy();i++) c.poll(100+i);
  assert(c.status().state==K::State::Complete && c.status().error==K::Error::None);
}
static void approve(K::Controller &c) {
  assert(c.needsPresentation() && c.present());c.rendered();c.observeKeyboard(0);c.observeKeyboard(uint64_t(1)<<56);assert(c.approve(3));
}
int main() {
  Flash flash;auto volume=std::make_unique<Volume>(flash.backend());
  std::vector<uint8_t> package(MaximumPackage),data(MaximumData);
  assert(volume->initialize(package.data(),package.size(),data.data(),data.size(),[](const uint8_t *,size_t,char id[49]) {strcpy(id,"unused");return true;}));
  K::Controller c(*volume,{prepare,begin,step,cancel,finish,removable});c.initialize();assert(c.status().registry==1 && !c.status().serial && c.table());
  auto r=request(1);assert(K::Controller::valid(r));int writes=flash.writes;
  assert(c.request(r,0));c.poll(1);assert(!c.needsPresentation() && c.status().state==K::State::AwaitAck);
  assert(!c.approve(1) && flash.writes==writes);c.abandonSetup();assert(c.status().state==K::State::Cancelled);
  assert(c.request(r,2) && c.status().state==K::State::Cancelled); // exact replay does not restart
  r=request(2);assert(c.request(r,0));c.acknowledge();c.poll(1);
  assert(c.status().state==K::State::AwaitUser && c.needsPresentation() && flash.writes==writes);
  assert(!c.approve(2));assert(c.present());
  c.observeKeyboard(0);c.observeKeyboard(uint64_t(1)<<56);assert(!c.approve(2)); // not rendered
  c.rendered();assert(!c.approve(2)); // held before display; no fresh all-up scan
  c.observeKeyboard(0);c.observeKeyboard((uint64_t(1)<<56)|2);assert(!c.approve(2));
  c.observeKeyboard(uint64_t(1)<<56);assert(c.approve(3));assert(c.status().state==K::State::Working);
  assert(c.request(r,3));auto conflicting=r;conflicting.label[0]='X';assert(!c.request(conflicting,3));
  assert(!c.request(request(3),3));done(c);assert(c.status().registry==2 && c.status().serial==1 && c.status().count==1);
  assert(!c.request(request(3),4));c.dismiss();
  K::KeyInfo key;assert(c.keyInfo(0,&key) && key.state==1 && key.serial==1 && !memcmp(key.id,r.id,32));
  assert(!c.keyInfo(1,&key) && !c.keyInfo(0,nullptr));
  r=request(3,0,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(1);
  assert(c.status().state==K::State::Failed && c.status().error==K::Error::Stale);
  writes=flash.writes;r=request(4,1,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(1);
  assert(c.present());c.rendered();c.observeKeyboard(0);assert(!c.approve(2)); // no physical key
  c.disconnect();assert(c.status().state==K::State::Cancelled && flash.writes==writes);c.dismiss();
  r=request(5,1,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(120000);
  assert(c.status().state==K::State::Expired && flash.writes==writes);
  r=request(6,1,K::Operation::Revoke);assert(c.request(r,100));c.acknowledge();c.poll(99);assert(c.status().state==K::State::Expired);
  r=request(7,1,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);
  K::Control cancel{32,1,c.status().sequence,0,{}};memcpy(cancel.nonce,r.nonce,16);
  cancel.sequence++;assert(!c.cancel(cancel));cancel.sequence--;assert(c.cancel(cancel));
  assert(c.status().state==K::State::Cancelled && c.status().serial==1);c.dismiss();
  r=request(8,1,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);done(c);c.dismiss();
  assert(c.table()->find(r.id,K::Purpose::Inspect) && !c.table()->find(r.id,K::Purpose::Execute));
  assert(c.status().serial==2 && c.status().count==1);
  // Restoring an existing public identity still needs a new rendered approval.
  r=request(9,2);assert(c.request(r,0));c.acknowledge();c.poll(1);assert(!c.approve(2));approve(c);done(c);c.dismiss();
  assert(c.status().serial==3 && c.table()->find(r.id,K::Purpose::Execute));
  // Protected firmware keys never reach the consent screen.
  r=request(10,3);memcpy(r.modulus,PrimeG2UpdateModulus,256);assert(K::fingerprint(r.modulus,r.id));
  assert(c.request(r,0));c.acknowledge();c.poll(1);assert(c.status().state==K::State::Failed && c.status().error==K::Error::ProtectedKey);
  for(unsigned offset:{0u,4u,8u,32u,64u,352u}) {auto bad=request(11,3);reinterpret_cast<uint8_t *>(&bad)[offset]^=128;assert(!K::Controller::valid(bad));}
  auto bad=request(11,3);memset(bad.nonce,0,16);assert(!K::Controller::valid(bad));
  bad=request(11,3,K::Operation::Revoke);bad.modulus[0]=1;assert(!K::Controller::valid(bad));
  // Recovery consent cannot become a key grant or a different package request.
  r=request(12,3,K::Operation::RecoverInstall);r.reserved[0]=123;
  assert(K::Controller::valid(r));bad=r;bad.label[0]='x';assert(!K::Controller::valid(bad));
  assert(c.request(r,0));c.acknowledge();c.poll(1);assert(c.status().state==K::State::AwaitUser && !starts);
  conflicting=r;conflicting.reserved[0]++;assert(!c.request(conflicting,1));
  assert(!c.approve(2));c.disconnect();assert(c.status().state==K::State::Cancelled && !starts);c.dismiss();
  r.nonce[0]++;assert(c.request(r,0));c.acknowledge();c.poll(1);beginError=K::Error::Stale;
  approve(c);assert(c.status().state==K::State::Failed && c.status().error==K::Error::Stale && starts==1 && !steps);c.dismiss();
  r.nonce[0]++;beginError=K::Error::None;assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);
  c.disconnect();assert(c.status().state==K::State::Cancelled && starts==2);c.dismiss();
  r.nonce[0]++;assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);committed=true;
  c.disconnect();assert(c.status().state==K::State::Working);done(c);c.dismiss();
  assert(c.status().serial==3 && c.table()->find(r.id,K::Purpose::Execute) && starts==3 && steps==1 && finishes>=4);
  r.nonce[0]++;preparation=K::Error::Ownership;assert(c.request(r,0));c.acknowledge();c.poll(1);
  assert(c.status().state==K::State::Failed && c.status().error==K::Error::Ownership && starts==3);
  r=request(30,3,K::Operation::Remove);assert(c.request(r,0));c.acknowledge();c.poll(1);
  assert(c.status().state==K::State::Failed && c.status().error==K::Error::KeyActive);
  r=request(31,3,K::Operation::Revoke);assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);done(c);c.dismiss();
  writes=flash.writes;removal=K::Error::KeyInUse;r=request(32,4,K::Operation::Remove);
  assert(c.request(r,0));c.acknowledge();c.poll(1);assert(c.status().state==K::State::Failed && c.status().error==K::Error::KeyInUse);
  removal=K::Error::None;r.nonce[0]++;assert(c.request(r,0));c.acknowledge();c.poll(1);removal=K::Error::KeyInUse;approve(c);
  assert(c.status().state==K::State::Failed && c.status().error==K::Error::KeyInUse && flash.writes==writes);c.dismiss();
  removal=K::Error::None;r.nonce[0]++;assert(c.request(r,0));c.acknowledge();c.poll(1);approve(c);done(c);c.dismiss();
  assert(c.status().registry==2 && c.status().serial==5 && !c.status().count && !c.keyInfo(0,&key));
  // The operation record is volatile, but acknowledged trust survives reboot.
  volume.reset();
  auto restored=std::make_unique<Volume>(flash.backend());assert(restored->mount());K::Controller reopened(*restored);reopened.initialize();
  assert(reopened.status().state==K::State::Idle && !reopened.status().sequence && reopened.status().serial==5 && !reopened.status().count);
  restored.reset();{Raw raw(flash);raw.corrupt(K::Store::Path);}
  auto damaged=std::make_unique<Volume>(flash.backend());assert(damaged->mount());K::Controller repair(*damaged);repair.initialize();
  assert(repair.status().registry==3 && !repair.table());K::DamageInfo damage;assert(repair.damageInfo(&damage) && damage.bytes==K::WireBytes);
  uint8_t chunk[512];assert(repair.damagedBytes(0,chunk,512)==512 && !chunk[0]);
  r=request(40,0,K::Operation::Repair);memcpy(r.reserved,damage.hash,32);assert(K::Controller::valid(r));
  r.reserved[0]^=1;writes=flash.writes;assert(repair.request(r,0));repair.acknowledge();repair.poll(1);
  assert(repair.status().state==K::State::Failed && repair.status().error==K::Error::Stale && flash.writes==writes);
  r.reserved[0]^=1;r.nonce[0]++;assert(repair.request(r,0));repair.acknowledge();repair.poll(1);
  assert(!repair.damageInfo(&damage) && repair.damagedBytes(0,chunk,512)<0); // mutations own the volume
  assert(!repair.approve(2));repair.disconnect();assert(repair.status().state==K::State::Cancelled && flash.writes==writes);
  r.nonce[0]++;assert(repair.request(r,0));repair.acknowledge();repair.poll(1);approve(repair);done(repair);repair.dismiss();
  assert(repair.status().registry==2 && repair.status().serial==1 && repair.status().count==1 && repair.table()->find(r.id,K::Purpose::Execute));
  puts("{\"status\":\"passed\",\"physical\":\"not_tested\"}");
}

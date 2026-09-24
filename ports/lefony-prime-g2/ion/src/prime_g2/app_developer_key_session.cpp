// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_developer_key_session.h"
#include "app_trust_roots.h"
#include "update_trust_root.h"
#if PRIME_G2_EMULATOR
#include "app_emulator_trust_root.h"
#endif
namespace PrimeG2 { namespace AppDeveloperKeys {
namespace {
bool zero(const void *p,unsigned n) {auto b=static_cast<const uint8_t *>(p);for(unsigned i=0;i<n;i++) if(b[i]) return false;return true;}
unsigned length(const char *p) {unsigned n=0;while(n<32 && p[n]) n++;return n;}
}
Controller::Controller(AppStorage::Volume &v,RecoveryHooks hooks):m_volume(v),m_store(&v.m_fs),m_snapshot(&v.m_fs),m_hooks(hooks) {}
bool Controller::compiledKey(const uint8_t id[32]) {
  if(!id) return false;
  for(unsigned i=0;i<LefonyAppTrustRootCount;i++) if(!memcmp(id,LefonyAppTrustRoots[i].id,32)) return true;
#if PRIME_G2_EMULATOR
  if(!memcmp(id,LefonyEmulatorAppKey.id,32)) return true;
#endif
  return false;
}
bool Controller::valid(const Request &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || zero(r.nonce,16)) return false;
  if(r.operation==Operation::BackupUnreadable) return !r.serial && zero(r.id,32) && zero(r.modulus,256) && zero(r.label,32) && zero(r.reserved,sizeof(r.reserved));
  if(r.operation==Operation::RecoverInstall) return !zero(r.reserved,sizeof(r.reserved)) && !zero(r.id,32) && zero(r.modulus,256) && zero(r.label,32);
  if(r.operation==Operation::Repair || r.operation==Operation::RepairUnreadable) {if(r.serial || zero(r.reserved,sizeof(r.reserved))) return false;}
  else if(!zero(r.reserved,sizeof(r.reserved))) return false;
  if(r.operation==Operation::Revoke || r.operation==Operation::Remove) return !zero(r.id,32) && zero(r.modulus,256) && zero(r.label,32);
  if(r.operation!=Operation::Enroll && r.operation!=Operation::Repair && r.operation!=Operation::RepairUnreadable) return false;
  uint8_t id[32];if(!fingerprint(r.modulus,id) || memcmp(id,r.id,32)) return false;
  unsigned n=length(r.label);
  if(!n || n==32 || r.label[0]==' ' || r.label[n-1]==' ' || !zero(r.label+n,32-n)) return false;
  for(unsigned i=0;i<n;i++) if(r.label[i]<32 || r.label[i]>126) return false;
  return true;
}
Error Controller::error(Result r) {
  switch(r) {
    case Result::Ok:case Result::Unchanged:return Error::None;
    case Result::Stale:return Error::Stale;
    case Result::Full:return Error::Full;
    case Result::Overflow:return Error::Overflow;
    case Result::Missing:return Error::Missing;
    case Result::Corrupt:return Error::Registry;
    case Result::Busy:return Error::Busy;
    case Result::Io:return Error::Io;
    case Result::Active:return Error::KeyActive;
    default:return Error::Invalid;
  }
}
void Controller::syncStatus(Result r) {
  const Table *t=m_store.current();
  m_status.registry=t?(t->serial?2:1):(r==Result::Corrupt?3:4);
  m_status.serial=t?t->serial:0;m_status.count=t?t->count:0;
}
void Controller::initialize() {
  if(busy()) return;
  if(!m_volume.documentReady()) {m_status.registry=4;return;}
  m_volume.refreshMetadata();
  syncStatus(m_store.load());
}
bool Controller::busy() const {return m_status.state>=State::AwaitAck && m_status.state<=State::Working;}
bool Controller::needsPolling() const {return m_status.state==State::Preparing || m_status.state==State::Working;}
void Controller::finish(State state,Error error) {
  m_snapshot.cancel();m_snapshotUse=SnapshotUse::None;
  m_status.state=state;m_status.error=error;m_rendered=m_released=false;
  if(m_request.operation==Operation::RecoverInstall && m_hooks.finish) m_hooks.finish(state);
}
bool Controller::request(const Request &r,uint64_t now) {
  if(!valid(r)) return false;
  // Exact replay only observes the existing operation; it never reopens consent.
  if(m_status.sequence && !memcmp(r.nonce,m_request.nonce,16)) return !memcmp(&r,&m_request,sizeof(r));
  if(busy() || m_presented || m_status.sequence==0xffffffffu) return false;
  if(r.operation==Operation::RecoverInstall && (!m_hooks.prepare || !m_hooks.begin || !m_hooks.step || !m_hooks.cancel || !m_hooks.finish)) return false;
  if(r.operation==Operation::Remove && !m_hooks.removable) return false;
  m_request=r;m_status.operation=r.operation;m_status.sequence++;m_status.error=Error::None;
  memcpy(m_status.nonce,r.nonce,16);memcpy(m_status.id,r.id,32);memcpy(m_status.label,r.label,32);
  memcpy(m_status.reserved,r.reserved,sizeof(r.reserved));m_recovery=RecoveryInfo{};
  m_since=now;m_rendered=m_released=false;m_status.state=State::AwaitAck;return true;
}
void Controller::acknowledge() {if(m_status.state==State::AwaitAck) m_status.state=State::Preparing;}
void Controller::abandonSetup() {if(m_status.state==State::AwaitAck) finish(State::Cancelled);}
void Controller::cancelPending(State state) {
  if(!busy()) return;
  if(m_status.state==State::Working) {
    if(m_snapshotUse!=SnapshotUse::None) m_snapshot.cancel();
    else if(m_request.operation==Operation::RecoverInstall) {if(!m_hooks.cancel()) return;}
    else {if(!m_store.cancel()) return;syncStatus(m_store.result());}
  }
  finish(state);
}
bool Controller::cancel(const Control &c) {
  if(c.size!=sizeof(c) || c.schema!=1 || c.reserved || c.sequence!=m_status.sequence || !c.sequence || memcmp(c.nonce,m_status.nonce,16)) return false;
  cancelPending(State::Cancelled);return true;
}
void Controller::disconnect() {cancelPending(State::Cancelled);}
bool Controller::present() {
  if(!needsPresentation()) return false;
  m_presented=true;m_rendered=m_released=false;return true;
}
void Controller::rendered() {if(m_presented && m_status.state==State::AwaitUser) m_rendered=true;}
void Controller::observeKeyboard(uint64_t physical) {
  m_physical=physical;
  if(m_rendered && m_status.state==State::AwaitUser && !physical) m_released=true;
}
void Controller::deny() {cancelPending(State::Denied);}
void Controller::dismiss() {cancelPending(State::Cancelled);m_presented=m_rendered=m_released=false;}
bool Controller::approve(uint64_t now) {
  poll(now);
  if(m_status.state!=State::AwaitUser || !m_presented || !m_rendered || !m_released || m_physical!=(uint64_t(1)<<56)) return false;
  m_volume.refreshMetadata();
  if(m_request.operation==Operation::RepairUnreadable) {
    // Re-capture observably readable/missing regions after approval. A changed
    // snapshot or now-readable registry must fail before any replacement write.
    m_snapshot.begin();m_snapshotUse=SnapshotUse::AfterApproval;
    m_status.state=State::Working;m_rendered=m_released=false;return true;
  }
  if(m_request.operation==Operation::RecoverInstall) {
    Result r=m_store.load();syncStatus(r);
    Error e=error(r);
    const Table *t=m_store.current();
    if(e==Error::None && (!t || t->serial!=m_request.serial)) e=Error::Stale;
    if(e==Error::None) e=m_hooks.begin(m_request,*t,m_recovery);
    m_rendered=m_released=false;
    if(e==Error::None) m_status.state=State::Working;else finish(State::Failed,e);
    return true;
  }
  // Recheck the canonical serial after the consent interval, before any write.
  Result r;
  if(m_request.operation==Operation::Repair) r=m_store.beginRepair(reinterpret_cast<const uint8_t *>(m_request.reserved),
    m_request.modulus,m_request.label,length(m_request.label));
  else if(m_request.operation==Operation::Remove) {
    r=m_store.load();syncStatus(r);const Table *t=m_store.current();
    Error e=error(r);
    if(e==Error::None && (!t || t->serial!=m_request.serial)) e=Error::Stale;
    if(e==Error::None) e=m_hooks.removable(m_request.id,*t);
    if(e!=Error::None) {finish(State::Failed,e);return true;}
    r=m_store.beginRemove(m_request.serial,m_request.id);
  } else if(m_request.operation==Operation::Enroll) r=m_store.beginEnroll(m_request.serial,m_request.modulus,m_request.label,length(m_request.label));
  else r=m_store.beginRevoke(m_request.serial,m_request.id);
  syncStatus(m_store.result());m_rendered=m_released=false;
  if(r==Result::Busy) m_status.state=State::Working;
  else finish(r==Result::Unchanged?State::Complete:State::Failed,error(r));
  return true;
}
void Controller::poll(uint64_t now) {
  if(busy() && m_status.state!=State::Working && (now<m_since || now-m_since>=120000)) {finish(State::Expired);return;}
  if(m_status.state==State::Preparing) {
    if(!m_volume.documentReady()) {finish(State::Failed,Error::Busy);return;}
    for(const auto &reader:m_volume.m_readers) if(reader.state()!=AppFileStore::Reader::State::Closed) {
      finish(State::Failed,Error::Busy);return;
    }
    m_volume.refreshMetadata();
    Result r=m_store.load();syncStatus(r);
    bool repair=m_request.operation==Operation::Repair;
    bool backup=m_request.operation==Operation::BackupUnreadable;
    bool unreadable=backup || m_request.operation==Operation::RepairUnreadable;
    if(unreadable && r!=Result::Io && r!=Result::Corrupt) {finish(State::Failed,r==Result::Ok?Error::Readable:error(r));return;}
    if(!unreadable && ((repair && r!=Result::Corrupt) || (!repair && r!=Result::Ok && r!=Result::Missing))) {
      finish(State::Failed,repair && (r==Result::Ok || r==Result::Missing)?Error::Stale:error(r));return;
    }
    // Firmware identity and the deliberately public emulator fixture can never
    // become private developer identities, including on physical builds.
    const uint8_t fixture[32]={0x18,0xf9,0x25,0x81,0x0b,0xc2,0x62,0xe8,0xfc,0xcb,0x42,0xdb,0x11,0x68,0xb8,0x26,
      0x5d,0xf6,0xb3,0xf6,0xf6,0xf7,0xd9,0x42,0x32,0xb0,0xb5,0x92,0x4e,0x6e,0xbe,0xbb};
    uint8_t firmware[32];fingerprint(PrimeG2UpdateModulus,firmware);
    if(!backup && (compiledKey(m_request.id) || !memcmp(fixture,m_request.id,32) || !memcmp(firmware,m_request.id,32))) {
      finish(State::Failed,Error::ProtectedKey);return;
    }
    if(unreadable) {
      m_snapshot.begin();m_snapshotUse=backup?SnapshotUse::Backup:SnapshotUse::BeforeApproval;
      m_status.state=State::Working;return;
    }
    if(repair) {
      uint8_t hash[32];uint32_t bytes;r=m_store.damaged(hash,&bytes);
      if(r!=Result::Ok) {finish(State::Failed,error(r));return;}
      if(memcmp(hash,m_request.reserved,32)) {finish(State::Failed,Error::Stale);return;}
      m_status.state=State::AwaitUser;return;
    }
    const Table &t=*m_store.current();Table candidate;
    if(m_request.operation==Operation::RecoverInstall) {
      if(t.serial!=m_request.serial) {finish(State::Failed,Error::Stale);return;}
      const Key *key=t.find(m_request.id,Purpose::Execute);
      if(!key) {finish(State::Failed,Error::Missing);return;}
      Error e=m_hooks.prepare(m_request,t,&m_recovery);
      if(e!=Error::None) {finish(State::Failed,e);return;}
      m_recovery.sequence=m_status.sequence;m_recovery.serial=t.serial;
      memcpy(m_status.label,key->label,32);m_status.state=State::AwaitUser;return;
    }
    if(m_request.operation==Operation::Enroll) r=t.enroll(m_request.serial,m_request.modulus,m_request.label,length(m_request.label),&candidate);
    else {
      r=m_request.operation==Operation::Remove?t.remove(m_request.serial,m_request.id,&candidate):t.revoke(m_request.serial,m_request.id,&candidate);
      const Key *key=t.find(m_request.id,Purpose::Inspect);if(key) memcpy(m_status.label,key->label,32);
    }
    if(r==Result::Ok && m_request.operation==Operation::Remove) {
      Error e=m_hooks.removable(m_request.id,t);if(e!=Error::None) {finish(State::Failed,e);return;}
    }
    if(r==Result::Unchanged) finish(State::Complete);
    else if(r!=Result::Ok) finish(State::Failed,error(r));
    else m_status.state=State::AwaitUser;
  } else if(m_status.state==State::Working) {
    if(m_snapshotUse!=SnapshotUse::None) {
      m_snapshot.step();if(m_snapshot.state()==Snapshot::State::Running) return;
      Snapshot::Info info;
      if(!m_snapshot.info(&info)) {
        Result result=m_snapshot.result();syncStatus(m_store.load());
        finish(State::Failed,result==Result::Readable?Error::Readable:error(result));return;
      }
      // The production NAND adapter may report LFS_ERR_CORRUPT for a failed
      // read. A completed partial capture establishes actual unreadable bytes.
      syncStatus(Result::Io);
      if(m_snapshotUse==SnapshotUse::Backup) {finish(State::Complete);return;}
      if(memcmp(info.hash,m_request.reserved,32)) {finish(State::Failed,Error::Stale);return;}
      if(m_snapshotUse==SnapshotUse::BeforeApproval) {
        m_snapshotUse=SnapshotUse::None;m_status.state=State::AwaitUser;return;
      }
      Result r=m_store.beginRepairSnapshot(m_snapshot,reinterpret_cast<const uint8_t *>(m_request.reserved),
        m_request.modulus,m_request.label,length(m_request.label));
      m_snapshotUse=SnapshotUse::None;
      if(r!=Result::Busy) finish(State::Failed,error(r));
      return;
    }
    if(m_request.operation==Operation::RecoverInstall) {
      Error e=Error::None;State state=m_hooks.step(&e);
      if(state!=State::Working) finish(state,e);
      return;
    }
    m_store.step();
    if(m_store.state()==Store::State::Complete) {syncStatus(Result::Ok);finish(State::Complete);}
    else if(m_store.state()==Store::State::Failed) {
      syncStatus(m_store.result());finish(State::Failed,m_store.commitStarted()?Error::Uncertain:error(m_store.result()));
    }
  }
}
bool Controller::keyInfo(unsigned index,KeyInfo *out) const {
  const Table *t=m_store.current();if(!out || !t || index>=t->count) return false;
  KeyInfo info;info.index=index;info.serial=t->serial;const Key &key=t->keys[index];info.state=uint32_t(key.state);
  memcpy(info.id,key.id,32);memcpy(info.modulus,key.modulus,256);memcpy(info.label,key.label,32);*out=info;return true;
}
bool Controller::damageInfo(DamageInfo *out) {
  if(!out || busy() || !m_volume.documentReady()) return false;
  DamageInfo value;Result r=m_store.damaged(value.hash,&value.bytes);syncStatus(m_store.result());
  if(r!=Result::Ok) return false;
  *out=value;return true;
}
int Controller::damagedBytes(uint32_t offset,void *out,uint32_t bytes) {
  if(busy() || !m_volume.documentReady()) return -1;
  int result=m_store.readDamaged(offset,out,bytes);syncStatus(m_store.result());return result;
}
bool Controller::unreadableInfo(UnreadableInfo *out) const {
  Snapshot::Info info;
  if(!out || m_status.operation!=Operation::BackupUnreadable || m_status.state!=State::Complete || !m_snapshot.info(&info)) return false;
  UnreadableInfo value;value.sequence=m_status.sequence;memcpy(value.nonce,m_status.nonce,16);
  value.originalBytes=info.originalBytes;value.bytes=info.bytes;value.readableBytes=info.readableBytes;
  value.unreadableChunks=info.unreadableChunks;memcpy(value.hash,info.hash,32);*out=value;return true;
}
int Controller::unreadableBytes(uint32_t offset,void *out,uint32_t bytes) {
  UnreadableInfo info;if(!m_volume.documentReady() || !unreadableInfo(&info)) return -1;
  return m_snapshot.read(offset,out,bytes);
}
}}

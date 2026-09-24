// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_data_session.h"
#include <string.h>
namespace PrimeG2 { namespace AppData {
using namespace AppStorage;
static_assert(sizeof(LefonyDataRequest)==64,"private data wire size");
bool Session::attach(const char *id,const uint32_t version[3],uint32_t appSchema,uint32_t savedSchema,
                     uint8_t *committed,uint32_t bytes) {
  if(active() || needsPolling() || !id || !id[0] || strlen(id)>48 || !version ||
     !committed || bytes>MaximumData) return false;
  memcpy(m_id,id,strlen(id)+1);memcpy(m_version,version,sizeof(m_version));
  m_appSchema=appSchema;m_savedSchema=savedSchema;m_committed=committed;
  memcpy(m_data,committed,bytes);m_bytes=m_committedBytes=bytes;
  m_generation=m_snapshotRevision=m_token=m_error=m_flags=0;m_editRevision=1;
  m_dirty=m_pendingUpgrade=m_migrating=m_done=m_cancel=m_cancelSent=m_frozen=m_poisoned=false;
  return true;
}
int Session::read(uint32_t offset,void *out,uint32_t bytes) const {
  if(!active() || !out || offset>m_bytes || bytes>m_bytes-offset) return -1;
  memcpy(out,m_data+offset,bytes);return bytes;
}
int Session::write(uint32_t offset,const void *input,uint32_t bytes) {
  if(!active() || m_frozen || m_poisoned || !input || offset>MaximumData || bytes>MaximumData-offset ||
     (m_appSchema!=m_savedSchema && !m_migrating) || m_editRevision==0xffffffffu) return -1;
  if(offset>m_bytes) memset(m_data+m_bytes,0,offset-m_bytes);
  memcpy(m_data+offset,input,bytes);if(offset+bytes>m_bytes) m_bytes=offset+bytes;
  m_editRevision++;m_dirty=true;return bytes;
}
void Session::reply(LefonyDataRequest &out) const {
  out={};out.size=sizeof(out);out.schema=1;out.operation=m_request.operation;out.token=m_token;
  out.generation=m_generation;out.dataSchema=m_savedSchema;out.bytes=m_committedBytes;
  out.flags=m_flags|(m_dirty?LEFONY_DATA_DIRTY:0)|(m_pendingUpgrade?LEFONY_DATA_PENDING_UPGRADE:0)|
    (m_migrating?LEFONY_DATA_MIGRATING:0);
  out.state=!m_done?LEFONY_DATA_PENDING:m_error==LEFONY_DATA_CANCELLED_ERROR?LEFONY_DATA_CANCELLED:
    m_error?LEFONY_DATA_FAILED:LEFONY_DATA_COMPLETE;
  out.error=m_error;out.appSchema=m_appSchema;out.stagedBytes=m_bytes;
  out.editRevision=m_editRevision;out.snapshotRevision=m_snapshotRevision;
}
int Session::request(LefonyDataRequest &r) {
  if(!active() || m_frozen) return -LEFONY_FILE_DENIED;
  if(r.size!=sizeof(r) || r.schema!=1 || r.flags || r.state || r.error || r.appSchema || r.stagedBytes ||
     r.editRevision || r.snapshotRevision || r.reserved[0] || r.reserved[1] || r.operation>LEFONY_DATA_CANCEL)
    return -LEFONY_FILE_INVALID;
  if(r.operation==LEFONY_DATA_POLL || r.operation==LEFONY_DATA_CANCEL) {
    if(!r.token || r.token!=m_token || r.generation || r.dataSchema || r.bytes) return -LEFONY_FILE_INVALID;
    if(r.operation==LEFONY_DATA_CANCEL) {if(!m_done) m_cancel=true;return 0;}
    bool done=m_done;reply(r);if(done) {m_token=0;m_done=false;}return done?0:1;
  }
  if(m_poisoned) return -LEFONY_FILE_IO;
  if(m_token || !m_files.quiescent()) return -LEFONY_FILE_BUSY;
  if(r.token || (r.operation==LEFONY_DATA_INSPECT?(r.generation || r.dataSchema || r.bytes):!r.generation) ||
     (r.operation!=LEFONY_DATA_CHECKPOINT && r.bytes) || r.bytes>m_bytes) return -LEFONY_FILE_INVALID;
  if(m_serial==0xffffffffu) return -LEFONY_FILE_LIMIT;
  m_request=r;m_token=++m_serial;m_error=m_flags=0;m_done=m_cancel=m_cancelSent=false;
  m_snapshotRevision=0;
  if(r.operation==LEFONY_DATA_CHECKPOINT) {
    memcpy(m_snapshot,m_data,r.bytes);m_snapshotRevision=m_editRevision;
  }
  m_phase=Phase::Start;r.token=m_token;return 1;
}
bool Session::inspect() {
  Volume::FileUsage usage{};
  if(!m_volume.fileUsage(m_id,&usage)) return false;
  AppDocumentRoot::Root root;
  bool documents=m_volume.documentRoot(m_id,&root);
  m_generation=usage.generation;m_committedBytes=usage.data.privateBytes;
  m_savedSchema=documents?root.current.dataSchema:m_appSchema;
  m_pendingUpgrade=documents && (root.flags&AppDocumentRoot::PendingUpgrade);
  return true;
}
void Session::complete(uint32_t error,uint32_t flags) {
  m_error=error;m_flags=flags;m_done=true;m_phase=Phase::Idle;
}
void Session::poll() {
  if(m_phase==Phase::Idle) return;
  if(m_phase==Phase::Start) {
    if(m_cancel) {complete(LEFONY_DATA_CANCELLED_ERROR);return;}
    if(!m_files.quiescent()) {complete(LEFONY_FILE_BUSY);return;}
    if(!inspect()) {complete(LEFONY_FILE_IO);return;}
    if(m_request.operation==LEFONY_DATA_INSPECT) {complete();return;}
    if(m_request.generation!=m_generation) {complete(LEFONY_FILE_CHANGED);return;}
    if(m_generation==0xffffffffu) {complete(LEFONY_FILE_LIMIT);return;}
    if(m_request.dataSchema!=m_appSchema || (m_appSchema!=m_savedSchema && !m_migrating &&
       m_request.operation!=LEFONY_DATA_BEGIN_MIGRATION)) {complete(LEFONY_FILE_SCHEMA);return;}
    if(m_request.operation==LEFONY_DATA_BEGIN_MIGRATION) {
      if(!m_pendingUpgrade) {complete(LEFONY_FILE_SCHEMA);return;}
      if(!m_files.dataContext(m_savedSchema,m_committed,m_committedBytes,true)) {complete(LEFONY_FILE_BUSY);return;}
      m_migrating=true;complete();return;
    }
    bool ok;
    if(m_request.operation==LEFONY_DATA_CHECKPOINT) {
      Volume::FileUsage usage{};
      if(!m_volume.fileUsage(m_id,&usage)) {complete(LEFONY_FILE_IO);return;}
      uint32_t used=usage.data.namedBytes+usage.data.privateBytes;
      uint32_t ceiling=used>AppFileStore::QuotaBytes?used:AppFileStore::QuotaBytes;
      if(m_request.bytes>ceiling-used+usage.data.privateBytes) {complete(LEFONY_FILE_QUOTA_EXCEEDED);return;}
      ok=m_volume.beginCheckpoint(m_id,m_snapshot,m_request.bytes,m_version,m_request.dataSchema);
    } else {
      if(m_dirty || !m_pendingUpgrade) {complete(m_dirty?LEFONY_FILE_BUSY:LEFONY_FILE_SCHEMA);return;}
      ok=m_volume.beginAccept(m_id,m_appSchema);
    }
    if(!ok) {
      if(m_volume.state()==State::Failed) m_poisoned=true;
      complete(LEFONY_FILE_IO);return;
    }
    m_phase=Phase::Writing;return;
  }
  if(m_cancel && !m_cancelSent) {m_volume.cancel();m_cancelSent=true;}
  if(m_volume.state()==State::Ready && m_cancelSent) {complete(LEFONY_DATA_CANCELLED_ERROR);return;}
  if(m_volume.state()!=State::Complete && m_volume.state()!=State::Failed) m_volume.step();
  if(m_volume.state()==State::Failed) {
    // A failure after publication can leave its result uncertain. Never save
    // stale staged state on Close or permit further writes in this session.
    m_poisoned=true;complete(LEFONY_FILE_IO,LEFONY_DATA_COMMIT_UNCERTAIN);return;
  }
  if(m_volume.state()!=State::Complete) return;
  if(m_request.operation==LEFONY_DATA_CHECKPOINT) {
    memcpy(m_committed,m_snapshot,m_request.bytes);m_committedBytes=m_request.bytes;
    m_savedSchema=m_request.dataSchema;
    m_dirty=m_editRevision!=m_snapshotRevision;
    if(!m_dirty) m_bytes=m_request.bytes;
  } else m_migrating=false;
  if(!inspect() || !m_files.dataContext(m_savedSchema,m_committed,m_committedBytes,m_migrating)) {
    m_poisoned=true;complete(LEFONY_FILE_IO,LEFONY_DATA_COMMITTED);return;
  }
  complete(0,LEFONY_DATA_COMMITTED);
}
void Session::finish(bool save) {
  m_frozen=true;if(!save && needsPolling()) m_cancel=true;
}
bool Session::reset() {
  if(needsPolling()) return false;
  m_id[0]=0;m_committed=nullptr;m_token=0;return true;
}
}}

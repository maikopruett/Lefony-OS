// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_file_session.h"
#include <string.h>
namespace PrimeG2 { namespace AppFiles {
using namespace AppStorage;
static_assert(sizeof(LefonyFileRequest)==64 && sizeof(LefonyFileInfo)==16,"file wire sizes");
static_assert(sizeof(LefonyDirectoryEntry)==104 && sizeof(LefonyDirectoryPage)==1688 &&
              sizeof(LefonyFileSpace)==64 && sizeof(LefonyFileQuota)==48,"catalog/quota wire sizes");
static bool containsZero(const char *bytes,uint32_t count) {
  for(uint32_t i=0;i<count;i++) if(!bytes[i]) return true;
  return false;
}
bool Session::attach(const char *id,const uint32_t version[3],uint32_t schema,
                     uint32_t savedSchema,const uint8_t *committed,uint32_t bytes) {
  if(active() || busy() || !id || !version || !id[0] || strlen(id)>48 ||
     bytes>MaximumData || (bytes && !committed)) return false;
  memcpy(m_id,id,strlen(id)+1);memcpy(m_version,version,sizeof(m_version));
  m_schema=schema;m_savedSchema=savedSchema;m_committed=committed;m_committedBytes=bytes;
  m_detaching=false;m_writerFailed=false;m_migrating=false;return true;
}
bool Session::dataContext(uint32_t savedSchema,const uint8_t *committed,uint32_t bytes,bool migrating) {
  if(!quiescent() || bytes>MaximumData || (bytes && !committed)) return false;
  m_savedSchema=savedSchema;m_committed=committed;m_committedBytes=bytes;m_migrating=migrating;return true;
}
int Session::slot(uint32_t token) const {
  if(!token) return -1;
  for(unsigned i=0;i<5;i++) if(m_handles[i].token==token) return i;
  return -1;
}
uint32_t Session::allocate(unsigned index,uint32_t flags,uint32_t snapshot) {
  if(m_handleSerial==0x7fffffffu) return 0;
  m_handles[index]={++m_handleSerial,snapshot,flags};return m_handleSerial;
}
bool Session::release(unsigned index) {
  bool ok=index>=4 || !m_handles[index].token || m_volume.closeSnapshot(m_id,m_handles[index].snapshot);
  m_handles[index]={};return ok;
}
uint32_t Session::error(int code) {
  switch(code) {
  case LFS_ERR_NOENT:return LEFONY_FILE_NOT_FOUND;
  case LFS_ERR_EXIST:return LEFONY_FILE_EXISTS;
  case LFS_ERR_ISDIR:return LEFONY_FILE_IS_DIRECTORY;
  case LFS_ERR_NOSPC:return LEFONY_FILE_NO_SPACE;
  case LFS_ERR_FBIG:return LEFONY_FILE_TOO_LARGE;
  case LFS_ERR_INVAL:return LEFONY_FILE_INVALID;
  case LFS_ERR_NOTEMPTY:return LEFONY_FILE_NOT_EMPTY;
  case LFS_ERR_NOTDIR:return LEFONY_FILE_NOT_DIRECTORY;
  case Volume::CatalogChanged:return LEFONY_FILE_CHANGED;
  case AppFileStore::QuotaExceeded:return LEFONY_FILE_QUOTA_EXCEEDED;
  default:return LEFONY_FILE_IO;
  }
}
void Session::complete(int result,uint32_t code) {
  m_result=result;m_error=code;m_done=true;m_phase=Phase::Idle;
}
bool Session::terminal() const {
  return m_volume.state()==State::Ready || m_volume.state()==State::Complete || m_volume.state()==State::Failed;
}
int Session::exchange(LefonyFileRequest &r,const char *path,const char *destination,
                       const void *input,void *output) {
  if(!active() || m_detaching) return -LEFONY_FILE_DENIED;
  if(r.size!=sizeof(r) || r.schema!=1 || r.result || r.error) return -LEFONY_FILE_INVALID;
  if(r.operation==LEFONY_FILE_POLL) {
    if(!r.token || r.token!=m_token || r.handle || r.flags || r.offset || r.length ||
       r.path || r.pathBytes || r.destination || r.destinationBytes ||
       r.capacity>sizeof(m_buffer) || (r.capacity && !output)) return -LEFONY_FILE_INVALID;
    if(!m_done) return 1;
    // Failed output validation does not consume a completion or repeat a write.
    if(m_outputBytes>r.capacity) return -LEFONY_FILE_INVALID;
    if(m_outputBytes) memcpy(output,m_buffer,m_outputBytes);
    r.result=m_result;r.error=m_error;r.length=m_outputBytes;
    m_token=0;m_done=false;m_outputBytes=0;return 0;
  }
  if(busy()) return -LEFONY_FILE_BUSY;
  if(r.token || r.operation>LEFONY_FILE_ABORT || r.length>sizeof(m_buffer) ||
     r.pathBytes>95 || r.destinationBytes>95 || r.capacity ||
     (r.pathBytes && (!path || containsZero(path,r.pathBytes))) ||
     (r.destinationBytes && (!destination || containsZero(destination,r.destinationBytes))) ||
     (r.operation==LEFONY_FILE_WRITE && r.length && !input)) return -LEFONY_FILE_INVALID;
  bool list=r.operation==LEFONY_FILE_LIST;
  bool named=r.operation==LEFONY_FILE_OPEN || r.operation==LEFONY_FILE_MKDIR ||
    r.operation==LEFONY_FILE_UNLINK || r.operation==LEFONY_FILE_RENAME ||
    (r.operation==LEFONY_FILE_STAT && !r.handle) || (list && r.pathBytes);
  if(named!=bool(r.pathBytes) || (r.operation==LEFONY_FILE_RENAME)!=bool(r.destinationBytes) ||
     (r.operation!=LEFONY_FILE_OPEN && !list && r.flags) || (r.operation!=LEFONY_FILE_SEEK && !list && r.offset) ||
     (r.operation!=LEFONY_FILE_READ && r.operation!=LEFONY_FILE_WRITE && r.length) ||
     (named && r.handle) || ((r.operation==LEFONY_FILE_FINISH || list || r.operation==LEFONY_FILE_SPACE || r.operation==LEFONY_FILE_QUOTA) && r.handle) ||
     (list && r.offset && !r.flags)) return -LEFONY_FILE_INVALID;
  if(r.operation==LEFONY_FILE_OPEN && (!(r.flags&3) || (r.flags&~63u) ||
     (!(r.flags&2) && (r.flags&60)) || ((r.flags&8) && (r.flags&16)) ||
     ((r.flags&32) && !(r.flags&4)))) return -LEFONY_FILE_INVALID;
  if(m_requestSerial==0xffffffffu) return -LEFONY_FILE_LIMIT;
  memcpy(m_path,path?path:"",r.pathBytes);m_path[r.pathBytes]=0;
  memcpy(m_destination,destination?destination:"",r.destinationBytes);m_destination[r.destinationBytes]=0;
  if(named && (!AppFileIndex::path(m_path) || (r.destinationBytes && !AppFileIndex::path(m_destination)))) return -LEFONY_FILE_INVALID;
  m_request=r;
  // Store no raw application addresses in a pending request.
  m_request.path=m_request.destination=m_request.buffer=0;
  if(r.operation==LEFONY_FILE_WRITE && r.length) memcpy(m_buffer,input,r.length);
  m_outputBytes=0;m_done=false;m_token=++m_requestSerial;m_phase=Phase::Start;
  r.token=m_token;
  // Pure RAM operations on an authenticated immutable snapshot can complete
  // immediately. Keep the same submit/token/poll protocol; no filesystem work,
  // hashing, writes or user pointers are retained/executed in this fast path.
  int h=slot(r.handle);
  if(h>=0 && h<4) {
    if(r.operation==LEFONY_FILE_SEEK || r.operation==LEFONY_FILE_STAT) dispatch();
    else if(r.operation==LEFONY_FILE_READ && (m_handles[h].flags&LEFONY_FILE_READABLE)) {
      int n=m_volume.readCachedSnapshot(m_id,m_handles[h].snapshot,m_buffer,r.length);
      if(n!=AppFileStore::Reader::Pending) {
        if(n>=0) m_outputBytes=n;
        complete(n,n<0?LEFONY_FILE_IO:0);
      }
    }
  }
  return 1;
}
void Session::start() {
  const auto &r=m_request;
  bool mutation=r.operation==LEFONY_FILE_MKDIR || r.operation==LEFONY_FILE_UNLINK ||
    r.operation==LEFONY_FILE_RENAME || (r.operation==LEFONY_FILE_OPEN && (r.flags&LEFONY_FILE_WRITABLE));
  if(mutation) {
    if(m_schema!=m_savedSchema && !m_migrating) { complete(-1,LEFONY_FILE_SCHEMA);return; }
    if(m_handles[4].token) { complete(-1,LEFONY_FILE_BUSY);return; }
    AppDocumentRoot::Root root;
    if(!m_volume.documentRoot(m_id,&root)) {
      if(!m_volume.beginCheckpoint(m_id,m_committed,m_committedBytes,m_version,m_savedSchema)) {
        complete(-1,LEFONY_FILE_IO);return;
      }
      m_phase=Phase::Convert;return;
    }
  }
  dispatch();
}
void Session::dispatch() {
  const auto &r=m_request;int h=slot(r.handle);
  if(r.operation==LEFONY_FILE_LIST || r.operation==LEFONY_FILE_SPACE || r.operation==LEFONY_FILE_QUOTA) { inspect();return; }
  if(r.operation==LEFONY_FILE_OPEN) {
    uint32_t f=r.flags;
    if(!(f&3) || (f&~63u) || (!(f&2) && (f&60)) || ((f&8) && (f&16)) || ((f&32) && !(f&4))) {
      complete(-1,LEFONY_FILE_INVALID);return;
    }
    uint32_t kind=0,bytes=0;int exists=m_volume.fileInfo(m_id,m_path,&kind,&bytes);
    if(exists<0) { complete(-1,error(exists));return; }
    if(exists && kind!=AppFileIndex::File) { complete(-1,LEFONY_FILE_IS_DIRECTORY);return; }
    if(exists && (f&32)) { complete(-1,LEFONY_FILE_EXISTS);return; }
    if(!exists && !(f&4)) { complete(-1,LEFONY_FILE_NOT_FOUND);return; }
    if(m_handleSerial==0x7fffffffu) { complete(-1,LEFONY_FILE_LIMIT);return; }
    if(f&2) {
      using Mode=AppFileStore::Store::StreamMode;
      Mode mode=(f&8)||!exists?Mode::Truncate:(f&16)?Mode::Append:Mode::Update;
      if(!m_volume.beginStream(m_id,m_path,mode)) { complete(-1,error(m_volume.fileError()));return; }
      memcpy(m_writerPath,m_path,strlen(m_path)+1);
      m_writerFailed=false;m_phase=Phase::Open;
    } else {
      unsigned i=0;while(i<4 && m_handles[i].token) i++;
      if(i==4) { complete(-1,LEFONY_FILE_LIMIT);return; }
      uint32_t snapshot=m_volume.openSnapshot(m_id,m_path);
      if(!snapshot) { complete(-1,LEFONY_FILE_IO);return; }
      complete(allocate(i,f,snapshot));
    }
    return;
  }
  if(r.operation==LEFONY_FILE_MKDIR || r.operation==LEFONY_FILE_UNLINK || r.operation==LEFONY_FILE_RENAME) {
    if(!m_volume.changeFile(m_id,m_path,r.operation==LEFONY_FILE_RENAME?m_destination:nullptr,r.operation==LEFONY_FILE_MKDIR)) {
      complete(-1,error(m_volume.fileError()));return;
    }
    m_phase=Phase::Mutation;return;
  }
  if(r.operation==LEFONY_FILE_FINISH) {
    for(unsigned i=0;i<4;i++) release(i);
    if(!m_handles[4].token) { complete(0);return; }
    h=4;
  } else if(r.operation!=LEFONY_FILE_STAT && h<0) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
  if(r.operation==LEFONY_FILE_ABORT) {
    // Only the authenticated writer is discarded. A completed sync stays
    // committed, and independently held reader snapshots remain valid.
    if(h!=4) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
    m_volume.cancel();release(4);m_writerFailed=false;m_phase=Phase::Abort;return;
  }
  if(r.operation==LEFONY_FILE_CLOSE || r.operation==LEFONY_FILE_FINISH || r.operation==LEFONY_FILE_SYNC) {
    // Snapshot readers already refer to committed data. Sync retains the handle.
    if(h<4) { bool ok=r.operation==LEFONY_FILE_SYNC || release(h);complete(ok?0:-1,ok?0:LEFONY_FILE_IO);return; }
    m_syncPosition=m_volume.filePosition();
    if(m_writerFailed || !m_volume.commitFile()) {
      m_volume.cancel();release(4);complete(-1,error(m_volume.fileError()));return;
    }
    m_phase=r.operation==LEFONY_FILE_SYNC?Phase::Sync:Phase::Close;return;
  }
  if(r.operation==LEFONY_FILE_STAT) {
    LefonyFileInfo info{};
    if(r.handle) {
      if(h<0) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
      info.flags=m_handles[h].flags;info.kind=AppFileIndex::File;
      if(h==4) { info.bytes=m_volume.fileSize();info.position=m_volume.filePosition(); }
      else {
        Volume::SnapshotInfo snapshot;
        if(!m_volume.snapshotInfo(m_id,m_handles[h].snapshot,&snapshot)) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
        info.bytes=snapshot.bytes;info.position=snapshot.position;
      }
    } else {
      int found=m_volume.fileInfo(m_id,m_path,&info.kind,&info.bytes);
      if(found<=0) { complete(-1,found?error(found):LEFONY_FILE_NOT_FOUND);return; }
    }
    memcpy(m_buffer,&info,sizeof(info));m_outputBytes=sizeof(info);complete(0);return;
  }
  if(r.operation==LEFONY_FILE_SEEK) {
    bool ok=h==4?m_volume.seekFile(r.offset):m_volume.seekSnapshot(m_id,m_handles[h].snapshot,r.offset);
    complete(ok?static_cast<int>(r.offset):-1,ok?0:LEFONY_FILE_INVALID);return;
  }
  if(r.operation==LEFONY_FILE_READ) {
    if(!(m_handles[h].flags&1)) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
    m_phase=Phase::Read;return;
  }
  if(r.operation==LEFONY_FILE_WRITE) {
    if(h!=4 || !(m_handles[h].flags&2)) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
    m_phase=Phase::Write;return;
  }
  complete(-1,LEFONY_FILE_INVALID);
}
void Session::inspect() {
  if(m_request.operation==LEFONY_FILE_LIST) {
    AppFileIndex::Entry entries[LEFONY_DIRECTORY_PAGE_ENTRIES]{};
    LefonyDirectoryPage page{};page.size=sizeof(page);page.schema=1;page.generation=m_request.flags;
    int count=m_volume.listFiles(m_id,m_path,m_request.offset,&page.generation,
      entries,LEFONY_DIRECTORY_PAGE_ENTRIES,&page.next);
    if(count<0) { complete(-1,error(count));return; }
    page.count=count;
    for(int i=0;i<count;i++) {
      memcpy(page.entries[i].path,entries[i].name,strlen(entries[i].name)+1);
      page.entries[i].kind=entries[i].kind;page.entries[i].bytes=entries[i].bytes;
    }
    memcpy(m_buffer,&page,sizeof(page));m_outputBytes=sizeof(page);complete(0);return;
  }
  Volume::FileUsage usage{};
  if(!m_volume.fileUsage(m_id,&usage)) { complete(-1,LEFONY_FILE_IO);return; }
  uint32_t writerCommitted=0;
  if(m_handles[4].token) {
    uint32_t kind=0;int found=m_volume.fileInfo(m_id,m_writerPath,&kind,&writerCommitted);
    if(found<0) { complete(-1,error(found));return; }
  }
  if(m_request.operation==LEFONY_FILE_QUOTA) {
    LefonyFileQuota quota{};quota.size=sizeof(quota);quota.schema=1;quota.generation=usage.generation;
    quota.limitBytes=AppFileStore::QuotaBytes;
    quota.committedBytes=usage.data.privateBytes+usage.data.namedBytes;
    quota.projectedBytes=quota.committedBytes;
    quota.ceilingBytes=quota.committedBytes>quota.limitBytes?quota.committedBytes:quota.limitBytes;
    if(quota.committedBytes>quota.limitBytes) quota.flags|=LEFONY_FILE_QUOTA_OVER_LIMIT;
    if(m_handles[4].token) {
      quota.flags|=LEFONY_FILE_QUOTA_WRITER_OPEN;
      if(m_writerFailed) quota.flags|=LEFONY_FILE_QUOTA_WRITER_FAILED;
      quota.projectedBytes=quota.committedBytes-writerCommitted+m_volume.fileSize();
    }
    quota.remainingBytes=quota.ceilingBytes>quota.projectedBytes?quota.ceilingBytes-quota.projectedBytes:0;
    memcpy(m_buffer,&quota,sizeof(quota));m_outputBytes=sizeof(quota);complete(0);return;
  }
  Space shared{};
  if(!m_volume.space(&shared)) { complete(-1,LEFONY_FILE_IO);return; }
  LefonyFileSpace info{};info.size=sizeof(info);info.schema=1;info.generation=usage.generation;
  info.packageBytes=usage.packageBytes;info.privateBytes=usage.data.privateBytes;
  info.fileBytes=usage.data.namedBytes;info.files=usage.data.files;info.directories=usage.data.directories;
  info.extents=usage.data.extents;info.capacityBytes=shared.capacity;info.allocatedBytes=shared.allocated;
  info.availableBytes=shared.available;info.reservedBytes=shared.overhead;
  if(m_handles[4].token) {
    info.writerCommittedBytes=writerCommitted;
    info.flags=LEFONY_FILE_SPACE_WRITER_OPEN;info.writerBytes=m_volume.fileSize();
  }
  memcpy(m_buffer,&info,sizeof(info));m_outputBytes=sizeof(info);complete(0);
}
void Session::detach() {
  if(!active()) return;
  if(m_detaching) return;
  m_detaching=true;m_token=0;m_done=false;m_outputBytes=0;m_cancelled=false;m_phase=Phase::Drain;
}
void Session::poll() {
  if(m_phase==Phase::Idle) return;
  if(m_phase==Phase::Start) { start();return; }
  if(m_phase==Phase::Abort) {
    if(!terminal()) m_volume.step();
    if(terminal()) complete(m_volume.state()==State::Failed?-1:0,m_volume.state()==State::Failed?LEFONY_FILE_IO:0);
    return;
  }
  if(m_phase==Phase::Drain) {
    if(!m_cancelled) {
      for(unsigned i=0;i<5;i++) release(i);
      m_volume.cancel();m_cancelled=true;return;
    }
    if(!terminal()) m_volume.step();
    if(terminal()) { m_phase=Phase::Idle;m_id[0]=0;m_committed=nullptr; }
    return;
  }
  if(m_phase==Phase::Read || m_phase==Phase::Write) {
    int h=slot(m_request.handle);
    if(h<0) { complete(-1,LEFONY_FILE_BAD_HANDLE);return; }
    int n;
    if(h==4) {
      if(m_writerFailed) { complete(-1,error(m_volume.fileError()));return; }
      if(!m_volume.fileWritable()) m_volume.step();
      n=m_phase==Phase::Read?m_volume.readFile(m_buffer,m_request.length):m_volume.writeFile(m_buffer,m_request.length);
      if(n==-1 || m_volume.state()==State::Failed) m_writerFailed=true;
    } else {
      m_volume.stepSnapshot(m_id,m_handles[h].snapshot);
      n=m_volume.readSnapshot(m_id,m_handles[h].snapshot,m_buffer,m_request.length);
    }
    // A failed writer must not poison independent snapshot readers, including
    // a newly opened reader checking the last committed save after an abort.
    if(n==AppFileStore::Store::Pending && (h!=4 || !m_writerFailed)) return;
    if(n<0) { complete(-1,h==4?error(m_volume.fileError()):LEFONY_FILE_IO);return; }
    if(m_phase==Phase::Read) m_outputBytes=n;
    complete(n);return;
  }
  m_volume.step();
  if(m_volume.state()==State::Failed) {
    if(m_phase==Phase::Close || m_phase==Phase::Open || m_phase==Phase::Sync || m_phase==Phase::Reopen) release(4);
    complete(-1,error(m_volume.fileError()));return;
  }
  if(m_phase==Phase::Open && m_volume.fileWritable()) { complete(allocate(4,m_request.flags));return; }
  if(m_phase==Phase::Reopen && m_volume.fileWritable()) {
    if(!m_volume.seekFile(m_syncPosition)) {
      m_volume.cancel();release(4);complete(-1,LEFONY_FILE_IO);
    } else complete(0);
    return;
  }
  if(m_volume.state()!=State::Complete) return;
  if(m_phase==Phase::Sync) {
    // Publishing consumes the stream's index buffer. Start the next transaction
    // from the committed root, retaining descriptor identity and file position.
    // Reopen never repeats CREATE/TRUNCATE/EXCLUSIVE. Append still applies to
    // each subsequent write, even when the caller has sought elsewhere.
    using Mode=AppFileStore::Store::StreamMode;
    Mode mode=(m_handles[4].flags&LEFONY_FILE_APPEND)?Mode::Append:Mode::Update;
    if(!m_volume.beginStream(m_id,m_writerPath,mode)) {
      release(4);complete(-1,error(m_volume.fileError()));return;
    }
    m_phase=Phase::Reopen;return;
  }
  if(m_phase==Phase::Convert) dispatch();
  else { if(m_phase==Phase::Close) release(4);complete(0); }
}
}}

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_file_exchange.h"
#include <string.h>
namespace PrimeG2 { namespace AppFileExchange {
static_assert(sizeof(Request)==224 && sizeof(Status)==96 && sizeof(Info)==144 && sizeof(DataInfo)==176,"file exchange wire layout");
static bool zero(const void *bytes,size_t n) {
  const uint8_t *p=static_cast<const uint8_t *>(bytes);for(size_t i=0;i<n;i++) if(p[i]) return false;return true;
}
static bool padded(const char *s,size_t capacity) {
  size_t n=0;while(n<capacity && s[n]) n++;return n<capacity && zero(s+n,capacity-n);
}
bool Session::valid(const Request &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || r.operation<Inspect || r.operation>Rollback ||
     !padded(r.id,sizeof(r.id)) || !padded(r.path,sizeof(r.path)) || !r.id[0] || strlen(r.id)>48) return false;
  for(const char *p=r.id;*p;p++) if(!((*p>='a' && *p<='z') || (*p>='0' && *p<='9') || *p=='-')) return false;
  if(r.id[0]<'a' || r.id[0]>'z') return false;
  if(r.operation==Inspect || r.operation==InspectData) return !r.flags && !r.generation && !r.dataSchema && !r.length && !r.cursor && !r.path[0] && zero(r.digest,32);
  if(!r.generation || (r.path[0] && !AppFileIndex::path(r.path))) return false;
  if(r.operation>=ExportData) {
    if(r.path[0] || r.flags) return false;
    if(r.operation==ImportData) return r.length<=AppStorage::MaximumData && !r.cursor;
    return !r.length && zero(r.digest,32) && (r.operation==Rollback?r.cursor!=0:r.cursor==0);
  }
  if(r.operation!=List && !r.path[0]) return false;
  if(r.operation==Import) return !(r.flags&~Replace) && r.length<=64u*1024u*1024u && !r.cursor;
  return !r.flags && !r.length && (r.operation==List || !r.cursor) && zero(r.digest,32);
}
void Session::reject(const Request &r,uint32_t error) {
  if(m_active) return;
  uint32_t sequence=m_status.sequence+(m_status.sequence!=0xffffffffu);
  m_status={0x5841464c,96,1,Failed,r.operation,error,sequence,0,0,0,0,0,512,0,{0,0},{0}};
}
bool Session::begin(const Request &r,const Identity &id,uint32_t now) {
  if(m_active || !valid(r) || strcmp(r.id,id.id) || m_status.sequence==0xffffffffu ||
     id.privateBytes>AppStorage::MaximumData || (id.privateBytes && !id.privateData)) return false;
  m_request=r;m_status={0x5841464c,96,1,Working,r.operation,0,m_status.sequence+1,0,r.length,0,
    id.generation,id.dataSchema,512,0,{0,0},{0}};
  m_step=Step::None;m_command=0;m_acknowledged=m_cancel=m_commitStarted=m_importOwned=false;m_handle=m_token=0;
  if(r.operation!=Inspect && r.operation!=InspectData && (r.generation!=id.generation || r.dataSchema!=id.dataSchema)) {
    m_status.error=LEFONY_FILE_CHANGED;m_status.state=Failed;return true;
  }
  if((r.operation==Import || r.operation==ImportData) && (id.appSchema!=id.dataSchema || id.pendingUpgrade)) {
    m_status.error=LEFONY_FILE_SCHEMA;m_status.state=Failed;return true;
  }
  if(r.operation==Rollback && (!id.pendingUpgrade || !(id.dataInfo.flags&RecoveryTrusted) ||
      r.cursor!=id.dataInfo.previousPackage)) {
    m_status.error=LEFONY_FILE_DENIED;m_status.state=Failed;return true;
  }
  if(!direct() && r.operation!=Import && !m_files.attach(id.id,id.version,id.appSchema,id.dataSchema,id.privateData,id.privateBytes)) return false;
  m_active=true;m_lastProgress=now;NativeAppHash::shaInit(&m_hash);
  m_saved=id.privateData;m_dataInfo=id.dataInfo;
  m_dataInfo.size=sizeof(m_dataInfo);m_dataInfo.schema=1;m_dataInfo.generation=id.generation;
  memcpy(m_dataInfo.version,id.version,sizeof(id.version));
  m_dataInfo.appSchema=id.appSchema;m_dataInfo.dataSchema=id.dataSchema;m_dataInfo.privateBytes=id.privateBytes;
  NativeAppHash::sha256(id.privateData,id.privateBytes,m_dataInfo.privateHash);
  if(r.operation==InspectData) {
    memcpy(m_reply,&m_dataInfo,sizeof(m_dataInfo));m_status.length=sizeof(m_dataInfo);ready(Readable,now);
  } else if(r.operation==ExportData) {
    m_status.length=id.privateBytes;
    if(id.privateBytes) ready(Readable,now);else finish();
  } else if(r.operation==ImportData) {
    AppStorage::Volume::FileUsage usage{};
    if(!m_volume.fileUsage(id.id,&usage)) {stop(LEFONY_FILE_IO);return true;}
    uint32_t used=usage.data.namedBytes+usage.data.privateBytes;
    uint32_t ceiling=used>AppFileStore::QuotaBytes?used:AppFileStore::QuotaBytes;
    if(r.length>ceiling-usage.data.namedBytes) {stop(LEFONY_FILE_QUOTA_EXCEEDED);return true;}
    ready(Writable,now);
  } else if(r.operation==Rollback) ready(Writable,now);
  else if(r.operation==Inspect) {
    m_info={};m_info.size=sizeof(m_info);m_info.schema=1;memcpy(m_info.version,id.version,sizeof(id.version));
    m_info.dataSchema=id.dataSchema;m_info.appSchema=id.appSchema;m_info.pendingUpgrade=id.pendingUpgrade;
    submit(LEFONY_FILE_SPACE,Step::InfoSpace);
  } else if(r.operation==List) submit(LEFONY_FILE_LIST,Step::Read);
  else if(r.operation==Export) submit(LEFONY_FILE_OPEN,Step::OpenExport,LEFONY_FILE_READABLE);
  else {
    AppStorage::Volume::FileUsage usage{};uint32_t kind=0,oldBytes=0;
    int found=m_volume.fileInfo(id.id,r.path,&kind,&oldBytes);
    if(found<0 || !m_volume.fileUsage(id.id,&usage)) { stop(LEFONY_FILE_IO);return true; }
    uint32_t used=usage.data.namedBytes+usage.data.privateBytes,ceiling=used>AppFileStore::QuotaBytes?used:AppFileStore::QuotaBytes;
    if(found && kind!=AppFileIndex::File) { stop(LEFONY_FILE_IS_DIRECTORY);return true; }
    if(r.length>ceiling-used+oldBytes) { stop(LEFONY_FILE_QUOTA_EXCEEDED);return true; }
    if(found && !(r.flags&Replace)) {stop(LEFONY_FILE_EXISTS);return true;}
    // Host imports declare their full length. Reserve once, then use the
    // existing fixed-length chunk writer instead of growing a stream.
    AppDocumentRoot::Root root;
    if(m_volume.documentRoot(id.id,&root)) beginImport();
    else if(m_volume.beginCheckpoint(id.id,id.privateData,id.privateBytes,id.version,id.dataSchema)) {
      m_importOwned=true;m_step=Step::ImportConvert;
    } else stop(LEFONY_FILE_IO);
  }
  return true;
}
void Session::beginImport() {
  if(!m_volume.beginFile(m_request.id,m_request.path,m_request.length)) {stop(LEFONY_FILE_IO);return;}
  m_importOwned=true;m_step=Step::ImportPrepare;m_status.state=Working;
}
void Session::pollImport(uint32_t now) {
  using State=AppStorage::State;
  if(m_step==Step::ImportConvert || m_step==Step::ImportCommit || !m_volume.fileWritable()) m_volume.step();
  if(m_volume.state()==State::Failed) {stop(LEFONY_FILE_IO);return;}
  if(m_step==Step::ImportConvert) {
    if(m_volume.state()==State::Complete) beginImport();
    return;
  }
  if(m_step==Step::ImportCommit) {
    if(m_volume.state()!=State::Complete) return;
    m_status.flags|=Committed;m_importOwned=false;
    AppStorage::Volume::FileUsage usage{};
    if(!m_volume.fileUsage(m_request.id,&usage)) {stop(LEFONY_FILE_IO);return;}
    m_status.generation=usage.generation;finish();return;
  }
  if(!m_volume.fileWritable()) return;
  if(m_step==Step::ImportWrite && m_uploadUsed<m_uploadBytes) {
    int used=m_volume.writeFile(m_upload+m_uploadUsed,m_uploadBytes-m_uploadUsed);
    if(used<=0 || static_cast<uint32_t>(used)>m_uploadBytes-m_uploadUsed) {stop(LEFONY_FILE_IO);return;}
    NativeAppHash::shaUpdate(&m_hash,m_upload+m_uploadUsed,used);
    m_uploadUsed+=used;m_status.offset+=used;
    // A chunk boundary still requires its existing physical readback before
    // accepting more bytes or exposing the host's final COMMIT boundary.
    if(m_uploadUsed<m_uploadBytes || !m_volume.fileWritable()) return;
  }
  if(m_status.offset==m_status.length) m_staged=nullptr;
  ready(Writable,now);
}
void Session::submit(uint32_t operation,Step step,uint32_t flags,uint32_t length) {
  LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=operation;r.flags=flags;r.length=length;
  bool named=operation==LEFONY_FILE_OPEN || operation==LEFONY_FILE_LIST;
  if(named && m_request.path[0]) {r.path=1;r.pathBytes=strlen(m_request.path);}
  if(operation==LEFONY_FILE_LIST) {r.offset=m_request.cursor;r.flags=m_request.generation;}
  else if(!named && operation!=LEFONY_FILE_SPACE && operation!=LEFONY_FILE_QUOTA) r.handle=m_handle;
  if(operation==LEFONY_FILE_WRITE) r.buffer=1;
  int result=m_files.exchange(r,named?m_request.path:nullptr,nullptr,
    operation==LEFONY_FILE_WRITE?m_upload+m_uploadUsed:nullptr,nullptr);
  if(result!=1) {stop(result<0?-result:LEFONY_FILE_IO);return;}
  m_token=r.token;m_step=step;m_status.state=Working;m_status.available=0;
}
void Session::ready(uint32_t state,uint32_t now) {
  m_step=Step::None;m_status.state=state;m_lastProgress=now;
  m_status.available=state==Readable?m_status.length-m_status.offset:0;
  if(m_status.available>512) m_status.available=512;
  if(state==Readable && m_request.operation==ExportData) memcpy(m_reply,m_saved+m_status.offset,m_status.available);
}
void Session::stop(uint32_t error) {
  m_staged=nullptr;m_export=nullptr;
  m_status.error=error;m_status.available=0;m_command=0;m_acknowledged=false;
  if(m_commitStarted && !(m_status.flags&Committed)) m_status.flags|=CommitUncertain;
  if(m_importOwned) m_volume.cancel();
  m_files.detach();m_step=Step::Drain;m_status.state=Working;
}
void Session::finish() {
  m_export=nullptr;
  NativeAppHash::shaFinal(&m_hash,m_status.digest);
  m_files.detach();m_step=Step::Drain;m_status.available=0;m_status.state=Working;
}
bool Session::request(uint8_t command,uint32_t arg,const uint8_t *data,size_t bytes) {
  if(!m_active || m_command || m_cancel) return false;
  if((m_staged || m_export) && command!=0x75) return false;
  if(command==0x75) {
    if(bytes || arg!=m_status.sequence || m_commitStarted) return false;
  } else if(command==0x74) {
    if(bytes || arg!=m_status.sequence || m_status.state!=Writable || m_status.offset!=m_status.length) return false;
  } else if(command==0x72 || command==0x73) {
    if(arg || !data || bytes<8) return false;
    uint32_t token,offset;memcpy(&token,data,4);memcpy(&offset,data+4,4);
    if(token!=m_status.sequence) return false;
    if(command==0x72) {
      if(m_status.state!=Writable || offset!=m_status.offset || bytes<=8 || bytes>512 || bytes-8>m_status.length-m_status.offset) return false;
      m_uploadBytes=bytes-8;m_uploadUsed=0;memcpy(m_upload,data+8,m_uploadBytes);
    } else {
      if(bytes!=8 || m_status.state!=Readable || offset!=m_status.offset+m_status.available) return false;
      m_ackOffset=offset;
    }
  } else return false;
  m_command=command;m_acknowledged=false;return true;
}
bool Session::response(uint8_t command,uint32_t arg,uint8_t *out,size_t capacity,size_t *bytes) const {
  if(!out || !bytes) return false;
  if(command==0x70) {
    if(arg || capacity!=sizeof(m_status)) return false;
    Status status=m_status;if(m_command) {status.state=Working;status.available=0;}
    memcpy(out,&status,sizeof(status));*bytes=sizeof(status);return true;
  }
  if(command!=0x72 || !m_active || m_command || arg!=m_status.sequence || m_status.state!=Readable ||
     capacity!=m_status.available) return false;
  memcpy(out,m_reply+(m_request.operation==Export || m_request.operation==ExportData?0:m_status.offset),capacity);*bytes=capacity;return true;
}
void Session::disconnect() {
  // The successful OUT status is the host's commit boundary. Poll may not yet
  // have started the filesystem transaction when a bus reset arrives.
  if(m_active && !m_commitStarted && !commitAcknowledged()) m_cancel=true;
}
bool Session::stage(uint32_t sequence,const uint8_t *data,uint32_t length) {
  if(!data || !length || !m_active || m_command || m_cancel || m_staged ||
     m_request.operation!=Import || m_status.state!=Writable || m_status.offset ||
     sequence!=m_status.sequence || length!=m_status.length) return false;
  m_staged=data;return true;
}
void Session::stageProgress(uint32_t sequence,uint32_t now) {
  if(m_active && m_status.sequence==sequence && m_status.state==Writable) m_lastProgress=now;
}
bool Session::stageExport(uint32_t sequence,uint8_t *data,uint32_t length) {
  if(!data || !length || !m_active || m_command || m_cancel || m_export ||
     m_request.operation!=Export || m_status.state!=Readable || m_status.offset ||
     sequence!=m_status.sequence || length!=m_status.length) return false;
  m_export=data;return true;
}
void Session::poll(uint32_t now) {
  if(!m_active) return;
  if(m_cancel || (!m_staged && !commitAcknowledged() && (m_status.state==Readable || m_status.state==Writable) && uint32_t(now-m_lastProgress)>=30000u)) {
    bool cancelled=m_cancel;m_cancel=false;stop(cancelled?CancelledError:Timeout);
  }
  if(m_step==Step::Drain) {
    if(m_importOwned) {
      using State=AppStorage::State;
      auto state=m_volume.state();
      if(state!=State::Ready && state!=State::Complete && state!=State::Failed) {m_volume.step();return;}
      m_importOwned=false;
    }
    m_files.poll();if(m_files.active()) return;
    m_active=false;m_step=Step::None;m_status.state=m_status.error?
      (m_status.error==CancelledError || m_status.error==Timeout?Cancelled:Failed):Complete;return;
  }
  if(m_step==Step::ImportConvert || m_step==Step::ImportPrepare ||
     m_step==Step::ImportWrite || m_step==Step::ImportCommit) {pollImport(now);return;}
  if(m_step==Step::DataCommit) {
    m_volume.step();auto state=m_volume.state();
    if(state==AppStorage::State::Failed) {stop(LEFONY_FILE_IO);return;}
    if(state!=AppStorage::State::Complete) return;
    m_status.flags|=Committed;AppStorage::Volume::FileUsage usage{};
    if(!m_volume.fileUsage(m_request.id,&usage)) {stop(LEFONY_FILE_IO);return;}
    m_status.generation=usage.generation;
    if(m_request.operation==Rollback) m_status.dataSchema=m_dataInfo.previousSchema;
    finish();return;
  }
  // RAM staging removes USB round trips; writes still use the normal bounded
  // file session. The host must explicitly commit after all bytes are hashed.
  if(m_staged && m_status.state==Writable && !m_command) {
    uint32_t remaining=m_status.length-m_status.offset;
    if(!remaining) {m_staged=nullptr;m_lastProgress=now;}
    else {
      m_uploadBytes=remaining<sizeof(m_upload)?remaining:sizeof(m_upload);
      m_uploadUsed=0;memcpy(m_upload,m_staged+m_status.offset,m_uploadBytes);
      m_command=0x72;m_acknowledged=true;
    }
  }
  if(m_export && m_status.state==Readable && !m_command) {
    memcpy(m_export+m_status.offset,m_reply,m_status.available);
    m_ackOffset=m_status.offset+m_status.available;m_command=0x73;m_acknowledged=true;
  }
  if(m_command && m_acknowledged) {
    uint8_t command=m_command;m_command=0;m_acknowledged=false;m_lastProgress=now;
    if(command==0x75) {stop(CancelledError);return;}
    if(command==0x72) {
      if(m_request.operation==ImportData) {
        memcpy(m_private+m_status.offset,m_upload,m_uploadBytes);
        NativeAppHash::shaUpdate(&m_hash,m_upload,m_uploadBytes);m_status.offset+=m_uploadBytes;ready(Writable,now);
      } else if(m_request.operation==Import) {m_step=Step::ImportWrite;m_status.state=Working;}
      else submit(LEFONY_FILE_WRITE,Step::Write,0,m_uploadBytes);
      return;
    }
    if(command==0x74) {
      auto hash=m_hash;uint8_t digest[32];NativeAppHash::shaFinal(&hash,digest);
      if(m_request.operation!=Rollback && memcmp(digest,m_request.digest,32)) {stop(DigestMismatch);return;}
      if(direct()) {
        AppStorage::Volume::FileUsage usage{};
        if(!m_volume.fileUsage(m_request.id,&usage)) {stop(LEFONY_FILE_IO);return;}
        if(usage.generation!=m_request.generation) {stop(LEFONY_FILE_CHANGED);return;}
        m_commitStarted=true;
        bool ok=m_request.operation==Rollback?m_volume.beginRollback(m_request.id):
          m_volume.beginCheckpoint(m_request.id,m_private,m_request.length,m_dataInfo.version,m_request.dataSchema,false);
        if(!ok) {stop(LEFONY_FILE_IO);return;}
        m_step=Step::DataCommit;m_status.state=Working;return;
      }
      m_commitStarted=true;
      if(m_request.operation==Import) {
        if(!m_volume.commitFile()) {stop(LEFONY_FILE_IO);return;}
        m_step=Step::ImportCommit;m_status.state=Working;
      } else submit(LEFONY_FILE_CLOSE,Step::Close);
      return;
    }
    uint32_t available=m_status.available;
    NativeAppHash::shaUpdate(&m_hash,m_reply+(m_request.operation==Export || m_request.operation==ExportData?0:m_status.offset),available);
    m_status.offset=m_ackOffset;m_status.available=0;
    if(m_status.offset==m_status.length) {
      if(m_request.operation==Export) submit(LEFONY_FILE_CLOSE,Step::Close);else finish();
    } else if(m_request.operation==Export) submit(LEFONY_FILE_READ,Step::Read,0,
      m_status.length-m_status.offset<512?m_status.length-m_status.offset:512);
    else ready(Readable,now);
    return;
  }
  if(m_step==Step::None) return;
  m_files.poll();LefonyFileRequest r{};r.size=sizeof(r);r.schema=1;r.operation=LEFONY_FILE_POLL;
  r.token=m_token;r.buffer=1;r.capacity=sizeof(m_reply);
  int result=m_files.exchange(r,nullptr,nullptr,nullptr,m_reply);
  if(result==1) return;
  if(result<0 || r.error) {stop(result<0?-result:r.error);return;}
  switch(m_step) {
  case Step::InfoSpace:
    if(r.length!=sizeof(m_info.space)) {stop(LEFONY_FILE_IO);return;}
    memcpy(&m_info.space,m_reply,r.length);submit(LEFONY_FILE_QUOTA,Step::InfoQuota);break;
  case Step::InfoQuota:
    if(r.length!=sizeof(m_info.quota)) {stop(LEFONY_FILE_IO);return;}
    memcpy(&m_info.quota,m_reply,r.length);memcpy(m_reply,&m_info,sizeof(m_info));
    m_status.length=sizeof(m_info);ready(Readable,now);break;
  case Step::OpenImport:m_handle=r.result;ready(Writable,now);break;
  case Step::OpenExport:m_handle=r.result;submit(LEFONY_FILE_STAT,Step::ExportStat);break;
  case Step::ExportStat: {
    if(r.length!=sizeof(LefonyFileInfo)) {stop(LEFONY_FILE_IO);return;}
    LefonyFileInfo info;memcpy(&info,m_reply,sizeof(info));m_status.length=info.bytes;
    if(!info.bytes) submit(LEFONY_FILE_CLOSE,Step::Close);
    else submit(LEFONY_FILE_READ,Step::Read,0,info.bytes<512?info.bytes:512);
    break;
  }
  case Step::Read:
    if(m_request.operation==List) {
      if(r.length!=sizeof(LefonyDirectoryPage)) {stop(LEFONY_FILE_IO);return;}
      m_status.length=r.length;
    } else if(r.result<=0 || r.length!=static_cast<uint32_t>(r.result) ||
       r.length>(m_status.length-m_status.offset<512?m_status.length-m_status.offset:512)) {stop(LEFONY_FILE_IO);return;}
    ready(Readable,now);if(m_request.operation==Export) m_status.available=r.length;break;
  case Step::Write:
    if(r.result<=0 || static_cast<uint32_t>(r.result)>m_uploadBytes-m_uploadUsed) {stop(LEFONY_FILE_IO);return;}
    NativeAppHash::shaUpdate(&m_hash,m_upload+m_uploadUsed,r.result);m_uploadUsed+=r.result;m_status.offset+=r.result;
    if(m_uploadUsed<m_uploadBytes) submit(LEFONY_FILE_WRITE,Step::Write,0,m_uploadBytes-m_uploadUsed);else {if(m_status.offset==m_status.length) m_staged=nullptr;ready(Writable,now);}
    break;
  case Step::Close:
    if(m_request.operation==Import) {
      m_status.flags|=Committed;AppStorage::Volume::FileUsage usage{};
      if(!m_volume.fileUsage(m_request.id,&usage)) {stop(LEFONY_FILE_IO);return;}
      m_status.generation=usage.generation;
    }
    finish();break;
  default:stop(LEFONY_FILE_IO);break;
  }
}
}}

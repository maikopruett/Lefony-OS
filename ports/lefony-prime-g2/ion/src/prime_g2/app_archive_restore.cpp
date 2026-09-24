// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_archive_restore.h"
namespace PrimeG2 { namespace AppArchive {
namespace {
uint32_t minimum(uint32_t a,uint32_t b) { return a<b?a:b; }
bool sameObject(const AppFileIndex::Extent &a,const AppFileIndex::Extent &b) {
  return a.type==b.type && a.generation==b.generation && a.part==b.part;
}
}
Restore::Restore(lfs_t *fs,AppDocumentStore::Store *documents):m_fs(fs),m_documents(documents) {
  m_fileConfig.buffer=m_cache;
}
Restore::State Restore::state() const {
  switch(m_phase) {
  case Phase::Idle:return State::Idle;
  case Phase::Header:case Phase::Pair:case Phase::Package:case Phase::Private:
  case Phase::Entry:case Phase::Content:case Phase::Trailer:return State::Receiving;
  case Phase::Ready:return State::Ready;
  case Phase::Done:return State::Complete;
  case Phase::Cancelled:return State::Cancelled;
  case Phase::Failed:return State::Failed;
  case Phase::Publish:
    if(m_commitAttempted || m_documents->state()==AppDocumentStore::Store::State::Committing) return State::Committing;
    return State::Working;
  default:return State::Working;
  }
}
bool Restore::begin(const char *id,const AppDocumentRoot::Root &before,uint32_t base,
                    uint32_t currentLimit,uint32_t bytes,const uint8_t digest[32],
                    uint8_t *scratch,uint32_t capacity,Hooks hooks) {
  State s=state();
  if((s!=State::Idle && s!=State::Complete && s!=State::Cancelled && s!=State::Failed) ||
     !m_fs || !m_documents || !id || !digest || !scratch || capacity<MaximumPackage ||
     bytes<sizeof(Header)+sizeof(PairHeader)+468 || bytes>MaximumArchive ||
     currentLimit>MaximumData || (before.serial && (!AppDocumentRoot::valid(before) || base!=before.serial)) ||
     !hooks.authenticate || !hooks.unchanged || !hooks.admit || (hooks.repairLegacy && !hooks.privateVerified) ||
     m_documents->state()==AppDocumentStore::Store::State::Busy ||
     m_documents->state()==AppDocumentStore::Store::State::Committing) return false;
  Header check{};memcpy(check.magic,"LFARCH1\0",8);check.schema=1;check.size=sizeof(check);
  check.bytes=bytes;check.pairs=1;
  unsigned n=0;for(;n<49 && id[n];n++) check.id[n]=id[n];
  if(n==49 || !valid(check) || !target(id,before,base,hooks.repairLegacy) || !hooks.unchanged(hooks.context)) return false;
  memcpy(m_id,check.id,n+1);m_before=before;m_base=base;m_limit=currentLimit;m_total=bytes;
  memcpy(m_expected,digest,32);m_hooks=hooks;m_package=scratch;m_after={};
  m_received=m_pairNumber=m_reused=0;m_error=Error::None;m_cancelled=m_cleanupFailed=false;
  m_publisher=m_commitAttempted=m_directoryCreated=m_objectsCreated=false;
  for(unsigned i=0;i<2;i++) {
    m_new[i].clear();m_old[i].clear();m_parts[i]=0;m_packageStaged[i]=m_indexStaged[i]=false;
  }
  NativeAppHash::shaInit(&m_whole);frame(Phase::Header);return true;
}
bool Restore::target(const char *id,const AppDocumentRoot::Root &before,uint32_t base,bool repairLegacy) {
  // Missing and unreadable are different states. Even an erroneous caller
  // cannot treat an empty, damaged or unknown canonical file as a new app.
  char path[64];size_t n=strlen(id);memcpy(path,"apps/",5);memcpy(path+5,id,n);memcpy(path+5+n,".app",5);
  lfs_info info;int rc=lfs_stat(m_fs,path,&info);
  if(rc==LFS_ERR_NOENT) return !base && !before.serial;
  if(rc || !base || info.type!=LFS_TYPE_REG) return false;
  if(before.serial) {
    AppDocumentRoot::Root actual;uint8_t expected[AppDocumentRoot::Bytes],observed[AppDocumentRoot::Bytes];
    return m_documents->root(id,&actual) &&
      AppDocumentRoot::encode(before,expected) && AppDocumentRoot::encode(actual,observed) &&
      !memcmp(expected,observed,sizeof(expected));
  }
  if(!open(path,LFS_O_RDONLY)) return false;
  uint8_t header[64];bool ok=lfs_file_read(m_fs,&m_file,header,sizeof(header))==sizeof(header);
  ok=close() && ok;
  using AppFileIndex::get;
  return ok && !memcmp(header,"LFAFILE2",8) && get(header+8)==2 && get(header+12)==base &&
    get(header+16)>=468 && get(header+16)<=MaximumPackage && get(header+20)<=65536 &&
    zero(header+56,8) && (repairLegacy || info.size==64+get(header+16)+get(header+20));
}
void Restore::frame(Phase next) { m_phase=next;m_frameBytes=0; }
void Restore::object(char type,uint32_t gen,char out[80],uint32_t part) const {
  memcpy(out,"objects/",8);size_t n=strlen(m_id);memcpy(out+8,m_id,n);out[n+8]='/';
  AppFileIndex::Extent x;x.generation=gen;x.part=part;x.type=type=='c'?AppFileIndex::ChunkObject:AppFileIndex::DataObject;
  AppFileIndex::objectName(x,out+n+9);out[n+9]=type;
}
bool Restore::open(const char *path,int mode) {
  if(m_open) return false;
  m_file={};m_cursor=0;m_open=lfs_file_opencfg(m_fs,&m_file,path,mode,&m_fileConfig)==0;return m_open;
}
bool Restore::close() {
  if(!m_open) return true;
  int rc=lfs_file_close(m_fs,&m_file);m_open=false;return !rc;
}
void Restore::fail(Error error) {
  if(m_error==Error::None) m_error=error;
  if(!close()) m_cleanupFailed=true;
  // A failed rename may have committed. Never remove its referenced objects.
  if(m_commitAttempted) { m_error=Error::CommitUnknown;m_phase=Phase::Failed;return; }
  if(m_publisher) m_documents->cancel();
  m_phase=Phase::Cleanup;
}
bool Restore::cancel() {
  State s=state();
  if(s==State::Committing || s==State::Complete || s==State::Failed || s==State::Cancelled || s==State::Idle) return false;
  m_cancelled=true;fail(Error::None);return true;
}
int Restore::write(const void *data,uint32_t bytes) {
  if(state()!=State::Receiving) return state()==State::Working?-2:-1;
  if(!bytes) return 0;
  if(!data || bytes>2048) return -1;
  uint32_t n=0;const uint8_t *in=static_cast<const uint8_t *>(data);
  if(m_phase==Phase::Package) {
    n=minimum(bytes,m_pair.packageBytes-m_cursor);memcpy(m_package+m_cursor,in,n);m_cursor+=n;
    NativeAppHash::shaUpdate(&m_contentHash,in,n);
    NativeAppHash::shaUpdate(&m_packagePrivateHash,in,n);
  } else if(m_phase==Phase::Private || m_phase==Phase::Content) {
    n=minimum(bytes,minimum(m_contentLeft,AppFileIndex::ChunkBytes-m_chunkFill));
    memcpy(m_chunk+m_chunkFill,in,n);m_chunkFill+=n;m_contentLeft-=n;
    NativeAppHash::shaUpdate(&m_contentHash,in,n);
    if(m_phase==Phase::Private) NativeAppHash::shaUpdate(&m_packagePrivateHash,in,n);
  } else {
    uint32_t target=m_phase==Phase::Header?sizeof(Header):m_phase==Phase::Pair?sizeof(PairHeader):
      m_phase==Phase::Entry?sizeof(EntryHeader):32;
    n=minimum(bytes,target-m_frameBytes);memcpy(m_frame+m_frameBytes,in,n);m_frameBytes+=n;
  }
  NativeAppHash::shaUpdate(&m_whole,in,n);m_received+=n;
  if(m_received>m_total) { fail(Error::Format);return -1; }
  parsed();
  if(m_received==m_total && state()==State::Receiving) fail(Error::Format);
  return n;
}
void Restore::parsed() {
  switch(m_phase) {
  case Phase::Header:
    if(m_frameBytes==sizeof(Header)) {
      memcpy(&m_header,m_frame,sizeof(m_header));
      if(!valid(m_header) || strcmp(m_header.id,m_id) || m_header.bytes!=m_total || m_base>0xffffffffu-m_header.pairs) { fail(Error::Format);break; }
      m_after.format=4;m_after.serial=m_base+m_header.pairs;m_after.flags=m_header.flags;
      memcpy(m_after.highVersion,compare(m_before.highVersion,m_header.highVersion)>0?m_before.highVersion:m_header.highVersion,12);
      frame(Phase::Pair);
    }
    break;
  case Phase::Pair:
    if(m_frameBytes==sizeof(PairHeader)) {
      memcpy(&m_pair,m_frame,sizeof(m_pair));
      if(!valid(m_pair) || compare(m_pair.version,m_header.highVersion)>0 ||
         (m_pairNumber && compare(m_pair.version,m_currentVersion)>=0)) { fail(Error::Format);break; }
      if(!m_pairNumber) memcpy(m_currentVersion,m_pair.version,12);
      index().clear();m_used=m_pair.privateBytes;
      if(m_used>(m_pairNumber?MaximumData:m_limit)) { fail(Error::Space);break; }
      auto &p=pair();p.package=p.data=generation();p.packageBytes=m_pair.packageBytes;
      p.dataKind=AppDocumentRoot::FileIndex;p.dataSchema=m_pair.dataSchema;memcpy(p.packageHash,m_pair.packageHash,32);
      m_cursor=0;NativeAppHash::shaInit(&m_contentHash);NativeAppHash::shaInit(&m_packagePrivateHash);m_phase=Phase::Package;
    }
    break;
  case Phase::Package:
    if(m_cursor==m_pair.packageBytes) {
      NativeAppHash::shaFinal(&m_contentHash,m_digest);
      if(memcmp(m_digest,m_pair.packageHash,32)) fail(Error::Integrity);else m_phase=Phase::Authenticate;
    }
    break;
  case Phase::Private:case Phase::Content:
    if(!m_contentLeft || m_chunkFill==AppFileIndex::ChunkBytes) {
      NativeAppHash::sha256(m_chunk,m_chunkFill,m_chunkHash);m_search=0;m_phase=Phase::FindReuse;
    }
    break;
  case Phase::Entry:
    if(m_frameBytes==sizeof(EntryHeader)) {
      EntryHeader e;memcpy(&e,m_frame,sizeof(e));
      if(!valid(e) || index().find(e.name)>=0 || index().entries>=AppFileIndex::MaximumEntries) { fail(Error::Format);break; }
      uint32_t limit=m_pairNumber?MaximumData:m_limit;
      if(e.bytes>limit-m_used || (e.bytes+AppFileIndex::ChunkBytes-1)/AppFileIndex::ChunkBytes>AppFileIndex::MaximumExtents-index().extents) { fail(Error::Space);break; }
      m_used+=e.bytes;auto &entry=index().entry[index().entries++];entry={};
      memcpy(entry.name,e.name,sizeof(e.name));entry.kind=e.kind;entry.bytes=e.bytes;entry.first=index().extents;
      if(e.kind==AppFileIndex::Directory) nextEntry();else content();
    }
    break;
  case Phase::Trailer:
    if(m_frameBytes==32) {
      if(memcmp(m_frame,m_digest,32)) fail(Error::Integrity);else nextEntry();
    }
    break;
  default:break;
  }
}
void Restore::content() {
  m_contentLeft=index().entry[index().entries-1].bytes;m_chunkFill=0;
  NativeAppHash::shaInit(&m_contentHash);m_phase=index().entries==1?Phase::Private:Phase::Content;
  if(!m_contentLeft) finishContent();
}
void Restore::finishContent() {
  NativeAppHash::shaFinal(&m_contentHash,m_digest);
  if(index().entries==1) {
    if(memcmp(m_digest,m_pair.privateHash,32)) {fail(Error::Integrity);return;}
    uint8_t combined[32];NativeAppHash::shaFinal(&m_packagePrivateHash,combined);
    if(m_hooks.privateVerified && !m_hooks.privateVerified(m_hooks.context,m_pair,m_pairNumber,combined)) fail(Error::Authority);
    else nextEntry();
  } else frame(Phase::Trailer);
}
void Restore::nextEntry() {
  if(index().entries==m_pair.entries+1) finishPair();else frame(Phase::Entry);
}
void Restore::finishPair() {
  if(!AppFileIndex::encode(index(),generation(),m_indexWire,sizeof(m_indexWire))) { fail(Error::Format);return; }
  pair().dataBytes=AppFileIndex::encodedBytes(index());
  NativeAppHash::sha256(m_indexWire,pair().dataBytes,pair().dataHash);m_phase=Phase::WriteIndex;
}
void Restore::chunkDone(const AppFileIndex::Extent &extent) {
  if(index().extents==AppFileIndex::MaximumExtents) { fail(Error::Space);return; }
  index().extent[index().extents++]=extent;index().entry[index().entries-1].count++;m_chunkFill=0;
  if(!m_contentLeft) finishContent();else m_phase=index().entries==1?Phase::Private:Phase::Content;
}
void Restore::findReuse() {
  // One candidate per step; a damaged old index is never a source of extents.
  unsigned source=m_search/AppFileIndex::MaximumExtents,offset=m_search++%AppFileIndex::MaximumExtents;
  if(source>=2+(m_pairNumber?1u:0u)) { m_phase=Phase::WriteChunk;return; }
  const auto &old=source==2?m_new[0]:m_old[source];
  if(offset>=old.extents) { m_search=(source+1)*AppFileIndex::MaximumExtents;return; }
  const auto &x=old.extent[offset];
  if(x.bytes!=m_chunkFill || memcmp(x.hash,m_chunkHash,32) || (x.type==AppFileIndex::DataObject && index().entries!=1)) return;
  for(uint32_t i=0;i<index().extents;i++) if(sameObject(x,index().extent[i])) return;
  m_candidate=x;NativeAppHash::shaInit(&m_reuseHash);m_phase=Phase::CheckReuse;
}
void Restore::checkReuse() {
  if(!m_open) {
    char path[80];object(m_candidate.type==AppFileIndex::ChunkObject?'c':'d',m_candidate.generation,path,m_candidate.part);
    if(!open(path,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(m_candidate.bytes)) {
      if(!close()) { fail(Error::IO);return; }m_phase=Phase::FindReuse;
    }
  } else if(m_cursor<m_candidate.bytes) {
    uint32_t n=minimum(sizeof(m_scratch),m_candidate.bytes-m_cursor);
    if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) {
      if(!close()) { fail(Error::IO);return; }m_phase=Phase::FindReuse;return;
    }
    NativeAppHash::shaUpdate(&m_reuseHash,m_scratch,n);m_cursor+=n;
  } else {
    uint8_t digest[32];NativeAppHash::shaFinal(&m_reuseHash,digest);
    if(!close()) { fail(Error::IO);return; }
    if(memcmp(digest,m_candidate.hash,32)) m_phase=Phase::FindReuse;
    else { m_reused+=m_candidate.bytes;chunkDone(m_candidate); }
  }
}
bool Restore::stage(char type,const uint8_t *data,uint32_t bytes,uint32_t part) {
  if(!m_open) {
    if(!m_hooks.admit(m_hooks.context,bytes)) { fail(Error::Space);return false; }
    if(type=='p') m_packageStaged[m_pairNumber]=true;
    else if(type=='d') m_indexStaged[m_pairNumber]=true;
    else m_parts[m_pairNumber]=part;
    char path[80];object(type,generation(),path,part);
    if(!open(path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC)) fail(Error::IO);
  } else if(m_cursor<bytes) {
    uint32_t n=minimum(2048,bytes-m_cursor);
    if(lfs_file_write(m_fs,&m_file,data+m_cursor,n)!=static_cast<lfs_ssize_t>(n)) fail(Error::IO);else m_cursor+=n;
  } else {
    if(!close()) fail(Error::IO);else return true;
  }
  return false;
}
bool Restore::commit() {
  if(m_phase!=Phase::Ready) return false;
  if(!m_hooks.unchanged(m_hooks.context)) { fail(Error::Changed);return false; }
  if(!m_hooks.admit(m_hooks.context,0)) { fail(Error::Space);return false; }
  if(!m_documents->publishStaged(m_id,m_before,m_after)) { fail(Error::IO);return false; }
  m_publisher=true;m_phase=Phase::Publish;return true;
}
void Restore::cleanup() {
  char path[80];bool remove=false;
  if(m_publisher) { memcpy(path,"apps/.pending",14);m_publisher=false;remove=true; }
  else for(unsigned i=0;i<2;i++) {
    if(m_parts[i]) { object('c',m_base+i+1,path,m_parts[i]--);remove=true;break; }
    if(m_indexStaged[i]) { object('d',m_base+i+1,path);m_indexStaged[i]=false;remove=true;break; }
    if(m_packageStaged[i]) { object('p',m_base+i+1,path);m_packageStaged[i]=false;remove=true;break; }
  }
  if(!remove && m_directoryCreated) {
    memcpy(path,"objects/",8);memcpy(path+8,m_id,strlen(m_id)+1);m_directoryCreated=false;remove=true;
  } else if(!remove && m_objectsCreated) { memcpy(path,"objects",8);m_objectsCreated=false;remove=true; }
  if(remove) {
    int rc=lfs_remove(m_fs,path);if(rc && rc!=LFS_ERR_NOENT && rc!=LFS_ERR_NOTEMPTY) m_cleanupFailed=true;
  } else m_phase=m_cancelled && m_error==Error::None && !m_cleanupFailed?Phase::Cancelled:Phase::Failed;
}
void Restore::step() {
  switch(m_phase) {
  case Phase::Authenticate:
    if(!m_hooks.authenticate(m_hooks.context,m_header,m_pair,m_pairNumber,m_package)) { fail(Error::Authority);break; }
    m_phase=m_pairNumber?Phase::WritePackage:Phase::Directory;break;
  case Phase::Directory: {
    int rc=lfs_mkdir(m_fs,"objects");m_objectsCreated=!rc;
    if(rc && rc!=LFS_ERR_EXIST) fail(Error::IO);else m_phase=Phase::AppDirectory;break;
  }
  case Phase::AppDirectory: {
    char path[64];memcpy(path,"objects/",8);memcpy(path+8,m_id,strlen(m_id)+1);
    int rc=lfs_mkdir(m_fs,path);m_directoryCreated=!rc;
    if(rc && rc!=LFS_ERR_EXIST) fail(Error::IO);else m_phase=Phase::OldCurrent;break;
  }
  case Phase::OldCurrent:
    if(!m_before.serial || !m_documents->index(m_id,m_before.current,&m_old[0])) m_old[0].clear();
    m_phase=Phase::OldPrevious;break;
  case Phase::OldPrevious:
    if(!m_before.previous.data || !m_documents->index(m_id,m_before.previous,&m_old[1])) m_old[1].clear();
    m_phase=Phase::WritePackage;break;
  case Phase::WritePackage:
    if(stage('p',m_package,m_pair.packageBytes)) { index().entry[0].bytes=m_pair.privateBytes;content(); }break;
  case Phase::FindReuse:findReuse();break;
  case Phase::CheckReuse:checkReuse();break;
  case Phase::WriteChunk:
    if(stage('c',m_chunk,m_chunkFill,m_parts[m_pairNumber]+(m_open?0:1))) {
      AppFileIndex::Extent x;x.type=AppFileIndex::ChunkObject;x.generation=generation();x.part=m_parts[m_pairNumber];
      x.bytes=m_chunkFill;memcpy(x.hash,m_chunkHash,32);chunkDone(x);
    }
    break;
  case Phase::WriteIndex:
    if(stage('d',m_indexWire,pair().dataBytes)) {
      if(++m_pairNumber<m_header.pairs) frame(Phase::Pair);
      else {
        NativeAppHash::shaFinal(&m_whole,m_digest);
        if(m_received!=m_total) fail(Error::Format);
        else if(memcmp(m_digest,m_expected,32)) fail(Error::Integrity);else m_phase=Phase::Ready;
      }
    }
    break;
  case Phase::Publish: {
    using S=AppDocumentStore::Store::State;
    if(m_documents->state()==S::Committing) {
      m_commitAttempted=true;
    }
    m_documents->step();
    if(m_documents->state()==S::Complete) m_phase=Phase::Done;
    else if(m_documents->state()==S::Failed) fail(Error::IO);
    break;
  }
  case Phase::Cleanup:cleanup();break;
  default:break;
  }
  if(m_received==m_total && state()==State::Receiving) fail(Error::Format);
}
}}

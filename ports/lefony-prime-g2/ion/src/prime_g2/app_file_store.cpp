// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_file_store.h"
#include <string.h>
namespace PrimeG2 { namespace AppFileStore {
using namespace AppFileIndex;
int ReadCache::find(const Reader *owner,uint32_t chunk) {
  for(unsigned i=0;i<Slots;i++) {
    auto &entry=m_entries[i];
    if(entry.owner==owner && entry.chunk==chunk && entry.verified) {
      entry.used=++m_serial;return i;
    }
  }
  return -1;
}
int ReadCache::reserve(const Reader *owner,uint32_t chunk) {
  int oldest=-1;
  for(unsigned i=0;i<Slots;i++) {
    auto &entry=m_entries[i];
    if(!entry.owner) { oldest=i;break; }
    // Partially read chunks are pinned until their owner publishes or closes.
    if(entry.verified && (oldest<0 || entry.used<m_entries[oldest].used)) oldest=i;
  }
  if(oldest<0) return -1;
  auto &entry=m_entries[oldest];entry.owner=owner;entry.chunk=chunk;
  entry.verified=false;entry.used=++m_serial;return oldest;
}
void ReadCache::publish(unsigned slot) { m_entries[slot].verified=true; }
void ReadCache::release(const Reader *owner) {
  for(auto &entry:m_entries) if(entry.owner==owner) {entry.owner=nullptr;entry.verified=false;}
}
bool Reader::open(lfs_t *fs,AppDocumentStore::Store *documents,const char *id,const char *name,
                  const AppDocumentRoot::Root &root) {
  if(m_state!=State::Closed || !fs || !documents ||
     !documents->snapshot(id,root.current,name,m_extents,&m_count,&m_bytes)) return false;
  // snapshot validates the namespace before it is copied here.
  m_fs=fs;memcpy(m_id,id,strlen(id)+1);m_config.buffer=m_cache;
  m_position=m_cursor=0;m_chunk=MaximumExtents;m_state=State::Ready;return true;
}
bool Reader::closeObject() {
  if(!m_open) return true;
  int result=lfs_file_close(m_fs,&m_file);m_open=false;return result==0;
}
void Reader::fail() {
  closeObject();if(m_contentCache) m_contentCache->release(this);
  m_cacheSlot=-1;m_state=State::Failed;
}
bool Reader::close() {
  if(m_contentCache) m_contentCache->release(this);
  m_cacheSlot=-1;
  bool ok=closeObject();m_state=State::Closed;m_count=m_bytes=m_position=m_cursor=0;
  m_id[0]=0;m_chunk=MaximumExtents;return ok;
}
bool Reader::belongsTo(const char *id) const {
  return m_state!=State::Closed && id && !strcmp(id,m_id);
}
bool Reader::retains(const char *id,uint32_t generation,uint32_t part) const {
  if(!belongsTo(id)) return false;
  for(uint32_t i=0;i<m_count;i++)
    if(m_extents[i].generation==generation && m_extents[i].part==part) return true;
  return false;
}
int Reader::readCached(void *out,uint32_t bytes) {
  if(m_state==State::Closed || m_state==State::Failed || bytes>sizeof(m_scratch) || (!out && bytes)) return -1;
  if(!bytes) return 0;
  if(m_state==State::Verifying) return Pending;
  if(m_position>=m_bytes) return 0;
  if(!m_contentCache) return Pending;
  uint32_t chunk=m_position/ChunkBytes,offset=m_position%ChunkBytes;
  if(chunk>=m_count) return -1;
  int slot=m_contentCache->find(this,chunk);
  if(slot<0) return Pending;
  if(bytes>m_extents[chunk].bytes-offset) bytes=m_extents[chunk].bytes-offset;
  memcpy(out,m_contentCache->bytes(slot)+offset,bytes);m_position+=bytes;return bytes;
}
int Reader::read(void *out,uint32_t bytes) {
  int cached=readCached(out,bytes);
  if(cached!=Pending || m_state==State::Verifying) return cached;
  uint32_t chunk=m_position/ChunkBytes,offset=m_position%ChunkBytes;
  if(chunk>=m_count) { fail();return -1; }
  const Extent &extent=m_extents[chunk];
  if(m_chunk!=chunk || m_contentCache) {
    if(!closeObject()) { fail();return -1; }
    char path[80];size_t n=strlen(m_id);
    memcpy(path,"objects/",8);memcpy(path+8,m_id,n);path[8+n]='/';objectName(extent,path+9+n);
    if(lfs_file_opencfg(m_fs,&m_file,path,LFS_O_RDONLY,&m_config)<0) { fail();return -1; }
    m_open=true;
    if(lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(extent.bytes)) { fail();return -1; }
    if(m_contentCache) {
      m_cacheSlot=m_contentCache->reserve(this,chunk);
      if(m_cacheSlot<0) {fail();return -1;}
    }
    m_chunk=chunk;m_cursor=0;NativeAppHash::shaInit(&m_hash);m_state=State::Verifying;return Pending;
  }
  if(bytes>extent.bytes-offset) bytes=extent.bytes-offset;
  // Copy to the caller only after both verification and this read succeed.
  if(lfs_file_seek(m_fs,&m_file,offset,LFS_SEEK_SET)!=static_cast<lfs_soff_t>(offset) ||
     lfs_file_read(m_fs,&m_file,m_scratch,bytes)!=static_cast<lfs_ssize_t>(bytes)) { fail();return -1; }
  memcpy(out,m_scratch,bytes);m_position+=bytes;return bytes;
}
void Reader::step() {
  if(m_state!=State::Verifying) return;
  const Extent &extent=m_extents[m_chunk];
  if(m_cursor<extent.bytes) {
    uint32_t n=extent.bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();return; }
    if(m_contentCache) memcpy(m_contentCache->bytes(m_cacheSlot)+m_cursor,m_scratch,n);
    NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
  } else {
    uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
    if(memcmp(hash,extent.hash,32)) {fail();return;}
    if(m_contentCache) {
      if(!closeObject()) {fail();return;}
      m_contentCache->publish(m_cacheSlot);m_cacheSlot=-1;
    }
    m_state=State::Ready;
  }
}
bool Reader::seek(uint32_t offset) {
  if(m_state!=State::Ready || offset>64*1024*1024) return false;
  m_position=offset;return true;
}
Store::Store(lfs_t *fs,AppDocumentStore::Store *documents):m_fs(fs),m_documents(documents) {
  m_config.buffer=m_cache;m_inputConfig.buffer=m_inputCache;
}
Store::State Store::state() const {
  switch(m_phase) {
  case Phase::Idle:return State::Idle;
  case Phase::Preparing:return State::Preparing;
  case Phase::Writable:return State::Writable;
  case Phase::Reading:return State::Reading;
  case Phase::Commit:return State::Committing;
  case Phase::Done:return State::Complete;
  case Phase::Failed:return State::Failed;
  default:return State::Working;
  }
}
void Store::path(const Extent &extent,char out[80]) const {
  size_t n=strlen(m_directory);memcpy(out,m_directory,n);out[n++]='/';objectName(extent,out+n);
}
bool Store::open(const Extent &extent,int flags) {
  char file[80];path(extent,file);
  if(m_open || lfs_file_opencfg(m_fs,&m_file,file,flags,&m_config)<0) return false;
  m_open=true;return true;
}
bool Store::close() {
  bool ok=true;
  if(m_open) { ok=lfs_file_close(m_fs,&m_file)==0;m_open=false; }
  if(m_inputOpen) { ok=(lfs_file_close(m_fs,&m_input)==0)&&ok;m_inputOpen=false; }
  return ok;
}
void Store::fail(int error) { close();m_error=error;m_phase=Phase::Failed; }
bool Store::setup(const char *id,const Root &before,const Root &after) {
  if(m_phase!=Phase::Idle && m_phase!=Phase::Done && m_phase!=Phase::Failed) return false;
  // The document reader validates the app ID before any path is constructed.
  if(!m_documents->index(id,before.current,&m_index)) return false;
  m_usage=0;for(uint32_t i=0;i<m_index.entries;i++) m_usage+=m_index.entry[i].bytes;
  // Existing oversized roots stay readable, editable and shrinkable. Each
  // subsequent committed root becomes the ceiling for another transaction.
  m_quotaCeiling=m_usage>QuotaBytes?m_usage:QuotaBytes;
  memcpy(m_id,id,strlen(id)+1);memcpy(m_directory,"objects/",8);memcpy(m_directory+8,id,strlen(id)+1);
  m_before=before;m_after=after;m_after.format=4;m_after.current.dataKind=AppDocumentRoot::FileIndex;
  m_after.current.data=m_after.serial;m_written=m_cursor=m_part=m_objectWrites=0;
  m_feed=m_metadata=m_stream=m_streamDirty=m_append=false;m_automatic=nullptr;
  m_error=0;m_streamLoaded=MaximumExtents;return true;
}
bool Store::resize(unsigned target,uint32_t bytes) {
  Entry &entry=m_index.entry[target];uint32_t count=(bytes+ChunkBytes-1)/ChunkBytes;
  if(count>MaximumExtents-(m_index.extents-entry.count)) { m_error=LFS_ERR_FBIG;return false; }
  if(bytes>quotaLimit(target)) { m_error=QuotaExceeded;return false; }
  uint32_t first=entry.first,old=entry.count,tail=m_index.extents-first-old;
  memmove(m_index.extent+first+count,m_index.extent+first+old,tail*sizeof(Extent));
  for(uint32_t i=0;i<count;i++) m_index.extent[first+i]={};
  for(uint32_t i=target+1;i<m_index.entries;i++) m_index.entry[i].first=m_index.entry[i].first-old+count;
  m_usage=m_usage-entry.bytes+bytes;
  m_index.extents=m_index.extents-old+count;entry.bytes=bytes;entry.count=count;return true;
}
bool Store::begin(const char *id,const char *name,uint32_t bytes,const Root &before,const Root &after,
                  bool patch,uint32_t offset,const uint8_t *automatic,bool feed) {
  if(bytes>64*1024*1024 || (name && !AppFileIndex::path(name)) || (!name && (bytes>65536 || patch)) ||
     (feed && bytes && !automatic) || !setup(id,before,after)) return false;
  int target=name?m_index.find(name):0;
  if(patch) {
    if(target<1 || m_index.entry[target].kind!=File || offset>m_index.entry[target].bytes ||
       bytes>m_index.entry[target].bytes-offset) return false;
  } else {
    if(target<0) {
      if(m_index.entries==MaximumEntries || !parent(m_index,name)) return false;
      target=m_index.entries++;m_index.entry[target]={};memcpy(m_index.entry[target].name,name,strlen(name)+1);
      m_index.entry[target].kind=File;m_index.entry[target].first=m_index.extents;
    }
    if(m_index.entry[target].kind==Directory || !resize(target,bytes)) return false;
  }
  m_target=target;m_expected=bytes;m_patch=patch;m_offset=patch?offset:0;m_chunk=m_offset/ChunkBytes;
  m_automatic=automatic;m_feed=feed;
  if(!m_documents->collect(id,before)) return false;
  m_phase=Phase::Preparing;return true;
}
bool Store::beginStream(const char *id,const char *name,StreamMode mode,const Root &before,const Root &after) {
  if(!AppFileIndex::path(name) || (mode!=StreamMode::Truncate && mode!=StreamMode::Update && mode!=StreamMode::Append) ||
     !before.serial || before.serial==0xffffffffu || after.serial!=before.serial+1) { m_error=LFS_ERR_INVAL;return false; }
  if(!setup(id,before,after)) return false;
  int target=m_index.find(name);
  if(target<0) {
    if(mode==StreamMode::Update) { m_error=LFS_ERR_NOENT;return false; }
    if(m_index.entries==MaximumEntries) { m_error=LFS_ERR_NOSPC;return false; }
    if(!parent(m_index,name)) { m_error=LFS_ERR_NOENT;return false; }
    target=m_index.entries++;auto &entry=m_index.entry[target];entry={};
    memcpy(entry.name,name,strlen(name)+1);entry.kind=File;entry.first=m_index.extents;
  }
  if(m_index.entry[target].kind!=File) { m_error=LFS_ERR_ISDIR;return false; }
  if(mode==StreamMode::Truncate && !resize(target,0)) return false;
  m_target=target;m_append=mode==StreamMode::Append;m_position=m_append?m_index.entry[target].bytes:0;
  m_stream=true;
  if(!m_documents->collect(id,before)) { m_error=LFS_ERR_IO;return false; }
  m_phase=Phase::Preparing;return true;
}
uint32_t Store::streamLimit() const {
  uint32_t chunks=MaximumExtents-(m_index.extents-m_index.entry[m_target].count);
  uint32_t bytes=chunks*ChunkBytes;return bytes<64*1024*1024?bytes:64*1024*1024;
}
bool Store::extend(uint32_t bytes) {
  auto &entry=m_index.entry[m_target];
  if(bytes<=entry.bytes) return true;
  if(bytes>streamLimit()) { m_error=LFS_ERR_FBIG;return false; }
  if(bytes>quotaLimit(m_target)) { m_error=QuotaExceeded;return false; }
  uint32_t count=(bytes+ChunkBytes-1)/ChunkBytes,added=count-entry.count,tail=entry.first+entry.count;
  if(added) {
    memmove(m_index.extent+tail+added,m_index.extent+tail,(m_index.extents-tail)*sizeof(Extent));
    for(uint32_t i=0;i<added;i++) m_index.extent[tail+i]={};
    for(uint32_t i=m_target+1;i<m_index.entries;i++) m_index.entry[i].first+=added;
    m_index.extents+=added;entry.count=count;
  }
  m_usage+=bytes-entry.bytes;entry.bytes=bytes;return true;
}
void Store::requestChunk(uint32_t chunk,Phase afterLoad) {
  m_streamRequested=chunk;m_afterLoad=afterLoad;m_afterFlush=Phase::StreamLoad;
  m_phase=m_streamDirty?Phase::StreamFlush:Phase::StreamLoad;
}
int Store::writeStream(const void *bytes,uint32_t count) {
  if(m_phase==Phase::Failed) return -1;
  if(count>sizeof(m_scratch) || (count && !bytes)) { m_error=LFS_ERR_INVAL;return -1; }
  if(m_phase!=Phase::Writable) {
    return m_phase==Phase::Preparing || m_phase==Phase::PrepareChunk || m_phase==Phase::StreamLoad ||
      m_phase==Phase::StreamLoading || m_phase==Phase::StreamGap ||
      (m_afterFlush==Phase::StreamLoad && (m_phase==Phase::StreamFlush || m_phase==Phase::StreamWriting || m_phase==Phase::StreamVerify))?Pending:-1;
  }
  if(!count) return 0;
  if(m_append) m_position=m_index.entry[m_target].bytes;
  if(m_position>=streamLimit()) { m_error=LFS_ERR_FBIG;return -1; }
  uint32_t quota=quotaLimit(m_target);
  if(m_position>=quota) { m_error=QuotaExceeded;return -1; }
  if(m_position>m_index.entry[m_target].bytes) { m_gapEnd=m_position;m_phase=Phase::StreamGap;return Pending; }
  uint32_t chunk=m_position/ChunkBytes,offset=m_position%ChunkBytes;
  if(m_streamLoaded!=chunk) { requestChunk(chunk,Phase::Writable);return Pending; }
  if(count>ChunkBytes-offset) count=ChunkBytes-offset;
  if(count>streamLimit()-m_position) count=streamLimit()-m_position;
  if(count>quota-m_position) count=quota-m_position;
  if(!extend(m_position+count)) return -1;
  memcpy(m_buffer+offset,bytes,count);m_streamDirty=true;m_position+=count;m_error=0;return count;
}
int Store::readStream(void *out,uint32_t count) {
  if(m_phase==Phase::Failed) return -1;
  if(count>sizeof(m_scratch) || (count && !out)) { m_error=LFS_ERR_INVAL;return -1; }
  if(m_phase!=Phase::Writable) return m_phase==Phase::StreamLoad || m_phase==Phase::StreamLoading ||
    (m_afterFlush==Phase::StreamLoad && (m_phase==Phase::StreamFlush || m_phase==Phase::StreamWriting || m_phase==Phase::StreamVerify))?Pending:-1;
  if(!count || m_position>=m_index.entry[m_target].bytes) return 0;
  uint32_t chunk=m_position/ChunkBytes,offset=m_position%ChunkBytes;
  if(m_streamLoaded!=chunk) { requestChunk(chunk,Phase::Writable);return Pending; }
  if(count>m_index.entry[m_target].bytes-m_position) count=m_index.entry[m_target].bytes-m_position;
  if(count>ChunkBytes-offset) count=ChunkBytes-offset;
  memcpy(out,m_buffer+offset,count);m_position+=count;m_error=0;return count;
}
void Store::stepStream() {
  switch(m_phase) {
  case Phase::StreamLoad: {
    m_old={};auto &entry=m_index.entry[m_target];
    if(m_streamRequested<entry.count) m_old=m_index.extent[entry.first+m_streamRequested];
    if(m_old.generation) {
      if(!open(m_old,LFS_O_RDONLY)) { fail();break; }
      if(lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(m_old.bytes)) { fail(LFS_ERR_CORRUPT);break; }
    }
    m_cursor=0;NativeAppHash::shaInit(&m_hash);m_phase=Phase::StreamLoading;break;
  }
  case Phase::StreamLoading: {
    if(m_cursor<ChunkBytes) {
      uint32_t end=m_cursor<m_old.bytes?m_old.bytes:ChunkBytes,n=end-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      if(m_cursor<m_old.bytes) {
        int rc=lfs_file_read(m_fs,&m_file,m_buffer+m_cursor,n);
        if(rc!=static_cast<int>(n)) { fail(rc<0?rc:LFS_ERR_IO);break; }
        NativeAppHash::shaUpdate(&m_hash,m_buffer+m_cursor,n);
      } else memset(m_buffer+m_cursor,0,n);
      m_cursor+=n;
    } else {
      uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
      if(!close() || (m_old.generation && memcmp(hash,m_old.hash,32))) { fail(LFS_ERR_CORRUPT);break; }
      m_streamLoaded=m_streamRequested;m_streamDirty=false;m_phase=m_afterLoad;
    }
    break;
  }
  case Phase::StreamGap: {
    uint32_t end=m_index.entry[m_target].bytes;
    if(end==m_gapEnd) { m_phase=Phase::Writable;break; }
    uint32_t chunk=end/ChunkBytes,offset=end%ChunkBytes;
    if(m_streamLoaded!=chunk) { requestChunk(chunk,Phase::StreamGap);break; }
    uint32_t n=m_gapEnd-end;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);if(n>ChunkBytes-offset) n=ChunkBytes-offset;
    if(!extend(end+n)) { fail(m_error);break; }
    memset(m_buffer+offset,0,n);m_streamDirty=true;break;
  }
  case Phase::StreamFlush: {
    const auto &entry=m_index.entry[m_target];
    if(!m_streamDirty || m_streamLoaded>=entry.count) { fail(LFS_ERR_INVAL);break; }
    m_new={};m_new.type=ChunkObject;m_new.generation=m_after.serial;m_new.part=m_streamLoaded+1;
    m_new.bytes=entry.bytes-m_streamLoaded*ChunkBytes;if(m_new.bytes>ChunkBytes) m_new.bytes=ChunkBytes;
    if(m_chunkAdmission && !m_chunkAdmission(m_admissionContext,m_new.bytes)) { fail(LFS_ERR_NOSPC);break; }
    // Only this uncommitted generation can be rewritten. No root or snapshot
    // can reference it until the final index/root transaction has completed.
    bool staged= m_index.extent[entry.first+m_streamLoaded].generation==m_after.serial;
    char file[80];path(m_new,file);
    int rc=lfs_file_opencfg(m_fs,&m_file,file,LFS_O_WRONLY|LFS_O_CREAT|(staged?LFS_O_TRUNC:LFS_O_EXCL),&m_config);
    if(rc<0) { fail(rc);break; }
    m_open=true;m_cursor=0;NativeAppHash::shaInit(&m_hash);m_phase=Phase::StreamWriting;break;
  }
  case Phase::StreamWriting:
    if(m_cursor<m_new.bytes) {
      uint32_t n=m_new.bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      int rc=lfs_file_write(m_fs,&m_file,m_buffer+m_cursor,n);
      if(rc!=static_cast<int>(n)) { fail(rc<0?rc:LFS_ERR_IO);break; }
      NativeAppHash::shaUpdate(&m_hash,m_buffer+m_cursor,n);m_cursor+=n;m_objectWrites+=n;
    } else {
      NativeAppHash::shaFinal(&m_hash,m_new.hash);
      if(!close() || !open(m_new,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(m_new.bytes)) { fail();break; }
      m_cursor=0;NativeAppHash::shaInit(&m_hash);m_phase=Phase::StreamVerify;
    }
    break;
  case Phase::StreamVerify:
    if(m_cursor<m_new.bytes) {
      uint32_t n=m_new.bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      int rc=lfs_file_read(m_fs,&m_file,m_scratch,n);
      if(rc!=static_cast<int>(n)) { fail(rc<0?rc:LFS_ERR_IO);break; }
      NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
    } else {
      uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
      if(!close() || memcmp(hash,m_new.hash,32)) { fail(LFS_ERR_CORRUPT);break; }
      m_index.extent[m_index.entry[m_target].first+m_streamLoaded]=m_new;
      m_streamDirty=false;m_phase=m_afterFlush;
    }
    break;
  case Phase::StreamCommit:publishIndex();break;
  default:break;
  }
}
bool Store::mutate(const char *id,const char *name,const char *destination,bool directory,
                   const Root &before,const Root &after) {
  if(!AppFileIndex::path(name) || (destination && !AppFileIndex::path(destination))) { m_error=LFS_ERR_INVAL;return false; }
  if(!setup(id,before,after)) { m_error=LFS_ERR_IO;return false; }
  int target=m_index.find(name);
  if(directory) {
    if(target>=0) { m_error=LFS_ERR_EXIST;return false; }
    if(m_index.entries==MaximumEntries) { m_error=LFS_ERR_NOSPC;return false; }
    if(!parent(m_index,name)) { m_error=LFS_ERR_NOENT;return false; }
    Entry &entry=m_index.entry[m_index.entries++];entry={};memcpy(entry.name,name,strlen(name)+1);
    entry.kind=Directory;entry.first=m_index.extents;
  } else if(destination) {
    if(target<1 || !parent(m_index,destination)) { m_error=LFS_ERR_NOENT;return false; }
    size_t length=strlen(name),next=strlen(destination);
    if(!strncmp(destination,name,length) && destination[length]=='/') { m_error=LFS_ERR_INVAL;return false; }
    int replaced=m_index.find(destination);
    if(replaced>=1 && replaced!=target) {
      if(m_index.entry[target].kind!=m_index.entry[replaced].kind) { m_error=LFS_ERR_ISDIR;return false; }
      for(uint32_t i=1;i<m_index.entries;i++) if(!strncmp(m_index.entry[i].name,destination,next) &&
         m_index.entry[i].name[next]=='/') { m_error=LFS_ERR_NOTEMPTY;return false; }
      if(!resize(replaced,0)) { m_error=LFS_ERR_INVAL;return false; }
      memmove(m_index.entry+replaced,m_index.entry+replaced+1,(m_index.entries-replaced-1)*sizeof(Entry));
      m_index.entries--;target=m_index.find(name);
    }
    for(uint32_t i=1;i<m_index.entries;i++) {
      char *path=m_index.entry[i].name;
      if(strcmp(path,name) && (strncmp(path,name,length) || path[length]!='/')) continue;
      size_t suffix=strlen(path+length);if(next+suffix>=sizeof(m_index.entry[i].name)) { m_error=LFS_ERR_INVAL;return false; }
      memmove(path+next,path+length,suffix+1);memcpy(path,destination,next);
    }
  } else {
    if(target<1) { m_error=LFS_ERR_NOENT;return false; }
    size_t length=strlen(name);
    for(uint32_t i=1;i<m_index.entries;i++) if(!strncmp(m_index.entry[i].name,name,length) &&
      m_index.entry[i].name[length]=='/') { m_error=LFS_ERR_NOTEMPTY;return false; }
    if(!resize(target,0)) return false;
    memmove(m_index.entry+target,m_index.entry+target+1,(m_index.entries-target-1)*sizeof(Entry));m_index.entries--;
  }
  if(!valid(m_index,m_after.serial) || !m_documents->collect(id,before)) return false;
  m_metadata=true;m_phase=Phase::Preparing;return true;
}
bool Store::output(const uint8_t *bytes,uint32_t count) {
  if(lfs_file_write(m_fs,&m_file,bytes,count)!=static_cast<lfs_ssize_t>(count)) return false;
  NativeAppHash::shaUpdate(&m_hash,bytes,count);m_cursor+=count;m_objectWrites+=count;return true;
}
bool Store::input(uint32_t offset,uint8_t *bytes,uint32_t count) {
  return m_inputOpen && lfs_file_seek(m_fs,&m_input,offset,LFS_SEEK_SET)==static_cast<lfs_soff_t>(offset) &&
    lfs_file_read(m_fs,&m_input,bytes,count)==static_cast<lfs_ssize_t>(count);
}
void Store::prepareChunk() {
  if(m_stream) { m_phase=Phase::Writable;return; }
  if(m_metadata) { m_written=m_expected=0;m_phase=Phase::Writable;if(!commit()) fail();return; }
  if(m_written==m_expected) { m_phase=Phase::Writable;return; }
  const Entry &entry=m_index.entry[m_target];uint32_t start=m_chunk*ChunkBytes;
  m_chunkBytes=entry.bytes-start;if(m_chunkBytes>ChunkBytes) m_chunkBytes=ChunkBytes;
  m_payloadStart=m_offset>start?m_offset-start:0;
  m_payloadEnd=m_offset+m_expected-start;if(m_payloadEnd>m_chunkBytes) m_payloadEnd=m_chunkBytes;
  m_new={};m_new.type=ChunkObject;m_new.generation=m_after.serial;m_new.part=++m_part;m_new.bytes=m_chunkBytes;
  if(m_part>MaximumExtents || !open(m_new,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_EXCL)) { fail();return; }
  if(m_patch && (m_payloadStart || m_payloadEnd<m_chunkBytes)) {
    m_old=m_index.extent[entry.first+m_chunk];char file[80];path(m_old,file);
    if(lfs_file_opencfg(m_fs,&m_input,file,LFS_O_RDONLY,&m_inputConfig)<0) { fail();return; }
    m_inputOpen=true;
    if(lfs_file_size(m_fs,&m_input)!=static_cast<lfs_soff_t>(m_old.bytes)) { fail();return; }
  }
  m_cursor=0;NativeAppHash::shaInit(&m_hash);m_phase=Phase::Prefix;
}
void Store::copyBoundary(uint32_t end,Phase next) {
  if(m_cursor==end) { m_phase=next;return; }
  uint32_t count=end-m_cursor;if(count>sizeof(m_scratch)) count=sizeof(m_scratch);
  if(!input(m_cursor,m_scratch,count) || !output(m_scratch,count)) fail();
}
int Store::write(const void *bytes,uint32_t count) {
  if(m_stream) return writeStream(bytes,count);
  if(m_phase!=Phase::Writable || !m_open || !bytes || count>sizeof(m_scratch)) return -1;
  uint32_t remaining=m_payloadEnd-m_cursor;if(count>remaining) count=remaining;
  if(!count) return 0;
  if(!output(static_cast<const uint8_t *>(bytes),count)) { fail();return -1; }
  m_written+=count;if(m_cursor==m_payloadEnd) m_phase=Phase::Suffix;return count;
}
bool Store::commit() {
  if(m_phase!=Phase::Writable || m_open) return false;
  if(m_stream) {
    m_afterFlush=Phase::StreamCommit;m_phase=m_streamDirty?Phase::StreamFlush:Phase::StreamCommit;return true;
  }
  if(m_written!=m_expected) return false;
  return publishIndex();
}
bool Store::publishIndex() {
  if(m_stream && m_chunkAdmission && !m_chunkAdmission(m_admissionContext,0)) { fail(LFS_ERR_NOSPC);return false; }
  if(!encode(m_index,m_after.serial,m_buffer,AppFileIndex::MaximumBytes)) { fail(LFS_ERR_INVAL);return false; }
  m_after.current.dataBytes=encodedBytes(m_index);
  if(!m_documents->begin(m_id,m_before,m_after,nullptr,m_buffer,true,false)) { fail();return false; }
  m_phase=Phase::Commit;return true;
}
void Store::step() {
  using D=AppDocumentStore::Store::State;
  if(m_stream && m_phase>=Phase::StreamLoad && m_phase<=Phase::StreamCommit) { stepStream();return; }
  switch(m_phase) {
  case Phase::Preparing:
    m_documents->step();
    if(m_documents->state()==D::Failed) fail();
    else if(m_documents->state()==D::Complete) m_phase=Phase::PrepareChunk;
    break;
  case Phase::PrepareChunk:prepareChunk();break;
  case Phase::Prefix:copyBoundary(m_payloadStart,Phase::Writable);break;
  case Phase::Writable:
    if(m_feed) {
      if(m_written==m_expected) { if(!commit()) fail(); }
      else { uint32_t n=m_expected-m_written;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);write(m_automatic+m_written,n); }
    }
    break;
  case Phase::Suffix:
    if(m_cursor<m_chunkBytes) copyBoundary(m_chunkBytes,Phase::Suffix);
    else {
      NativeAppHash::shaFinal(&m_hash,m_new.hash);
      if(!close() || !open(m_new,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(m_new.bytes)) { fail();break; }
      m_cursor=0;NativeAppHash::shaInit(&m_hash);m_phase=Phase::Verify;
    }
    break;
  case Phase::Verify:
    if(m_cursor<m_chunkBytes) {
      uint32_t n=m_chunkBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();break; }
      NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
    } else {
      uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
      if(!close() || memcmp(hash,m_new.hash,32)) { fail();break; }
      m_index.extent[m_index.entry[m_target].first+m_chunk]=m_new;m_chunk++;m_phase=Phase::PrepareChunk;
    }
    break;
  case Phase::Commit:
    m_documents->step();
    if(m_documents->state()==D::Failed) fail();else if(m_documents->state()==D::Complete) m_phase=Phase::Done;
    break;
  default:break;
  }
}
void Store::cancel() {
  if(m_phase==Phase::Idle || m_phase==Phase::Done) return;
  if(m_phase==Phase::Preparing || m_phase==Phase::Commit) {
    m_documents->cancel();
    if(m_documents->state()==AppDocumentStore::Store::State::Committing) return;
    if(m_documents->state()==AppDocumentStore::Store::State::Failed) { fail();return; }
  }
  if(!close()) fail();else m_phase=Phase::Idle;
}
bool Store::openRead(const char *id,const char *name,const Root &root) {
  if(!AppFileIndex::path(name) || !setup(id,root,root)) return false;
  int target=m_index.find(name);if(target<1 || m_index.entry[target].kind!=File) return false;
  m_target=target;m_position=0;m_readExtent=MaximumExtents;m_phase=Phase::Reading;return true;
}
bool Store::verifyRead(const Extent &extent) {
  if(!close() || !open(extent,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(extent.bytes)) return false;
  NativeAppHash::shaInit(&m_hash);
  for(uint32_t cursor=0;cursor<extent.bytes;) {
    uint32_t n=extent.bytes-cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) return false;
    NativeAppHash::shaUpdate(&m_hash,m_scratch,n);cursor+=n;
  }
  uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);return !memcmp(hash,extent.hash,32);
}
int Store::read(void *out,uint32_t bytes) {
  if(m_stream) return readStream(out,bytes);
  if(m_phase!=Phase::Reading || !out || bytes>sizeof(m_scratch)) return -1;
  const Entry &entry=m_index.entry[m_target];
  if(m_position>=entry.bytes || !bytes) return 0;
  uint32_t chunk=m_position/ChunkBytes,offset=m_position%ChunkBytes;
  const Extent &extent=m_index.extent[entry.first+chunk];
  if(m_readExtent!=chunk) {
    if(!verifyRead(extent)) { fail();return -1; }m_readExtent=chunk;
  }
  if(bytes>extent.bytes-offset) bytes=extent.bytes-offset;
  if(lfs_file_seek(m_fs,&m_file,offset,LFS_SEEK_SET)!=static_cast<lfs_soff_t>(offset) ||
     lfs_file_read(m_fs,&m_file,out,bytes)!=static_cast<lfs_ssize_t>(bytes)) { fail();return -1; }
  m_position+=bytes;return bytes;
}
bool Store::seek(uint32_t offset) {
  if((m_stream?m_phase!=Phase::Writable:m_phase!=Phase::Reading) || offset>64*1024*1024) return false;
  m_position=offset;return true;
}
bool Store::closeRead() {
  if(m_phase!=Phase::Reading) return false;
  if(!close()) { fail();return false; }m_phase=Phase::Idle;return true;
}
}}

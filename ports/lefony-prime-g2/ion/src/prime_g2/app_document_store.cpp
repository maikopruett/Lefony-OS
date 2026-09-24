// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_document_store.h"
#include "app_root_record.h"
#include <string.h>
namespace PrimeG2 { namespace AppDocumentStore {
namespace { const char *Pending="apps/.pending"; }
Store::Store(lfs_t *fs):m_fs(fs) { m_fileConfig.buffer=m_cache;m_inputConfig.buffer=m_inputCache; }
bool Store::name(const char *id) {
  if(!id || id[0]<'a' || id[0]>'z') return false;
  unsigned n=0;
  while(n<49 && id[n]) {
    char c=id[n];if(!((c>='a' && c<='z') || (n && ((c>='0' && c<='9') || c=='-')))) return false;
    n++;
  }
  if(n>48) return false;
  memcpy(m_id,id,n+1);memcpy(m_path,"apps/",5);memcpy(m_path+5,id,n);memcpy(m_path+5+n,".app",5);
  memcpy(m_directory,"objects/",8);memcpy(m_directory+8,id,n+1);return true;
}
void Store::object(char type,uint32_t generation,char out[80]) const {
  const char *hex="0123456789abcdef";size_t n=strlen(m_directory);
  memcpy(out,m_directory,n);out[n++]='/';out[n++]=type;
  for(unsigned i=0;i<8;i++) out[n++]=hex[(generation>>(28-4*i))&15];
  out[n]=0;
}
bool Store::open(const char *path,int flags) {
  if(m_open || lfs_file_opencfg(m_fs,&m_file,path,flags,&m_fileConfig)<0) return false;
  m_open=true;m_cursor=0;NativeAppHash::shaInit(&m_hash);return true;
}
bool Store::close() {
  if(!m_open) return true;
  int rc=lfs_file_close(m_fs,&m_file);m_open=false;return rc==0;
}
Store::State Store::state() const {
  if(m_phase==Phase::Idle) return State::Idle;
  if(m_phase==Phase::Done) return State::Complete;
  if(m_phase==Phase::Failed) return State::Failed;
  // Pruning starts only after the canonical root has been removed. It is past
  // the cancellation boundary even while object cleanup is still in progress.
  return m_prune || m_phase==Phase::Commit?State::Committing:State::Busy;
}
void Store::fail() {
  close();
  if(m_inputOpen) { lfs_file_close(m_fs,&m_input);m_inputOpen=false; }
  if(m_dirOpen) { lfs_dir_close(m_fs,&m_dir);m_dirOpen=false; }
  m_phase=Phase::Failed;
}
void Store::cancel() {
  if(state()!=State::Busy) return;
  bool ok=close();
  if(m_inputOpen) { ok=(lfs_file_close(m_fs,&m_input)==0)&&ok;m_inputOpen=false; }
  if(m_dirOpen) { ok=(lfs_dir_close(m_fs,&m_dir)==0)&&ok;m_dirOpen=false; }
  m_phase=ok?Phase::Idle:Phase::Failed;
}
bool Store::root(const char *id,Root *out) {
  if(!out || m_open || state()==State::Busy || state()==State::Committing || !name(id)) return false;
  AppRootRecord::Info value;
  if(AppRootRecord::read(m_fs,m_path,id,m_cache,&value)!=AppRootRecord::Result::Ok)return false;
  *out=value.root;return true;
}
bool Store::readObject(const char *path,uint8_t *out,uint32_t bytes,const uint8_t expected[32]) {
  if((bytes && !out) || !open(path,LFS_O_RDONLY)) return false;
  bool ok=lfs_file_size(m_fs,&m_file)==static_cast<lfs_soff_t>(bytes);
  for(uint32_t cursor=0;ok && cursor<bytes;) {
    uint32_t n=bytes-cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    ok=lfs_file_read(m_fs,&m_file,out+cursor,n)==static_cast<lfs_ssize_t>(n);
    if(ok) NativeAppHash::shaUpdate(&m_hash,out+cursor,n);
    cursor+=n;
  }
  uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);ok=close()&&ok;
  return ok && !memcmp(hash,expected,32);
}
bool Store::read(const char *id,uint8_t *package,size_t capacity,uint8_t *data,size_t dataCapacity) {
  Root r;if(!root(id,&r) || capacity<r.current.packageBytes) return false;
  char path[80];object('p',r.current.package,path);
  if(!readObject(path,package,r.current.packageBytes,r.current.packageHash)) return false;
  if(r.current.dataKind==AppDocumentRoot::FileIndex) {
    if(!index(id,r.current,&m_index) || dataCapacity<m_index.entry[0].bytes) return false;
    if(!m_index.entry[0].bytes) return true;
    const auto &extent=m_index.extent[0];extentPath(extent,path);
    return readObject(path,data,extent.bytes,extent.hash);
  }
  if(dataCapacity<r.current.dataBytes) return false;
  object('d',r.current.data,path);return readObject(path,data,r.current.dataBytes,r.current.dataHash);
}
bool Store::readRecoveryPackage(const char *id,uint8_t *package,size_t capacity) {
  Root r;
  if(!root(id,&r) || !(r.flags&AppDocumentRoot::PendingUpgrade) || capacity<r.previous.packageBytes) return false;
  char path[80];object('p',r.previous.package,path);
  return readObject(path,package,r.previous.packageBytes,r.previous.packageHash);
}
void Store::extentPath(const AppFileIndex::Extent &extent,char out[80]) const {
  size_t n=strlen(m_directory);memcpy(out,m_directory,n);out[n++]='/';AppFileIndex::objectName(extent,out+n);
}
bool Store::index(const char *id,const AppDocumentRoot::Pair &pair,AppFileIndex::Index *out) {
  if(!out || state()==State::Busy || state()==State::Committing || !name(id)) return false;
  if(pair.dataKind==AppDocumentRoot::ByteStore) {
    out->clear();out->entry[0].bytes=pair.dataBytes;
    if(pair.dataBytes) {
      out->extents=1;out->entry[0].count=1;auto &extent=out->extent[0];extent={};
      extent.generation=pair.data;extent.bytes=pair.dataBytes;memcpy(extent.hash,pair.dataHash,32);
    }
    return AppFileIndex::valid(*out,pair.data);
  }
  char file[80];object('d',pair.data,file);
  return pair.dataBytes<=sizeof(m_indexWire) && readObject(file,m_indexWire,pair.dataBytes,pair.dataHash) &&
    AppFileIndex::decode(m_indexWire,pair.dataBytes,pair.data,out);
}
bool Store::privateBytes(const char *id,const AppDocumentRoot::Pair &pair,uint32_t *out) {
  if(!out) return false;
  if(pair.dataKind==AppDocumentRoot::ByteStore) { *out=pair.dataBytes;return true; }
  if(!index(id,pair,&m_index)) return false;
  *out=m_index.entry[0].bytes;return true;
}
bool Store::snapshot(const char *id,const AppDocumentRoot::Pair &pair,const char *file,
                     AppFileIndex::Extent *extents,uint32_t *count,uint32_t *bytes) {
  if(!extents || !count || !bytes || !AppFileIndex::path(file) || !index(id,pair,&m_index)) return false;
  int target=m_index.find(file);
  if(target<1 || m_index.entry[target].kind!=AppFileIndex::File) return false;
  const auto &entry=m_index.entry[target];
  memcpy(extents,m_index.extent+entry.first,entry.count*sizeof(*extents));
  *count=entry.count;*bytes=entry.bytes;return true;
}
int Store::fileInfo(const char *id,const AppDocumentRoot::Pair &pair,const char *file,uint32_t *kind,uint32_t *bytes) {
  if(!kind || !bytes || !AppFileIndex::path(file)) return LFS_ERR_INVAL;
  if(!index(id,pair,&m_index)) return LFS_ERR_IO;
  int target=m_index.find(file);if(target<1) return 0;
  *kind=m_index.entry[target].kind;*bytes=m_index.entry[target].bytes;return 1;
}
bool Store::fileUsage(const char *id,const AppDocumentRoot::Pair &pair,FileUsage *out) {
  if(!out || !index(id,pair,&m_index)) return false;
  FileUsage usage{};usage.privateBytes=m_index.entry[0].bytes;usage.extents=m_index.extents;
  // The validated index has at most 512 non-overlapping extents; their total
  // logical payload fits the reserved 64 MiB region and uint32_t.
  for(uint32_t i=1;i<m_index.entries;i++) {
    const auto &entry=m_index.entry[i];
    if(entry.kind==AppFileIndex::Directory) usage.directories++;
    else { usage.files++;usage.namedBytes+=entry.bytes; }
  }
  *out=usage;return true;
}
int Store::listFiles(const char *id,const AppDocumentRoot::Pair &pair,const char *directory,
                     uint32_t offset,AppFileIndex::Entry *out,uint32_t capacity,uint32_t *next) {
  if(!directory || (*directory && !AppFileIndex::path(directory)) || !out || !capacity || !next) return LFS_ERR_INVAL;
  if(!index(id,pair,&m_index)) return LFS_ERR_IO;
  size_t prefix=strlen(directory);
  if(prefix) {
    int parent=m_index.find(directory);
    if(parent<1) return LFS_ERR_NOENT;
    if(m_index.entry[parent].kind!=AppFileIndex::Directory) return LFS_ERR_NOTDIR;
  }
  if(offset>m_index.entries) return LFS_ERR_INVAL;
  uint32_t count=0,i=offset?offset:1;
  for(;i<m_index.entries && count<capacity;i++) {
    const auto &entry=m_index.entry[i];const char *name=entry.name;
    if(prefix) {
      if(strncmp(name,directory,prefix) || name[prefix]!='/') continue;
      name+=prefix+1;
    }
    if(!strchr(name,'/')) out[count++]=entry;
  }
  *next=i<m_index.entries?i:0;return count;
}
bool Store::references(const AppFileIndex::Index &index) {
  for(uint32_t i=0;i<index.extents;i++) {
    const auto &extent=index.extent[i];bool found=false;
    for(uint32_t j=0;j<m_referenceCount;j++) {
      const auto &old=m_references[j];
      if(old.generation==extent.generation && old.part==extent.part && old.type==extent.type) {
        if(old.bytes!=extent.bytes || memcmp(old.hash,extent.hash,32)) return false;
        found=true;break;
      }
    }
    if(!found) {
      if(m_referenceCount==3*AppFileIndex::MaximumExtents) return false;
      m_references[m_referenceCount++]=extent;
    }
  }
  return true;
}
void Store::checkReference() {
  if(m_referenceCursor==m_referenceCount) { m_phase=m_staged?Phase::RootWrite:Phase::Directory;return; }
  const auto &extent=m_references[m_referenceCursor];
  if(!m_open) {
    char file[80];extentPath(extent,file);
    if(!open(file,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(extent.bytes)) fail();
  } else if(m_cursor<extent.bytes) {
    uint32_t n=extent.bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();return; }
    NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
  } else {
    uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
    if(!close() || memcmp(hash,extent.hash,32)) fail();else m_referenceCursor++;
  }
}
bool Store::begin(const char *id,const Root &before,const Root &after,const uint8_t *package,
                  const uint8_t *data,bool writeData,bool copyLegacy) {
  if(state()==State::Busy || state()==State::Committing || !name(id) ||
     !AppDocumentRoot::valid(after) || (before.serial && !AppDocumentRoot::valid(before)) ||
     (copyLegacy && (before.serial || package)) || (writeData && after.current.dataBytes && !data)) return false;
  m_before=before;m_after=after;m_package=package;m_data=data;m_writeData=writeData;m_copyLegacy=copyLegacy;
  m_prune=false;m_collectOnly=false;m_staged=false;m_referenceCount=m_referenceCursor=0;
  if(writeData && after.current.dataKind==AppDocumentRoot::FileIndex &&
     (!AppFileIndex::decode(data,after.current.dataBytes,after.current.data,&m_index) || !references(m_index))) return false;
  m_packageWrites=m_dataWrites=m_entries=m_cursor=0;
  m_phase=before.serial?Phase::CheckPackage:(copyLegacy?Phase::LegacyCheck:Phase::Directory);return true;
}
bool Store::publishStaged(const char *id,const Root &before,const Root &after) {
  if(!begin(id,before,after,nullptr,nullptr,false,false)) return false;
  m_staged=true;m_phase=Phase::CheckStagedPackage;return true;
}
bool Store::collect(const char *id,const Root &root) {
  if(!begin(id,root,root,nullptr,nullptr,false,false)) return false;
  m_collectOnly=true;return true;
}
bool Store::prune(const char *id) {
  if(state()==State::Busy || state()==State::Committing || !name(id)) return false;
  lfs_info info;if(lfs_stat(m_fs,m_path,&info)!=LFS_ERR_NOENT) return false;
  m_before={};m_after={};m_prune=true;m_staged=false;m_entries=0;m_packageWrites=m_dataWrites=0;m_referenceCount=0;
  int rc=lfs_stat(m_fs,m_directory,&info);
  if(rc==LFS_ERR_NOENT) { m_phase=Phase::Done;return true; }
  if(rc || info.type!=LFS_TYPE_DIR) return false;
  m_phase=Phase::CollectOpen;return true;
}
bool Store::retained(char type,uint32_t generation) const {
  if(type=='d') for(uint32_t i=0;i<m_referenceCount;i++)
    if(m_references[i].type==AppFileIndex::DataObject && m_references[i].generation==generation) return true;
  return type=='p'?(generation==m_before.current.package || generation==m_before.previous.package):
                   (generation==m_before.current.data || generation==m_before.previous.data);
}
void Store::checkObject(char type,const AppDocumentRoot::Pair &pair,Phase next) {
  uint32_t generation=type=='p'?pair.package:pair.data;
  if(!generation) { m_phase=next;return; }
  uint32_t bytes=type=='p'?pair.packageBytes:pair.dataBytes;
  const uint8_t *expected=type=='p'?pair.packageHash:pair.dataHash;
  if(!m_open) {
    if(type=='d' && pair.dataKind==AppDocumentRoot::FileIndex && bytes>sizeof(m_indexWire)) { fail();return; }
    char path[80];object(type,generation,path);
    if(!open(path,LFS_O_RDONLY) || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(bytes)) fail();
  } else if(m_cursor<bytes) {
    uint32_t n=bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();return; }
    if(type=='d' && pair.dataKind==AppDocumentRoot::FileIndex) memcpy(m_indexWire+m_cursor,m_scratch,n);
    NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
  } else {
    uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
    if(!close() || memcmp(hash,expected,32) || (type=='d' && pair.dataKind==AppDocumentRoot::FileIndex &&
       (!AppFileIndex::decode(m_indexWire,bytes,pair.data,&m_index) || !references(m_index)))) fail();else m_phase=next;
  }
}
void Store::writeObject(char type,Phase next) {
  uint32_t bytes=type=='p'?m_after.current.packageBytes:m_after.current.dataBytes;
  const uint8_t *source=type=='p'?m_package:m_data;
  bool copy=type=='p' && m_copyLegacy;
  if(!m_open) {
    char path[80];object(type,type=='p'?m_after.current.package:m_after.current.data,path);
    if(copy) {
      if(lfs_file_opencfg(m_fs,&m_input,m_path,LFS_O_RDONLY,&m_inputConfig)<0) { fail();return; }
      m_inputOpen=true;
      if(lfs_file_seek(m_fs,&m_input,64,LFS_SEEK_SET)!=64) { fail();return; }
    }
    if(!open(path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_EXCL)) fail();
  } else if(m_cursor<bytes) {
    uint32_t n=bytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    if(copy) {
      if(lfs_file_read(m_fs,&m_input,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();return; }
    } else memcpy(m_scratch,source+m_cursor,n);
    if(lfs_file_write(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();return; }
    NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
    if(type=='p') m_packageWrites+=n;else m_dataWrites+=n;
  } else {
    NativeAppHash::shaFinal(&m_hash,type=='p'?m_after.current.packageHash:m_after.current.dataHash);
    bool ok=close();
    if(m_inputOpen) { ok=(lfs_file_close(m_fs,&m_input)==0)&&ok;m_inputOpen=false; }
    if(!ok) fail();else m_phase=next;
  }
}
void Store::step() {
  switch(m_phase) {
  case Phase::LegacyCheck:
    if(!m_open) {
      if(!open(m_path,LFS_O_RDONLY) || lfs_file_read(m_fs,&m_file,m_scratch,64)!=64) { fail();break; }
      using AppDocumentRoot::Detail::get;
      if(memcmp(m_scratch,"LFAFILE2",8) || get(m_scratch+8)!=2 || get(m_scratch+16)!=m_after.current.packageBytes ||
         get(m_scratch+20)>LegacyAppStorage::MaximumData) { fail();break; }
      m_legacyBytes=get(m_scratch+16)+get(m_scratch+20);memcpy(m_legacyHash,m_scratch+24,32);
      if(lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(m_legacyBytes+64)) fail();
    } else if(m_cursor<m_legacyBytes) {
      uint32_t n=m_legacyBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail();break; }
      NativeAppHash::shaUpdate(&m_hash,m_scratch,n);m_cursor+=n;
    } else {
      uint8_t hash[32];NativeAppHash::shaFinal(&m_hash,hash);
      if(!close() || memcmp(hash,m_legacyHash,32)) fail();else m_phase=Phase::Directory;
    }
    break;
  case Phase::CheckPackage:checkObject('p',m_before.current,Phase::CheckData);break;
  case Phase::CheckData:checkObject('d',m_before.current,Phase::CheckPreviousPackage);break;
  case Phase::CheckPreviousPackage:checkObject('p',m_before.previous,Phase::CheckPreviousData);break;
  case Phase::CheckPreviousData:checkObject('d',m_before.previous,Phase::CheckReferences);break;
  case Phase::CheckStagedPackage:checkObject('p',m_after.current,Phase::CheckStagedData);break;
  case Phase::CheckStagedData:checkObject('d',m_after.current,Phase::CheckStagedPreviousPackage);break;
  case Phase::CheckStagedPreviousPackage:checkObject('p',m_after.previous,Phase::CheckStagedPreviousData);break;
  case Phase::CheckStagedPreviousData:checkObject('d',m_after.previous,Phase::CheckReferences);break;
  case Phase::CheckReferences:checkReference();break;
  case Phase::Directory: {
    int rc=lfs_mkdir(m_fs,"objects");if(rc && rc!=LFS_ERR_EXIST) fail();else m_phase=Phase::AppDirectory;break;
  }
  case Phase::AppDirectory: {
    int rc=lfs_mkdir(m_fs,m_directory);if(rc && rc!=LFS_ERR_EXIST) fail();else m_phase=Phase::CollectOpen;break;
  }
  case Phase::CollectOpen:
    if(lfs_dir_open(m_fs,&m_dir,m_directory)<0) fail();else { m_dirOpen=true;m_phase=Phase::Collect; }break;
  case Phase::Collect: {
    lfs_info info;int rc=lfs_dir_read(m_fs,&m_dir,&info);
    if(rc<0 || ++m_entries>8192) { fail();break; }
    if(!rc) {
      rc=lfs_dir_close(m_fs,&m_dir);m_dirOpen=false;
      if(rc) fail();else m_phase=m_prune?Phase::RemoveDirectory:m_collectOnly?Phase::Done:
        (m_package || m_copyLegacy)?Phase::Package:(m_writeData?Phase::Data:Phase::RootWrite);
      break;
    }
    if(!strcmp(info.name,".") || !strcmp(info.name,"..")) break;
    bool chunk=info.name[0]=='c';size_t length=strlen(info.name);
    if(info.type!=LFS_TYPE_REG || length!=(chunk?18u:9u) ||
       (chunk?info.name[9]!='.':(info.name[0]!='p' && info.name[0]!='d'))) { fail();break; }
    uint32_t generation=0;
    for(unsigned i=1;i<9;i++) {
      char c=info.name[i];unsigned digit=c>='0' && c<='9'?c-'0':c>='a' && c<='f'?c-'a'+10:16;
      if(digit==16) { fail();return; }generation=(generation<<4)|digit;
    }
    if(!generation) { fail();break; }
    bool keep=false;char path[80];
    if(chunk) {
      uint32_t part=0;
      for(unsigned i=10;i<18;i++) {
        char c=info.name[i];unsigned digit=c>='0' && c<='9'?c-'0':c>='a' && c<='f'?c-'a'+10:16;
        if(digit==16) { fail();return; }part=(part<<4)|digit;
      }
      if(!part || part>AppFileIndex::MaximumExtents) { fail();break; }
      AppFileIndex::Extent extent;extent.type=AppFileIndex::ChunkObject;extent.generation=generation;extent.part=part;
      extentPath(extent,path);
      for(uint32_t i=0;i<m_referenceCount;i++) if(m_references[i].type==extent.type &&
          m_references[i].generation==generation && m_references[i].part==part) { keep=true;break; }
      if(!keep && m_chunkRetainer) keep=m_chunkRetainer(m_retainerContext,m_id,generation,part);
    } else { object(info.name[0],generation,path);keep=retained(info.name[0],generation); }
    if(!keep) {
      if(lfs_remove(m_fs,path)<0) fail();
    }
    break;
  }
  case Phase::Package:writeObject('p',Phase::VerifyPackage);break;
  case Phase::VerifyPackage:checkObject('p',m_after.current,m_writeData?Phase::Data:Phase::RootWrite);break;
  case Phase::Data:writeObject('d',Phase::VerifyData);break;
  case Phase::VerifyData:checkObject('d',m_after.current,Phase::RootWrite);break;
  case Phase::RootWrite:
    if(!AppRootRecord::stage(m_fs,Pending,m_id,m_after,m_cache)) fail();
    else m_phase=Phase::RootVerify;
    break;
  case Phase::RootVerify: {
    uint8_t expected[AppDocumentRoot::Bytes];AppDocumentRoot::encode(m_after,expected);AppRootRecord::Info observed;
    bool ok=AppRootRecord::read(m_fs,Pending,m_id,m_cache,&observed)==AppRootRecord::Result::Ok &&
      observed.copies==AppRootRecord::Copies::Both && AppDocumentRoot::encode(observed.root,m_scratch) &&
      !memcmp(expected,m_scratch,AppDocumentRoot::Bytes);
    if(!ok) fail();else m_phase=Phase::Commit;break;
  }
  case Phase::Commit:
    if(lfs_rename(m_fs,Pending,m_path)<0) fail();else m_phase=Phase::Done;
    break;
  case Phase::RemoveDirectory:
    if(lfs_remove(m_fs,m_directory)<0) fail();else m_phase=Phase::Done;
    break;
  default:break;
  }
}
}}

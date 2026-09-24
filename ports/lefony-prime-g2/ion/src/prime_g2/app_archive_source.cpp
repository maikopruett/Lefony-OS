// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_archive_source.h"
#include "app_root_record.h"
namespace PrimeG2 { namespace AppArchive {
bool Source::name(const char *id) {
  if(!id || id[0]<'a' || id[0]>'z') return false;
  unsigned n=0;
  for(;n<49 && id[n];n++) if(!((id[n]>='a' && id[n]<='z') || (id[n]>='0' && id[n]<='9') || id[n]=='-')) return false;
  return n<=48;
}
void Source::canonicalPath(const char *id,char out[64]) {
  size_t n=strlen(id);memcpy(out,"apps/",5);memcpy(out+5,id,n);memcpy(out+5+n,".app",5);
}
void Source::objectPath(const char *id,char type,uint32_t generation,char out[80],uint32_t part) {
  size_t n=strlen(id);memcpy(out,"objects/",8);memcpy(out+8,id,n);out[8+n]='/';
  AppFileIndex::Extent extent;extent.generation=generation;extent.part=part;
  extent.type=type=='c'?AppFileIndex::ChunkObject:AppFileIndex::DataObject;
  AppFileIndex::objectName(extent,out+9+n);out[9+n]=type;
}
Source::Result Source::inspect(const char *id,SourceInfo *out,bool repair) {
  if(!out || !name(id)) return Result::Invalid;
  char path[64];canonicalPath(id,path);lfs_info info;int rc=lfs_stat(m_fs,path,&info);
  if(rc==LFS_ERR_NOENT) { *out={};memcpy(out->id,id,strlen(id)+1);return Result::Missing; }
  if(rc) return Result::IO;
  if(info.type!=LFS_TYPE_REG || info.size<64) return Result::Invalid;
  SourceInfo value;value.repairInspection=repair;memcpy(value.id,id,strlen(id)+1);lfs_file_t file{};
  if(info.size==AppRootRecord::Bytes) {
    AppRootRecord::Info record;auto found=AppRootRecord::read(m_fs,path,id,m_cache,&record);
    if(found!=AppRootRecord::Result::Ok)return found==AppRootRecord::Result::IO?Result::IO:Result::Invalid;
    value.root=record.root;value.rootCopies=record.copies;value.canonicalBytes=AppDocumentRoot::Bytes;value.generation=record.root.serial;
    value.packageBytes=record.root.current.packageBytes;
    if(!AppDocumentRoot::encode(record.root,value.canonical))return Result::Invalid;
    *out=value;return Result::Ok;
  }
  if(lfs_file_opencfg(m_fs,&file,path,LFS_O_RDONLY,&m_config)) return Result::IO;
  lfs_ssize_t read=lfs_file_read(m_fs,&file,value.canonical,64);
  bool io=read<0,ok=read==64;
  if(ok && !memcmp(value.canonical,"LFAFILE2",8)) {
    using AppFileIndex::get;
    value.legacy=true;value.generation=get(value.canonical+12);value.packageBytes=get(value.canonical+16);
    value.legacyPrivateBytes=get(value.canonical+20);value.canonicalBytes=64;
    ok=get(value.canonical+8)==2 && value.generation && value.packageBytes>=468 && value.packageBytes<=MaximumPackage &&
      value.legacyPrivateBytes<=65536 && (repair || info.size==64+value.packageBytes+value.legacyPrivateBytes) && zero(value.canonical+56,8);
  } else if(ok && info.size==AppDocumentRoot::Bytes) {
    read=lfs_file_read(m_fs,&file,value.canonical+64,AppDocumentRoot::Bytes-64);
    io=read<0;
    ok=read==AppDocumentRoot::Bytes-64 &&
      AppDocumentRoot::decode(value.canonical,sizeof(value.canonical),&value.root)==AppDocumentRoot::Result::Ok;
    value.canonicalBytes=AppDocumentRoot::Bytes;value.generation=value.root.serial;value.packageBytes=value.root.current.packageBytes;
  } else ok=false;
  if(lfs_file_close(m_fs,&file) || io) return Result::IO;
  if(!ok) return Result::Invalid;
  *out=value;return Result::Ok;
}
bool Source::unchanged(const SourceInfo &before) {
  SourceInfo after;Result result=inspect(before.id,&after,before.repairInspection);
  if(!before.generation) return result==Result::Missing;
  return result==Result::Ok && after.canonicalBytes==before.canonicalBytes &&
    !memcmp(after.canonical,before.canonical,before.canonicalBytes);
}
bool Source::package(const SourceInfo &source,unsigned number,uint8_t *out,uint32_t capacity) {
  if(!source.generation || !out || number>1 || (source.legacy && number) || !name(source.id)) return false;
  const auto &pair=number?source.root.previous:source.root.current;
  uint32_t bytes=source.legacy?source.packageBytes:pair.packageBytes;
  if(bytes<468 || bytes>MaximumPackage || capacity<bytes || (!source.legacy && !pair.package)) return false;
  char path[80];
  if(source.legacy) canonicalPath(source.id,path);else objectPath(source.id,'p',pair.package,path);
  lfs_file_t file{};if(lfs_file_opencfg(m_fs,&file,path,LFS_O_RDONLY,&m_config)) return false;
  bool ok=lfs_file_size(m_fs,&file)==static_cast<lfs_soff_t>(source.legacy?64+bytes+source.legacyPrivateBytes:bytes);
  if(ok && source.legacy) ok=lfs_file_seek(m_fs,&file,64,LFS_SEEK_SET)==64;
  NativeAppHash::SHA256 hash;NativeAppHash::shaInit(&hash);
  for(uint32_t offset=0;ok && offset<bytes;) {
    uint32_t n=bytes-offset;if(n>2048) n=2048;
    ok=lfs_file_read(m_fs,&file,out+offset,n)==static_cast<lfs_ssize_t>(n);
    if(ok) NativeAppHash::shaUpdate(&hash,out+offset,n);
    offset+=n;
  }
  uint8_t digest[32];NativeAppHash::shaFinal(&hash,digest);
  ok=(lfs_file_close(m_fs,&file)==0) && ok;
  return ok && (source.legacy || !memcmp(digest,pair.packageHash,32));
}
bool Source::legacyPrefix(const SourceInfo &source,uint8_t digest[32]) {
  if(!source.legacy || !source.generation || !digest || !name(source.id)) return false;
  char path[64];canonicalPath(source.id,path);lfs_file_t file{};
  if(lfs_file_opencfg(m_fs,&file,path,LFS_O_RDONLY,&m_config)) return false;
  uint8_t prefix[SignedPrefixBytes];
  bool ok=lfs_file_seek(m_fs,&file,64,LFS_SEEK_SET)==64 &&
    lfs_file_read(m_fs,&file,prefix,sizeof(prefix))==sizeof(prefix);
  ok=(lfs_file_close(m_fs,&file)==0) && ok;
  if(ok) NativeAppHash::sha256(prefix,sizeof(prefix),digest);
  return ok;
}
}}

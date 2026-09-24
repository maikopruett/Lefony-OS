// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_root_record.h"
namespace PrimeG2 { namespace AppRootRecord {
namespace {
bool name(const char *id) {
  if(!id || id[0]<'a' || id[0]>'z')return false;
  unsigned n=0;for(;n<49 && id[n];n++)
    if(!((id[n]>='a' && id[n]<='z') || (id[n]>='0' && id[n]<='9') || id[n]=='-'))return false;
  return n<=48;
}
bool zero(const uint8_t *p,unsigned n) {for(unsigned i=0;i<n;i++)if(p[i])return false;return true;}
bool incompatible(Result r) {return r==Result::Unsupported || r==Result::WrongApp;}
}
bool encode(const char *id,const Root &root,uint8_t out[Bytes]) {
  if(!out || !name(id) || !AppDocumentRoot::valid(root))return false;
  uint8_t wire[Bytes]{};memcpy(wire,"LFAFILE5",8);
  AppDocumentRoot::Detail::put(wire+8,5);AppDocumentRoot::Detail::put(wire+12,Bytes);
  memcpy(wire+16,id,strlen(id));
  if(!AppDocumentRoot::encode(root,wire+80))return false;
  NativeAppHash::sha256(wire,Bytes-32,wire+Bytes-32);memcpy(out,wire,Bytes);return true;
}
Result decode(const char *id,const uint8_t *wire,unsigned bytes,Root *out) {
  if(!name(id) || !wire || !out || bytes!=Bytes)return Result::Invalid;
  uint8_t hash[32];NativeAppHash::sha256(wire,Bytes-32,hash);
  if(memcmp(hash,wire+Bytes-32,32))return Result::Invalid;
  // A self-consistent unsupported record cannot be masked by an older copy.
  if(memcmp(wire,"LFAFILE5",8) || AppDocumentRoot::Detail::get(wire+8)!=5 ||
     AppDocumentRoot::Detail::get(wire+12)!=Bytes)return Result::Unsupported;
  unsigned n=0;while(n<64 && wire[16+n])n++;
  if(n>48 || !n || !zero(wire+16+n,64-n))return Result::Invalid;
  char stored[49]{};memcpy(stored,wire+16,n);if(!name(stored))return Result::Invalid;
  if(strcmp(id,stored))return Result::WrongApp;
  Root root;auto result=AppDocumentRoot::decode(wire+80,AppDocumentRoot::Bytes,&root);
  if(result!=AppDocumentRoot::Result::Ok)return result==AppDocumentRoot::Result::Unsupported?Result::Unsupported:Result::Invalid;
  *out=root;return Result::Ok;
}
Result read(lfs_t *fs,const char *path,const char *id,void *cache,Info *out) {
  if(!fs || !path || !name(id) || !cache || !out)return Result::Invalid;
  lfs_file_t file{};lfs_file_config config{};config.buffer=cache;
  int rc=lfs_file_opencfg(fs,&file,path,LFS_O_RDONLY,&config);
  if(rc<0)return rc==LFS_ERR_NOENT?Result::Missing:Result::IO;
  int size=lfs_file_size(fs,&file);uint8_t payload[Bytes];Info value;
  if(size==AppDocumentRoot::Bytes) {
    rc=lfs_file_read(fs,&file,payload,size);int closed=lfs_file_close(fs,&file);
    if(rc<0 || closed<0)return Result::IO;
    if(rc!=size)return Result::Invalid;
    auto decoded=AppDocumentRoot::decode(payload,size,&value.root);
    if(decoded!=AppDocumentRoot::Result::Ok)return decoded==AppDocumentRoot::Result::Unsupported?Result::Unsupported:Result::Invalid;
    *out=value;return Result::Ok;
  }
  if(size!=Bytes || file.flags&LFS_F_INLINE) {
    lfs_file_close(fs,&file);return size<0?Result::IO:Result::Unsupported;
  }
  rc=lfs_file_read(fs,&file,payload,Bytes);int closed=lfs_file_close(fs,&file);
  if(closed<0)return Result::IO;
  if(rc>=0 && rc!=Bytes)return Result::IO;
  if(rc<0 && rc!=LFS_ERR_IO && rc!=LFS_ERR_CORRUPT)return Result::IO;
  Result primary=rc<0?Result::IO:decode(id,payload,Bytes,&value.root);
  uint8_t attribute[Bytes];Root alternate;
  rc=lfs_getattr(fs,path,Attribute,attribute,Bytes);
  if(rc<0 && rc!=LFS_ERR_NOATTR && rc!=LFS_ERR_IO && rc!=LFS_ERR_CORRUPT)return Result::IO;
  Result mirror=rc<0?(rc==LFS_ERR_NOATTR?Result::Missing:Result::IO):decode(id,attribute,rc,&alternate);
  if(incompatible(primary))return primary;
  if(incompatible(mirror))return mirror;
  if(primary==Result::Ok && mirror==Result::Ok) {
    if(memcmp(payload,attribute,Bytes))return Result::Conflict;
    value.copies=Copies::Both;
  } else if(primary==Result::Ok)value.copies=Copies::Payload;
  else if(mirror==Result::Ok) {value.root=alternate;value.copies=Copies::Attribute;}
  else return primary==Result::IO || mirror==Result::IO?Result::IO:Result::Invalid;
  *out=value;return Result::Ok;
}
bool stage(lfs_t *fs,const char *path,const char *id,const Root &root,void *cache) {
  uint8_t wire[Bytes];
  if(!fs || !path || !cache || Bytes<=fs->inline_max || fs->attr_max<Bytes || !encode(id,root,wire))return false;
  lfs_file_t file{};lfs_attr attr{Attribute,wire,Bytes};lfs_file_config config{};
  config.buffer=cache;config.attrs=&attr;config.attr_count=1;
  if(lfs_file_opencfg(fs,&file,path,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC,&config)<0)return false;
  int written=lfs_file_write(fs,&file,wire,Bytes);bool outlined=!(file.flags&LFS_F_INLINE);
  int closed=lfs_file_close(fs,&file);return written==Bytes && outlined && closed==0;
}
}}

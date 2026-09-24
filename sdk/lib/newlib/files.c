/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
/* Descriptor and stdio adapter for public foreground execution and API 2 files. */
#include <lefony/files.h>
#include <lefony/foreground.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <reent.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
static int failure(uint32_t error) {
  switch(error) {
  case LEFONY_FILE_INVALID:errno=EINVAL;break;
  case LEFONY_FILE_BAD_HANDLE:errno=EBADF;break;
  case LEFONY_FILE_NOT_FOUND:errno=ENOENT;break;
  case LEFONY_FILE_EXISTS:errno=EEXIST;break;
  case LEFONY_FILE_IS_DIRECTORY:errno=EISDIR;break;
  case LEFONY_FILE_NO_SPACE:errno=ENOSPC;break;
  case LEFONY_FILE_TOO_LARGE:errno=EFBIG;break;
  case LEFONY_FILE_BUSY:errno=EBUSY;break;
  case LEFONY_FILE_LIMIT:errno=EMFILE;break;
  case LEFONY_FILE_SCHEMA:case LEFONY_FILE_DENIED:errno=EACCES;break;
  case LEFONY_FILE_NOT_EMPTY:errno=ENOTEMPTY;break;
  case LEFONY_FILE_NOT_DIRECTORY:errno=ENOTDIR;break;
  case LEFONY_FILE_CHANGED:errno=ESTALE;break;
  case LEFONY_FILE_QUOTA_EXCEEDED:errno=EDQUOT;break;
  default:errno=EIO;break;
  }
  return -1;
}
static int call(LefonyFileRequest *request,void *output,uint32_t capacity) {
  int status=lefony_files(request);
  if(status<0) return failure((uint32_t)-status);
  if(status!=1 || !request->token) return failure(LEFONY_FILE_IO);
  uint32_t token=request->token;
  do {
    /* Cached snapshot operations may already be complete. Older firmware and
     * misses still yield for normal input/storage polling; never busy-spin. */
    *request=lefony_file_request(LEFONY_FILE_POLL);request->token=token;
    request->buffer=(uint32_t)(uintptr_t)output;request->capacity=capacity;
    status=lefony_files(request);
    if(status==1 && lefony_program_yield()!=0) return failure(LEFONY_FILE_IO);
  } while(status==1);
  if(status<0) return failure((uint32_t)-status);
  return request->error?failure(request->error):request->result;
}
static int path(LefonyFileRequest *r,const char *name,int destination) {
  if(!name) { errno=EINVAL;return -1; }
  // Conventional tools commonly prepend ./ to names in their working root.
  // This is the app's namespace, with no chdir, absolute paths or parent walk.
  // Keep all remaining components under the unchanged OS path validation.
  unsigned prefix=0;
  while(name[0]=='.' && name[1]=='/') {
    if(prefix==256) { errno=ENAMETOOLONG;return -1; }
    prefix+=2;name+=2;
  }
  if(r->operation==LEFONY_FILE_LIST && name[0]=='/') { errno=EINVAL;return -1; }
  unsigned n=0;while(n<=96 && name[n]) n++;
  // A trailing slash is conventional for mkdir; file operations retain the
  // original strict names so fopen("file/") never opens an ordinary file.
  if((r->operation==LEFONY_FILE_MKDIR || r->operation==LEFONY_FILE_LIST) && n && n<=96 && name[n-1]=='/') --n;
  if(r->operation==LEFONY_FILE_LIST && (!n || (n==1 && name[0]=='.'))) return 0;
  if(!n || n>95) { errno=ENAMETOOLONG;return -1; }
  if(destination) { r->destination=(uint32_t)(uintptr_t)name;r->destinationBytes=n; }
  else { r->path=(uint32_t)(uintptr_t)name;r->pathBytes=n; }
  return 0;
}
int _open(const char *name,int flags,...) {
  const int allowed=O_ACCMODE|O_CREAT|O_TRUNC|O_APPEND|O_EXCL|O_BINARY;
  if(flags&~allowed) { errno=EINVAL;return -1; }
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_OPEN);
  switch(flags&O_ACCMODE) {
  case O_RDONLY:r.flags=LEFONY_FILE_READABLE;break;
  case O_WRONLY:r.flags=LEFONY_FILE_WRITABLE;break;
  case O_RDWR:r.flags=LEFONY_FILE_READABLE|LEFONY_FILE_WRITABLE;break;
  default:errno=EINVAL;return -1;
  }
  if(flags&O_CREAT) r.flags|=LEFONY_FILE_CREATE;
  if(flags&O_TRUNC) r.flags|=LEFONY_FILE_TRUNCATE;
  if(flags&O_APPEND) r.flags|=LEFONY_FILE_APPEND;
  if(flags&O_EXCL) r.flags|=LEFONY_FILE_EXCLUSIVE;
  return path(&r,name,0)<0?-1:call(&r,0,0);
}
int _close(int fd) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_CLOSE);r.handle=fd;return call(&r,0,0);
}
int fsync(int fd) {
  // Discover before submitting the additive operation. Older firmware keeps
  // working with this runtime and reports an explicit unsupported operation.
  uint32_t caps[12]={48,1,0};
  if(lefony_service(6,caps)!=0 || !(caps[3]&LEFONY_FILE_SYNC_CAPABILITY)) {
    errno=ENOSYS;return -1;
  }
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_SYNC);r.handle=fd;return call(&r,0,0);
}
int lefony_file_abort(int fd) {
  uint32_t caps[12]={48,1,0};
  if(lefony_service(6,caps)!=0 || !(caps[3]&LEFONY_FILE_ABORT_CAPABILITY)) {
    errno=ENOSYS;return -1;
  }
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_ABORT);r.handle=fd;return call(&r,0,0);
}
static int catalog_available(void) {
  uint32_t caps[12]={48,1,0};
  if(lefony_service(6,caps)!=0 || !(caps[3]&LEFONY_FILE_CATALOG_CAPABILITY)) {
    errno=ENOSYS;return -1;
  }
  return 0;
}
int lefony_file_list(const char *directory,uint32_t offset,uint32_t generation,LefonyDirectoryPage *out) {
  if(!out) { errno=EINVAL;return -1; }
  if(catalog_available()<0) return -1;
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_LIST);r.offset=offset;r.flags=generation;
  return path(&r,directory,0)<0?-1:call(&r,out,sizeof(*out));
}
int lefony_file_space(LefonyFileSpace *out) {
  if(!out) { errno=EINVAL;return -1; }
  if(catalog_available()<0) return -1;
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_SPACE);return call(&r,out,sizeof(*out));
}
int lefony_file_quota(LefonyFileQuota *out) {
  if(!out) { errno=EINVAL;return -1; }
  uint32_t caps[12]={48,1,0};
  if(lefony_service(6,caps)!=0 || !(caps[3]&LEFONY_FILE_QUOTA_CAPABILITY)) {
    errno=ENOSYS;return -1;
  }
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_QUOTA);return call(&r,out,sizeof(*out));
}
int _read(int fd,void *buffer,size_t bytes) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_READ);r.handle=fd;
  r.length=bytes>2048?2048:(uint32_t)bytes;return call(&r,buffer,r.length);
}
int _write(int fd,const void *buffer,size_t bytes) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_WRITE);r.handle=fd;
  r.length=bytes>2048?2048:(uint32_t)bytes;r.buffer=(uint32_t)(uintptr_t)buffer;return call(&r,0,0);
}
static int info(int fd,const char *name,LefonyFileInfo *info) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_STAT);r.handle=fd;
  if(name && path(&r,name,0)<0) return -1;
  return call(&r,info,sizeof(*info));
}
off_t _lseek(int fd,off_t offset,int whence) {
  int64_t position=offset;
  if(whence!=SEEK_SET) {
    if(whence!=SEEK_CUR && whence!=SEEK_END) { errno=EINVAL;return -1; }
    LefonyFileInfo value;if(info(fd,0,&value)<0) return -1;
    position+=whence==SEEK_CUR?value.position:value.bytes;
  }
  if(position<0 || position>64*1024*1024) { errno=EINVAL;return -1; }
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_SEEK);r.handle=fd;r.offset=(uint32_t)position;
  return call(&r,0,0);
}
static int stat_value(int fd,const char *name,struct stat *out) {
  if(!out) { errno=EINVAL;return -1; }
  LefonyFileInfo value;if(info(fd,name,&value)<0) return -1;
  *out=(struct stat){0};out->st_mode=value.kind==2?S_IFDIR|0700:S_IFREG|0600;
  out->st_size=(off_t)value.bytes;out->st_nlink=1;out->st_blksize=2048;return 0;
}
int _fstat(int fd,struct stat *out) { return stat_value(fd,0,out); }
int _stat(const char *name,struct stat *out) { return stat_value(0,name,out); }
int _isatty(int fd) { (void)fd;errno=ENOTTY;return 0; }
int _unlink(const char *name) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_UNLINK);return path(&r,name,0)<0?-1:call(&r,0,0);
}
int _rename(const char *old,const char *next) {
  LefonyFileRequest r=lefony_file_request(LEFONY_FILE_RENAME);
  return path(&r,old,0)<0 || path(&r,next,1)<0?-1:call(&r,0,0);
}
/* The pinned newlib was built without HAVE_RENAME. Supply its reentrant hook
 * explicitly so rename never falls back to separately committed link/unlink. */
int _rename_r(struct _reent *context,const char *old,const char *next) {
  int result=_rename(old,next);if(result<0) context->_errno=errno;return result;
}
int mkdir(const char *name,mode_t mode) {
  (void)mode;LefonyFileRequest r=lefony_file_request(LEFONY_FILE_MKDIR);
  return path(&r,name,0)<0?-1:call(&r,0,0);
}

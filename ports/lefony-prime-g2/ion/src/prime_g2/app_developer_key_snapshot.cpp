// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_developer_key_snapshot.h"
namespace PrimeG2 { namespace AppDeveloperKeys {
namespace {
void put(uint8_t *p,uint32_t v) {for(unsigned i=0;i<4;i++) p[i]=v>>(8*i);}
}
Snapshot::Snapshot(lfs_t *fs):m_fs(fs) {m_config.buffer=m_cache;}
Snapshot::~Snapshot() {close();}
int Snapshot::open() {
  if(!m_fs || m_open) return LFS_ERR_INVAL;
  int result=lfs_file_opencfg(m_fs,&m_file,Store::Path,LFS_O_RDONLY,&m_config);
  m_open=result==0;return result;
}
int Snapshot::close() {
  if(!m_open) return 0;
  int result=lfs_file_close(m_fs,&m_file);m_open=false;return result;
}
void Snapshot::fail(Result result) {close();m_state=State::Failed;m_result=result;}
Result Snapshot::begin() {
  if(m_state==State::Running) return Result::Busy;
  if(close()<0) {fail(Result::Io);return m_result;}
  m_info={};memset(m_missing,0,sizeof(m_missing));m_cursor=0;
  m_phase=Phase::Open;m_state=State::Running;return m_result=Result::Busy;
}
void Snapshot::cancel() {
  if(m_state!=State::Running) return;
  if(close()<0) {fail(Result::Io);return;}
  m_state=State::Cancelled;m_result=Result::Cancelled;
}
unsigned Snapshot::length(unsigned chunk) const {
  unsigned n=m_info.originalBytes-chunk*ChunkBytes;return n>ChunkBytes?ChunkBytes:n;
}
void Snapshot::header(uint8_t out[HeaderBytes]) const {
  memset(out,0,HeaderBytes);memcpy(out,"LFKREAD1",8);
  put(out+8,1);put(out+12,m_info.originalBytes);put(out+16,ChunkBytes);put(out+20,count());
}
void Snapshot::record(unsigned chunk,uint8_t out[RecordHeaderBytes]) const {
  memset(out,0,RecordHeaderBytes);put(out,chunk*ChunkBytes);put(out+4,length(chunk));put(out+8,missing(chunk)?1:0);
}
void Snapshot::step() {
  if(m_state!=State::Running) return;
  if(m_phase==Phase::Open) {
    int rc=open();
    if(rc<0) {fail(rc==LFS_ERR_NOENT?Result::Missing:Result::Io);return;}
    lfs_soff_t bytes=lfs_file_size(m_fs,&m_file);
    if(bytes<0 || uint32_t(bytes)>Store::MaximumDamagedBytes) {fail(bytes<0?Result::Io:Result::Invalid);return;}
    m_info.originalBytes=bytes;m_info.bytes=HeaderBytes;
    uint8_t encoded[HeaderBytes];header(encoded);NativeAppHash::shaInit(&m_hash);
    NativeAppHash::shaUpdate(&m_hash,encoded,sizeof(encoded));m_phase=Phase::Read;return;
  }
  if(m_phase==Phase::Close) {
    if(close()<0) {fail(Result::Io);return;}
    if(!m_info.unreadableChunks) {fail(Result::Readable);return;}
    NativeAppHash::shaFinal(&m_hash,m_info.hash);m_state=State::Ready;m_result=Result::Ok;return;
  }
  if(m_cursor==count()) {m_phase=Phase::Close;return;}
  unsigned n=length(m_cursor),offset=m_cursor*ChunkBytes;
  int rc=lfs_file_seek(m_fs,&m_file,offset,LFS_SEEK_SET);
  if(rc!=int(offset)) {fail(Result::Io);return;}
  rc=lfs_file_read(m_fs,&m_file,m_scratch,n);
  if(rc!=int(n)) {
    // Only explicit media errors describe an unreadable region. Short reads
    // or other errors invalidate the snapshot instead of inventing holes.
    if(rc!=LFS_ERR_IO && rc!=LFS_ERR_CORRUPT) {fail(Result::Io);return;}
    m_missing[m_cursor/8]|=1u<<(m_cursor%8);m_info.unreadableChunks++;
  } else {m_info.readableBytes+=n;m_info.bytes+=n;}
  uint8_t encoded[RecordHeaderBytes];record(m_cursor,encoded);
  NativeAppHash::shaUpdate(&m_hash,encoded,sizeof(encoded));m_info.bytes+=sizeof(encoded);
  if(!missing(m_cursor)) NativeAppHash::shaUpdate(&m_hash,m_scratch,n);
  m_cursor++;
}
bool Snapshot::info(Info *out) const {
  if(!out || m_state!=State::Ready) return false;
  *out=m_info;return true;
}
int Snapshot::read(uint32_t offset,void *output,uint32_t bytes) {
  if(m_state!=State::Ready || !output || !bytes || bytes>ChunkBytes || offset>m_info.bytes || bytes>m_info.bytes-offset) return -1;
  if(open()<0) return -1;
  if(lfs_file_size(m_fs,&m_file)!=int(m_info.originalBytes)) {close();return -1;}
  uint8_t *out=static_cast<uint8_t *>(output);unsigned done=0,position=0;
  auto copy=[&](const uint8_t *source,unsigned n) {
    if(done<bytes && offset<position+n && offset+bytes>position) {
      unsigned start=offset>position?offset-position:0,amount=n-start;
      if(amount>bytes-done) amount=bytes-done;
      memcpy(out+done,source+start,amount);done+=amount;
    }
    position+=n;
  };
  uint8_t encoded[HeaderBytes];header(encoded);copy(encoded,HeaderBytes);
  bool ok=true;
  for(unsigned chunk=0;chunk<count() && done<bytes;chunk++) {
    record(chunk,encoded);copy(encoded,RecordHeaderBytes);
    if(!missing(chunk)) {
      unsigned n=length(chunk);
      if(offset<position+n && offset+bytes>position) {
        unsigned fileOffset=chunk*ChunkBytes;
        if(lfs_file_seek(m_fs,&m_file,fileOffset,LFS_SEEK_SET)!=int(fileOffset) ||
           lfs_file_read(m_fs,&m_file,m_scratch,n)!=int(n)) {ok=false;break;}
        copy(m_scratch,n);
      } else position+=n;
    }
  }
  int result=close();return ok && result==0 && done==bytes?int(done):-1;
}

Result Store::beginRepairSnapshot(Snapshot &snapshot,const uint8_t hash[32],const uint8_t modulus[256],const char *label,size_t bytes) {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  Snapshot::Info info;
  if(!hash || snapshot.m_fs!=m_fs || !snapshot.info(&info) || !info.unreadableChunks) return Result::Invalid;
  if(memcmp(hash,info.hash,32)) return Result::Stale;
  Table empty,candidate;Result result=empty.enroll(0,modulus,label,bytes,&candidate);
  if(result!=Result::Ok) return result;
  m_loaded=false;m_current={};result=start(candidate);
  if(result==Result::Busy) {snapshot.m_state=Snapshot::State::Idle;snapshot.m_result=Result::Missing;}
  return result;
}
}}

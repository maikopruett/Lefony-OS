// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_developer_keys.h"
#include "native_app_signature.h"

namespace PrimeG2 { namespace AppDeveloperKeys {
namespace {
bool zero(const void *data,size_t bytes) {
  const uint8_t *p=static_cast<const uint8_t *>(data);
  for(size_t i=0;i<bytes;i++) if(p[i]) return false;
  return true;
}
uint32_t word(const uint8_t *p) {
  return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);
}
void put(uint8_t *p,uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=v>>(8*i); }
bool labelValid(const char *label,size_t bytes) {
  if(!label || !bytes || bytes>=LabelBytes || label[0]==' ' || label[bytes-1]==' ') return false;
  for(size_t i=0;i<bytes;i++) if(label[i]<32 || label[i]>126) return false;
  return true;
}
bool storedLabel(const char label[LabelBytes]) {
  size_t n=0;while(n<LabelBytes && label[n]) n++;
  return labelValid(label,n) && zero(label+n,LabelBytes-n);
}
void digest(const uint8_t *wire,uint8_t out[32]) {
  NativeAppHash::SHA256 h;NativeAppHash::shaInit(&h);
  NativeAppHash::shaUpdate(&h,wire,32);
  NativeAppHash::shaUpdate(&h,wire+HeaderBytes,WireBytes-HeaderBytes);
  NativeAppHash::shaFinal(&h,out);
}
Result ioResult(int rc) { return rc==LFS_ERR_CORRUPT?Result::Corrupt:Result::Io; }
}

bool fingerprint(const uint8_t modulus[256],uint8_t id[32]) {
  if(!modulus || !id || !(modulus[0]&128) || !(modulus[255]&1)) return false;
  const uint8_t prefix[]={0x30,0x82,0x01,0x22,0x30,0x0d,0x06,0x09,0x2a,0x86,0x48,0x86,0xf7,0x0d,0x01,
    0x01,0x01,0x05,0x00,0x03,0x82,0x01,0x0f,0x00,0x30,0x82,0x01,0x0a,0x02,0x82,0x01,0x01,0x00};
  const uint8_t suffix[]={0x02,0x03,0x01,0x00,0x01};
  NativeAppHash::SHA256 h;NativeAppHash::shaInit(&h);
  NativeAppHash::shaUpdate(&h,prefix,sizeof(prefix));
  NativeAppHash::shaUpdate(&h,modulus,256);NativeAppHash::shaUpdate(&h,suffix,sizeof(suffix));
  NativeAppHash::shaFinal(&h,id);return true;
}

bool Table::valid() const {
  if(count>MaximumKeys || serial<count) return false;
  for(unsigned i=0;i<MaximumKeys;i++) {
    const Key &key=keys[i];
    if(i>=count) {
      if(uint32_t(key.state) || !zero(key.id,32) || !zero(key.modulus,256) || !zero(key.label,LabelBytes)) return false;
      continue;
    }
    uint8_t id[32];
    if((key.state!=KeyState::Active && key.state!=KeyState::Revoked) || !storedLabel(key.label) ||
       !fingerprint(key.modulus,id) || memcmp(key.id,id,32)) return false;
    for(unsigned j=0;j<i;j++) if(!memcmp(keys[j].id,id,32)) return false;
  }
  return true;
}
const Key *Table::find(const uint8_t id[32],Purpose purpose) const {
  if(!id || (purpose!=Purpose::Execute && purpose!=Purpose::Inspect) || !valid()) return nullptr;
  for(unsigned i=0;i<count;i++) if(!memcmp(keys[i].id,id,32) &&
      (purpose==Purpose::Inspect || keys[i].state==KeyState::Active)) return keys+i;
  return nullptr;
}
bool Table::unwrap(const uint8_t *package,size_t bytes,Purpose purpose,const uint8_t **payload,size_t *length,void (*progress)()) const {
  if(!package || bytes<468 || bytes>2101664) return false;
  const Key *key=find(package+24,purpose);
  return key && NativeAppSignature::unwrapWithKey(package,bytes,key->id,key->modulus,payload,length,progress);
}
Result Table::enroll(uint32_t expected,const uint8_t modulus[256],const char *label,size_t bytes,Table *out) const {
  if(!out || out==this || !valid() || !labelValid(label,bytes)) return Result::Invalid;
  Key key;key.state=KeyState::Active;
  if(!fingerprint(modulus,key.id)) return Result::Invalid;
  memcpy(key.modulus,modulus,256);memcpy(key.label,label,bytes);
  if(expected!=serial) return Result::Stale;
  unsigned index=0;while(index<count && memcmp(keys[index].id,key.id,32)) index++;
  if(index<count && keys[index].state==KeyState::Active && !memcmp(keys[index].label,key.label,LabelBytes)) return Result::Unchanged;
  if(index==MaximumKeys) return Result::Full;
  if(serial==0xffffffffu) return Result::Overflow;
  *out=*this;out->keys[index]=key;out->count=count+(index==count);out->serial++;
  return Result::Ok;
}
Result Table::revoke(uint32_t expected,const uint8_t id[32],Table *out) const {
  if(!out || out==this || !id || !valid()) return Result::Invalid;
  if(expected!=serial) return Result::Stale;
  unsigned index=0;while(index<count && memcmp(keys[index].id,id,32)) index++;
  if(index==count) return Result::Missing;
  if(keys[index].state==KeyState::Revoked) return Result::Unchanged;
  if(serial==0xffffffffu) return Result::Overflow;
  *out=*this;out->keys[index].state=KeyState::Revoked;out->serial++;
  return Result::Ok;
}
Result Table::remove(uint32_t expected,const uint8_t id[32],Table *out) const {
  if(!out || out==this || !id || !valid()) return Result::Invalid;
  if(expected!=serial) return Result::Stale;
  unsigned index=0;while(index<count && memcmp(keys[index].id,id,32)) index++;
  if(index==count) return Result::Missing;
  if(keys[index].state!=KeyState::Revoked) return Result::Active;
  if(serial==0xffffffffu) return Result::Overflow;
  *out=*this;
  for(unsigned i=index+1;i<count;i++) out->keys[i-1]=out->keys[i];
  out->keys[count-1]=Key{};out->count--;out->serial++;return Result::Ok;
}
bool encode(const Table &table,uint8_t out[WireBytes]) {
  if(!out || !table.serial || !table.valid()) return false;
  memset(out,0,WireBytes);memcpy(out,"LFDKEY1\0",8);
  // Version 2 can retain a nonzero serial after removing the final key.
  put(out+8,2);put(out+12,WireBytes);put(out+16,table.serial);put(out+20,table.count);
  for(unsigned i=0;i<table.count;i++) {
    uint8_t *p=out+HeaderBytes+i*RecordBytes;const Key &key=table.keys[i];
    put(p,uint32_t(key.state));memcpy(p+16,key.id,32);memcpy(p+48,key.modulus,256);memcpy(p+304,key.label,LabelBytes);
  }
  digest(out,out+32);return true;
}
Result decode(const uint8_t *wire,size_t bytes,Table *out) {
  if(!wire || !out || bytes!=WireBytes || memcmp(wire,"LFDKEY1\0",8) ||
     (word(wire+8)!=1 && word(wire+8)!=2) || word(wire+12)!=WireBytes || !word(wire+16) || !zero(wire+24,8) ||
     (word(wire+8)==1 && !word(wire+20))) return Result::Corrupt;
  uint8_t hash[32];digest(wire,hash);if(memcmp(hash,wire+32,32)) return Result::Corrupt;
  Table table;table.serial=word(wire+16);table.count=word(wire+20);
  if(table.count>MaximumKeys) return Result::Corrupt;
  for(unsigned i=0;i<MaximumKeys;i++) {
    const uint8_t *p=wire+HeaderBytes+i*RecordBytes;
    if(i>=table.count) { if(!zero(p,RecordBytes)) return Result::Corrupt;continue; }
    if(!zero(p+4,12)) return Result::Corrupt;
    Key &key=table.keys[i];key.state=KeyState(word(p));
    memcpy(key.id,p+16,32);memcpy(key.modulus,p+48,256);memcpy(key.label,p+304,LabelBytes);
  }
  if(!table.valid()) return Result::Corrupt;
  *out=table;return Result::Ok;
}

Store::Store(lfs_t *fs):m_fs(fs) { m_config.buffer=m_cache; }
Store::~Store() { close(); }
int Store::open(const char *path,int flags) {
  if(!m_fs || m_open) return LFS_ERR_INVAL;
  int rc=lfs_file_opencfg(m_fs,&m_file,path,flags,&m_config);
  if(rc==0) { m_open=true;m_cursor=0; }
  return rc;
}
int Store::close() {
  if(!m_open) return 0;
  int rc=lfs_file_close(m_fs,&m_file);m_open=false;return rc;
}
Store::State Store::state() const {
  if(m_phase==Phase::Idle) return State::Idle;
  if(m_phase==Phase::Done) return State::Complete;
  if(m_phase==Phase::Cancelled) return State::Cancelled;
  if(m_phase==Phase::Failed) return State::Failed;
  return m_commitStarted?State::Committing:State::Busy;
}
Result Store::load() {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  m_loaded=false;m_current={};m_phase=Phase::Idle;m_commitStarted=false;
  int rc=open(Path,LFS_O_RDONLY);
  if(rc==LFS_ERR_NOENT) { m_loaded=true;return m_result=Result::Missing; }
  if(rc<0) return m_result=ioResult(rc);
  lfs_soff_t size=lfs_file_size(m_fs,&m_file);
  Result result=size<0?ioResult(size):(size==WireBytes?Result::Ok:Result::Corrupt);
  while(result==Result::Ok && m_cursor<WireBytes) {
    unsigned n=WireBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    rc=lfs_file_read(m_fs,&m_file,m_wire+m_cursor,n);
    if(rc!=int(n)) result=rc<0?ioResult(rc):Result::Corrupt;
    m_cursor+=n;
  }
  rc=close();if(rc<0) result=ioResult(rc);
  if(result==Result::Ok) result=decode(m_wire,WireBytes,&m_current);
  m_loaded=result==Result::Ok;return m_result=result;
}
Result Store::prepare(uint32_t expected) {
  Result result=load();
  if(result!=Result::Ok && result!=Result::Missing) return result;
  if(m_current.serial!=expected) return Result::Stale;
  return Result::Ok;
}
Result Store::start(const Table &candidate) {
  if(!encode(candidate,m_wire)) return Result::Invalid;
  m_phase=Phase::Create;m_commitStarted=false;return m_result=Result::Busy;
}
Result Store::beginEnroll(uint32_t expected,const uint8_t modulus[256],const char *label,size_t bytes) {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  if(!modulus || !labelValid(label,bytes)) return Result::Invalid;
  // Inputs may point into current(), which load() deliberately invalidates.
  uint8_t key[256];char name[LabelBytes]{};memcpy(key,modulus,256);memcpy(name,label,bytes);
  Result result=prepare(expected);if(result!=Result::Ok) return m_result=result;
  Table candidate;result=m_current.enroll(expected,key,name,bytes,&candidate);
  return m_result=result==Result::Ok?start(candidate):result;
}
Result Store::beginRevoke(uint32_t expected,const uint8_t id[32]) {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  if(!id) return Result::Invalid;
  uint8_t identity[32];memcpy(identity,id,32);
  Result result=prepare(expected);if(result!=Result::Ok) return m_result=result;
  Table candidate;result=m_current.revoke(expected,identity,&candidate);
  return m_result=result==Result::Ok?start(candidate):result;
}
Result Store::beginRemove(uint32_t expected,const uint8_t id[32]) {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  if(!id) return Result::Invalid;
  uint8_t identity[32];memcpy(identity,id,32);
  Result result=prepare(expected);if(result!=Result::Ok) return m_result=result;
  Table candidate;result=m_current.remove(expected,identity,&candidate);
  return m_result=result==Result::Ok?start(candidate):result;
}
Result Store::damaged(uint8_t hash[32],uint32_t *bytes) {
  if(!hash || !bytes) return Result::Invalid;
  Result result=load();if(result!=Result::Corrupt) return result==Result::Ok || result==Result::Missing?Result::Invalid:result;
  int rc=open(Path,LFS_O_RDONLY);if(rc<0) return ioResult(rc);
  lfs_soff_t size=lfs_file_size(m_fs,&m_file);
  if(size<0 || uint32_t(size)>MaximumDamagedBytes) {close();return size<0?ioResult(size):Result::Invalid;}
  NativeAppHash::SHA256 h;NativeAppHash::shaInit(&h);
  while(m_cursor<uint32_t(size)) {
    unsigned n=uint32_t(size)-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
    rc=lfs_file_read(m_fs,&m_file,m_scratch,n);
    if(rc!=int(n)) {close();return rc<0?ioResult(rc):Result::Io;}
    NativeAppHash::shaUpdate(&h,m_scratch,n);m_cursor+=n;
  }
  rc=close();if(rc<0) return ioResult(rc);
  NativeAppHash::shaFinal(&h,hash);*bytes=uint32_t(size);return Result::Ok;
}
int Store::readDamaged(uint32_t offset,void *out,uint32_t bytes) {
  if(!out || !bytes || bytes>512 || load()!=Result::Corrupt) return -1;
  if(open(Path,LFS_O_RDONLY)<0) return -1;
  lfs_soff_t size=lfs_file_size(m_fs,&m_file);int rc=-1;
  if(size>=0 && uint32_t(size)<=MaximumDamagedBytes && offset<=uint32_t(size) && bytes<=uint32_t(size)-offset &&
      lfs_file_seek(m_fs,&m_file,offset,LFS_SEEK_SET)==int(offset)) rc=lfs_file_read(m_fs,&m_file,out,bytes);
  int closed=close();return closed<0?-1:rc;
}
Result Store::beginRepair(const uint8_t hash[32],const uint8_t modulus[256],const char *label,size_t bytes) {
  if(state()==State::Busy || state()==State::Committing) return Result::Busy;
  if(!hash || !modulus || !labelValid(label,bytes)) return Result::Invalid;
  uint8_t expected[32],key[256],current[32];char name[LabelBytes]{};
  memcpy(expected,hash,32);memcpy(key,modulus,256);memcpy(name,label,bytes);
  uint32_t length;Result result=damaged(current,&length);
  if(result!=Result::Ok) return m_result=result;
  if(memcmp(current,expected,32)) return m_result=Result::Stale;
  Table empty,candidate;result=empty.enroll(0,key,name,bytes,&candidate);
  return m_result=result==Result::Ok?start(candidate):result;
}
void Store::fail(Result result) {
  close();m_result=result;m_phase=Phase::Failed;
  // A failed rename/readback may have committed. No cached authority survives
  // that ambiguity; the owner must reload the canonical file before using it.
  if(m_commitStarted) { m_loaded=false;m_current={}; }
}
bool Store::cancel() {
  if(state()!=State::Busy || m_commitStarted) return false;
  int rc=close();
  if(rc<0) { fail(ioResult(rc));return false; }
  m_phase=Phase::Cancelled;m_result=Result::Cancelled;return true;
}
bool Store::compareChunk() {
  unsigned n=WireBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
  int rc=lfs_file_read(m_fs,&m_file,m_scratch,n);
  if(rc!=int(n) || memcmp(m_scratch,m_wire+m_cursor,n)) {
    fail(rc<0?ioResult(rc):Result::Corrupt);return false;
  }
  m_cursor+=n;return true;
}
void Store::step() {
  int rc=0;
  switch(m_phase) {
    case Phase::Create:
      rc=open(Pending,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC);
      if(rc<0) fail(ioResult(rc));else m_phase=Phase::Write;
      break;
    case Phase::Write: {
      unsigned n=WireBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      rc=lfs_file_write(m_fs,&m_file,m_wire+m_cursor,n);
      if(rc!=int(n)) { fail(rc<0?ioResult(rc):Result::Io);break; }
      m_cursor+=n;if(m_cursor==WireBytes) m_phase=Phase::CloseWrite;
      break;
    }
    case Phase::CloseWrite:
      rc=close();if(rc<0) fail(ioResult(rc));else m_phase=Phase::OpenVerify;
      break;
    case Phase::OpenVerify: case Phase::OpenReadback: {
      bool published=m_phase==Phase::OpenReadback;
      rc=open(published?Path:Pending,LFS_O_RDONLY);
      if(rc<0) { fail(ioResult(rc));break; }
      lfs_soff_t size=lfs_file_size(m_fs,&m_file);
      if(size!=WireBytes) { fail(size<0?ioResult(size):Result::Corrupt);break; }
      m_phase=published?Phase::Readback:Phase::Verify;break;
    }
    case Phase::Verify:
      if(compareChunk() && m_cursor==WireBytes) m_phase=Phase::CloseVerify;
      break;
    case Phase::CloseVerify:
      rc=close();if(rc<0) fail(ioResult(rc));else m_phase=Phase::Commit;
      break;
    case Phase::Commit:
      m_commitStarted=true;m_loaded=false;m_current={};
      rc=lfs_rename(m_fs,Pending,Path);
      if(rc<0) fail(ioResult(rc));else m_phase=Phase::OpenReadback;
      break;
    case Phase::Readback:
      if(compareChunk() && m_cursor==WireBytes) m_phase=Phase::CloseReadback;
      break;
    case Phase::CloseReadback:
      rc=close();if(rc<0) { fail(ioResult(rc));break; }
      m_result=decode(m_wire,WireBytes,&m_current);
      if(m_result!=Result::Ok) { fail(m_result);break; }
      m_loaded=true;m_phase=Phase::Done;break;
    default: break;
  }
}
}}

// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_archive_export.h"
namespace PrimeG2 { namespace AppArchive {
Export::Export(lfs_t *fs,AppDocumentStore::Store *documents):m_fs(fs),m_documents(documents),m_inspector(fs) {
  m_config.buffer=m_cache;
}
Export::State Export::state() const {
  switch(m_phase) {
  case Phase::Idle:return State::Idle;
  case Phase::Done:return State::Complete;
  case Phase::Cancelled:return State::Cancelled;
  case Phase::Failed:return State::Failed;
  case Phase::Header:case Phase::Pair:case Phase::Entry:case Phase::Trailer:
  case Phase::Package:case Phase::Private:return State::Readable;
  case Phase::File:return m_reader.state()==AppFileStore::Reader::State::Verifying?State::Working:State::Readable;
  default:return State::Working;
  }
}
bool Export::begin(const SourceInfo &source,uint8_t *scratch,uint32_t capacity,Verify verify,void *context) {
  State s=state();
  if(s==State::Readable || s==State::Working || !m_fs || !m_documents || !source.generation ||
     !scratch || capacity<MaximumPackage || !verify || !m_inspector.unchanged(source) ||
     m_documents->state()==AppDocumentStore::Store::State::Busy || m_documents->state()==AppDocumentStore::Store::State::Committing) return false;
  m_source=source;m_package=scratch;m_verify=verify;m_context=context;m_number=m_sent=0;m_header={};m_error=Error::None;
  memcpy(m_header.magic,"LFARCH1\0",8);m_header.schema=1;m_header.size=sizeof(m_header);m_header.bytes=sizeof(m_header);
  memcpy(m_header.id,source.id,strlen(source.id)+1);
  m_header.pairs=!source.legacy && (source.root.flags&AppDocumentRoot::PendingUpgrade)?2:1;
  m_header.flags=m_header.pairs==2?PendingUpgrade:0;memcpy(m_header.highVersion,source.root.highVersion,12);
  m_pairs[0]={};m_pairs[1]={};NativeAppHash::shaInit(&m_whole);m_phase=Phase::PreparePackage;return true;
}
bool Export::open(const char *path,uint32_t bytes,uint32_t offset) {
  if(m_open) return false;
  m_file={};m_open=lfs_file_opencfg(m_fs,&m_file,path,LFS_O_RDONLY,&m_config)==0;m_cursor=0;
  NativeAppHash::shaInit(&m_content);
  if(!m_open || lfs_file_size(m_fs,&m_file)!=static_cast<lfs_soff_t>(bytes)) return false;
  return !offset || lfs_file_seek(m_fs,&m_file,offset,LFS_SEEK_SET)==static_cast<lfs_soff_t>(offset);
}
bool Export::close() {
  if(!m_open) return true;
  int rc=lfs_file_close(m_fs,&m_file);m_open=false;return !rc;
}
void Export::fail(Error error) { close();m_reader.close();m_error=error;m_phase=Phase::Failed; }
void Export::cancel() {
  if(state()!=State::Working && state()!=State::Readable) return;
  bool ok=close();ok=m_reader.close() && ok;m_phase=ok?Phase::Cancelled:Phase::Failed;
  if(!ok) m_error=Error::IO;
}
void Export::frame(Phase next,const void *data,uint32_t bytes) {
  memcpy(m_frame,data,bytes);m_frameBytes=bytes;m_frameOffset=0;m_phase=next;
}
void Export::preparePair() {
  auto &p=m_pairs[m_number];const auto &index=m_index[m_number];
  uint32_t used=index.entry[0].bytes,bytes=sizeof(PairHeader)+p.packageBytes+used;
  for(unsigned i=1;i<index.entries;i++) {
    const auto &entry=index.entry[i];
    if(entry.bytes>MaximumData-used) { fail(Error::Format);return; }
    used+=entry.bytes;bytes+=sizeof(EntryHeader)+entry.bytes+(entry.kind==AppFileIndex::File?32:0);
  }
  if(!valid(p) || compare(p.version,m_header.highVersion)>0 ||
     (m_number && compare(p.version,m_pairs[0].version)>=0) || bytes>MaximumArchive-m_header.bytes) { fail(Error::Format);return; }
  m_header.bytes+=bytes;
  if(++m_number<m_header.pairs) m_phase=Phase::PreparePackage;
  else {
    if(!valid(m_header)) { fail(Error::Format);return; }
    m_number=0;frame(Phase::Header,&m_header,sizeof(m_header));
  }
}
void Export::nextFrame() {
  switch(m_phase) {
  case Phase::Header:frame(Phase::Pair,&m_pairs[m_number],sizeof(PairHeader));break;
  case Phase::Pair:m_phase=Phase::OpenPackage;break;
  case Phase::Entry:
    if(m_index[m_number].entry[m_entry].kind==AppFileIndex::File) m_phase=Phase::OpenFile;
    else {m_entry++;m_phase=Phase::NextEntry;}break;
  case Phase::Trailer:m_entry++;m_phase=Phase::NextEntry;break;
  default:break;
  }
}
int Export::read(void *out,uint32_t bytes) {
  State s=state();if(s==State::Working) return -2;if(s==State::Complete) return 0;
  if(s!=State::Readable || !out || !bytes || bytes>2048) return -1;
  uint32_t n=0;
  if(m_phase==Phase::Package || m_phase==Phase::Private) {
    n=m_contentBytes-m_cursor;if(n>bytes) n=bytes;
    if(lfs_file_read(m_fs,&m_file,out,n)!=static_cast<lfs_ssize_t>(n)) { fail(Error::IO);return -1; }
    NativeAppHash::shaUpdate(&m_content,static_cast<uint8_t *>(out),n);m_cursor+=n;
    if(m_cursor==m_contentBytes) m_phase=m_phase==Phase::Package?Phase::ClosePackage:Phase::ClosePrivate;
  } else if(m_phase==Phase::File) {
    int got=m_reader.read(out,bytes);
    if(got==-2) return -2;
    if(got<=0 || uint32_t(got)>m_contentBytes-m_cursor) { fail(Error::IO);return -1; }
    n=got;NativeAppHash::shaUpdate(&m_content,static_cast<uint8_t *>(out),n);m_cursor+=n;
    if(m_cursor==m_contentBytes) m_phase=Phase::CloseFile;
  } else {
    n=m_frameBytes-m_frameOffset;if(n>bytes) n=bytes;memcpy(out,m_frame+m_frameOffset,n);m_frameOffset+=n;
    if(m_frameOffset==m_frameBytes) nextFrame();
  }
  NativeAppHash::shaUpdate(&m_whole,static_cast<uint8_t *>(out),n);m_sent+=n;
  return n;
}
void Export::finishRaw(Phase next,const uint8_t expected[32]) {
  uint8_t digest[32];NativeAppHash::shaFinal(&m_content,digest);
  if(!close()) fail(Error::IO);else if(memcmp(digest,expected,32)) fail(Error::Integrity);else m_phase=next;
}
void Export::step() {
  switch(m_phase) {
  case Phase::PreparePackage: {
    if(!m_inspector.package(m_source,m_number,m_package,MaximumPackage)) { fail(Error::Integrity);break; }
    auto &p=m_pairs[m_number];p.size=sizeof(p);p.schema=1;p.packageBytes=m_source.legacy?m_source.packageBytes:pair().packageBytes;
    PackageInfo metadata;
    if(!m_verify(m_context,m_source.id,m_package,p.packageBytes,&metadata)) { fail(Error::Authority);break; }
    memcpy(p.version,metadata.version,12);p.dataSchema=m_source.legacy?metadata.schema:pair().dataSchema;
    if((m_number || m_header.pairs==1) && p.dataSchema!=metadata.schema) { fail(Error::Format);break; }
    NativeAppHash::sha256(m_package,p.packageBytes,p.packageHash);
    if(m_source.legacy) {
      memcpy(m_header.highVersion,p.version,12);NativeAppHash::shaInit(&m_legacy);NativeAppHash::shaUpdate(&m_legacy,m_package,p.packageBytes);
    }
    m_phase=Phase::PrepareIndex;break;
  }
  case Phase::PrepareIndex: {
    auto &index=m_index[m_number];auto &p=m_pairs[m_number];
    if(m_source.legacy) {index.clear();index.entry[0].bytes=m_source.legacyPrivateBytes;}
    else if(!m_documents->index(m_source.id,pair(),&index)) {fail(Error::Integrity);break;}
    p.privateBytes=index.entry[0].bytes;p.entries=index.entries-1;
    if(m_source.legacy) { m_phase=Phase::LegacyHash;break; }
    if(p.privateBytes) memcpy(p.privateHash,index.extent[0].hash,32);else NativeAppHash::sha256(nullptr,0,p.privateHash);
    preparePair();break;
  }
  case Phase::LegacyHash:
    if(!m_open) {
      char path[64];Source::canonicalPath(m_source.id,path);
      if(!open(path,64+m_source.packageBytes+m_source.legacyPrivateBytes,64+m_source.packageBytes)) fail(Error::IO);
    } else if(m_cursor<m_source.legacyPrivateBytes) {
      uint32_t n=m_source.legacyPrivateBytes-m_cursor;if(n>sizeof(m_scratch)) n=sizeof(m_scratch);
      if(lfs_file_read(m_fs,&m_file,m_scratch,n)!=static_cast<lfs_ssize_t>(n)) { fail(Error::IO);break; }
      NativeAppHash::shaUpdate(&m_content,m_scratch,n);NativeAppHash::shaUpdate(&m_legacy,m_scratch,n);m_cursor+=n;
    } else {
      uint8_t digest[32];NativeAppHash::shaFinal(&m_legacy,digest);NativeAppHash::shaFinal(&m_content,m_pairs[0].privateHash);
      if(!close()) fail(Error::IO);else if(memcmp(digest,m_source.canonical+24,32)) fail(Error::Integrity);else preparePair();
    }
    break;
  case Phase::OpenPackage: {
    char path[80];uint32_t size=m_pairs[m_number].packageBytes,offset=0;m_contentBytes=size;
    if(m_source.legacy) {Source::canonicalPath(m_source.id,path);size+=64+m_source.legacyPrivateBytes;offset=64;}
    else Source::objectPath(m_source.id,'p',pair().package,path);
    if(!open(path,size,offset)) fail(Error::IO);else m_phase=Phase::Package;break;
  }
  case Phase::ClosePackage:finishRaw(Phase::OpenPrivate,m_pairs[m_number].packageHash);break;
  case Phase::OpenPrivate: {
    m_entry=1;m_contentBytes=m_pairs[m_number].privateBytes;
    if(!m_contentBytes) {m_phase=Phase::NextEntry;break;}
    char path[80];uint32_t size=m_contentBytes,offset=0;
    if(m_source.legacy) {Source::canonicalPath(m_source.id,path);size+=64+m_source.packageBytes;offset=64+m_source.packageBytes;}
    else {const auto &extent=m_index[m_number].extent[0];Source::objectPath(m_source.id,extent.type==AppFileIndex::ChunkObject?'c':'d',extent.generation,path,extent.part);}
    if(!open(path,size,offset)) fail(Error::IO);else m_phase=Phase::Private;break;
  }
  case Phase::ClosePrivate:finishRaw(Phase::NextEntry,m_pairs[m_number].privateHash);break;
  case Phase::NextEntry:
    if(m_entry==m_index[m_number].entries) m_phase=Phase::FinishPair;
    else {
      const auto &entry=m_index[m_number].entry[m_entry];EntryHeader wire{};memcpy(wire.name,entry.name,strlen(entry.name)+1);
      wire.kind=entry.kind;wire.bytes=entry.bytes;frame(Phase::Entry,&wire,sizeof(wire));
    }
    break;
  case Phase::OpenFile: {
    AppDocumentRoot::Root selected=m_source.root;selected.current=pair();
    const auto &entry=m_index[m_number].entry[m_entry];
    if(!m_reader.open(m_fs,m_documents,m_source.id,entry.name,selected) || m_reader.size()!=entry.bytes) {fail(Error::IO);break;}
    m_contentBytes=entry.bytes;m_cursor=0;NativeAppHash::shaInit(&m_content);
    m_phase=m_contentBytes?Phase::File:Phase::CloseFile;break;
  }
  case Phase::File:m_reader.step();if(m_reader.state()==AppFileStore::Reader::State::Failed) fail(Error::Integrity);break;
  case Phase::CloseFile: {
    uint8_t digest[32];NativeAppHash::shaFinal(&m_content,digest);
    if(!m_reader.close()) fail(Error::IO);else frame(Phase::Trailer,digest,32);break;
  }
  case Phase::FinishPair:
    if(++m_number<m_header.pairs) frame(Phase::Pair,&m_pairs[m_number],sizeof(PairHeader));
    else if(m_sent!=m_header.bytes || !m_inspector.unchanged(m_source)) fail(Error::Changed);
    else {NativeAppHash::shaFinal(&m_whole,m_digest);m_phase=Phase::Done;}
    break;
  default:break;
  }
}
}}

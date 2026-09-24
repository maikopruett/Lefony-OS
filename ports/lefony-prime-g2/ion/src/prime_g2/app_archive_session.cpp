// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_archive_session.h"
namespace PrimeG2 { namespace AppArchive {
using TS=TransferState;
using TE=TransferError;
Session::Session(AppStorage::Volume &volume,uint8_t *upload,uint8_t *inspection,uint32_t capacity,Hooks hooks):
  m_volume(volume),m_source(&volume.m_fs),m_export(&volume.m_fs,&volume.m_documents),m_restore(&volume.m_fs,&volume.m_documents),
  m_upload(upload),m_inspection(inspection),m_capacity(capacity),m_hooks(hooks) {}
bool Session::valid(const Request &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || !padded(r.id,sizeof(r.id)) || !Source::name(r.id) ||
     !zero(r.reserved,sizeof(r.reserved)) || zero(r.nonce,16)) return false;
  if(r.operation==Operation::Restore) return !(r.flags&~(Replace|AllowRecoveryPair|RepairCode)) &&
    (!(r.flags&RepairCode) || ((r.flags&Replace) && !(r.flags&AllowRecoveryPair))) &&
    r.length>=128+128+468 && r.length<=MaximumArchive;
  return (r.operation==Operation::Inspect || r.operation==Operation::Export) &&
    !(r.flags&~(r.operation==Operation::Inspect?(RepairCode|InspectRoot):0u)) && !r.length && zero(r.digest,32) &&
    (r.operation!=Operation::Inspect || !r.generation);
}
TransferStatus Session::status() const {
  auto result=m_status;if(m_command) {result.state=TS::Working;result.available=0;}return result;
}
bool Session::needsPolling(uint32_t now) const {
  if(!m_active) return false;
  return m_cancel || (m_command && m_acknowledged) || m_step==Step::Initialize || m_step==Step::Write ||
    m_step==Step::Publish || m_step==Step::Drain || (m_step==Step::Export && m_status.state==TS::Working) ||
    expired(now);
}
bool Session::request(uint8_t command,uint32_t arg,const uint8_t *data,size_t bytes) {
  if(command==0x91) {
    if(arg || !data || bytes!=sizeof(Request) || m_command) return false;
    Request r;memcpy(&r,data,sizeof(r));if(!valid(r)) return false;
    if(m_status.sequence && !memcmp(r.nonce,m_request.nonce,16)) return !memcmp(&r,&m_request,sizeof(r));
    if(m_active || m_status.sequence==0xffffffffu || !m_upload || !m_inspection || m_capacity<MaximumPackage ||
       !m_hooks.verify || !m_hooks.sameAuthority || !m_hooks.trustRevision) return false;
    uint32_t sequence=m_status.sequence+1;m_request=r;m_status={};m_status.sequence=sequence;m_status.state=TS::Working;
    m_status.operation=r.operation;m_status.length=r.length;memcpy(m_status.nonce,r.nonce,16);
    m_active=true;m_command=command;m_acknowledged=m_cancel=m_restoreStarted=m_commitRequested=false;
    m_step=Step::None;m_fill=m_inputBytes=m_inputUsed=0;m_policyError=TE::None;
    m_consentRequired=m_presented=m_rendered=m_released=false;m_physical=0;m_approval={};
    m_repairInfo={};m_legacyPrefixProved=false;
    m_approval.sequence=sequence;memcpy(m_approval.id,r.id,sizeof(r.id));
    memcpy(m_approval.digest,r.digest,32);memcpy(m_approval.nonce,r.nonce,16);return true;
  }
  if(!m_active || m_command || m_cancel) return false;
  if(command==0x94 || command==0x95) {
    if(arg!=m_status.sequence || !data || bytes!=16 || memcmp(data,m_request.nonce,16)) return false;
    if(command==0x94 && (m_request.operation!=Operation::Restore || m_status.state!=TS::Ready)) return false;
    if(command==0x95 && m_commitRequested) return false;
  } else if(command==0x92 || command==0x93) {
    if(arg || !data || bytes<24 || AppFileIndex::get(data)!=m_status.sequence || memcmp(data+8,m_request.nonce,16)) return false;
    uint32_t offset=AppFileIndex::get(data+4);
    if(command==0x92) {
      if(m_request.operation!=Operation::Restore || m_status.state!=TS::Writable || offset!=m_status.offset || bytes<=24 || bytes>512 || bytes-24>m_status.length-offset) return false;
      m_inputBytes=bytes-24;m_inputUsed=0;memcpy(m_input,data+24,m_inputBytes);
    } else {
      if(bytes!=24 || m_status.state!=TS::Readable || offset!=m_status.offset+m_status.available) return false;
      m_ackOffset=offset;
    }
  } else return false;
  m_command=command;m_acknowledged=false;return true;
}
bool Session::response(uint8_t command,uint32_t arg,uint8_t *out,size_t capacity,size_t *bytes) const {
  if(!out || !bytes) return false;
  if(command==0x90) {
    if(arg || capacity!=sizeof(TransferStatus)) return false;
    auto value=status();memcpy(out,&value,sizeof(value));*bytes=sizeof(value);return true;
  }
  if(command==0x96) {
    if(!m_active || m_command || !m_consentRequired || arg!=m_status.sequence || capacity!=sizeof(ApprovalInfo) ||
       (m_status.state!=TS::AwaitUser && m_status.state!=TS::Ready)) return false;
    memcpy(out,&m_approval,sizeof(m_approval));*bytes=sizeof(m_approval);return true;
  }
  if(command!=0x92 || !m_active || m_command || arg!=m_status.sequence || m_status.state!=TS::Readable || capacity!=m_status.available) return false;
  memcpy(out,m_reply,capacity);*bytes=capacity;return true;
}
void Session::abandonSetup() {
  if(m_command && !m_acknowledged) {
    if(m_command==0x91) m_cancel=true;
    m_command=0;
  }
}
void Session::disconnect() {
  if(m_active && !m_commitRequested && !commitAcknowledged()) m_cancel=true;
}
bool Session::expired(uint32_t now) const {
  if(m_commitRequested || commitAcknowledged() || m_command) return false;
  return (m_status.state==TS::Readable || m_status.state==TS::Writable || m_status.state==TS::Ready || m_status.state==TS::AwaitUser) &&
    uint32_t(now-m_lastProgress)>=(m_status.state==TS::AwaitUser?120000u:30000u);
}
bool Session::present() {
  if(!needsPresentation()) return false;
  m_presented=true;m_rendered=m_released=false;return true;
}
void Session::rendered() {if(m_presented && m_status.state==TS::AwaitUser) m_rendered=true;}
void Session::observeKeyboard(uint64_t physical) {
  m_physical=physical;
  if(m_rendered && m_status.state==TS::AwaitUser && !physical) m_released=true;
}
bool Session::approve(uint32_t now) {
  poll(now);
  if(m_status.state!=TS::AwaitUser || !m_presented || !m_rendered || !m_released || m_physical!=(uint64_t(1)<<56)) return false;
  if(!unchanged(this)) {stop(TE::Changed);return true;}
  m_status.state=TS::Ready;m_lastProgress=now;m_rendered=m_released=false;return true;
}
void Session::dismiss() {
  if(m_active && m_consentRequired && !m_commitRequested && !commitAcknowledged()) m_cancel=true;
  m_presented=m_rendered=m_released=false;
}
void Session::deny() {if(m_active && m_status.state==TS::AwaitUser) stop(TE::Denied);}
bool Session::exportVerify(void *opaque,const char *id,const uint8_t *package,uint32_t bytes,PackageInfo *out) {
  auto &self=*static_cast<Session *>(opaque);
  return self.m_hooks.verify(self.m_hooks.context,id,package,bytes,true,false,out);
}
bool Session::unchanged(void *opaque) {
  auto &self=*static_cast<Session *>(opaque);
  self.m_volume.refreshMetadata();
  return self.m_hooks.trustRevision(self.m_hooks.context)==self.m_trustRevision && self.m_source.unchanged(self.m_before);
}
bool Session::admit(void *opaque,uint32_t bytes) {
  auto &self=*static_cast<Session *>(opaque);AppStorage::Space space;
  if(!self.m_volume.space(&space)) {self.m_policyError=TE::IO;return false;}
  constexpr uint32_t block=AppStorage::BlockBytes;
  uint32_t total=space.capacity+(self.m_before.generation?AppStorage::ReserveBlocks*block:0);
  // Directory/commit reserve plus the separate FILE5 root payload block.
  uint32_t needed=7+(bytes?(bytes+64+(block-128)-1)/(block-128):0);
  if(space.allocated>total || needed>(total-space.allocated)/block) {self.m_policyError=TE::Space;return false;}
  return true;
}
bool Session::authenticate(void *opaque,const Header &h,const PairHeader &p,unsigned number,const uint8_t *package) {
  auto &self=*static_cast<Session *>(opaque);PackageInfo metadata;
  if(!self.m_hooks.verify(self.m_hooks.context,h.id,package,p.packageBytes,number!=0,true,&metadata)) {self.m_policyError=TE::Authority;return false;}
  if(compare(metadata.version,p.version) || ((number || h.pairs==1) && metadata.schema!=p.dataSchema)) {self.m_policyError=TE::Schema;return false;}
  if(!number) {
    memcpy(self.m_currentSigner,package+24,32);
    memcpy(self.m_approval.currentSigner,package+24,32);memcpy(self.m_approval.version,metadata.version,12);
    if(self.m_request.flags&RepairCode) {
      // Authenticate the replacement first, then bind it to the surviving
      // installed identity. Repair never permits a different/newer package.
      if(p.packageBytes!=self.m_info.packageBytes) {self.m_policyError=TE::Version;return false;}
      if(!self.m_before.legacy) {
        if(memcmp(p.packageHash,self.m_info.packageHash,32)) {self.m_policyError=TE::Version;return false;}
      } else {
        uint8_t prefix[32];NativeAppHash::sha256(package,Source::SignedPrefixBytes,prefix);
        self.m_legacyPrefixProved=(self.m_info.flags&PrefixKnown) && !memcmp(prefix,self.m_repairInfo.prefixHash,32);
        if(!self.m_legacyPrefixProved && p.privateBytes!=self.m_before.legacyPrivateBytes) {self.m_policyError=TE::Authority;return false;}
      }
    } else if(self.m_before.generation) {
      if(!self.m_hooks.sameAuthority(self.m_hooks.context,self.m_info.signer,package+24)) {self.m_policyError=TE::Authority;return false;}
      int order=compare(metadata.version,self.m_info.version);
      if((!order && (p.packageBytes!=self.m_info.packageBytes || memcmp(p.packageHash,self.m_info.packageHash,32))) ||
         (order && compare(metadata.version,self.m_info.highVersion)<=0)) {self.m_policyError=TE::Version;return false;}
    }
  } else if(!self.m_hooks.sameAuthority(self.m_hooks.context,self.m_currentSigner,package+24)) {
    // A retained package under a different developer key must be the exact
    // recovery pair already authorized on this calculator. An arbitrary old
    // signed package must not become a cross-signer takeover through rollback.
    const auto &old=self.m_before.root.previous;
    if(!(self.m_before.root.flags&AppDocumentRoot::PendingUpgrade) || old.packageBytes!=p.packageBytes || memcmp(old.packageHash,p.packageHash,32)) {
      if(self.m_before.generation || !(self.m_request.flags&AllowRecoveryPair) || !self.m_hooks.developerKey ||
         !self.m_hooks.developerKey(self.m_hooks.context,self.m_currentSigner) || !self.m_hooks.developerKey(self.m_hooks.context,package+24)) {
        self.m_policyError=TE::Authority;return false;
      }
      // Stage both authenticated pairs, but never expose COMMIT until the full
      // archive hash has verified and the OS has approved these exact identities.
      self.m_consentRequired=true;self.m_status.flags|=RecoveryPair;
      memcpy(self.m_approval.previousSigner,package+24,32);memcpy(self.m_approval.previousVersion,metadata.version,12);
    }
  }
  return true;
}
bool Session::privateVerified(void *opaque,const PairHeader &,unsigned number,const uint8_t *combined) {
  auto &self=*static_cast<Session *>(opaque);
  if(number || !(self.m_request.flags&RepairCode) || !self.m_before.legacy || self.m_legacyPrefixProved) return true;
  if(memcmp(combined,self.m_repairInfo.legacyHash,32)) {self.m_policyError=TE::Authority;return false;}
  return true;
}
void Session::initialize(uint32_t now) {
  if(!m_volume.documentReady()) {stop(TE::Busy);return;}
  for(const auto &reader:m_volume.m_readers) if(reader.state()!=AppFileStore::Reader::State::Closed) {stop(TE::Busy);return;}
  m_volume.refreshMetadata();
  m_info={};memcpy(m_info.id,m_request.id,strlen(m_request.id)+1);m_info.quota=AppFileStore::QuotaBytes;
  bool repair=m_request.flags&RepairCode;
  auto found=m_source.inspect(m_request.id,&m_before,repair);
  if(found!=Source::Result::Ok && found!=Source::Result::Missing) {
    stop(found==Source::Result::IO?TE::IO:TE::Integrity);return;
  }
  m_trustRevision=m_hooks.trustRevision(m_hooks.context);
  if(found==Source::Result::Ok) {
    PackageInfo metadata;
    bool readable=m_source.package(m_before,0,m_inspection,m_capacity) && exportVerify(this,m_request.id,m_inspection,m_before.packageBytes,&metadata);
    if(!readable && !repair) {stop(TE::Authority);return;}
    m_info.flags=Exists;m_info.generation=m_before.generation;m_info.packageBytes=m_before.packageBytes;
    if((m_request.flags&InspectRoot) && m_before.rootCopies!=AppRootRecord::Copies::Legacy) {
      m_info.flags|=RootReplicated;
      if(m_before.rootCopies!=AppRootRecord::Copies::Attribute)m_info.flags|=RootPayloadValid;
      if(m_before.rootCopies!=AppRootRecord::Copies::Payload)m_info.flags|=RootAttributeValid;
    }
    if(readable) {
      memcpy(m_info.version,metadata.version,12);m_info.appSchema=metadata.schema;
      m_info.dataSchema=m_before.legacy?metadata.schema:m_before.root.current.dataSchema;
      memcpy(m_info.highVersion,m_before.legacy?metadata.version:m_before.root.highVersion,12);
      NativeAppHash::sha256(m_inspection,m_before.packageBytes,m_info.packageHash);memcpy(m_info.signer,m_inspection+24,32);
    } else {
      m_info.flags|=CodeUnavailable;
      if(m_before.legacy) {
        m_info.flags|=Legacy;m_info.privateBytes=m_before.legacyPrivateBytes;
        memcpy(m_repairInfo.legacyHash,m_before.canonical+24,32);
        if(m_source.legacyPrefix(m_before,m_repairInfo.prefixHash)) m_info.flags|=PrefixKnown;
      } else {
        m_info.dataSchema=m_before.root.current.dataSchema;
        memcpy(m_info.highVersion,m_before.root.highVersion,12);memcpy(m_info.packageHash,m_before.root.current.packageHash,32);
      }
    }
    if(m_before.root.flags&AppDocumentRoot::PendingUpgrade) m_info.flags|=Pending;
    AppStorage::Volume::FileUsage usage;
    if(m_volume.fileUsage(m_request.id,&usage)) {
      m_info.flags|=IndexKnown;m_info.privateBytes=usage.data.privateBytes;m_info.namedBytes=usage.data.namedBytes;
      uint32_t used=m_info.privateBytes+m_info.namedBytes;if(used>m_info.quota) m_info.quota=used;
    }
  }
  m_status.generation=m_info.generation;m_lastProgress=now;
  if(m_request.operation==Operation::Inspect) {
    if(repair) {
      m_repairInfo.info=m_info;m_repairInfo.info.size=sizeof(RepairInfo);m_repairInfo.info.schema=2;
      memcpy(m_reply,&m_repairInfo,sizeof(m_repairInfo));m_status.length=m_status.available=sizeof(m_repairInfo);
    } else {memcpy(m_reply,&m_info,sizeof(m_info));m_status.length=m_status.available=sizeof(m_info);}
    NativeAppHash::sha256(m_reply,m_status.length,m_status.digest);m_status.state=TS::Readable;m_step=Step::None;return;
  }
  if(m_request.generation!=m_before.generation) {stop(TE::Changed);return;}
  if(m_request.operation==Operation::Export) {
    if(found!=Source::Result::Ok) {stop(TE::Missing);return;}
    if(!m_export.begin(m_before,m_inspection,m_capacity,exportVerify,this)) {stop(TE::IO);return;}
    m_step=Step::Export;return;
  }
  if(found==Source::Result::Ok && (m_request.flags&AllowRecoveryPair)) {stop(TE::Exists);return;}
  if(found==Source::Result::Ok && !(m_request.flags&Replace)) {stop(TE::Exists);return;}
  if(repair) {
    if(found!=Source::Result::Ok) {stop(TE::Missing);return;}
    if(!(m_info.flags&CodeUnavailable)) {stop(TE::Invalid);return;}
    m_status.flags|=CodeRepair;
  }
  auto before=m_before.root;memcpy(before.highVersion,m_info.highVersion,12);
  if(!m_restore.begin(m_request.id,before,m_before.generation,m_info.quota,m_request.length,m_request.digest,m_upload,m_capacity,
      {this,authenticate,unchanged,admit,privateVerified,repair && m_before.legacy})) {stop(TE::Changed);return;}
  m_restoreStarted=true;m_status.state=TS::Writable;m_step=Step::None;
}
void Session::stop(TransferError error) {
  m_status.error=error;m_status.available=0;m_status.state=TS::Working;m_command=0;m_acknowledged=false;m_cancel=false;
  if(m_restoreStarted) m_restore.cancel();
  m_export.cancel();m_step=Step::Drain;
}
void Session::finish() {
  m_active=false;m_step=Step::None;m_command=0;m_acknowledged=false;m_status.available=0;
  m_status.state=m_status.error==TE::None?TS::Complete:
    (m_status.error==TE::Cancelled || m_status.error==TE::Timeout)?TS::Cancelled:TS::Failed;
}
void Session::exportStep(uint32_t now) {
  auto s=m_export.state();using S=AppArchive::Export::State;
  if(s==S::Failed) {stop(m_export.error()==AppArchive::Export::Error::Authority?TE::Authority:TE::Integrity);return;}
  if(s==S::Working) {m_export.step();return;}
  m_status.length=m_export.bytes();
  if(s==S::Complete) {
    if(!m_fill) {memcpy(m_status.digest,m_export.digest(),32);finish();return;}
  } else {
    int n=m_export.read(m_reply+m_fill,sizeof(m_reply)-m_fill);
    if(n==-2) return;
    if(n<=0) {stop(TE::Integrity);return;}
    m_fill+=n;
  }
  if(m_fill==sizeof(m_reply) || m_export.state()==S::Complete) {
    m_status.available=m_fill;m_status.state=TS::Readable;m_lastProgress=now;
  }
}
void Session::restoreStep(uint32_t now) {
  using S=AppArchive::Restore::State;
  auto state=m_restore.state();
  if(state==S::Failed || state==S::Cancelled) {
    auto error=m_restore.error();
    if(error==AppArchive::Restore::Error::CommitUnknown) {m_status.flags|=CommitUncertain;stop(TE::Uncertain);return;}
    TE mapped=m_policyError!=TE::None?m_policyError:error==AppArchive::Restore::Error::Space?TE::Quota:
      error==AppArchive::Restore::Error::Changed?TE::Changed:error==AppArchive::Restore::Error::IO?TE::IO:TE::Integrity;
    stop(mapped);return;
  }
  if(state==S::Complete) {
    SourceInfo result;uint8_t expected[AppDocumentRoot::Bytes];
    if(m_source.inspect(m_request.id,&result)!=Source::Result::Ok || result.legacy ||
       !AppDocumentRoot::encode(m_restore.result(),expected) || memcmp(expected,result.canonical,sizeof(expected))) {
      m_status.flags|=CommitUncertain;stop(TE::Uncertain);return;
    }
    m_status.flags|=Committed;m_status.generation=result.generation;memcpy(m_status.digest,m_request.digest,32);finish();return;
  }
  if(state==S::Working || state==S::Committing) {m_restore.step();return;}
  if(m_inputUsed<m_inputBytes) {
    int n=m_restore.write(m_input+m_inputUsed,m_inputBytes-m_inputUsed);
    if(n<0) {if(n!=-2) stop(TE::Invalid);return;}
    m_inputUsed+=n;
  }
  if(m_inputUsed==m_inputBytes) {
    // Staged work after the final bytes must finish before COMMIT is offered.
    if(m_restore.state()==S::Working) return;
    m_status.offset=m_restore.received();m_status.state=m_restore.state()==S::Ready?TS::Ready:TS::Writable;
    if(m_status.state==TS::Ready) {
      memcpy(m_status.digest,m_request.digest,32);
      if(m_consentRequired) m_status.state=TS::AwaitUser;
    }
    m_lastProgress=now;m_step=Step::None;
  }
}
void Session::poll(uint32_t now) {
  if(!m_active) return;
  if(m_cancel || expired(now)) {
    stop(m_cancel?TE::Cancelled:TE::Timeout);
  }
  if(m_command && m_acknowledged) {
    uint8_t command=m_command;m_command=0;m_acknowledged=false;m_lastProgress=now;
    if(command==0x91) m_step=Step::Initialize;
    else if(command==0x95) stop(TE::Cancelled);
    else if(command==0x92) {m_status.state=TS::Working;m_step=Step::Write;}
    else if(command==0x93) {
      m_status.offset=m_ackOffset;m_status.available=0;m_fill=0;
      if(m_request.operation==Operation::Inspect) {finish();return;}
      m_status.state=TS::Working;m_step=Step::Export;
    } else if(command==0x94) {
      m_commitRequested=true;m_status.state=TS::Working;m_step=Step::Publish;
      if(!m_restore.commit()) {restoreStep(now);return;}
    }
  }
  if(m_step==Step::Initialize) initialize(now);
  else if(m_step==Step::Export && m_status.state==TS::Working) exportStep(now);
  else if(m_step==Step::Write || m_step==Step::Publish) restoreStep(now);
  else if(m_step==Step::Drain) {
    using S=AppArchive::Restore::State;
    auto state=m_restore.state();
    if(m_restoreStarted && (state==S::Working || state==S::Committing)) {m_restore.step();return;}
    if(m_restoreStarted && m_restore.cleanupFailed() && m_status.error==TE::Cancelled) m_status.error=TE::IO;
    finish();
  }
}
}}

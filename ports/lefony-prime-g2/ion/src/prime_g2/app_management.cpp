// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_management.h"
#include "app_storage.h"
#include "app_file_session.h"
#include "app_file_exchange.h"
#include "app_data_session.h"
#include "app_developer_key_session.h"
#include "app_archive_session.h"
#include <ion/timing.h>
#include "app_icon.h"
#include "native_app.h"
#include "native_app_manifest.h"
#include "native_app_signature.h"
#include "nand_physical.h"
#include "development_update.h"
#include "registers.h"
#include "services.h"
#include <string.h>
namespace PrimeG2 { namespace AppManagement {
static AppDeveloperKeys::Error prepareRecovery(const AppDeveloperKeys::Request &,const AppDeveloperKeys::Table &,AppDeveloperKeys::RecoveryInfo *);
static AppDeveloperKeys::Error beginRecovery(const AppDeveloperKeys::Request &,const AppDeveloperKeys::Table &,const AppDeveloperKeys::RecoveryInfo &);
static AppDeveloperKeys::State stepRecovery(AppDeveloperKeys::Error *);
static bool cancelRecovery();
static void finishRecovery(AppDeveloperKeys::State);
static AppDeveloperKeys::Error removableKey(const uint8_t *,const AppDeveloperKeys::Table &);
static bool archiveVerify(void *,const char *,const uint8_t *,uint32_t,bool,bool,AppArchive::PackageInfo *);
static bool archiveSameAuthority(void *,const uint8_t *,const uint8_t *);
static uint32_t archiveTrustRevision(void *);
static bool archiveDeveloperKey(void *,const uint8_t *);
namespace {
static_assert(sizeof(CatalogEntry)==168,"app catalog protocol layout");
static_assert(offsetof(CatalogEntry,metadata)==8 && offsetof(Metadata,id)==4 && offsetof(Metadata,name)==53 && offsetof(Metadata,version)==134,"app catalog text offsets");
using namespace AppStorage;
static_assert(MaximumEntries==MaximumIcons,"menu cache bounds");
alignas(64) uint8_t sRaw[2176];
bool range(uint32_t block) { return block>=FirstBlock && block<FirstBlock+BlockCount; }
bool usable(void *,uint32_t block) {
  if(!range(block)) return false;
#if PRIME_G2_EMULATOR
  reg32(GPMI+0x104)=block*PagesPerBlock; return !reg32(GPMI+0x128);
#else
  return NANDPhysical::appBlockUsable(block);
#endif
}
bool read(void *,uint32_t page,uint8_t *data) {
  if(!range(page/PagesPerBlock)) return false;
#if PRIME_G2_EMULATOR
  reg32(GPMI+0x100)=0; reg32(GPMI+0x104)=page;
  for(unsigned i=0;i<PageBytes;i+=4) { uint32_t word=reg32(GPMI+0x14c); memcpy(data+i,&word,4); }
  return !reg32(GPMI+0x148);
#else
  if(!NANDPhysical::readAppPage(page)) {
    // BCH qualification rejects erased pages. littlefs must see an exact
    // erased page, but transport/geometry faults and non-erased damage fail.
    if(NANDPhysical::pageReport().error!=static_cast<uint32_t>(NANDPhysical::Error::Uncorrectable) ||
        !NANDPhysical::readRawAppPage(page,sRaw) || !NANDPhysical::erasedRawAppPage(sRaw)) return false;
    memset(data,0xff,PageBytes);return true;
  }
  memcpy(data,NANDPhysical::pageData(),PageBytes); return true;
#endif
}
bool erase(void *,uint32_t block) {
  if(!range(block)) return false;
#if PRIME_G2_EMULATOR
  reg32(GPMI+0x104)=block*PagesPerBlock; reg32(GPMI+0x100)=0xd0; return !(reg32(GPMI+0x10c)&1);
#else
  return NANDPhysical::eraseAppBlock(block);
#endif
}
bool program(void *,uint32_t page,const uint8_t *data) {
  if(!range(page/PagesPerBlock)) return false;
#if PRIME_G2_EMULATOR
  reg32(GPMI+0x104)=page; reg32(GPMI+0x100)=0x80;
  for(unsigned i=0;i<PageBytes;i+=4) { uint32_t word; memcpy(&word,data+i,4); reg32(GPMI+0x14c)=word; }
  reg32(GPMI+0x100)=0x10; return !(reg32(GPMI+0x10c)&1);
#else
  return NANDPhysical::programAppPage(page,data);
#endif
}
AppFileStore::ReadCache sReadCache;
Volume sVolume({nullptr,usable,read,erase,program},&sReadCache);
AppDeveloperKeys::Controller sKeys(sVolume,{prepareRecovery,beginRecovery,stepRecovery,cancelRecovery,finishRecovery,removableKey});
bool sRecoveryConverting=false;
uint32_t sObservedKeySequence=0;AppDeveloperKeys::State sObservedKeyState=AppDeveloperKeys::State::Idle;
AppFiles::Session sFiles(sVolume);
AppData::Session sData(sVolume,sFiles);
AppFileExchange::Session sExchange(sVolume);
AppFileExchange::Request sExchangeRequest{};
CatalogEntry sCatalog[MaximumEntries]={};
uint8_t sAppHashes[MaximumEntries][32], sIconHashes[MaximumEntries][32];
uint8_t sIcons[MaximumEntries][AppIcon::CompressedBytes], sIconPackage[AppIcon::PackageBytes];
bool sHasIcon[MaximumEntries]={};
alignas(64) uint8_t sUpload[MaximumPackage],sLoaded[MaximumPackage];
AppArchive::Session sArchive(sVolume,sUpload,sLoaded,sizeof(sUpload),{nullptr,archiveVerify,archiveSameAuthority,archiveTrustRevision,archiveDeveloperKey});
uint8_t sUploadData[MaximumData],sBackupDigest[32];
uint32_t sRevision=0,sCount=0,sUsed=0;
uint32_t sUnavailable=0;
uint32_t sLoadedSchema=0;
Space sSpace={};
NativeAppHash::SHA256 sBackupHash;
// Wire state is independent of the storage engine's internal states.
enum : uint32_t { Cold,Unprovisioned,Ready,Backup,Receiving,Working,Complete,Error };
uint32_t sState=Cold,sError=0,sReceived=0,sLength=0,sBackupOffset=0;
uint32_t sLoadedBytes=0,sPendingArgument=0,sTarget=0;
uint8_t sPending=0;
bool sAcknowledged=false,sExplicitData=false,sEndFilesQueued=false;
int sOpen=-1;
bool sClosing=false,sSaveOnClose=false;
AppInstallProgress::Tracker sInstallProgress;
bool sInstallData=false;
uint8_t sHomeOrder[AppStorage::Volume::MaximumHomeOrder]{},sHomePending[AppStorage::Volume::MaximumHomeOrder]{};
uint32_t sHomeBytes=0,sHomePendingBytes=0;
bool sHomeSaving=false,sHomeStarted=false,sHomeFailed=false;
unsigned sCloseSlot=0;
constexpr uint32_t RawBytes=2112,BackupBytes=BlockCount*PagesPerBlock*RawBytes;
uint32_t word(const uint8_t *p) { uint32_t value;memcpy(&value,p,4);return value; }
void fail(uint32_t error) { sInstallProgress.finish(false);sState=Error;sError=error;sPending=0;sAcknowledged=false; }
bool idle() { return sState==Ready || sState==Complete; }
void versionParts(const char *text,uint32_t parts[3]) {
  for(unsigned i=0;i<3;i++) {
    parts[i]=0;while(*text>='0' && *text<='9') parts[i]=parts[i]*10+(*text++-'0');
    if(*text=='.') text++;
  }
}
bool appName(const uint8_t *package,size_t size,char id[49]) {
  Metadata m;if(!metadata(package,size,&m)) return false;memcpy(id,m.id,49);return true;
}
bool catalogFile(void *,const char *id,const Entry &e) {
  if(sCount>=MaximumEntries) return false;
  Metadata m;
  if(!sVolume.read(id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) || !metadata(sLoaded,e.packageBytes,&m,false,true) || strcmp(id,m.id)) {
    // An unavailable developer key or damaged package cannot prevent unrelated
    // authenticated apps from appearing. Never use unauthenticated metadata.
    sUnavailable++;return true;
  }
  NativeAppHash::sha256(sLoaded,e.packageBytes,sAppHashes[sCount]);
  sHasIcon[sCount]=false; memset(sIconHashes[sCount],0,32);
  Entry icon;
  if(sVolume.entry(id,&icon,true)) {
    sUsed+=icon.packageBytes+icon.dataBytes;
    if(icon.packageBytes==AppIcon::PackageBytes && !icon.dataBytes &&
        sVolume.read(id,sIconPackage,sizeof(sIconPackage),nullptr,0,true)) {
      const uint8_t *pixels=AppIcon::pixels(sIconPackage,sizeof(sIconPackage),sAppHashes[sCount],Services::noteVerificationProgress);
      if(pixels) {
        AppIcon::compress(pixels,sIcons[sCount]); sHasIcon[sCount]=true;
        NativeAppHash::sha256(sIconPackage,sizeof(sIconPackage),sIconHashes[sCount]);
      }
    }
  }
  sCatalog[sCount++]={e.packageBytes,e.generation,m};sUsed+=e.packageBytes+e.dataBytes;return true;
}
void refresh() {
  sRevision++;sCount=0;sUsed=0;sUnavailable=0;memset(sCatalog,0,sizeof(sCatalog));
  if(!sVolume.list(catalogFile,nullptr,true) || !sVolume.space(&sSpace)) fail(4);
  sLoadedBytes=0;
}
bool queue(uint8_t command,uint32_t argument) {
  if(sPending) return false;
  sPending=command; sPendingArgument=argument;sAcknowledged=false;return true;
}
}
bool unwrap(const uint8_t *package,size_t size,const uint8_t **payload,size_t *bytes,bool inspect) {
  if(NativeAppSignature::unwrap(package,size,payload,bytes,Services::noteVerificationProgress)) return true;
  const auto *table=sKeys.table();
  return table && table->unwrap(package,size,inspect?AppDeveloperKeys::Purpose::Inspect:AppDeveloperKeys::Purpose::Execute,payload,bytes,Services::noteVerificationProgress);
}
static bool parseMetadata(const uint8_t *package,size_t size,Metadata *out,bool requireSupported,uint32_t *dataSchema,uint32_t *features=nullptr,bool inspect=false) {
  const uint8_t *payload;size_t bytes;
  if(!out || !unwrap(package,size,&payload,&bytes,inspect) || bytes<64 || memcmp(payload,"LFAPP0\0\0",8) || word(payload+8)>1 || word(payload+20)>1 || word(payload+56) || word(payload+60)) return false;
  uint32_t length=word(payload+12),image=word(payload+16);
  if(!length || length>4096 || image<52 || image>2*1024*1024 || bytes!=64+length+image || word(package+16)!=word(payload+20)) return false;
  uint8_t hash[32];NativeAppHash::sha256(payload+64,bytes-64,hash);
  if(memcmp(hash,payload+24,32)) return false;
  NativeAppManifest::Manifest m;
  if(!NativeAppManifest::parse(payload+64,length,word(payload+8),word(payload+20),&m) ||
      (requireSupported && !NativeAppManifest::supported(m))) return false;
  if(dataSchema) *dataSchema=m.dataSchema;
  if(features) *features=m.required|m.optional;
  out->abi=m.abi;memcpy(out->id,m.id,sizeof(out->id));memcpy(out->name,m.name,sizeof(out->name));
  memcpy(out->version,m.version,sizeof(out->version));return true;
}
bool metadata(const uint8_t *package,size_t size,Metadata *out,bool requireSupported,bool inspect) {
  return parseMetadata(package,size,out,requireSupported,nullptr,nullptr,inspect);
}
static AppDeveloperKeys::Error removableKey(const uint8_t *id,const AppDeveloperKeys::Table &) {
  struct Scan {const uint8_t *id;};Scan scan{id};
  // Visit occupied namespaces, including quarantined ones. If an identity or
  // retained package cannot be authenticated, deletion must fail closed.
  bool safe=sVolume.list([](void *context,const char *name,const Entry &entry) {
    const auto *id=static_cast<Scan *>(context)->id;Metadata m;
    if(!sVolume.read(name,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) ||
       !metadata(sLoaded,entry.packageBytes,&m,false,true) || strcmp(name,m.id) || !memcmp(sLoaded+24,id,32)) return false;
    AppDocumentRoot::Root root;
    if(sVolume.documentRoot(name,&root) && root.previous.package && root.previous.package!=root.current.package) {
      Entry previous;
      if(!sVolume.recoveryPackage(name,sLoaded,sizeof(sLoaded),&previous) ||
         !metadata(sLoaded,previous.packageBytes,&m,false,true) || strcmp(name,m.id) || !memcmp(sLoaded+24,id,32)) return false;
    }
    return true;
  },&scan,true);
  sLoadedBytes=0;return safe?AppDeveloperKeys::Error::None:AppDeveloperKeys::Error::KeyInUse;
}
static bool archiveVerify(void *,const char *id,const uint8_t *package,uint32_t bytes,bool inspect,bool supported,AppArchive::PackageInfo *out) {
  Metadata metadata;uint32_t schema;
  if(!parseMetadata(package,bytes,&metadata,supported,&schema,nullptr,inspect) || metadata.abi!=1 || strcmp(metadata.id,id)) return false;
  versionParts(metadata.version,out->version);out->schema=schema;return true;
}
static bool archiveSameAuthority(void *,const uint8_t *a,const uint8_t *b) {
  return !memcmp(a,b,32) || (AppDeveloperKeys::Controller::compiledKey(a) && AppDeveloperKeys::Controller::compiledKey(b));
}
static uint32_t archiveTrustRevision(void *) {return sKeys.status().serial;}
static bool archiveDeveloperKey(void *,const uint8_t *id) {return !AppDeveloperKeys::Controller::compiledKey(id);}
static void installPackage(bool recoveryApproved=false) {
      Metadata m; if(!metadata(sUpload,sLength,&m,true) || m.abi!=1) { fail(3);return; }
      int target=-1;
      for(unsigned i=0;i<sCount;i++) if(sCatalog[i].bytes && !strcmp(sCatalog[i].metadata.id,m.id)) { target=i;break; }
      sInstallProgress.identify(m.name,target>=0);
      uint32_t bytes=0;
      if(target>=0) {
        Entry e;if(!sVolume.entry(m.id,&e)) { fail(4);return; }bytes=e.dataBytes;
        if(!sVolume.read(m.id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData))) { fail(4);return; }
        // Store roots share their existing central publication authority. A
        // developer update must retain its exact enrolled signing identity.
        if(memcmp(sLoaded+24,sUpload+24,32) &&
           !(AppDeveloperKeys::Controller::compiledKey(sLoaded+24) && AppDeveloperKeys::Controller::compiledKey(sUpload+24)) && !recoveryApproved) {
          fail(10);return;
        }
        const char *old=sCatalog[target].metadata.version,*next=m.version;
        int order=0;
        for(unsigned part=0;part<3;part++) {
          uint32_t a=0,b=0;
          while(*old>='0' && *old<='9') a=a*10+(*old++-'0');
          while(*next>='0' && *next<='9') b=b*10+(*next++-'0');
          if(!order && a!=b) order=b>a?1:-1;
          if(*old=='.') old++;
          if(*next=='.') next++;
        }
        if(order<0 || (!order && (sLength!=e.packageBytes || memcmp(sUpload,sLoaded,sLength)))) { fail(8);return; }
        if(!order) { sTarget=target;sState=Complete;sInstallProgress.finish(true);return; }
      } else {
        // Unauthenticated/quarantined packages are absent from the catalog;
        // their namespace still belongs to the installed package and data.
        if(sVolume.namespaceState(m.id)!=0) {fail(10);return;}
        target=sCount;
      }
      if(target<0 || static_cast<unsigned>(target)>=MaximumEntries) { fail(5);return; }
      sTarget=target;sState=Working;
      AppDocumentRoot::Root root;
      if(sVolume.documentRoot(m.id,&root)) {
        uint32_t version[3];versionParts(m.version,version);
        if(!sVolume.beginUpgrade(m.id,sUpload,sLength,version)) fail(8);
      } else if(!sVolume.begin(m.id,sUpload,sLength,sUploadData,bytes)) fail(6);

}
// Called only with AppManagement's upload/storage ownership held. The old
// package must still authenticate; damaged/unknown namespaces cannot be claimed.
static AppDeveloperKeys::Error prepareRecovery(const AppDeveloperKeys::Request &request,const AppDeveloperKeys::Table &table,AppDeveloperKeys::RecoveryInfo *info) {
  using E=AppDeveloperKeys::Error;
  if(sState!=Receiving || sReceived!=sLength) return E::Busy;
  uint8_t hash[32];NativeAppHash::sha256(sUpload,sLength,hash);
  if(memcmp(hash,request.reserved,32) || memcmp(sUpload+24,request.id,32)) return E::Package;
  Metadata next,old;Entry entry;
  if(!table.find(request.id,AppDeveloperKeys::Purpose::Execute) || !metadata(sUpload,sLength,&next,true) || next.abi!=1) return E::Package;
  if(!sVolume.entry(next.id,&entry) || !sVolume.read(next.id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) ||
     !metadata(sLoaded,entry.packageBytes,&old,false,true) || strcmp(old.id,next.id)) return E::Missing;
  const auto *previous=table.find(sLoaded+24,AppDeveloperKeys::Purpose::Inspect);
  if(!previous || previous->state!=AppDeveloperKeys::KeyState::Revoked || !memcmp(sLoaded+24,request.id,32) ||
     AppDeveloperKeys::Controller::compiledKey(sLoaded+24) || AppDeveloperKeys::Controller::compiledKey(request.id)) return E::Ownership;
  uint32_t before[3],after[3];versionParts(old.version,before);versionParts(next.version,after);
  int order=0;for(unsigned i=0;i<3;i++) if(!order && before[i]!=after[i]) order=after[i]>before[i]?1:-1;
  if(order<=0) return E::Package;
  AppDocumentRoot::Root root;
  if(sVolume.documentRoot(next.id,&root)) {
    if(root.flags&AppDocumentRoot::PendingUpgrade) return E::Busy;
    order=0;for(unsigned i=0;i<3;i++) if(!order && root.highVersion[i]!=after[i]) order=after[i]>root.highVersion[i]?1:-1;
    if(order<=0) return E::Package;
  }
  *info=AppDeveloperKeys::RecoveryInfo{};info->generation=entry.generation;
  memcpy(info->appId,next.id,sizeof(next.id));memcpy(info->version,next.version,sizeof(next.version));
  memcpy(info->oldSigner,sLoaded+24,32);memcpy(info->packageHash,hash,32);return E::None;
}
static AppDeveloperKeys::Error beginRecovery(const AppDeveloperKeys::Request &request,const AppDeveloperKeys::Table &table,const AppDeveloperKeys::RecoveryInfo &approved) {
  using E=AppDeveloperKeys::Error;AppDeveloperKeys::RecoveryInfo current;
  E error=prepareRecovery(request,table,&current);if(error!=E::None) return error;
  current.sequence=approved.sequence;current.serial=table.serial;
  if(memcmp(&current,&approved,sizeof(current))) return E::Stale;
  AppDocumentRoot::Root root;sRecoveryConverting=!sVolume.documentRoot(current.appId,&root);
  if(sRecoveryConverting) {
    Entry entry;Metadata old;uint32_t schema,version[3];
    if(!sVolume.entry(current.appId,&entry) || !parseMetadata(sLoaded,entry.packageBytes,&old,false,&schema,nullptr,true)) return E::Package;
    versionParts(old.version,version);
    // Preserve a legacy package/data pair before the ordinary retained upgrade.
    // A cancelled conversion changes representation, never signer or user bytes.
    if(!sVolume.beginCheckpoint(current.appId,sUploadData,entry.dataBytes,version,schema)) return E::Io;
    sState=Working;
  } else installPackage(true);
  return sState==Working?E::None:E::Package;
}
static AppDeveloperKeys::State stepRecovery(AppDeveloperKeys::Error *error) {
  using S=AppDeveloperKeys::State;sVolume.step();
  if(sVolume.state()==AppStorage::State::Failed) {fail(7);*error=AppDeveloperKeys::Error::Uncertain;return S::Failed;}
  if(sVolume.state()!=AppStorage::State::Complete) return S::Working;
  if(sRecoveryConverting) {
    sRecoveryConverting=false;installPackage(true);
    if(sState!=Working) {*error=AppDeveloperKeys::Error::Package;return S::Failed;}
    return S::Working;
  }
  sState=Complete;sError=0;return S::Complete;
}
static bool cancelRecovery() {
  sVolume.cancel();
  if(sVolume.state()!=AppStorage::State::Ready) return false;
  sState=Ready;sError=0;return true;
}
static void finishRecovery(AppDeveloperKeys::State) {
  sRecoveryConverting=false;
  if(sState==Receiving) {sState=Ready;sError=0;}
  sReceived=sLength=0;
}
static bool keyResultChanged() {
  const auto status=sKeys.status();
  return !sKeys.busy() && (status.sequence!=sObservedKeySequence || status.state!=sObservedKeyState);
}
void init() {
  sState=Working;
  if(!sVolume.initialize(sUpload,sizeof(sUpload),sUploadData,sizeof(sUploadData),appName)) { fail(9);return; }
  sState=Ready;sError=0;sKeys.initialize();refresh();
  int homeBytes=sVolume.readHomeOrder(sHomeOrder,sizeof(sHomeOrder));
  sHomeBytes=homeBytes>0?homeBytes:0;
}
AppDeveloperKeys::RecoveryInfo developerKeyRecoveryInfo() {return sKeys.recoveryInfo();}
AppDeveloperKeys::Status developerKeyStatus() {auto status=sKeys.status();status.unavailableApps=sUnavailable;return status;}
bool developerKeyNeedsPresentation() {return sKeys.needsPresentation();}
bool developerKeyPresent() {return sKeys.present();}
void developerKeyRendered() {sKeys.rendered();}
void developerKeyObserve(uint64_t physical) {sKeys.observeKeyboard(physical);}
bool developerKeyApprove() {return sKeys.approve(Ion::Timing::millis());}
void developerKeyDismiss() {sKeys.dismiss();}
void developerKeyDeny() {sKeys.deny();}
AppArchive::TransferStatus archiveStatus() {return sArchive.status();}
AppArchive::ApprovalInfo archiveApprovalInfo() {return sArchive.approvalInfo();}
bool archiveNeedsPresentation() {return sArchive.needsPresentation();}
bool archivePresent() {return sArchive.present();}
void archiveRendered() {sArchive.rendered();}
void archiveObserve(uint64_t physical) {sArchive.observeKeyboard(physical);}
bool archiveApprove() {return sArchive.approve(Ion::Timing::millis());}
void archiveDismiss() {sArchive.dismiss();}
void archiveDeny() {sArchive.deny();}
AppInstallProgress::Status installationStatus() {
  // Physical trust/restore consent must retain presentation priority.
  return sKeys.busy() || sArchive.busy() ? AppInstallProgress::Status{} : sInstallProgress.status();
}
uint32_t revision() { return sRevision; }
unsigned count() { return sCount; }
const uint8_t *icon(unsigned index) { return index<sCount && sHasIcon[index] ? sIcons[index] : nullptr; }
static bool sBulkActive=false;
void setBulkActive(bool active) {sBulkActive=active;}
const uint8_t *homeOrder(uint32_t *bytes) {*bytes=sHomeBytes;return sHomeOrder;}
bool homeOrderSaveFailed() {bool failed=sHomeFailed;sHomeFailed=false;return failed;}
bool saveHomeOrder(const uint8_t *data,uint32_t bytes) {
  if(!data || bytes<8 || bytes>sizeof(sHomePending) || busy() || !idle() || sOpen>=0) return false;
  memcpy(sHomePending,data,bytes);sHomePendingBytes=bytes;sHomeSaving=true;sHomeStarted=false;sHomeFailed=false;
  sState=Working;return true;
}
bool busy() { return sHomeSaving || sBulkActive || sArchive.busy() || sKeys.busy() || sData.needsPolling() || sExchange.busy() || sClosing || sPending || sState==Backup || sState==Receiving || sState==Working; }
bool needsPolling() {
  if(DevelopmentUpdate::busy()) return false;
  if(sHomeSaving) return true;
  if(sKeys.busy()) return sKeys.needsPolling();
  if(keyResultChanged() || sData.needsPolling()) return true;
  if(sArchive.busy()) return sArchive.needsPolling(Ion::Timing::millis());
  if(sExchange.busy()) return sExchange.needsPolling();
  if(sFiles.needsPolling()) return true;
  return sOpen<0 && (sClosing || sState==Working || (sPending && sAcknowledged));
}
void acknowledge() { if(sPending) sAcknowledged=true;sExchange.acknowledge();sKeys.acknowledge();sArchive.acknowledge(); }
void abandonSetup() { if(sPending && !sAcknowledged) sPending=0;sExchange.abandonSetup();sKeys.abandonSetup();sArchive.abandonSetup(); }
void disconnect() {
  if(sPending==0x71) {sPending=0;sAcknowledged=false;}
  sExchange.disconnect();
  sKeys.disconnect();
  sArchive.disconnect();
  // A reset during upload must not strand storage in Receiving before an
  // approval request exists. Preserve an acknowledged install COMMIT: USB
  // inspects the completed status transfer before calling this handler.
  if(sPending && !sAcknowledged) {sPending=0;sAcknowledged=false;}
  if(sState==Receiving && !sPending && !sKeys.busy()) {
    sInstallProgress.cancel();sReceived=sLength=0;sError=0;
    sState=(sVolume.state()==AppStorage::State::Ready || sVolume.state()==AppStorage::State::Complete)?Ready:Cold;
  }
}
uint8_t *bulkPackage(uint32_t length) {
  return !DevelopmentUpdate::busy() && !sPending && sOpen<0 && !sClosing &&
    !sExchange.busy() && !sKeys.busy() && !sArchive.busy() &&
    sState==Receiving && !sReceived && length==sLength ? sUpload : nullptr;
}
bool bulkPackageReceived(uint32_t length) {
  if(!bulkPackage(length)) return false;sReceived=length;sInstallProgress.progress(sReceived);return true;
}
const uint8_t *bulkPackageRead(uint32_t length) {
  return !busy() && sOpen<0 && sLoadedBytes && length==sLoadedBytes ? sLoaded : nullptr;
}
void bulkFileProgress(uint32_t sequence) {sExchange.stageProgress(sequence,Ion::Timing::millis());}
bool bulkFileExport(uint32_t sequence,uint8_t *data,uint32_t length) {
  return !DevelopmentUpdate::busy() && !sPending && sOpen<0 && !sClosing &&
    sExchange.stageExport(sequence,data,length);
}
bool bulkFile(uint32_t sequence,const uint8_t *data,uint32_t length) {
  return !DevelopmentUpdate::busy() && !sPending && sOpen<0 && !sClosing &&
    sExchange.stage(sequence,data,length);
}
bool request(uint8_t command,uint32_t arg,const uint8_t *data,size_t size) {
  if(command==0x82) {
    if(arg || !data || size!=sizeof(AppDeveloperKeys::Control)) return false;
    AppDeveloperKeys::Control control;memcpy(&control,data,size);return sKeys.cancel(control);
  }
  if(DevelopmentUpdate::busy() || sHomeSaving || sPending || sOpen>=0 || sClosing) return false;
  if(command==0x81) {
    if(arg || sArchive.busy() || sExchange.busy() || sData.needsPolling() || !data || size!=sizeof(AppDeveloperKeys::Request)) return false;
    AppDeveloperKeys::Request r;memcpy(&r,data,size);
    if(r.operation==AppDeveloperKeys::Operation::RecoverInstall) {
      if(sState!=Receiving || sReceived!=sLength) return false;
    } else if(!idle()) return false;
    bool accepted=sKeys.request(r,Ion::Timing::millis());
    if(accepted) sInstallProgress.cancel();
    return accepted;
  }
  if(sKeys.busy()) return false;
  if(command>=0x90 && command<=0x95) {
    if(command==0x91 && (!(idle() || sState==Error) || sExchange.busy() || sFiles.active() || sEndFilesQueued || sData.needsPolling())) return false;
    return sArchive.request(command,arg,data,size);
  }
  if(sArchive.busy()) return false;
  if(command==0x71) {
    if(arg || !idle() || !sExchange.canBegin() || !data || size!=sizeof(sExchangeRequest)) return false;
    AppFileExchange::Request request;memcpy(&request,data,sizeof(request));
    if(!AppFileExchange::Session::valid(request)) return false;
    sExchangeRequest=request;return queue(command,0);
  }
  if(command>=0x70 && command<=0x75) return sExchange.request(command,arg,data,size);
  if(sExchange.busy()) return false;
  if(command==0x60) return !size && !arg && !busy() && queue(command,0);
  if(command==0x61) {
    if(size || arg || sState!=Unprovisioned) return false;
    sBackupOffset=0;memset(sBackupDigest,0,32);NativeAppHash::shaInit(&sBackupHash);sState=Backup;return true;
  }
  if(command==0x62) {
    if(arg || size!=32 || sState!=Backup || sBackupOffset!=BackupBytes || memcmp(data,sBackupDigest,32)) return false;
    return queue(command,0);
  }
  if(command==0x63) {
    if(size || !idle() || arg<468 || arg>MaximumPackage) return false;
    sInstallData=false;sInstallProgress.begin(AppInstallProgress::Phase::Receiving,arg);
    sLength=arg;sReceived=0;sState=Receiving;sError=0;return true;
  }
  if(command==0x64) {
    if(sState!=Receiving || !size || size>512 || arg!=sReceived || size>sLength-sReceived) return false;
    memcpy(sUpload+sReceived,data,size);sReceived+=size;sInstallProgress.progress(sReceived);return true;
  }
  if(command==0x65 || command==0x6c) {
    return !size && !arg && sState==Receiving && sReceived==sLength && queue(command,0);
  }
  if(command==0x66 || command==0x6a) return !size && idle() && arg<sCount && sCatalog[arg].bytes && queue(command,arg);
  if(command==0x67) {
    if(size || arg || sState==Working) return false;
    sState=(sVolume.state()==State::Ready || sVolume.state()==State::Complete)?Ready:Cold;
    sInstallProgress.cancel();sReceived=sLength=sBackupOffset=0;sError=0;return true;
  }
  return false;
}
bool response(uint8_t command,uint32_t arg,uint8_t *data,size_t capacity,size_t *size) {
  if(!data || !size || capacity>512) return false;
  if(command==0x85 || command==0x86 || command==0x87 || command==0x88) {
    if(busy() || !idle() || sOpen>=0 || sFiles.active() || sEndFilesQueued) return false;
    if(command==0x85) {
      AppDeveloperKeys::DamageInfo info;
      if(arg || capacity!=sizeof(info) || !sKeys.damageInfo(&info)) return false;
      memcpy(data,&info,sizeof(info));*size=sizeof(info);return true;
    }
    if(command==0x87) {
      AppDeveloperKeys::UnreadableInfo info;
      if(arg || capacity!=sizeof(info) || !sKeys.unreadableInfo(&info)) return false;
      memcpy(data,&info,sizeof(info));*size=sizeof(info);return true;
    }
    int n=command==0x88?sKeys.unreadableBytes(arg,data,capacity):sKeys.damagedBytes(arg,data,capacity);
    if(n!=int(capacity)) return false;
    *size=capacity;return true;
  }
  if(command>=0x90 && command<=0x96) return sArchive.response(command,arg,data,capacity,size);
  if(command==0x80) {
    if(arg || capacity!=sizeof(AppDeveloperKeys::Status)) return false;
    auto status=developerKeyStatus();memcpy(data,&status,sizeof(status));*size=sizeof(status);return true;
  }
  if(command==0x84) {
    if(arg || capacity!=sizeof(AppDeveloperKeys::RecoveryInfo) || sKeys.status().operation!=AppDeveloperKeys::Operation::RecoverInstall) return false;
    auto info=sKeys.recoveryInfo();memcpy(data,&info,sizeof(info));*size=sizeof(info);return true;
  }
  if(command==0x83) {
    if(capacity!=sizeof(AppDeveloperKeys::KeyInfo)) return false;
    AppDeveloperKeys::KeyInfo info;if(!sKeys.keyInfo(arg,&info)) return false;
    memcpy(data,&info,sizeof(info));*size=sizeof(info);return true;
  }
  if(command>=0x70 && command<=0x75) {
    if(!sExchange.response(command,arg,data,capacity,size)) return false;
    // BEGIN is acknowledged before poll authenticates and selects its app.
    // Expose that queued operation instead of the previous completed session.
    if(command==0x70 && sPending==0x71) {
      AppFileExchange::Status old;memcpy(&old,data,sizeof(old));
      AppFileExchange::Status pending{0x5841464c,96,1,AppFileExchange::Working,sExchangeRequest.operation,0,
        old.sequence+1,0,sExchangeRequest.length,0,sExchangeRequest.generation,sExchangeRequest.dataSchema,512,0,{0,0},{0}};
      memcpy(data,&pending,sizeof(pending));
    }
    return true;
  }
  if(command==0x60) {
    uint32_t status[16]={0x3141464c,2,(sArchive.busy() || sKeys.busy() || sPending || sClosing || sExchange.busy() || sData.needsPolling())?Working:sState,sError,sReceived,sLength,2,sCount,1,BackupBytes,sBackupOffset,static_cast<uint32_t>(sVolume.state()),sVolume.progress(),sTarget,sPending,65470u|(sOpen>=0?64u:0u)};
    *size=capacity<sizeof(status)?capacity:sizeof(status);memcpy(data,status,*size);return !arg;
  }
  if(command==0x6e) {
    if(arg || capacity!=48) return false;
    // Read-only contract discovery is independent of mount, app and USB state.
    const uint32_t info[12]={0x4341464c,48,1,0,1,NativeAppManifest::APIRevision,
      NativeAppManifest::Features,NativeAppManifest::PackageSchemas,2,MaximumPackage,MaximumData,0};
    memcpy(data,info,sizeof(info));*size=sizeof(info);return true;
  }
  if(command==0x62) { if(arg || sBackupOffset!=BackupBytes || sState!=Backup || capacity<32) return false;memcpy(data,sBackupDigest,32);*size=32;return true; }
  if(command==0x61) {
    if(sState!=Backup || arg!=sBackupOffset || !capacity || arg>=BackupBytes || capacity>RawBytes-arg%RawBytes) return false;
    if(arg%RawBytes==0) {
#if PRIME_G2_EMULATOR
      // VM backup is a modeled raw image: payload plus erased spare bytes.
      // Physical builds always return the actual spare bytes through GPMI.
      if(!read(nullptr,FirstBlock*PagesPerBlock+arg/RawBytes,sRaw)) { fail(1);return false; }
      memset(sRaw+PageBytes,255,RawBytes-PageBytes);
#else
      if(!NANDPhysical::readRawAppPage(FirstBlock*PagesPerBlock+arg/RawBytes,sRaw)) { fail(1);return false; }
#endif
    }
    memcpy(data,sRaw+arg%RawBytes,capacity);NativeAppHash::shaUpdate(&sBackupHash,data,capacity);sBackupOffset+=capacity;*size=capacity;
    if(sBackupOffset==BackupBytes) NativeAppHash::shaFinal(&sBackupHash,sBackupDigest);
    return true;
  }
  if(command==0x6b) {
    if(!idle() || arg || capacity<48) return false;
    // USB responses only copy cached accounting; NAND traversal belongs in poll().
    const Space &info=sSpace;
    uint32_t summary[12]={0x5341464c,2,BlockCount*BlockBytes,info.capacity,sUsed,info.available,sCount,BlockBytes,MaximumPackage,MaximumData,info.allocated,info.overhead};
    memcpy(data,summary,sizeof(summary));*size=sizeof(summary);return true;
  }
  if(command==0x6d) {
    if(!idle() || arg>=sCount || capacity<32) return false;
    memcpy(data,sIconHashes[arg],32); *size=32; return true;
  }
  if(command==0x68) {
    if(!idle() || arg>=sCount) return false;
    *size=capacity<sizeof(CatalogEntry)?capacity:sizeof(CatalogEntry);memcpy(data,&sCatalog[arg],*size);return true;
  }
  if(command==0x6a) {
    if(!idle() || arg>=sLoadedBytes || !capacity) return false;
    *size=sLoadedBytes-arg;if(*size>capacity) *size=capacity;memcpy(data,sLoaded+arg,*size);return true;
  }
  return false;
}
void poll() {
  if(DevelopmentUpdate::busy()) return;
  if(sHomeSaving) {
    if(!sHomeStarted) {
      sHomeStarted=true;
      if(!sVolume.beginHomeOrder(sHomePending,sHomePendingBytes)) sHomeFailed=true;
    } else sVolume.step();
    if(sHomeFailed || sVolume.state()==State::Failed || sVolume.state()==State::Complete) {
      sHomeFailed=sHomeFailed || sVolume.state()==State::Failed;
      if(!sHomeFailed) {memcpy(sHomeOrder,sHomePending,sHomePendingBytes);sHomeBytes=sHomePendingBytes;}
      sHomeSaving=false;sRevision++;
      if(sVolume.state()==State::Failed) fail(7);else sState=Complete;
    }
    return;
  }
  if(sKeys.busy()) {
    sKeys.poll(Ion::Timing::millis());
    if(sKeys.busy()) return;
  }
  if(keyResultChanged()) {
    auto status=sKeys.status();sObservedKeySequence=status.sequence;sObservedKeyState=status.state;refresh();return;
  }
  if(sData.needsPolling()) {
    sData.poll();if(sData.needsPolling()) return;
  }
  if(sEndFilesQueued) {sEndFilesQueued=false;sFiles.detach();}
  if(sFiles.active()) sFiles.poll();
  // Foreground file completion must not rebuild the catalog or reuse package
  // and committed-data scratch while the authenticated app still owns it.
  if(sOpen>=0 || (sClosing && sFiles.active())) return;
  if(sArchive.busy()) {
    sArchive.poll(static_cast<uint32_t>(Ion::Timing::millis()));
    if(!sArchive.busy()) {sState=Complete;sError=0;refresh();}
    return;
  }
  if(sExchange.busy()) {
    sExchange.poll(static_cast<uint32_t>(Ion::Timing::millis()));
    if(sInstallData) sInstallProgress.progress(sExchange.status().offset);
    if(!sExchange.busy()) {
      sState=Complete;sError=0;refresh();
      if(sInstallData) {
        auto status=sExchange.status();
        if(status.state==AppFileExchange::Cancelled) sInstallProgress.cancel();
        else sInstallProgress.finish(status.state==AppFileExchange::Complete && !sError);
        sInstallData=false;
      }
    }
    return;
  }
  if(sClosing) {
    sClosing=false;
    if(sSaveOnClose) {
      const char *id=sCatalog[sCloseSlot].metadata.id;AppDocumentRoot::Root root;
      bool documents=sVolume.documentRoot(id,&root);
      bool accept=documents && (root.flags&AppDocumentRoot::PendingUpgrade) && !sExplicitData && !sLoadedSchema && !sData.savedSchema();
      if(sData.dirty()) {
        sTarget=sCloseSlot;sState=Working;
        uint32_t schema=sData.migrating()?sLoadedSchema:sData.savedSchema();
        bool ok=documents?sVolume.beginCheckpoint(id,sData.data(),sData.bytes(),nullptr,schema,accept):
                          sVolume.begin(id,sLoaded,sLoadedBytes,sData.data(),sData.bytes());
        if(!ok) fail(6);
      } else if(accept) {
        sTarget=sCloseSlot;sState=Working;if(!sVolume.beginAccept(id,0)) fail(6);
      }
    }
    if(!sData.reset()) fail(6);
    if(sState!=Working) { if(sVolume.state()==State::Failed) fail(7);else refresh(); }
  }
  if(sPending && sAcknowledged) {
    uint8_t command=sPending;sPending=0;sAcknowledged=false;
    if(command==0x65 || command==0x6c)
      sInstallProgress.phase(command==0x65?AppInstallProgress::Phase::Package:AppInstallProgress::Phase::Icon,sLength);
    if(command==0x71) {
      const auto &request=sExchangeRequest;Metadata metadata;Entry entry;uint32_t schema=0;
      AppStorage::Volume::FileUsage usage{};
      if(!sVolume.entry(request.id,&entry) || !sVolume.read(request.id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) ||
         !parseMetadata(sLoaded,entry.packageBytes,&metadata,false,&schema,nullptr,true) || strcmp(metadata.id,request.id) ||
         !sVolume.fileUsage(request.id,&usage)) {sExchange.reject(request,LEFONY_FILE_NOT_FOUND);return;}
      AppFileExchange::Identity identity{};memcpy(identity.id,metadata.id,sizeof(identity.id));versionParts(metadata.version,identity.version);
      identity.appSchema=identity.dataSchema=schema;identity.generation=usage.generation;
      identity.privateBytes=entry.dataBytes;identity.privateData=sUploadData;
      AppDocumentRoot::Root root;
      bool documents=sVolume.documentRoot(request.id,&root);
      if(documents) {identity.dataSchema=root.current.dataSchema;identity.pendingUpgrade=root.flags&AppDocumentRoot::PendingUpgrade;}
      if(request.operation>=AppFileExchange::InspectData) {
        auto &info=identity.dataInfo;
        NativeAppHash::sha256(sLoaded,entry.packageBytes,info.packageHash);
        memcpy(info.highVersion,documents?root.highVersion:identity.version,sizeof(info.highVersion));
        if(identity.pendingUpgrade) {
          info.flags=AppFileExchange::PendingUpgrade;info.previousPackage=root.previous.package;
          info.previousSchema=root.previous.dataSchema;memcpy(info.previousPackageHash,root.previous.packageHash,32);
          Entry previous;Metadata old;uint32_t oldSchema;
          if(sVolume.recoveryPackage(request.id,sUpload,sizeof(sUpload),&previous) &&
             parseMetadata(sUpload,previous.packageBytes,&old,true,&oldSchema) && !strcmp(old.id,request.id) &&
             oldSchema==root.previous.dataSchema) {
            info.flags|=AppFileExchange::RecoveryTrusted;versionParts(old.version,info.previousVersion);
            info.previousPrivateBytes=previous.dataBytes;
          }
        }
      }
      if(!sExchange.begin(request,identity,static_cast<uint32_t>(Ion::Timing::millis()))) sExchange.reject(request,LEFONY_FILE_IO);
      if(request.operation==AppFileExchange::Import || request.operation==AppFileExchange::ImportData) {
        sInstallData=sExchange.busy();
        sInstallProgress.begin(AppInstallProgress::Phase::Data,request.length);
        sInstallProgress.identify(metadata.name,false);
        if(!sInstallData) sInstallProgress.finish(false);
      }
    }
    else if(command==0x60) { if(sVolume.mount()) { sState=Ready;sError=0;sKeys.initialize();refresh(); } else sState=sVolume.state()==State::Unprovisioned?Unprovisioned:Error; }
    else if(command==0x62) { sState=Working;if(!sVolume.provision(sBackupDigest) || !sVolume.initialize(sUpload,sizeof(sUpload),sUploadData,sizeof(sUploadData),appName)) fail(2);else { sState=Ready;sKeys.initialize();refresh(); } }
    else if(command==0x6c) {
      if(!AppIcon::pixels(sUpload,sLength,nullptr,Services::noteVerificationProgress)) { fail(3);return; }
      int target=-1;
      for(unsigned i=0;i<sCount;i++) if(!memcmp(sUpload+352+8,sAppHashes[i],32)) { target=i;break; }
      if(target<0) { fail(3);return; }
      sInstallProgress.identify(sCatalog[target].metadata.name,false);
      sTarget=target;sState=Working;
      if(!sVolume.begin(sCatalog[target].metadata.id,sUpload,sLength,nullptr,0,true)) fail(6);
    }
    else if(command==0x65) { installPackage();
    } else if(command==0x66) { sTarget=sPendingArgument;sState=Working;if(!sVolume.begin(sCatalog[sTarget].metadata.id,nullptr,0,nullptr,0)) fail(6); }
    else if(command==0x6a) { auto e=sCatalog[sPendingArgument];if(!sVolume.read(e.metadata.id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData))) fail(4);else { sLoadedBytes=e.bytes;sState=Complete; } }
  }
  if(sState==Working) {
    sVolume.step();
    sInstallProgress.progress(sVolume.progress());
    if(sVolume.state()==State::Failed) fail(7);
    else if(sVolume.state()==State::Complete) { sState=Complete;sError=0;refresh();sInstallProgress.finish(!sError); }
  }
}
const CatalogEntry &entry(unsigned slot) { return sCatalog[slot<sCount?slot:0]; }
bool open(unsigned slot) {
  if(busy() || slot>=sCount || !sCatalog[slot].bytes || sOpen>=0) return false;
  Entry e;if(!sVolume.entry(sCatalog[slot].metadata.id,&e)) return false;
  NativeAppManifest::Manifest loaded;
  // Installed apps require signatures even in the VM; unsigned packages are
  // supported only by its separate developer-preview loader.
  if(!sVolume.read(sCatalog[slot].metadata.id,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) ||
      e.packageBytes<8 || memcmp(sLoaded,"LFAPP1\0\0",8) ||
      !NativeApp::load(sLoaded,e.packageBytes,&loaded)) return false;
  // The loader already authenticated and parsed these exact bytes. Reusing
  // its result avoids a second RSA verification and two package hash passes.
  sLoadedSchema=loaded.dataSchema;
  uint32_t features=loaded.required|loaded.optional;
  AppDocumentRoot::Root root;
  uint32_t savedSchema=sVolume.documentRoot(loaded.id,&root)?root.current.dataSchema:sLoadedSchema;
  uint32_t version[3];versionParts(loaded.version,version);
  if(!sData.attach(loaded.id,version,sLoadedSchema,savedSchema,sUploadData,e.dataBytes)) {NativeApp::unload();return false;}
  if(!sFiles.attach(loaded.id,version,sLoadedSchema,savedSchema,sUploadData,e.dataBytes)) {
    sData.reset();
    NativeApp::unload();return false;
  }
  sExplicitData=features&LEFONY_DATA_CAPABILITY;sEndFilesQueued=false;
  sOpen=slot;sLoadedBytes=e.packageBytes;return true;
}
bool hasOpen() {return sOpen>=0;}
void close() {
  if(sOpen<0) return;
  sCloseSlot=sOpen;sOpen=-1;sSaveOnClose=NativeApp::saveDataOnClose();
  sClosing=true;endFiles();
}
int files(LefonyFileRequest &r,const char *path,const char *destination,const void *input,void *output) {
  if(sOpen<0) return -LEFONY_FILE_DENIED;
  return sData.needsPolling()?-LEFONY_FILE_BUSY:sFiles.exchange(r,path,destination,input,output);
}
int data(LefonyDataRequest &r) { return sOpen<0?-LEFONY_FILE_DENIED:sData.request(r); }
void endFiles() {
  if(sData.active()) sData.finish(NativeApp::saveDataOnClose());
  if(sData.needsPolling()) sEndFilesQueued=true;else sFiles.detach();
}
int readData(uint32_t offset,void *data,uint32_t size) {
  return sOpen<0?-1:sData.read(offset,data,size);
}
int writeData(uint32_t offset,const void *data,uint32_t size) {
  return sOpen<0?-1:sData.write(offset,data,size);
}
}}

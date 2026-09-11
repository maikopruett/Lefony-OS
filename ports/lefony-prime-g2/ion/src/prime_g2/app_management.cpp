// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_management.h"
#include "app_storage.h"
#include "native_app.h"
#include "native_app_signature.h"
#include "nand_physical.h"
#include "development_update.h"
#include "registers.h"
#include <string.h>
namespace PrimeG2 { namespace AppManagement {
namespace {
static_assert(sizeof(CatalogEntry)==168,"app catalog protocol layout");
static_assert(offsetof(CatalogEntry,metadata)==8 && offsetof(Metadata,id)==4 && offsetof(Metadata,name)==53 && offsetof(Metadata,version)==134,"app catalog text offsets");
using namespace AppStorage;
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
  if(!NANDPhysical::readAppPage(page)) return false;
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
Volume sVolume({nullptr,usable,read,erase,program});
CatalogEntry sCatalog[Slots]={};
alignas(64) uint8_t sUpload[MaximumPackage],sLoaded[MaximumPackage],sRaw[2176];
uint8_t sData[MaximumData],sUploadData[MaximumData],sBackupDigest[32];
uint32_t sCapacity[Slots]={},sRevision=0;
NativeAppHash::SHA256 sBackupHash;
// Wire state is independent of the storage engine's internal states.
enum : uint32_t { Cold,Unprovisioned,Ready,Backup,Receiving,Working,Complete,Error };
uint32_t sState=Cold,sError=0,sReceived=0,sLength=0,sBackupOffset=0,sDataBytes=0;
uint32_t sLoadedBytes=0,sPendingArgument=0,sTarget=0;
uint8_t sPending=0;
bool sAcknowledged=false,sDirty=false;
int sOpen=-1;
constexpr uint32_t RawBytes=2112,BackupBytes=BlockCount*PagesPerBlock*RawBytes;
uint32_t word(const uint8_t *p) { uint32_t value;memcpy(&value,p,4);return value; }
void fail(uint32_t error) { sState=Error;sError=error;sPending=0;sAcknowledged=false; }
bool idle() { return sState==Ready || sState==Complete; }
bool match(const uint8_t *&p,const uint8_t *end,const char *text) {
  size_t n=strlen(text); if(size_t(end-p)<n || memcmp(p,text,n)) return false; p+=n; return true;
}
bool string(const uint8_t *&p,const uint8_t *end,char *out,size_t capacity) {
  if(p==end || *p++!='"') return false;
  size_t count=0; bool nonspace=false;
  while(p<end && *p!='"') {
    uint8_t c=*p++;
    if(c=='\\') { if(p==end || (*p!='"' && *p!='\\')) return false; c=*p++; }
    if(c<32 || c>126 || count+1>=capacity) return false;
    out[count++]=c; nonspace|=c!=' ';
  }
  if(p==end || !count || !nonspace) return false;
  p++;out[count]=0;return true;
}
void refresh() {
  sRevision++;
  memset(sCatalog,0,sizeof(sCatalog));
  for(unsigned slot=0;slot<Slots;slot++) {
    auto e=sVolume.entry(slot);
    if(!e.packageBytes) continue;
    Metadata m;
    if(sVolume.read(slot,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData)) && metadata(sLoaded,e.packageBytes,&m)) sCatalog[slot]={e.packageBytes,e.generation,m};
  }
  sLoadedBytes=0;
}
bool queue(uint8_t command,uint32_t argument) {
  if(sPending) return false;
  sPending=command; sPendingArgument=argument;sAcknowledged=false;return true;
}
}
bool metadata(const uint8_t *package,size_t size,Metadata *out) {
  const uint8_t *payload;size_t bytes;
  if(!out || !NativeAppSignature::unwrap(package,size,&payload,&bytes) || bytes<64 || memcmp(payload,"LFAPP0\0\0",8) || word(payload+8) || word(payload+20)>1 || word(payload+56) || word(payload+60)) return false;
  uint32_t length=word(payload+12),image=word(payload+16);
  if(!length || length>4096 || image<52 || image>2*1024*1024 || bytes!=64+length+image || word(package+16)!=word(payload+20)) return false;
  uint8_t hash[32];NativeAppHash::sha256(payload+64,bytes-64,hash);
  if(memcmp(hash,payload+24,32)) return false;
  const uint8_t *p=payload+64,*end=p+length;
  Metadata m={};char license[81];
  if(!match(p,end,"{\"abi\":" ) || p==end || (*p!='0' && *p!='1')) return false;
  m.abi=*p++-'0';
  if(m.abi!=word(payload+20) || !match(p,end,",\"id\":") || !string(p,end,m.id,sizeof(m.id)) ||
      !match(p,end,",\"license\":") || !string(p,end,license,sizeof(license)) ||
      !match(p,end,",\"name\":") || !string(p,end,m.name,sizeof(m.name)) ||
      !match(p,end,",\"version\":") || !string(p,end,m.version,sizeof(m.version)) || !match(p,end,"}") || p!=end) return false;
  for(unsigned i=0;m.id[i];i++) if(!((m.id[i]>='a' && m.id[i]<='z') || (i && ((m.id[i]>='0' && m.id[i]<='9') || m.id[i]=='-')))) return false;
  unsigned groups=0,digits=0;
  for(unsigned i=0;;i++) { char c=m.version[i]; if(c=='.' || !c) { if(!digits || digits>6) return false;groups++;digits=0;if(!c) break; } else if(c>='0' && c<='9') digits++; else return false; }
  if(groups!=3) return false;
  *out=m;return true;
}
void init() {
  sState=Working;
  if(!sVolume.mount() && (sVolume.state()!=State::Unprovisioned || !sVolume.reserve())) { fail(9);return; }
  for(unsigned slot=0;slot<Slots;slot++) sCapacity[slot]=sVolume.capacity(slot);
  refresh();sState=Ready;sError=0;
}
uint32_t revision() { return sRevision; }
bool busy() { return sPending || sState==Backup || sState==Receiving || sState==Working; }
void acknowledge() { if(sPending) sAcknowledged=true; }
void abandonSetup() { if(sPending && !sAcknowledged) sPending=0; }
bool request(uint8_t command,uint32_t arg,const uint8_t *data,size_t size) {
  if(DevelopmentUpdate::busy() || sPending || sOpen>=0) return false;
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
    sLength=arg;sReceived=0;sState=Receiving;sError=0;return true;
  }
  if(command==0x64) {
    if(sState!=Receiving || !size || size>512 || arg!=sReceived || size>sLength-sReceived) return false;
    memcpy(sUpload+sReceived,data,size);sReceived+=size;return true;
  }
  if(command==0x65) return !size && !arg && sState==Receiving && sReceived==sLength && queue(command,0);
  if(command==0x66 || command==0x6a) return !size && idle() && arg<Slots && sCatalog[arg].bytes && queue(command,arg);
  if(command==0x67) {
    if(size || arg || sState==Working) return false;
    sState=Cold;sReceived=sLength=sBackupOffset=0;sError=0;return true;
  }
  return false;
}
bool response(uint8_t command,uint32_t arg,uint8_t *data,size_t capacity,size_t *size) {
  if(!data || !size || capacity>512) return false;
  if(command==0x60) {
    uint32_t status[16]={0x3141464c,1,sPending?Working:sState,sError,sReceived,sLength,1,Slots,1,BackupBytes,sBackupOffset,static_cast<uint32_t>(sVolume.state()),sVolume.progress(),sTarget,sPending,2};
    *size=capacity<sizeof(status)?capacity:sizeof(status);memcpy(data,status,*size);return !arg;
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
    if(!idle() || arg || capacity<40) return false;
    uint32_t total=0,used=0,available=0,installed=0;
    for(unsigned slot=0;slot<Slots;slot++) {
      const auto e=sVolume.entry(slot);total+=sCapacity[slot];used+=e.packageBytes+e.dataBytes;
      if(e.packageBytes) installed++;else available+=sCapacity[slot];
    }
    uint32_t summary[10]={0x5341464c,1,BlockCount*PagesPerBlock*PageBytes,total,used,available,installed,Slots,MaximumPackage,MaximumData};
    memcpy(data,summary,sizeof(summary));*size=sizeof(summary);return true;
  }
  if(command==0x68) {
    if(!idle() || arg>=Slots) return false;
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
  if(sPending && sAcknowledged) {
    uint8_t command=sPending;sPending=0;sAcknowledged=false;
    if(command==0x60) { if(sVolume.mount()) { refresh();sState=Ready;sError=0; } else sState=sVolume.state()==State::Unprovisioned?Unprovisioned:Error; }
    else if(command==0x62) { sState=Working;if(!sVolume.provision(sBackupDigest)) fail(2);else { refresh();sState=Ready; } }
    else if(command==0x65) {
      Metadata m; if(!metadata(sUpload,sLength,&m) || m.abi!=1) { fail(3);return; }
      int target=-1;
      for(unsigned i=0;i<Slots;i++) if(sCatalog[i].bytes && !strcmp(sCatalog[i].metadata.id,m.id)) { target=i;break; }
      uint32_t bytes=0;
      if(target>=0) {
        auto e=sVolume.entry(target);bytes=e.dataBytes;
        if(!sVolume.read(target,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData))) { fail(4);return; }
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
        if(!order) { sTarget=target;sState=Complete;return; }
      } else for(unsigned i=0;i<Slots;i++) if(!sVolume.entry(i).packageBytes) { target=i;break; }
      if(target<0) { fail(5);return; }
      sTarget=target;sState=Working;
      if(!sVolume.begin(target,sUpload,sLength,sUploadData,bytes)) fail(6);
    } else if(command==0x66) { sTarget=sPendingArgument;sState=Working;if(!sVolume.begin(sTarget,nullptr,0,nullptr,0)) fail(6); }
    else if(command==0x6a) { auto e=sVolume.entry(sPendingArgument);if(!sVolume.read(sPendingArgument,sLoaded,sizeof(sLoaded),sUploadData,sizeof(sUploadData))) fail(4);else { sLoadedBytes=e.packageBytes;sState=Complete; } }
  }
  if(sState==Working) {
    sVolume.step();
    if(sVolume.state()==State::Failed) fail(7);
    else if(sVolume.state()==State::Complete) { refresh();sState=Complete;sError=0; }
  }
}
const CatalogEntry &entry(unsigned slot) { return sCatalog[slot<Slots?slot:0]; }
bool open(unsigned slot) {
  if(busy() || slot>=Slots || !sCatalog[slot].bytes || sOpen>=0) return false;
  auto e=sVolume.entry(slot);
  if(!sVolume.read(slot,sLoaded,sizeof(sLoaded),sData,sizeof(sData)) || !NativeApp::load(sLoaded,e.packageBytes)) return false;
  sOpen=slot;sLoadedBytes=e.packageBytes;sDataBytes=e.dataBytes;sDirty=false;return true;
}
void close() {
  if(sOpen<0) return;
  unsigned slot=sOpen;sOpen=-1;
  if(sDirty && NativeApp::lastResult()==1) { sTarget=slot;sState=Working;if(!sVolume.begin(slot,sLoaded,sLoadedBytes,sData,sDataBytes)) fail(6); }
  sDirty=false;
}
int readData(uint32_t offset,void *data,uint32_t size) {
  if(sOpen<0 || !data || offset>sDataBytes || size>sDataBytes-offset) return -1;
  memcpy(data,sData+offset,size);return size;
}
int writeData(uint32_t offset,const void *data,uint32_t size) {
  if(sOpen<0 || !data || offset>MaximumData || size>MaximumData-offset) return -1;
  if(offset>sDataBytes) memset(sData+sDataBytes,0,offset-sDataBytes);
  memcpy(sData+offset,data,size);if(offset+size>sDataBytes) sDataBytes=offset+size;sDirty=true;return size;
}
}}

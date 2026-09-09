#include "nand_update.h"
#include "usb_diagnostics.h"
#include "development_update.h"

#include "registers.h"
#include "update_trust_root.h"
#include "release_version.h"

#include <string.h>

namespace {
using PrimeG2::NANDUpdate::Error;
using PrimeG2::NANDUpdate::Manifest;
using PrimeG2::NANDUpdate::State;

constexpr uint32_t ModelHPG2 = 0x32475048;
constexpr uint32_t CurrentVersion[4] = LEFONY_UPDATE_VERSION;
constexpr uint32_t PageBytes=2048, PagesPerBlock=64, SlotBlocks=64;
constexpr uint32_t SlotAFirstBlock=32, SlotBFirstBlock=3968;
constexpr uint32_t MetadataBlocks[2]={104,105};
constexpr uint32_t MetadataMagic=0x314D4241, MetadataCommitted=0x434F4D4D;
constexpr uint32_t NoSlot=0xffffffff;
constexpr uintptr_t BootHandoffAddress=0x87fff000;
constexpr uint32_t BootHandoffMagic=0x3142464c; // "LFB1"
constexpr uint32_t BootHandoffSchema=2;
constexpr uintptr_t ConfirmMagicAddress=PrimeG2::SNVS+0x68;
constexpr uintptr_t ConfirmSlotAddress=PrimeG2::SNVS+0x6c;
constexpr uint32_t ConfirmMagic=0x4b4f464c; // "LFOK"

struct BootHandoff {
  uint32_t magic,booted,active,pending,attempts,bootLimit,generation,schema;
  uint32_t version[4],reserved[4];
};

struct SHA256 { uint32_t state[8]; uint64_t bytes; uint8_t buffer[64]; size_t buffered; };
constexpr uint32_t K[64]={
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
uint32_t rr(uint32_t v,unsigned n){return(v>>n)|(v<<(32-n));}
uint32_t be32(const uint8_t*p){return(uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3];}
void shaTransform(SHA256*c,const uint8_t*b){
  uint32_t w[64];for(unsigned i=0;i<16;i++)w[i]=be32(b+i*4);
  for(unsigned i=16;i<64;i++){uint32_t a=w[i-15],d=w[i-2];w[i]=w[i-16]+(rr(a,7)^rr(a,18)^(a>>3))+w[i-7]+(rr(d,17)^rr(d,19)^(d>>10));}
  uint32_t a=c->state[0],b0=c->state[1],cc=c->state[2],d=c->state[3],e=c->state[4],f=c->state[5],g=c->state[6],h=c->state[7];
  for(unsigned i=0;i<64;i++){uint32_t t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^((~e)&g))+K[i]+w[i];uint32_t t2=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b0)^(a&cc)^(b0&cc));h=g;g=f;f=e;e=d+t1;d=cc;cc=b0;b0=a;a=t1+t2;}
  c->state[0]+=a;c->state[1]+=b0;c->state[2]+=cc;c->state[3]+=d;c->state[4]+=e;c->state[5]+=f;c->state[6]+=g;c->state[7]+=h;
}
void shaInit(SHA256*c){const uint32_t v[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};memcpy(c->state,v,sizeof(v));c->bytes=0;c->buffered=0;}
void shaUpdate(SHA256*c,const uint8_t*p,size_t n){c->bytes+=n;while(n){size_t a=64-c->buffered;if(a>n)a=n;memcpy(c->buffer+c->buffered,p,a);c->buffered+=a;p+=a;n-=a;if(c->buffered==64){shaTransform(c,c->buffer);c->buffered=0;}}}
void shaFinal(SHA256*c,uint8_t out[32]){uint64_t bits=c->bytes*8;c->buffer[c->buffered++]=0x80;if(c->buffered>56){memset(c->buffer+c->buffered,0,64-c->buffered);shaTransform(c,c->buffer);c->buffered=0;}memset(c->buffer+c->buffered,0,56-c->buffered);for(unsigned i=0;i<8;i++)c->buffer[63-i]=bits>>(i*8);shaTransform(c,c->buffer);for(unsigned i=0;i<8;i++){out[i*4]=c->state[i]>>24;out[i*4+1]=c->state[i]>>16;out[i*4+2]=c->state[i]>>8;out[i*4+3]=c->state[i];}}
void sha256(const uint8_t*p,size_t n,uint8_t out[32]){SHA256 c;shaInit(&c);shaUpdate(&c,p,n);shaFinal(&c,out);}

constexpr size_t RSAWords=64;typedef uint32_t BigInt[RSAWords];
void fromWire(BigInt v,const uint8_t*w){for(size_t i=0;i<RSAWords;i++){size_t o=256-(i+1)*4;v[i]=be32(w+o);}}
int compare(const BigInt a,const BigInt b){for(size_t i=RSAWords;i-->0;)if(a[i]!=b[i])return a[i]<b[i]?-1:1;return 0;}
void subtract(BigInt a,const BigInt b){uint64_t borrow=0;for(size_t i=0;i<RSAWords;i++){uint64_t s=uint64_t(b[i])+borrow,v=a[i];a[i]=uint32_t(v-s);borrow=v<s;}}
void addMod(BigInt o,const BigInt a,const BigInt b,const BigInt m){uint64_t c=0;for(size_t i=0;i<RSAWords;i++){uint64_t s=uint64_t(a[i])+b[i]+c;o[i]=uint32_t(s);c=s>>32;}if(c||compare(o,m)>=0)subtract(o,m);}
void multiplyMod(BigInt o,const BigInt a,const BigInt b,const BigInt m){BigInt r={},x,t;memcpy(x,a,sizeof(x));for(size_t bit=0;bit<2048;bit++){if((b[bit/32]>>(bit&31))&1){addMod(t,r,x,m);memcpy(r,t,sizeof(r));}addMod(t,x,x,m);memcpy(x,t,sizeof(x));}memcpy(o,r,sizeof(r));}
bool verifySignature(const Manifest&m){
  BigInt n,b,r,t;fromWire(n,PrimeG2UpdateModulus);fromWire(b,m.signature);if(compare(b,n)>=0)return false;memcpy(r,b,sizeof(r));for(unsigned i=0;i<16;i++){multiplyMod(t,r,r,n);memcpy(r,t,sizeof(r));}multiplyMod(t,r,b,n);memcpy(r,t,sizeof(r));
  uint8_t em[256];for(size_t i=0;i<RSAWords;i++){uint32_t w=r[i];size_t o=256-(i+1)*4;em[o]=w>>24;em[o+1]=w>>16;em[o+2]=w>>8;em[o+3]=w;}
  uint8_t digest[32];sha256(reinterpret_cast<const uint8_t*>(&m),PrimeG2::NANDUpdate::SignedPrefixBytes,digest);
  const uint8_t der[]={0x30,0x31,0x30,0x0d,0x06,0x09,0x60,0x86,0x48,0x01,0x65,0x03,0x04,0x02,0x01,0x05,0x00,0x04,0x20};
  if(em[0]||em[1]!=1)return false;
  size_t d=2;
  while(d<sizeof(em)&&em[d]==0xff)d++;
  if(d<10||d>=sizeof(em)||em[d++]!=0||
      sizeof(em)-d!=sizeof(der)+sizeof(digest))return false;
  return !memcmp(em+d,der,sizeof(der))&&
    !memcmp(em+d+sizeof(der),digest,sizeof(digest));
}

Manifest sManifest={};PrimeG2::NANDUpdate::Status sStatus={};uint32_t sBootHandoffSlot=NoSlot;
#if PRIME_G2_EMULATOR
struct SlotMetadata{uint32_t bytes,version[4];uint8_t sha256[32];};
struct Metadata{uint32_t magic,schema,bytes,generation,active,pending,attempts,bootLimit;SlotMetadata slots[2];uint32_t committed,crc;};
alignas(4) uint8_t sPage[PageBytes];
/* Keep the on-NAND ABI independent from Ion's historical word-oriented CRC.
 * This is the conventional reflected CRC-32 used by U-Boot's crc32(0, ...). */
uint32_t metadataCRC(const Metadata&m){
  Metadata c=m;c.crc=0;uint32_t crc=0xffffffffu;
  const uint8_t*p=reinterpret_cast<const uint8_t*>(&c);
  for(size_t i=0;i<sizeof(c);i++){crc^=p[i];for(unsigned b=0;b<8;b++)crc=(crc>>1)^(0xedb88320u&uint32_t(0-int32_t(crc&1)));}
  return crc^0xffffffffu;
}
bool metadataValid(const Metadata&m){return m.magic==MetadataMagic&&m.schema==1&&m.bytes==sizeof(Metadata)&&m.committed==MetadataCommitted&&m.bootLimit&&m.bootLimit<=10&&m.active<=1&&(m.pending<=1||m.pending==NoSlot)&&m.crc==metadataCRC(m);}
#endif
void setError(Error e){sStatus.state=uint32_t(State::Error);sStatus.error=uint32_t(e);}
int compareVersion(const uint32_t a[4],const uint32_t b[4]){for(unsigned i=0;i<4;i++)if(a[i]!=b[i])return a[i]<b[i]?-1:1;return 0;}

#if PRIME_G2_EMULATOR
constexpr uintptr_t Cmd=PrimeG2::GPMI+0x100,Page=PrimeG2::GPMI+0x104,StatusReg=PrimeG2::GPMI+0x10c;
constexpr uintptr_t GeoPage=PrimeG2::GPMI+0x110,GeoOOB=PrimeG2::GPMI+0x114,GeoErase=PrimeG2::GPMI+0x118,GeoBlocks=PrimeG2::GPMI+0x11c,GeoECC=PrimeG2::GPMI+0x120;
constexpr uintptr_t Bad=PrimeG2::GPMI+0x128,Uncorrectable=PrimeG2::GPMI+0x148,FIFO32=PrimeG2::GPMI+0x14c;
bool geometryValid(){return PrimeG2::reg32(GeoPage)==PageBytes&&PrimeG2::reg32(GeoOOB)==64&&PrimeG2::reg32(GeoErase)==PageBytes*PagesPerBlock&&PrimeG2::reg32(GeoBlocks)==4096&&PrimeG2::reg32(GeoECC)>=8;}
bool blockBad(uint32_t b){PrimeG2::reg32(Page)=b*PagesPerBlock;return PrimeG2::reg32(Bad);}
bool eraseBlock(uint32_t b){PrimeG2::reg32(Page)=b*PagesPerBlock;PrimeG2::reg32(Cmd)=0xd0;return !(PrimeG2::reg32(StatusReg)&1);}
bool programPage(uint32_t p,const uint8_t*d){PrimeG2::reg32(Page)=p;PrimeG2::reg32(Cmd)=0x80;for(size_t i=0;i<PageBytes;i+=4){uint32_t w;memcpy(&w,d+i,4);PrimeG2::reg32(FIFO32)=w;}PrimeG2::reg32(Cmd)=0x10;return !(PrimeG2::reg32(StatusReg)&1);}
bool readPage(uint32_t p,uint8_t*d){PrimeG2::reg32(Cmd)=0;PrimeG2::reg32(Page)=p;for(size_t i=0;i<PageBytes;i+=4){uint32_t w=PrimeG2::reg32(FIFO32);memcpy(d+i,&w,4);}return !PrimeG2::reg32(Uncorrectable);}
bool readMetadataBlock(uint32_t b,Metadata*m){if(blockBad(b)||!readPage(b*PagesPerBlock,sPage))return false;memcpy(m,sPage,sizeof(*m));return metadataValid(*m);}
Metadata currentMetadata(int*source){Metadata v[2]={};bool ok[2]={readMetadataBlock(MetadataBlocks[0],&v[0]),readMetadataBlock(MetadataBlocks[1],&v[1])};if(ok[0]||ok[1]){*source=ok[1]&&(!ok[0]||v[1].generation>v[0].generation)?1:0;return v[*source];}*source=-1;Metadata m={};m.magic=MetadataMagic;m.schema=1;m.bytes=sizeof(m);m.active=0;m.pending=NoSlot;m.bootLimit=3;m.committed=MetadataCommitted;memcpy(m.slots[0].version,CurrentVersion,sizeof(CurrentVersion));m.crc=metadataCRC(m);return m;}
bool writeMetadataCopy(const Metadata&m,int copy){uint32_t b=MetadataBlocks[copy];if(blockBad(b)||!eraseBlock(b))return false;memset(sPage,0xff,sizeof(sPage));memcpy(sPage,&m,sizeof(m));if(!programPage(b*PagesPerBlock,sPage)||!readPage(b*PagesPerBlock,sPage))return false;Metadata r;memcpy(&r,sPage,sizeof(r));return metadataValid(r)&&!memcmp(&r,&m,sizeof(m));}
bool writeMetadata(const Metadata&m,int previous){
  /* Commit the copy that does not currently contain the newest generation
   * first. A reset at any point therefore leaves at least one valid record.
   * Mirroring is best-effort: the first verified copy is the commit point. */
  int first=previous==0?1:0;if(previous<0)first=0;
  if(!writeMetadataCopy(m,first)){int other=1-first;return writeMetadataCopy(m,other);}
  (void)writeMetadataCopy(m,1-first);return true;
}
bool installPayload(const uint8_t*payload,size_t length,Metadata*m,int source){
  uint32_t target=m->active?0:1,first=target?SlotBFirstBlock:SlotAFirstBlock;size_t capacity=0;for(uint32_t i=0;i<SlotBlocks;i++)if(!blockBad(first+i))capacity+=PageBytes*PagesPerBlock;if(length>capacity){setError(Error::SlotCapacity);return false;}
  for(uint32_t i=0;i<SlotBlocks;i++)if(!blockBad(first+i)&&!eraseBlock(first+i)){setError(Error::EraseFailed);return false;}
  size_t cursor=0;for(uint32_t i=0;i<SlotBlocks&&cursor<length;i++){if(blockBad(first+i))continue;for(uint32_t p=0;p<PagesPerBlock&&cursor<length;p++){size_t amount=length-cursor<PageBytes?length-cursor:PageBytes;memset(sPage,0xff,sizeof(sPage));memcpy(sPage,payload+cursor,amount);if(!programPage((first+i)*PagesPerBlock+p,sPage)){setError(Error::ProgramFailed);return false;}cursor+=amount;sStatus.writtenBytes=cursor;}}
  SHA256 hash;shaInit(&hash);size_t remaining=length;for(uint32_t i=0;i<SlotBlocks&&remaining;i++){if(blockBad(first+i))continue;for(uint32_t p=0;p<PagesPerBlock&&remaining;p++){if(!readPage((first+i)*PagesPerBlock+p,sPage)){setError(Error::ReadbackFailed);return false;}size_t amount=remaining<PageBytes?remaining:PageBytes;shaUpdate(&hash,sPage,amount);remaining-=amount;}}
  uint8_t digest[32];shaFinal(&hash,digest);if(remaining||memcmp(digest,sManifest.payloadSHA256,32)){setError(Error::ReadbackFailed);return false;}
  m->generation++;m->pending=target;m->attempts=0;m->slots[target].bytes=length;memcpy(m->slots[target].version,sManifest.version,sizeof(sManifest.version));memcpy(m->slots[target].sha256,digest,32);m->crc=metadataCRC(*m);if(!writeMetadata(*m,source)){setError(Error::MetadataCommitFailed);return false;}sStatus.activeSlot=m->active;sStatus.pendingSlot=target;sStatus.generation=m->generation;return true;
}
#endif
}

namespace PrimeG2 { namespace NANDUpdate {
void init(){memset(&sManifest,0,sizeof(sManifest));memset(&sStatus,0,sizeof(sStatus));sStatus.magic=StatusMagic;sStatus.protocol=2;sStatus.state=uint32_t(State::Idle);sStatus.activeSlot=0;sStatus.pendingSlot=NoSlot;sStatus.bootLimit=3;memcpy(sStatus.version,CurrentVersion,sizeof(CurrentVersion));
#if PRIME_G2_EMULATOR
sStatus.flags=FlagDirectInstall;
#else
sStatus.flags=FlagRecoveryInstall;
#endif
#if PRIME_G2_EMULATOR
if(geometryValid()){int source;Metadata m=currentMetadata(&source);sStatus.activeSlot=m.active;sStatus.pendingSlot=m.pending;sStatus.attempts=m.attempts;sStatus.bootLimit=m.bootLimit;sStatus.generation=m.generation;if(m.slots[m.active].bytes)memcpy(sStatus.version,m.slots[m.active].version,sizeof(sStatus.version));if(m.pending<=1&&m.slots[m.pending].bytes&&compareVersion(m.slots[m.pending].version,sStatus.version)>0)memcpy(sStatus.version,m.slots[m.pending].version,sizeof(sStatus.version));}else setError(Error::GeometryMismatch);
#endif
volatile BootHandoff*handoff=reinterpret_cast<volatile BootHandoff*>(BootHandoffAddress);sBootHandoffSlot=NoSlot;if(handoff->magic==BootHandoffMagic){sBootHandoffSlot=handoff->booted;if(handoff->schema==BootHandoffSchema){sStatus.activeSlot=handoff->active;sStatus.pendingSlot=handoff->pending;sStatus.attempts=handoff->attempts;sStatus.bootLimit=handoff->bootLimit;sStatus.generation=handoff->generation;for(unsigned i=0;i<4;i++)sStatus.version[i]=handoff->version[i];}handoff->magic=0;PrimeG2::barrier();}
}
bool acceptManifest(const void*data,size_t length){if(length!=sizeof(Manifest)){setError(Error::ManifestLength);return false;}
#if !PRIME_G2_EMULATOR
if(sStatus.pendingSlot<=1){setError(Error::PendingUpdateExists);return false;}
#endif
memcpy(&sManifest,data,sizeof(sManifest));if(sManifest.magic!=ManifestMagic||sManifest.schema!=1||sManifest.headerBytes!=512||sManifest.payloadBytes<0x30||sManifest.payloadBytes>8u*1024u*1024u){setError(Error::ManifestFormat);return false;}if(sManifest.model!=ModelHPG2){setError(Error::WrongModel);return false;}uint32_t manifestVersion[4];memcpy(manifestVersion,sManifest.version,sizeof(manifestVersion));if(compareVersion(manifestVersion,sStatus.version)<=0){setError(Error::VersionRejected);return false;}if(!verifySignature(sManifest)){setError(Error::SignatureRejected);return false;}sStatus.state=uint32_t(State::ManifestReady);sStatus.error=0;sStatus.totalBytes=sManifest.payloadBytes;sStatus.writtenBytes=0;memcpy(sStatus.version,manifestVersion,sizeof(manifestVersion));sStatus.flags|=FlagManifestAuthenticated;return true;}
bool noteCapsuleReady(const uint8_t*payload,size_t length){if(sStatus.state!=uint32_t(State::ManifestReady)||length!=sManifest.payloadBytes){setError(Error::CapsuleMismatch);return false;}uint8_t digest[32];sha256(payload,length,digest);if(memcmp(digest,sManifest.payloadSHA256,32)){setError(Error::CapsuleMismatch);return false;}sStatus.state=uint32_t(State::CapsuleReady);sStatus.flags|=FlagPayloadAuthenticated;return true;}
bool install(const uint8_t*payload,size_t length){if(sStatus.state!=uint32_t(State::CapsuleReady)||length!=sManifest.payloadBytes){setError(Error::CapsuleMismatch);return false;}
#if PRIME_G2_EMULATOR
if(!geometryValid()){setError(Error::GeometryMismatch);return false;}int source;Metadata m=currentMetadata(&source);sStatus.state=uint32_t(State::Installing);if(!installPayload(payload,length,&m,source))return false;sStatus.state=uint32_t(State::PendingReboot);sStatus.flags|=FlagSlotCommitted;return true;
#else
(void)payload;(void)length;setError(Error::LayoutNotProvisioned);return false;
#endif
}
bool confirmBootIfReady(){
  uint32_t slot=sBootHandoffSlot;
  if(slot>1||slot!=sStatus.pendingSlot){
    sBootHandoffSlot=NoSlot;
    return true;
  }
  bool confirmed=confirmPending();
  sBootHandoffSlot=NoSlot;
  return confirmed;
}
bool confirmPending(){
#if PRIME_G2_EMULATOR
int source;Metadata m=currentMetadata(&source);if(m.pending>1){setError(Error::NoPendingSlot);return false;}m.active=m.pending;m.pending=NoSlot;m.attempts=0;m.generation++;m.crc=metadataCRC(m);if(!writeMetadata(m,source)){setError(Error::MetadataCommitFailed);return false;}sStatus.activeSlot=m.active;sStatus.pendingSlot=NoSlot;sStatus.attempts=0;sStatus.generation=m.generation;sStatus.state=uint32_t(State::Confirmed);return true;
#else
if(sBootHandoffSlot>1||sBootHandoffSlot!=sStatus.pendingSlot)return true;
PrimeG2::reg32(ConfirmSlotAddress)=sBootHandoffSlot;
PrimeG2::reg32(ConfirmMagicAddress)=ConfirmMagic;
PrimeG2::barrier();
sStatus.state=uint32_t(State::Confirmed);
return true;
#endif
}
void abort(){memset(&sManifest,0,sizeof(sManifest));sStatus.state=uint32_t(State::Idle);sStatus.error=0;sStatus.totalBytes=0;sStatus.writtenBytes=0;sStatus.flags&=FlagDirectInstall|FlagRecoveryInstall;}
const Status&status(){return sStatus;}
}}

extern "C" bool prime_g2_update_in_progress() {
  if (PrimeG2::DevelopmentUpdate::busy()) return true;
  // App auto-suspend uses this independently of the platform idle timer.
  // A short lease covers all management traffic, including read-only NAND
  // qualification; disconnected/abandoned sessions do not inhibit sleep.
  if (PrimeG2::USBDiagnostics::managementActive()) return true;
  using PrimeG2::NANDUpdate::State;
  uint32_t state = PrimeG2::NANDUpdate::status().state;
  return state == uint32_t(State::ManifestReady) ||
    state == uint32_t(State::CapsuleReady) ||
    state == uint32_t(State::Installing) ||
    state == uint32_t(State::PendingReboot);
}

extern "C" void prime_g2_update_boot_ready() {
  (void)PrimeG2::NANDUpdate::confirmBootIfReady();
}

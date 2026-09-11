// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "native_app.h"
#include "app_management.h"
#include "system.h"
#include "timing.h"
#include <string.h>
#include "native_app_signature.h"
#include <kandinsky/context.h>
#include <ion/display.h>
#include <ion/timing.h>
extern "C" {
uintptr_t prime_app_kernel_sp = 0;
int prime_app_enter(uint32_t entry,uint32_t event,uint32_t first,uint32_t second);
}
namespace {
constexpr uint32_t Code=0x10000000,Data=0x10201000,DataEnd=0x102ef000;
constexpr uint32_t Stack=0x102f0000,End=0x10300000;
alignas(4096) uint8_t sCode[1024*1024];
alignas(4096) uint8_t sData[1024*1024];
uint32_t sEntry=0;
volatile bool sActive=false;
uint64_t sDeadline=0;
int sResult=0;
uint32_t sLastPC=0,sCalls=0,sLastService=0;
// Compose into a bounded private surface. Present once after the callback so
// drawing each glyph does not wait on LCD/DMA and consume the app deadline.
class AppSurface final : public KDContext {
public:
  AppSurface() : KDContext(KDPointZero,KDRect(0,0,320,240)) {}
  KDColor pixels[320*240];
  void pushRect(KDRect r,const KDColor *p) override {
    for (int y=0;y<r.height();y++) memcpy(pixels+(r.y()+y)*320+r.x(),p+y*r.width(),r.width()*sizeof(KDColor));
  }
  void pushRectUniform(KDRect r,KDColor c) override {
    for (int y=0;y<r.height();y++) for(int x=0;x<r.width();x++) pixels[(r.y()+y)*320+r.x()+x]=c;
  }
  void pullRect(KDRect r,KDColor *p) override {
    for (int y=0;y<r.height();y++) memcpy(p+y*r.width(),pixels+(r.y()+y)*320+r.x(),r.width()*sizeof(KDColor));
  }
};
AppSurface sSurface;
uint32_t word(const uint8_t *p) { uint32_t v; memcpy(&v,p,4); return v; }
uint16_t half(const uint8_t *p) { uint16_t v; memcpy(&v,p,2); return v; }
bool readable(uint32_t p,uint32_t n) {
  return (p>=Code && p<Code+sizeof(sCode) && n<=Code+sizeof(sCode)-p) ||
    (p>=Data && p<DataEnd && n<=DataEnd-p) || (p>=Stack && p<End && n<=End-p);
}
bool user(uint32_t psr) { return sActive && (psr&31)==16; }
bool expired() { return PrimeG2::Timing::interruptTicks()>=sDeadline; }
}
namespace PrimeG2 { namespace NativeApp {
bool load(const uint8_t *package,size_t size) {
  if (sActive) return false;
  sEntry=0;
  System::mapNativeApp(nullptr,nullptr);
  if (!package) return false;
  const bool signedPackage=size>=8 && !memcmp(package,"LFAPP1\0\0",8);
#if !PRIME_G2_EMULATOR
  if (!signedPackage) return false;
#endif
  if (signedPackage) {
    if (!NativeAppSignature::unwrap(package,size,&package,&size)) return false;
  }
  if (size<116 || size>MaximumPackage || memcmp(package,"LFAPP0\0\0",8) ||
      word(package+8) || word(package+20)>1 || word(package+56) || word(package+60)) return false;
#if !PRIME_G2_EMULATOR
  if (word(package+20)!=1) return false;
#endif
  uint32_t metadata=word(package+12),length=word(package+16);
  if (!metadata || metadata>4096 || length<52 || length>2*1024*1024 || size!=64+metadata+length) return false;
  uint8_t digest[32];
  NativeAppHash::sha256(package+64,size-64,digest);
  if (memcmp(digest,package+24,32)) return false;
  // ABI 0 remains a VM compatibility path; physical apps require signed ABI 1.
  const uint8_t *image=package+64+metadata;
  const uint8_t ident[16]={0x7f,'E','L','F',1,1,1};
  if (memcmp(image,ident,16) || half(image+16)!=2 || half(image+18)!=40 || word(image+20)!=1 ||
      half(image+40)!=52 || half(image+42)!=32 || word(image+36)!=0x05000400) return false;
  uint32_t entry=word(image+24),offset=word(image+28),count=half(image+44);
  if (!count || count>8 || offset<52 || offset>length || count*32>length-offset || (entry&3)) return false;
  bool code=false,data=false,validEntry=false;
  for (unsigned pass=0;pass<2;pass++) {
    if (pass) { memset(sCode,0,sizeof(sCode)); memset(sData,0,sizeof(sData)); }
    for (uint32_t i=0;i<count;i++) {
      const uint8_t *h=image+offset+i*32;
      uint32_t type=word(h),file=word(h+4),address=word(h+8),physical=word(h+12);
      uint32_t bytes=word(h+16),memory=word(h+20),flags=word(h+24),align=word(h+28);
      if (!type) continue;
      if (type==0x6474e551 && flags==6) continue;
      if (type!=1) return false;
      if (!bytes && !memory && !address && !physical && flags==6) continue;
      uint32_t low=flags==5?Code:Data,high=flags==5?Code+sizeof(sCode):DataEnd;
      if ((flags!=5 && flags!=6) || !memory || bytes>memory || file>length || bytes>length-file ||
          address<low || address>=high || memory>high-address || address!=physical ||
          align<4096 || align>0x100000 || (align&(align-1)) || address%align!=file%align) return false;
      if (!pass) {
        if ((flags==5 && code) || (flags==6 && data)) return false;
        if (flags==5) { code=true; validEntry=entry>=address && entry-address<bytes; }
        else data=true;
      } else {
        memcpy((flags==5?sCode:sData)+(address-(flags==5?Code:0x10200000)),image+file,bytes);
      }
    }
    if (!code || !validEntry) return false;
  }
  System::cleanDataCacheRange(sCode,sizeof(sCode));
  System::cleanDataCacheRange(sData,sizeof(sData));
  System::mapNativeApp(sCode,sData);
  sEntry=entry; sResult=0;
  sSurface.fillRect(KDRect(0,0,320,240),KDColorWhite);
  return true;
}
int invoke(uint32_t event,uint32_t first,uint32_t second) {
  if (!sEntry || sActive) return -1;
  // Experimental VM budget includes modeled display-service latency. This is
  // a bounded one-second callback, not a physical performance qualification.
  sDeadline=Timing::interruptTicks()+1000;
  sCalls=0; sLastPC=0; sLastService=0;
  sActive=true;
  sResult=prime_app_enter(sEntry,event,first,second);
  sActive=false;
  if (sResult==1) Ion::Display::pushRect(KDRect(0,0,320,240),sSurface.pixels);
  if (sResult!=1) { sEntry=0; System::mapNativeApp(nullptr,nullptr); }
  return sResult;
}
void unload() { if(!sActive) { sEntry=0;sResult=0;System::mapNativeApp(nullptr,nullptr); } }
int lastResult() {
  return sResult;
}
uint32_t diagnostic(unsigned index) {
  return index==0?sLastPC:index==1?sCalls:sLastService;
}
const void *pixels() {
  return sEntry?sSurface.pixels:nullptr;
}
}}
extern "C" int prime_app_fault(unsigned kind,const uint32_t *,uint32_t,uint32_t psr) {
  return user(psr)?-10-static_cast<int>(kind):0;
}
extern "C" int prime_app_irq_expired(uint32_t psr,uint32_t pc) {
  if (user(psr)) sLastPC=pc;
  return user(psr) && expired()?-2:0;
}
extern "C" int prime_app_svc(uint32_t *r,uint32_t psr) {
  if (!user(psr)) return -100;
  sCalls++; sLastService=r[0]; sLastPC=r[13];
  if (expired()) return -2;
  if (r[0]==0) return 1;
  if (r[0]==3) { r[0]=static_cast<uint32_t>(Ion::Timing::millis()); return 0; }
  if (r[0]==4 || r[0]==5) {
    if (!readable(r[1],12)) { r[0]=uint32_t(-4); return 0; }
    uint32_t args[3]; memcpy(args,reinterpret_cast<const void *>(r[1]),12);
    const uint32_t pointer=args[1],length=args[2];
    const bool writable=(pointer>=Data && pointer<DataEnd && length<=DataEnd-pointer) ||
      (pointer>=Stack && pointer<End && length<=End-pointer);
    if (length>4096 || !readable(pointer,length) || (r[0]==4 && !writable)) { r[0]=uint32_t(-4); return 0; }
    r[0]=r[0]==4?PrimeG2::AppManagement::readData(args[0],reinterpret_cast<void *>(pointer),length):
      PrimeG2::AppManagement::writeData(args[0],reinterpret_cast<const void *>(pointer),length);
    return 0;
  }
  if (r[0]!=1 && r[0]!=2) { r[0]=static_cast<uint32_t>(-3); return 0; }
  uint32_t address=r[1],bytes=r[0]==1?20:24;
  if (!readable(address,bytes)) { r[0]=static_cast<uint32_t>(-4); return 0; }
  uint32_t args[6]={}; memcpy(args,reinterpret_cast<const void *>(address),bytes);
  int32_t x=args[0],y=args[1];
  auto *context=&sSurface;
  context->setOrigin(KDPointZero); context->setClippingRect(KDRect(0,0,320,240));
  if (r[0]==1) {
    int32_t w=args[2],h=args[3];
    if (x<0 || y<0 || x>=320 || y>=240 || w<=0 || h<=0 || w>320-x || h>240-y || args[4]>65535) {
      r[0]=static_cast<uint32_t>(-4); return 0;
    }
    context->fillRect(KDRect(x,y,w,h),KDColor::RGB16(args[4]));
  } else {
    if (x<0 || y<0 || x>=320 || y>=240 || args[2]>65535 || args[3]>65535 ||
        args[5]>128 || !readable(args[4],args[5])) { r[0]=static_cast<uint32_t>(-4); return 0; }
    char text[129]; memcpy(text,reinterpret_cast<const void *>(args[4]),args[5]); text[args[5]]=0;
    for (unsigned i=0;i<args[5];i++) if (text[i]<32 || text[i]>126) { r[0]=static_cast<uint32_t>(-4); return 0; }
    context->drawString(text,KDPoint(x,y),KDFont::SmallFont,KDColor::RGB16(args[2]),KDColor::RGB16(args[3]));
  }
  r[0]=0; return 0;
}

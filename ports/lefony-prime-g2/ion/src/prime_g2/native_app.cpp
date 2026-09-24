// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "native_app.h"
#include "native_app_manifest.h"
#include "lefony/foreground_wire.h"
#include "app_text.h"
#include "app_system.h"
#include "app_channel.h"
#include "app_input_stream.h"
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
alignas(8) uint32_t prime_app_user_context[82] = {};
int prime_app_enter(uint32_t entry,uint32_t event,uint32_t first,uint32_t second);
int prime_app_resume();
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
uint32_t sLastEvent=0,sElapsed=0,sDrawPixels=0;
uint32_t sKeyEvents=0,sTouchEvents=0;
int sCrashResult=0;
uint32_t sCrashPC=0,sCrashEvent=0;
Lefony::InputSnapshot sInput;
bool sInputPrepared=false;
uint32_t sInputSequence=0;
PrimeG2::AppInputStream sInputStream;
bool sChannelInputPaused=false;
uint32_t sNavigationDepth=0;
bool sSurfaceDirty=false;
// Opt-in foreground execution. Legacy callbacks keep their original bounds.
bool sResumable=false,sSuspended=false,sExited=false,sForeground=false;
bool sPublicForeground=false;
bool sForcedExit=false;
int32_t sProgramStatus=0;
uint32_t sDeclaredFeatures=0;
uint32_t sPreemptions=0,sYields=0,sResumes=0;
constexpr uint32_t Heap=0x11001000,HeapEnd=0x117ff000;
alignas(4096) uint8_t sHeap[8*1024*1024];
bool sHeapMapped=false;
bool sHeapPreparing=false;
uint32_t sHeapPrepared=0;
uint64_t sHeapStarted=0,sSleepUntil=0;
uint32_t sFrames=0,sLastFrameMillis=0;
uint32_t sPixelFrames=0,sFirstPixelMillis=0,sFirstPixelElapsed=0;
uint32_t sHeapSetupMillis=0;
#if PRIME_G2_EMULATOR
uint32_t sForegroundWakes=0,sUITimers=0;
PrimeG2::NativeApp::ResourceProfile sProfile={};
PrimeG2::NativeApp::HeapResourceProfile sHeapProfile={};
bool sHeapProfileMapped=false;
constexpr uint32_t HeapArmed=1,HeapObserved=2,HeapInvalid=4,HeapSaturated=8,HeapPartial=16;
constexpr uint32_t ProfileArmed=1,ProfileLoaded=2,ProfileInvalidSP=4,ProfileSaturated=8;
constexpr uint8_t StackPaint=0xa5;
void profileIncrement(uint32_t &value) {
  if(value==0xffffffffu) sProfile.flags|=ProfileSaturated;
  else value++;
}
bool profiling() { return sProfile.flags&ProfileLoaded; }
void profileHeap() {
  if(!profiling() || !(sHeapProfile.flags&HeapArmed) || !sHeapProfileMapped) return;
  const volatile uint32_t *p=reinterpret_cast<const volatile uint32_t *>(sHeapProfile.address);
  uint32_t before=p[3];
  if(before&1) {sHeapProfile.flags|=HeapPartial;return;}
  LefonyHeapProfile value;
  uint32_t words[sizeof(value)/4];
  for(unsigned i=0;i<sizeof(value)/4;i++) words[i]=p[i];
  memcpy(&value,words,sizeof(value));
  asm volatile("dmb ish" ::: "memory");
  if(before!=p[3] || value.sequence!=before) {sHeapProfile.flags|=HeapPartial;return;}
  if(value.magic!=LEFONY_HEAP_PROFILE_MAGIC || value.schema!=LEFONY_HEAP_PROFILE_SCHEMA ||
      value.size!=sizeof(value) || (value.flags&~7u) || (value.flags&LEFONY_HEAP_PROFILE_INVALID) ||
      value.allocatedBytes>value.arenaBytes || value.arenaBytes>value.arenaPeak ||
      value.allocatedBytes>value.allocatedPeak || value.allocatedPeak>value.arenaPeak ||
      value.arenaPeak>HeapEnd-Heap ||
      (!!value.observations!=!!(value.flags&LEFONY_HEAP_PROFILE_OBSERVED)) ||
      (!(value.flags&LEFONY_HEAP_PROFILE_OBSERVED) &&
        (value.allocatedBytes || value.allocatedPeak || value.arenaBytes || value.arenaPeak))) {
    sHeapProfile.flags|=HeapInvalid;return;
  }
  sHeapProfile.flags&=~HeapPartial;
  if(value.flags&LEFONY_HEAP_PROFILE_OBSERVED) sHeapProfile.flags|=HeapObserved;
  if(value.flags&LEFONY_HEAP_PROFILE_SATURATED) sHeapProfile.flags|=HeapSaturated;
  if(sHeapProfile.samples==0xffffffffu) sHeapProfile.flags|=HeapSaturated;
  else sHeapProfile.samples++;
  sHeapProfile.allocatedBytes=value.allocatedBytes;sHeapProfile.arenaBytes=value.arenaBytes;
  sHeapProfile.observations=value.observations;
  if(value.allocatedPeak>sHeapProfile.allocatedPeak) sHeapProfile.allocatedPeak=value.allocatedPeak;
  if(value.arenaPeak>sHeapProfile.arenaPeak) sHeapProfile.arenaPeak=value.arenaPeak;
}
void profileStack() {
  if(!profiling() || sActive) return;
  profileHeap();
  if(sHeapMapped) sProfile.heapReservedPeak=HeapEnd-Heap;
  // Read the app's mapped alias while it still exists; the backing sData alias
  // need not reflect dirty user cache lines. No scan runs inside an app slice.
  const volatile uint8_t *p=reinterpret_cast<const volatile uint8_t *>(Stack);
  uint32_t untouched=0;
  while(untouched<End-Stack && p[untouched]==StackPaint) untouched++;
  uint32_t written=End-Stack-untouched;
  if(written>sProfile.stackWrittenBytes) sProfile.stackWrittenBytes=written;
}
void profileFinish() {
  if(!profiling()) return;
  profileStack();profileIncrement(sProfile.finishedLoads);
  sProfile.flags&=~ProfileLoaded;
}
void profileSample() {
  if(!profiling()) return;
  profileHeap();
  uint32_t userSP;
  // Exceptions run privileged. As in prime_app_suspend, ^ selects the banked
  // user register, not this C helper's kernel stack pointer.
  asm volatile("stmia %0, {sp}^\n\tnop" : : "r"(&userSP) : "memory");
  profileIncrement(sProfile.samples);
  if(userSP<Stack || userSP>End) {sProfile.flags|=ProfileInvalidSP;return;}
  uint32_t used=End-userSP;
  if(used>sProfile.stackPointerBytes) sProfile.stackPointerBytes=used;
}
#endif
void resetExecution() {
  PrimeG2::AppSystem::finish();
  PrimeG2::AppChannel::clear();
  sChannelInputPaused=false;
  sInputStream.focus(false);
  if(sHeapMapped) {
    PrimeG2::System::cleanInvalidateDataCacheRange(reinterpret_cast<const void *>(Heap),HeapEnd-Heap);
    PrimeG2::System::mapNativeAppHeap(nullptr);
  }
  sHeapMapped=false;sHeapPreparing=false;sHeapPrepared=0;sHeapSetupMillis=0;
  sSleepUntil=0;sFrames=0;sLastFrameMillis=0;sPublicForeground=false;
  sPixelFrames=0;sFirstPixelMillis=0;sFirstPixelElapsed=0;
#if PRIME_G2_EMULATOR
  sForegroundWakes=0;sUITimers=0;
  sHeapProfileMapped=false;
#endif
  sResumable=false;sSuspended=false;sExited=false;sForeground=false;
  sForcedExit=false;sDeclaredFeatures=0;sProgramStatus=0;
  sPreemptions=0;sYields=0;sResumes=0;
  memset(prime_app_user_context,0,sizeof(prime_app_user_context));
}
// Compose into a bounded private surface. Present once after the callback so
// drawing each glyph does not wait on LCD/DMA and consume the app deadline.
class AppSurface final : public KDContext {
public:
  AppSurface() : KDContext(KDPointZero,KDRect(0,0,320,240)) {}
  KDColor pixels[320*240];
  void pushRect(KDRect r,const KDColor *p) override {
    sSurfaceDirty=true;
    for (int y=0;y<r.height();y++) memcpy(pixels+(r.y()+y)*320+r.x(),p+y*r.width(),r.width()*sizeof(KDColor));
  }
  void pushRectUniform(KDRect r,KDColor c) override {
    sSurfaceDirty=true;
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
  if(sHeapMapped && p>=Heap && p<HeapEnd && n<=HeapEnd-p) return true;
  return (p>=Code && p<Code+sizeof(sCode) && n<=Code+sizeof(sCode)-p) ||
    (p>=Data && p<DataEnd && n<=DataEnd-p) || (p>=Stack && p<End && n<=End-p);
}
bool writable(uint32_t p,uint32_t n) {
  if(sHeapMapped && p>=Heap && p<HeapEnd && n<=HeapEnd-p) return true;
  return (p>=Data && p<DataEnd && n<=DataEnd-p) || (p>=Stack && p<End && n<=End-p);
}
bool rectangle(const uint32_t *a) {
  return a[0]<320 && a[1]<240 && a[2]>0 && a[3]>0 && a[2]<=320-a[0] && a[3]<=240-a[1] && a[4]<=65535;
}
bool user(uint32_t psr) { return sActive && (psr&31)==16; }
bool expired() { return PrimeG2::Timing::interruptTicks()>=sDeadline; }
}
namespace PrimeG2 { namespace NativeApp {
bool load(const uint8_t *package,size_t size) {
  if (sActive) return false;
#if PRIME_G2_EMULATOR
  profileFinish();
#endif
  sEntry=0;
  resetExecution();
  System::mapNativeApp(nullptr,nullptr);
  if (!package) return false;
  const bool signedPackage=size>=8 && !memcmp(package,"LFAPP1\0\0",8);
  uint8_t channelHash[32]={},channelSigner[32]={};
#if !PRIME_G2_EMULATOR
  if (!signedPackage) return false;
#endif
  if (signedPackage) {
    const uint8_t *envelope=package;
    if (!AppManagement::unwrap(package,size,&package,&size)) return false;
    memcpy(channelHash,envelope+56,32);memcpy(channelSigner,envelope+24,32);
  }
  if (size<116 || size>MaximumPackage || memcmp(package,"LFAPP0\0\0",8) ||
      word(package+8)>1 || word(package+20)>1 || word(package+56) || word(package+60)) return false;
#if !PRIME_G2_EMULATOR
  if (word(package+20)!=1) return false;
#endif
  uint32_t metadata=word(package+12),length=word(package+16);
  if (!metadata || metadata>4096 || length<52 || length>2*1024*1024 || size!=64+metadata+length) return false;
  uint8_t digest[32];
  NativeAppHash::sha256(package+64,size-64,digest);
  if (memcmp(digest,package+24,32)) return false;
  NativeAppManifest::Manifest manifest;
  if(!NativeAppManifest::parse(package+64,metadata,word(package+8),word(package+20),&manifest) ||
      !NativeAppManifest::supported(manifest)) return false;
  // ABI 0 remains a VM compatibility path; physical apps require signed ABI 1.
  const uint8_t *image=package+64+metadata;
  const uint8_t ident[16]={0x7f,'E','L','F',1,1,1};
  if (memcmp(image,ident,16) || half(image+16)!=2 || half(image+18)!=40 || word(image+20)!=1 ||
      half(image+40)!=52 || half(image+42)!=32 || word(image+36)!=0x05000400) return false;
  uint32_t entry=word(image+24),offset=word(image+28),count=half(image+44);
  if (!count || count>8 || offset<52 || offset>length || count*32>length-offset || (entry&3)) return false;
  bool code=false,data=false,validEntry=false;
#if PRIME_G2_EMULATOR
  uint32_t codeBytes=0,staticBytes=0;
#endif
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
#if PRIME_G2_EMULATOR
        if(flags==5) codeBytes=memory;else {
          staticBytes=memory;
          sHeapProfileMapped=sHeapProfile.address>=address &&
            sHeapProfile.address-address<=bytes && sizeof(LefonyHeapProfile)<=bytes-(sHeapProfile.address-address);
        }
#endif
        if ((flags==5 && code) || (flags==6 && data)) return false;
        if (flags==5) { code=true; validEntry=entry>=address && entry-address<bytes; }
        else data=true;
      } else {
        memcpy((flags==5?sCode:sData)+(address-(flags==5?Code:0x10200000)),image+file,bytes);
      }
    }
    if (!code || !validEntry) return false;
  }
#if PRIME_G2_EMULATOR
  if(sProfile.flags&ProfileArmed) {
    uint8_t hash[32];NativeAppHash::sha256(package,size,hash);
    if(!memcmp(hash,sProfile.packageHash,sizeof(hash))) {
      sProfile.flags|=ProfileLoaded;profileIncrement(sProfile.loads);
      sProfile.codeBytes=codeBytes;sProfile.staticBytes=staticBytes;
      if(sHeapProfile.flags&HeapArmed) {
        sHeapProfile.loads=sProfile.loads;
        if(!sHeapProfileMapped) sHeapProfile.flags|=HeapInvalid;
      }
      memset(sData+Stack-0x10200000,StackPaint,End-Stack);
    }
  }
#endif
  System::cleanDataCacheRange(sCode,sizeof(sCode));
  System::cleanDataCacheRange(sData,sizeof(sData));
  System::mapNativeApp(sCode,sData);
  sEntry=entry; sResult=0;sKeyEvents=0;sTouchEvents=0;sCrashResult=0;sCrashPC=0;sCrashEvent=0;
  sDeclaredFeatures=manifest.required|manifest.optional;
  if(signedPackage) AppChannel::owner(manifest.id,manifest.name,channelHash,channelSigner);
  sInput=Lefony::InputSnapshot{};sInputPrepared=false;sInputSequence=0;
  sNavigationDepth=0;
  sSurface.fillRect(KDRect(0,0,320,240),KDColorWhite);
  return true;
}
void prepareInput(const Lefony::InputSnapshot &input) {
  if(sActive) return;
  sInput=input;sInputPrepared=true;
  if(input.event==3) {
    LefonyContactTransition touch={};touch.phase=input.touchPhase;touch.count=input.contactCount;
    for(unsigned i=0;i<2;i++) touch.contacts[i]={input.contacts[i].id,input.contacts[i].x,input.contacts[i].y};
    sInputStream.touch(touch,input.flags&Lefony::ContactsChanged?LEFONY_INPUT_CONTACTS_CHANGED:0,
                       static_cast<uint32_t>(Ion::Timing::millis()));
  }
}
void observeKeyboard(uint64_t physicalKeys,uint32_t modifiers) {
  // Reset only at the OS modal boundary, preserving queued edges between scans.
  // Resuming blocks keys still held from the consent gesture until release.
  bool paused=AppChannel::pairing();
  if(paused!=sChannelInputPaused) {
    sChannelInputPaused=paused;sInputStream.focus(sForeground && !paused);
  }
  sInputStream.observe(physicalKeys,static_cast<uint32_t>(Ion::Timing::millis()),modifiers);
}
uint32_t navigationDepth() { return sEntry?sNavigationDepth:0; }
static int execute(uint32_t event,uint32_t first,uint32_t second,bool deliverInput) {
  if (!sEntry || sActive) return -1;
  if(AppChannel::pairing() && event!=4) {sInputPrepared=false;return sResult;}
  if(event==1) sKeyEvents++;
  if(event==3) sTouchEvents++;
  if(sExited) { sInputPrepared=false;return sResult; }
  if(sResumable && event==4) {
    // OS-owned close terminates even a non-cooperative program. No further
    // user instruction runs; resources are reclaimed by the normal unload.
    sExited=true;sSuspended=false;sForcedExit=true;
    AppSystem::finish();
    AppChannel::finish();
    memset(prime_app_user_context,0,sizeof(prime_app_user_context));
    return sResult=1;
  }
  if(deliverInput) {
    if(!sInputPrepared || sInput.event!=event) sInput=Lefony::InputSnapshot{};
    sInputPrepared=false;sInput.event=event;sInput.sequence=++sInputSequence;
    sInput.millis=static_cast<uint32_t>(Ion::Timing::millis());
    if(sForeground) AppSystem::input(event,static_cast<uint32_t>(sInput.key),sInput.sequence);
  }
  // Input remains observable during a sleep, but does not shorten it. Heap
  // preparation also runs without entering user mode or retaining user pointers.
  if(sSuspended && (sHeapPreparing || Ion::Timing::millis()<sSleepUntil)) return sResult=1;
  sSleepUntil=0;
  // Experimental VM budget includes modeled display-service latency. This is
  // a bounded one-second callback, not a physical performance qualification.
  sDeadline=Timing::interruptTicks()+(sResumable?10:1000);
  sCalls=0; sLastPC=0; sLastService=0;
  sLastEvent=event;sDrawPixels=0;
  const uint64_t started=Timing::interruptTicks();
#if PRIME_G2_EMULATOR
  if(profiling()) profileIncrement(sProfile.entries);
#endif
  sActive=true;
  if(sSuspended) {
    sSuspended=false;sResumes++;
    sResult=prime_app_resume();
  } else sResult=prime_app_enter(sEntry,event,first,second);
  sActive=false;
  sElapsed=static_cast<uint32_t>(Timing::interruptTicks()-started);
#if PRIME_G2_EMULATOR
  if(profiling()) {
    if(sElapsed>sProfile.maxSliceMillis) sProfile.maxSliceMillis=sElapsed;
    if(sResult!=1) {
      profileIncrement(sProfile.faults);sProfile.failureResult=static_cast<uint32_t>(sResult);
      sProfile.faultPC=sLastPC;sProfile.faultEvent=event;
    }
  }
#endif
  if (sResult==1 && sSurfaceDirty) {
    Ion::Display::pushRect(KDRect(0,0,320,240),sSurface.pixels);
    sFrames++;sLastFrameMillis=static_cast<uint32_t>(Ion::Timing::millis());
#if PRIME_G2_EMULATOR
    if(profiling()) profileIncrement(sProfile.frames);
#endif
  }
  if (sResult!=1) {
#if PRIME_G2_EMULATOR
    profileFinish();
#endif
    sCrashResult=sResult;sCrashPC=sLastPC;sCrashEvent=event;sEntry=0;AppManagement::endFiles();resetExecution();System::mapNativeApp(nullptr,nullptr);
  }
  return sResult;
}
int invoke(uint32_t event,uint32_t first,uint32_t second) { return execute(event,first,second,true); }
void setForeground(bool active) {
  if(!active) {AppSystem::finish();AppChannel::finish();}
  sForeground=active;sChannelInputPaused=AppChannel::pairing();
  sInputStream.focus(active && !sChannelInputPaused);
}
bool resumable() { return sResumable; }
bool saveDataOnClose() { return sResult==1 && !sForcedExit && !sProgramStatus; }
bool resumePending() {
  return sForeground && !AppChannel::pairing() && sEntry && sResumable && sSuspended && !sActive && !sExited &&
    (sHeapPreparing || Ion::Timing::millis()>=sSleepUntil);
}
bool resumeForeground() {
  if(!resumePending()) return false;
  if(sHeapPreparing) {
    // One bounded block per low-priority event. Normal input/Home/services run
    // before each block; pages remain inaccessible until every byte is cleared.
    constexpr unsigned Block=64*1024;
    memset(sHeap+sHeapPrepared,0,Block);
    System::cleanDataCacheRange(sHeap+sHeapPrepared,Block);
    sHeapPrepared+=Block;
    if(sHeapPrepared==sizeof(sHeap)) {
      System::mapNativeAppHeap(sHeap);sHeapMapped=true;sHeapPreparing=false;
#if PRIME_G2_EMULATOR
      if(profiling()) sProfile.heapReservedPeak=HeapEnd-Heap;
#endif
      sHeapSetupMillis=static_cast<uint32_t>(Ion::Timing::millis()-sHeapStarted);
    }
    return false;
  }
  // The first container refresh owns a freshly loaded surface. Subsequent
  // waits and CPU preemptions must not repaint pixels that have not changed.
  sSurfaceDirty=false;
#if PRIME_G2_EMULATOR
  sForegroundWakes++;
#endif
  int result=execute(2,static_cast<uint32_t>(Ion::Timing::millis()),0,false);
  return result!=1 || sSurfaceDirty;
}
void noteUITimer() {
#if PRIME_G2_EMULATOR
  sUITimers++;
#endif
}
void unload() { if(!sActive) {
#if PRIME_G2_EMULATOR
  profileFinish();
#endif
  AppManagement::endFiles();sEntry=0;sResult=0;resetExecution();System::mapNativeApp(nullptr,nullptr);
} }
#if PRIME_G2_EMULATOR
bool armResourceProfile(const uint8_t hash[32]) {
  if(sActive || sEntry) return false;
  sProfile={};sProfile.version=1;sProfile.bytes=sizeof(sProfile);
  sProfile.flags=ProfileArmed;sProfile.stackCapacity=End-Stack;
  sHeapProfile={};sHeapProfile.version=1;sHeapProfile.bytes=sizeof(sHeapProfile);
  memcpy(sHeapProfile.packageHash,hash,32);sHeapProfileMapped=false;
  memcpy(sProfile.packageHash,hash,32);return true;
}
const ResourceProfile &resourceProfile() { profileStack();return sProfile; }
bool configureHeapResourceProfile(uint32_t address) {
  if(sActive || sEntry || sProfile.loads || !(sProfile.flags&ProfileArmed) || address%4 ||
      address<Data || address>DataEnd-sizeof(LefonyHeapProfile)) return false;
  sHeapProfile.address=address;sHeapProfile.flags=HeapArmed;return true;
}
const HeapResourceProfile &heapResourceProfile() { profileHeap();return sHeapProfile; }
#endif
int lastResult() {
  return sResult;
}
RuntimeReport runtimeReport() {
  uint32_t flags=(sEntry?1u:0u)|(sForeground?2u:0u)|(sPublicForeground?4u:0u)|(sExited?8u:0u);
  return {{0x5452464c,1,sizeof(RuntimeReport),flags,
    sPublicForeground?static_cast<uint32_t>(sHeapStarted):0u,
    static_cast<uint32_t>(Ion::Timing::millis()),sFirstPixelMillis,sFirstPixelElapsed,
    sPixelFrames,sFrames,sHeapSetupMillis,static_cast<uint32_t>(sCrashResult),
    static_cast<uint32_t>(sProgramStatus),0,0,0}};
}
uint32_t diagnostic(unsigned index) {
  const uint32_t values[]={sLastPC,sCalls,sLastService,sLastEvent,sElapsed,sDrawPixels,static_cast<uint32_t>(sResult),sKeyEvents,sTouchEvents,static_cast<uint32_t>(sCrashResult),sCrashPC,sCrashEvent,
    sPreemptions,sYields,sResumes,static_cast<uint32_t>(sExited)
#if PRIME_G2_EMULATOR
    ,sHeapSetupMillis,sHeapMapped?HeapEnd-Heap:0,PrimeG2::System::heapSize(),sForegroundWakes,sUITimers,static_cast<uint32_t>(sProgramStatus)
#endif
  };
  return index<sizeof(values)/sizeof(values[0])?values[index]:0;
}
const void *pixels() {
  return sEntry?sSurface.pixels:nullptr;
}
}}
extern "C" bool prime_g2_native_clipboard_shortcuts() {
  return sForeground && sEntry && !sExited && (sDeclaredFeatures&LEFONY_SYSTEM_CAPABILITY);
}
extern "C" int prime_app_fault(unsigned kind,const uint32_t *,uint32_t lr,uint32_t psr) {
  if(!user(psr)) return 0;
#if PRIME_G2_EMULATOR
  profileSample();
#endif
  // ARM exception LR points past the faulting instruction (data abort: +8;
  // undefined/prefetch abort: +4). App entry is always ARM, never Thumb.
  sLastPC=lr-(kind==4?8:4);
  return -10-static_cast<int>(kind);
}
extern "C" int prime_app_irq_expired(uint32_t psr,uint32_t pc) {
#if PRIME_G2_EMULATOR
  if(user(psr)) profileSample();
#endif
  if (user(psr)) sLastPC=pc;
  if(!user(psr) || !expired()) return 0;
  if(sResumable) { sPreemptions++;sSuspended=true;return 2; }
  return -2;
}
extern "C" int prime_app_svc(uint32_t *r,uint32_t psr) {
  if (!user(psr)) return -100;
#if PRIME_G2_EMULATOR
  profileSample();
  if(profiling()) profileIncrement(sProfile.services);
#endif
  sCalls++; sLastService=r[0]; sLastPC=r[13];
  if (expired()) {
    if(!sResumable) return -2;
    // No service has executed. Retry the SVC after resumption instead of
    // losing its result or duplicating side effects.
    r[13]-=(psr&(1u<<5))?2:4;sPreemptions++;sSuspended=true;return 2;
  }
#if PRIME_G2_EMULATOR
  if(r[0]==0x7fff0005u) {
    if(!sResumable) { r[0]=uint32_t(-4);return 0; }
    sProgramStatus=static_cast<int32_t>(r[1]);sExited=true;PrimeG2::AppManagement::endFiles();PrimeG2::AppSystem::finish();PrimeG2::AppChannel::finish();return 1;
  }
  if(r[0]==0x7fff0001u) {
    if(r[1] || sResumable || sLastEvent!=0) { r[0]=uint32_t(-4);return 0; }
    sResumable=true;sDeadline=PrimeG2::Timing::interruptTicks()+10;
    r[0]=0;return 0;
  }
  if(r[0]==0x7fff0002u) {
    if(r[1] || !sResumable) { r[0]=uint32_t(-4);return 0; }
    sYields++;sSuspended=true;r[0]=0;return 2;
  }
  if(r[0]==0x7fff0003u) {
    if(!sResumable || !readable(r[1],8) || !writable(r[1],24)) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[2];memcpy(args,reinterpret_cast<const void *>(r[1]),8);
    if(args[0]!=24 || args[1]!=1) { r[0]=uint32_t(-4);return 0; }
    if(!sHeapMapped) {
      // A fixed, bounded initialization; measure its privileged cost in R0.
      // New launches never see the previous app's heap contents.
      uint64_t started=Ion::Timing::millis();
      memset(sHeap,0,sizeof(sHeap));
      PrimeG2::System::cleanDataCacheRange(sHeap,sizeof(sHeap));
      PrimeG2::System::mapNativeAppHeap(sHeap);sHeapMapped=true;
      sHeapSetupMillis=static_cast<uint32_t>(Ion::Timing::millis()-started);
    }
    const uint32_t result[]={24,1,Heap,HeapEnd-Heap,PrimeG2::System::heapSize(),End-Stack};
    memcpy(reinterpret_cast<void *>(r[1]),result,sizeof(result));r[0]=0;return 0;
  }
  if(r[0]==0x7fff0004u) {
    if(!sResumable || !readable(r[1],40)) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[10];memcpy(args,reinterpret_cast<const void *>(r[1]),40);
    const uint32_t x=args[3],y=args[4],width=args[5],height=args[6],stride=args[7],pointer=args[8];
    if(args[0]!=40 || args[1]!=1 || args[2] || x>=320 || y>=240 || !width || !height ||
       width>320-x || height>240-y || stride<width || stride>320 || (pointer&1) ||
       args[9]!=((height-1)*stride+width)*2 || !readable(pointer,args[9])) { r[0]=uint32_t(-4);return 0; }
    for(unsigned row=0;row<height;row++)
      memcpy(sSurface.pixels+(y+row)*320+x,reinterpret_cast<const void *>(pointer+row*stride*2),width*2);
    sSurfaceDirty=true;
    sDrawPixels+=width*height;r[0]=0;return 0;
  }
#endif
  if(r[0]==LEFONY_FOREGROUND_SERVICE) {
    static_assert(sizeof(LefonyProgramRequest)==64,"program wire size");
    if(!(sDeclaredFeatures&LEFONY_FOREGROUND_CAPABILITY)) { r[0]=uint32_t(-3);return 0; }
    if(!readable(r[1],64) || !writable(r[1],64)) { r[0]=uint32_t(-4);return 0; }
    LefonyProgramRequest q;memcpy(&q,reinterpret_cast<const void *>(r[1]),sizeof(q));
    bool enter=q.operation==LEFONY_PROGRAM_ENTER;
    bool valid=q.size==sizeof(q) && q.schema==1 && !q.flags &&
      q.operation>=LEFONY_PROGRAM_ENTER && q.operation<=LEFONY_PROGRAM_INFO &&
      q.profile==(enter?static_cast<uint32_t>(LEFONY_FOREGROUND_PROFILE):0u) && !q.heap && !q.heapBytes &&
      !q.stackBytes && !q.sliceMillis && !q.frames && !q.lastFrameMillis;
    for(unsigned i=0;i<4;i++) valid=valid && !q.reserved[i];
    if(q.operation==LEFONY_PROGRAM_SLEEP) valid=valid && q.argument>=0 && q.argument<=60000;
    else if(q.operation!=LEFONY_PROGRAM_EXIT) valid=valid && !q.argument;
    if(!valid || (enter?(!sForeground || sResumable || sLastEvent!=0):!sPublicForeground)) {
      r[0]=uint32_t(-4);return 0;
    }
    if(enter) {
      sPublicForeground=true;sResumable=true;sSuspended=true;
      sHeapPreparing=true;sHeapPrepared=0;sHeapStarted=Ion::Timing::millis();
      r[0]=0;return 2;
    }
    if(q.operation==LEFONY_PROGRAM_EXIT) {
      sProgramStatus=q.argument;sExited=true;PrimeG2::AppManagement::endFiles();PrimeG2::AppSystem::finish();PrimeG2::AppChannel::finish();return 1;
    }
    if(q.operation==LEFONY_PROGRAM_INFO) {
      q.profile=LEFONY_FOREGROUND_PROFILE;q.heap=Heap;q.heapBytes=HeapEnd-Heap;
      q.stackBytes=End-Stack;q.sliceMillis=10;q.frames=sFrames;q.lastFrameMillis=sLastFrameMillis;
      memcpy(reinterpret_cast<void *>(r[1]),&q,sizeof(q));r[0]=0;return 0;
    }
    // Use the public millisecond clock, not the coarse IRQ accounting clock:
    // rounding the start down to an IRQ tick can wake a requested sleep early.
    sSleepUntil=q.operation==LEFONY_PROGRAM_SLEEP?Ion::Timing::millis()+q.argument:0;
    sYields++;sSuspended=true;r[0]=0;return 2;
  }
  if(r[0]==LEFONY_PIXELS_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_FOREGROUND_CAPABILITY)) { r[0]=uint32_t(-3);return 0; }
    if(!sPublicForeground || !readable(r[1],sizeof(LefonyPixelRequest))) { r[0]=uint32_t(-4);return 0; }
    LefonyPixelRequest q;memcpy(&q,reinterpret_cast<const void *>(r[1]),sizeof(q));
    if(q.size!=sizeof(q) || q.schema!=1 || q.flags || q.x>=320 || q.y>=240 || !q.width || !q.height ||
       q.width>320-q.x || q.height>240-q.y || q.stride<q.width || q.stride>320 || (q.buffer&1) ||
       q.bytes!=((q.height-1)*q.stride+q.width)*2 || !readable(q.buffer,q.bytes)) {
      r[0]=uint32_t(-4);return 0;
    }
    for(unsigned row=0;row<q.height;row++)
      memcpy(sSurface.pixels+(q.y+row)*320+q.x,reinterpret_cast<const void *>(q.buffer+row*q.stride*2),q.width*2);
    sSurfaceDirty=true;sDrawPixels+=q.width*q.height;
    if(!sPixelFrames) {
      uint64_t now=Ion::Timing::millis();sFirstPixelMillis=static_cast<uint32_t>(now);
      sFirstPixelElapsed=static_cast<uint32_t>(now-sHeapStarted);
    }
    if(sPixelFrames!=0xffffffffu) sPixelFrames++;
    sYields++;sSuspended=true;r[0]=0;return 2;
  }
  if (r[0]==0) { if(sResumable) { sExited=true;PrimeG2::AppManagement::endFiles();PrimeG2::AppSystem::finish();PrimeG2::AppChannel::finish(); }return 1; }
  if(r[0]==LEFONY_CHANNEL_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_CHANNEL_CAPABILITY)) {r[0]=uint32_t(-LEFONY_CHANNEL_DENIED);return 0;}
    if(!readable(r[1],sizeof(LefonyChannelRequest)) || !writable(r[1],sizeof(LefonyChannelRequest))) {
      r[0]=uint32_t(-LEFONY_CHANNEL_INVALID);return 0;
    }
    LefonyChannelRequest q;memcpy(&q,reinterpret_cast<const void *>(r[1]),sizeof(q));
    bool send=q.operation==LEFONY_CHANNEL_SEND;
    if(!PrimeG2::AppChannel::validRequest(q) ||
       (q.capacity && !(send?readable(q.buffer,q.capacity):writable(q.buffer,q.capacity))) ||
       (q.capacity && (q.buffer<=r[1]?r[1]-q.buffer<q.capacity:q.buffer-r[1]<sizeof(q)))) {
      r[0]=uint32_t(-LEFONY_CHANNEL_INVALID);return 0;
    }
    int result=PrimeG2::AppChannel::request(q,reinterpret_cast<void *>(q.buffer),sForeground && PrimeG2::AppManagement::hasOpen());
    if(!result) memcpy(reinterpret_cast<void *>(r[1]),&q,sizeof(q));
    r[0]=result;return 0;
  }
  if(r[0]==LEFONY_SYSTEM_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_SYSTEM_CAPABILITY)) {r[0]=uint32_t(-LEFONY_SYSTEM_DENIED);return 0;}
    if(!readable(r[1],sizeof(LefonySystemRequest)) || !writable(r[1],sizeof(LefonySystemRequest))) {
      r[0]=uint32_t(-LEFONY_SYSTEM_INVALID);return 0;
    }
    LefonySystemRequest q;memcpy(&q,reinterpret_cast<const void *>(r[1]),sizeof(q));
    bool write=q.operation==LEFONY_SYSTEM_CLIPBOARD_WRITE;
    if(!PrimeG2::AppSystem::validRequest(q) ||
       (q.capacity && !(write?readable(q.buffer,q.capacity):writable(q.buffer,q.capacity))) ||
       (q.capacity && (q.buffer<=r[1]?r[1]-q.buffer<q.capacity:q.buffer-r[1]<sizeof(q)))) {
      r[0]=uint32_t(-LEFONY_SYSTEM_INVALID);return 0;
    }
    int result=PrimeG2::AppSystem::request(q,reinterpret_cast<void *>(q.buffer),sForeground);
    if(!result) memcpy(reinterpret_cast<void *>(r[1]),&q,sizeof(q));
    r[0]=result;return 0;
  }
  if(r[0]==LEFONY_DATA_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_DATA_CAPABILITY)) {r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0;}
    if(!readable(r[1],sizeof(LefonyDataRequest)) || !writable(r[1],sizeof(LefonyDataRequest))) {
      r[0]=uint32_t(-LEFONY_FILE_INVALID);return 0;
    }
    LefonyDataRequest request;memcpy(&request,reinterpret_cast<const void *>(r[1]),sizeof(request));
    int result=PrimeG2::AppManagement::data(request);
    memcpy(reinterpret_cast<void *>(r[1]),&request,sizeof(request));r[0]=result;return 0;
  }
  if(r[0]==10) {
    if(!(sDeclaredFeatures&8)) { r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0; }
    if(!readable(r[1],64) || !writable(r[1],64)) { r[0]=uint32_t(-LEFONY_FILE_INVALID);return 0; }
    LefonyFileRequest request;memcpy(&request,reinterpret_cast<const void *>(r[1]),sizeof(request));
    if(request.operation==LEFONY_FILE_SYNC && !(sDeclaredFeatures&LEFONY_FILE_SYNC_CAPABILITY)) {
      r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0;
    }
    if(request.operation==LEFONY_FILE_ABORT && !(sDeclaredFeatures&LEFONY_FILE_ABORT_CAPABILITY)) {
      r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0;
    }
    if(request.operation==LEFONY_FILE_QUOTA && !(sDeclaredFeatures&LEFONY_FILE_QUOTA_CAPABILITY)) {
      r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0;
    }
    if((request.operation==LEFONY_FILE_LIST || request.operation==LEFONY_FILE_SPACE) &&
       !(sDeclaredFeatures&LEFONY_FILE_CATALOG_CAPABILITY)) {
      r[0]=uint32_t(-LEFONY_FILE_DENIED);return 0;
    }
    const bool poll=request.operation==LEFONY_FILE_POLL;
    if(request.pathBytes>95 || request.destinationBytes>95 || request.length>2048 || request.capacity>2048 ||
       (request.pathBytes && !readable(request.path,request.pathBytes)) ||
       (request.destinationBytes && !readable(request.destination,request.destinationBytes)) ||
       (request.operation==LEFONY_FILE_WRITE && request.length && !readable(request.buffer,request.length)) ||
       (poll && request.capacity && !writable(request.buffer,request.capacity))) {
      r[0]=uint32_t(-LEFONY_FILE_INVALID);return 0;
    }
    int result=PrimeG2::AppManagement::files(request,reinterpret_cast<const char *>(request.path),
      reinterpret_cast<const char *>(request.destination),reinterpret_cast<const void *>(request.buffer),
      poll?reinterpret_cast<void *>(request.buffer):nullptr);
    memcpy(reinterpret_cast<void *>(r[1]),&request,sizeof(request));r[0]=result;return 0;
  }
  if (r[0]==3) { r[0]=static_cast<uint32_t>(Ion::Timing::millis()); return 0; }
  if (r[0]==6) {
    if(!readable(r[1],12) || !writable(r[1],48)) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[3];memcpy(args,reinterpret_cast<const void *>(r[1]),12);
    if(args[0]!=48 || args[1]!=1 || args[2]) { r[0]=uint32_t(-4);return 0; }
    const uint32_t result[]={48,1,0,PrimeG2::NativeAppManifest::Features,1,320,240,65536,4096,64,76800,1000};
    memcpy(reinterpret_cast<void *>(r[1]),result,sizeof(result));r[0]=0;return 0;
  }
  if(r[0]==8) {
    if(!readable(r[1],12) || !writable(r[1],sizeof(sInput))) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[3];memcpy(args,reinterpret_cast<const void *>(r[1]),12);
    if(args[0]!=sizeof(sInput) || args[1]!=1 || args[2]) { r[0]=uint32_t(-4);return 0; }
    memcpy(reinterpret_cast<void *>(r[1]),&sInput,sizeof(sInput));r[0]=0;return 0;
  }
  if(r[0]==LEFONY_INPUT_STREAM_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_INPUT_STREAM_CAPABILITY)) { r[0]=uint32_t(-3);return 0; }
    if(!readable(r[1],12) || !writable(r[1],sizeof(LefonyInputStream))) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[3];memcpy(args,reinterpret_cast<const void *>(r[1]),sizeof(args));
    if(args[0]!=sizeof(LefonyInputStream) || args[1]!=1 || args[2]) { r[0]=uint32_t(-4);return 0; }
    LefonyInputStream stream;sInputStream.read(stream,static_cast<uint32_t>(Ion::Timing::millis()));
    memcpy(reinterpret_cast<void *>(r[1]),&stream,sizeof(stream));r[0]=0;return 0;
  }
  if(r[0]==9) {
    if(!readable(r[1],16)) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[4];memcpy(args,reinterpret_cast<const void *>(r[1]),16);
    if(args[0]!=16 || args[1]!=1 || args[2] || args[3]>8) { r[0]=uint32_t(-4);return 0; }
    sNavigationDepth=args[3];
    sInputStream.backAllowed(sNavigationDepth!=0,static_cast<uint32_t>(Ion::Timing::millis()));
    r[0]=0;return 0;
  }
  if(r[0]==7) {
    if(!readable(r[1],20)) { r[0]=uint32_t(-4);return 0; }
    uint32_t args[5];memcpy(args,reinterpret_cast<const void *>(r[1]),20);
    if(args[0]!=20 || args[1]!=1 || args[2] || !args[4] || args[4]>64 || !readable(args[3],args[4]*20)) { r[0]=uint32_t(-4);return 0; }
    uint32_t rects[64][5],pixels=0;memcpy(rects,reinterpret_cast<const void *>(args[3]),args[4]*20);
    for(unsigned i=0;i<args[4];i++) {
      if(!rectangle(rects[i])) { r[0]=uint32_t(-4);return 0; }
      uint32_t n=rects[i][2]*rects[i][3];
      if(n>76800-pixels) { r[0]=uint32_t(-4);return 0; }pixels+=n;
    }
    sSurface.setOrigin(KDPointZero);sSurface.setClippingRect(KDRect(0,0,320,240));
    for(unsigned i=0;i<args[4];i++) {
      const uint32_t *a=rects[i];sSurface.fillRect(KDRect(a[0],a[1],a[2],a[3]),KDColor::RGB16(a[4]));
    }
    sDrawPixels+=pixels;r[0]=0;return 0;
  }
  if (r[0]==4 || r[0]==5) {
    if (!readable(r[1],12)) { r[0]=uint32_t(-4); return 0; }
    uint32_t args[3]; memcpy(args,reinterpret_cast<const void *>(r[1]),12);
    const uint32_t pointer=args[1],length=args[2];
    if (length>4096 || !readable(pointer,length) || (r[0]==4 && !writable(pointer,length))) { r[0]=uint32_t(-4); return 0; }
    r[0]=r[0]==4?PrimeG2::AppManagement::readData(args[0],reinterpret_cast<void *>(pointer),length):
      PrimeG2::AppManagement::writeData(args[0],reinterpret_cast<const void *>(pointer),length);
    return 0;
  }
  if(r[0]==LEFONY_TEXT_SERVICE) {
    if(!(sDeclaredFeatures&LEFONY_TEXT_CAPABILITY)) {r[0]=uint32_t(-4);return 0;}
    if(!readable(r[1],sizeof(LefonyTextRequest)) || !writable(r[1],sizeof(LefonyTextRequest))) {r[0]=uint32_t(-4);return 0;}
    LefonyTextRequest request;memcpy(&request,reinterpret_cast<const void *>(r[1]),sizeof(request));
    if(!PrimeG2::AppText::validRequest(request) || (request.textBytes && !readable(request.text,request.textBytes))) {r[0]=uint32_t(-4);return 0;}
    char text[LEFONY_TEXT_MAXIMUM+1];
    if(request.textBytes) memcpy(text,reinterpret_cast<const void *>(request.text),request.textBytes);
    text[request.textBytes]=0;
    if(!PrimeG2::AppText::validText(text,request.textBytes)) {r[0]=uint32_t(-4);return 0;}
    if(!KDFont::CanBeWrittenWithGlyphs(text)) {r[0]=uint32_t(-5);return 0;}
    const KDFont *fonts[]={KDFont::SmallFont,KDFont::LargeFont,KDFont::ItalicSmallFont,KDFont::ItalicLargeFont};
    const KDFont *font=fonts[request.font];KDSize size=font->stringSize(text),glyph=font->glyphSize();
    request.width=size.width();request.height=size.height();request.glyphWidth=glyph.width();request.glyphHeight=glyph.height();
    if(request.operation==LEFONY_TEXT_DRAW) {
      request.flags=request.x<request.clipX || request.y<request.clipY ||
        int64_t(request.x)+request.width>request.clipX+request.clipWidth ||
        int64_t(request.y)+request.height>request.clipY+request.clipHeight?LEFONY_TEXT_CLIPPED:0;
      if(request.clipWidth && request.clipHeight && request.textBytes) {
        sSurface.setOrigin(KDPointZero);sSurface.setClippingRect(KDRect(request.clipX,request.clipY,request.clipWidth,request.clipHeight));
        sSurface.drawString(text,KDPoint(request.x,request.y),font,KDColor::RGB16(request.foreground),KDColor::RGB16(request.background));
        sSurface.setClippingRect(KDRect(0,0,320,240));
      }
    }
    memcpy(reinterpret_cast<void *>(r[1]),&request,sizeof(request));r[0]=0;return 0;
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
    sDrawPixels+=w*h;
  } else {
    if (x<0 || y<0 || x>=320 || y>=240 || args[2]>65535 || args[3]>65535 ||
        args[5]>128 || !readable(args[4],args[5])) { r[0]=static_cast<uint32_t>(-4); return 0; }
    char text[129]; memcpy(text,reinterpret_cast<const void *>(args[4]),args[5]); text[args[5]]=0;
    for (unsigned i=0;i<args[5];i++) if (text[i]<32 || text[i]>126) { r[0]=static_cast<uint32_t>(-4); return 0; }
    context->drawString(text,KDPoint(x,y),KDFont::SmallFont,KDColor::RGB16(args[2]),KDColor::RGB16(args[3]));
  }
  r[0]=0; return 0;
}

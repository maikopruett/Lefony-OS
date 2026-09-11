// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_storage.h"
#include "native_app_digest.h"
#include <string.h>
namespace PrimeG2 { namespace AppStorage {
namespace {
uint32_t get(const uint8_t *p) { return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24); }
void put(uint8_t *p,uint32_t v) { for(unsigned i=0;i<4;i++) p[i]=v>>(i*8); }
uint32_t first(unsigned slot,unsigned bank) { return FirstBlock+16+(slot*2+bank)*BankBlocks; }
void seal(uint8_t *p) { NativeAppHash::sha256(p,PageBytes-32,p+PageBytes-32); }
bool sealed(const uint8_t *p) { uint8_t hash[32]; NativeAppHash::sha256(p,PageBytes-32,hash); return !memcmp(hash,p+PageBytes-32,32); }
uint32_t map(const uint8_t *p,unsigned i) { return get(p+128+i*4); }
}
Volume::Volume(Backend b):m_backend(b),m_state(State::Unprovisioned),m_entries{},m_identity{},m_header{},m_scratch{},m_package(nullptr),m_data(nullptr),m_cursor(0),m_pages(0),m_packageBytes(0),m_dataBytes(0),m_slot(0) {
  for(auto &entry:m_entries) entry.bank=-1;
}
bool Volume::validMarker(const uint8_t *p) const {
  return !memcmp(p,"LFAVOL1\0",8) && get(p+8)==1 && get(p+12)==FirstBlock && get(p+16)==BlockCount && get(p+20)==PageBytes && get(p+24)==PagesPerBlock && sealed(p);
}
bool Volume::readHeader(unsigned slot,unsigned bank,uint8_t *h) {
  const uint32_t start=first(slot,bank);
  uint32_t block=start;
  while(block<start+BankBlocks && !m_backend.usable(m_backend.context,block)) block++;
  if(block==start+BankBlocks || !m_backend.read(m_backend.context,block*PagesPerBlock,h)) return false;
  if(memcmp(h,"LFASLOT1",8) || get(h+8)!=1 || get(h+12)!=slot || get(h+16)!=bank || !get(h+20) ||
      memcmp(h+24,m_identity,32) || get(h+56)>MaximumPackage || get(h+60)>MaximumData ||
      (!get(h+56) && get(h+60)) || !sealed(h)) return false;
  uint32_t count=get(h+64),pages=(get(h+56)+get(h+60)+PageBytes-1)/PageBytes;
  if(count<2 || count>BankBlocks || pages>(count-1)*PagesPerBlock || map(h,0)!=block) return false;
  for(unsigned i=0;i<count;i++) {
    uint32_t b=map(h,i);
    if(b<start || b>=start+BankBlocks || (i && b<=map(h,i-1))) return false;
  }
  uint8_t commit[PageBytes];
  return m_backend.read(m_backend.context,block*PagesPerBlock+1,commit) &&
    !memcmp(commit,"LFACMT1\0",8) && !memcmp(commit+8,h+PageBytes-32,32) && sealed(commit);
}
uint32_t Volume::payloadPage(const uint8_t *h,uint32_t i) const { return map(h,1+i/PagesPerBlock)*PagesPerBlock+i%PagesPerBlock; }
bool Volume::checkPayload(const uint8_t *h,uint8_t *package,uint8_t *data) {
  uint32_t packageBytes=get(h+56),dataBytes=get(h+60),total=packageBytes+dataBytes;
  NativeAppHash::SHA256 hash; NativeAppHash::shaInit(&hash);
  uint8_t page[PageBytes],digest[32];
  for(uint32_t offset=0;offset<total;offset+=PageBytes) {
    if(!m_backend.read(m_backend.context,payloadPage(h,offset/PageBytes),page)) return false;
    uint32_t bytes=total-offset; if(bytes>PageBytes) bytes=PageBytes;
    NativeAppHash::shaUpdate(&hash,page,bytes);
    uint32_t app=offset<packageBytes?packageBytes-offset:0; if(app>bytes) app=bytes;
    if(package && app) memcpy(package+offset,page,app);
    if(data && bytes>app) memcpy(data+(offset+app-packageBytes),page+app,bytes-app);
  }
  NativeAppHash::shaFinal(&hash,digest);
  return !memcmp(digest,h+80,32);
}
bool Volume::mount() {
  if(m_state==State::Erasing || m_state==State::Writing || m_state==State::Verifying || m_state==State::Committing) return false;
  m_state=State::Unprovisioned;
  bool found=false;
  for(unsigned i=0;i<2;i++) {
    if(!m_backend.usable(m_backend.context,FirstBlock+i) || !m_backend.read(m_backend.context,(FirstBlock+i)*PagesPerBlock,m_scratch) || !validMarker(m_scratch)) continue;
    if(found && memcmp(m_identity,m_scratch+32,32)) { m_state=State::Failed; return false; }
    memcpy(m_identity,m_scratch+32,32); found=true;
  }
  if(!found) return false;
  for(unsigned slot=0;slot<Slots;slot++) {
    m_entries[slot]={0,0,0,-1};
    for(unsigned bank=0;bank<2;bank++) {
      if(!readHeader(slot,bank,m_header) || !checkPayload(m_header)) continue;
      const uint32_t generation=get(m_header+20);
      if(generation==m_entries[slot].generation) { m_state=State::Failed; return false; }
      if(generation>m_entries[slot].generation) m_entries[slot]={generation,get(m_header+56),get(m_header+60),static_cast<int>(bank)};
    }
  }
  m_state=State::Ready; return true;
}
bool Volume::writeChecked(uint32_t page,const uint8_t *data) {
  uint8_t verify[PageBytes];
  return m_backend.program(m_backend.context,page,data) && m_backend.read(m_backend.context,page,verify) && !memcmp(data,verify,PageBytes);
}
bool Volume::provision(const uint8_t backup[32]) {
  if(m_state!=State::Unprovisioned || !backup) return false;
  // Both reserved blocks must be usable. We never create an ad-hoc layout.
  if(!m_backend.usable(m_backend.context,FirstBlock) || !m_backend.usable(m_backend.context,FirstBlock+1)) return false;
  memset(m_header,0xff,PageBytes); memcpy(m_header,"LFAVOL1\0",8);
  put(m_header+8,1); put(m_header+12,FirstBlock); put(m_header+16,BlockCount); put(m_header+20,PageBytes); put(m_header+24,PagesPerBlock);
  memcpy(m_header+32,backup,32); seal(m_header);
  for(unsigned i=0;i<2;i++) {
    if(!m_backend.erase(m_backend.context,FirstBlock+i) || !writeChecked((FirstBlock+i)*PagesPerBlock,m_header)) { m_state=State::Failed; return false; }
  }
  return mount();
}
bool Volume::reserve() {
  if(m_state!=State::Unprovisioned) return false;
  NativeAppHash::SHA256 hash;NativeAppHash::shaInit(&hash);
  const char domain[]="Lefony app volume profile 1";
  NativeAppHash::shaUpdate(&hash,reinterpret_cast<const uint8_t *>(domain),sizeof(domain));
  // Only erased blocks or stock UBI erase-counter pages can be retired by
  // this path. Scan every usable block so missing/damaged volume markers can
  // never turn an existing app bank into a fresh, apparently empty volume.
  for(uint32_t block=FirstBlock;block<FirstBlock+BlockCount;block++) {
    if(!m_backend.usable(m_backend.context,block)) continue;
    if(!m_backend.read(m_backend.context,block*PagesPerBlock,m_scratch)) { m_state=State::Failed;return false; }
    NativeAppHash::shaUpdate(&hash,m_scratch,PageBytes);
    bool erased=true;
    for(unsigned i=0;i<PageBytes;i++) erased&=m_scratch[i]==0xff;
    if(!erased && memcmp(m_scratch,"UBI#",4)) { m_state=State::Failed;return false; }
  }
  // The on-media identity field is unchanged. It need not be a backup hash;
  // legacy receipt-based provisioning remains available to the SDK host tool.
  uint8_t identity[32];NativeAppHash::shaFinal(&hash,identity);
  return provision(identity);
}
uint32_t Volume::capacity(unsigned slot) const {
  if(slot>=Slots) return 0;
  uint32_t capacity=MaximumPackage;
  // Budget for an atomic update in either bank and the full private-data area.
  for(unsigned bank=0;bank<2;bank++) {
    unsigned usable=0;
    for(uint32_t b=first(slot,bank);b<first(slot,bank)+BankBlocks;b++) usable+=m_backend.usable(m_backend.context,b)?1:0;
    uint32_t bytes=usable>1?(usable-1)*PagesPerBlock*PageBytes:0;
    bytes=bytes>MaximumData?bytes-MaximumData:0;
    if(bytes<capacity) capacity=bytes;
  }
  return capacity;
}
bool Volume::read(unsigned slot,uint8_t *package,size_t capacity,uint8_t *data,size_t dataCapacity) {
  if(slot>=Slots || (m_state!=State::Ready && m_state!=State::Complete) || m_entries[slot].bank<0 || !m_entries[slot].packageBytes ||
      !package || capacity<m_entries[slot].packageBytes || (m_entries[slot].dataBytes && (!data || dataCapacity<m_entries[slot].dataBytes))) return false;
  return readHeader(slot,m_entries[slot].bank,m_header) && checkPayload(m_header,package,data);
}
bool Volume::begin(unsigned slot,const uint8_t *package,uint32_t packageBytes,const uint8_t *data,uint32_t dataBytes) {
  if((m_state!=State::Ready && m_state!=State::Complete) || slot>=Slots || packageBytes>MaximumPackage || dataBytes>MaximumData ||
      (packageBytes && !package) || (dataBytes && !data) || (!packageBytes && dataBytes) || m_entries[slot].generation==0xffffffffu) return false;
  unsigned bank=m_entries[slot].bank==0?1:0;
  memset(m_header,0xff,PageBytes); memcpy(m_header,"LFASLOT1",8);
  put(m_header+8,1); put(m_header+12,slot); put(m_header+16,bank); put(m_header+20,m_entries[slot].generation+1);
  memcpy(m_header+24,m_identity,32); put(m_header+56,packageBytes); put(m_header+60,dataBytes);
  unsigned count=0;
  for(uint32_t b=first(slot,bank);b<first(slot,bank)+BankBlocks;b++) if(m_backend.usable(m_backend.context,b)) put(m_header+128+count++*4,b);
  m_pages=(packageBytes+dataBytes+PageBytes-1)/PageBytes;
  if(count<2 || m_pages>(count-1)*PagesPerBlock) return false;
  count=1+(m_pages+PagesPerBlock-1)/PagesPerBlock; if(count<2) count=2;
  put(m_header+64,count);
  NativeAppHash::SHA256 hash; NativeAppHash::shaInit(&hash);
  if(packageBytes) NativeAppHash::shaUpdate(&hash,package,packageBytes);
  if(dataBytes) NativeAppHash::shaUpdate(&hash,data,dataBytes);
  NativeAppHash::shaFinal(&hash,m_header+80); seal(m_header);
  m_slot=slot; m_package=package; m_data=data; m_packageBytes=packageBytes; m_dataBytes=dataBytes; m_cursor=0; m_state=State::Erasing; return true;
}
void Volume::makePage(uint32_t i,uint8_t *out) const {
  memset(out,0xff,PageBytes);
  uint32_t offset=i*PageBytes,bytes=m_packageBytes+m_dataBytes-offset;
  if(bytes>PageBytes) bytes=PageBytes;
  uint32_t app=offset<m_packageBytes?m_packageBytes-offset:0; if(app>bytes) app=bytes;
  if(app) memcpy(out,m_package+offset,app);
  if(bytes>app) memcpy(out+app,m_data+offset+app-m_packageBytes,bytes-app);
}
void Volume::step() {
  bool ok=true;
  if(m_state==State::Erasing) {
    ok=m_backend.erase(m_backend.context,map(m_header,m_cursor));
    if(++m_cursor==get(m_header+64)) { m_cursor=0; m_state=State::Writing; }
  } else if(m_state==State::Writing) {
    if(m_cursor==0) ok=m_backend.program(m_backend.context,map(m_header,0)*PagesPerBlock,m_header);
    else { makePage(m_cursor-1,m_scratch); ok=m_backend.program(m_backend.context,payloadPage(m_header,m_cursor-1),m_scratch); }
    if(++m_cursor==m_pages+1) { m_cursor=0; m_state=State::Verifying; }
  } else if(m_state==State::Verifying) {
    uint8_t expected[PageBytes];
    if(!m_cursor) memcpy(expected,m_header,PageBytes); else makePage(m_cursor-1,expected);
    uint32_t page=m_cursor?payloadPage(m_header,m_cursor-1):map(m_header,0)*PagesPerBlock;
    ok=m_backend.read(m_backend.context,page,m_scratch) && !memcmp(expected,m_scratch,PageBytes);
    if(++m_cursor==m_pages+1) { m_cursor=0; m_state=State::Committing; }
  } else if(m_state==State::Committing) {
    if(!m_cursor) {
      memset(m_scratch,0xff,PageBytes); memcpy(m_scratch,"LFACMT1\0",8); memcpy(m_scratch+8,m_header+PageBytes-32,32); seal(m_scratch);
      ok=m_backend.program(m_backend.context,map(m_header,0)*PagesPerBlock+1,m_scratch); m_cursor=1;
    } else {
      ok=m_backend.read(m_backend.context,map(m_header,0)*PagesPerBlock+1,m_scratch) && sealed(m_scratch) && !memcmp(m_scratch,"LFACMT1\0",8) && !memcmp(m_scratch+8,m_header+PageBytes-32,32);
      if(ok) { m_entries[m_slot]={get(m_header+20),m_packageBytes,m_dataBytes,static_cast<int>(get(m_header+16))}; m_state=State::Complete; }
    }
  }
  if(!ok) m_state=State::Failed;
}
void Volume::cancel() {
  if(m_state==State::Erasing || m_state==State::Writing || m_state==State::Verifying) { m_package=nullptr; m_data=nullptr; m_state=State::Ready; }
  // Commit outcome cannot be cancelled or guessed. Finish/read status instead.
}
}}

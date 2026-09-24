// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_SYSTEM_H
#define LEFONY_APP_SYSTEM_H
#include "lefony/system_wire.h"
namespace PrimeG2 { namespace AppSystem {
inline bool validRequest(const LefonySystemRequest &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || r.flags || r.transferred ||
     r.reserved[0] || r.reserved[1] || r.reserved[2]) return false;
  switch(r.operation) {
    case LEFONY_SYSTEM_INFO:return !r.value && !r.sequence && r.buffer && r.capacity==sizeof(LefonySystemInfo);
    case LEFONY_SYSTEM_BRIGHTNESS:return !r.sequence && !r.buffer && !r.capacity;
    case LEFONY_SYSTEM_RESTORE_BRIGHTNESS:return !r.value && !r.sequence && !r.buffer && !r.capacity;
    case LEFONY_SYSTEM_CLIPBOARD_READ:return !r.value && r.sequence && r.buffer && r.capacity && r.capacity<=LEFONY_CLIPBOARD_MAXIMUM+1;
    case LEFONY_SYSTEM_CLIPBOARD_WRITE:return !r.value && r.sequence && r.capacity<=LEFONY_CLIPBOARD_MAXIMUM && (!r.capacity || r.buffer);
    default:return false;
  }
}
inline bool validClipboard(const char *text,uint32_t length) {
  if(length>LEFONY_CLIPBOARD_MAXIMUM || (length && !text)) return false;
  for(uint32_t i=0;i<length;) {
    uint32_t c=static_cast<uint8_t>(text[i++]),extra=0,minimum=0;
    if(c<128) {if((c<32 && c!=9 && c!=10) || c==127) return false;continue;}
    if(c>=0xc2 && c<=0xdf) {c&=31;extra=1;minimum=0x80;}
    else if(c>=0xe0 && c<=0xef) {c&=15;extra=2;minimum=0x800;}
    else if(c>=0xf0 && c<=0xf4) {c&=7;extra=3;minimum=0x10000;}
    else return false;
    if(extra>length-i) return false;
    while(extra--) {uint32_t b=static_cast<uint8_t>(text[i++]);if((b&0xc0)!=0x80) return false;c=(c<<6)|(b&63);}
    if(c<minimum || c>0x10ffff || (c>=0xd800 && c<=0xdfff) || (c>=0x80 && c<=0x9f)) return false;
  }
  return true;
}
class Session {
public:
  void revoke() {m_sequence=0;m_action=0;m_at=0;}
  void input(uint32_t event,uint32_t action,uint32_t sequence,uint64_t now) {
    if(event!=1 && event!=3) return;
    revoke();
    if(event==1 && action>=LEFONY_CLIPBOARD_COPY && action<=LEFONY_CLIPBOARD_CUT && sequence) {
      m_action=action;m_sequence=sequence;m_at=now;
    }
  }
  bool live(uint64_t now) const {return m_sequence && now>=m_at && now-m_at<LEFONY_CLIPBOARD_GESTURE_MILLIS;}
  uint32_t sequence(uint64_t now) const {return live(now)?m_sequence:0;}
  uint32_t action(uint64_t now) const {return live(now)?m_action:0;}
  bool permits(bool write,uint32_t sequence,uint64_t now) const {
    return live(now) && sequence==m_sequence && (write?m_action!=LEFONY_CLIPBOARD_PASTE:m_action==LEFONY_CLIPBOARD_PASTE);
  }
  void brightness(uint32_t current,uint32_t next) {
    if(!m_ownsBrightness || current!=m_lastBrightness) m_originalBrightness=current;
    m_lastBrightness=next;m_ownsBrightness=true;
  }
  uint32_t restoreBrightness(uint32_t current) {
    uint32_t next=m_ownsBrightness && current==m_lastBrightness?m_originalBrightness:current;
    m_ownsBrightness=false;return next;
  }
private:
  uint32_t m_sequence=0,m_action=0,m_originalBrightness=0,m_lastBrightness=0;
  uint64_t m_at=0;
  bool m_ownsBrightness=false;
};
void finish();
void input(uint32_t event,uint32_t key,uint32_t sequence);
int request(LefonySystemRequest &request,void *buffer,bool foreground);
}}
// OS UI services are implemented by the native-app frontend, never by user
// code. No OS object or shared-clipboard pointer crosses the app boundary.
extern "C" void prime_app_system_preferences(LefonySystemInfo *info);
extern "C" uint32_t prime_app_system_brightness();
extern "C" void prime_app_system_set_brightness(uint32_t value);
extern "C" int prime_app_system_clipboard_read(char *buffer,uint32_t capacity);
extern "C" void prime_app_system_clipboard_write(const char *buffer,uint32_t length);
#endif

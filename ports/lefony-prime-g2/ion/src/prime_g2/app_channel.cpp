// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#include "app_channel.h"
#include "app_system.h"
#include "development_update.h"
#include <ion/timing.h>
namespace PrimeG2 { namespace AppChannel {
namespace {Session sSession;}
void owner(const char *id,const char *name,const uint8_t *hash,const uint8_t *signer) {sSession.owner(id,name,hash,signer);}
void clear() {sSession.clear();}
void finish(uint32_t error) {sSession.finish(error);}
void poll() {
  if(DevelopmentUpdate::busy()) sSession.finish();
  sSession.poll(Ion::Timing::millis());
}
bool pairing() {return sSession.pairing();}
LefonyChannelInfo info() {return sSession.info();}
void consent(bool allow) {sSession.consent(allow,Ion::Timing::millis());}
int request(LefonyChannelRequest &r,void *buffer,bool foregroundInstalled) {
  if(!foregroundInstalled || !sSession.info().appId[0]) return -LEFONY_CHANNEL_DENIED;
  return sSession.request(r,buffer,Ion::Timing::millis());
}
bool usbRequest(uint8_t command,uint32_t argument,const uint8_t *bytes,unsigned size) {
  if(argument || !bytes) return false;
  uint64_t now=Ion::Timing::millis();
  if(command==0x79 && size==sizeof(LefonyChannelAttach)) {
    LefonyChannelAttach a;memcpy(&a,bytes,sizeof(a));bool was=sSession.pairing();
    bool result=sSession.attach(a,now);
    if(result && !was && sSession.pairing()) AppSystem::finish();
    return result;
  }
  if(command==0x7a && size>=64 && size<=sizeof(LefonyChannelFrame)) {
    LefonyChannelFrame f={};memcpy(&f,bytes,size);return sSession.receive(f,size,now);
  }
  if(command>=0x7c && command<=0x7e && size==sizeof(LefonyChannelControl)) {
    LefonyChannelControl c;memcpy(&c,bytes,size);return sSession.control(command,c,now);
  }
  return false;
}
bool usbResponse(uint8_t command,uint32_t argument,uint8_t *buffer,unsigned capacity,unsigned *size) {
  sSession.poll(Ion::Timing::millis());
  if(command==0x78 && !argument && capacity>=sizeof(LefonyChannelInfo)) {
    auto info=sSession.info();memcpy(buffer,&info,sizeof(info));*size=sizeof(info);return true;
  }
  return command==0x7b && sSession.read(argument,buffer,capacity,size,Ion::Timing::millis());
}
}}

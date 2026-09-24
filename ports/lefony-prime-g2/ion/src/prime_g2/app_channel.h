// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_APP_CHANNEL_H
#define LEFONY_APP_CHANNEL_H
#include "lefony/channel_wire.h"
#include <string.h>
namespace PrimeG2 { namespace AppChannel {
inline bool validRequest(const LefonyChannelRequest &r) {
  if(r.size!=sizeof(r) || r.schema!=1 || r.flags || r.sequence || r.transferred || r.state || r.error ||
     r.reserved[0] || r.reserved[1] || r.reserved[2]) return false;
  switch(r.operation) {
    case LEFONY_CHANNEL_OPEN:return !r.session && !r.buffer && !r.capacity && !r.length && !r.kind;
    case LEFONY_CHANNEL_INFO:return !r.session && r.buffer && r.capacity==sizeof(LefonyChannelInfo) && !r.length && !r.kind;
    case LEFONY_CHANNEL_SEND:return r.session && r.kind && r.kind<=65535 && r.length<=LEFONY_CHANNEL_PAYLOAD &&
      r.capacity==r.length && (!r.length || r.buffer);
    case LEFONY_CHANNEL_RECEIVE:return r.session && !r.kind && !r.length && r.capacity<=LEFONY_CHANNEL_PAYLOAD && (!r.capacity || r.buffer);
    case LEFONY_CHANNEL_CLOSE:return r.session && !r.buffer && !r.capacity && !r.length && !r.kind;
    default:return false;
  }
}
class Session {
public:
  Session() {clear();}
  void clear() {
    m_info={};m_info.size=sizeof(m_info);m_info.schema=1;
    m_info.maximumPayload=LEFONY_CHANNEL_PAYLOAD;m_info.queueCapacity=LEFONY_CHANNEL_QUEUE;
    m_tx.clear();m_rx.clear();m_lastReceive={};m_lastAck=0;m_since=m_hostAt=0;
  }
  void owner(const char *id,const char *name,const uint8_t *hash,const uint8_t *signer) {
    clear();memcpy(m_info.appId,id,49);memcpy(m_info.appName,name,81);
    memcpy(m_info.packageHash,hash,32);memcpy(m_info.signer,signer,32);
  }
  bool pairing() const {return m_info.state==LEFONY_CHANNEL_WAIT_USER;}
  bool active() const {return m_info.state>=LEFONY_CHANNEL_WAIT_HOST && m_info.state<=LEFONY_CHANNEL_CONNECTED;}
  LefonyChannelInfo info() const {
    auto result=m_info;result.sendQueued=m_tx.count;result.receiveQueued=m_rx.count;
    result.nextReceiveBytes=m_rx.count?m_rx.front().length:0;return result;
  }
  void finish(uint32_t error=LEFONY_CHANNEL_DISCONNECTED) {
    if(!active()) return;
    m_info.state=LEFONY_CHANNEL_ENDED;m_info.error=error;m_tx.clear();m_rx.clear();m_lastReceive={};
  }
  void poll(uint64_t now) {
    if(!active()) return;
    uint64_t then=m_info.state==LEFONY_CHANNEL_CONNECTED?m_hostAt:m_since;
    uint32_t limit=m_info.state==LEFONY_CHANNEL_CONNECTED?LEFONY_CHANNEL_LEASE_MILLIS:LEFONY_CHANNEL_PAIR_MILLIS;
    if(now<then || now-then>=limit) finish(LEFONY_CHANNEL_TIMEOUT);
  }
  void consent(bool allow,uint64_t now) {
    poll(now);if(!pairing()) return;
    if(!allow) {finish(LEFONY_CHANNEL_DENIED);return;}
    m_info.state=LEFONY_CHANNEL_CONNECTED;m_hostAt=now;
  }
  int request(LefonyChannelRequest &r,void *buffer,uint64_t now) {
    if(!validRequest(r)) return -LEFONY_CHANNEL_INVALID;
    poll(now);
    if(r.operation==LEFONY_CHANNEL_INFO) {auto value=info();memcpy(buffer,&value,sizeof(value));r.transferred=sizeof(value);return 0;}
    if(r.operation==LEFONY_CHANNEL_OPEN) {
      if(active()) return -LEFONY_CHANNEL_AGAIN;
      if(m_counter==0xffffffffu) return -LEFONY_CHANNEL_EXHAUSTED;
      m_tx.clear();m_rx.clear();m_lastReceive={};m_lastAck=0;
      memset(m_info.nonce,0,sizeof(m_info.nonce));memset(m_info.hostLabel,0,sizeof(m_info.hostLabel));
      m_info.session=++m_counter;m_info.error=0;m_info.state=LEFONY_CHANNEL_WAIT_HOST;
      m_info.sendSequence=m_info.receiveSequence=1;m_since=m_hostAt=now;
      r.session=m_info.session;r.state=m_info.state;return 0;
    }
    if(r.session!=m_info.session) return -LEFONY_CHANNEL_STALE;
    if(r.operation==LEFONY_CHANNEL_CLOSE) {finish(LEFONY_CHANNEL_CANCELLED);return 0;}
    if(m_info.state==LEFONY_CHANNEL_ENDED) return -static_cast<int>(m_info.error?m_info.error:LEFONY_CHANNEL_DISCONNECTED);
    if(m_info.state!=LEFONY_CHANNEL_CONNECTED) return -LEFONY_CHANNEL_AGAIN;
    if(r.operation==LEFONY_CHANNEL_SEND) {
      if(m_tx.count==LEFONY_CHANNEL_QUEUE) return -LEFONY_CHANNEL_AGAIN;
      if(m_info.sendSequence==0xffffffffu) {finish(LEFONY_CHANNEL_EXHAUSTED);return -LEFONY_CHANNEL_EXHAUSTED;}
      LefonyChannelFrame frame={};frame.size=64+r.length;frame.schema=1;frame.session=m_info.session;
      frame.sequence=m_info.sendSequence++;frame.kind=r.kind;frame.length=r.length;
      memcpy(frame.nonce,m_info.nonce,sizeof(frame.nonce));if(r.length) memcpy(frame.data,buffer,r.length);
      m_tx.push(frame);r.sequence=frame.sequence;r.transferred=r.length;return 0;
    }
    if(!m_rx.count) return -LEFONY_CHANNEL_AGAIN;
    const auto &frame=m_rx.front();if(r.capacity<frame.length) return -LEFONY_CHANNEL_TOO_SMALL;
    if(frame.length) memcpy(buffer,frame.data,frame.length);
    r.sequence=frame.sequence;r.kind=frame.kind;r.length=r.transferred=frame.length;m_rx.pop();return 0;
  }
  bool attach(const LefonyChannelAttach &a,uint64_t now) {
    poll(now);
    if(a.size!=sizeof(a) || a.schema!=1 || a.flags || !a.session || a.session!=m_info.session ||
       !(a.nonce[0]|a.nonce[1]|a.nonce[2]|a.nonce[3]) || !label(a.label)) return false;
    if(m_info.state==LEFONY_CHANNEL_WAIT_USER || m_info.state==LEFONY_CHANNEL_CONNECTED)
      return !memcmp(a.nonce,m_info.nonce,16) && !memcmp(a.label,m_info.hostLabel,32);
    if(m_info.state!=LEFONY_CHANNEL_WAIT_HOST) return false;
    memcpy(m_info.nonce,a.nonce,16);memcpy(m_info.hostLabel,a.label,32);
    m_info.state=LEFONY_CHANNEL_WAIT_USER;return true;
  }
  bool receive(const LefonyChannelFrame &f,unsigned bytes,uint64_t now) {
    poll(now);
    if(!matches(f.session,f.nonce) || f.schema!=1 || f.length>LEFONY_CHANNEL_PAYLOAD || f.size!=64+f.length || bytes!=f.size ||
       !f.kind || f.kind>65535 || !f.sequence) return false;
    for(auto word:f.reserved) if(word) return false;
    if(f.sequence==m_info.receiveSequence-1 && f.sequence && !memcmp(&f,&m_lastReceive,bytes)) {m_hostAt=now;return true;}
    if(f.sequence!=m_info.receiveSequence || m_rx.count==LEFONY_CHANNEL_QUEUE) return false;
    if(m_info.receiveSequence==0xffffffffu) {finish(LEFONY_CHANNEL_EXHAUSTED);return false;}
    m_rx.push(f);m_lastReceive=f;m_info.receiveSequence++;m_hostAt=now;return true;
  }
  bool read(uint32_t session,void *buffer,unsigned capacity,unsigned *bytes,uint64_t now) {
    poll(now);if(m_info.state!=LEFONY_CHANNEL_CONNECTED || session!=m_info.session || !m_tx.count) return false;
    const auto &frame=m_tx.front();if(capacity<frame.size) return false;
    memcpy(buffer,&frame,frame.size);*bytes=frame.size;return true;
  }
  bool control(unsigned command,const LefonyChannelControl &c,uint64_t now) {
    poll(now);
    bool pendingClose=command==0x7e && pairing() && c.session==m_info.session && !memcmp(c.nonce,m_info.nonce,16);
    if(c.size!=sizeof(c) || c.schema!=1 || !(matches(c.session,c.nonce) || pendingClose)) return false;
    if(command==0x7c) {
      if(!c.sequence) return false;
      if(c.sequence!=m_lastAck) {
        if(!m_tx.count || c.sequence!=m_tx.front().sequence) return false;
        m_tx.pop();m_lastAck=c.sequence;
      }
    } else if(command==0x7d || command==0x7e) {
      if(c.sequence) return false;
      if(command==0x7e) finish(LEFONY_CHANNEL_DISCONNECTED);
    } else return false;
    m_hostAt=now;return true;
  }
private:
  struct Queue {
    LefonyChannelFrame frames[LEFONY_CHANNEL_QUEUE]{};unsigned first=0,count=0;
    void clear() {memset(frames,0,sizeof(frames));first=count=0;}
    const LefonyChannelFrame &front() const {return frames[first];}
    void push(const LefonyChannelFrame &f) {frames[(first+count)%LEFONY_CHANNEL_QUEUE]=f;count++;}
    void pop() {frames[first]={};first=(first+1)%LEFONY_CHANNEL_QUEUE;count--;}
  };
  bool matches(uint32_t session,const uint32_t *nonce) const {
    return m_info.state==LEFONY_CHANNEL_CONNECTED && session==m_info.session && !memcmp(nonce,m_info.nonce,16);
  }
  static bool label(const char *s) {
    unsigned n=0;while(n<32 && s[n]) {if(s[n]<32 || s[n]>126) return false;n++;}
    if(!n || n==32) return false;
    while(n<32) if(s[n++]) return false;
    return true;
  }
  LefonyChannelInfo m_info{};Queue m_tx,m_rx;LefonyChannelFrame m_lastReceive{};
  uint32_t m_counter=0,m_lastAck=0;uint64_t m_since=0,m_hostAt=0;
};
void owner(const char *,const char *,const uint8_t *,const uint8_t *);
void clear();
void finish(uint32_t error=LEFONY_CHANNEL_DISCONNECTED);
void poll();
bool pairing();
LefonyChannelInfo info();
void consent(bool);
int request(LefonyChannelRequest &,void *,bool);
bool usbRequest(uint8_t,uint32_t,const uint8_t *,unsigned);
bool usbResponse(uint8_t,uint32_t,uint8_t *,unsigned,unsigned *);
}}
#endif

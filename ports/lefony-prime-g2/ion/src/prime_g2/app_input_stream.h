// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef PRIME_G2_APP_INPUT_STREAM_H
#define PRIME_G2_APP_INPUT_STREAM_H
#include "lefony/input_stream_wire.h"
#include <string.h>
namespace PrimeG2 {
// Observes the normal OS scan and touch dispatch. No peripheral access, heap,
// user pointer or asynchronous callback. One foreground session owns the queue.
class AppInputStream {
public:
  static constexpr uint64_t Back=UINT64_C(1)<<38;
  void focus(bool active) {
    mActive=active;mHead=0;mCount=0;mDropped=0;mSequence=0;
    mHeld=0;mBlocked=mRaw|mStable;mBackAllowed=false;mTouch={};mTouch.phase=3;
    mFlags=LEFONY_INPUT_FOCUS_RESET;++mGeneration;
  }
  void backAllowed(bool allowed,uint32_t now) {
    if(allowed==mBackAllowed) return;
    mBackAllowed=allowed;
    if(allowed) mBlocked|=(mRaw|mStable)&Back;
    publishKeys(now);
  }
  void observe(uint64_t down,uint32_t now,uint32_t modifiers) {
    // Per-key stability avoids a bouncing key delaying the rest of a chord.
    // Existing logical events/repeats retain their independent OS policy.
    const uint64_t changed=down^mRaw;mRaw=down;
    for(unsigned bit=0;bit<64;bit++) {
      const uint64_t mask=UINT64_C(1)<<bit;
      if(changed&mask) mChanged[bit]=now;
      else if((mStable^down)&mask && uint32_t(now-mChanged[bit])>=10)
        mStable=(mStable&~mask)|(down&mask);
    }
    mBlocked&=mRaw|mStable;mModifiers=modifiers&7;
    publishKeys(now);
  }
  void touch(const LefonyContactTransition &touch,uint32_t flags,uint32_t now) {
    if(!mActive) return;
    mTouch=touch;
    // Event coordinates retain the released contact; live state has none.
    if(!mTouch.count) memset(mTouch.contacts,0,sizeof(mTouch.contacts));
    LefonyStreamEvent event={};event.kind=LEFONY_INPUT_CONTACTS;
    event.flags=flags&LEFONY_INPUT_CONTACTS_CHANGED;event.data.touch=touch;
    append(event,now);
  }
  void read(LefonyInputStream &out,uint32_t now) {
    memset(&out,0,sizeof(out));out.size=sizeof(out);out.version=1;
    out.sequence=mSequence;out.millis=now;out.flags=mFlags;
    words(mHeld,out.held);out.modifiers=mModifiers;
    out.touchPhase=mTouch.phase;out.contactCount=mTouch.count;
    memcpy(out.contacts,mTouch.contacts,sizeof(out.contacts));out.generation=mGeneration;
    if(mDropped) {
      // A gap cannot be safely replayed. Return one authoritative resync and
      // count every discarded event, including the remaining stale backlog.
      out.flags|=LEFONY_INPUT_OVERFLOW;
      out.dropped=mDropped>0xffffffffu-mCount?0xffffffffu:mDropped+mCount;
      mHead=0;mCount=0;mDropped=0;
    } else {
      while(mCount && out.count<LEFONY_INPUT_STREAM_EVENTS) {
        out.events[out.count++]=mQueue[mHead];
        mHead=(mHead+1)%LEFONY_INPUT_STREAM_QUEUE;--mCount;
      }
      out.pending=mCount;
    }
    mFlags=0;
  }
private:
  static void words(uint64_t value,uint32_t out[2]) { out[0]=uint32_t(value);out[1]=uint32_t(value>>32); }
  void publishKeys(uint32_t now) {
    if(!mActive) return;
    const uint64_t held=mStable&~mBlocked&~(mBackAllowed?UINT64_C(0):Back);
    if(held==mHeld) return;
    LefonyStreamEvent event={};event.kind=LEFONY_INPUT_KEYS;
    words(held&~mHeld,event.data.keys.down);words(mHeld&~held,event.data.keys.up);
    words(held,event.data.keys.held);event.data.keys.modifiers=mModifiers;
    mHeld=held;append(event,now);
  }
  void append(LefonyStreamEvent &event,uint32_t now) {
    event.sequence=++mSequence;event.millis=now;
    if(mCount==LEFONY_INPUT_STREAM_QUEUE) {
      mHead=(mHead+1)%LEFONY_INPUT_STREAM_QUEUE;--mCount;
      if(mDropped!=0xffffffffu) ++mDropped;
    }
    mQueue[(mHead+mCount)%LEFONY_INPUT_STREAM_QUEUE]=event;++mCount;
  }
  bool mActive=false,mBackAllowed=false;
  uint64_t mRaw=0,mStable=0,mHeld=0,mBlocked=0;
  uint32_t mChanged[64]={},mModifiers=0,mSequence=0;
  uint32_t mHead=0,mCount=0,mDropped=0,mFlags=0,mGeneration=0;
  LefonyContactTransition mTouch={3,0,{{0,0,0},{0,0,0}}};
  LefonyStreamEvent mQueue[LEFONY_INPUT_STREAM_QUEUE]={};
};
}
#endif

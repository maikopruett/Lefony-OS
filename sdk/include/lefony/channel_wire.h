/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_CHANNEL_WIRE_H
#define LEFONY_CHANNEL_WIRE_H
#include <stdint.h>
#define LEFONY_CHANNEL_SERVICE 17u
#define LEFONY_CHANNEL_CAPABILITY 4096u
#define LEFONY_CHANNEL_API 11u
#define LEFONY_CHANNEL_PAYLOAD 448u
#define LEFONY_CHANNEL_QUEUE 4u
#define LEFONY_CHANNEL_PAIR_MILLIS 30000u
#define LEFONY_CHANNEL_LEASE_MILLIS 5000u
enum LefonyChannelOperation {LEFONY_CHANNEL_OPEN=1,LEFONY_CHANNEL_INFO=2,
  LEFONY_CHANNEL_SEND=3,LEFONY_CHANNEL_RECEIVE=4,LEFONY_CHANNEL_CLOSE=5};
enum LefonyChannelState {LEFONY_CHANNEL_CLOSED=0,LEFONY_CHANNEL_WAIT_HOST=1,
  LEFONY_CHANNEL_WAIT_USER=2,LEFONY_CHANNEL_CONNECTED=3,LEFONY_CHANNEL_ENDED=4};
enum LefonyChannelError {LEFONY_CHANNEL_UNSUPPORTED=3,LEFONY_CHANNEL_INVALID=4,
  LEFONY_CHANNEL_DENIED=5,LEFONY_CHANNEL_AGAIN=6,LEFONY_CHANNEL_STALE=7,
  LEFONY_CHANNEL_DISCONNECTED=8,LEFONY_CHANNEL_TIMEOUT=9,LEFONY_CHANNEL_CANCELLED=10,
  LEFONY_CHANNEL_EXHAUSTED=11,LEFONY_CHANNEL_TOO_SMALL=12};
/* All outputs/flags/reserved zero on entry. OPEN has no arguments. INFO copies
 * 320 bytes. SEND copies one kind 1..65535, length 0..448. RECEIVE reports kind,
 * length and sequence and consumes exactly one complete message. Failed calls
 * preserve the request/output. Buffers cannot overlap the request. */
typedef struct {
  uint32_t size,schema,operation,flags,session,buffer,capacity,length,kind,sequence;
  uint32_t transferred,state,error,reserved[3];
} LefonyChannelRequest;
/* Package payload and signer IDs come from the authenticated LFAPP1 envelope.
 * Strings are NUL-terminated ASCII. Nonce binds host frames to a session; USB
 * is not encrypted and does not isolate a compromised host with USB access. */
typedef struct {
  uint32_t size,schema,state,session,error,sendSequence,receiveSequence;
  uint32_t sendQueued,receiveQueued,nextReceiveBytes,maximumPayload,queueCapacity;
  uint32_t nonce[4];char appId[52],appName[84];uint8_t packageHash[32],signer[32];
  char hostLabel[32];uint32_t reserved[6];
} LefonyChannelInfo;
/* USB 0x79 OUT; size=64, schema=1, flags=0; cryptographically random host nonce.
 * Only an app-created WAIT_HOST session can be attached. Repeated identical
 * attaches do not restart pairing or clear queues. */
typedef struct {uint32_t size,schema,session,flags,nonce[4];char label[32];} LefonyChannelAttach;
/* USB 0x7a OUT / 0x7b IN. Actual wire bytes are 64+length. App and host sequence
 * spaces are independent. Host reads do not consume; 0x7c explicitly ACKs. */
typedef struct {
  uint32_t size,schema,session,sequence,kind,length,nonce[4],reserved[6];
  uint8_t data[LEFONY_CHANNEL_PAYLOAD];
} LefonyChannelFrame;
/* USB 0x7c ACK (sequence), 0x7d keepalive and 0x7e close (sequence=0). */
typedef struct {uint32_t size,schema,session,sequence,nonce[4];} LefonyChannelControl;
#ifdef __cplusplus
static_assert(sizeof(LefonyChannelRequest)==64,"channel request size");
static_assert(sizeof(LefonyChannelInfo)==320,"channel info size");
static_assert(sizeof(LefonyChannelFrame)==512,"channel frame size");
static_assert(sizeof(LefonyChannelAttach)==64,"channel attach size");
static_assert(sizeof(LefonyChannelControl)==32,"channel control size");
#else
_Static_assert(sizeof(LefonyChannelRequest)==64,"channel request size");
_Static_assert(sizeof(LefonyChannelInfo)==320,"channel info size");
_Static_assert(sizeof(LefonyChannelFrame)==512,"channel frame size");
_Static_assert(sizeof(LefonyChannelAttach)==64,"channel attach size");
_Static_assert(sizeof(LefonyChannelControl)==32,"channel control size");
#endif
#endif

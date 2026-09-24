/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_HTTPS_H
#define LEFONY_HTTPS_H
#include "channel.h"
#include <string.h>
/* Companion protocol 1 over the API 11 channel. Integers are little-endian.
 * Request IDs increase within one paired session. One request runs at a time.
 * URL and headers follow BEGIN in separate ordered fragments. Header bytes are
 * ASCII "Name: value\n" lines; URL bytes are percent-encoded ASCII, without NUL.
 * Upload chunks require CREDIT. Response HEADER/DATA offsets start at zero.
 * A failed/cancelled mutation can have an unknown remote outcome. Never retry
 * it automatically. All helpers return the underlying channel status. */
enum {
  LEFONY_HTTPS_BEGIN=0x100,LEFONY_HTTPS_URL=0x101,LEFONY_HTTPS_HEADERS=0x102,
  LEFONY_HTTPS_UPLOAD=0x103,LEFONY_HTTPS_CANCEL=0x104,
  LEFONY_HTTPS_RESPONSE=0x180,LEFONY_HTTPS_HEADER=0x181,LEFONY_HTTPS_DATA=0x182,
  LEFONY_HTTPS_DONE=0x183,LEFONY_HTTPS_ERROR=0x184,LEFONY_HTTPS_CREDIT=0x185,
  LEFONY_HTTPS_PROGRESS=0x186,
  LEFONY_HTTPS_GET=1,LEFONY_HTTPS_HEAD=2,LEFONY_HTTPS_POST=3,
  LEFONY_HTTPS_PUT=4,LEFONY_HTTPS_PATCH=5,LEFONY_HTTPS_DELETE=6,
  LEFONY_HTTPS_POLICY=1,LEFONY_HTTPS_PROTOCOL=2,LEFONY_HTTPS_TLS=3,
  LEFONY_HTTPS_NETWORK=4,LEFONY_HTTPS_TIMEOUT=5,LEFONY_HTTPS_CANCELLED=6,
  LEFONY_HTTPS_OUTCOME_UNKNOWN=1,LEFONY_HTTPS_UPLOAD_FINAL=1,
  LEFONY_HTTPS_UPLOAD_CHUNK=436,LEFONY_HTTPS_CHUNK=440
};
#define LEFONY_HTTPS_UNKNOWN UINT32_MAX
typedef struct {
  uint32_t schema,id,method,uploadBytes,responseLimit,timeoutMillis,urlBytes,headerBytes;
} LefonyHTTPSBegin;
typedef struct {
  uint32_t schema,id,status,headerBytes,uploadBytes,responseBytes,flags,reserved;
} LefonyHTTPSResponse;
typedef struct {uint32_t id,uploadBytes,responseBytes,flags;} LefonyHTTPSDone;
typedef struct {uint32_t id,code,flags,uploadBytes,responseBytes,reserved;} LefonyHTTPSError;
typedef struct {uint32_t id,offset,maximum;} LefonyHTTPSCredit;
typedef struct {uint32_t id,uploadBytes,responseBytes,phase;} LefonyHTTPSProgress;
static inline int32_t lefony_https_begin(uint32_t session,const LefonyHTTPSBegin *request) {
  if(!request || request->schema!=1 || !request->id || request->method<1 || request->method>6 ||
     !request->urlBytes || request->urlBytes>2048 || request->headerBytes>4096 ||
     request->responseLimit>32u*1024*1024 || request->timeoutMillis<100 || request->timeoutMillis>120000 ||
     (request->uploadBytes!=LEFONY_HTTPS_UNKNOWN && request->uploadBytes>32u*1024*1024) ||
     (request->method<=2 && request->uploadBytes)) return -LEFONY_CHANNEL_INVALID;
  return lefony_channel_send(session,LEFONY_HTTPS_BEGIN,request,sizeof(*request));
}
static inline int32_t lefony_https_metadata(uint32_t session,uint32_t kind,uint32_t id,uint32_t offset,const void *data,uint32_t bytes) {
  if((kind!=LEFONY_HTTPS_URL && kind!=LEFONY_HTTPS_HEADERS) || !id || !bytes || bytes>440 || !data) return -LEFONY_CHANNEL_INVALID;
  uint32_t frame[112];frame[0]=id;frame[1]=offset;memcpy(frame+2,data,bytes);
  return lefony_channel_send(session,kind,frame,8+bytes);
}
static inline int32_t lefony_https_upload(uint32_t session,uint32_t id,uint32_t offset,const void *data,uint32_t bytes,int final) {
  if(!id || bytes>436 || (bytes && !data) || (!bytes && !final) || (final!=0 && final!=1)) return -LEFONY_CHANNEL_INVALID;
  uint32_t frame[112];frame[0]=id;frame[1]=offset;frame[2]=(uint32_t)final;
  if(bytes) memcpy(frame+3,data,bytes);
  return lefony_channel_send(session,LEFONY_HTTPS_UPLOAD,frame,12+bytes);
}
static inline int32_t lefony_https_cancel(uint32_t session,uint32_t id) {
  if(!id) return -LEFONY_CHANNEL_INVALID;
  return lefony_channel_send(session,LEFONY_HTTPS_CANCEL,&id,4);
}
#ifdef __cplusplus
static_assert(sizeof(LefonyHTTPSBegin)==32 && sizeof(LefonyHTTPSResponse)==32 && sizeof(LefonyHTTPSError)==24,"HTTPS wire sizes");
#else
_Static_assert(sizeof(LefonyHTTPSBegin)==32 && sizeof(LefonyHTTPSResponse)==32 && sizeof(LefonyHTTPSError)==24,"HTTPS wire sizes");
#endif
#endif

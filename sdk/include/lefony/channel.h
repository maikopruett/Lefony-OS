/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_CHANNEL_H
#define LEFONY_CHANNEL_H
#include "app_c.h"
#include "channel_wire.h"
static inline LefonyChannelRequest lefony_channel_request(uint32_t operation) {
#ifdef __cplusplus
  LefonyChannelRequest r={};
#else
  LefonyChannelRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;return r;
}
static inline int32_t lefony_channel(LefonyChannelRequest *r) {
  return r?lefony_service(LEFONY_CHANNEL_SERVICE,r):-LEFONY_CHANNEL_INVALID;
}
static inline int32_t lefony_channel_open(uint32_t *session) {
  if(!session) return -LEFONY_CHANNEL_INVALID;
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_OPEN);
  int32_t result=lefony_channel(&r);if(!result) *session=r.session;return result;
}
static inline int32_t lefony_channel_info(LefonyChannelInfo *info) {
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_INFO);
  r.buffer=(uint32_t)(uintptr_t)info;r.capacity=sizeof(*info);return lefony_channel(&r);
}
static inline int32_t lefony_channel_send(uint32_t session,uint32_t kind,const void *buffer,uint32_t length) {
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_SEND);
  r.session=session;r.kind=kind;r.buffer=(uint32_t)(uintptr_t)buffer;r.capacity=r.length=length;return lefony_channel(&r);
}
/* On success r.kind/r.sequence/r.length identify the received message. */
static inline int32_t lefony_channel_receive(uint32_t session,void *buffer,uint32_t capacity,LefonyChannelRequest *result) {
  if(!result) return -LEFONY_CHANNEL_INVALID;
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_RECEIVE);
  r.session=session;r.buffer=(uint32_t)(uintptr_t)buffer;r.capacity=capacity;
  int32_t status=lefony_channel(&r);if(!status) *result=r;return status;
}
static inline int32_t lefony_channel_close(uint32_t session) {
  LefonyChannelRequest r=lefony_channel_request(LEFONY_CHANNEL_CLOSE);r.session=session;return lefony_channel(&r);
}
#endif

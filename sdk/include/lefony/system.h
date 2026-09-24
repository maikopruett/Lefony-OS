/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_SYSTEM_H
#define LEFONY_SYSTEM_H
#include "app_c.h"
#include "system_wire.h"
static inline LefonySystemRequest lefony_system_request(uint32_t operation) {
#ifdef __cplusplus
  LefonySystemRequest r={};
#else
  LefonySystemRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;return r;
}
static inline int32_t lefony_system(LefonySystemRequest *request) {
  return request?lefony_service(LEFONY_SYSTEM_SERVICE,request):-LEFONY_SYSTEM_INVALID;
}
static inline int32_t lefony_system_info(LefonySystemInfo *info) {
  LefonySystemRequest r=lefony_system_request(LEFONY_SYSTEM_INFO);
  r.buffer=(uint32_t)(uintptr_t)info;r.capacity=sizeof(*info);return lefony_system(&r);
}
static inline uint64_t lefony_system_millis(const LefonySystemInfo *info) {
  return ((uint64_t)info->monotonicHigh<<32)|info->monotonicLow;
}
static inline int32_t lefony_brightness(uint32_t value) {
  LefonySystemRequest r=lefony_system_request(LEFONY_SYSTEM_BRIGHTNESS);r.value=value;return lefony_system(&r);
}
static inline int32_t lefony_restore_brightness(void) {
  LefonySystemRequest r=lefony_system_request(LEFONY_SYSTEM_RESTORE_BRIGHTNESS);return lefony_system(&r);
}
static inline int32_t lefony_clipboard_write(uint32_t sequence,const char *text,uint32_t bytes) {
  LefonySystemRequest r=lefony_system_request(LEFONY_SYSTEM_CLIPBOARD_WRITE);
  r.sequence=sequence;r.buffer=(uint32_t)(uintptr_t)text;r.capacity=bytes;return lefony_system(&r);
}
/* Returns payload bytes (excluding the terminating NUL), or a negative error. */
static inline int32_t lefony_clipboard_read(uint32_t sequence,char *text,uint32_t capacity) {
  LefonySystemRequest r=lefony_system_request(LEFONY_SYSTEM_CLIPBOARD_READ);
  r.sequence=sequence;r.buffer=(uint32_t)(uintptr_t)text;r.capacity=capacity;
  int32_t result=lefony_system(&r);return result<0?result:(int32_t)r.transferred;
}
#endif

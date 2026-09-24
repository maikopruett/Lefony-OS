/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_FOREGROUND_H
#define LEFONY_FOREGROUND_H
#include "app_c.h"
#include "foreground_wire.h"
static inline LefonyProgramRequest lefony_program_request(uint32_t operation) {
#ifdef __cplusplus
  LefonyProgramRequest r={};
#else
  LefonyProgramRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;return r;
}
static inline int32_t lefony_program_enter(void) {
  LefonyProgramRequest r=lefony_program_request(LEFONY_PROGRAM_ENTER);
  r.profile=LEFONY_FOREGROUND_PROFILE;
  return lefony_service(LEFONY_FOREGROUND_SERVICE,&r);
}
static inline int32_t lefony_program_yield(void) {
  LefonyProgramRequest r=lefony_program_request(LEFONY_PROGRAM_YIELD);
  return lefony_service(LEFONY_FOREGROUND_SERVICE,&r);
}
static inline int32_t lefony_program_sleep(uint32_t milliseconds) {
  LefonyProgramRequest r=lefony_program_request(LEFONY_PROGRAM_SLEEP);
  if(milliseconds>60000) return -4;
  r.argument=(int32_t)milliseconds;return lefony_service(LEFONY_FOREGROUND_SERVICE,&r);
}
/* A successful exit never returns. Failure leaves the caller running. */
static inline int32_t lefony_program_exit(int32_t status) {
  LefonyProgramRequest r=lefony_program_request(LEFONY_PROGRAM_EXIT);
  r.argument=status;return lefony_service(LEFONY_FOREGROUND_SERVICE,&r);
}
static inline int32_t lefony_program_info(LefonyProgramRequest *out) {
  if(!out) return -4;
  *out=lefony_program_request(LEFONY_PROGRAM_INFO);
  return lefony_service(LEFONY_FOREGROUND_SERVICE,out);
}
/* Copies pixels to OS composition and yields for presentation. No app buffer
 * remains owned by the OS when this call returns. RGB565, stride in pixels. */
static inline int32_t lefony_present(const uint16_t *pixels,uint32_t x,uint32_t y,
                                    uint32_t width,uint32_t height,uint32_t stride) {
  if(!height || height>240 || stride>320 || width>320) return -4;
  LefonyPixelRequest r={sizeof(r),1,0,x,y,width,height,stride,
    (uint32_t)(uintptr_t)pixels,((height-1)*stride+width)*2};
  return lefony_service(LEFONY_PIXELS_SERVICE,&r);
}
#endif

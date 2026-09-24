/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_TEXT_H
#define LEFONY_TEXT_H
#include "app_c.h"
#include "text_wire.h"
static inline LefonyTextRequest lefony_text_request(uint32_t operation,uint32_t font,const char *text,uint32_t bytes) {
#ifdef __cplusplus
  LefonyTextRequest r={};
#else
  LefonyTextRequest r={0};
#endif
  r.size=sizeof(r);r.schema=1;r.operation=operation;r.font=font;
  r.text=(uint32_t)(uintptr_t)text;r.textBytes=bytes;return r;
}
static inline int32_t lefony_typography(LefonyTextRequest *request) {
  return request?lefony_service(LEFONY_TEXT_SERVICE,request):-4;
}
#endif

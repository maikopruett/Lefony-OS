/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
#ifndef LEFONY_TEXT_WIRE_H
#define LEFONY_TEXT_WIRE_H
#include <stdint.h>
#define LEFONY_TEXT_SERVICE 15u
#define LEFONY_TEXT_CAPABILITY 1024u
#define LEFONY_TEXT_API 9u
#define LEFONY_TEXT_MAXIMUM 256u
enum LefonyTextOperation { LEFONY_TEXT_MEASURE=1,LEFONY_TEXT_DRAW=2 };
enum LefonyFont { LEFONY_FONT_SMALL=0,LEFONY_FONT_LARGE=1,LEFONY_FONT_SMALL_ITALIC=2,LEFONY_FONT_LARGE_ITALIC=3 };
enum LefonyTextFlags { LEFONY_TEXT_CLIPPED=1 };
/* Outputs must be zero on input. UTF-8 is bounded and excludes controls.
 * Unsupported glyphs return -5 without drawing or changing the request. */
typedef struct {
  uint32_t size,schema,operation,font;
  int32_t x,y,clipX,clipY,clipWidth,clipHeight;
  uint32_t foreground,background,text,textBytes;
  uint32_t width,height,glyphWidth,glyphHeight,flags,reserved;
} LefonyTextRequest;
#ifdef __cplusplus
static_assert(sizeof(LefonyTextRequest)==80,"text wire size");
#else
_Static_assert(sizeof(LefonyTextRequest)==80,"text wire size");
#endif
#endif

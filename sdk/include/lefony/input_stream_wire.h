/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_INPUT_STREAM_WIRE_H
#define LEFONY_INPUT_STREAM_WIRE_H
#include <stdint.h>

/* API 4, explicitly declared capability 32. Service 8 and ABI 1 are unchanged.
 * All masks use physical row*8+column positions in contracts/keys.json. */
enum {
  LEFONY_INPUT_STREAM_SERVICE=13, LEFONY_INPUT_STREAM_CAPABILITY=32,
  LEFONY_INPUT_STREAM_EVENTS=8, LEFONY_INPUT_STREAM_QUEUE=32,
  LEFONY_INPUT_KEYS=1, LEFONY_INPUT_CONTACTS=2,
  LEFONY_INPUT_OVERFLOW=1, LEFONY_INPUT_FOCUS_RESET=2,
  LEFONY_INPUT_CONTACTS_CHANGED=1,
  LEFONY_INPUT_SHIFT=1, LEFONY_INPUT_ALPHA=2, LEFONY_INPUT_ALPHA_LOCK=4
};
typedef struct { uint32_t id; int32_t x,y; } LefonyStreamContact;
typedef struct {
  uint32_t down[2],up[2],held[2],modifiers,reserved;
} LefonyKeyTransition;
typedef struct {
  uint32_t phase,count;
  LefonyStreamContact contacts[2];
} LefonyContactTransition;
typedef struct {
  uint32_t sequence,millis,kind,flags;
  union { LefonyKeyTransition keys; LefonyContactTransition touch; } data;
} LefonyStreamEvent;
typedef struct {
  uint32_t size,version,reserved;
  uint32_t sequence,millis,flags;
  uint32_t held[2],modifiers,touchPhase,contactCount;
  LefonyStreamContact contacts[2];
  uint32_t count,pending,dropped,generation,reservedOutput[3];
  LefonyStreamEvent events[LEFONY_INPUT_STREAM_EVENTS];
} LefonyInputStream;
#ifdef __cplusplus
static_assert(sizeof(LefonyStreamEvent)==48,"input event wire size");
static_assert(sizeof(LefonyInputStream)==480,"input stream wire size");
#else
_Static_assert(sizeof(LefonyStreamEvent)==48,"input event wire size");
_Static_assert(sizeof(LefonyInputStream)==480,"input stream wire size");
#endif
#endif

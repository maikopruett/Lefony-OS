/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_FOREGROUND_WIRE_H
#define LEFONY_FOREGROUND_WIRE_H
#include <stdint.h>
/* API 3, manifest capability 16. Explicit opt-in; ABI 1 remains unchanged. */
enum {
  LEFONY_FOREGROUND_SERVICE=11, LEFONY_PIXELS_SERVICE=12,
  LEFONY_FOREGROUND_CAPABILITY=16, LEFONY_FOREGROUND_PROFILE=1,
  LEFONY_PROGRAM_ENTER=1, LEFONY_PROGRAM_YIELD=2, LEFONY_PROGRAM_SLEEP=3,
  LEFONY_PROGRAM_EXIT=4, LEFONY_PROGRAM_INFO=5
};
typedef struct {
  uint32_t size,schema,operation,flags;
  int32_t argument;
  uint32_t profile,heap,heapBytes,stackBytes,sliceMillis,frames,lastFrameMillis;
  uint32_t reserved[4];
} LefonyProgramRequest;
typedef struct {
  uint32_t size,schema,flags,x,y,width,height,stride,buffer,bytes;
} LefonyPixelRequest;
/* Optional app-local diagnostics, not a service request or firmware ABI.
 * Define LEFONY_PROFILE_HEAP=1 in a foreground-newlib-1 project to include it.
 * Allocated bytes include allocator padding/metadata, not requested payload. */
enum {
  LEFONY_HEAP_PROFILE_MAGIC=0x5048464c, LEFONY_HEAP_PROFILE_SCHEMA=1,
  LEFONY_HEAP_PROFILE_OBSERVED=1, LEFONY_HEAP_PROFILE_INVALID=2,
  LEFONY_HEAP_PROFILE_SATURATED=4
};
typedef struct {
  uint32_t magic,schema,size,sequence;
  uint32_t allocatedBytes,allocatedPeak,arenaBytes,arenaPeak;
  uint32_t observations,flags;
} LefonyHeapProfile;
#endif

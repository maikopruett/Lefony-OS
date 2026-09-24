/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
#ifndef LEFONY_APP_C_H
#define LEFONY_APP_C_H
#include <stdint.h>

/* C interface to the existing ABI 1 callback contract. This does not provide
 * main(), libc, persistent execution across waits, or additional memory. */
typedef uint32_t lefony_event_t;
enum {
  LEFONY_START = 0, LEFONY_KEY = 1, LEFONY_TICK = 2,
  LEFONY_TOUCH = 3, LEFONY_CLOSE = 4,
  LEFONY_WIDTH = 320, LEFONY_HEIGHT = 240,
  LEFONY_WHITE = 0xffff, LEFONY_GREEN = 0x2528, LEFONY_BLACK = 0
};
enum {
  LEFONY_KEY_UNKNOWN = 0, LEFONY_KEY_LEFT = 1, LEFONY_KEY_RIGHT = 2,
  LEFONY_KEY_UP = 3, LEFONY_KEY_DOWN = 4, LEFONY_KEY_CONFIRM = 5,
  LEFONY_KEY_DELETE = 6, LEFONY_KEY_DIGIT0 = 16,
  LEFONY_KEY_DECIMAL = 26, LEFONY_KEY_MINUS = 27
};
typedef struct {
  int32_t x, y, width, height;
  uint32_t color;
} lefony_rect_t;
typedef struct {
  int32_t x, y;
  uint32_t color, background;
  const char *value;
  uint32_t length;
} lefony_text_t;
typedef struct {
  uint32_t offset;
  void *buffer;
  uint32_t length;
} lefony_data_transfer_t;

static inline int32_t lefony_service(uint32_t number, const void *argument) {
  register uint32_t r0 __asm__("r0") = number;
  register const void *r1 __asm__("r1") = argument;
  __asm__ volatile("svc #0" : "+r"(r0), "+r"(r1) : :
                   "r2", "r3", "r12", "lr", "cc", "memory");
  return (int32_t)r0;
}
static inline int32_t lefony_fill(lefony_rect_t rect) {
  return lefony_service(1, &rect);
}
static inline int32_t lefony_text(lefony_text_t text) {
  return lefony_service(2, &text);
}
static inline uint32_t lefony_millis(void) {
  return (uint32_t)lefony_service(3, (const void *)0);
}
/* At most 4096 bytes per transfer into the app's 64 KiB staging store.
 * Positive returns count bytes; negative returns are errors. Writes become
 * durable only after the existing normal-close storage transaction completes. */
static inline int32_t lefony_read_data(uint32_t offset, void *buffer, uint32_t length) {
  lefony_data_transfer_t transfer = {offset, buffer, length};
  return lefony_service(4, &transfer);
}
static inline int32_t lefony_write_data(uint32_t offset, const void *buffer, uint32_t length) {
  lefony_data_transfer_t transfer = {offset, (void *)buffer, length};
  return lefony_service(5, &transfer);
}

#ifndef __cplusplus
void lefony_event(lefony_event_t event, uint32_t first, uint32_t second);
#endif
#endif

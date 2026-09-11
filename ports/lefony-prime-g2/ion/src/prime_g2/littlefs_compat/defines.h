// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_LITTLEFS_DEFINES_H
#define LEFONY_LITTLEFS_DEFINES_H
#include <stddef.h>
// The freestanding liba has bounded copy helpers but omits these C functions.
// Keep the adaptation local to littlefs's documented LFS_DEFINES hook.
static inline char *lefony_lfs_strcpy(char *dst, const char *src) {
  char *result = dst;
  while ((*dst++ = *src++)) {
  }
  return result;
}
static inline size_t lefony_lfs_span(const char *s, const char *set, int accept) {
  size_t n = 0;
  while (s[n]) {
    int found = 0;
    for (size_t i = 0; set[i]; i++)
      found |= s[n] == set[i];
    if (found != accept)
      break;
    n++;
  }
  return n;
}
static inline size_t lefony_lfs_strspn(const char *s, const char *set) {
  return lefony_lfs_span(s, set, 1);
}
static inline size_t lefony_lfs_strcspn(const char *s, const char *set) {
  return lefony_lfs_span(s, set, 0);
}
#define strcpy lefony_lfs_strcpy
#define strspn lefony_lfs_strspn
#define strcspn lefony_lfs_strcspn
#endif

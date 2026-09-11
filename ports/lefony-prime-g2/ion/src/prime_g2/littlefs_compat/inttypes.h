// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Upsilon's freestanding liba omits inttypes.h. littlefs only uses these
// printf fragments in diagnostics (disabled in firmware); no libc is linked.
#ifndef LEFONY_LITTLEFS_INTTYPES_H
#define LEFONY_LITTLEFS_INTTYPES_H
#include <stdint.h>
#define PRIu32 "u"
#define PRId32 "d"
#define PRIx32 "x"
#endif

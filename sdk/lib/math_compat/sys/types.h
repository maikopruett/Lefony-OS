// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_MATH_SYS_TYPES_H
#define LEFONY_MATH_SYS_TYPES_H
#include <stdint.h>
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "SDK math currently supports little-endian targets only"
#endif
#define LITTLE_ENDIAN 0x1234
#define BIG_ENDIAN 0x4321
#define BYTE_ORDER LITTLE_ENDIAN
typedef uint32_t u_int32_t;
typedef uint64_t u_int64_t;
#endif

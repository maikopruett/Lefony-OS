// SPDX-License-Identifier: CC-BY-NC-SA-4.0
// Private OpenBSD C compatibility: its int32_t function definitions match int
// declarations. GCC's freestanding ARM stdint instead chooses 32-bit long.
#ifndef LEFONY_MATH_STDINT_H
#define LEFONY_MATH_STDINT_H
_Static_assert(sizeof(int)==4 && sizeof(short)==2 && sizeof(char)==1,"unsupported integer widths");
typedef signed char int8_t;
typedef unsigned char uint8_t;
typedef signed short int16_t;
typedef unsigned short uint16_t;
typedef signed int int32_t;
typedef unsigned int uint32_t;
typedef __INT64_TYPE__ int64_t;
typedef __UINT64_TYPE__ uint64_t;
#endif

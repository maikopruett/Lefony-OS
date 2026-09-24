// SPDX-License-Identifier: CC-BY-NC-SA-4.0
#ifndef LEFONY_MEMORY_H
#define LEFONY_MEMORY_H
#include <stddef.h>
extern "C" {
void *memcpy(void *destination,const void *source,size_t size);
void *memmove(void *destination,const void *source,size_t size);
void *memset(void *destination,int value,size_t size);
int memcmp(const void *a,const void *b,size_t size);
}
#endif

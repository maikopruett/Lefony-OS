/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
/* App-local newlib hooks. Derived from the qualified architecture adapter. */
#include <lefony/foreground.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/time.h>
#include <sys/times.h>
static unsigned char *heap;
static size_t used, capacity;

#if LEFONY_PROFILE_HEAP
#include <malloc.h>
/* The pinned single-thread newlib normally supplies empty lock hooks. Sampling
 * at every unlock also sees realloc's temporary allocation before old storage
 * is freed. mallinfo scans free lists: this is an explicit diagnostic cost. */
_Static_assert(sizeof(LefonyHeapProfile)==40,"heap diagnostic layout");
__attribute__((used,section(".lefony.heap_profile"),aligned(4)))
volatile LefonyHeapProfile lefony_heap_profile={
  LEFONY_HEAP_PROFILE_MAGIC,LEFONY_HEAP_PROFILE_SCHEMA,sizeof(LefonyHeapProfile),
  0,0,0,0,0,0,0
};
static int sampling_heap;
void __malloc_lock(struct _reent *context) { (void)context; }
void __malloc_unlock(struct _reent *context) {
  if(sampling_heap) return;
  sampling_heap=1;
  int saved_errno=context->_errno;
  struct mallinfo info=_mallinfo_r(context);
  context->_errno=saved_errno;
  lefony_heap_profile.sequence++;
  __asm__ volatile("dmb ish" ::: "memory");
  if(info.arena>capacity || info.uordblks>info.arena) {
    lefony_heap_profile.flags|=LEFONY_HEAP_PROFILE_INVALID;
  } else {
    lefony_heap_profile.allocatedBytes=info.uordblks;
    lefony_heap_profile.arenaBytes=info.arena;
    if(info.uordblks>lefony_heap_profile.allocatedPeak)
      lefony_heap_profile.allocatedPeak=info.uordblks;
    if(info.arena>lefony_heap_profile.arenaPeak)
      lefony_heap_profile.arenaPeak=info.arena;
    lefony_heap_profile.flags|=LEFONY_HEAP_PROFILE_OBSERVED;
    if(lefony_heap_profile.observations==UINT32_MAX)
      lefony_heap_profile.flags|=LEFONY_HEAP_PROFILE_SATURATED;
    else lefony_heap_profile.observations++;
  }
  __asm__ volatile("dmb ish" ::: "memory");
  lefony_heap_profile.sequence++;
  sampling_heap=0;
}
#endif

void *_sbrk(ptrdiff_t increment) {
  if (!heap) {
    LefonyProgramRequest info;
    if (lefony_program_info(&info) != 0) { errno = ENOMEM; return (void *)-1; }
    heap = (unsigned char *)(uintptr_t)info.heap;
    capacity = info.heapBytes;
  }
  void *result = heap + used;
  if (increment < 0) {
    size_t shrink = (size_t)(-(increment + 1)) + 1;
    if (shrink > used) { errno = ENOMEM; return (void *)-1; }
    used -= shrink;
  } else {
    if ((size_t)increment > capacity - used) { errno = ENOMEM; return (void *)-1; }
    used += (size_t)increment;
  }
  return result;
}

/* There is no process/signal service, CPU-time accounting or qualified wall
 * clock in this profile. Do not turn monotonic time into a fictitious date. */
int _getpid(void) { errno = ENOSYS; return -1; }
int _kill(int pid, int signal) { (void)pid; (void)signal; errno = ENOSYS; return -1; }
int _gettimeofday(struct timeval *value, void *zone) {
  (void)value; (void)zone; errno = ENOSYS; return -1;
}
clock_t _times(struct tms *value) { (void)value; errno = ENOSYS; return (clock_t)-1; }
__attribute__((noreturn)) void _exit(int result) {
  lefony_program_exit(result);
  /* A failed exit request cannot be reported as successful termination. */
  __asm__ volatile("udf #0");
  for (;;) {}
}

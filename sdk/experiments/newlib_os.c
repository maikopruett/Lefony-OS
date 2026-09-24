/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Reusable R0 newlib integration. File/process hooks explicitly fail until
 * actual OS adapters are implemented; this is not the public libc profile. */
#include <lefony/app_c.h>
#ifdef LEFONY_PUBLIC_FOREGROUND
#include <lefony/foreground.h>
#endif
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>

#ifndef NEWLIB_KERNEL_HEAP
static unsigned char storage[256*1024] __attribute__((aligned(16)));
static unsigned char *heap=storage;
static size_t capacity=sizeof(storage);
#else
static unsigned char *heap;
static size_t capacity;
#endif
static size_t used,peak;
size_t lefony_experiment_heap_used(void) { return used; }
size_t lefony_experiment_heap_peak(void) { return peak; }
size_t lefony_experiment_heap_capacity(void) { return capacity; }

void *_sbrk(ptrdiff_t increment) {
#ifdef NEWLIB_KERNEL_HEAP
  if(!heap) {
#ifdef LEFONY_PUBLIC_FOREGROUND
    LefonyProgramRequest info;
    if(lefony_program_info(&info)!=0) { errno=ENOMEM;return (void *)-1; }
    heap=(unsigned char *)(uintptr_t)info.heap;capacity=info.heapBytes;
#else
    uint32_t info[6]={24,1,0,0,0,0};
    if(lefony_service(0x7fff0003u,info)!=0) { errno=ENOMEM;return (void *)-1; }
    heap=(unsigned char *)(uintptr_t)info[2];capacity=info[3];
#endif
  }
#endif
  void *result=heap+used;
  if(increment<0) {
    size_t shrink=(size_t)(-(increment+1))+1;
    if(shrink>used) { errno=ENOMEM;return (void *)-1; }
    used-=shrink;
  } else {
    if((size_t)increment>capacity-used) { errno=ENOMEM;return (void *)-1; }
    used+=(size_t)increment;
    if(used>peak) peak=used;
  }
  return result;
}

#ifndef NEWLIB_FILES
int _open(const char *path,int flags,...) { (void)path;(void)flags;errno=ENOSYS;return -1; }
int _close(int fd) { (void)fd;errno=ENOSYS;return -1; }
int _read(int fd,void *buffer,size_t size) { (void)fd;(void)buffer;(void)size;errno=ENOSYS;return -1; }
int _write(int fd,const void *buffer,size_t size) { (void)fd;(void)buffer;(void)size;errno=ENOSYS;return -1; }
off_t _lseek(int fd,off_t offset,int whence) { (void)fd;(void)offset;(void)whence;errno=ENOSYS;return -1; }
int _fstat(int fd,struct stat *out) { (void)fd;(void)out;errno=ENOSYS;return -1; }
int _isatty(int fd) { (void)fd;errno=ENOSYS;return 0; }
#endif
int _getpid(void) { errno=ENOSYS;return -1; }
int _kill(int pid,int signal) { (void)pid;(void)signal;errno=ENOSYS;return -1; }
__attribute__((noreturn)) void _exit(int result) {
  (void)result;
#ifdef NEWLIB_KERNEL_HEAP
#ifdef LEFONY_PUBLIC_FOREGROUND
  lefony_program_exit(result);
#else
  lefony_service(0x7fff0005u,(const void *)(intptr_t)result);
#endif
#endif
  __asm__ volatile("udf #0");for(;;) {}
}

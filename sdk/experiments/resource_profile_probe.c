/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
/* Actual ARM stack writes, untouched reservations and guard faults. */
#include <lefony/app_c.h>
#ifdef PROFILE_MAIN
#include <lefony/foreground.h>
#include <stdlib.h>
#endif
#ifndef PROFILE_MODE
#define PROFILE_MODE 0
#endif
__attribute__((noinline)) static void paint(void) {
  volatile unsigned char bytes[8192];
  for(unsigned i=0;i<sizeof(bytes);i++) bytes[i]=0x3c;
  __asm__ volatile("" : : "r"(&bytes[0]) : "memory");
}
__attribute__((naked,noinline)) static void reserve(void) {
  __asm__ volatile("sub sp,sp,#32768\nmov r0,#3\nsvc #0\nadd sp,sp,#32768\nbx lr");
}
__attribute__((naked,noinline)) static void overflow(void) {
  __asm__ volatile("sub sp,sp,#65536\nsub sp,sp,#4096\nstr r0,[sp]\nudf #0");
}
__attribute__((naked,noinline)) static void spin(void) {
  __asm__ volatile("sub sp,sp,#49152\n1: b 1b");
}
static void work(void) {
  if(PROFILE_MODE==0) paint();
  if(PROFILE_MODE==1) reserve();
  if(PROFILE_MODE==2) overflow();
  if(PROFILE_MODE==4) spin();
  if(PROFILE_MODE==3) {
    if(*(volatile unsigned char *)0x102f0000!=0) __asm__ volatile("udf #0");
  }
}
#ifdef PROFILE_MAIN
int main(void) {
  void *allocation=malloc(65536);
  if(!allocation) return 7;
  work();lefony_program_sleep(20);reserve();free(allocation);
  return 0;
}
#else
void lefony_event(lefony_event_t event,uint32_t first,uint32_t second) {
  (void)event;(void)first;(void)second;work();
}
#endif

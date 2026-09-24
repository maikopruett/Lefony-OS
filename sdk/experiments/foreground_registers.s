/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
.syntax unified
.cpu cortex-a7
.fpu neon-vfpv4
.arm
.text
.global foreground_registers
.type foreground_registers,%function
foreground_registers:
  push {r4-r12,lr}
  vpush {d8-d15}
  vmrs r1,fpscr
  push {r1,r2}
  sub sp,sp,#328
  str r0,[sp,#256]
  /* Public 64-byte YIELD request after the VFP scratch area. */
  add r0,sp,#264
  mov r1,#0
  mov r2,#16
10:
  str r1,[r0],#4
  subs r2,r2,#1
  bne 10b
  mov r0,#64
  str r0,[sp,#264]
  mov r0,#1
  str r0,[sp,#268]
  mov r0,#2
  str r0,[sp,#272]
  /* Every VFP lane gets a distinct exact bit pattern, including caller-saved
   * d0..7 and d16..31. Round mode differs from the kernel's default. */
  mov r0,sp
  ldr r1,=0x12340000
  mov r2,#64
1:
  str r1,[r0],#4
  add r1,r1,#1
  subs r2,r2,#1
  bne 1b
  mov r0,sp
  vldmia r0!,{d0-d15}
  vldmia r0,{d16-d31}
  mov r0,#0x800000
  vmsr fpscr,r0
  mov r1,#1
  mov r2,#2
  mov r3,#3
  mov r4,#4
  mov r5,#5
  mov r6,#6
  mov r7,#7
  mov r8,#8
  mov r9,#9
  mov r10,#10
  mov r11,#11
  mov r12,#12
  ldr r0,[sp,#256]
  cmp r0,#0
  bne 3f
  /* Long enough to cross multiple timer periods even with a fast JIT. The
   * test also requires the kernel preemption counter to increase. */
  mov r0,#0x10000000
2:
  /* No service or library calls: only the OS timer can regain control.
   * An interruption between SUBS/BNE must also preserve condition flags. */
  subs r0,r0,#1
  bne 2b
  b 4f
3:
  mov r0,#11
  add r1,sp,#264
  svc #0
  cmp r0,#0
  bne 9f
  add r0,sp,#264
  cmp r1,r0
  bne 9f
  mov r0,#0
  mov r1,#1
4:
  cmp r0,#0
  bne 9f
  cmp r1,#1
  bne 9f
  cmp r2,#2
  bne 9f
  cmp r3,#3
  bne 9f
  cmp r4,#4
  bne 9f
  cmp r5,#5
  bne 9f
  cmp r6,#6
  bne 9f
  cmp r7,#7
  bne 9f
  cmp r8,#8
  bne 9f
  cmp r9,#9
  bne 9f
  cmp r10,#10
  bne 9f
  cmp r11,#11
  bne 9f
  cmp r12,#12
  bne 9f
  vmrs r0,fpscr
  cmp r0,#0x800000
  bne 9f
  mov r0,sp
  vstmia r0!,{d0-d15}
  vstmia r0,{d16-d31}
  mov r0,sp
  ldr r1,=0x12340000
  mov r2,#64
5:
  ldr r3,[r0],#4
  cmp r3,r1
  bne 9f
  add r1,r1,#1
  subs r2,r2,#1
  bne 5b
  add sp,sp,#328
  pop {r0,r1}
  vmsr fpscr,r0
  vpop {d8-d15}
  mov r0,#1
  pop {r4-r12,pc}
9:
  udf #0
.size foreground_registers,.-foreground_registers
.section .note.GNU-stack,"",%progbits

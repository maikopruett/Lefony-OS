/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
.syntax unified
.cpu cortex-a7
.fpu neon-vfpv4
.arm
.text
.global prime_app_enter
.type prime_app_enter,%function
prime_app_enter:
  push {r4-r12,lr}
  vpush {d0-d15}
  vpush {d16-d31}
  vmrs r4,fpscr
  mrs r5,cpsr
  push {r4,r5}
  cpsid i
  ldr r4,=prime_app_kernel_sp
  str sp,[r4]
  mov r4,r0
  mov r0,r1
  mov r1,r2
  mov r2,r3
  cps #0x1f
  ldr sp,=0x10300000
  mov lr,#0
  cps #0x13
  mov lr,r4
  mov r3,#0x50
  msr spsr_cxsf,r3
  mov r3,#0
  mov r4,#0
  vmsr fpscr,r4
  veor q0,q0,q0
  veor q1,q1,q1
  veor q2,q2,q2
  veor q3,q3,q3
  veor q4,q4,q4
  veor q5,q5,q5
  veor q6,q6,q6
  veor q7,q7,q7
  veor q8,q8,q8
  veor q9,q9,q9
  veor q10,q10,q10
  veor q11,q11,q11
  veor q12,q12,q12
  veor q13,q13,q13
  veor q14,q14,q14
  veor q15,q15,q15
  mov r5,#0
  mov r6,#0
  mov r7,#0
  mov r8,#0
  mov r9,#0
  mov r10,#0
  mov r11,#0
  mov r12,#0
  movs pc,lr
.global prime_app_resume
.type prime_app_resume,%function
prime_app_resume:
  /* The same kernel frame as prime_app_enter. Saved user state is privileged
   * storage: the app cannot choose its SPSR or exception-return address. */
  push {r4-r12,lr}
  vpush {d0-d15}
  vpush {d16-d31}
  vmrs r4,fpscr
  mrs r5,cpsr
  push {r4,r5}
  cpsid i
  ldr r4,=prime_app_kernel_sp
  str sp,[r4]
  ldr r0,=prime_app_user_context
  add r1,r0,#320
  ldmia r1,{sp,lr}^
  nop
  vldmia r0!,{d16-d31}
  vldmia r0!,{d0-d15}
  ldmia r0!,{r1,r2}
  msr spsr_cxsf,r1
  vmsr fpscr,r2
  ldmia r0,{r0-r12,pc}^
.global prime_app_suspend
prime_app_suspend:
  /* Both IRQ and SVC build: d16..31, d0..15, SPSR, FPSCR, r0..12, PC.
   * User SP/LR are banked and must be saved separately without writeback. */
  mov r0,sp
  ldr r1,=prime_app_user_context
  mov r2,#80
3:
  ldr r3,[r0],#4
  str r3,[r1],#4
  subs r2,r2,#1
  bne 3b
  stmia r1,{sp,lr}^
  nop
  add sp,sp,#320
  mov r0,#1
  b prime_app_leave
.global prime_app_leave
prime_app_leave:
  cpsid i
  cps #0x13
  ldr r1,=prime_app_kernel_sp
  ldr sp,[r1]
  pop {r4,r5}
  vmsr fpscr,r4
  vpop {d16-d31}
  vpop {d0-d15}
  msr cpsr_c,r5
  pop {r4-r12,pc}
.global exception_svc
exception_svc:
  cpsid i
  push {r0-r12,lr}
  mov r0,sp
  mrs r1,spsr
  vmrs r2,fpscr
  push {r1,r2}
  vpush {d0-d15}
  vpush {d16-d31}
  mov r2,#0
  vmsr fpscr,r2
  bl prime_app_svc
  cmp r0,#0
  bne 1f
  vpop {d16-d31}
  vpop {d0-d15}
  pop {r1,r2}
  msr spsr_cxsf,r1
  vmsr fpscr,r2
  pop {r0-r12,lr}
  movs pc,lr
1:
  cmp r0,#2
  beq prime_app_suspend
  cmn r0,#100
  beq 2f
  add sp,sp,#320
  b prime_app_leave
2:
  add sp,sp,#256
  pop {r3,r2}
  mov r1,sp
  ldr r2,[sp,#52]
  mov r0,#2
  b prime_g2_exception_report
.section .note.GNU-stack,"",%progbits

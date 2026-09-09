.syntax unified
.cpu cortex-a7
.fpu neon-vfpv4
.arm

.section .vectors, "ax"
.align 5
.global _vectors
_vectors:
  b _start
  b exception_undefined
  b exception_svc
  b exception_prefetch_abort
  b exception_data_abort
  b exception_reserved
  b exception_irq
  b exception_fiq

.section .text._start, "ax"
.global _start
.type _start, %function
_start:
  cpsid if

  /* U-Boot uses an identity-mapped handoff. Normalize the native payload to
   * MMU- and cache-off operation for the first hardware milestone. bootelf
   * flushes the loaded ELF before transferring control. */
  dsb
  mrc p15, 0, r0, c1, c0, 0
  bic r0, r0, #(1 << 0)       /* MMU */
  bic r0, r0, #(1 << 1)       /* alignment fault checking */
  bic r0, r0, #(1 << 2)       /* data cache */
  bic r0, r0, #(1 << 12)      /* instruction cache */
  orr r0, r0, #(1 << 22)      /* ARMv6+ unaligned access support */
  mcr p15, 0, r0, c1, c0, 0
  isb

  /* Give every exception mode a private stack before unmasking can ever be
   * considered. The reporter can therefore preserve state without trusting
   * U-Boot's banked stack pointers. */
  cps #0x1b
  ldr sp, =_stack_exception_und
  cps #0x17
  ldr sp, =_stack_exception_abt
  cps #0x12
  ldr sp, =_stack_exception_irq
  cps #0x11
  ldr sp, =_stack_exception_fiq
  cps #0x13
  ldr sp, =_stack_main_top
  ldr r0, =_vectors
  mcr p15, 0, r0, c12, c0, 0
  isb

  /* Permit CP10/CP11 and enable the VFP/NEON register file before any C++
   * code or static initialization can use floating point. */
  mrc p15, 0, r0, c1, c0, 2
  orr r0, r0, #(0xF << 20)
  mcr p15, 0, r0, c1, c0, 2
  isb
  mov r0, #(1 << 30)
  vmsr fpexc, r0

  b prime_g2_runtime_start

.macro fatal_exception name, kind
.global \name
\name:
  cpsid if
  sub sp, sp, #4
  stmdb sp!, {r0-r12}
  mov r1, sp
  mov r2, lr
  mrs r3, spsr
  mov r0, #\kind
  b prime_g2_exception_report
.endm

fatal_exception exception_undefined, 1
fatal_exception exception_svc, 2
fatal_exception exception_prefetch_abort, 3
fatal_exception exception_data_abort, 4
fatal_exception exception_reserved, 5
fatal_exception exception_fiq, 7

/* Acknowledge/dispatch/EOI is performed in C. r4-r11 are ABI-preserved by
 * the dispatcher; the interrupted volatile register set and SPSR live on the
 * dedicated IRQ stack. */
.global exception_irq
exception_irq:
  sub lr, lr, #4
  stmdb sp!, {r0-r3, r12, lr}
  mrs r0, spsr
  stmdb sp!, {r0}
  bl prime_g2_irq_dispatch
  ldmia sp!, {r0}
  msr spsr_cxsf, r0
  ldmia sp!, {r0-r3, r12, pc}^

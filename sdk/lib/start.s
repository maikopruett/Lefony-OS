/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 OR MIT */
/* Copyright (c) 2026 Maiko Pruett.
 * Additional MIT grant: see LICENSES/MIT.txt and LICENSE.md in the SDK. */
.syntax unified
.cpu cortex-a7
.fpu neon-vfpv4
.arm
.section .text.entry,"ax"
.global _start
.type _start,%function
.cfi_sections .debug_frame
_start:
  .cfi_startproc
  .cfi_def_cfa sp,0
  .cfi_undefined lr
  bl lefony_event
  mov r0, #0
  svc #0
  b .
  .cfi_endproc
.size _start,.-_start
.section .note.GNU-stack,"",%progbits

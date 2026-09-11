/* SPDX-License-Identifier: CC-BY-NC-SA-4.0 */
.syntax unified
.cpu cortex-a7
.fpu neon-vfpv4
.arm
.section .text.entry,"ax"
.global _start
_start:
  bl lefony_event
  mov r0, #0
  svc #0
  b .

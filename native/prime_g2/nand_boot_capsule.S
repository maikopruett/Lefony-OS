/*
 * ARM zImage-compatible loader for the HP Prime G2 NAND kernel slot.
 *
 * U-Boot loads this image at 0x80800000 and enters at its first word through
 * bootz.  The loader copies the embedded, flat native image to its linked
 * address (0x82000000) and enters its reset vector at +0x20.
 *
 * The native payload is appended at 0x1000 by the build script.  Keeping the
 * loader independent from the payload lets the script validate both inputs
 * and record their hashes before producing an installation artifact.
 */

.syntax unified
.arch armv7-a
.arm
.section .text.boot, "ax", %progbits
.global _start

.equ CAPSULE_BASE,       0x80800000
.equ PAYLOAD_OFFSET,     0x00001000
.equ PAYLOAD_SOURCE,     CAPSULE_BASE + PAYLOAD_OFFSET
.equ PAYLOAD_DESTINATION, 0x82000000
.equ NATIVE_ENTRY,       PAYLOAD_DESTINATION + 0x20
.equ CACHE_LINE_BYTES,   32

#ifndef NATIVE_PAYLOAD_BYTES
#error NATIVE_PAYLOAD_BYTES must be supplied by the capsule build
#endif
.equ PAYLOAD_SIZE,       NATIVE_PAYLOAD_BYTES

_start:
  b loader

  /* Linux ARM zImage header consumed by U-Boot bootz. */
  .org 0x24
  .word 0x016f2818
  .word 0x00000000
  .word capsule_end - _start

  .org 0x40
loader:
  cpsid if
  ldr r0, =PAYLOAD_SOURCE
  ldr r1, =PAYLOAD_DESTINATION
  ldr r2, =PAYLOAD_SIZE

copy_words:
  cmp r2, #0
  beq copy_complete
  ldr r3, [r0], #4
  str r3, [r1], #4
  subs r2, r2, #4
  bne copy_words

copy_complete:
  /* Unlike bootelf, this private zImage loader copied the native image with
   * ordinary CPU stores. On ARMv7 those bytes may exist only in dirty D-cache
   * lines, while I-cache may still contain instructions from an older native
   * image at the same destination. DSB alone does not make either cache
   * coherent. Clean/invalidate the copied range to PoC, then invalidate all
   * instruction and branch-predictor state before entering the payload. */
  ldr r0, =PAYLOAD_DESTINATION
  ldr r2, =PAYLOAD_SIZE
  add r1, r0, r2
  bic r0, r0, #(CACHE_LINE_BYTES - 1)

clean_payload_cache:
  mcr p15, 0, r0, c7, c14, 1  /* DCCIMVAC */
  add r0, r0, #CACHE_LINE_BYTES
  cmp r0, r1
  blo clean_payload_cache

  dsb sy
  mov r0, #0
  mcr p15, 0, r0, c7, c5, 0   /* ICIALLU */
  mcr p15, 0, r0, c7, c5, 6   /* BPIALL */
  dsb sy
  isb sy
  ldr pc, =NATIVE_ENTRY

  .ltorg
  .org PAYLOAD_OFFSET

capsule_end:

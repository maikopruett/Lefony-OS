/* SPDX-License-Identifier: GPL-3.0-or-later */
.syntax unified
.arm
.text
.global _start
_start:
    ldr r0, [sp]
    add r1, sp, #4
    bl helper_main
    mov r7, #1
    svc #0
1:  b 1b

/* Position-independent handoff copied by Linux to 0x80008000. Linux handles
 * shutdown, relocation, cache/MMU cleanup. Only the existing one-shot mailbox
 * is set here, causing the RAM U-Boot to expose its bounded SDP service. */
.section .rodata
.balign 4
.global handoff_start, handoff_end
handoff_start:
    ldr r3, mailbox_address
    ldr r4, mailbox_token
    str r4, [r3]
    dsb sy
    isb sy
    ldr r3, uboot_entry
    bx r3
mailbox_address: .word 0x020cc068
mailbox_token:   .word 0x3153464c
uboot_entry:    .word 0x87800000
handoff_end:
.balign 4
.global uboot_payload_start, uboot_payload_end
uboot_payload_start:
.incbin UBOOT_PAYLOAD
uboot_payload_end:
.section .note.GNU-stack,"",%progbits

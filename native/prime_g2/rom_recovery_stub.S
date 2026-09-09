/*
 * RAM-resident i.MX6ULL transition into USB serial-download protocol.
 *
 * This payload only requests the Boot ROM's USB boot mode and performs a warm
 * watchdog reset. It never initializes, erases, or programs NAND. A stock-OS
 * execution mechanism would still be required to launch it.
 */

    .syntax unified
    .cpu cortex-a7
    .arm

    .equ SRC_GPR9,          0x020d8040
    .equ SRC_GPR10,         0x020d8044
    .equ SRC_GPR10_BMODE,   0x10000000
    .equ ROM_USB_BOOT_CFG,  0x00000020
    .equ WDOG1_WCR,         0x020bc000
    .equ WDOG_WCR_WDE,      0x00000004

    .section .text.entry, "ax", %progbits
    .global _start
    .type _start, %function
_start:
    cpsid   if

    /* A direct-loader emulator restarts this entry after system reset. The
     * real chip runs Boot ROM instead, so park if that reset was already
     * requested rather than creating an emulator-only reset loop. */
    ldr     r0, =SRC_GPR10
    ldr     r1, [r0]
    tst     r1, #SRC_GPR10_BMODE
    bne     1f

    ldr     r0, =SRC_GPR9
    mov     r1, #ROM_USB_BOOT_CFG
    str     r1, [r0]

    ldr     r0, =SRC_GPR10
    ldr     r1, [r0]
    orr     r1, r1, #SRC_GPR10_BMODE
    str     r1, [r0]
    dsb     sy
    isb     sy

    /* WDE set with WDA/SRS clear requests an immediate warm reset. */
    ldr     r0, =WDOG1_WCR
    mov     r1, #WDOG_WCR_WDE
    strh    r1, [r0]

1:  wfi
    b       1b
    .size _start, . - _start

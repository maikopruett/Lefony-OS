/* Secure ARM-state diagnostic, loaded at 0x80010000. No NAND access. */
.syntax unified
.cpu cortex-a7
.arm
.text
.balign 32
vectors:
    b start
    b fault
    b fault
    b fault
    b fault
    b fault
    b irq
    b fault
start:
    cpsid if
    ldr r0, =0x80010000
    mcr p15, 0, r0, c12, c0, 0
    isb
    cps #0x12
    ldr sp, =0x80030000
    cps #0x13
    ldr sp, =0x80031000
    ldr r4, =0x80020000
    mov r0, #0
    str r0, [r4]
    str r0, [r4, #4]
    str r0, [r4, #8]
    str r0, [r4, #12]
    ldr r1, =0x00a01000
    mov r0, #1
    str r0, [r1]
    mov r0, #(1 << 20)
    str r0, [r1, #0x110]
    ldr r0, =0x01010101
    str r0, [r1, #0x894]
    ldr r1, =0x00a02000
    mov r0, #0xff
    str r0, [r1, #4]
    mov r0, #1
    str r0, [r1]
    ldr r1, =0x020c401c
    ldr r0, [r1]
    bic r0, r0, #0x7f
    orr r0, r0, #0x40
    str r0, [r1]
    ldr r1, =0x020c4080
    ldr r0, [r1]
    orr r0, r0, #(3 << 30)
    str r0, [r1]
    ldr r1, =0x020f8000
    mov r0, #8
    str r0, [r1]
    ldr r0, =23998
    str r0, [r1, #16]
    ldr r0, =6000
    str r0, [r1, #12]
    mov r0, #2
    str r0, [r1, #8]
    ldr r0, =0x20001
    str r0, [r1]
    mov r0, #1
    str r0, [r4]
    dsb sy
    cpsie i
wait_irq:
    ldr r0, [r4, #8]
    cmp r0, #1
    bne wait_irq
    mov r0, #1
    str r0, [r4, #12]
done:
    wfi
    b done
irq:
    push {r0-r3, r12, lr}
    ldr r1, =0x00a02000
    ldr r2, [r1, #12]
    ldr r3, =0x80020000
    ubfx r0, r2, #0, #10
    str r0, [r3, #4]
    ldr r12, =0x020f8000
    mov r0, #0
    str r0, [r12, #8]
    str r0, [r12]
    mov r0, #0x78
    str r0, [r12, #4]
    dsb sy
    str r2, [r1, #16]
    mov r0, #1
    str r0, [r3, #8]
    pop {r0-r3, r12, lr}
    subs pc, lr, #4
fault:
    ldr r0, =0x80020000
    mvn r1, #0
    str r1, [r0]
    b fault
    .ltorg

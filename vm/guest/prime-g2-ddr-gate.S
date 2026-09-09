/* Runs entirely from OCRAM. Deliberately exercises external DDR aborts. */
.syntax unified
.cpu cortex-a7
.arm
.text
.balign 32
    b start
    b fault
    b fault
    b fault
    b data_abort
    b fault
    b fault
    b fault
start:
    cpsid if
    ldr r0, =0x00910000
    mcr p15, 0, r0, c12, c0, 0
    isb
    ldr r4, =0x80001000
    ldr r5, =0x00920000
    mov r8, #0
    ldr r0, [r4]          /* Must abort; handler skips this instruction. */
    ldr r1, =0x021b0000
    ldr r0, =0x8000
    str r0, [r1, #0x1c]
    ldr r0, =0x83180000
    str r0, [r1]
    ldr r0, =0x02008032
    str r0, [r1, #0x1c]
    ldr r0, =0x00008033
    str r0, [r1, #0x1c]
    ldr r0, =0x00048031
    str r0, [r1, #0x1c]
    ldr r0, =0x15208030
    str r0, [r1, #0x1c]
    ldr r0, =0x04008040
    str r0, [r1, #0x1c]
    mov r0, #0
    str r0, [r1, #0x1c]
    dsb sy
    ldr r0, =0x1234abcd
    str r0, [r4]
    ldr r0, [r4]
    str r0, [r5, #12]
    ldr r0, =0x8000
    str r0, [r1, #0x1c]  /* Close access while reconfiguring. */
    dsb sy
    ldr r0, =0xbad00bad
    str r0, [r4]          /* Must abort without changing DDR. */
    mov r0, #0
    str r0, [r1, #0x1c]
    dsb sy
    ldr r0, [r4]
    str r0, [r5, #16]
    ldr r0, =0x00200001
    str r0, [r1, #0x404] /* Explicit software self-refresh request. */
    ldr r0, [r1, #0x404]
    str r0, [r5, #24]
    ldr r0, =0xbad00bad
    str r0, [r4]          /* Must abort and preserve retained DDR. */
    mov r0, #1
    str r0, [r1, #0x404] /* Exit self-refresh without reinitializing. */
    dsb sy
    ldr r0, [r4]
    str r0, [r5, #28]
    str r8, [r5, #20]
    mov r0, #1
    str r0, [r5]
done:
    wfi
    b done
data_abort:
    add r8, r8, #1
    mrc p15, 0, r9, c6, c0, 0
    mrc p15, 0, r10, c5, c0, 0
    str r9, [r5, #8]
    str r10, [r5, #4]
    subs pc, lr, #4       /* Skip the faulting access, return to SVC. */
fault:
    ldr r0, =0x00920000
    mvn r1, #0
    str r1, [r0]
    b fault
    .ltorg

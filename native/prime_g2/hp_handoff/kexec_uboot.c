/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Isolated ARM Linux recovery helper. Loads an embedded, host-verified U-Boot
 * into RAM through the standard kexec ABI. No MTD/file/register access here.
 * --load only stages it; --execute loads this same image then leaves Linux. */
typedef unsigned long word;
extern const unsigned char handoff_start[], handoff_end[];
extern const unsigned char uboot_payload_start[], uboot_payload_end[];
struct segment { const void *buffer; word bytes, destination, memory_bytes; };
_Static_assert(sizeof(struct segment) == 16, "ARM EABI kexec segment");

static long call4(long number, word a, word b, word c, word d)
{
    register word r0 asm("r0") = a, r1 asm("r1") = b;
    register word r2 asm("r2") = c, r3 asm("r3") = d;
    register word r7 asm("r7") = number;
    asm volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3), "r"(r7)
                 : "memory", "cc");
    return (long)r0;
}
static int equal(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}
static void message(const char *s)
{
    const char *end = s;
    while (*end) end++;
    call4(4, 1, (word)s, end - s, 0);
}
int helper_main(int argc, char **argv)
{
    word bytes = uboot_payload_end - uboot_payload_start;
    struct segment segments[2];
    long result;
    int execute;
    if (argc != 2) return 2;
    execute = equal(argv[1], "--execute");
    if (execute || equal(argv[1], "--load")) {
        if (bytes < 0x100 || bytes > 0xff000 ||
            handoff_end - handoff_start > 4096) return 2;
        segments[0].buffer = handoff_start;
        segments[0].bytes = handoff_end - handoff_start;
        segments[0].destination = 0x80008000;
        segments[0].memory_bytes = 4096;
        segments[1].buffer = uboot_payload_start;
        segments[1].bytes = bytes;
        segments[1].destination = 0x87800000;
        segments[1].memory_bytes = (bytes + 4095) & ~4095UL;
        /* Linux ARM __NR_kexec_load=347; KEXEC_ARCH_ARM=(40 << 16). */
        result = call4(347, 0x80008000, 2, (word)segments, 40UL << 16);
        if (!result) {
            message("RAM-KEXEC-LOADED\n");
            if (!execute) return 0;
            message("Executing embedded RAM recovery image\n");
            result = call4(88, 0xfee1dead, 0x28121969, 0x45584543, 0);
        }
    } else return 2;
    message("RAM-KEXEC-FAILED\n");
    return result < 0 && result >= -255 ? -result : 1;
}

/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Bounded RAM upload verification for the private Phase 6 recovery transport.
 * No NAND operation and no caller-selected address is accepted. */
#include <common.h>
#include <command.h>
#include <asm/cache.h>
#include <u-boot/sha256.h>

static int do_hpstagehash(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    u32 *report = (u32 *)0x83e02000;
    unsigned long length;
    char *end;
    (void)cmdtp; (void)flag;
    memset(report, 0, 64);
    if (argc != 2) return CMD_RET_FAILURE;
    length = simple_strtoul(argv[1], &end, 16);
    if (!*argv[1] || *end || !length || length > 64 * 2112)
        return CMD_RET_FAILURE;
    sha256_csum_wd((const unsigned char *)0x84000000, length,
                   (unsigned char *)(report + 2), CHUNKSZ_SHA256);
    report[1] = length;
    report[0] = 0x3648534c; /* LSH6; publish after complete bounded hash */
    flush_dcache_range(0x83e02000, 0x83e02040);
    return CMD_RET_SUCCESS;
}

U_BOOT_CMD(hpstagehash, 2, 0, do_hpstagehash,
           "read-only SHA-256 of staged RAM at 84000000",
           "<length-hex, 1..21000>; report at 83e02000");

static int do_hprecoverybudget(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    u32 *report = (u32 *)0x83e02040;
    unsigned long elapsed = get_timer(0);
    (void)cmdtp; (void)flag; (void)argv;
    memset(report, 0, 64);
    if (argc != 1) return CMD_RET_FAILURE;
    /* Conservative: SDP's 90-minute window starts after boot. Never extend
     * this deadline when the host reconnects or starts another transaction. */
    report[1] = 1;
    report[2] = elapsed < 5400000 ? 5400000 - elapsed : 0;
    report[3] = 5400000;
    report[0] = 0x36445242; /* BRD6 */
    flush_dcache_range(0x83e02040, 0x83e02080);
    return CMD_RET_SUCCESS;
}

U_BOOT_CMD(hprecoverybudget, 1, 0, do_hprecoverybudget,
           "read-only remaining RAM recovery budget at 83e02040", "");

/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Read-only geometry/bad-block report for an explicitly approved raw restore.
 * This command never erases, programs, marks bad, or changes NAND geometry. */
#include <common.h>
#include <command.h>
#include <nand.h>
#include <asm/cache.h>
#include <watchdog.h>
#include <u-boot/sha256.h>

static int do_hpnandinfo(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    u32 *report = (u32 *)0x83e00000;
    struct mtd_info *mtd = get_nand_dev_by_index(0);
    unsigned block;
    (void)cmdtp; (void)flag; (void)argv;
    memset(report, 0, 0x240);
    if (argc != 1 || !mtd || mtd->size != 0x20000000ULL ||
        mtd->erasesize != 131072 || mtd->writesize != 2048 || mtd->oobsize != 64)
        return CMD_RET_FAILURE;
    report[1] = 1;
    report[2] = mtd->size;
    report[3] = mtd->erasesize;
    report[4] = mtd->writesize;
    report[5] = mtd->oobsize;
    for (block = 0; block < 4096; block++) {
        int bad = nand_block_isbad(mtd, (loff_t)block * mtd->erasesize);
        if (bad < 0) return CMD_RET_FAILURE;
        if (bad) { report[8 + block / 32] |= 1U << (block % 32); report[6]++; }
        WATCHDOG_RESET();
    }
    report[0] = 0x314e5048; /* HPN1, published only after a complete scan */
    flush_dcache_range(0x83e00000, 0x83e00240);
    return CMD_RET_SUCCESS;
}

U_BOOT_CMD(hpnandinfo, 1, 0, do_hpnandinfo,
           "read-only Prime G2 NAND inventory into RAM 83e00000", "");

static int do_hpnandhash(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    struct mtd_info *mtd = get_nand_dev_by_index(0);
    u32 *report = (u32 *)0x83e01000;
    u8 *buffer = (u8 *)0x84000000, *hashes = (u8 *)0x83000000;
    unsigned first, count, block, page;
    char *end;
    (void)cmdtp; (void)flag;
    report[0] = 0;
    if (argc != 3 || !mtd || mtd->size != 0x20000000ULL ||
        mtd->erasesize != 131072 || mtd->writesize != 2048 || mtd->oobsize != 64)
        return CMD_RET_FAILURE;
    first = simple_strtoul(argv[1], &end, 16);
    if (!*argv[1] || *end || first >= 4096) return CMD_RET_FAILURE;
    count = simple_strtoul(argv[2], &end, 16);
    if (!*argv[2] || *end || !count || count > 128 || count > 4096 - first)
        return CMD_RET_FAILURE;
    for (block = 0; block < count; block++) {
        for (page = 0; page < 64; page++) {
            struct mtd_oob_ops ops = {
                .mode = MTD_OPS_RAW, .len = 2048, .ooblen = 64,
                .datbuf = buffer + page * 2112,
                .oobbuf = buffer + page * 2112 + 2048,
            };
            if (mtd_read_oob(mtd, (loff_t)(first + block) * 131072 + page * 2048, &ops) ||
                ops.retlen != 2048 || ops.oobretlen != 64)
                return CMD_RET_FAILURE;
            WATCHDOG_RESET();
        }
        sha256_csum_wd(buffer, 64 * 2112, hashes + block * 32, CHUNKSZ_SHA256);
    }
    report[1] = first; report[2] = count;
    report[0] = 0x31484e48; /* HNH1; all requested raw blocks were read */
    flush_dcache_range(0x83000000, 0x83000000 + ((count * 32 + 63) & ~63));
    flush_dcache_range(0x83e01000, 0x83e01040);
    return CMD_RET_SUCCESS;
}

U_BOOT_CMD(hpnandhash, 3, 0, do_hpnandhash,
           "read-only physical NAND block SHA-256 list at 83000000",
           "<first-block-hex> <count-hex, 1..80>; status at 83e01000");

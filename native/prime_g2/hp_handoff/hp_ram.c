/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Experimental RAM loader only. No NAND reader/writer or installation policy.
 * HP itself can write NAND: execute only in an isolated stock-HP test setup.
 * This command is excluded from the ordinary boot-menu build. */
#include <common.h>
#include <command.h>
#include <asm/cache.h>
#include <asm/system.h>
#include <asm/io.h>
#include <watchdog.h>
#include <nand.h>
#include "hardware.h"
#include "hp_confinement.h"
#ifdef LEFONY_DUAL_WAKE_MENU
#include "hp_wake_menu.h"
#endif
#include <u-boot/sha256.h>

#define HP_BASE 0x80000000UL
#define HP_STAGE 0x84000000UL
#define HP_ENTRY 0x80002000UL

static const struct hp_image {
    const char *name;
    unsigned int size;
    const char *sha256;
} hp_images[] = {
    {"os", 8192864, "25d3d2d27e45fc3ce7dc8c4a111b31f8aefc14c4b21e8d8ee4b32251e31c1b82"},
    {"updater", 358316, "9bfe04ec74eed51b606001caa3e5c0f701acd70eeb7d622f5a25616efdc0436e"},
};

static int verify_image(const struct hp_image *image, ulong base)
{
    unsigned char digest[SHA256_SUM_LEN];
    char hex[SHA256_SUM_LEN * 2 + 1];
    unsigned i;
    const u32 *ivt = (const u32 *)(base + 0x400);
    sha256_csum_wd((const unsigned char *)base, image->size, digest, CHUNKSZ_SHA256);
    for (i = 0; i < SHA256_SUM_LEN; i++)
        sprintf(hex + 2 * i, "%02x", digest[i]);
    return !strcmp(hex, image->sha256) && ivt[0] == 0x412000d1 &&
           ivt[1] == HP_ENTRY && ivt[5] == HP_BASE + 0x400;
}

int hp_staged_os_valid(void) { return verify_image(&hp_images[0], HP_STAGE); }

/* Phase 4 fixed-layout research only. The whole original image was verified
 * above; check every site and geometry before the first RAM modification. */
static int hp_apply_confinement(const struct hp_image *image)
{
    const struct hp_patch *patches = image == &hp_images[0] ? hp_patches_os : hp_patches_updater;
    unsigned count = image == &hp_images[0] ? ARRAY_SIZE(hp_patches_os) : ARRAY_SIZE(hp_patches_updater);
    struct mtd_info *nand = get_nand_dev_by_index(0);
    unsigned i;
    if (!nand || nand->size != 0x20000000ULL || nand->erasesize != 0x20000 ||
        nand->writesize != 2048 || nand->oobsize != 64)
        return -1;
    for (i = 0; i < count; i++)
        if (memcmp((void *)patches[i].address, patches[i].before, patches[i].length))
            return -1;
#ifdef LEFONY_DUAL_WAKE_MENU
    if (image == &hp_images[0])
        for (i = 0; i < ARRAY_SIZE(hp_wake_patches); i++)
            if (memcmp((void *)hp_wake_patches[i].address, hp_wake_patches[i].before,
                       hp_wake_patches[i].length)) return -1;
#endif
    for (i = 0; i < count; i++)
        memcpy((void *)patches[i].address, patches[i].after, patches[i].length);
#ifdef LEFONY_DUAL_WAKE_MENU
    if (image == &hp_images[0]) {
        for (i = 0; i < ARRAY_SIZE(hp_wake_patches); i++)
            memcpy((void *)hp_wake_patches[i].address, hp_wake_patches[i].after,
                   hp_wake_patches[i].length);
        puts("HP RAM: wake-menu-v1 applied\n");
    }
#endif
    puts("HP RAM: research-256 confinement applied; emulator qualification only\n");
    return 0;
}

/* HP reprograms LCDIF but inherits the panel's initialization. Stop U-Boot
 * scanout before releasing its buffers; leave the panel awake. Touch I/O is
 * synchronous and is no longer polled once this command transfers control. */
static int hp_quiesce(void)
{
    unsigned remaining = 50000;
    if (lf_hw_init()) return -1;
    writel(1, (void *)0x021c8008); /* LCDIF_CTRL_CLR RUN */
    while (readl((void *)0x021c8000) & 1) {
        if (!remaining--) return -1;
        WATCHDOG_RESET(); udelay(1);
    }
    clrbits_le32((void *)0x020a0004, 0xaaaa); /* release keypad columns */
    return 0;
}

static int do_hpram(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    const struct hp_image *image = NULL;
    char *end;
    unsigned long supplied;
    unsigned int i;
    (void)cmdtp;
    (void)flag;
    if ((argc != 3 && argc != 4) || (argc == 4 && strcmp(argv[3], "research-256")))
        return CMD_RET_USAGE;
    for (i = 0; i < ARRAY_SIZE(hp_images); i++)
        if (!strcmp(argv[1], hp_images[i].name))
            image = &hp_images[i];
    supplied = simple_strtoul(argv[2], &end, 16);
    if (!image || end == argv[2] || *end || supplied != image->size) {
        puts("HP RAM: unsupported component or exact length\n");
        return CMD_RET_FAILURE;
    }
    if (!verify_image(image, HP_BASE)) {
        puts("HP RAM: image verification failed\n");
        return CMD_RET_FAILURE;
    }
    /* The native/Lefony DDR setup ends CS0 below HP's 0x90000000 alias.
     * Only the separately built HP-compatible ROM DCD establishes this map.
     * Refuse before stopping the menu display; never rewrite live DDR here. */
    if (readl((void *)0x021b0000) != 0x85180000 ||
        readl((void *)0x021b0040) != 0x0000005f) {
        puts("HP RAM: incompatible DDR map; start with the HP research DCD\n");
        return CMD_RET_FAILURE;
    }
    if (argc == 4 && hp_apply_confinement(image)) {
        puts("HP RAM: confinement geometry/site verification failed\n");
        return CMD_RET_FAILURE;
    }
    printf("HP RAM: verified V15751 %s (%u bytes); original ARM entry\n",
           image->name, image->size);
    if (hp_quiesce()) {
        puts("HP RAM: display handoff failed\n");
        return CMD_RET_FAILURE;
    }
    cleanup_before_linux();
    /* The image is ARM at entry; do not use the Prime port's Thumb-only go.
     * Optional research patches affect RAM only; no persistent preference write. */
    asm volatile("dsb\n\tisb\n\tmov r0, #0\n\tmov r1, #0\n\t"
                 "mov r2, #0\n\tbx %0" : : "r" (HP_ENTRY) : "r0", "r1", "r2", "memory");
    hang();
    return CMD_RET_FAILURE;
}

int hp_boot_staged_os(int confined)
{
    char *args[] = {"hpram", "os", "7d0360", "research-256"};
    if (!hp_staged_os_valid()) return CMD_RET_FAILURE;
    memcpy((void *)HP_BASE, (const void *)HP_STAGE, hp_images[0].size);
    return do_hpram(NULL, 0, confined ? 4 : 3, args);
}

U_BOOT_CMD(hpram, 4, 0, do_hpram, "experimental exact-image HP RAM handoff",
           "os|updater <exact-hex-byte-count> [research-256] (image at 80000000)");

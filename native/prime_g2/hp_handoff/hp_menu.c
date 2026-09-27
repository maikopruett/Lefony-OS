/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Isolated stock-layout experiment; no Lefony NAND offsets or preference writes. */
#include <common.h>
#include <command.h>
#include <watchdog.h>
#include "hardware.h"

int hp_staged_os_valid(void);
int hp_boot_staged_os(int confined);

static int do_lfhpboot(cmd_tbl_t *cmdtp, int flag, int argc, char * const argv[])
{
    struct lf_menu menu;
    int drawn = -1;
    unsigned selected = 99;
    enum lf_notice notice = LF_NONE;
    (void)cmdtp; (void)flag;
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "research-256")))
        return CMD_RET_USAGE;
    if (lf_hw_init())
        return CMD_RET_FAILURE;
    lf_menu_init(&menu, get_timer(0), LF_HP, 0,
                 hp_staged_os_valid() ? (1u << LF_HP) : 0, NULL, NULL);
    menu.notice = LF_NONE;
    puts("HP RAM menu: ready; stock-layout experiment, priority saves disabled\n");
    for (;;) {
        u32 now = get_timer(0);
        WATCHDOG_RESET();
        lf_menu_step(&menu, now, lf_hw_keys());
        lf_hw_touch(&menu, now);
        if (drawn != menu.screen || selected != menu.selected || notice != menu.notice) {
            if (lf_hw_present(&menu, now))
                return CMD_RET_FAILURE;
            drawn = menu.screen; selected = menu.selected; notice = menu.notice;
            printf("HP RAM menu: screen=%u selected=%u\n", menu.screen, menu.selected);
        }
        if (menu.screen == LF_BOOT) {
            if (menu.boot_os == LF_HP)
                hp_boot_staged_os(argc == 2);
            lf_menu_boot_failed(&menu);
            drawn = -1;
        } else if (menu.screen == LF_RECOVERY) {
            run_command("sdp 0", 0);
            lf_menu_init(&menu, get_timer(0), LF_HP, 0,
                         hp_staged_os_valid() ? (1u << LF_HP) : 0, NULL, NULL);
            drawn = -1;
        }
        udelay(5000);
    }
}
U_BOOT_CMD(lfhpboot, 2, 0, do_lfhpboot,
           "isolated HP RAM menu", "[research-256] (emulator research only)");

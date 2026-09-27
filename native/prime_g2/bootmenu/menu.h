/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef LEFONY_BOOT_MENU_H
#define LEFONY_BOOT_MENU_H
#ifdef __UBOOT__
#include <common.h>
#else
#include <stdint.h>
#endif
#define LF_ENTER 1
#define LF_UP 2
#define LF_DOWN 4
#define LF_BACK 8
#define LF_LEFT 16
#define LF_RIGHT 32
#define LF_LEFONY 0
#define LF_HP 1
#define LF_COUNTDOWN_MS 3000
/* Boot-manager UI only. Neither OS is running while this state exists. */
enum lf_screen { LF_COUNTDOWN, LF_MENU, LF_PRIORITY, LF_RECOVERY_CONFIRM, LF_BOOT, LF_RECOVERY };
enum lf_notice { LF_NONE, LF_UNAVAILABLE, LF_SAVED, LF_SAVE_FAILED, LF_BAD_IMAGE, LF_BAD_PREF };
struct lf_menu {
    enum lf_screen screen;
    enum lf_notice notice;
    uint32_t start, changed_at, raw_keys, keys, touch_at;
    unsigned priority, selected, boot_os, available;
    int release_gate, touch_target, touch_id, touch_blocked;
    int (*save)(void *, unsigned);
    void *context;
};
void lf_menu_init(struct lf_menu *, uint32_t, unsigned, int, unsigned,
                  int (*)(void *, unsigned), void *);
void lf_menu_step(struct lf_menu *, uint32_t, unsigned);
void lf_menu_touch(struct lf_menu *, uint32_t, int, int, int, int);
void lf_menu_boot_failed(struct lf_menu *);
void lf_menu_draw(const struct lf_menu *, uint32_t, uint32_t *);
#endif

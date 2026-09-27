/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef LEFONY_BOOT_HARDWARE_H
#define LEFONY_BOOT_HARDWARE_H
#include "menu.h"
int lf_hw_init(void);
int lf_hw_present(const struct lf_menu *, uint32_t);
void lf_hw_shutdown(void);
unsigned lf_hw_keys(void);
void lf_hw_touch(struct lf_menu *, uint32_t);
#endif

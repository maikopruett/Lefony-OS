/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef LEFONY_BOOT_PREFERENCES_H
#define LEFONY_BOOT_PREFERENCES_H
#ifdef __UBOOT__
#include <common.h>
#else
#include <stdint.h>
#endif
#define LF_PREF_BYTES 64
#define LF_PREF_LAYOUT 1
struct lf_pref_io {
    void *ctx;
    int (*read)(void *, unsigned, uint8_t *);
    int (*replace)(void *, unsigned, const uint8_t *);
};
struct lf_preference { uint32_t generation; unsigned priority, slot; int valid; };
int lf_pref_load(const struct lf_pref_io *, struct lf_preference *);
int lf_pref_save(const struct lf_pref_io *, unsigned);
void lf_pref_encode(uint8_t *, uint32_t, unsigned);
#endif

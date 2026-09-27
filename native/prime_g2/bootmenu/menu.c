/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "menu.h"
#ifndef __UBOOT__
#include <string.h>
#endif
static int allowed(const struct lf_menu *m, unsigned os) { return os < 2 && (m->available & (1u << os)); }
static void open_menu(struct lf_menu *m) {
    m->screen = LF_MENU; m->selected = allowed(m, m->priority) ? m->priority : 0;
    m->release_gate = 1; m->touch_target = -1; m->touch_blocked = 1;
}
void lf_menu_init(struct lf_menu *m, uint32_t now, unsigned priority, int valid,
                  unsigned available, int (*save)(void *, unsigned), void *ctx) {
    memset(m, 0, sizeof(*m));
    m->priority = priority; m->available = available; m->start = now;
    m->save = save; m->context = ctx; m->touch_target = -1;
    m->screen = LF_COUNTDOWN;
    if (!valid || !allowed(m, priority)) { open_menu(m); m->notice = LF_BAD_PREF; }
}
static void activate(struct lf_menu *m) {
    unsigned s = m->selected;
    m->touch_target = -1; m->touch_blocked = 1;
    if (m->screen == LF_RECOVERY_CONFIRM) {
        if (s == 1) m->screen = LF_RECOVERY;
        else open_menu(m);
    } else if (m->screen == LF_PRIORITY) {
        if (!allowed(m, s)) { m->notice = LF_UNAVAILABLE; return; }
        if (m->save && !m->save(m->context, s)) {
            m->priority = s; open_menu(m); m->notice = LF_SAVED;
        } else m->notice = LF_SAVE_FAILED;
    } else if (m->screen == LF_MENU) {
        if (s < 2) {
            if (!allowed(m, s)) { m->notice = LF_UNAVAILABLE; return; }
            m->boot_os = s; m->screen = LF_BOOT;
        } else if (s == 2) {
            m->screen = LF_PRIORITY; m->selected = allowed(m, m->priority) ? m->priority : 0;
            m->notice = LF_NONE;
        } else {
            m->screen = LF_RECOVERY_CONFIRM; m->selected = 0; m->notice = LF_NONE;
        }
    }
}
void lf_menu_step(struct lf_menu *m, uint32_t now, unsigned keys) {
    unsigned pressed;
    if (keys != m->raw_keys) { m->raw_keys = keys; m->changed_at = now; }
    /* Enter wins even on the deadline scan; require a stable release before
     * any selection. This also makes a held startup key safe. */
    if (m->screen == LF_COUNTDOWN) {
        if (keys & LF_ENTER) { open_menu(m); return; }
        if ((uint32_t)(now - m->start) >= LF_COUNTDOWN_MS) {
            m->boot_os = m->priority; m->screen = LF_BOOT;
        }
        return;
    }
    if ((uint32_t)(now - m->changed_at) < 25) return;
    pressed = keys & ~m->keys; m->keys = keys;
    if (m->release_gate) { if (!keys) m->release_gate = 0; return; }
    if (m->screen == LF_BOOT || m->screen == LF_RECOVERY) return;
    if (pressed) { m->touch_target = -1; m->touch_blocked = 1; }
    if (pressed & LF_BACK) { open_menu(m); m->notice = LF_NONE; return; }
    if (pressed & (LF_UP | LF_DOWN | LF_LEFT | LF_RIGHT)) {
        unsigned count = m->screen == LF_MENU ? 4 : 2;
        /* All arrows navigate; activation always requires Enter or touch. */
        unsigned forward = pressed & (LF_DOWN | LF_RIGHT);
        unsigned backward = pressed & (LF_UP | LF_LEFT);
        if (!!forward == !!backward) return;
        if (forward && m->selected + 1 < count) m->selected++;
        else if (backward && m->selected > 0) m->selected--;
        m->notice = LF_NONE;
    } else if (pressed & LF_ENTER) activate(m);
    /* A long held key never repeats actions or passes into another screen. */
}
static int hit(const struct lf_menu *m, int x, int y) {
    if (x < 20 || x >= 300) return -1;
    if (m->screen == LF_RECOVERY_CONFIRM) {
        if (y >= 150 && y < 190) return x < 156 ? 0 : x >= 164 ? 1 : -1;
        return -1;
    }
    if (y >= 64 && y < 114) return 0;
    if (y >= 122 && y < 172) return 1;
    if (m->screen == LF_MENU && y >= 184 && y < 212)
        return x < 156 ? 2 : x >= 164 ? 3 : -1;
    return -1;
}
void lf_menu_touch(struct lf_menu *m, uint32_t now, int count, int id, int x, int y) {
    int target;
    if (m->screen == LF_COUNTDOWN || m->screen == LF_BOOT || m->screen == LF_RECOVERY) {
        m->touch_target = -1; m->touch_blocked = count != 0; return;
    }
    if (count < 0 || count > 1 || (count && (x < 0 || x >= 320 || y < 0 || y >= 240))) {
        m->touch_target = -1; m->touch_blocked = 1; return;
    }
    if (!count) {
        target = m->touch_target; m->touch_target = -1;
        if (!m->touch_blocked && !m->release_gate && target >= 0 &&
            (uint32_t)(now - m->touch_at) <= 2000) {
            m->selected = target; activate(m);
        }
        m->touch_blocked = 0; return;
    }
    if (m->touch_blocked || m->release_gate || m->keys) return;
    target = hit(m, x, y);
    if (m->touch_target < 0) {
        if (target < 0) { m->touch_blocked = 1; return; }
        m->touch_target = target; m->touch_id = id; m->touch_at = now;
    } else if (target != m->touch_target || id != m->touch_id || (uint32_t)(now - m->touch_at) > 2000) {
        m->touch_target = -1; m->touch_blocked = 1;
    }
}
void lf_menu_boot_failed(struct lf_menu *m) {
    m->available &= ~(1u << m->boot_os); open_menu(m); m->notice = LF_BAD_IMAGE;
}

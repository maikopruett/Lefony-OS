/*
 * HP Prime G2 board peripherals missing from upstream QEMU's i.MX6UL.
 *
 * Captured facts are documented in hardware/prime_g2.  Values not yet read
 * from the physical unit are explicitly marked PROVISIONAL below.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "qemu/osdep.h"
#include "qapi/error.h"
#include "qapi/visitor.h"
#include "hw/arm/prime_g2_peripherals.h"
#include "prime_g2_bch.h"
#include "hw/core/sysbus.h"
#include "hw/core/cpu.h"
#include "hw/i2c/i2c.h"
#include "hw/core/irq.h"
#include "hw/core/qdev-clock.h"
#include "system/dma.h"
#include "migration/vmstate.h"
#include "chardev/char-fe.h"
#include "system/address-spaces.h"
#include "system/runstate.h"
#include "system/tcg.h"
#include "exec/tb-flush.h"
#include "hw/core/qdev-properties.h"
#include "hw/core/qdev-properties-system.h"
#include "qemu/log.h"
#include "qemu/module.h"
#include "qemu/timer.h"
#include "qom/object.h"

/* MMDC DDR3 command lifecycle -------------------------------------------
 * Nominal CS0 initialization state, not PHY calibration/electrical timing.
 * Other registers remain explicit shadows pending register-level modeling.
 */
#define TYPE_PRIME_MMDC TYPE_PRIME_G2_MMDC
OBJECT_DECLARE_SIMPLE_TYPE(PrimeMMDCState, PRIME_MMDC)
struct PrimeMMDCState {
    SysBusDevice parent_obj;
    MemoryRegion regs_region;
    MemoryRegion ddr_gate;
    MemoryRegion *ddr_ram;
    uint32_t regs[0x1000 / 4];
    uint16_t mode[4];
    uint8_t mode_seen;
    bool zq_initial;
    bool preinitialized;
    bool supply_present;
};

static bool prime_mmdc_ready(PrimeMMDCState *s)
{
    return s->supply_present && (s->regs[0] & BIT(31)) && !(s->regs[0x18 / 4] & BIT(3)) &&
           !(s->regs[0x1c / 4] & BIT(15)) && s->mode_seen == 15 &&
           s->zq_initial;
}

static void prime_mmdc_update_gate(PrimeMMDCState *s)
{
    memory_region_set_enabled(&s->ddr_gate, !prime_mmdc_ready(s) ||
                              (s->regs[0x404 / 4] & BIT(21)));
}

void prime_g2_mmdc_map_ddr_gate(MemoryRegion *ram)
{
    PrimeMMDCState *s = PRIME_MMDC(object_resolve_path("/machine/soc/mmdc", NULL));
    s->ddr_ram = ram;
    /* Cover the fitted bank and its board alias with one higher-priority
     * responder. CPU and DMA address spaces see the same access decision. */
    memory_region_add_subregion_overlap(get_system_memory(), 0x80000000,
                                       &s->ddr_gate, 1);
}

static MemTxResult prime_mmdc_blocked_read(void *opaque, hwaddr address,
                                          uint64_t *value, unsigned size,
                                          MemTxAttrs attrs)
{
    *value = 0;
    return MEMTX_ERROR;
}

static MemTxResult prime_mmdc_blocked_write(void *opaque, hwaddr address,
                                           uint64_t value, unsigned size,
                                           MemTxAttrs attrs)
{
    return MEMTX_ERROR;
}

static const MemoryRegionOps prime_mmdc_gate_ops = {
    .read_with_attrs = prime_mmdc_blocked_read,
    .write_with_attrs = prime_mmdc_blocked_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 1, .max_access_size = 8, .unaligned = true },
};

bool prime_g2_mmdc_initialized(void)
{
    Object *obj = object_resolve_path("/machine/soc/mmdc", NULL);
    return obj && prime_mmdc_ready(PRIME_MMDC(obj)) &&
           !(PRIME_MMDC(obj)->regs[0x404 / 4] & BIT(21));
}

static bool prime_mmdc_get_initialized(Object *obj, Error **errp)
{
    return prime_mmdc_ready(PRIME_MMDC(obj));
}

static bool prime_mmdc_get_supply(Object *obj, Error **errp)
{
    return PRIME_MMDC(obj)->supply_present;
}

static void prime_mmdc_set_supply(Object *obj, bool present, Error **errp)
{
    PrimeMMDCState *s = PRIME_MMDC(obj);
    /* Explicit rail fault injection, not a guessed PF1550/USB wiring rule.
     * Pausing also makes direct backing-store invalidation and TB flushing
     * safe. A future board power sequencer needs an asynchronous path. */
    if (runstate_is_running() || !s->ddr_ram) {
        error_setg(errp, "pause the Prime VM before changing the DDR supply");
        return;
    }
    if (present == s->supply_present) {
        return;
    }
    s->supply_present = present;
    if (!present) {
        s->mode_seen = 0;
        s->zq_initial = false;
        memset(s->mode, 0, sizeof(s->mode));
        /* Deterministic invalid contents, not a silicon power-up pattern.
         * Clearing the actual RAM also covers its alias and migration. */
        uint64_t bytes = memory_region_size(s->ddr_ram);
        memset(memory_region_get_ram_ptr(s->ddr_ram), 0, bytes);
        memory_region_set_dirty(s->ddr_ram, 0, bytes);
        if (tcg_enabled()) {
            tb_flush__exclusive_or_serial();
        }
    }
    prime_mmdc_update_gate(s);
}

static uint64_t prime_mmdc_read(void *opaque, hwaddr offset, unsigned size)
{
    PrimeMMDCState *s = opaque;
    if (offset == 0x404) {
        /* Software DVFS/self-refresh handshake used by suspend-imx6.S.
         * No clock-dependent entry/exit delay or CCM handshake yet. */
        uint32_t value = s->regs[offset / 4] & ~BIT(25);
        if ((value & BIT(21)) && prime_mmdc_ready(s)) {
            value |= BIT(25);
        }
        return value;
    }
    return s->regs[offset / 4];
}

static void prime_mmdc_write(void *opaque, hwaddr offset, uint64_t value,
                             unsigned size)
{
    PrimeMMDCState *s = opaque;
    if (offset == 0x1c) {
        unsigned command = (value >> 4) & 7;
        unsigned bank = value & 7;
        bool request = value & BIT(15);
        /* CON_ACK is controller-owned, never set by a software write.
         * Acknowledgement is synchronous here; bus-drain latency is open. */
        s->regs[offset / 4] = (value & ~BIT(14)) | (request ? BIT(14) : 0);
        if (s->supply_present && !(s->regs[0x404 / 4] & BIT(21)) &&
            request && (s->regs[0] & BIT(31)) && !(value & BIT(3)) &&
            !(s->regs[0x18 / 4] & BIT(3))) {
            if (command == 3 && bank < 4) {
                /* DDR3 startup: MR2 -> MR3 -> MR1 (DLL enabled) ->
                 * MR0 (DLL reset), then ZQCL. Do not qualify a mere set
                 * of unordered register writes. Once initialized, normal
                 * MRS updates need not repeat the cold-start order. */
                static const uint8_t preceding[4] = { 14, 12, 0, 4 };
                s->mode[bank] = value >> 16;
                if (s->mode_seen != 15) {
                    if (s->mode_seen == preceding[bank] &&
                        (bank != 1 || !(s->mode[1] & BIT(0))) &&
                        (bank != 0 || (s->mode[0] & BIT(8)))) {
                        s->mode_seen |= BIT(bank);
                    } else {
                        s->mode_seen = bank == 2 ? BIT(2) : 0;
                        s->zq_initial = false;
                        qemu_log_mask(LOG_GUEST_ERROR,
                            "prime-mmdc: invalid DDR3 startup MRS 0x%08" PRIx64 "\n", value);
                    }
                }
                if (bank == 0 && (s->mode[0] & BIT(8))) {
                    s->zq_initial = false;
                }
            } else if (command == 4 && bank == 0 &&
                       (value & BIT(26)) && s->mode_seen == 15) {
                s->zq_initial = true;
            } else if (command) {
                qemu_log_mask(LOG_UNIMP, "prime-mmdc: unsupported/incomplete command 0x%08" PRIx64 "\n", value);
            }
        }
        prime_mmdc_update_gate(s);
        return;
    }
    if (offset == 0x404) {
        /* DVACK is device-owned, not a writable completion flag. Other
         * MAPSR fields remain shadows; automatic low power is not modeled. */
        s->regs[offset / 4] = value & ~BIT(25);
        prime_mmdc_update_gate(s);
        return;
    }
    s->regs[offset / 4] = value;
    prime_mmdc_update_gate(s);
    qemu_log_mask(LOG_UNIMP, "prime-mmdc: shadow register 0x%03" HWADDR_PRIx " = 0x%08" PRIx64 "\n", offset, value);
}

static const MemoryRegionOps prime_mmdc_ops = {
    .read = prime_mmdc_read, .write = prime_mmdc_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 4, .max_access_size = 4, .unaligned = false },
};

static void prime_mmdc_reset(DeviceState *dev)
{
    PrimeMMDCState *s = PRIME_MMDC(dev);
    /* Cold model reset. Physical warm-reset/PMIC retention is not inferred. */
    memset(s->regs, 0, sizeof(s->regs));
    memset(s->mode, 0, sizeof(s->mode));
    s->mode_seen = 0;
    s->zq_initial = false;
    if (s->preinitialized && s->supply_present) {
        /* Explicit debugger/direct-load fixture, never the default cold boot.
         * This supplies nominal command state, not a claim of PHY training. */
        s->regs[0] = 0x83180000;
        s->mode_seen = 15;
        s->zq_initial = true;
    }
    prime_mmdc_update_gate(s);
}

static void prime_mmdc_init(Object *obj)
{
    PrimeMMDCState *s = PRIME_MMDC(obj);
    s->supply_present = true;
    memory_region_init_io(&s->regs_region, obj, &prime_mmdc_ops, s,
                         TYPE_PRIME_G2_MMDC, sizeof(s->regs));
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->regs_region);
    memory_region_init_io(&s->ddr_gate, obj, &prime_mmdc_gate_ops, s,
                         "prime-g2-unavailable-ddr", 0x20000000);
    object_property_add_bool(obj, "initialized", prime_mmdc_get_initialized, NULL);
    object_property_add_bool(obj, "ddr-supply-present", prime_mmdc_get_supply,
                             prime_mmdc_set_supply);
}

static int prime_mmdc_post_load(void *opaque, int version_id)
{
    PrimeMMDCState *s = opaque;
    if (version_id < 2) {
        s->supply_present = true;
    }
    prime_mmdc_update_gate(opaque);
    return 0;
}

static const VMStateDescription prime_mmdc_vmstate = {
    .name = TYPE_PRIME_G2_MMDC, .version_id = 2, .minimum_version_id = 1,
    .post_load = prime_mmdc_post_load,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT32_ARRAY(regs, PrimeMMDCState, 0x1000 / 4),
        VMSTATE_UINT16_ARRAY(mode, PrimeMMDCState, 4),
        VMSTATE_UINT8(mode_seen, PrimeMMDCState),
        VMSTATE_BOOL(zq_initial, PrimeMMDCState),
        VMSTATE_BOOL_V(supply_present, PrimeMMDCState, 2), VMSTATE_END_OF_LIST()
    }
};

static void prime_mmdc_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);
    static const Property properties[] = {
        DEFINE_PROP_BOOL("preinitialized", PrimeMMDCState, preinitialized, false),
    };
    device_class_set_props(dc, properties);
    dc->vmsd = &prime_mmdc_vmstate;
    device_class_set_legacy_reset(dc, prime_mmdc_reset);
}

/* i.MX KPP --------------------------------------------------------------- */
#define TYPE_PRIME_KPP TYPE_PRIME_G2_KPP
OBJECT_DECLARE_SIMPLE_TYPE(PrimeKPPState, PRIME_KPP)
struct PrimeKPPState {
    SysBusDevice parent_obj;
    MemoryRegion iomem;
    qemu_irq irq;
    uint16_t kpcr, kpsr, kddr, kpdr;
    uint64_t pressed;
};

#define KPSR_KPKD 0x0001
#define KPSR_KPKR 0x0002
#define KPSR_KDIE 0x0100
#define KPSR_KRIE 0x0200
#define KPSR_KDSC 0x0400
#define KPSR_KRSS 0x0800

static void prime_kpp_irq(PrimeKPPState *s)
{
    qemu_set_irq(s->irq, ((s->kpsr & KPSR_KDIE) && (s->kpsr & KPSR_KPKD)) ||
                         ((s->kpsr & KPSR_KRIE) && (s->kpsr & KPSR_KPKR)));
}

static uint16_t prime_kpp_rows(PrimeKPPState *s)
{
    uint8_t rows = 0xff;
    bool reached_col[8] = { false };
    bool reached_row[8] = { false };
    bool changed;
    unsigned col, row;
    /* Closed keys form a bipartite electrical graph. Starting at every
     * actively driven-low column and finding its connected component models
     * both ordinary row sense and the ghost keys produced by an un-dioded
     * rectangle. */
    for (col = 0; col < 8; col++) {
        if ((s->kddr & (1u << (col + 8))) &&
            (s->kpcr & (1u << (col + 8))) &&
            !(s->kpdr & (1u << (col + 8)))) {
            reached_col[col] = true;
        }
    }
    do {
        changed = false;
        for (col = 0; col < 8; col++) {
            for (row = 0; row < 8; row++) {
                if (s->pressed & (1ULL << (row * 8 + col))) {
                    if (reached_col[col] && !reached_row[row]) {
                        reached_row[row] = true;
                        changed = true;
                    }
                    if (reached_row[row] && !reached_col[col]) {
                        reached_col[col] = true;
                        changed = true;
                    }
                }
            }
        }
    } while (changed);
    for (row = 0; row < 8; row++) {
        if (reached_row[row]) {
            rows &= ~(1u << row);
        }
    }
    return (s->kpdr & 0xff00) | rows;
}

static uint64_t prime_kpp_read(void *opaque, hwaddr off, unsigned size)
{
    PrimeKPPState *s = opaque;
    switch (off) {
    case 0x0: return s->kpcr;
    case 0x2: return s->kpsr;
    case 0x4: return s->kddr;
    case 0x6: return prime_kpp_rows(s);
    case 0x8: return s->pressed & 0xffff;       /* VM diagnostic ingress */
    case 0xa: return (s->pressed >> 16) & 0xffff;
    case 0xc: return (s->pressed >> 32) & 0xffff;
    case 0xe: return (s->pressed >> 48) & 0xffff;
    default: return 0;
    }
}

static void prime_kpp_write(void *opaque, hwaddr off, uint64_t value,
                            unsigned size)
{
    PrimeKPPState *s = opaque;
    switch (off) {
    case 0x0: s->kpcr = value; break;
    case 0x2:
        /* Status bits are write-one-to-clear; enable/sync bits are writable. */
        s->kpsr = (s->kpsr & ~((uint16_t)value & (KPSR_KPKD | KPSR_KPKR))) |
                  ((uint16_t)value & (KPSR_KDIE | KPSR_KRIE | KPSR_KDSC | KPSR_KRSS));
        break;
    case 0x4: s->kddr = value; break;
    case 0x6: s->kpdr = value; break;
    case 0x8: {
        /* Emulator-only packed event: bit15=down, bits10:8=row, bits2:0=col. */
        unsigned row = (value >> 8) & 7, col = value & 7;
        uint64_t mask = 1ULL << (row * 8 + col);
        bool down = value & 0x8000;
        if (down) {
            s->pressed |= mask;
            s->kpsr |= KPSR_KPKD;
        } else {
            s->pressed &= ~mask;
            s->kpsr |= KPSR_KPKR;
        }
        prime_kpp_irq(s);
        break;
    }
    default: break;
    }
    prime_kpp_irq(s);
}

static const MemoryRegionOps prime_kpp_ops = {
    .read = prime_kpp_read, .write = prime_kpp_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 2, .max_access_size = 2, .unaligned = false },
};

static void prime_kpp_reset(DeviceState *dev)
{
    PrimeKPPState *s = PRIME_KPP(dev);
    s->kpcr = 0; s->kpsr = 0; s->kddr = 0; s->kpdr = 0xffff; s->pressed = 0;
    prime_kpp_irq(s);
}
static void prime_kpp_realize(DeviceState *dev, Error **errp)
{
    PrimeKPPState *s = PRIME_KPP(dev);
    memory_region_init_io(&s->iomem, OBJECT(dev), &prime_kpp_ops, s,
                          TYPE_PRIME_KPP, 0x10);
    sysbus_init_mmio(SYS_BUS_DEVICE(dev), &s->iomem);
    sysbus_init_irq(SYS_BUS_DEVICE(dev), &s->irq);
}
static const VMStateDescription prime_kpp_vmstate = {
    .name = TYPE_PRIME_KPP, .version_id = 1, .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT16(kpcr, PrimeKPPState), VMSTATE_UINT16(kpsr, PrimeKPPState),
        VMSTATE_UINT16(kddr, PrimeKPPState), VMSTATE_UINT16(kpdr, PrimeKPPState),
        VMSTATE_UINT64(pressed, PrimeKPPState), VMSTATE_END_OF_LIST()
    },
};
static void prime_kpp_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);
    dc->realize = prime_kpp_realize; dc->vmsd = &prime_kpp_vmstate;
    device_class_set_legacy_reset(dc, prime_kpp_reset);
}

/* i.MX6UL ChipIdea USBOTG1 device mode -----------------------------------
 * Upstream QEMU implements only this controller's EHCI host personality.
 * The Prime is a USB peripheral, so this compact device-mode model provides
 * the EP0 queue-head/dTD behavior used by the native diagnostic/recovery
 * driver.  A line-oriented chardev represents transactions on the cable;
 * it is deliberately below the guest driver rather than a guest test hook.
 */
#define TYPE_PRIME_USBOTG TYPE_PRIME_G2_USBOTG
OBJECT_DECLARE_SIMPLE_TYPE(PrimeUSBOTGState, PRIME_USBOTG)

#define USB_USBCMD          0x140
#define USB_USBSTS          0x144
#define USB_USBINTR         0x148
#define USB_DEVICEADDR      0x154
#define USB_ENDPTLISTADDR   0x158
#define USB_BURSTSIZE       0x160
#define USB_PORTSC1         0x184
#define USB_OTGSC           0x1a4
#define USB_USBMODE         0x1a8
#define USB_SETUPSTAT       0x1ac
#define USB_ENDPTPRIME      0x1b0
#define USB_ENDPTFLUSH      0x1b4
#define USB_ENDPTSTAT       0x1b8
#define USB_ENDPTCOMPLETE   0x1bc
#define USB_ENDPTCTRL0      0x1c0
#define USB_EP0_RX_STALL    BIT(0)
#define USB_EP0_TX_STALL    BIT(16)
#define USB_STS_USBINT      BIT(0)
#define USB_STS_ERROR       BIT(1)
#define USB_STS_PORTCHANGE  BIT(2)
#define USB_STS_RESET       BIT(6)
#define USB_STS_SUSPEND     BIT(8)
#define USB_EP0_OUT         BIT(0)
#define USB_EP0_IN          BIT(16)
#define USB_TD_ACTIVE       BIT(7)
#define USB_TD_TERMINATE    BIT(0)

struct PrimeUSBOTGState {
    SysBusDevice parent_obj;
    MemoryRegion iomem;
    qemu_irq irq;
    qemu_irq cable[2];
    MemoryRegion usbnc_iomem;
    uint32_t usbnc_ctrl[2], usbnc_phy[2];
    bool usbnc_wake[2];
    CharFrontend chr;
    uint32_t usbcmd, usbsts, usbintr, deviceaddr, endptlistaddr;
    uint32_t burstsize, portsc1, otgsc, usbmode, setupstat;
    uint32_t endptprime, endptstat, endptcomplete, endptctrl0, endptctrl1;
    bool connected;
    bool suspended;
    bool rom_downloader;
    uint8_t rom_control[512];
    uint16_t rom_control_len;
    uint16_t rom_control_offset;
    bool rom_status_in;
    uint8_t sdp_report[1025];
    uint16_t sdp_report_len, sdp_report_offset;
    uint8_t sdp_report_id, sdp_phase;
    uint16_t sdp_command;
    uint32_t sdp_address, sdp_remaining, sdp_status, sdp_entry;
    uint8_t sdp_dcd[1768]; /* i.MX image v2: 220 register pairs + headers */
    uint16_t sdp_dcd_length, sdp_dcd_offset;
    bool sdp_skip_dcd;
    uint8_t input[65536];
    uint16_t input_len;
};

/* Public, non-proprietary USB identity used by the i.MX6ULL Boot ROM's SDP
 * device.  The ROM transport itself is intentionally kept separate from the
 * guest-owned ChipIdea queue heads: after a software boot override and warm
 * watchdog reset, no HP or Lefony code is running the USB controller. */
static const uint8_t prime_usb_rom_device_descriptor[] = {
    18, 1, 0x00, 0x02, 0, 0, 0, 64,
    0xa2, 0x15, 0x80, 0x00, 0x01, 0x00, 1, 2, 0, 1,
};

static const uint8_t prime_usb_rom_configuration_descriptor[] = {
    9, 2, 34, 0, 1, 1, 4, 0xc0, 5,
    9, 4, 0, 0, 1, 3, 0, 0, 5,
    9, 0x21, 0x10, 0x01, 0, 1, 0x22, 76, 0,
    7, 5, 0x81, 3, 64, 0, 1,
};

static const uint8_t prime_usb_rom_report_descriptor[] = {
    /* SDP report layout from U-Boot drivers/usb/gadget/f_sdp.c, whose
     * descriptor is synchronized with the i.MX SoC implementation. */
    0x06, 0x00, 0xff, 0x09, 0x01, 0xa1, 0x01,
    0x85, 1, 0x19, 1, 0x29, 1, 0x15, 0, 0x26, 0xff, 0,
    0x75, 8, 0x95, 16, 0x91, 2,
    0x85, 2, 0x19, 1, 0x29, 1, 0x15, 0, 0x26, 0xff, 0,
    0x75, 128, 0x95, 64, 0x91, 2,
    0x85, 3, 0x19, 1, 0x29, 1, 0x15, 0, 0x26, 0xff, 0,
    0x75, 8, 0x95, 4, 0x81, 2,
    0x85, 4, 0x19, 1, 0x29, 1, 0x15, 0, 0x26, 0xff, 0,
    0x75, 8, 0x95, 64, 0x81, 2, 0xc0,
};

static void prime_usb_irq(PrimeUSBOTGState *s)
{
    qemu_set_irq(s->irq, (s->usbsts & s->usbintr) != 0 ||
                        (s->usbnc_wake[0] && (s->usbnc_ctrl[0] & BIT(10))));
}

static void prime_usbnc_bvalid_change(PrimeUSBOTGState *s)
{
    /* The local USB transport provides digital cable/BVALID transitions.
     * Other analog source thresholds are not inferred from this signal. */
    if ((s->usbnc_ctrl[0] & (BIT(10) | BIT(17))) == (BIT(10) | BIT(17)) &&
        ((s->usbnc_phy[0] >> 8) & 3) == 2) {
        s->usbnc_wake[0] = true;
    }
    prime_usb_irq(s);
}

static uint64_t prime_usbnc_read(void *opaque, hwaddr off, unsigned size)
{
    PrimeUSBOTGState *s = opaque;
    if (off == 0 || off == 4) {
        unsigned port = off / 4;
        return s->usbnc_ctrl[port] | (s->usbnc_wake[port] ? BIT(31) : 0);
    }
    if (off == 0x18 || off == 0x1c) return s->usbnc_phy[(off - 0x18) / 4];
    qemu_log_mask(LOG_UNIMP, "prime-g2-usbnc: unsupported read at 0x%" HWADDR_PRIx "\n", off);
    return 0;
}

static void prime_usbnc_write(void *opaque, hwaddr off, uint64_t value, unsigned size)
{
    PrimeUSBOTGState *s = opaque;
    if (off == 0 || off == 4) {
        unsigned port = off / 4;
        const uint32_t mask = BIT(1) | BIT(7) | BIT(8) | BIT(9) | BIT(10) |
                              BIT(13) | BIT(16) | BIT(17) | BIT(29);
        s->usbnc_ctrl[port] = value & mask;
        /* WIR is a hardware latch, acknowledged by disabling WIE. */
        if (!(value & BIT(10))) s->usbnc_wake[port] = false;
        prime_usb_irq(s);
        return;
    }
    if (off == 0x18 || off == 0x1c) {
        s->usbnc_phy[(off - 0x18) / 4] = value & (3u << 8);
        return;
    }
    qemu_log_mask(LOG_UNIMP, "prime-g2-usbnc: unsupported write at 0x%" HWADDR_PRIx "\n", off);
}

static const MemoryRegionOps prime_usbnc_ops = {
    .read = prime_usbnc_read, .write = prime_usbnc_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 4, .max_access_size = 4, .unaligned = false },
};

static bool prime_usb_dma_read(hwaddr address, void *buffer, size_t length)
{
    return dma_memory_read(&address_space_memory, address, buffer, length,
                           MEMTXATTRS_UNSPECIFIED) == MEMTX_OK;
}

static bool prime_usb_dma_write(hwaddr address, const void *buffer,
                                size_t length)
{
    return dma_memory_write(&address_space_memory, address, buffer, length,
                            MEMTXATTRS_UNSPECIFIED) == MEMTX_OK;
}

static bool prime_usb_read32(hwaddr address, uint32_t *value)
{
    uint8_t bytes[4];
    if (!prime_usb_dma_read(address, bytes, sizeof(bytes))) {
        return false;
    }
    *value = ldl_le_p(bytes);
    return true;
}

static bool prime_usb_write32(hwaddr address, uint32_t value)
{
    uint8_t bytes[4];
    stl_le_p(bytes, value);
    return prime_usb_dma_write(address, bytes, sizeof(bytes));
}

static void prime_usb_signal(PrimeUSBOTGState *s, uint32_t status)
{
    s->usbsts |= status;
    prime_usb_irq(s);
}

static void prime_usb_reply(PrimeUSBOTGState *s, const char *reply)
{
    if (qemu_chr_fe_backend_connected(&s->chr)) {
        qemu_chr_fe_write_all(&s->chr, (const uint8_t *)reply, strlen(reply));
        qemu_chr_fe_write_all(&s->chr, (const uint8_t *)"\n", 1);
    }
}

static uint32_t prime_usb_endpoint_bit(unsigned endpoint, bool in)
{
    return BIT(endpoint + (in ? 16 : 0));
}

static bool prime_usb_td(PrimeUSBOTGState *s, unsigned endpoint, bool in,
                         hwaddr *td,
                         uint32_t *token, uint32_t buffers[5])
{
    hwaddr qh = (s->endptlistaddr & ~0x7ffu) +
                (endpoint * 2 + (in ? 1 : 0)) * 64;
    uint32_t next;
    if (!prime_usb_read32(qh + 8, &next) || (next & USB_TD_TERMINATE)) {
        return false;
    }
    *td = next & ~0x1fu;
    if (!prime_usb_read32(*td + 4, token)) {
        return false;
    }
    for (unsigned i = 0; i < 5; i++) {
        if (!prime_usb_read32(*td + 8 + i * 4, &buffers[i])) {
            return false;
        }
    }
    return (*token & USB_TD_ACTIVE) != 0;
}

static bool prime_usb_transfer_memory(uint32_t buffers[5], uint8_t *data,
                                      size_t length, bool to_guest)
{
    size_t done = 0;
    for (unsigned page = 0; page < 5 && done < length; page++) {
        hwaddr address = buffers[page];
        size_t room = 0x1000 - (address & 0xfff);
        size_t amount = MIN(room, length - done);
        bool ok = to_guest ? prime_usb_dma_write(address, data + done, amount) :
                             prime_usb_dma_read(address, data + done, amount);
        if (!ok) {
            return false;
        }
        done += amount;
    }
    return done == length;
}

static void prime_usb_complete(PrimeUSBOTGState *s, unsigned endpoint,
                               bool in, hwaddr td,
                               uint32_t token, uint16_t remaining)
{
    uint32_t endpoint_bit = prime_usb_endpoint_bit(endpoint, in);
    hwaddr qh = (s->endptlistaddr & ~0x7ffu) +
                (endpoint * 2 + (in ? 1 : 0)) * 64;
    uint32_t next = USB_TD_TERMINATE;
    token &= ~(0x7fffu << 16);
    token |= (uint32_t)remaining << 16;
    token &= ~USB_TD_ACTIVE;
    /* ChipIdea writes the completed dTD state into both the descriptor and
     * the queue-head overlay, advancing the overlay to dTD.next.  Stock HP
     * firmware inspects that overlay before dispatching its endpoint callback;
     * updating only the dTD acknowledges the IRQ but strands the receiver. */
    if (!prime_usb_read32(td, &next) ||
        !prime_usb_write32(td + 4, token) ||
        !prime_usb_write32(qh + 4, td) ||
        !prime_usb_write32(qh + 8, next) ||
        !prime_usb_write32(qh + 12, token)) {
        prime_usb_signal(s, USB_STS_ERROR);
        return;
    }
    s->endptprime &= ~endpoint_bit;
    if (endpoint && !(next & USB_TD_TERMINATE)) {
        s->endptstat |= endpoint_bit;
    } else {
        s->endptstat &= ~endpoint_bit;
    }
    s->endptcomplete |= endpoint_bit;
    prime_usb_signal(s, USB_STS_USBINT);
}

static int prime_usb_hex(unsigned char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static bool prime_usb_decode_hex(const char *text, uint8_t *bytes,
                                 size_t capacity, size_t *length)
{
    size_t count = 0;
    if (!strcmp(text, "-")) {
        *length = 0;
        return true;
    }
    while (text[0] && text[1]) {
        int high = prime_usb_hex(text[0]), low = prime_usb_hex(text[1]);
        if (high < 0 || low < 0 || count == capacity) return false;
        bytes[count++] = high << 4 | low;
        text += 2;
    }
    if (*text) return false;
    *length = count;
    return true;
}

static void prime_usb_reply_data(PrimeUSBOTGState *s, const uint8_t *data,
                                 size_t length)
{
    GString *reply = g_string_new("DATA ");
    for (size_t i = 0; i < length; i++) {
        g_string_append_printf(reply, "%02x", data[i]);
    }
    prime_usb_reply(s, reply->str);
    g_string_free(reply, true);
}

static bool prime_rom_execute_dcd(const uint8_t *image, uint32_t image_bytes,
                                  uint32_t image_start, uint32_t dcd,
                                  Error **errp);

/* Functional open-device SDP. Report/command byte order and acknowledgements
 * follow the Prime U-Boot fork's f_sdp.c. HAB authentication and unsupported
 * DCD operations are rejected explicitly. */
static void prime_sdp_reset(PrimeUSBOTGState *s)
{
    s->sdp_report_len = s->sdp_report_offset = s->sdp_report_id = 0;
    s->sdp_phase = s->sdp_command = 0;
    s->sdp_address = s->sdp_remaining = s->sdp_status = s->sdp_entry = 0;
    s->sdp_dcd_length = s->sdp_dcd_offset = 0;
    s->sdp_skip_dcd = false;
}

static bool prime_sdp_ram_range(uint32_t address, uint32_t length)
{
    uint64_t end = (uint64_t)address + length;
    return length && ((address >= 0x80000000 && end <= 0x90000000) ||
                      (address >= 0x00900000 && end <= 0x00920000));
}

static bool prime_sdp_report(PrimeUSBOTGState *s)
{
    uint8_t *p = s->sdp_report;
    size_t length = s->sdp_report_len;
    if (p[0] != s->sdp_report_id) {
        return false;
    }
    if (p[0] == 2) {
        if ((s->sdp_command != 0x0404 && s->sdp_command != 0x0a0a) ||
            !s->sdp_remaining || length < 2) {
            return false;
        }
        size_t amount = MIN(length - 1, s->sdp_remaining);
        if (s->sdp_command == 0x0a0a) {
            memcpy(s->sdp_dcd + s->sdp_dcd_offset, p + 1, amount);
            s->sdp_dcd_offset += amount;
        } else {
            if (!prime_usb_dma_write(s->sdp_address, p + 1, amount)) {
                return false;
            }
            s->sdp_address += amount;
        }
        s->sdp_remaining -= amount;
        if (!s->sdp_remaining) {
            if (s->sdp_command == 0x0a0a) {
                Error *err = NULL;
                if (!prime_rom_execute_dcd(s->sdp_dcd, s->sdp_dcd_length,
                                          0x00910000, 0x00910000, &err)) {
                    error_free(err);
                    s->sdp_status = 0x000a0533;
                }
            }
            s->sdp_phase = 1;
        }
        return true;
    }
    if (length != 17 || s->sdp_remaining || s->sdp_phase) {
        return false;
    }
    s->sdp_command = lduw_be_p(p + 1);
    s->sdp_address = ldl_be_p(p + 3);
    uint32_t count = ldl_be_p(p + 8);
    s->sdp_status = 0;
    switch (s->sdp_command) {
    case 0x0101: /* READ_REGISTER: RAM plus the modeled SRC register bank. */
        if (count && p[7] == 32 && !(s->sdp_address & 3) && !(count & 3) &&
            s->sdp_address >= 0x020d8000 &&
            (uint64_t)s->sdp_address + count <= 0x020d8048) {
            s->sdp_remaining = count;
            s->sdp_phase = 1;
            return true;
        }
        /* fall through */
    case 0x0404: /* WRITE_FILE */
        if (!prime_sdp_ram_range(s->sdp_address, count)) {
            return false;
        }
        s->sdp_remaining = count;
        s->sdp_status = 0x88888888;
        s->sdp_phase = s->sdp_command == 0x0101 ? 1 : 0;
        return true;
    case 0x0505: /* ERROR_STATUS */
        break;
    case 0x0a0a: /* DCD_WRITE */
        if (count < 4 || count > sizeof(s->sdp_dcd)) {
            return false;
        }
        s->sdp_dcd_length = s->sdp_remaining = count;
        s->sdp_dcd_offset = 0;
        s->sdp_status = 0x128a8a12;
        return true;
    case 0x0c0c: /* SKIP_DCD_HEADER: host already applied DCD_WRITE. */
        s->sdp_skip_dcd = true;
        s->sdp_status = 0x900dd009;
        break;
    case 0x0b0b: { /* JUMP_ADDRESS points to an i.MX IVT, not raw code. */
        uint8_t ivt[32];
        if (!prime_sdp_ram_range(s->sdp_address, sizeof(ivt)) ||
            !prime_usb_dma_read(s->sdp_address, ivt, sizeof(ivt)) ||
            ivt[0] != 0xd1 || lduw_be_p(ivt + 1) != 32 ||
            (ivt[3] != 0x40 && ivt[3] != 0x41) ||
            ldl_le_p(ivt + 20) != s->sdp_address ||
            ldl_le_p(ivt + 24)) { /* HAB/CSF execution is not modeled. */
            s->sdp_status = 0x000a0533;
            break;
        }
        s->sdp_entry = ldl_le_p(ivt + 4);
        if (!prime_sdp_ram_range(s->sdp_entry, 4) || (s->sdp_entry & 3)) {
            s->sdp_status = 0x000a0533;
            break;
        }
        uint32_t dcd = ldl_le_p(ivt + 12);
        if (dcd && !s->sdp_skip_dcd) {
            Error *err = NULL;
            uint8_t header[4];
            if (!prime_sdp_ram_range(dcd, sizeof(header)) ||
                !prime_usb_dma_read(dcd, header, sizeof(header))) {
                s->sdp_status = 0x000a0533;
                break;
            }
            size_t bytes = lduw_be_p(header + 1);
            if (bytes < 4 || bytes > sizeof(s->sdp_dcd) ||
                !prime_sdp_ram_range(dcd, bytes) ||
                !prime_usb_dma_read(dcd, s->sdp_dcd, bytes) ||
                !prime_rom_execute_dcd(s->sdp_dcd, bytes, dcd, dcd, &err)) {
                error_free(err);
                s->sdp_status = 0x000a0533;
            }
        }
        break;
    }
    default:
        return false;
    }
    s->sdp_phase = 1;
    return true;
}

static void prime_sdp_enter_image(CPUState *cpu, run_on_cpu_data data)
{
    /* The functional ROM does not execute an instruction-level ROM image.
     * Start its handoff in the CPU reset profile (ARM, MMU off), on the vCPU
     * thread so an in-flight translation cannot overwrite the entry PC. */
    cpu_reset(cpu);
    cpu_set_pc(cpu, data.target_ptr);
    cpu->halted = false;
}

static void prime_sdp_in(PrimeUSBOTGState *s, const char *argument)
{
    char *end = NULL;
    unsigned long requested = strtoul(argument, &end, 10);
    uint8_t data[65] = { 0 };
    size_t length = 5;
    if (!s->connected || s->suspended || !s->sdp_phase ||
        !argument[0] || *end) {
        prime_usb_reply(s, "NAK");
        return;
    }
    if (s->sdp_phase == 1) {
        data[0] = 3;
        stl_le_p(data + 1, 0x56787856); /* HAB open */
    } else if (s->sdp_phase == 2) {
        data[0] = 4;
        stl_le_p(data + 1, s->sdp_status);
    } else {
        length = 1 + MIN(s->sdp_remaining, 64);
        data[0] = 4;
        if (!prime_usb_dma_read(s->sdp_address, data + 1, length - 1)) {
            prime_usb_reply(s, "ERR dma");
            return;
        }
    }
    if (requested < length || requested > 512) {
        prime_usb_reply(s, "NAK");
        return;
    }
    prime_usb_reply_data(s, data, length);
    if (s->sdp_phase == 1) {
        if (s->sdp_command == 0x0b0b && !s->sdp_status) {
            CPUState *cpu = qemu_get_cpu(0);
            s->sdp_phase = 0;
            s->rom_downloader = false;
            s->deviceaddr = 0;
            run_on_cpu(cpu, prime_sdp_enter_image,
                       RUN_ON_CPU_TARGET_PTR(s->sdp_entry));
        } else {
            s->sdp_phase = s->sdp_command == 0x0101 ? 3 : 2;
        }
    } else if (s->sdp_phase == 2) {
        s->sdp_phase = 0;
    } else {
        s->sdp_address += length - 1;
        s->sdp_remaining -= length - 1;
        if (!s->sdp_remaining) {
            s->sdp_phase = 0;
        }
    }
}

static bool prime_usb_rom_prepare_control(PrimeUSBOTGState *s,
                                          const uint8_t *data,
                                          size_t available,
                                          uint16_t requested)
{
    size_t length = MIN(available, (size_t)requested);
    if (length > sizeof(s->rom_control)) {
        return false;
    }
    memcpy(s->rom_control, data, length);
    s->rom_control_len = length;
    s->rom_control_offset = 0;
    s->rom_status_in = false;
    return true;
}

static void prime_usb_rom_setup(PrimeUSBOTGState *s, const char *hex)
{
    uint8_t setup[8];
    size_t length;
    if (!s->connected ||
        !prime_usb_decode_hex(hex, setup, sizeof(setup), &length) ||
        length != sizeof(setup)) {
        prime_usb_reply(s, "ERR setup");
        return;
    }

    uint8_t request_type = setup[0];
    uint8_t request = setup[1];
    uint16_t value = lduw_le_p(setup + 2);
    uint16_t requested = lduw_le_p(setup + 6);
    s->rom_control_len = s->rom_control_offset = 0;
    s->rom_status_in = false;

    s->sdp_report_len = s->sdp_report_offset = s->sdp_report_id = 0;
    if (request_type == 0x80 && request == 6) {
        const uint8_t *descriptor = NULL;
        size_t descriptor_len = 0;
        uint8_t string_descriptor[128] = { 0 };
        switch (value >> 8) {
        case 1:
            descriptor = prime_usb_rom_device_descriptor;
            descriptor_len = sizeof(prime_usb_rom_device_descriptor);
            break;
        case 2:
            descriptor = prime_usb_rom_configuration_descriptor;
            descriptor_len = sizeof(prime_usb_rom_configuration_descriptor);
            break;
        case 3: {
            const char *text = NULL;
            uint8_t index = value & 0xff;
            if (!index) {
                string_descriptor[0] = 4;
                string_descriptor[1] = 3;
                string_descriptor[2] = 9;
                string_descriptor[3] = 4;
                descriptor_len = 4;
            } else {
                switch (index) {
                case 1: text = "Freescale SemiConductor Inc "; break;
                case 2: text = "SE Blank 6ULL"; break;
                case 4: case 5: text = "Freescale Flash"; break;
                }
                if (!text || lduw_le_p(setup + 4) != 0x409) {
                    prime_usb_reply(s, "ERR setup");
                    return;
                }
                /* The physical ROM includes a trailing UTF-16 NUL in its
                 * product string; preserve that byte-level detail. */
                size_t chars = strlen(text) + (index == 2);
                descriptor_len = 2 + 2 * chars;
                string_descriptor[0] = descriptor_len;
                string_descriptor[1] = 3;
                for (size_t i = 0; i < chars; i++) {
                    string_descriptor[2 + 2 * i] = text[i];
                }
            }
            descriptor = string_descriptor;
            break;
        }
        default:
            prime_usb_reply(s, "ERR setup");
            return;
        }
        if (!prime_usb_rom_prepare_control(s, descriptor, descriptor_len,
                                           requested)) {
            prime_usb_reply(s, "ERR setup");
            return;
        }
    } else if (request_type == 0x81 && request == 6 &&
               (value >> 8) == 0x22) {
        if (!prime_usb_rom_prepare_control(
                s, prime_usb_rom_report_descriptor,
                sizeof(prime_usb_rom_report_descriptor), requested)) {
            prime_usb_reply(s, "ERR setup");
            return;
        }
    } else if (request_type == 0x21 && request == 9 &&
               (value >> 8) == 2 && lduw_le_p(setup + 4) == 0 &&
               (((value & 0xff) == 1 && requested == 17) ||
                ((value & 0xff) == 2 && requested >= 2 && requested <= 1025))) {
        s->sdp_report_id = value & 0xff;
        s->sdp_report_len = requested;
    } else if (request_type == 0x00 && request == 5 && requested == 0) {
        s->deviceaddr = (uint32_t)(value & 0x7f) << 25;
        s->rom_status_in = true;
    } else if (request_type == 0x00 && request == 9 && requested == 0) {
        s->rom_status_in = true;
    } else if (request_type == 0x21 && request == 10 && requested == 0) {
        s->rom_status_in = true;
    } else {
        prime_usb_reply(s, "ERR setup");
        return;
    }
    prime_usb_reply(s, "OK");
}

static void prime_usb_rom_in(PrimeUSBOTGState *s, const char *argument)
{
    char *end = NULL;
    unsigned long requested = strtoul(argument, &end, 10);
    if (!argument[0] || *end || requested > 512 || !s->connected) {
        prime_usb_reply(s, "NAK");
        return;
    }
    if (s->rom_control_offset < s->rom_control_len) {
        size_t available = s->rom_control_len - s->rom_control_offset;
        size_t amount = MIN((size_t)requested, available);
        prime_usb_reply_data(s, s->rom_control + s->rom_control_offset,
                             amount);
        s->rom_control_offset += amount;
        return;
    }
    if (s->rom_status_in && requested == 0) {
        s->rom_status_in = false;
        prime_usb_reply_data(s, NULL, 0);
        return;
    }
    prime_usb_reply(s, "NAK");
}

static void prime_usb_rom_out(PrimeUSBOTGState *s, const char *hex)
{
    uint8_t data[1025];
    size_t length;
    if (!s->connected ||
        !prime_usb_decode_hex(hex, data, sizeof(data), &length)) {
        prime_usb_reply(s, "NAK");
        return;
    }
    if (s->sdp_report_len) {
        if (!length || length > s->sdp_report_len - s->sdp_report_offset) {
            prime_usb_reply(s, "ERR length");
            return;
        }
        memcpy(s->sdp_report + s->sdp_report_offset, data, length);
        s->sdp_report_offset += length;
        if (s->sdp_report_offset == s->sdp_report_len) {
            bool ok = prime_sdp_report(s);
            s->sdp_report_len = s->sdp_report_offset = s->sdp_report_id = 0;
            if (!ok) {
                prime_usb_reply(s, "ERR sdp");
                return;
            }
            s->rom_status_in = true;
        }
        prime_usb_reply(s, "OK");
        return;
    }
    if (length) {
        prime_usb_reply(s, "NAK");
        return;
    }
    s->rom_control_len = s->rom_control_offset = 0;
    prime_usb_reply(s, "OK");
}

static void prime_usb_host_setup(PrimeUSBOTGState *s, const char *hex)
{
    if (s->rom_downloader) {
        prime_usb_rom_setup(s, hex);
        return;
    }
    uint8_t setup[8];
    size_t length;
    hwaddr qh = s->endptlistaddr & ~0x7ffu;
    if (!s->connected || !(s->usbcmd & 1) || s->setupstat ||
        !prime_usb_decode_hex(hex, setup, sizeof(setup), &length) ||
        length != sizeof(setup) || !prime_usb_dma_write(qh + 40, setup, 8)) {
        prime_usb_reply(s, "ERR setup");
        return;
    }
    s->setupstat |= 1;
    /* A new control SETUP clears the preceding protocol stall. See Linux
     * ChipIdea commit 56ffa1d154c7e12af16273f0cdc42690dd05caf5. */
    s->endptctrl0 &= ~(USB_EP0_RX_STALL | USB_EP0_TX_STALL);
    prime_usb_signal(s, USB_STS_USBINT);
    prime_usb_reply(s, "OK");
}

/* Full bulk packets advance an active dTD. Only exhausting its bytes or a
 * short packet completes it. Synthetic EP0 commands carry the complete data
 * phase, preserving the existing host interface. */
static void prime_usb_packet_done(PrimeUSBOTGState *s, unsigned endpoint,
                                  bool in, hwaddr td, uint32_t token,
                                  uint32_t buffers[5], size_t length)
{
    size_t capacity = (token >> 16) & 0x7fff;
    hwaddr qh = (s->endptlistaddr & ~0x7ffu) + (endpoint * 2 + in) * 64;
    uint32_t cap = 0;
    prime_usb_read32(qh, &cap);
    unsigned maxpacket = (cap >> 16) & 0x7ff;
    if (endpoint && maxpacket && length && !(length % maxpacket) && length < capacity) {
        size_t remaining = length;
        unsigned page = 0;
        while (page < 5 && remaining >= 0x1000 - (buffers[page] & 0xfff)) {
            remaining -= 0x1000 - (buffers[page] & 0xfff); page++;
        }
        if (page >= 5) { prime_usb_signal(s, USB_STS_ERROR); return; }
        uint32_t advanced[5] = {0};
        advanced[0] = buffers[page] + remaining;
        for (unsigned i = 1; i + page < 5; i++) advanced[i] = buffers[i + page];
        for (unsigned i = 0; i < 5; i++) {
            prime_usb_write32(td + 8 + i * 4, advanced[i]);
            prime_usb_write32(qh + 16 + i * 4, advanced[i]);
        }
        token = (token & ~(0x7fffu << 16)) | ((capacity - length) << 16);
        prime_usb_write32(td + 4, token);
        prime_usb_write32(qh + 12, token);
    } else {
        prime_usb_complete(s, endpoint, in, td, token, capacity - length);
    }
}

static void prime_usb_host_in(PrimeUSBOTGState *s, unsigned endpoint,
                              const char *argument)
{
    if (s->rom_downloader) {
        if (endpoint == 0) {
            prime_usb_rom_in(s, argument);
        } else if (endpoint == 1) {
            prime_sdp_in(s, argument);
        } else {
            prime_usb_reply(s, "NAK");
        }
        return;
    }
    hwaddr td;
    uint32_t token, buffers[5];
    unsigned long requested;
    char *end = NULL;
    requested = strtoul(argument, &end, 10);
    uint32_t endpoint_bit = prime_usb_endpoint_bit(endpoint, true);
    if (endpoint == 0 && (s->endptctrl0 & USB_EP0_TX_STALL)) {
        prime_usb_reply(s, "STALL");
        return;
    }
    if (!argument[0] || *end || requested > (endpoint ? 16384 : 512) ||
        !(s->endptstat & endpoint_bit) ||
        !prime_usb_td(s, endpoint, true, &td, &token, buffers)) {
        prime_usb_reply(s, "NAK");
        return;
    }
    size_t available = (token >> 16) & 0x7fff;
    size_t amount = MIN((size_t)requested, available);
    uint8_t data[16384];
    if (!prime_usb_transfer_memory(buffers, data, amount, false)) {
        prime_usb_signal(s, USB_STS_ERROR);
        prime_usb_reply(s, "ERR dma");
        return;
    }
    prime_usb_reply_data(s, data, amount);
    prime_usb_packet_done(s, endpoint, true, td, token, buffers, amount);
}

static void prime_usb_host_out(PrimeUSBOTGState *s, unsigned endpoint,
                               const char *hex)
{
    if (s->rom_downloader) {
        if (endpoint == 0) {
            prime_usb_rom_out(s, hex);
        } else {
            prime_usb_reply(s, "NAK");
        }
        return;
    }
    hwaddr td;
    uint32_t token, buffers[5];
    uint8_t data[16384];
    size_t length;
    uint32_t endpoint_bit = prime_usb_endpoint_bit(endpoint, false);
    if (endpoint == 0 && (s->endptctrl0 & USB_EP0_RX_STALL)) {
        prime_usb_reply(s, "STALL");
        return;
    }
    if (!prime_usb_decode_hex(hex, data, sizeof(data), &length) ||
        !(s->endptstat & endpoint_bit) ||
        !prime_usb_td(s, endpoint, false, &td, &token, buffers)) {
        prime_usb_reply(s, "NAK");
        return;
    }
    size_t capacity = (token >> 16) & 0x7fff;
    if (length > capacity ||
        !prime_usb_transfer_memory(buffers, data, length, true)) {
        prime_usb_signal(s, USB_STS_ERROR);
        prime_usb_reply(s, "ERR length");
        return;
    }
    prime_usb_packet_done(s, endpoint, false, td, token, buffers, length);
    prime_usb_reply(s, "OK");
}

static bool prime_usb_endpoint_argument(char *argument, unsigned *endpoint,
                                        char **payload)
{
    char *separator = strchr(argument, ' ');
    char *end = NULL;
    unsigned long parsed;
    if (!separator) {
        return false;
    }
    *separator = 0;
    parsed = strtoul(argument, &end, 10);
    if (!argument[0] || *end || parsed >= 8 || !separator[1]) {
        return false;
    }
    *endpoint = parsed;
    *payload = separator + 1;
    return true;
}

static void prime_usb_host_command(PrimeUSBOTGState *s, char *line)
{
    if (!strcmp(line, "HELLO")) {
        prime_usb_reply(s, "USBHOST 1");
    } else if (!strcmp(line, "CONNECT")) {
        bool changed = !s->connected;
        s->connected = true;
        if (changed) prime_usbnc_bvalid_change(s);
        s->suspended = false;
        qemu_set_irq(s->cable[0], 1);
        qemu_set_irq(s->cable[1], 1);
        s->portsc1 = (s->portsc1 & ~((3u << 26) | BIT(7))) |
                     BIT(0) | BIT(1) | (2u << 26);
        prime_usb_signal(s, USB_STS_PORTCHANGE);
        prime_usb_reply(s, "OK");
    } else if (!strcmp(line, "DISCONNECT")) {
        bool changed = s->connected;
        prime_sdp_reset(s);
        s->connected = false;
        if (changed) prime_usbnc_bvalid_change(s);
        s->suspended = false;
        qemu_set_irq(s->cable[0], 0);
        qemu_set_irq(s->cable[1], 0);
        s->portsc1 &= ~(BIT(0) | BIT(1) | BIT(7));
        prime_usb_signal(s, USB_STS_PORTCHANGE);
        prime_usb_reply(s, "OK");
    } else if (!strcmp(line, "RESET")) {
        if (!s->connected) {
            prime_usb_reply(s, "ERR disconnected");
        } else if (s->rom_downloader) {
            prime_sdp_reset(s);
            s->deviceaddr = 0;
            s->rom_control_len = s->rom_control_offset = 0;
            s->rom_status_in = false;
            s->usbsts = 0;
            prime_usb_reply(s, "OK");
        } else {
            s->deviceaddr = 0;
            s->setupstat = s->endptprime = s->endptstat = 0;
            s->endptcomplete = 0;
            prime_usb_signal(s, USB_STS_RESET | USB_STS_PORTCHANGE);
            prime_usb_reply(s, "OK");
        }
    } else if (!strcmp(line, "SUSPEND")) {
        s->suspended = true;
        s->portsc1 |= BIT(7);
        prime_usb_signal(s, USB_STS_SUSPEND);
        prime_usb_reply(s, "OK");
    } else if (!strcmp(line, "RESUME")) {
        s->suspended = false;
        s->portsc1 &= ~BIT(7);
        prime_usb_signal(s, USB_STS_PORTCHANGE);
        prime_usb_reply(s, "OK");
    } else if (g_str_has_prefix(line, "SETUP ")) {
        prime_usb_host_setup(s, line + 6);
    } else if (g_str_has_prefix(line, "IN ")) {
        prime_usb_host_in(s, 0, line + 3);
    } else if (g_str_has_prefix(line, "OUT ")) {
        prime_usb_host_out(s, 0, line + 4);
    } else if (g_str_has_prefix(line, "EPIN ")) {
        unsigned endpoint;
        char *argument;
        if (prime_usb_endpoint_argument(line + 5, &endpoint, &argument)) {
            prime_usb_host_in(s, endpoint, argument);
        } else {
            prime_usb_reply(s, "ERR endpoint");
        }
    } else if (g_str_has_prefix(line, "EPOUT ")) {
        unsigned endpoint;
        char *argument;
        if (prime_usb_endpoint_argument(line + 6, &endpoint, &argument)) {
            prime_usb_host_out(s, endpoint, argument);
        } else {
            prime_usb_reply(s, "ERR endpoint");
        }
    } else if (!strcmp(line, "STATUS")) {
        char reply[256];
        snprintf(reply, sizeof(reply),
                 "STATUS connected=%u suspended=%u address=%u run=%u mode=%s vid=%04x pid=%04x setup=%08x prime=%08x complete=%08x sts=%08x",
                 s->connected, s->suspended, s->deviceaddr >> 25,
                 s->rom_downloader || !!(s->usbcmd & 1),
                 s->rom_downloader ? "rom-sdp" : "guest",
                 s->rom_downloader ? 0x15a2 : 0,
                 s->rom_downloader ? 0x0080 : 0,
                 s->setupstat, s->endptprime,
                 s->endptcomplete, s->usbsts);
        prime_usb_reply(s, reply);
    } else {
        prime_usb_reply(s, "ERR command");
    }
}

static int prime_usb_can_receive(void *opaque)
{
    PrimeUSBOTGState *s = opaque;
    return sizeof(s->input) - s->input_len;
}

static void prime_usb_receive(void *opaque, const uint8_t *buffer, int size)
{
    PrimeUSBOTGState *s = opaque;
    for (int i = 0; i < size; i++) {
        if (buffer[i] == '\n') {
            s->input[s->input_len] = 0;
            if (s->input_len && s->input[s->input_len - 1] == '\r') {
                s->input[--s->input_len] = 0;
            }
            prime_usb_host_command(s, (char *)s->input);
            s->input_len = 0;
        } else if (s->input_len + 1 < sizeof(s->input)) {
            s->input[s->input_len++] = buffer[i];
        } else {
            s->input_len = 0;
            prime_usb_reply(s, "ERR overflow");
        }
    }
}

static uint64_t prime_usb_read(void *opaque, hwaddr offset, unsigned size)
{
    PrimeUSBOTGState *s = opaque;
    switch (offset) {
    case 0x120: return 1;                         /* DCIVERSION */
    case 0x124: return BIT(7) | 8;                /* DC + 8 endpoints */
    case USB_USBCMD: return s->usbcmd;
    case USB_USBSTS: return s->usbsts;
    case USB_USBINTR: return s->usbintr;
    case USB_DEVICEADDR: return s->deviceaddr;
    case USB_ENDPTLISTADDR: return s->endptlistaddr;
    case USB_BURSTSIZE: return s->burstsize;
    case USB_PORTSC1: return s->portsc1;
    case USB_OTGSC: return s->otgsc;
    case USB_USBMODE: return s->usbmode;
    case USB_SETUPSTAT: return s->setupstat;
    case USB_ENDPTPRIME: return s->endptprime;
    case USB_ENDPTFLUSH: return 0;
    case USB_ENDPTSTAT: return s->endptstat;
    case USB_ENDPTCOMPLETE: return s->endptcomplete;
    case USB_ENDPTCTRL0: return s->endptctrl0;
    case USB_ENDPTCTRL0 + 4: return s->endptctrl1;
    default: return 0;
    }
}

static void prime_usb_write(void *opaque, hwaddr offset, uint64_t value,
                            unsigned size)
{
    PrimeUSBOTGState *s = opaque;
    uint32_t v = value;
    switch (offset) {
    case USB_USBCMD:
        s->usbcmd = v & ~BIT(1);                 /* reset self-clears */
        if (v & BIT(1)) {
            s->deviceaddr = s->endptprime = s->endptstat = 0;
            s->setupstat = s->endptcomplete = 0;
        }
        break;
    case USB_USBSTS: s->usbsts &= ~v; break;      /* W1C */
    case USB_USBINTR: s->usbintr = v; break;
    case USB_DEVICEADDR: s->deviceaddr = v; break;
    case USB_ENDPTLISTADDR: s->endptlistaddr = v & ~0x7ffu; break;
    case USB_BURSTSIZE: s->burstsize = v; break;
    case USB_PORTSC1:
        s->portsc1 = (v & ~(BIT(0) | BIT(1) | (3u << 26))) |
                     (s->portsc1 & (BIT(0) | BIT(1) | (3u << 26)));
        break;
    case USB_OTGSC: s->otgsc = v & ~0x007f0000u; break;
    case USB_USBMODE: s->usbmode = v; break;
    case USB_SETUPSTAT: s->setupstat &= ~v; break;
    case USB_ENDPTPRIME:
        /* The controller accepts a valid dTD immediately: PRIME is a
         * doorbell and self-clears, while STAT remains asserted until the
         * transfer completes.  Keeping PRIME high until host traffic races
         * stock firmware's endpoint callback registration. */
        s->endptprime |= v;
        s->endptstat |= v;
        s->endptprime &= ~v;
        break;
    case USB_ENDPTFLUSH:
        s->endptprime &= ~v;
        s->endptstat &= ~v;
        break;
    case USB_ENDPTCOMPLETE: s->endptcomplete &= ~v; break;
    case USB_ENDPTCTRL0: s->endptctrl0 = v; break;
    case USB_ENDPTCTRL0 + 4: s->endptctrl1 = v; break;
    default: break;
    }
    prime_usb_irq(s);
}

static const MemoryRegionOps prime_usb_ops = {
    .read = prime_usb_read, .write = prime_usb_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .valid = { .min_access_size = 4, .max_access_size = 4,
               .unaligned = false },
};

static void prime_usb_reset(DeviceState *dev)
{
    PrimeUSBOTGState *s = PRIME_USBOTG(dev);
    prime_sdp_reset(s);
    /* Provisional cold defaults; physical USBNC reset capture is pending. */
    memset(s->usbnc_ctrl, 0, sizeof(s->usbnc_ctrl));
    memset(s->usbnc_phy, 0, sizeof(s->usbnc_phy));
    memset(s->usbnc_wake, 0, sizeof(s->usbnc_wake));
    s->usbcmd = s->usbsts = s->usbintr = s->deviceaddr = 0;
    s->endptlistaddr = s->burstsize = s->otgsc = s->usbmode = 0;
    s->setupstat = s->endptprime = s->endptstat = s->endptcomplete = 0;
    s->endptctrl0 = s->endptctrl1 = 0;
    s->suspended = false;
    qemu_set_irq(s->cable[0], s->connected);
    qemu_set_irq(s->cable[1], s->connected);
    s->portsc1 = s->connected ? BIT(0) | BIT(1) | (2u << 26) : 0;
    s->rom_control_len = s->rom_control_offset = 0;
    s->rom_status_in = false;
    s->input_len = 0;
    prime_usb_irq(s);
}

static void prime_usb_rom_downloader(void *opaque, int line, int level)
{
    PrimeUSBOTGState *s = opaque;
    (void)line;
    prime_sdp_reset(s);
    s->rom_downloader = level != 0;
    s->deviceaddr = 0;
    s->rom_control_len = s->rom_control_offset = 0;
    s->rom_status_in = false;
    if (s->rom_downloader) {
        s->usbcmd = s->usbsts = s->usbintr = 0;
        s->setupstat = s->endptprime = s->endptstat = 0;
        s->endptcomplete = 0;
    }
    prime_usb_irq(s);
}

static void prime_usb_realize(DeviceState *dev, Error **errp)
{
    PrimeUSBOTGState *s = PRIME_USBOTG(dev);
    qemu_chr_fe_set_handlers(&s->chr, prime_usb_can_receive,
                             prime_usb_receive, NULL, NULL, s, NULL, true);
}

static void prime_usb_init(Object *obj)
{
    PrimeUSBOTGState *s = PRIME_USBOTG(obj);
    memory_region_init_io(&s->iomem, obj, &prime_usb_ops, s,
                          TYPE_PRIME_USBOTG, 0x200);
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->iomem);
    memory_region_init_io(&s->usbnc_iomem, obj, &prime_usbnc_ops, s,
                         "prime-g2-usbnc", 0x200);
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->usbnc_iomem);
    sysbus_init_irq(SYS_BUS_DEVICE(obj), &s->irq);
    qdev_init_gpio_out_named(DEVICE(obj), s->cable, "cable", 2);
    qdev_init_gpio_in_named(DEVICE(obj), prime_usb_rom_downloader,
                            "rom-downloader", 1);
}

static int prime_usb_post_load(void *opaque, int version_id)
{
    PrimeUSBOTGState *s = opaque;
    qemu_set_irq(s->cable[0], s->connected);
    qemu_set_irq(s->cable[1], s->connected);
    prime_usb_irq(s);
    return 0;
}

static const VMStateDescription prime_usb_vmstate = {
    .name = TYPE_PRIME_USBOTG, .version_id = 5, .minimum_version_id = 3,
    .post_load = prime_usb_post_load,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT32_ARRAY_V(usbnc_ctrl, PrimeUSBOTGState, 2, 4),
        VMSTATE_UINT32_ARRAY_V(usbnc_phy, PrimeUSBOTGState, 2, 4),
        VMSTATE_BOOL_ARRAY_V(usbnc_wake, PrimeUSBOTGState, 2, 4),
        VMSTATE_UINT32(usbcmd, PrimeUSBOTGState),
        VMSTATE_UINT32(usbsts, PrimeUSBOTGState),
        VMSTATE_UINT32(usbintr, PrimeUSBOTGState),
        VMSTATE_UINT32(deviceaddr, PrimeUSBOTGState),
        VMSTATE_UINT32(endptlistaddr, PrimeUSBOTGState),
        VMSTATE_UINT32(burstsize, PrimeUSBOTGState),
        VMSTATE_UINT32(portsc1, PrimeUSBOTGState),
        VMSTATE_UINT32(otgsc, PrimeUSBOTGState),
        VMSTATE_UINT32(usbmode, PrimeUSBOTGState),
        VMSTATE_UINT32(setupstat, PrimeUSBOTGState),
        VMSTATE_UINT32(endptprime, PrimeUSBOTGState),
        VMSTATE_UINT32(endptstat, PrimeUSBOTGState),
        VMSTATE_UINT32(endptcomplete, PrimeUSBOTGState),
        VMSTATE_UINT32(endptctrl0, PrimeUSBOTGState),
        VMSTATE_UINT32_V(endptctrl1, PrimeUSBOTGState, 5),
        VMSTATE_BOOL(connected, PrimeUSBOTGState),
        VMSTATE_BOOL(suspended, PrimeUSBOTGState),
        VMSTATE_BOOL(rom_downloader, PrimeUSBOTGState),
        VMSTATE_UINT8_ARRAY(rom_control, PrimeUSBOTGState, 512),
        VMSTATE_UINT16(rom_control_len, PrimeUSBOTGState),
        VMSTATE_UINT16(rom_control_offset, PrimeUSBOTGState),
        VMSTATE_BOOL(rom_status_in, PrimeUSBOTGState),
        VMSTATE_UINT8_ARRAY(sdp_report, PrimeUSBOTGState, 1025),
        VMSTATE_UINT16(sdp_report_len, PrimeUSBOTGState),
        VMSTATE_UINT16(sdp_report_offset, PrimeUSBOTGState),
        VMSTATE_UINT8(sdp_report_id, PrimeUSBOTGState),
        VMSTATE_UINT8(sdp_phase, PrimeUSBOTGState),
        VMSTATE_UINT16(sdp_command, PrimeUSBOTGState),
        VMSTATE_UINT32(sdp_address, PrimeUSBOTGState),
        VMSTATE_UINT32(sdp_remaining, PrimeUSBOTGState),
        VMSTATE_UINT32(sdp_status, PrimeUSBOTGState),
        VMSTATE_UINT32(sdp_entry, PrimeUSBOTGState),
        VMSTATE_UINT8_ARRAY(sdp_dcd, PrimeUSBOTGState, 1768),
        VMSTATE_UINT16(sdp_dcd_length, PrimeUSBOTGState),
        VMSTATE_UINT16(sdp_dcd_offset, PrimeUSBOTGState),
        VMSTATE_BOOL(sdp_skip_dcd, PrimeUSBOTGState),
        VMSTATE_END_OF_LIST()
    },
};

static const Property prime_usb_properties[] = {
    DEFINE_PROP_CHR("chardev", PrimeUSBOTGState, chr),
};

static void prime_usb_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);
    dc->realize = prime_usb_realize;
    dc->vmsd = &prime_usb_vmstate;
    device_class_set_legacy_reset(dc, prime_usb_reset);
    device_class_set_props(dc, prime_usb_properties);
}

/* Goodix GT5688 ---------------------------------------------------------- */
#define TYPE_PRIME_GOODIX TYPE_PRIME_G2_GOODIX
OBJECT_DECLARE_SIMPLE_TYPE(PrimeGoodixState, PRIME_GOODIX)
struct PrimeGoodixState {
    I2CSlave parent_obj;
    uint16_t ptr;
    uint8_t addr_bytes;
    qemu_irq irq;
    bool drive_irq;
    bool reset_asserted;
    bool release_pending;
    uint8_t fault_mode;
    uint16_t release_delay_ms;
    uint16_t step_delay_ms;
    uint16_t start_x, start_y;
    QEMUTimer *release_timer;
    uint16_t end_x, end_y;
    uint8_t move_step, move_steps;
    uint8_t regs[0x10000];
};
static void prime_goodix_irq(PrimeGoodixState *s, int level)
{
    qemu_set_irq(s->irq, s->drive_irq ? level : 0);
}
static void prime_goodix_report(PrimeGoodixState *s, bool down,
                                uint16_t x, uint16_t y)
{
    if (s->fault_mode == 2) {
        down = true;
        x = y = 0xffff;
    }
    s->regs[0x814e] = 0x80 | (down ? 1 : 0);
    s->regs[0x814f] = 0;
    s->regs[0x8150] = x & 0xff;
    s->regs[0x8151] = x >> 8;
    s->regs[0x8152] = y & 0xff;
    s->regs[0x8153] = y >> 8;
    s->regs[0x8154] = 8;
    s->regs[0x8155] = 0;
    s->regs[0x8156] = 0;
    if (s->fault_mode != 3) {
        prime_goodix_irq(s, 0); /* captured active-low falling-edge IRQ */
    }
}
static void prime_goodix_release(void *opaque)
{
    PrimeGoodixState *s = opaque;

    if (s->move_step < s->move_steps) {
        uint32_t divisor = s->move_steps;
        int32_t dx = (int32_t)s->end_x - s->start_x;
        int32_t dy = (int32_t)s->end_y - s->start_y;

        s->move_step++;
        prime_goodix_report(s, true,
                            s->start_x + dx * s->move_step / divisor,
                            s->start_y + dy * s->move_step / divisor);
        return;
    }
    s->release_pending = false;
    prime_goodix_report(s, false, s->end_x, s->end_y);
}
static void prime_goodix_reset_input(void *opaque, int line, int level)
{
    PrimeGoodixState *s = opaque;
    s->reset_asserted = !level;
    if (s->reset_asserted) {
        s->ptr = 0;
        s->regs[0x814e] = 0;
        prime_goodix_irq(s, 1);
    }
}
static void prime_goodix_init(Object *obj)
{
    PrimeGoodixState *s = PRIME_GOODIX(obj);
    qdev_init_gpio_in_named(DEVICE(obj), prime_goodix_reset_input, "reset", 1);
    qdev_init_gpio_out_named(DEVICE(obj), &s->irq, "irq", 1);
    s->release_timer = timer_new_ms(QEMU_CLOCK_VIRTUAL,
                                    prime_goodix_release, s);
}
static int prime_goodix_event(I2CSlave *i2c, enum i2c_event event)
{
    PrimeGoodixState *s = PRIME_GOODIX(i2c);
    if (event == I2C_START_SEND) { s->addr_bytes = 2; }
    return 0;
}
static int prime_goodix_send(I2CSlave *i2c, uint8_t data)
{
    PrimeGoodixState *s = PRIME_GOODIX(i2c);
    if (s->addr_bytes == 2) { s->ptr = (uint16_t)data << 8; s->addr_bytes--; }
    else if (s->addr_bytes == 1) { s->ptr |= data; s->addr_bytes--; }
    else {
        uint16_t reg = s->ptr++;
        s->regs[reg] = data;
        if (reg == 0x814e && data == 0) {
            /*
             * The captured Goodix interrupt is active-low.  Acknowledge each
             * consumed report before arming the next point so every move and
             * release produces a distinct falling edge.  Leaving the line
             * low here makes stock firmware see only the initial touch and
             * lets its unlock animation time out before the final release.
             */
            prime_goodix_irq(s, 1);
            if (s->release_pending) {
                if (s->step_delay_ms) {
                    timer_mod(s->release_timer,
                              qemu_clock_get_ms(QEMU_CLOCK_VIRTUAL) +
                              s->step_delay_ms);
                } else {
                    prime_goodix_release(s);
                }
            }
        } else if (reg == 0x9009) {
            s->start_x = s->regs[0x9000] | s->regs[0x9001] << 8;
            s->start_y = s->regs[0x9002] | s->regs[0x9003] << 8;
            s->end_x = s->regs[0x9004] | s->regs[0x9005] << 8;
            s->end_y = s->regs[0x9006] | s->regs[0x9007] << 8;
            s->release_delay_ms = s->regs[0x9008] | s->regs[0x9009] << 8;
            s->move_step = 0;
            s->move_steps = (s->start_x != s->end_x ||
                             s->start_y != s->end_y) ? 8 : 0;
            s->step_delay_ms = s->move_steps ?
                MAX(1, s->release_delay_ms / (s->move_steps + 1)) :
                s->release_delay_ms;
            s->release_pending = true;
            prime_goodix_report(s, true, s->start_x, s->start_y);
        } else if (reg == 0x9030) {
            /* Emulator-only ingress: one complete, explicitly released frame.
             * It traverses the ordinary Goodix register/acknowledgement path. */
            timer_del(s->release_timer);
            s->release_pending = false;
            memcpy(&s->regs[0x814e], &s->regs[0x9020], 17);
            prime_goodix_irq(s, 0);
        } else if (reg == 0x90f0) {
            s->fault_mode = data <= 3 ? data : 2;
        }
    }
    return 0;
}
static uint8_t prime_goodix_recv(I2CSlave *i2c)
{
    PrimeGoodixState *s = PRIME_GOODIX(i2c);
    if (s->fault_mode == 1) return 0xff;
    return s->regs[s->ptr++];
}
static void prime_goodix_reset(DeviceState *dev)
{
    PrimeGoodixState *s = PRIME_GOODIX(dev);
    memset(s->regs, 0, sizeof(s->regs)); s->ptr = 0; s->addr_bytes = 0;
    memcpy(&s->regs[0x8140], "5688", 4); /* captured DT compatible/model */
    s->regs[0x8144] = 0x02; s->regs[0x8145] = 0x00; /* captured version 0200 */
    s->regs[0x8047] = 0x41;             /* PROVISIONAL config version */
    s->regs[0x8048] = 320 & 0xff; s->regs[0x8049] = 320 >> 8;
    s->regs[0x804a] = 240 & 0xff; s->regs[0x804b] = 240 >> 8;
    s->reset_asserted = false; s->release_pending = false;
    s->fault_mode = 0; s->release_delay_ms = s->step_delay_ms = 0;
    s->start_x = s->start_y = s->end_x = s->end_y = 0;
    s->move_step = s->move_steps = 0; timer_del(s->release_timer);
    prime_goodix_irq(s, 1);
}
static const Property prime_goodix_properties[] = {
    DEFINE_PROP_BOOL("drive-irq", PrimeGoodixState, drive_irq, true),
};
static const VMStateDescription prime_goodix_vmstate = {
    .name = TYPE_PRIME_G2_GOODIX, .version_id = 2, .minimum_version_id = 1,
    .fields = (const VMStateField[]) { VMSTATE_I2C_SLAVE(parent_obj, PrimeGoodixState),
        VMSTATE_UINT16(ptr, PrimeGoodixState), VMSTATE_UINT8(addr_bytes, PrimeGoodixState),
        VMSTATE_BOOL(reset_asserted, PrimeGoodixState),
        VMSTATE_BOOL(release_pending, PrimeGoodixState),
        VMSTATE_UINT8(fault_mode, PrimeGoodixState),
        VMSTATE_UINT16(release_delay_ms, PrimeGoodixState),
        VMSTATE_UINT16_V(step_delay_ms, PrimeGoodixState, 2),
        VMSTATE_UINT16_V(start_x, PrimeGoodixState, 2),
        VMSTATE_UINT16_V(start_y, PrimeGoodixState, 2),
        VMSTATE_TIMER_PTR(release_timer, PrimeGoodixState),
        VMSTATE_UINT16(end_x, PrimeGoodixState), VMSTATE_UINT16(end_y, PrimeGoodixState),
        VMSTATE_UINT8_V(move_step, PrimeGoodixState, 2),
        VMSTATE_UINT8_V(move_steps, PrimeGoodixState, 2),
        VMSTATE_UINT8_ARRAY(regs, PrimeGoodixState, 0x10000), VMSTATE_END_OF_LIST() },
};
static void prime_goodix_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc); I2CSlaveClass *ic = I2C_SLAVE_CLASS(oc);
    dc->vmsd = &prime_goodix_vmstate; device_class_set_legacy_reset(dc, prime_goodix_reset);
    device_class_set_props(dc, prime_goodix_properties);
    ic->event = prime_goodix_event; ic->send = prime_goodix_send; ic->recv = prime_goodix_recv;
}

/* Ilitek ILI2117 ---------------------------------------------------------
 *
 * HP's stock runtime probes this legacy, polled endpoint before its first-use
 * screen accepts touch.  The Linux device tree retains both this endpoint and
 * the Goodix fitted to later G2 hardware.  A bare 43-byte read returns one
 * 12-bit coordinate pair and an additive checksum; 0xffff/0xffff is release.
 */
#define TYPE_PRIME_ILITEK TYPE_PRIME_G2_ILITEK
#define PRIME_ILITEK_PACKET_BYTES 43
OBJECT_DECLARE_SIMPLE_TYPE(PrimeIlitekState, PRIME_ILITEK)
struct PrimeIlitekState {
    I2CSlave parent_obj;
    qemu_irq irq;
    uint16_t ptr;
    uint8_t addr_bytes;
    uint8_t command;
    uint8_t read_index;
    uint8_t reply_len;
    uint8_t packet[PRIME_ILITEK_PACKET_BYTES];
    uint8_t reply[PRIME_ILITEK_PACKET_BYTES];
    bool touching;
    bool present;
    uint16_t release_delay_ms;
    uint16_t step_delay_ms;
    uint16_t start_x, start_y;
    uint16_t end_x, end_y;
    uint8_t move_step, move_steps;
    QEMUTimer *move_timer;
};

static uint16_t prime_ilitek_raw_x(uint16_t x, uint16_t y)
{
    int64_t u = MIN(x, 319), v = MIN(y, 239);
    int64_t value = 120 * 319 * 239 +
        u * (1938 - 120) * 239 + v * (209 - 120) * 319 +
        u * v * (1933 - 1938 - 209 + 120);
    return value / (319 * 239);
}

static uint16_t prime_ilitek_raw_y(uint16_t x, uint16_t y)
{
    int64_t u = MIN(x, 319), v = MIN(y, 239);
    int64_t value = 183 * 319 * 239 +
        u * (164 - 183) * 239 + v * (1848 - 183) * 319 +
        u * v * (1859 - 164 - 1848 + 183);
    return value / (319 * 239);
}

static void prime_ilitek_build_packet(PrimeIlitekState *s)
{
    unsigned i;
    uint8_t sum = 0;

    memset(s->packet, 0, sizeof(s->packet));
    s->packet[0] = 0x5a;
    if (s->touching) {
        int32_t dx = (int32_t)s->end_x - s->start_x;
        int32_t dy = (int32_t)s->end_y - s->start_y;
        uint16_t divisor = MAX(1, s->move_steps);
        uint16_t x = s->start_x + dx * s->move_step / divisor;
        uint16_t y = s->start_y + dy * s->move_step / divisor;
        uint16_t raw_x = prime_ilitek_raw_x(x, y);
        uint16_t raw_y = prime_ilitek_raw_y(x, y);

        s->packet[1] = ((raw_x >> 8) << 4) | (raw_y >> 8);
        s->packet[2] = raw_x;
        s->packet[3] = raw_y;
        s->packet[4] = 0;
    } else {
        memset(&s->packet[1], 0xff, 4);
    }
    for (i = 0; i < PRIME_ILITEK_PACKET_BYTES - 1; i++) {
        sum += s->packet[i];
    }
    s->packet[PRIME_ILITEK_PACKET_BYTES - 1] = -sum;
}

static void prime_ilitek_begin_swipe(PrimeIlitekState *s)
{
    s->move_step = 0;
    s->move_steps = (s->start_x != s->end_x || s->start_y != s->end_y) ? 8 : 0;
    s->step_delay_ms = MAX(1, s->release_delay_ms / (s->move_steps + 1));
    s->touching = true;
    prime_ilitek_build_packet(s);
    qemu_set_irq(s->irq, 1);
    timer_mod(s->move_timer,
              qemu_clock_get_ms(QEMU_CLOCK_VIRTUAL) + s->step_delay_ms);
}

static void prime_ilitek_advance(void *opaque)
{
    PrimeIlitekState *s = opaque;

    if (s->move_step < s->move_steps) {
        s->move_step++;
        prime_ilitek_build_packet(s);
        qemu_set_irq(s->irq, 1);
        timer_mod(s->move_timer,
                  qemu_clock_get_ms(QEMU_CLOCK_VIRTUAL) + s->step_delay_ms);
    } else {
        s->touching = false;
        prime_ilitek_build_packet(s);
        /* A final report containing 0xffff/0xffff releases the contact. */
        qemu_set_irq(s->irq, 1);
    }
}

static void prime_ilitek_prepare_reply(PrimeIlitekState *s)
{
    memset(s->reply, 0, sizeof(s->reply));
    switch (s->command) {
    case 0x03:
        /* Four-byte presence/mode read. 0x5a is ILI2117 application mode.
         * Idle 0xff contact bytes are not part of this command. */
        s->reply[0] = 0x5a;
        s->reply_len = 4;
        break;
    case 0x20:
        s->reply[0] = 0xff;
        s->reply[1] = 0x07;
        s->reply[2] = 0xff;
        s->reply[3] = 0x07;
        s->reply_len = 10;
        break;
    case 0x40:
        s->reply[0] = 0x06;
        s->reply_len = 4;
        break;
    case 0x42:
        s->reply[0] = 0x03;
        s->reply_len = 2;
        break;
    case 0x80:
        s->reply[0] = 0x50;
        s->reply_len = 1;
        break;
    case 0xc0:
        s->reply[0] = 0x5a;
        s->reply_len = 2;
        break;
    default:
        prime_ilitek_build_packet(s);
        memcpy(s->reply, s->packet, PRIME_ILITEK_PACKET_BYTES);
        s->reply_len = PRIME_ILITEK_PACKET_BYTES;
        break;
    }
}

static int prime_ilitek_event(I2CSlave *i2c, enum i2c_event event)
{
    PrimeIlitekState *s = PRIME_ILITEK(i2c);

    if (event == I2C_START_SEND) {
        s->addr_bytes = 1;
        s->command = 0;
    } else if (event == I2C_START_RECV) {
        /* Reading the pending report acknowledges the active-high IRQ. */
        qemu_set_irq(s->irq, 0);
        s->read_index = 0;
        prime_ilitek_prepare_reply(s);
        s->command = 0;
    }
    /* Missing 0x26 endpoint: stock OS continues as "no Ilitek fitted". */
    if (!s->present &&
        (event == I2C_START_SEND || event == I2C_START_RECV)) {
        return 1;
    }
    return 0;
}

static int prime_ilitek_send(I2CSlave *i2c, uint8_t data)
{
    PrimeIlitekState *s = PRIME_ILITEK(i2c);

    if (s->addr_bytes) {
        s->command = data;
        s->addr_bytes = 0;
        return 0;
    }
    /* ILI2117 commands are a single byte. Extra payload is ignored so a
     * guest write cannot collide with the host swipe properties. */
    (void)data;
    return 0;
}

static uint8_t prime_ilitek_recv(I2CSlave *i2c)
{
    PrimeIlitekState *s = PRIME_ILITEK(i2c);
    return s->read_index < s->reply_len ? s->reply[s->read_index++] : 0xff;
}

static void prime_ilitek_init(Object *obj)
{
    PrimeIlitekState *s = PRIME_ILITEK(obj);
    qdev_init_gpio_out_named(DEVICE(obj), &s->irq, "irq", 1);
    s->move_timer = timer_new_ms(QEMU_CLOCK_VIRTUAL,
                                 prime_ilitek_advance, s);
}

static void prime_ilitek_reset(DeviceState *dev)
{
    PrimeIlitekState *s = PRIME_ILITEK(dev);
    s->ptr = 0;
    s->addr_bytes = s->command = s->read_index = s->reply_len = 0;
    s->touching = false;
    s->release_delay_ms = s->step_delay_ms = 0;
    s->start_x = s->start_y = s->end_x = s->end_y = 0;
    s->move_step = s->move_steps = 0;
    timer_del(s->move_timer);
    qemu_set_irq(s->irq, 0);
    prime_ilitek_build_packet(s);
    memcpy(s->reply, s->packet, PRIME_ILITEK_PACKET_BYTES);
    s->reply_len = PRIME_ILITEK_PACKET_BYTES;
}

static uint16_t *prime_ilitek_coord(PrimeIlitekState *s, const char *name)
{
    if (!strcmp(name, "host-x1")) {
        return &s->start_x;
    }
    if (!strcmp(name, "host-y1")) {
        return &s->start_y;
    }
    if (!strcmp(name, "host-x2")) {
        return &s->end_x;
    }
    if (!strcmp(name, "host-y2")) {
        return &s->end_y;
    }
    return &s->release_delay_ms;
}

static void prime_ilitek_get_coord(Object *obj, Visitor *v, const char *name,
                                  void *opaque, Error **errp)
{
    uint16_t value = *prime_ilitek_coord(PRIME_ILITEK(obj), name);

    visit_type_uint16(v, name, &value, errp);
}

static void prime_ilitek_set_coord(Object *obj, Visitor *v, const char *name,
                                  void *opaque, Error **errp)
{
    uint16_t value = 0;

    if (!visit_type_uint16(v, name, &value, errp)) {
        return;
    }
    *prime_ilitek_coord(PRIME_ILITEK(obj), name) = value;
}

static const Property prime_ilitek_properties[] = {
    DEFINE_PROP_BOOL("present", PrimeIlitekState, present, true),
};

static void prime_ilitek_get_host_ms(Object *obj, Visitor *v, const char *name,
                                    void *opaque, Error **errp)
{
    uint16_t value = PRIME_ILITEK(obj)->release_delay_ms;

    visit_type_uint16(v, name, &value, errp);
}

static void prime_ilitek_set_host_ms(Object *obj, Visitor *v, const char *name,
                                    void *opaque, Error **errp)
{
    PrimeIlitekState *s = PRIME_ILITEK(obj);
    uint16_t value = 0;

    if (!visit_type_uint16(v, name, &value, errp)) {
        return;
    }
    s->release_delay_ms = MAX(1, value);
    prime_ilitek_begin_swipe(s);
}

static const VMStateDescription prime_ilitek_vmstate = {
    .name = TYPE_PRIME_G2_ILITEK, .version_id = 2, .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_I2C_SLAVE(parent_obj, PrimeIlitekState),
        VMSTATE_UINT16(ptr, PrimeIlitekState),
        VMSTATE_UINT8(addr_bytes, PrimeIlitekState),
        VMSTATE_UINT8(read_index, PrimeIlitekState),
        VMSTATE_UINT8_ARRAY(packet, PrimeIlitekState,
                            PRIME_ILITEK_PACKET_BYTES),
        VMSTATE_BOOL(touching, PrimeIlitekState),
        VMSTATE_UINT16(release_delay_ms, PrimeIlitekState),
        VMSTATE_UINT16(step_delay_ms, PrimeIlitekState),
        VMSTATE_UINT16(start_x, PrimeIlitekState),
        VMSTATE_UINT16(start_y, PrimeIlitekState),
        VMSTATE_UINT16(end_x, PrimeIlitekState),
        VMSTATE_UINT16(end_y, PrimeIlitekState),
        VMSTATE_UINT8(move_step, PrimeIlitekState),
        VMSTATE_UINT8(move_steps, PrimeIlitekState),
        VMSTATE_TIMER_PTR(move_timer, PrimeIlitekState),
        VMSTATE_UINT8_V(command, PrimeIlitekState, 2),
        VMSTATE_UINT8_V(reply_len, PrimeIlitekState, 2),
        VMSTATE_UINT8_ARRAY_V(reply, PrimeIlitekState,
                              PRIME_ILITEK_PACKET_BYTES, 2),
        VMSTATE_END_OF_LIST()
    },
};

static void prime_ilitek_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);
    I2CSlaveClass *ic = I2C_SLAVE_CLASS(oc);
    dc->vmsd = &prime_ilitek_vmstate;
    device_class_set_legacy_reset(dc, prime_ilitek_reset);
    object_class_property_add(oc, "host-x1", "uint16",
                              prime_ilitek_get_coord, prime_ilitek_set_coord,
                              NULL, NULL);
    object_class_property_add(oc, "host-y1", "uint16",
                              prime_ilitek_get_coord, prime_ilitek_set_coord,
                              NULL, NULL);
    object_class_property_add(oc, "host-x2", "uint16",
                              prime_ilitek_get_coord, prime_ilitek_set_coord,
                              NULL, NULL);
    object_class_property_add(oc, "host-y2", "uint16",
                              prime_ilitek_get_coord, prime_ilitek_set_coord,
                              NULL, NULL);
    object_class_property_add(oc, "host-ms", "uint16",
                              prime_ilitek_get_host_ms,
                              prime_ilitek_set_host_ms,
                              NULL, NULL);
    device_class_set_props(dc, prime_ilitek_properties);
    ic->event = prime_ilitek_event;
    ic->send = prime_ilitek_send;
    ic->recv = prime_ilitek_recv;
}

/* i.MX6ULL ADC1 ---------------------------------------------------------- */
#define TYPE_PRIME_ADC TYPE_PRIME_G2_ADC
OBJECT_DECLARE_SIMPLE_TYPE(PrimeADCState, PRIME_ADC)
struct PrimeADCState {
    SysBusDevice parent_obj;
    MemoryRegion iomem;
    qemu_irq irq;
    uint32_t regs[0x40];
};

static uint16_t prime_battery_model_mv = 3850;

static uint16_t prime_adc_raw_for_mv(uint16_t millivolts)
{
    unsigned raw, best_raw = 0, best_error = UINT_MAX;
    for (raw = 0; raw < 4096; raw++) {
        unsigned converted = ((0x5a3cU * raw) / 5U >> 8) +
                             (raw >= 0xd0 ? 0x2e : 0x16);
        unsigned error = converted > millivolts ?
                         converted - millivolts : millivolts - converted;
        if (error < best_error) {
            best_error = error;
            best_raw = raw;
        }
    }
    return best_raw;
}

static uint64_t prime_adc_read(void *opaque, hwaddr off, unsigned size)
{
    PrimeADCState *s = opaque;
    if (off == 0x0c) {
        s->regs[0x08 >> 2] &= ~1U;
        return prime_adc_raw_for_mv(prime_battery_model_mv);
    }
    return off < 0x100 ? s->regs[off >> 2] : 0;
}

static void prime_adc_write(void *opaque, hwaddr off, uint64_t value,
                            unsigned size)
{
    PrimeADCState *s = opaque;
    if (off >= 0x100) {
        return;
    }
    switch (off) {
    case 0x00: /* HC0: selecting ADC1_IN1 starts a conversion. */
        s->regs[off >> 2] = value;
        if ((value & 0x1f) == 1) {
            s->regs[0x0c >> 2] = prime_adc_raw_for_mv(prime_battery_model_mv);
            s->regs[0x08 >> 2] |= 1U;
            qemu_set_irq(s->irq, (value & (1U << 7)) != 0);
        }
        break;
    case 0x18: /* GC calibration completes deterministically without CALF. */
        s->regs[off >> 2] = value & ~(1U << 7);
        s->regs[0x1c >> 2] &= ~(1U << 1);
        break;
    case 0x1c: /* GS CALF is write-one-to-clear. */
        s->regs[off >> 2] &= ~value;
        break;
    default:
        s->regs[off >> 2] = value;
        break;
    }
}

static const MemoryRegionOps prime_adc_ops = {
    .read = prime_adc_read,
    .write = prime_adc_write,
    .endianness = DEVICE_NATIVE_ENDIAN,
    .valid = { .min_access_size = 4, .max_access_size = 4 },
};

static void prime_adc_reset(DeviceState *dev)
{
    PrimeADCState *s = PRIME_ADC(dev);
    memset(s->regs, 0, sizeof(s->regs));
    qemu_set_irq(s->irq, 0);
}

static void prime_adc_realize(DeviceState *dev, Error **errp)
{
    PrimeADCState *s = PRIME_ADC(dev);
    memory_region_init_io(&s->iomem, OBJECT(dev), &prime_adc_ops, s,
                          "prime-g2-adc1", 0x100);
    sysbus_init_mmio(SYS_BUS_DEVICE(dev), &s->iomem);
    sysbus_init_irq(SYS_BUS_DEVICE(dev), &s->irq);
}

static const VMStateDescription prime_adc_vmstate = {
    .name = TYPE_PRIME_G2_ADC, .version_id = 1, .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT32_ARRAY(regs, PrimeADCState, 0x40),
        VMSTATE_END_OF_LIST()
    },
};

static void prime_adc_class_init(ObjectClass *oc, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(oc);
    dc->realize = prime_adc_realize;
    dc->vmsd = &prime_adc_vmstate;
    device_class_set_legacy_reset(dc, prime_adc_reset);
}

/* NXP PF1550 ------------------------------------------------------------- */
#define TYPE_PRIME_PF1550 TYPE_PRIME_G2_PF1550
OBJECT_DECLARE_SIMPLE_TYPE(PrimePF1550State, PRIME_PF1550)
struct PrimePF1550State {
    I2CSlave parent_obj; uint8_t ptr; bool expect_ptr; qemu_irq irq;
    uint16_t millivolts; uint8_t level; bool charging, external_power;
    uint32_t energy_remainder_ms; uint8_t regs[256];
};
static void prime_pf_update(PrimePF1550State *s)
{
    bool external_power;
    bool charger_enabled;
    s->level = s->regs[0xf0] & 3;
    s->millivolts = s->regs[0xf1] | s->regs[0xf2] << 8;
    prime_battery_model_mv = s->millivolts;
    external_power = s->regs[0xf3] != 0;
    charger_enabled = (s->regs[0x89] & 3) == 2;
    s->charging = external_power && charger_enabled && s->level != 0 &&
                  s->level != 3;
    /* VBUS_SNS: unplugged hardware reports UVLO and IN2SYS, not a retained
     * VBUS_VALID bit.  Model that transition so firmware tests use the same
     * mutually exclusive sense bits as the physical PF1550. */
    s->regs[0x86] = external_power ? 0x20 : 0x0c;
    s->regs[0x87] = s->charging ? 1 :
                    (external_power && charger_enabled && s->level == 3 ? 4 : 8);
    s->regs[0x88] = s->level == 0 ? 6 : (s->level == 1 ? 1 : 4);
    s->regs[0x80] |= (1u << 3) | (1u << 5);
    qemu_set_irq(s->irq, 0);
}
static void prime_pf_advance(PrimePF1550State *s)
{
    uint32_t elapsed = ldl_le_p(&s->regs[0xf5]) + s->energy_remainder_ms;
    uint32_t interval = s->charging ? 10000 :
                        (s->regs[0xf4] == 1 ? 3600000 : 60000);
    uint32_t delta = elapsed / interval;
    s->energy_remainder_ms = elapsed % interval;
    if (s->charging) s->millivolts = MIN(4200, s->millivolts + delta);
    else s->millivolts = MAX(3000, (int)s->millivolts - (int)delta);
    s->level = s->millivolts <= 3350 ? 0 : s->millivolts <= 3550 ? 1 :
               s->millivolts >= 4180 ? 3 : 2;
    s->regs[0xf0] = s->level;
    s->regs[0xf1] = s->millivolts;
    s->regs[0xf2] = s->millivolts >> 8;
    prime_pf_update(s);
}
static void prime_pf_init(Object *obj)
{
    PrimePF1550State *s = PRIME_PF1550(obj);
    qdev_init_gpio_out_named(DEVICE(obj), &s->irq, "irq", 1);
}
static int prime_pf_event(I2CSlave *i2c, enum i2c_event event)
{ PrimePF1550State *s = PRIME_PF1550(i2c); if (event == I2C_START_SEND) s->expect_ptr = true; return 0; }
static int prime_pf_send(I2CSlave *i2c, uint8_t data)
{ PrimePF1550State *s = PRIME_PF1550(i2c); if (s->expect_ptr) { s->ptr=data; s->expect_ptr=false; } else { uint8_t reg=s->ptr++; s->regs[reg]=data; if(reg==0x89||reg==0xf3)prime_pf_update(s); if(reg==0xf8)prime_pf_advance(s); if(reg==0x80){s->regs[0x80]&=~data;qemu_set_irq(s->irq,1);} } return 0; }
static uint8_t prime_pf_recv(I2CSlave *i2c)
{ PrimePF1550State *s = PRIME_PF1550(i2c); return s->regs[s->ptr++]; }
static void prime_pf_reset(DeviceState *dev)
{
    PrimePF1550State *s = PRIME_PF1550(dev); memset(s->regs, 0, sizeof(s->regs));
    s->ptr=0; s->expect_ptr=false;
    s->regs[0x00]=0x7c; /* PF1550 device-family ID reset value. */
    s->regs[0x59]=0x80; /* PWRCTRL1: ONKEY_RST_EN reset value. */
    s->regs[0x89]=0x01; /* CHG_OPER reset mode 1: battery charger off. */
    /* Deliberately cold/unconfigured panel rail. Native firmware must set
     * LDO1 to 3.3 V and enable RUN+standby rather than inheriting Linux. */
    s->regs[0x4c]=0x10; s->regs[0x4d]=0x00;
    s->regs[0xf0]=2; s->regs[0xf1]=3850&0xff; s->regs[0xf2]=3850>>8;
    s->regs[0xf3]=s->external_power; s->regs[0xf4]=0; s->energy_remainder_ms=0;
    prime_pf_update(s); s->regs[0x80]=0; qemu_set_irq(s->irq,1);
}
static const VMStateDescription prime_pf_vmstate = {
    .name=TYPE_PRIME_G2_PF1550, .version_id=2, .minimum_version_id=1,
    .fields=(const VMStateField[]){ VMSTATE_I2C_SLAVE(parent_obj, PrimePF1550State),
        VMSTATE_UINT8(ptr, PrimePF1550State), VMSTATE_BOOL(expect_ptr, PrimePF1550State),
        VMSTATE_UINT16(millivolts, PrimePF1550State), VMSTATE_UINT8(level, PrimePF1550State),
        VMSTATE_BOOL(charging, PrimePF1550State),
        VMSTATE_BOOL_V(external_power, PrimePF1550State, 2),
        VMSTATE_UINT32(energy_remainder_ms, PrimePF1550State),
        VMSTATE_UINT8_ARRAY(regs, PrimePF1550State, 256), VMSTATE_END_OF_LIST() },
};
static const Property prime_pf_properties[] = {
    DEFINE_PROP_BOOL("external-power", PrimePF1550State, external_power, false),
};
static void prime_pf_class_init(ObjectClass *oc, const void *data)
{ DeviceClass *dc=DEVICE_CLASS(oc); I2CSlaveClass *ic=I2C_SLAVE_CLASS(oc);
  dc->vmsd=&prime_pf_vmstate; device_class_set_legacy_reset(dc, prime_pf_reset);
  device_class_set_props(dc, prime_pf_properties);
  ic->event=prime_pf_event; ic->send=prime_pf_send; ic->recv=prime_pf_recv; }

/* GPMI/BCH NAND ---------------------------------------------------------- */
#define TYPE_PRIME_NAND TYPE_PRIME_G2_NAND
/* The overlay must hold more than one legacy 8 MiB Lefony slot. HP's signed
 * maintenance package writes the OS, updater, and bundled filesystem content
 * in one transaction; a 4096-page (8 MiB) overlay filled mid-update and made
 * every subsequent program operation look like a bad NAND block. 65536 pages
 * keeps the VM sparse while covering HP's multi-copy/filesystem update work. */
#define PRIME_NAND_SPARSE_PAGES 65536
#define PRIME_NAND_PAGE_BYTES (2048 + 64)
#define PRIME_NAND_BLOCKS 4096
#define PRIME_NAND_TOTAL_PAGES (PRIME_NAND_BLOCKS * 64)
OBJECT_DECLARE_SIMPLE_TYPE(PrimeNANDState, PRIME_NAND)
struct PrimeNANDState {
    SysBusDevice parent_obj; MemoryRegion gpmi, bch, apbh;
    qemu_irq gpmi_irq, bch_irq, apbh_irq;
    uint32_t gpmi_regs[0x80], bch_regs[0x80]; uint8_t id[5]; uint8_t status;
    uint32_t apbh_ctrl[4], apbh_next, apbh_bar, apbh_sema;
    uint32_t apbh_cmd;
    QEMUTimer *ready_timer;
    uint32_t gpmi_clock_hz; /* optional isolated-test override */
    Clock *gpmi_clock, *bch_clock;
    uint8_t dma_clock_blocked;
    bool use_ccm_clock;
    uint64_t wait_nano_cycles;
    int64_t wait_clock_ns;
    uint32_t wait_clock_hz;
    bool nand_ready, wait_pending, wait_completed, sense_failed;
    uint32_t last_descriptor, last_dma_buffer, last_ecc_payload, nand_command_count;
    uint32_t overlay_pages_used, program_failures, program_out_of_range;
    uint32_t program_overlay_full, ecc_write_count;
    uint8_t command, id_cursor, address_count; uint16_t column; uint32_t page;
    uint8_t page_cache[PRIME_NAND_PAGE_BYTES]; bool page_cache_valid;
    char *stock_nand_path, *stock_overlay_path, *onfi_parameters_path;
    GMappedFile *stock_nand;
    uint8_t onfi_parameters[256]; bool onfi_enabled;
    bool physical_pages;
    PrimeBCH *codecs[2][21]; /* immutable arithmetic cache, not migrated */
    uint8_t corrected_bits, fault_kind, fault_mask; uint16_t fault_offset;
    uint32_t fault_page; bool uncorrectable, initialized;
    uint16_t wear_limit, read_disturb_limit;
    uint32_t page_tags[PRIME_NAND_SPARSE_PAGES];
    uint8_t page_used[PRIME_NAND_SPARSE_PAGES];
    uint8_t program_counts[PRIME_NAND_SPARSE_PAGES];
    uint16_t read_counts[PRIME_NAND_SPARSE_PAGES];
    uint8_t page_data[PRIME_NAND_SPARSE_PAGES * PRIME_NAND_PAGE_BYTES];
    uint8_t bad_blocks[PRIME_NAND_BLOCKS / 8];
    uint8_t erased_blocks[PRIME_NAND_BLOCKS / 8];
    uint16_t erase_counts[PRIME_NAND_BLOCKS];
};

#define APBH_CTRL0 0x000
#define APBH_BLOCK_SFTRST (1u << 31)
#define APBH_BLOCK_CLKGATE (1u << 30)
#define APBH_CTRL1 0x010
#define APBH_CTRL2 0x020
#define APBH_CHANNEL_CTRL 0x030
#define APBH_CH0_CURCMDAR 0x100
#define APBH_CH0_NXTCMDAR 0x110
#define APBH_CH0_CMD 0x120
#define APBH_CH0_BAR 0x130
#define APBH_CH0_SEMA 0x140

#define APBH_CCW_COMMAND_MASK 0x3
#define APBH_CCW_CHAIN (1u << 2)
#define APBH_CCW_IRQ (1u << 3)
#define APBH_CCW_DEC_SEM (1u << 6)
#define APBH_CCW_PIO_SHIFT 12
#define APBH_CCW_PIO_MASK 0xf

#define APBH_CMD_NO_XFER 0
#define APBH_CMD_DEV_TO_MEM 1
#define APBH_CMD_MEM_TO_DEV 2
#define APBH_CMD_SENSE 3

#define GPMI_MODE(ctrl0) (((ctrl0) >> 24) & 3)
#define GPMI_ADDRESS(ctrl0) (((ctrl0) >> 17) & 3)
#define GPMI_ADDRESS_INCREMENT (1u << 16)
#define GPMI_MODE_WRITE 0
#define GPMI_MODE_READ 1
#define GPMI_MODE_READ_COMPARE 2
#define GPMI_MODE_WAIT_READY 3
#define GPMI_ADDRESS_DATA 0
#define GPMI_ADDRESS_CLE 1
#define GPMI_ADDRESS_ALE 2
#define GPMI_ECC_ENABLE (1u << 12)

/* nanddump's 2112-byte records contain 2048 bytes already decoded by the
 * recovery kernel followed by 64 conventional OOB bytes. Feed that decoded
 * payload to the emulated BCH path unchanged. No private bytes are embedded. */
#define PRIME_CAPTURE_METADATA_BYTES 10
#define PRIME_NAND_CHUNKS 4
#define PRIME_NAND_OVERLAY_MAGIC "PG2OVL1\n"
#define PRIME_NAND_PHYSICAL_OVERLAY_MAGIC "PG2RAW1\n"
#define PRIME_NAND_OVERLAY_MAGIC_BYTES 8
#define PRIME_NAND_OVERLAY_PROGRAM 1
#define PRIME_NAND_OVERLAY_ERASE 2

/* i.MX6ULL ROM NAND boot structures as they appear in a Linux GPMI
 * nanddump --noecc --oob capture.  The ROM's BCH-40 FCB payload begins 22
 * bytes into that projected page; ordinary firmware pages expose their
 * decoded 2 KiB payload at byte zero. */
#define PRIME_ROM_FCB_OFFSET 22
#define PRIME_ROM_FCB_FINGERPRINT 0x20424346u
#define PRIME_ROM_FCB_VERSION 0x01000000u
#define PRIME_ROM_DBBT_FINGERPRINT 0x54424244u
#define PRIME_ROM_IVT_HEADER 0x402000d1u
#define PRIME_ROM_IVT_OFFSET 0x400u
#define PRIME_ROM_FCB_COPIES 4
#define PRIME_ROM_MAX_BOOT_PAGES 2048
#define PRIME_ROM_DCD_HEADER_TAG 0xd2
#define PRIME_ROM_DCD_WRITE_TAG 0xcc
#define PRIME_ROM_DCD_VERSION 0x40

static void prime_nand_decode_stock_record(const uint8_t *record,
                                           uint8_t *destination)
{
  memcpy(destination,record,PRIME_NAND_PAGE_BYTES);
}

static void prime_nand_backing_page(PrimeNANDState *s, uint32_t page,
                                    uint8_t *destination)
{
  unsigned block=page/64;
  if(page>=PRIME_NAND_TOTAL_PAGES||
     (s->erased_blocks[block/8]&(1u<<(block&7)))||!s->stock_nand){
    memset(destination,0xff,PRIME_NAND_PAGE_BYTES);return;
  }
  prime_nand_decode_stock_record(
    (const uint8_t*)g_mapped_file_get_contents(s->stock_nand)+
      (size_t)page*PRIME_NAND_PAGE_BYTES,destination);
}
static int prime_nand_find(PrimeNANDState *s, uint32_t page, bool create)
{
  unsigned start=page%PRIME_NAND_SPARSE_PAGES,i;
  for(i=0;i<PRIME_NAND_SPARSE_PAGES;i++){
    unsigned slot=(start+i)%PRIME_NAND_SPARSE_PAGES;
    if(s->page_used[slot]&&s->page_tags[slot]==page)return slot;
    if(!s->page_used[slot]){
      if(!create)return -1;
      s->page_used[slot]=1;s->page_tags[slot]=page;
      s->overlay_pages_used++;
      prime_nand_backing_page(s,page,&s->page_data[slot*PRIME_NAND_PAGE_BYTES]);
      return slot;
    }
  }
  return -1;
}

/* A private stock-update run can be resumed by a later normal-OS VM without
 * ever modifying the captured raw+OOB source.  The sidecar is an append-only
 * journal: a torn final record is ignored, while every complete program or
 * erase record is replayed in order.  It contains private NAND bytes and is
 * therefore only enabled when the caller explicitly supplies a path under the
 * ignored fixture directory. */
static bool prime_nand_overlay_append(PrimeNANDState *s, uint8_t type,
                                      uint32_t index, const uint8_t *payload)
{
  uint8_t header[8]={type,0,0,0};FILE *file;size_t payload_bytes=0;
  if(!s->stock_overlay_path)return true;
  stl_le_p(header+4,index);
  file=fopen(s->stock_overlay_path,"ab");
  if(!file){qemu_log_mask(LOG_GUEST_ERROR,
      "prime-g2-nand: cannot append private overlay '%s': %s\n",
      s->stock_overlay_path,strerror(errno));return false;}
  if(type==PRIME_NAND_OVERLAY_PROGRAM)payload_bytes=PRIME_NAND_PAGE_BYTES;
  if(fwrite(header,1,sizeof(header),file)!=sizeof(header)||
     (payload_bytes&&fwrite(payload,1,payload_bytes,file)!=payload_bytes)||
     fflush(file)!=0){qemu_log_mask(LOG_GUEST_ERROR,
      "prime-g2-nand: cannot persist private overlay '%s': %s\n",
      s->stock_overlay_path,strerror(errno));fclose(file);return false;}
  fclose(file);return true;
}

static bool prime_nand_overlay_replay(PrimeNANDState *s, Error **errp)
{
  gchar *contents=NULL;gsize length=0,offset=PRIME_NAND_OVERLAY_MAGIC_BYTES;
  GError *file_error=NULL;
  if(!s->stock_overlay_path)return true;
  if(!g_file_test(s->stock_overlay_path,G_FILE_TEST_EXISTS)){
    if(!g_file_set_contents(s->stock_overlay_path,s->physical_pages?
                            PRIME_NAND_PHYSICAL_OVERLAY_MAGIC:PRIME_NAND_OVERLAY_MAGIC,
                            PRIME_NAND_OVERLAY_MAGIC_BYTES,&file_error)){
      error_setg(errp,"cannot create private NAND overlay '%s': %s",
                 s->stock_overlay_path,file_error->message);
      g_error_free(file_error);return false;
    }
    return true;
  }
  if(!g_file_get_contents(s->stock_overlay_path,&contents,&length,&file_error)){
    error_setg(errp,"cannot read private NAND overlay '%s': %s",
               s->stock_overlay_path,file_error->message);
    g_error_free(file_error);return false;
  }
  if(length<PRIME_NAND_OVERLAY_MAGIC_BYTES||
     memcmp(contents,s->physical_pages?PRIME_NAND_PHYSICAL_OVERLAY_MAGIC:PRIME_NAND_OVERLAY_MAGIC,
            PRIME_NAND_OVERLAY_MAGIC_BYTES)!=0){
    error_setg(errp,"private NAND overlay '%s' has an invalid header",
               s->stock_overlay_path);g_free(contents);return false;
  }
  while(offset+8<=length){
    const uint8_t *record=(const uint8_t*)contents+offset;
    uint8_t type=record[0];uint32_t index=ldl_le_p(record+4);int slot;
    offset+=8;
    if(type==PRIME_NAND_OVERLAY_PROGRAM){
      if(index>=PRIME_NAND_TOTAL_PAGES||offset+PRIME_NAND_PAGE_BYTES>length)break;
      slot=prime_nand_find(s,index,true);
      if(slot<0){error_setg(errp,"private NAND overlay exceeds sparse capacity");
        g_free(contents);return false;}
      memcpy(&s->page_data[slot*PRIME_NAND_PAGE_BYTES],contents+offset,
             PRIME_NAND_PAGE_BYTES);
      s->program_counts[slot]=1;offset+=PRIME_NAND_PAGE_BYTES;
    }else if(type==PRIME_NAND_OVERLAY_ERASE){
      unsigned i;
      if(index>=PRIME_NAND_BLOCKS)break;
      s->erased_blocks[index/8]|=1u<<(index&7);
      for(i=0;i<PRIME_NAND_SPARSE_PAGES;i++)
        if(s->page_used[i]&&s->page_tags[i]/64==index){
          s->page_used[i]=0;if(s->overlay_pages_used)s->overlay_pages_used--;
          s->program_counts[i]=0;s->read_counts[i]=0;
        }
    }else break;
  }
  if(offset!=length)qemu_log_mask(LOG_GUEST_ERROR,
    "prime-g2-nand: ignoring torn private overlay tail in '%s'\n",
    s->stock_overlay_path);
  g_free(contents);return true;
}
static bool prime_nand_bad(PrimeNANDState*s,uint32_t page)
{unsigned block=page/64,index;const uint8_t *stock;
 if(block>=PRIME_NAND_BLOCKS)return true;
 if(s->bad_blocks[block/8]&(1u<<(block&7)))return true;
 /* Large-page NAND marks a factory/runtime bad block in the OOB
  * of either of its first two pages.  The private fixture is a Linux
  * nanddump --oob stream, so those marker bytes are already available and
  * must affect both Boot ROM and guest-controller reads. */
 stock=s->stock_nand?(const uint8_t*)g_mapped_file_get_contents(s->stock_nand):NULL;
 for(index=0;index<2;index++){
   unsigned number=block*64+index;int slot=prime_nand_find(s,number,false);
   if(slot>=0){
     if(s->page_data[slot*PRIME_NAND_PAGE_BYTES+2048]!=0xff)return true;
   }else if(stock&&!(s->erased_blocks[block/8]&(1u<<(block&7)))){
     if(stock[(size_t)number*PRIME_NAND_PAGE_BYTES+2048]!=0xff)return true;
   }
 }
 return false;}
static void prime_nand_load_page(PrimeNANDState*s)
{int slot=prime_nand_find(s,s->page,false);s->corrected_bits=0;s->uncorrectable=false;
 if(slot<0)prime_nand_backing_page(s,s->page,s->page_cache);
 else {memcpy(s->page_cache,&s->page_data[slot*PRIME_NAND_PAGE_BYTES],PRIME_NAND_PAGE_BYTES);
  if(s->read_counts[slot]!=0xffff)s->read_counts[slot]++;
  if(s->read_counts[slot]>s->read_disturb_limit){s->uncorrectable=true;s->page_cache[0]^=1;}}
 if(s->fault_page==s->page&&s->fault_kind){unsigned off=MIN(s->fault_offset,PRIME_NAND_PAGE_BYTES-1);
  if(s->physical_pages)s->page_cache[off]^=s->fault_mask;
  else if(s->fault_kind==1)s->corrected_bits=ctpop8(s->fault_mask);
  else {s->page_cache[off]^=s->fault_mask;s->uncorrectable=true;}}
 s->page_cache_valid=true;}

static PrimeNANDState *prime_nand_instance(void)
{
  Object *obj=object_resolve_path_type("",TYPE_PRIME_G2_NAND,NULL);
  return obj?PRIME_NAND(obj):NULL;
}

bool prime_g2_nand_has_backing(void)
{
  PrimeNANDState *s=prime_nand_instance();
  return s&&s->stock_nand;
}

static bool prime_rom_read_page_internal(PrimeNANDState *s,uint32_t page,
                                         uint8_t *data,bool scan_marker)
{
  int slot;
  if(page>=PRIME_NAND_TOTAL_PAGES||(scan_marker&&prime_nand_bad(s,page)))return false;
  slot=prime_nand_find(s,page,false);
  if(slot<0)prime_nand_backing_page(s,page,data);
  else memcpy(data,&s->page_data[slot*PRIME_NAND_PAGE_BYTES],
              PRIME_NAND_PAGE_BYTES);
  return true;
}

static bool prime_rom_read_page(PrimeNANDState *s,uint32_t page,uint8_t *data)
{
  return prime_rom_read_page_internal(s,page,data,true);
}

static bool prime_rom_fcb_valid(const uint8_t *page)
{
  const uint8_t *fcb=page+PRIME_ROM_FCB_OFFSET;
  return ldl_le_p(fcb+0x04)==PRIME_ROM_FCB_FINGERPRINT&&
         ldl_le_p(fcb+0x08)==PRIME_ROM_FCB_VERSION&&
         ldl_le_p(fcb+0x14)==2048&&ldl_le_p(fcb+0x18)==2112&&
         ldl_le_p(fcb+0x1c)==64;
}

static uint8_t prime_bch_reverse(uint8_t byte);
static bool prime_nand_capture_layout(PrimeNANDState *s,unsigned *metadata,
                                      unsigned *chunks,unsigned *marker);
static void prime_nand_swap_marker(uint8_t *payload,uint8_t *aux,unsigned bit);
static bool prime_nand_bch_transfer(PrimeNANDState *s,bool encode,
                                    uint8_t *payload,uint8_t *aux);

/* i.MX6ULL FCB: 32 reserved bytes, then eight 128-byte blocks, each with
 * 65 parity bytes (GF13 BCH-40). This differs from ordinary firmware ECC. */
static bool prime_rom_decode_fcb(PrimeNANDState *s,uint8_t *page)
{
  uint8_t fcb[1024],parity[65];unsigned block,j,corrected=0;uint32_t sum=0;
  PrimeBCH **bch=&s->codecs[0][20];
  if(!*bch)*bch=prime_bch_new(13,40,0x201b);
  if(!*bch)return false;
  for(block=0;block<8;block++){
    unsigned start=32+block*193;int result;
    for(j=0;j<128;j++)fcb[block*128+j]=prime_bch_reverse(page[start+j]);
    for(j=0;j<65;j++)parity[j]=prime_bch_reverse(page[start+128+j]);
    result=prime_bch_decode(*bch,fcb+block*128,128,parity,NULL);
    if(result<0)return false;
    corrected+=result;
    for(j=0;j<128;j++)fcb[block*128+j]=prime_bch_reverse(fcb[block*128+j]);
  }
  for(j=4;j<sizeof(fcb);j++)sum+=fcb[j];
  if(ldl_le_p(fcb)!=~sum)return false;
  memset(page,0xff,PRIME_NAND_PAGE_BYTES);
  memcpy(page+PRIME_ROM_FCB_OFFSET,fcb,sizeof(fcb));
  qemu_log("hp-prime-g2-rom: FCB BCH-40/checksum valid; corrected %u bits\n",corrected);
  return true;
}

static bool prime_rom_configure_bch(PrimeNANDState *s,const uint8_t *fcb)
{
  uint32_t eccn=ldl_le_p(fcb+0x2c),first=ldl_le_p(fcb+0x30);
  uint32_t size=ldl_le_p(fcb+0x34),ecc0=ldl_le_p(fcb+0x38);
  uint32_t meta=ldl_le_p(fcb+0x3c),blocks=ldl_le_p(fcb+0x40);
  uint32_t gf=ldl_le_p(fcb+0x88);
  unsigned metadata,chunks,marker,page_bytes;
  if(eccn>20||ecc0>20||meta>255||blocks>255||gf>1||
     first>4092||size>4092||(first&3)||(size&3))return false;
  /* ROM transfers only the interleaved codewords, not the unused spare
   * tail. The physical Prime capture uses 2071 bytes for its BCH-2 FCB
   * geometry, while the NAND backing record remains 2048+64 bytes. */
  page_bytes=((meta+first+blocks*size)*8+
              (ecc0+blocks*eccn)*2*(13+gf)+7)/8;
  if(page_bytes>PRIME_NAND_PAGE_BYTES)return false;
  s->bch_regs[8]=(blocks<<24)|(meta<<16)|(ecc0<<11)|(gf<<10)|(first/4);
  s->bch_regs[9]=(page_bytes<<16)|(eccn<<11)|(gf<<10)|(size/4);
  if(!prime_nand_capture_layout(s,&metadata,&chunks,&marker))return false;
  /* This board's boot path uses swapping, not the i.MX23 transcription
   * mode. Reject unsupported swap modes instead of guessing at the layout. */
  if(ldl_le_p(fcb+0xac)||ldl_le_p(fcb+0x84)!=2048||
     ldl_le_p(fcb+0x80)>7||ldl_le_p(fcb+0x7c)>=2048||
     ldl_le_p(fcb+0x7c)*8+ldl_le_p(fcb+0x80)!=marker)return false;
  /* fcb_block.erase_th at 0x5c is the ROM BCH_MODE configuration,
   * not the SDK ECC geometry. Only ERASE_THRESHOLD[7:0] is defined. */
  s->bch_regs[2]=ldl_le_p(fcb+0x5c)&0xff;
  qemu_log("hp-prime-g2-rom: FCB configured BCH layout %08x/%08x\n",
           s->bch_regs[8],s->bch_regs[9]);
  return true;
}

static bool prime_rom_decode_data(PrimeNANDState *s,uint32_t number,uint8_t *page)
{
  uint8_t aux[64];unsigned metadata,chunks,marker;
  if(!s->physical_pages)return true;
  if(!prime_nand_capture_layout(s,&metadata,&chunks,&marker))return false;
  memcpy(s->page_cache,page,PRIME_NAND_PAGE_BYTES);
  if(!prime_nand_bch_transfer(s,false,page,aux)||s->uncorrectable)return false;
  prime_nand_swap_marker(page,aux,marker);
  memcpy(page+2048,aux,metadata);
  if(s->corrected_bits)qemu_log("hp-prime-g2-rom: BCH corrected %u bits at NAND page %u\n",
                              s->corrected_bits,number);
  return true;
}

static bool prime_rom_dbbt_load(PrimeNANDState *s,uint32_t start,uint8_t *bad)
{
  uint8_t page[PRIME_NAND_PAGE_BYTES],candidate_bad[PRIME_NAND_BLOCKS/8];unsigned copy;
  for(copy=0;copy<PRIME_ROM_FCB_COPIES;copy++){
    uint64_t address=(uint64_t)start+copy*64;uint32_t count=0,pages,j;
    if(address>=PRIME_NAND_TOTAL_PAGES)break;
    if(!prime_rom_read_page(s,address,page)||!prime_rom_decode_data(s,address,page)||
       ldl_le_p(page+4)!=PRIME_ROM_DBBT_FINGERPRINT||
       ldl_le_p(page+8)!=PRIME_ROM_FCB_VERSION)continue;
    /* i.MX6 checksum and header numberbb fields are reserved. The actual
     * count lives in BBTN, four pages after this header, not in page+0x0c.
     * Prime's single-NAND kobs/U-Boot format uses zero or one BBTN page. */
    pages=ldl_le_p(page+0x10);memset(candidate_bad,0,sizeof(candidate_bad));
    if(pages>1){
      qemu_log("hp-prime-g2-rom: DBBT copy %u has unsupported BBTN page count %u\n",copy,pages);
      continue;
    }
    if(pages){
      if(address+4>=PRIME_NAND_TOTAL_PAGES||
         !prime_rom_read_page(s,address+4,page)||!prime_rom_decode_data(s,address+4,page))continue;
      count=ldl_le_p(page+4);
      if(ldl_le_p(page)!=0||count>(2048-8)/4){
        qemu_log("hp-prime-g2-rom: DBBT copy %u has invalid NAND/count fields\n",copy);
        continue;
      }
      for(j=0;j<count;j++){
        uint32_t block=ldl_le_p(page+8+j*4);
        if(block>=PRIME_NAND_BLOCKS)break;
        candidate_bad[block/8]|=1u<<(block%8);
      }
      if(j!=count){
        qemu_log("hp-prime-g2-rom: DBBT copy %u has an out-of-range block\n",copy);
        continue;
      }
    }
    /* Publish only after the complete candidate is decoded and validated.
     * Never contaminate a later copy or the physical NAND bad-block flags. */
    memcpy(bad,candidate_bad,sizeof(candidate_bad));
    qemu_log("hp-prime-g2-rom: selected DBBT copy %u with %u bad-block entries\n",copy,count);
    return true;
  }
  return false;
}

static bool prime_rom_execute_dcd(const uint8_t *image, uint32_t image_bytes,
                                  uint32_t image_start, uint32_t dcd,
                                  Error **errp)
{
  uint32_t offset, end;

  if(!dcd)return true;
  if(dcd<image_start){
    error_setg(errp,"NAND DCD pointer precedes the boot image");return false;
  }
  offset=dcd-image_start;
  if((uint64_t)offset+4>image_bytes||
     image[offset]!=PRIME_ROM_DCD_HEADER_TAG||
     image[offset+3]!=PRIME_ROM_DCD_VERSION){
    error_setg(errp,"NAND boot stream has an invalid DCD header");return false;
  }
  end=offset+lduw_be_p(image+offset+1);
  if(end<offset+4||end>image_bytes){
    error_setg(errp,"NAND DCD length is outside the boot image");return false;
  }
  offset+=4;
  while(offset<end){
    uint32_t command_end;uint16_t length;uint8_t parameter;
    if(end-offset<4){
      error_setg(errp,"NAND DCD contains a truncated command");return false;
    }
    length=lduw_be_p(image+offset+1);parameter=image[offset+3];
    command_end=offset+length;
    /* The Prime's production image contains one HAB Write Data command with
     * 32-bit address/value pairs.  Rejecting every other command or width is
     * intentional: silently skipping DCD operations would create a launch
     * state which cannot occur on the physical i.MX6ULL Boot ROM. */
    if(image[offset]!=PRIME_ROM_DCD_WRITE_TAG||parameter!=4||length<12||
       ((length-4)&7)||command_end<offset||command_end>end){
      error_setg(errp,"NAND DCD contains an unsupported command");return false;
    }
    offset+=4;
    while(offset<command_end){
      uint32_t address=ldl_be_p(image+offset);
      uint32_t value=ldl_be_p(image+offset+4);uint8_t encoded[4];
      MemTxResult result;
      stl_le_p(encoded,value);
      result=address_space_write(&address_space_memory,address,
                                 MEMTXATTRS_UNSPECIFIED,encoded,sizeof(encoded));
      if(result!=MEMTX_OK){
        error_setg(errp,"NAND DCD write to 0x%08x failed",address);return false;
      }
      offset+=8;
    }
  }
  qemu_log("hp-prime-g2-rom: executed i.MX DCD through 0x%08x\n",dcd);
  return true;
}

/* Decode only bytes actually received. A true result with !prepared means
 * more header/DCD pages are needed, not that unreceived bytes are valid. */
static bool prime_rom_prepare_firmware(const uint8_t *image, uint32_t available,
                                       uint32_t image_bytes, bool *prepared,
                                       uint32_t *start, uint32_t *size,
                                       uint32_t *entry, Error **errp)
{
  uint32_t ivt_header,ivt_entry,dcd,boot_data,self;
  uint32_t boot_start,boot_size,plugin,boot_data_offset;
  if(available<PRIME_ROM_IVT_OFFSET+0x20)return true;
  ivt_header=ldl_le_p(image+PRIME_ROM_IVT_OFFSET+0x00);
  ivt_entry=ldl_le_p(image+PRIME_ROM_IVT_OFFSET+0x04);
  dcd=ldl_le_p(image+PRIME_ROM_IVT_OFFSET+0x0c);
  boot_data=ldl_le_p(image+PRIME_ROM_IVT_OFFSET+0x10);
  self=ldl_le_p(image+PRIME_ROM_IVT_OFFSET+0x14);
  if(ivt_header!=PRIME_ROM_IVT_HEADER||self<PRIME_ROM_IVT_OFFSET||
     boot_data<self-PRIME_ROM_IVT_OFFSET){
    error_setg(errp,"NAND boot stream has an invalid i.MX IVT");return false;
  }
  boot_data_offset=boot_data-(self-PRIME_ROM_IVT_OFFSET);
  if((uint64_t)boot_data_offset+12>image_bytes){
    error_setg(errp,"NAND IVT boot-data pointer is out of range");return false;
  }
  if((uint64_t)boot_data_offset+12>available)return true;
  boot_start=ldl_le_p(image+boot_data_offset+0x00);
  boot_size=ldl_le_p(image+boot_data_offset+0x04);
  plugin=ldl_le_p(image+boot_data_offset+0x08);
  if(plugin||boot_start!=self-PRIME_ROM_IVT_OFFSET||!boot_size||
     boot_size>image_bytes||ivt_entry<boot_start||
     (uint64_t)boot_start+boot_size>UINT32_MAX||
     ivt_entry>=(uint64_t)boot_start+boot_size||
     (dcd&&(dcd<boot_start||dcd>=(uint64_t)boot_start+boot_size))){
    error_setg(errp,"NAND IVT boot-data bounds are invalid");return false;
  }
  if(dcd){
    uint32_t offset=dcd-boot_start;
    uint32_t length;
    if((uint64_t)offset+4>boot_size){
      error_setg(errp,"NAND DCD header exceeds declared boot size");return false;
    }
    if((uint64_t)offset+4>available)return true;
    length=lduw_be_p(image+offset+1);
    if(length<4||(uint64_t)offset+length>boot_size){
      error_setg(errp,"NAND DCD exceeds declared boot size");return false;
    }
    if((uint64_t)offset+length>available)return true;
  }
  /* DCD lives in the ROM's staging buffer. Execute it before touching the
   * external destination: it may be the code that makes DDR usable. */
  if(!prime_rom_execute_dcd(image,available,boot_start,dcd,errp))return false;
  if(boot_start>=0x80000000 && !prime_g2_mmdc_initialized()){
    error_setg(errp,"MMDC DDR3 initialization incomplete before NAND load");return false;
  }
  *start=boot_start;*size=boot_size;*entry=ivt_entry;*prepared=true;
  return true;
}

static bool prime_rom_load_firmware(PrimeNANDState *s, uint32_t start_page,
                                    uint32_t page_count,const uint8_t *dbbt,uint32_t *entry,
                                    bool scan_marker,Error **errp)
{
  uint8_t page[PRIME_NAND_PAGE_BYTES];uint8_t *image;
  uint32_t boot_start=0,boot_size=0,ivt_entry=0;
  uint32_t image_bytes;unsigned copied=0,skipped_blocks=0;
  uint32_t written=0;
  uint32_t page_index=start_page;
  bool prepared=false;
  MemTxResult result;

  if(!page_count||page_count>PRIME_ROM_MAX_BOOT_PAGES){
    error_setg(errp,"invalid NAND boot-stream page count %u",page_count);
    return false;
  }
  image_bytes=page_count*2048;
  image=g_malloc(image_bytes);
  while(copied<page_count){
    if(page_index>=PRIME_NAND_TOTAL_PAGES){
      error_setg(errp,"NAND boot stream runs beyond the device");goto fail;
    }
    if((dbbt[(page_index/64)/8]&(1u<<((page_index/64)%8)))||
       !prime_rom_read_page_internal(s,page_index,page,scan_marker)){
      page_index=(page_index/64+1)*64;skipped_blocks++;continue;
    }
    if(!prime_rom_decode_data(s,page_index,page)){
      error_setg(errp,"uncorrectable BCH in NAND firmware page %u",page_index);goto fail;
    }
    memcpy(image+(size_t)copied*2048,page,2048);
    copied++;page_index++;
    if(!prepared){
      if(!prime_rom_prepare_firmware(image,copied*2048,image_bytes,&prepared,
                                    &boot_start,&boot_size,&ivt_entry,errp))goto fail;
      if(prepared)qemu_log("hp-prime-g2-rom: DCD stage ready after %u firmware pages from %u\n",
                           copied,start_page);
    }
    if(prepared){
      uint32_t received=MIN(copied*2048,boot_size);
      /* Flush the staged prefix once DCD completes, then only new bytes.
       * A later ECC fault must not roll back already transferred DDR. */
      if(received>written){
        result=address_space_write(&address_space_memory,boot_start+written,
                                   MEMTXATTRS_UNSPECIFIED,image+written,received-written);
        if(result!=MEMTX_OK){
          error_setg(errp,"cannot load NAND boot stream at 0x%08x",boot_start+written);
          goto fail;
        }
        written=received;
      }
    }
  }
  if(!prepared){
    error_setg(errp,"NAND boot stream ended before header/DCD preparation");goto fail;
  }
  *entry=ivt_entry;
  qemu_log("hp-prime-g2-rom: loaded %u bytes from NAND page %u to "
           "0x%08x, entry 0x%08x; skipped %u marked block%s\n",
           boot_size,start_page,boot_start,*entry,skipped_blocks,
           skipped_blocks==1?"":"s");
  g_free(image);return true;
fail:
  g_free(image);return false;
}

bool prime_g2_nand_rom_load(uint32_t *entry, Error **errp)
{
  PrimeNANDState *s=prime_nand_instance();uint8_t page[PRIME_NAND_PAGE_BYTES];
  uint8_t bad[PRIME_NAND_BLOCKS/8];
  unsigned copy;Error *last_error=NULL;
  if(!s||!s->stock_nand){error_setg(errp,"no NAND capture is attached");return false;}
  for(copy=0;copy<PRIME_ROM_FCB_COPIES;copy++){
    const uint8_t *fcb;uint32_t fw1,fw2,pages1,pages2,dbbt;bool scan_marker=true;
    if(!prime_rom_read_page(s,copy*64,page))continue;
    if(s->physical_pages&&!prime_rom_decode_fcb(s,page))continue;
    if(!prime_rom_fcb_valid(page))continue;
    fcb=page+PRIME_ROM_FCB_OFFSET;
    if(s->physical_pages&&!prime_rom_configure_bch(s,fcb))continue;
    if(s->physical_pages){
      uint32_t disable_search=ldl_le_p(fcb+0xd8);
      if(disable_search>1)continue;
      scan_marker=!disable_search;
      if(disable_search)qemu_log("hp-prime-g2-rom: firmware uses DBBT-only bad-block search\n");
    }
    if(s->physical_pages)qemu_log("hp-prime-g2-rom: selected FCB copy %u\n",copy);
    fw1=ldl_le_p(fcb+0x68);fw2=ldl_le_p(fcb+0x6c);
    pages1=ldl_le_p(fcb+0x70);pages2=ldl_le_p(fcb+0x74);
    dbbt=ldl_le_p(fcb+0x78);
    if(!prime_rom_dbbt_load(s,dbbt,bad)){
      qemu_log("hp-prime-g2-rom: FCB copy %u has no valid DBBT\n",copy);
      continue;
    }
    if(prime_rom_load_firmware(s,fw1,pages1,bad,entry,scan_marker,&last_error))return true;
    if(last_error){qemu_log("hp-prime-g2-rom: firmware 1 rejected: %s\n",
                           error_get_pretty(last_error));error_free(last_error);last_error=NULL;}
    if(prime_rom_load_firmware(s,fw2,pages2,bad,entry,scan_marker,&last_error))return true;
    if(last_error){qemu_log("hp-prime-g2-rom: firmware 2 rejected: %s\n",
                           error_get_pretty(last_error));error_free(last_error);last_error=NULL;}
  }
  error_setg(errp,"no valid i.MX6ULL NAND FCB/DBBT/IVT boot chain");
  return false;
}
static bool prime_nand_program_page(PrimeNANDState*s)
{unsigned i;int slot;if(prime_nand_bad(s,s->page)){
   s->program_failures++;if(s->page>=PRIME_NAND_TOTAL_PAGES)s->program_out_of_range++;
   return false;}
 slot=prime_nand_find(s,s->page,true);if(slot<0){
   s->program_failures++;s->program_overlay_full++;return false;}
 if(s->program_counts[slot]>=4){s->program_failures++;return false;}s->program_counts[slot]++;
 for(i=0;i<PRIME_NAND_PAGE_BYTES;i++)s->page_data[slot*PRIME_NAND_PAGE_BYTES+i]&=s->page_cache[i];
 prime_nand_overlay_append(s,PRIME_NAND_OVERLAY_PROGRAM,s->page,
   &s->page_data[slot*PRIME_NAND_PAGE_BYTES]);
 return true;}
static bool prime_nand_erase_block(PrimeNANDState*s)
{unsigned i,block=s->page/64;if(prime_nand_bad(s,s->page))return false;
 if(s->erase_counts[block]!=0xffff)s->erase_counts[block]++;
 if(s->erase_counts[block]>s->wear_limit){s->bad_blocks[block/8]|=1u<<(block&7);return false;}
 s->erased_blocks[block/8]|=1u<<(block&7);
 for(i=0;i<PRIME_NAND_SPARSE_PAGES;i++)if(s->page_used[i]&&s->page_tags[i]/64==block){s->page_used[i]=0;if(s->overlay_pages_used)s->overlay_pages_used--;s->program_counts[i]=0;s->read_counts[i]=0;}
 prime_nand_overlay_append(s,PRIME_NAND_OVERLAY_ERASE,block,NULL);
 return true;}
static uint64_t prime_alias_read(uint32_t *r, hwaddr off)
{ return r[(off & ~0xf) >> 4]; }
static void prime_alias_write(uint32_t *r, hwaddr off, uint32_t val)
{ unsigned i=(off & ~0xf)>>4; switch(off&0xf){case 0:r[i]=val;break;case 4:r[i]|=val;break;case 8:r[i]&=~val;break;case 12:r[i]^=val;break;} }

static void prime_nand_command_cycle(PrimeNANDState *s, uint8_t value)
{
  s->command=value;s->address_count=0;s->id_cursor=0;s->nand_command_count++;
  switch(value){
  case 0x90:case 0xec:s->column=0;s->id_cursor=0;break;
  case 0xff:s->status=0xe0;s->column=0;break;
  case 0x00:s->column=0;s->page=0;break;
  case 0x30:prime_nand_load_page(s);break;
  case 0x80:s->column=0;memset(s->page_cache,0xff,sizeof(s->page_cache));s->page_cache_valid=true;break;
  case 0x10:s->status=prime_nand_program_page(s)?0xe0:0xe1;break;
  case 0x60:s->page=0;break;
  case 0xd0:s->status=prime_nand_erase_block(s)?0xe0:0xe1;s->page_cache_valid=false;break;
  default:break;
  }
}

static void prime_nand_address_cycle(PrimeNANDState *s, uint8_t value)
{
  unsigned cycle=s->address_count++;
  if(s->command==0x90||s->command==0xec){
    if(!cycle){s->column=value;s->id_cursor=0;}
    return;
  }
  /* ERASE1 is followed by three row cycles and no column cycles. Treating
   * those like READ0/SEQIN's five column+row cycles erases block zero-ish,
   * makes HP's writeback comparison fail, and eventually retires every block. */
  if(s->command==0x60){
    switch(cycle){
    case 0:s->page=(s->page&0xffff00)|value;break;
    case 1:s->page=(s->page&0xff00ff)|((uint32_t)value<<8);break;
    case 2:s->page=(s->page&0x00ffff)|((uint32_t)value<<16);break;
    default:break;
    }
    return;
  }
  switch(cycle){
  case 0:s->column=(s->column&0xff00)|value;break;
  case 1:s->column=(s->column&0x00ff)|((uint16_t)value<<8);break;
  case 2:s->page=(s->page&0xffff00)|value;break;
  case 3:s->page=(s->page&0xff00ff)|((uint32_t)value<<8);break;
  case 4:s->page=(s->page&0x00ffff)|((uint32_t)value<<16);break;
  default:break;
  }
}

static void prime_gpmi_push(PrimeNANDState *s, const uint8_t *data, size_t len)
{
  uint32_t ctrl0=s->gpmi_regs[0];unsigned address=GPMI_ADDRESS(ctrl0);size_t i;
  for(i=0;i<len;i++){
    if(address==GPMI_ADDRESS_CLE)prime_nand_command_cycle(s,data[i]);
    else if(address==GPMI_ADDRESS_ALE)prime_nand_address_cycle(s,data[i]);
    else if(s->command==0x80&&s->column<sizeof(s->page_cache))s->page_cache[s->column++]=data[i];
    if(ctrl0&GPMI_ADDRESS_INCREMENT)address=GPMI_ADDRESS_ALE;
  }
}

static void prime_gpmi_pull(PrimeNANDState *s, uint8_t *data, size_t len)
{
  size_t i;
  for(i=0;i<len;i++){
    if(s->command==0x90){
      unsigned cursor=s->id_cursor++;
      if(s->column==0x20)data[i]=s->onfi_enabled&&cursor<4?"ONFI"[cursor]:0xff;
      else data[i]=s->column==0?s->id[cursor%5]:0xff;
    }
    else if(s->command==0xec)data[i]=s->onfi_enabled&&s->column<768?
      s->onfi_parameters[s->column++%256]:0xff;
    else if(s->command==0x70)data[i]=s->status;
    else data[i]=s->column<sizeof(s->page_cache)?s->page_cache[s->column++]:0xff;
  }
}

/* The backing store is a decoded capture, not physical interleaved ECC.
 * Adapt the driver-side marker swap to the guest's current BCH layout;
 * do not bake in the zero-ECC marker offset used by the old model. */
static bool prime_nand_capture_layout(PrimeNANDState *s, unsigned *metadata,
                                      unsigned *chunks, unsigned *marker)
{
  uint32_t l0=s->bch_regs[8],l1=s->bch_regs[9];
  unsigned index,wire=0,payload=0;bool found=false;
  *metadata=(l0>>16)&255;*chunks=(l0>>24)+1;
  if(!*metadata||((*metadata+3)&~3u)+*chunks>64)return false;
  for(index=0;index<*chunks;index++){
    uint32_t reg=index?l1:l0;
    unsigned bytes=(reg&0x3ff)*4,meta=index?0:*metadata;
    unsigned strength=((reg>>11)&31)*2,gf=reg&(1<<10)?14:13;
    unsigned begin=wire+meta*8;
    if(strength>40)return false;
    if(begin<=2048*8&&2048*8+8<=begin+bytes*8){
      *marker=payload*8+2048*8-begin;found=true;
    }
    wire=begin+bytes*8+strength*gf;payload+=bytes;
  }
  return found&&payload==2048&&wire<=(l1>>16)*8&&wire<=PRIME_NAND_PAGE_BYTES*8;
}

static void prime_nand_swap_marker(uint8_t *payload,uint8_t *aux,unsigned bit)
{
  unsigned byte=bit/8,shift=bit%8;
  if(!shift){uint8_t old=payload[byte];payload[byte]=aux[0];aux[0]=old;return;}
  uint16_t pair=payload[byte]|((uint16_t)payload[byte+1]<<8);
  uint8_t old=(pair>>shift)&255;
  pair=(pair&~(255u<<shift))|((uint16_t)aux[0]<<shift);
  payload[byte]=pair&255;payload[byte+1]=pair>>8;aux[0]=old;
}

static uint8_t prime_bch_reverse(uint8_t byte)
{
  byte=((byte&0x55)<<1)|((byte>>1)&0x55);
  byte=((byte&0x33)<<2)|((byte>>2)&0x33);
  return (byte<<4)|(byte>>4);
}

/* LSB-first, unaligned bit transfers. Parity is interleaved, not an OOB tail. */
static void prime_nand_bits(uint8_t *dst,unsigned dstbit,const uint8_t *src,
                             unsigned srcbit,unsigned count)
{
  unsigned i;
  for(i=0;i<count;i++){
    unsigned to=dstbit+i,from=srcbit+i,mask=1u<<(to%8);
    dst[to/8]=(dst[to/8]&~mask)|(((src[from/8]>>(from%8))&1)<<(to%8));
  }
}

static bool prime_nand_bch_transfer(PrimeNANDState *s,bool encode,
                                    uint8_t *payload,uint8_t *aux)
{
  unsigned metadata,chunks,marker,index,wire=0,offset=0;
  uint32_t result_status=0;
  if(!prime_nand_capture_layout(s,&metadata,&chunks,&marker))return false;
  s->corrected_bits=0;s->uncorrectable=false;
  /* Linux/MXS software repairs erased data after inspecting DEBUG1. Keep
   * damaged DMA bytes intact. Nine-bit saturation and page aggregation are
   * provisional until measured on the Prime (see the parity ledger). */
  s->bch_regs[0x17]=0;
  if(encode)memset(s->page_cache,0xff,sizeof(s->page_cache));
  else memset(aux,0xff,64);
  for(index=0;index<chunks;index++){
    uint32_t reg=s->bch_regs[index?9:8];
    unsigned bytes=(reg&0x3ff)*4,meta=index?0:metadata;
    unsigned strength=((reg>>11)&31)*2,gf=reg&(1<<10)?14:13;
    unsigned length=bytes+meta,parity_bits=strength*gf,j;
    uint8_t message[2112],parity[70]={0};int status=0;
    PrimeBCH *bch=NULL;
    if(strength){
      PrimeBCH **slot=&s->codecs[gf-13][strength/2];
      if(!*slot)*slot=prime_bch_new(gf,strength,gf==13?0x201b:0x402b);
      bch=*slot;
      if(!bch||prime_bch_bits(bch)!=parity_bits)return false;
    }
    if(encode){
      memcpy(message,aux,meta);memcpy(message+meta,payload+offset,bytes);
      prime_nand_bits(s->page_cache,wire,message,0,length*8);
      if(bch){
        for(j=0;j<length;j++)message[j]=prime_bch_reverse(message[j]);
        if(prime_bch_encode(bch,message,length,parity))return false;
        for(j=0;j<prime_bch_bytes(bch);j++)parity[j]=prime_bch_reverse(parity[j]);
        prime_nand_bits(s->page_cache,wire+length*8,parity,0,parity_bits);
      }
    }else{
      unsigned zeros=0;
      memset(message,0,length);
      prime_nand_bits(message,0,s->page_cache,wire,length*8);
      prime_nand_bits(parity,0,s->page_cache,wire+length*8,parity_bits);
      for(j=0;j<length*8+parity_bits;j++){
        unsigned bit=wire+j;
        if(!(s->page_cache[bit/8]&(1u<<(bit%8))))zeros++;
      }
      if(bch&&zeros<=(s->bch_regs[2]&0xff)){
        status=0xff;
        s->bch_regs[0x17]=MIN(0x1ffu,s->bch_regs[0x17]+zeros);
      }
      else if(bch){
        for(j=0;j<length;j++)message[j]=prime_bch_reverse(message[j]);
        for(j=0;j<prime_bch_bytes(bch);j++)parity[j]=prime_bch_reverse(parity[j]);
        status=prime_bch_decode(bch,message,length,parity,NULL);
        for(j=0;j<length;j++)message[j]=prime_bch_reverse(message[j]);
        if(status==-1)return false;
        if(status<0){status=0xfe;s->uncorrectable=true;}
        else s->corrected_bits=MAX(s->corrected_bits,status);
      }
      memcpy(aux,message,meta);memcpy(payload+offset,message+meta,bytes);
      aux[((metadata+3)&~3u)+index]=status;
      /* STATUS_BLK0 describes only the first codeword. Error flags cover
       * every codeword, so a clean first block can coexist with a later
       * uncorrectable block (as in the physical recovery snapshot). */
      if(!index)result_status=(uint32_t)status<<8;
      if(status==0xfe)result_status|=1u<<2;
      else if(status>0&&status<0xfe)result_status|=1u<<3;
    }
    wire+=length*8+parity_bits;offset+=bytes;
  }
  if(!encode)s->bch_regs[1]=result_status;
  return true;
}

static bool prime_apbh_guest_read(hwaddr address, void *buffer, size_t length)
{ return dma_memory_read(&address_space_memory,address,buffer,length,MEMTXATTRS_UNSPECIFIED)==MEMTX_OK; }
static bool prime_apbh_guest_write(hwaddr address, const void *buffer, size_t length)
{ return dma_memory_write(&address_space_memory,address,buffer,length,MEMTXATTRS_UNSPECIFIED)==MEMTX_OK; }

static void prime_gpmi_update_irq(PrimeNANDState *s)
{
  /* NAND WAIT_FOR_READY timeout. ATA DEV_IRQ has no input on this board.
   * COMPARE writes and NAND program/erase completion do not raise this IRQ. */
  uint32_t ctrl=s->gpmi_regs[6];
  qemu_set_irq(s->gpmi_irq,!!((ctrl&(1u<<9))&&(ctrl&(1u<<20))));
}

static void prime_bch_update_irq(PrimeNANDState *s)
{
  uint32_t ctrl=s->bch_regs[0];
  qemu_set_irq(s->bch_irq,!!((ctrl&1u)&&(ctrl&(1u<<8))));
}

static void prime_apbh_update_irq(PrimeNANDState *s)
{
  /* CTRL1 channel-zero completion is sticky until acknowledged. The
   * interrupt enable masks its wire, not the recorded completion. */
  uint32_t ctrl=s->apbh_ctrl[1];
  qemu_set_irq(s->apbh_irq,!!((ctrl&1u)&&(ctrl&(1u<<16))));
}

static void prime_nand_ready_finish(PrimeNANDState *s,bool failed);
static void prime_apbh_execute(PrimeNANDState *s);
static uint32_t prime_nand_clock_hz(PrimeNANDState *s)
{
  if(s->gpmi_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))return 0;
  return s->gpmi_clock_hz ? s->gpmi_clock_hz :
         (s->use_ccm_clock ? clock_get_hz(s->gpmi_clock) : 0);
}
static void prime_nand_wait_clock_update(PrimeNANDState *s)
{
  int64_t now=qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
  uint64_t elapsed=now>s->wait_clock_ns ? now-s->wait_clock_ns : 0;
  if(!s->wait_pending)return;
  /* Track nano-cycles rather than rounding elapsed time to whole cycles.
   * Clamp before multiplying so arbitrarily long pauses cannot overflow. */
  if(s->wait_clock_hz){
    uint64_t until=(s->wait_nano_cycles+s->wait_clock_hz-1)/s->wait_clock_hz;
    if(elapsed>=until)s->wait_nano_cycles=0;
    else s->wait_nano_cycles-=elapsed*s->wait_clock_hz;
  }
  s->wait_clock_ns=now;s->wait_clock_hz=prime_nand_clock_hz(s);
  timer_del(s->ready_timer);
  if(s->wait_clock_hz){
    uint64_t ns=(s->wait_nano_cycles+s->wait_clock_hz-1)/s->wait_clock_hz;
    timer_mod(s->ready_timer,now+ns);
  }
}
static void prime_nand_clock_changed(void *opaque,ClockEvent event)
{
  PrimeNANDState *s=opaque;
  if(s->wait_pending){
    prime_nand_wait_clock_update(s);
    if(s->nand_ready&&s->wait_clock_hz)prime_nand_ready_finish(s,false);
  }
  if(s->dma_clock_blocked&&
     (!(s->dma_clock_blocked&1)||
      (!(s->gpmi_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))&&
       (!s->use_ccm_clock||prime_nand_clock_hz(s))))&&
     (!(s->dma_clock_blocked&2)||
      (!(s->bch_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))&&
       (!s->use_ccm_clock||clock_get_hz(s->bch_clock))))){
    s->dma_clock_blocked=0;
    prime_apbh_execute(s);
  }
}

static void prime_apbh_execute(PrimeNANDState *s)
{
  uint32_t descriptor=s->apbh_next;unsigned count;
  /* The i.MX6 channel-zero gate is CTRL0 bit 0 (not the MX23 bit 8).
   * FREEZE_CHANNEL is separate from peripheral GPMI/BCH clock gating. */
  if(!s->apbh_sema||s->wait_pending||s->dma_clock_blocked||
     (s->apbh_ctrl[0]&(1u|APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))||
     (s->apbh_ctrl[3]&1u))return;
  for(count=0;descriptor&&count<128;count++){
    uint32_t raw[3+16],next,command_word,buffer;uint16_t bits,xfer;unsigned pio_count,i,command;uint8_t *bytes=NULL;
    s->last_descriptor=descriptor;
    if(!prime_apbh_guest_read(descriptor,raw,3*sizeof(uint32_t)))break;
    next=le32_to_cpu(raw[0]);command_word=le32_to_cpu(raw[1]);buffer=le32_to_cpu(raw[2]);
    s->apbh_cmd=command_word;
    bits=command_word&0xffff;xfer=command_word>>16;command=bits&APBH_CCW_COMMAND_MASK;
    pio_count=(bits>>APBH_CCW_PIO_SHIFT)&APBH_CCW_PIO_MASK;
    if(pio_count){
      if(!prime_apbh_guest_read(descriptor+12,&raw[3],pio_count*sizeof(uint32_t)))break;
    }
    s->apbh_bar=buffer;
    {
      uint32_t ctrl=pio_count?le32_to_cpu(raw[3]):s->gpmi_regs[0];
      bool wait=pio_count&&GPMI_MODE(ctrl)==GPMI_MODE_WAIT_READY;
      uint32_t eccctrl=pio_count>2?le32_to_cpu(raw[5]):s->gpmi_regs[2];
      bool ecc=pio_count&&(eccctrl&GPMI_ECC_ENABLE)&&
               (GPMI_MODE(ctrl)==GPMI_MODE_READ||GPMI_MODE(ctrl)==GPMI_MODE_WRITE);
      bool gpmi_local=s->gpmi_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE);
      bool bch_local=s->bch_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE);
      s->dma_clock_blocked=((pio_count||xfer)&&
          (gpmi_local||(!wait&&s->use_ccm_clock&&!prime_nand_clock_hz(s)))?1:0)|
          (ecc&&(bch_local||(s->use_ccm_clock&&!clock_get_hz(s->bch_clock)))?2:0);
      if(s->dma_clock_blocked){s->apbh_next=descriptor;return;}
    }
    if(pio_count){
      for(i=0;i<pio_count;i++)s->gpmi_regs[i]=le32_to_cpu(raw[3+i]);
      if(pio_count>6)prime_gpmi_update_irq(s);
    }
    s->apbh_bar=buffer;if(buffer)s->last_dma_buffer=buffer;
    if(pio_count&&GPMI_MODE(s->gpmi_regs[0])==GPMI_MODE_READ_COMPARE){
      uint32_t ctrl=s->gpmi_regs[0],compare=s->gpmi_regs[1];uint8_t value;
      /* NAND status descriptor: peripheral reads one byte internally;
       * APBH has no RAM data transfer. MASK selects significant XOR bits.
       * Do not silently accept unqualified wider/multi-byte forms. */
      if(!(ctrl&(1u<<23))||(ctrl&0xffff)!=1||
         GPMI_ADDRESS(ctrl)!=GPMI_ADDRESS_DATA||command!=APBH_CMD_NO_XFER||xfer){
        qemu_log_mask(LOG_UNIMP,"prime-g2-gpmi: unsupported read/compare form\n");
        break;
      }
      prime_gpmi_pull(s,&value,1);
      s->sense_failed=!!((value^compare)&(compare>>16)&0xffu);
    }
    if(pio_count&&GPMI_MODE(s->gpmi_regs[0])==GPMI_MODE_WAIT_READY){
      if(s->wait_completed){
        s->wait_completed=false;
      }else{
        s->sense_failed=false;
        s->gpmi_regs[0xb]&=~(1u<<16);
        if(!s->nand_ready||(!s->gpmi_clock_hz&&s->use_ccm_clock&&!prime_nand_clock_hz(s))){
          uint64_t cycles=(uint64_t)(s->gpmi_regs[8]>>16)*4096;
          s->wait_pending=true;s->apbh_next=descriptor;
          s->wait_nano_cycles=cycles*1000000000ULL;
          s->wait_clock_ns=qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
          s->wait_clock_hz=0;
          prime_nand_wait_clock_update(s);
          return;
        }
      }
    }
    if(command==APBH_CMD_SENSE&&s->sense_failed)next=buffer;
    if(xfer){
      bytes=g_malloc(xfer);
      if(command==APBH_CMD_MEM_TO_DEV){
        if(prime_apbh_guest_read(buffer,bytes,xfer))prime_gpmi_push(s,bytes,xfer);
      }else if(command==APBH_CMD_DEV_TO_MEM){
        prime_gpmi_pull(s,bytes,xfer);prime_apbh_guest_write(buffer,bytes,xfer);
      }
      g_free(bytes);
    }
    if(pio_count&&GPMI_MODE(s->gpmi_regs[0])==GPMI_MODE_READ&&
       (s->gpmi_regs[2]&GPMI_ECC_ENABLE)&&s->page_cache_valid){
      uint8_t payload_data[2048],auxiliary[64];unsigned metadata,chunks,marker;
      uint32_t payload=s->gpmi_regs[4],aux=s->gpmi_regs[5];s->last_ecc_payload=payload;
      /* Raw mode decodes stored codewords. Decoded capture mode only adapts
       * the driver-side marker representation; it is not raw ECC evidence. */
      memcpy(payload_data,s->page_cache,sizeof(payload_data));
      memset(auxiliary,0xff,sizeof(auxiliary));
      if(!prime_nand_capture_layout(s,&metadata,&chunks,&marker)){
        qemu_log_mask(LOG_GUEST_ERROR,"prime-g2-bch: unsupported capture layout\n");
        s->uncorrectable=true;break;
      }
      if(s->physical_pages){
        if(!prime_nand_bch_transfer(s,false,payload_data,auxiliary)){
          s->uncorrectable=true;break;
        }
      }else{
        memcpy(auxiliary,s->page_cache+2048,metadata);
        prime_nand_swap_marker(payload_data,auxiliary,marker);
        memset(auxiliary+((metadata+3)&~3u),s->uncorrectable?0xfe:0,chunks);
      }
      if(payload)prime_apbh_guest_write(payload,payload_data,sizeof(payload_data));
      if(aux)prime_apbh_guest_write(aux,auxiliary,sizeof(auxiliary));
      s->bch_regs[0]|=1u;prime_bch_update_irq(s);
    }else if(pio_count&&GPMI_MODE(s->gpmi_regs[0])==GPMI_MODE_WRITE&&
             (s->gpmi_regs[2]&GPMI_ECC_ENABLE)&&s->command==0x80){
      /* BCH encode descriptors carry data through PAYLOAD/AUXILIARY pointers,
       * not the APBH descriptor's ordinary data buffer. Mirror the read path:
       * capture the clean payload and metadata before PAGEPROG consumes them. */
      uint32_t payload=s->gpmi_regs[4],aux=s->gpmi_regs[5];unsigned metadata,chunks,marker;
      if(!prime_nand_capture_layout(s,&metadata,&chunks,&marker)){
        qemu_log_mask(LOG_GUEST_ERROR,"prime-g2-bch: unsupported capture layout\n");
        s->uncorrectable=true;s->page_cache_valid=false;break;
      }
      if(s->physical_pages){
        uint8_t message[2048],auxiliary[64];
        memset(message,0xff,sizeof(message));memset(auxiliary,0xff,sizeof(auxiliary));
        if(payload)prime_apbh_guest_read(payload,message,sizeof(message));
        if(aux)prime_apbh_guest_read(aux,auxiliary,metadata);
        if(!prime_nand_bch_transfer(s,true,message,auxiliary)){
          s->page_cache_valid=false;s->uncorrectable=true;break;
        }
        s->last_ecc_payload=payload;
      }else{
        memset(s->page_cache,0xff,sizeof(s->page_cache));
        if(payload){prime_apbh_guest_read(payload,s->page_cache,2048);s->last_ecc_payload=payload;}
        if(aux)prime_apbh_guest_read(aux,s->page_cache+2048,metadata);
        prime_nand_swap_marker(s->page_cache,s->page_cache+2048,marker);
      }
      s->page_cache_valid=true;s->ecc_write_count++;
      s->bch_regs[0]|=1u;prime_bch_update_irq(s);
    }
    s->apbh_next=next;
    if(bits&APBH_CCW_DEC_SEM){if(s->apbh_sema)s->apbh_sema--;}
    if(bits&APBH_CCW_IRQ){s->apbh_ctrl[1]|=1u;prime_apbh_update_irq(s);}
    /* U-Boot deliberately leaves CHAIN set on a one-descriptor NAND command;
     * NEXT points back to that command and the hardware semaphore is what
     * terminates execution. Following NEXT after PHORE reaches zero loops the
     * same command forever and makes every MXS NAND operation time out. */
    if(!s->apbh_sema||!(bits&APBH_CCW_CHAIN)){
      break;
    }
    descriptor=next;
  }
  if(count==128)qemu_log_mask(LOG_GUEST_ERROR,"prime-g2-apbh: descriptor chain limit reached\n");
}

static void prime_nand_ready_finish(PrimeNANDState *s,bool failed)
{
  if(!s->wait_pending)return;
  timer_del(s->ready_timer);
  s->wait_pending=false;s->wait_completed=true;s->sense_failed=failed;
  if(failed){s->gpmi_regs[6]|=1u<<9;s->gpmi_regs[0xb]|=1u<<16;}
  prime_gpmi_update_irq(s);
  prime_apbh_execute(s);
}
static void prime_nand_ready_timeout(void *opaque)
{ prime_nand_ready_finish(opaque,true); }
static void prime_nand_ready_input(void *opaque,int index,int level)
{
  PrimeNANDState *s=opaque;s->nand_ready=!!level;
  if(level&&!(s->gpmi_regs[0]&(APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))&&
     (s->gpmi_clock_hz||!s->use_ccm_clock||prime_nand_clock_hz(s)))
    prime_nand_ready_finish(s,false);
}
static void prime_nand_init(Object *obj)
{
  PrimeNANDState *s=PRIME_NAND(obj);s->nand_ready=true;
  s->ready_timer=timer_new_ns(QEMU_CLOCK_VIRTUAL,prime_nand_ready_timeout,s);
  s->gpmi_clock=qdev_init_clock_in(DEVICE(obj),"gpmi",prime_nand_clock_changed,s,ClockUpdate);
  s->bch_clock=qdev_init_clock_in(DEVICE(obj),"bch",prime_nand_clock_changed,s,ClockUpdate);
  qdev_init_gpio_in_named(DEVICE(obj),prime_nand_ready_input,"nand-ready",1);
}

static uint64_t prime_apbh_read(void *o, hwaddr off, unsigned size)
{ PrimeNANDState*s=o;
  /* CURCMDAR remains on the descriptor most recently fetched. HP's stock
   * NAND discovery uses it to prove that an APBH chain reached its terminal
   * descriptor before accepting the READID result. */
  if(off==APBH_CH0_CURCMDAR)return s->last_descriptor;
  if(off==APBH_CH0_NXTCMDAR)return s->apbh_next;
  if(off==APBH_CH0_CMD)return s->apbh_cmd;
  if(off==APBH_CH0_BAR)return s->apbh_bar;
  if(off==APBH_CH0_SEMA)return (s->apbh_sema&0xffu)<<16;
  if((off&~0xf)<=APBH_CHANNEL_CTRL)return s->apbh_ctrl[(off&~0xf)>>4];
  return 0; }
static void prime_apbh_write(void *o, hwaddr off, uint64_t v, unsigned size)
{ PrimeNANDState*s=o;
  /* While reset is held, channel programming and IRQ writes are ignored.
   * CTRL0 remains accessible so software can release reset and its gate. */
  if((s->apbh_ctrl[0]&APBH_BLOCK_SFTRST)&&(off&~0xf)!=APBH_CTRL0)return;
  if(off==APBH_CH0_NXTCMDAR){s->apbh_next=v;return;}
  if(off==APBH_CH0_SEMA){s->apbh_sema+=(uint8_t)v;prime_apbh_execute(s);return;}
  if((off&~0xf)<=APBH_CHANNEL_CTRL){
    uint32_t previous=s->apbh_ctrl[0];
    bool held=(previous&(1u|APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))||(s->apbh_ctrl[3]&1u);
    prime_alias_write(s->apbh_ctrl,off,v);
    if((off&~0xf)==APBH_CTRL0&&!(previous&APBH_BLOCK_SFTRST)&&
       (s->apbh_ctrl[0]&APBH_BLOCK_SFTRST)){
      memset(s->apbh_ctrl,0,sizeof(s->apbh_ctrl));
      s->apbh_ctrl[0]=APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE;
      s->apbh_next=0;s->apbh_bar=0;s->apbh_sema=0;s->apbh_cmd=0;
      s->last_descriptor=0;s->dma_clock_blocked=0;
      /* Detach the queued DMA continuation. Physical peripheral-abort
       * timing during an in-flight wait is not yet cycle modeled. */
      timer_del(s->ready_timer);s->wait_pending=false;s->wait_completed=false;
      s->wait_nano_cycles=0;s->wait_clock_hz=0;
      prime_apbh_update_irq(s);
      return;
    }
    if((off&~0xf)==0x10)prime_apbh_update_irq(s);
    if(held&&!(s->apbh_ctrl[0]&(1u|APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE))&&!(s->apbh_ctrl[3]&1u))
      prime_apbh_execute(s);
    return;
  }
}
static uint64_t prime_gpmi_read(void *o, hwaddr off, unsigned size)
{ PrimeNANDState *s=o;
  switch(off){
  case 0xb0:return (s->nand_ready?1u<<24:0)|(s->gpmi_regs[0xb]&(1u<<16))|
                   (s->sense_failed?1u<<8:0);
  case 0x100:return s->command; case 0x104:return s->page; case 0x108:
    {uint8_t value;prime_gpmi_pull(s,&value,1);return value;}
  case 0x10c:return s->status; case 0x110:return 2048; case 0x114:return 64;
  case 0x118:return 128*1024; case 0x11c:return 4096; case 0x120:return 8;
  case 0x124:return 5; case 0x128:return prime_nand_bad(s,s->page);
  case 0x12c:return s->corrected_bits;
  case 0x130:return s->fault_kind; case 0x134:return s->fault_page;
  case 0x138:return s->fault_offset|((uint32_t)s->fault_mask<<16);
  case 0x13c:return s->wear_limit; case 0x140:return s->read_disturb_limit;
  case 0x144:return s->erase_counts[MIN(s->page/64,PRIME_NAND_BLOCKS-1)];
  case 0x148:return s->uncorrectable;
  case 0x14c:{uint32_t value=0xffffffffu;unsigned i;
    for(i=0;i<4;i++){
      if(s->column<sizeof(s->page_cache))((uint8_t*)&value)[i]=s->page_cache[s->column++];
    }
    return value;}
  case 0x150:return s->last_descriptor;case 0x154:return s->last_dma_buffer;
  case 0x158:return s->last_ecc_payload;case 0x15c:return s->nand_command_count;
  case 0x160:return s->overlay_pages_used;case 0x164:return s->program_failures;
  case 0x168:return s->program_out_of_range;case 0x16c:return s->program_overlay_full;
  case 0x170:return s->ecc_write_count;
  default:return prime_alias_read(s->gpmi_regs,off); } }
static void prime_gpmi_write(void *o, hwaddr off, uint64_t v, unsigned size)
{ PrimeNANDState *s=o;
  uint32_t previous=s->gpmi_regs[0];
  if(off<0x100&&(off&~0xf)!=0&&(previous&APBH_BLOCK_SFTRST))return;
  if((off&~0xf)==0xb0)return; /* STAT reflects hardware, not guest writes. */
  switch(off){
  case 0x100:prime_nand_command_cycle(s,v);return;
  case 0x104:s->page=v;s->column=0;if(s->command==0x00)prime_nand_load_page(s);return;
  case 0x108:if(s->command==0x80&&s->column<sizeof(s->page_cache))s->page_cache[s->column++]=v;return;
  case 0x128:{unsigned block=v&0xfff;if(block<PRIME_NAND_BLOCKS)s->bad_blocks[block/8]|=1u<<(block&7);return;}
  case 0x12c:s->corrected_bits=v;return;
  case 0x130:s->fault_kind=v<=2?v:2;return; case 0x134:s->fault_page=v;return;
  case 0x138:s->fault_offset=v&0xffff;s->fault_mask=(v>>16)&0xff;return;
  case 0x13c:s->wear_limit=v?MIN(v,0xffff):0xffff;return;
  case 0x140:s->read_disturb_limit=v?MIN(v,0xffff):0xffff;return;
  case 0x14c:{unsigned i;
    if(s->command==0x80)for(i=0;i<4;i++){
      if(s->column<sizeof(s->page_cache))s->page_cache[s->column++]=(v>>(i*8))&0xff;
    }
    return;}
  default:prime_alias_write(s->gpmi_regs,off,v);
    if((off&~0xf)==0){
      if(!(previous&APBH_BLOCK_SFTRST)&&(s->gpmi_regs[0]&APBH_BLOCK_SFTRST)){
        memset(s->gpmi_regs,0,sizeof(s->gpmi_regs));
        s->gpmi_regs[0]=APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE;
        timer_del(s->ready_timer);s->wait_pending=false;s->wait_completed=false;
        s->wait_nano_cycles=0;s->wait_clock_hz=0;s->sense_failed=false;
        prime_gpmi_update_irq(s);
      }
      prime_nand_clock_changed(s,ClockUpdate);
    }
    if((off&~0xf)==0x60)prime_gpmi_update_irq(s);
  } }
static uint64_t prime_bch_read(void *o, hwaddr off, unsigned size)
{ PrimeNANDState *s=o;
  if((off&~0xf)==0x160)return 0x01000000; /* physical Prime BCH_VERSION */
  if(off==0x100)return (s->uncorrectable?0x80000000u:0)|s->corrected_bits;
  return prime_alias_read(s->bch_regs,off); }
static void prime_bch_write(void *o, hwaddr off, uint64_t v, unsigned size)
{
  PrimeNANDState *s=o;hwaddr reg=off&~0xf;
  uint32_t previous=s->bch_regs[0];
  if(reg!=0&&(previous&APBH_BLOCK_SFTRST))return;
  /* Completion is acknowledged through CTRL_CLR, not STATUS0. The result
   * and erased-zero count registers cannot be fabricated by guest writes. */
  if(reg==0x10||reg==0x160||reg==0x170)return;
  prime_alias_write(s->bch_regs,off,v);
  if(reg==0x20)s->bch_regs[2]&=0xff;
  if(reg==0){
    if(!(previous&APBH_BLOCK_SFTRST)&&(s->bch_regs[0]&APBH_BLOCK_SFTRST)){
      memset(s->bch_regs,0,sizeof(s->bch_regs));
      s->bch_regs[0]=APBH_BLOCK_SFTRST|APBH_BLOCK_CLKGATE;
    }
    prime_bch_update_irq(s);
    prime_nand_clock_changed(s,ClockUpdate);
  }
}
static const MemoryRegionOps prime_gpmi_ops={.read=prime_gpmi_read,.write=prime_gpmi_write,.endianness=DEVICE_LITTLE_ENDIAN,.valid={.min_access_size=4,.max_access_size=4}};
static const MemoryRegionOps prime_bch_ops={.read=prime_bch_read,.write=prime_bch_write,.endianness=DEVICE_LITTLE_ENDIAN,.valid={.min_access_size=4,.max_access_size=4}};
static const MemoryRegionOps prime_apbh_ops={.read=prime_apbh_read,.write=prime_apbh_write,.endianness=DEVICE_LITTLE_ENDIAN,.valid={.min_access_size=4,.max_access_size=4}};
static void prime_nand_reset(DeviceState *dev)
{ PrimeNANDState*s=PRIME_NAND(dev);memset(s->gpmi_regs,0,sizeof(s->gpmi_regs));memset(s->bch_regs,0,sizeof(s->bch_regs));
  prime_gpmi_update_irq(s);
  prime_bch_update_irq(s);
  memset(s->apbh_ctrl,0,sizeof(s->apbh_ctrl));s->apbh_next=0;s->apbh_bar=0;s->apbh_sema=0;
  prime_apbh_update_irq(s);
  s->apbh_cmd=0;
  timer_del(s->ready_timer);
  s->wait_pending=false;s->wait_completed=false;s->sense_failed=false;
  s->wait_nano_cycles=0;s->wait_clock_ns=0;s->wait_clock_hz=0;
  s->dma_clock_blocked=0;
  s->last_descriptor=0;s->last_dma_buffer=0;s->last_ecc_payload=0;s->nand_command_count=0;
  s->program_failures=0;s->program_out_of_range=0;
  s->program_overlay_full=0;s->ecc_write_count=0;
  s->id[0]=0x2c;s->id[1]=0xdc;s->id[2]=0x90;s->id[3]=0x95;s->id[4]=0x56;s->status=0xe0;
  s->command=0xff;s->id_cursor=0;s->address_count=0;s->column=0;s->page=0;s->page_cache_valid=false;s->corrected_bits=0;s->uncorrectable=false;
  s->fault_kind=0;s->fault_mask=1;s->fault_offset=0;s->fault_page=0xffffffffu;
  s->wear_limit=0xffff;s->read_disturb_limit=0xffff;
  memset(s->page_cache,0xff,sizeof(s->page_cache));
  if(!s->initialized){memset(s->page_tags,0,sizeof(s->page_tags));memset(s->page_used,0,sizeof(s->page_used));
   memset(s->program_counts,0,sizeof(s->program_counts));memset(s->read_counts,0,sizeof(s->read_counts));
   memset(s->page_data,0xff,sizeof(s->page_data));memset(s->bad_blocks,0,sizeof(s->bad_blocks));
   memset(s->erased_blocks,0,sizeof(s->erased_blocks));
   memset(s->erase_counts,0,sizeof(s->erase_counts));s->initialized=true;}
  /* Initial functional profile; software reconfigures these registers. */
  s->bch_regs[8]=(3u<<24)|(10u<<16)|(1u<<11)|128u;
  s->bch_regs[9]=(2112u<<16)|(1u<<11)|128u; }

static uint16_t prime_nand_onfi_crc(const uint8_t *data)
{
  uint16_t crc=0x4f4e;unsigned byte,bit;
  for(byte=0;byte<254;byte++){
    crc^=(uint16_t)data[byte]<<8;
    for(bit=0;bit<8;bit++)crc=(crc<<1)^((crc&0x8000)?0x8005:0);
  }
  return crc;
}
static void prime_nand_realize(DeviceState *dev, Error **errp)
{ PrimeNANDState*s=PRIME_NAND(dev);
  if(s->onfi_parameters_path){
    gchar *data=NULL;gsize length;GError *error=NULL;
    if(!g_file_get_contents(s->onfi_parameters_path,&data,&length,&error)){
      error_setg(errp,"cannot read ONFI parameters: %s",error->message);
      g_error_free(error);return;
    }
    if(length!=256){g_free(data);error_setg(errp,"ONFI parameters must be 256 bytes");return;}
    memcpy(s->onfi_parameters,data,256);g_free(data);
    if(memcmp(s->onfi_parameters,"ONFI",4)||
       lduw_le_p(s->onfi_parameters+254)!=prime_nand_onfi_crc(s->onfi_parameters)){
      error_setg(errp,"invalid ONFI parameter signature/CRC");return;
    }
  }else{
    /* PROVISIONAL ONFI profile, NOT a capture of the calculator's parameter
     * page. Geometry matches NAND backing and archived recovery kobs.log.
     * A 1-bit per 512-byte requirement becomes the observed BCH strength 2. */
    uint8_t *p=s->onfi_parameters;
    memcpy(p,"ONFI",4);stw_le_p(p+4,2); /* ONFI 1.0, x8 async */
    memcpy(p+32,"MICRON      ",12);memcpy(p+44,"PROVISIONAL PRIME   ",20);
    p[64]=0x2c;stl_le_p(p+80,2048);stw_le_p(p+84,64);
    stl_le_p(p+92,64);stl_le_p(p+96,4096);p[100]=1;p[101]=0x23;p[102]=1;
    p[110]=4;p[112]=1;stw_le_p(p+129,1); /* async timing mode 0 */
    stw_le_p(p+254,prime_nand_onfi_crc(p));
  }
  if(ldl_le_p(s->onfi_parameters+80)!=2048||lduw_le_p(s->onfi_parameters+84)!=64||
     ldl_le_p(s->onfi_parameters+92)!=64||ldl_le_p(s->onfi_parameters+96)!=4096||
     s->onfi_parameters[100]!=1){
    error_setg(errp,"ONFI geometry does not match the Prime NAND backing");return;
  }
  if(s->stock_nand_path){
    GError *mapped_error=NULL;
    s->stock_nand=g_mapped_file_new(s->stock_nand_path,false,&mapped_error);
    if(!s->stock_nand){error_setg(errp,"cannot map private stock NAND '%s': %s",s->stock_nand_path,mapped_error->message);g_error_free(mapped_error);return;}
    if(g_mapped_file_get_length(s->stock_nand)!=(size_t)PRIME_NAND_TOTAL_PAGES*PRIME_NAND_PAGE_BYTES){
      error_setg(errp,"private stock NAND has wrong size (expected %u bytes)",PRIME_NAND_TOTAL_PAGES*PRIME_NAND_PAGE_BYTES);return;
    }
  }
  if(s->stock_overlay_path){
    memset(s->page_tags,0,sizeof(s->page_tags));memset(s->page_used,0,sizeof(s->page_used));
    memset(s->program_counts,0,sizeof(s->program_counts));memset(s->read_counts,0,sizeof(s->read_counts));
    memset(s->bad_blocks,0,sizeof(s->bad_blocks));memset(s->erased_blocks,0,sizeof(s->erased_blocks));
    memset(s->erase_counts,0,sizeof(s->erase_counts));s->overlay_pages_used=0;
    if(!prime_nand_overlay_replay(s,errp))return;
    s->initialized=true;
  }
  memory_region_init_io(&s->gpmi,OBJECT(dev),&prime_gpmi_ops,s,"prime-g2-gpmi",0x200);
  memory_region_init_io(&s->bch,OBJECT(dev),&prime_bch_ops,s,"prime-g2-bch",0x200);
  memory_region_init_io(&s->apbh,OBJECT(dev),&prime_apbh_ops,s,"prime-g2-apbh",0x1000);
  sysbus_init_mmio(SYS_BUS_DEVICE(dev),&s->gpmi);sysbus_init_mmio(SYS_BUS_DEVICE(dev),&s->bch);sysbus_init_mmio(SYS_BUS_DEVICE(dev),&s->apbh);
  sysbus_init_irq(SYS_BUS_DEVICE(dev),&s->gpmi_irq);sysbus_init_irq(SYS_BUS_DEVICE(dev),&s->bch_irq);sysbus_init_irq(SYS_BUS_DEVICE(dev),&s->apbh_irq); }
static int prime_nand_post_load(void *opaque,int version_id)
{
  PrimeNANDState *s=opaque;
  if(version_id<4&&s->wait_pending){
    int64_t now=qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
    int64_t deadline=timer_expire_time_ns(s->ready_timer);
    s->wait_clock_ns=now;s->wait_clock_hz=prime_nand_clock_hz(s);
    s->wait_nano_cycles=deadline>now ? (uint64_t)(deadline-now)*s->wait_clock_hz : 0;
  }
  prime_gpmi_update_irq(s);prime_bch_update_irq(s);prime_apbh_update_irq(s);return 0;
}
static const VMStateDescription prime_nand_vmstate={.name=TYPE_PRIME_G2_NAND,.version_id=5,.minimum_version_id=1,.post_load=prime_nand_post_load,.fields=(const VMStateField[]){
 VMSTATE_UINT32_ARRAY(gpmi_regs,PrimeNANDState,0x80),VMSTATE_UINT32_ARRAY(bch_regs,PrimeNANDState,0x80),
 VMSTATE_UINT8_ARRAY(id,PrimeNANDState,5),VMSTATE_UINT8(status,PrimeNANDState),
 VMSTATE_UINT8(command,PrimeNANDState),VMSTATE_UINT8(id_cursor,PrimeNANDState),VMSTATE_UINT8(address_count,PrimeNANDState),
 VMSTATE_UINT32_ARRAY(apbh_ctrl,PrimeNANDState,4),VMSTATE_UINT32(apbh_next,PrimeNANDState),VMSTATE_UINT32(apbh_bar,PrimeNANDState),VMSTATE_UINT32(apbh_sema,PrimeNANDState),
 VMSTATE_UINT32_V(apbh_cmd,PrimeNANDState,2),
 VMSTATE_BOOL_V(nand_ready,PrimeNANDState,3),VMSTATE_BOOL_V(wait_pending,PrimeNANDState,3),
 VMSTATE_BOOL_V(wait_completed,PrimeNANDState,3),VMSTATE_BOOL_V(sense_failed,PrimeNANDState,3),
 VMSTATE_TIMER_PTR_V(ready_timer,PrimeNANDState,3),
 VMSTATE_UINT64_V(wait_nano_cycles,PrimeNANDState,4),
 VMSTATE_INT64_V(wait_clock_ns,PrimeNANDState,4),VMSTATE_UINT32_V(wait_clock_hz,PrimeNANDState,4),
 VMSTATE_UINT8_V(dma_clock_blocked,PrimeNANDState,5),
 VMSTATE_UINT32(last_descriptor,PrimeNANDState),VMSTATE_UINT32(last_dma_buffer,PrimeNANDState),VMSTATE_UINT32(last_ecc_payload,PrimeNANDState),VMSTATE_UINT32(nand_command_count,PrimeNANDState),
 VMSTATE_UINT32(overlay_pages_used,PrimeNANDState),VMSTATE_UINT32(program_failures,PrimeNANDState),VMSTATE_UINT32(program_out_of_range,PrimeNANDState),VMSTATE_UINT32(program_overlay_full,PrimeNANDState),
 VMSTATE_UINT32(ecc_write_count,PrimeNANDState),
 VMSTATE_UINT16(column,PrimeNANDState),VMSTATE_UINT32(page,PrimeNANDState),
 VMSTATE_UINT8_ARRAY(page_cache,PrimeNANDState,2112),VMSTATE_BOOL(page_cache_valid,PrimeNANDState),
 VMSTATE_UINT8(corrected_bits,PrimeNANDState),
 VMSTATE_UINT8(fault_kind,PrimeNANDState),VMSTATE_UINT8(fault_mask,PrimeNANDState),
 VMSTATE_UINT16(fault_offset,PrimeNANDState),VMSTATE_UINT32(fault_page,PrimeNANDState),
 VMSTATE_BOOL(uncorrectable,PrimeNANDState),VMSTATE_BOOL(initialized,PrimeNANDState),
 VMSTATE_UINT16(wear_limit,PrimeNANDState),VMSTATE_UINT16(read_disturb_limit,PrimeNANDState),
 VMSTATE_UINT32_ARRAY(page_tags,PrimeNANDState,PRIME_NAND_SPARSE_PAGES),
 VMSTATE_UINT8_ARRAY(page_used,PrimeNANDState,PRIME_NAND_SPARSE_PAGES),
 VMSTATE_UINT8_ARRAY(program_counts,PrimeNANDState,PRIME_NAND_SPARSE_PAGES),
 VMSTATE_UINT16_ARRAY(read_counts,PrimeNANDState,PRIME_NAND_SPARSE_PAGES),
 VMSTATE_UINT8_ARRAY(page_data,PrimeNANDState,PRIME_NAND_SPARSE_PAGES*PRIME_NAND_PAGE_BYTES),
 VMSTATE_UINT8_ARRAY(bad_blocks,PrimeNANDState,PRIME_NAND_BLOCKS/8),
 VMSTATE_UINT8_ARRAY(erased_blocks,PrimeNANDState,PRIME_NAND_BLOCKS/8),
 VMSTATE_UINT16_ARRAY(erase_counts,PrimeNANDState,PRIME_NAND_BLOCKS),VMSTATE_END_OF_LIST()}};
static const Property prime_nand_properties[]={
 DEFINE_PROP_UINT32("gpmi-clock-hz",PrimeNANDState,gpmi_clock_hz,0),
 DEFINE_PROP_BOOL("use-ccm-clock",PrimeNANDState,use_ccm_clock,true),
 DEFINE_PROP_BOOL("physical-pages",PrimeNANDState,physical_pages,false),
 DEFINE_PROP_BOOL("onfi",PrimeNANDState,onfi_enabled,true),
 DEFINE_PROP_STRING("onfi-parameters",PrimeNANDState,onfi_parameters_path),
 DEFINE_PROP_STRING("stock-nand",PrimeNANDState,stock_nand_path),
 DEFINE_PROP_STRING("stock-overlay",PrimeNANDState,stock_overlay_path)};
static void prime_nand_finalize(Object*obj){PrimeNANDState*s=PRIME_NAND(obj);unsigned i,j;
 timer_free(s->ready_timer);
 for(i=0;i<2;i++)for(j=0;j<21;j++)prime_bch_free(s->codecs[i][j]);
 if(s->stock_nand)g_mapped_file_unref(s->stock_nand);}
static void prime_nand_class_init(ObjectClass*oc,const void*data){DeviceClass*dc=DEVICE_CLASS(oc);dc->realize=prime_nand_realize;dc->vmsd=&prime_nand_vmstate;device_class_set_legacy_reset(dc,prime_nand_reset);device_class_set_props(dc,prime_nand_properties);}

static const TypeInfo types[] = {
 { .name=TYPE_PRIME_G2_MMDC,.parent=TYPE_SYS_BUS_DEVICE,.instance_size=sizeof(PrimeMMDCState),.instance_init=prime_mmdc_init,.class_init=prime_mmdc_class_init },
 { .name=TYPE_PRIME_KPP,.parent=TYPE_SYS_BUS_DEVICE,.instance_size=sizeof(PrimeKPPState),.class_init=prime_kpp_class_init },
 { .name=TYPE_PRIME_ADC,.parent=TYPE_SYS_BUS_DEVICE,.instance_size=sizeof(PrimeADCState),.class_init=prime_adc_class_init },
 { .name=TYPE_PRIME_USBOTG,.parent=TYPE_SYS_BUS_DEVICE,.instance_size=sizeof(PrimeUSBOTGState),.instance_init=prime_usb_init,.class_init=prime_usb_class_init },
 { .name=TYPE_PRIME_G2_GOODIX,.parent=TYPE_I2C_SLAVE,.instance_size=sizeof(PrimeGoodixState),.instance_init=prime_goodix_init,.class_init=prime_goodix_class_init },
 { .name=TYPE_PRIME_G2_ILITEK,.parent=TYPE_I2C_SLAVE,.instance_size=sizeof(PrimeIlitekState),.instance_init=prime_ilitek_init,.class_init=prime_ilitek_class_init },
 { .name=TYPE_PRIME_G2_PF1550,.parent=TYPE_I2C_SLAVE,.instance_size=sizeof(PrimePF1550State),.instance_init=prime_pf_init,.class_init=prime_pf_class_init },
 { .name=TYPE_PRIME_G2_NAND,.parent=TYPE_SYS_BUS_DEVICE,.instance_size=sizeof(PrimeNANDState),.instance_init=prime_nand_init,.instance_finalize=prime_nand_finalize,.class_init=prime_nand_class_init },
};
static void prime_types_init(void){unsigned i;for(i=0;i<ARRAY_SIZE(types);i++)type_register_static(&types[i]);}
type_init(prime_types_init)

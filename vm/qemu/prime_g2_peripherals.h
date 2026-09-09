/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HW_ARM_PRIME_G2_PERIPHERALS_H
#define HW_ARM_PRIME_G2_PERIPHERALS_H

#define TYPE_PRIME_G2_KPP "prime-g2-kpp"
#define TYPE_PRIME_G2_ADC "prime-g2-adc1"
#define TYPE_PRIME_G2_NAND "prime-g2-gpmi-bch"
#define TYPE_PRIME_G2_GOODIX "prime-g2-goodix-gt5688"
#define TYPE_PRIME_G2_ILITEK "prime-g2-ilitek-ili2117"
#define TYPE_PRIME_G2_PF1550 "prime-g2-pf1550"
#define TYPE_PRIME_G2_USBOTG "prime-g2-usbotg-device"
#define TYPE_PRIME_G2_MMDC "prime-g2-mmdc"

bool prime_g2_mmdc_initialized(void);
void prime_g2_mmdc_map_ddr_gate(MemoryRegion *ram);

/* Functional i.MX6ULL Boot ROM boundary.  The board reset path calls this
 * only when booting from NAND without an explicitly supplied QEMU kernel.
 * It scans the ROM FCB copies, validates the IVT/boot-data records, copies
 * the selected boot stream to DDR, and returns the image entry point. */
bool prime_g2_nand_has_backing(void);
bool prime_g2_nand_rom_load(uint32_t *entry, Error **errp);

#endif

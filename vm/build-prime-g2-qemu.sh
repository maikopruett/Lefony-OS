#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
QEMU_VERSION=v11.1.1
QEMU_COMMIT=c3d48b7d1e89604920e5b81b91140c2ad39a1943
# Bump this whenever an already-applied patch changes semantics. Keeping the
# patch-set revision in both paths prevents an old modified source tree or
# Meson object from silently surviving a corrected hardware model.
PATCHSET_REV=r70
SOURCE_DIR=${PRIME_G2_QEMU_SOURCE_DIR:-"$REPO_DIR/build/qemu-prime-g2-source-$QEMU_VERSION-$PATCHSET_REV"}
# Include the checkout identity: different clones must never share a Meson
# source link or objects, even when the upstream and patch revision match.
CHECKOUT_ID=$(printf '%s' "$REPO_DIR" | cksum | awk '{print $1}')
RUNTIME_ROOT=${PRIME_G2_QEMU_RUNTIME_ROOT:-"${TMPDIR:-/tmp}/lefony-qemu-prime-$CHECKOUT_ID-$QEMU_VERSION-$PATCHSET_REV"}
SOURCE_LINK="$RUNTIME_ROOT-source"
BUILD_DIR="$RUNTIME_ROOT-build"
OUTPUT=${PRIME_G2_QEMU_OUTPUT:-"$REPO_DIR/build/qemu-prime-g2/qemu-system-arm"}
PANEL_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-panel.patch"
FIDELITY_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-electrical-fidelity.patch"
PERIPHERALS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-peripherals.patch"
APBH_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-apbh.patch"
ILI9322_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-ili9322-datasheet.patch"
PWM_COUNTER_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-counter.patch"
USBOTG_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-usbotg-device.patch"
ADC_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-adc.patch"
STOCK_BOOT_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-stock-boot.patch"
NAND_ROM_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-nand-rom.patch"
SNVS_PWRKEY_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-snvs-pwrkey.patch"
SNVS_HPRTC_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-snvs-hprtc.patch"
ROM_RECOVERY_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-rom-recovery.patch"
RESET_STATUS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-reset-status.patch"
BOOT_STRAPS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-boot-straps.patch"
GPIO_PAD_STATUS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-gpio-pad-status.patch"
GPIO_PULLS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-gpio-pulls.patch"
REFRESH_CLOCK_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-refresh-clock.patch"

for tool in git ninja pkg-config; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing QEMU build dependency: $tool" >&2
    echo "On macOS: brew install ninja pkgconf" >&2
    exit 1
  fi
done

if [ ! -d "$SOURCE_DIR/.git" ]; then
  mkdir -p "$(dirname -- "$SOURCE_DIR")"
  git clone --depth 1 --branch "$QEMU_VERSION" \
    https://gitlab.com/qemu-project/qemu.git "$SOURCE_DIR"
fi

ACTUAL_COMMIT=$(git -C "$SOURCE_DIR" rev-parse HEAD)
if [ "$ACTUAL_COMMIT" != "$QEMU_COMMIT" ]; then
  echo "QEMU source is not the pinned $QEMU_VERSION commit: $ACTUAL_COMMIT" >&2
  exit 1
fi

if grep -q 'prime-g2-fault-fifo' \
    "$SOURCE_DIR/hw/display/imx6ul_lcdif.c" 2>/dev/null; then
  : # Ordered panel and electrical-fidelity patches are already present.
else
  if ! git -C "$SOURCE_DIR" apply --reverse --check \
      "$PANEL_PATCH" >/dev/null 2>&1; then
    git -C "$SOURCE_DIR" apply --check "$PANEL_PATCH"
    git -C "$SOURCE_DIR" apply "$PANEL_PATCH"
  fi
  git -C "$SOURCE_DIR" apply --check "$FIDELITY_PATCH"
  git -C "$SOURCE_DIR" apply "$FIDELITY_PATCH"
fi

# The board models are kept as ordinary reviewable source files in this repo;
# copy them into the exact pinned QEMU tree before applying the small glue patch.
cp "$REPO_DIR/vm/qemu/prime_g2_peripherals.c" "$SOURCE_DIR/hw/arm/prime_g2_peripherals.c"
cp "$REPO_DIR/vm/qemu/prime_g2_bch.c" "$SOURCE_DIR/hw/arm/prime_g2_bch.c"
cp "$REPO_DIR/vm/qemu/prime_g2_bch.h" "$SOURCE_DIR/hw/arm/prime_g2_bch.h"
cp "$REPO_DIR/vm/qemu/prime_g2_peripherals.h" "$SOURCE_DIR/include/hw/arm/prime_g2_peripherals.h"
if grep -q 'qdev_new(TYPE_PRIME_G2_NAND)' \
    "$SOURCE_DIR/hw/arm/fsl-imx6ul.c" 2>/dev/null; then
  : # Prime peripheral glue is already present; the board model was refreshed above.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$PERIPHERALS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$PERIPHERALS_PATCH"
  git -C "$SOURCE_DIR" apply "$PERIPHERALS_PATCH"
fi
if ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$APBH_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$APBH_PATCH"
  git -C "$SOURCE_DIR" apply "$APBH_PATCH"
fi
if grep -q 'ILI9322_CHIP_ID' \
    "$SOURCE_DIR/hw/display/imx6ul_lcdif.c" 2>/dev/null; then
  : # ILI9322 register model is already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$ILI9322_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$ILI9322_PATCH"
  git -C "$SOURCE_DIR" apply "$ILI9322_PATCH"
fi
if grep -q 'prime_pwm_enable_ns' \
    "$SOURCE_DIR/hw/display/imx6ul_lcdif.c" 2>/dev/null; then
  : # PWM7 counter register advances while the peripheral is enabled.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$PWM_COUNTER_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$PWM_COUNTER_PATCH"
  git -C "$SOURCE_DIR" apply "$PWM_COUNTER_PATCH"
fi
if grep -q 'qdev_new(TYPE_PRIME_G2_USBOTG)' \
    "$SOURCE_DIR/hw/arm/fsl-imx6ul.c" 2>/dev/null; then
  : # Prime USB device-mode model is already instantiated.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$USBOTG_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$USBOTG_PATCH"
  git -C "$SOURCE_DIR" apply "$USBOTG_PATCH"
fi
if ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$ADC_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$ADC_PATCH"
  git -C "$SOURCE_DIR" apply "$ADC_PATCH"
fi
if grep -q 'hp_prime_g2_init' "$SOURCE_DIR/hw/arm/mcimx6ul-evk.c" 2>/dev/null && \
    grep -q 'Prime firmware reads CBAR' "$SOURCE_DIR/hw/arm/fsl-imx6ul.c" 2>/dev/null && \
    grep -q 'imx_i2c_update_irq' "$SOURCE_DIR/hw/i2c/imx_i2c.c" 2>/dev/null && \
    grep -q 'SNVS_HPCOMR' "$SOURCE_DIR/hw/misc/imx7_snvs.c" 2>/dev/null; then
  : # Dedicated stock-firmware board boot accommodations are already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$STOCK_BOOT_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$STOCK_BOOT_PATCH"
  git -C "$SOURCE_DIR" apply "$STOCK_BOOT_PATCH"
fi
if grep -q 'hp_prime_g2_nand_boot' \
    "$SOURCE_DIR/hw/arm/mcimx6ul-evk.c" 2>/dev/null; then
  : # NAND FCB/DBBT/IVT Boot ROM handoff is already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$NAND_ROM_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$NAND_ROM_PATCH"
  git -C "$SOURCE_DIR" apply "$NAND_ROM_PATCH"
fi
if grep -q 'SNVS_DIAG_PWRKEY' \
    "$SOURCE_DIR/hw/misc/imx7_snvs.c" 2>/dev/null; then
  : # Prime SNVS power-key ingress is already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$SNVS_PWRKEY_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$SNVS_PWRKEY_PATCH"
  git -C "$SOURCE_DIR" apply "$SNVS_PWRKEY_PATCH"
fi
if grep -q 'SNVS_HPTAMR' \
    "$SOURCE_DIR/hw/misc/imx7_snvs.c" 2>/dev/null; then
  : # Prime SNVS high-power counter and alarm are already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$SNVS_HPRTC_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$SNVS_HPRTC_PATCH"
  git -C "$SOURCE_DIR" apply "$SNVS_HPRTC_PATCH"
fi
if grep -q 'rom-downloader' \
    "$SOURCE_DIR/hw/misc/imx6_src.c" 2>/dev/null; then
  : # Persistent bmode plus watchdog-to-ROM transition is already present.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$ROM_RECOVERY_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$ROM_RECOVERY_PATCH"
  git -C "$SOURCE_DIR" apply "$ROM_RECOVERY_PATCH"
fi
if grep -q 'SRC_SRSR accumulates' "$SOURCE_DIR/hw/misc/imx6_src.c" && \
    grep -q 'hp_prime_g2_rom_enter_image' "$SOURCE_DIR/hw/arm/mcimx6ul-evk.c"; then
  : # Later boot-strap wiring changes the reset patch's surrounding context.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$RESET_STATUS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$RESET_STATUS_PATCH"
  git -C "$SOURCE_DIR" apply "$RESET_STATUS_PATCH"
fi
if ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$BOOT_STRAPS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$BOOT_STRAPS_PATCH"
  git -C "$SOURCE_DIR" apply "$BOOT_STRAPS_PATCH"
fi
if grep -q 'PSR samples the pad' \
    "$SOURCE_DIR/hw/gpio/imx_gpio.c" 2>/dev/null; then
  : # Output pads are visible through PSR, matching i.MX6ULL pad sampling.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$GPIO_PAD_STATUS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$GPIO_PAD_STATUS_PATCH"
  git -C "$SOURCE_DIR" apply "$GPIO_PAD_STATUS_PATCH"
fi
if grep -q 'prime_gpio2_pulled_up' \
    "$SOURCE_DIR/hw/arm/fsl-imx6ul.c" 2>/dev/null; then
  : # Prime board pull resistors are already connected to GPIO2 inputs.
elif ! git -C "$SOURCE_DIR" apply --reverse --check \
    "$GPIO_PULLS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$GPIO_PULLS_PATCH"
  git -C "$SOURCE_DIR" apply "$GPIO_PULLS_PATCH"
fi

# Publish live GPMI/BCH clock roots after the existing CCM/board patches.
PWM_SOURCES_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-sources.patch"
if grep -q 'static void prime_pwm_clock_changed' "$SOURCE_DIR/hw/display/imx6ul_lcdif.c"; then
  : # The later live-clock patch replaces the source-selection context.
elif ! git -C "$SOURCE_DIR" apply --recount --reverse --check "$PWM_SOURCES_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --check "$PWM_SOURCES_PATCH"
  git -C "$SOURCE_DIR" apply --recount "$PWM_SOURCES_PATCH"
fi
GPT_STATUS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-gpt-status.patch"
if ! git -C "$SOURCE_DIR" apply --recount --reverse --check "$GPT_STATUS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --check "$GPT_STATUS_PATCH"
  git -C "$SOURCE_DIR" apply --recount "$GPT_STATUS_PATCH"
fi
NAND_CLOCK_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-nand-clocks.patch"
GPT_STATE_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-gpt-state.patch"
if ! git -C "$SOURCE_DIR" apply --recount --reverse --check "$GPT_STATE_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --check "$GPT_STATE_PATCH"
  git -C "$SOURCE_DIR" apply --recount "$GPT_STATE_PATCH"
fi
USBNC_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-usbnc.patch"
if ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$USBNC_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$USBNC_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$USBNC_PATCH"
fi
if grep -q 'pwm_ipg_clock = qdev_init_clock_out' "$SOURCE_DIR/hw/misc/imx6ul_ccm.c"; then
  : # Live PWM roots extend the already-applied NAND clock notifications.
elif ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$NAND_CLOCK_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$NAND_CLOCK_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$NAND_CLOCK_PATCH"
fi

PWM_CLOCKS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-clocks.patch"
if grep -q 'static void prime_pwm_fifo_reset' "$SOURCE_DIR/hw/display/imx6ul_lcdif.c"; then
  : # The later FIFO patch changes synchronization and migration context.
elif ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$PWM_CLOCKS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$PWM_CLOCKS_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$PWM_CLOCKS_PATCH"
fi

PWM_FIFO_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-fifo.patch"
if grep -q 'static void prime_pwm_advance' "$SOURCE_DIR/hw/display/imx6ul_lcdif.c"; then
  : # Timed event delivery extends the FIFO synchronization path.
elif ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$PWM_FIFO_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$PWM_FIFO_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$PWM_FIFO_PATCH"
fi

PWM_EVENTS_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-events.patch"
if ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$PWM_EVENTS_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$PWM_EVENTS_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$PWM_EVENTS_PATCH"
fi

PWM_SWAP_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-pwm-swap.patch"
if ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$PWM_SWAP_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$PWM_SWAP_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$PWM_SWAP_PATCH"
fi

MMDC_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-mmdc.patch"
if ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$MMDC_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$MMDC_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$MMDC_PATCH"
fi

DDR_GATE_PATCH="$REPO_DIR/vm/patches/qemu-prime-g2-ddr-gate.patch"
if ! git -C "$SOURCE_DIR" apply --recount --unidiff-zero --reverse --check "$DDR_GATE_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero --check "$DDR_GATE_PATCH"
  git -C "$SOURCE_DIR" apply --recount --unidiff-zero "$DDR_GATE_PATCH"
fi

# QEMU rejects source/build paths containing spaces. Stable short paths also
# let incremental Ninja builds survive between emulator runs.
ln -sfn "$SOURCE_DIR" "$SOURCE_LINK"
mkdir -p "$BUILD_DIR"
if ! git -C "$SOURCE_DIR" apply --reverse --check "$REFRESH_CLOCK_PATCH" >/dev/null 2>&1; then
  git -C "$SOURCE_DIR" apply --check "$REFRESH_CLOCK_PATCH"
  git -C "$SOURCE_DIR" apply "$REFRESH_CLOCK_PATCH"
fi

if [ ! -f "$BUILD_DIR/build.ninja" ]; then
  case "$(uname -s)" in
    Darwin) DISPLAY_OPTION=--enable-cocoa ;;
    *) DISPLAY_OPTION=--enable-sdl ;;
  esac
  (cd "$BUILD_DIR" && "$SOURCE_LINK/configure" \
    --target-list=arm-softmmu --disable-werror --disable-docs "$DISPLAY_OPTION")
fi
ninja -C "$BUILD_DIR" -j"${JOBS:-4}" qemu-system-arm

mkdir -p "$(dirname -- "$OUTPUT")"
TEMP_OUTPUT="${OUTPUT}.new"
case "$(uname -s)" in
  Darwin) cp -X "$BUILD_DIR/qemu-system-arm" "$TEMP_OUTPUT" ;;
  *) cp "$BUILD_DIR/qemu-system-arm" "$TEMP_OUTPUT" ;;
esac
if command -v codesign >/dev/null 2>&1; then
  # A replaced destination can retain Finder attributes even with cp -X.
  xattr -c "$TEMP_OUTPUT"
  codesign --force --sign - "$TEMP_OUTPUT" >/dev/null
fi
mv -f "$TEMP_OUTPUT" "$OUTPUT"
echo "$OUTPUT"

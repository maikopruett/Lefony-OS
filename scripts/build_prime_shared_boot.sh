#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# One compiled bootloader core, two explicit embedded NAND configurations.
# No device access; preserves the accepted historical build outputs.
set -eu
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO/build/lefony-uboot-shared-src"
OUTPUT="$REPO/build/lefony-uboot-shared"
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1790467200}
PRIME_DUAL_SOURCE_DIR="$SOURCE" PRIME_DUAL_OUTPUT_DIR="$OUTPUT" \
  "$REPO/scripts/build_prime_dual_boot.sh"
for profile in dual simple; do
  layout=5; [ "$profile" != simple ] || layout=1
  "$REPO/.venv/bin/python" "$REPO/scripts/prepare_prime_shared_boot.py" "$SOURCE" --layout "$layout"
  docker run --rm -e SOURCE_DATE_EPOCH -v "$REPO:/work" -v "$SOURCE:/hp-src" -v "$OUTPUT:/hp-out" -w /hp-src \
    lefony-prime-g2-u-boot sh -ec '
    make O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
    make -j8 O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi-
  '
  mkdir -p "$OUTPUT/$profile"
  for file in u-boot-dtb.bin u-boot-dtb.imx u-boot-nodtb.bin u-boot.dtb .config; do
    cp "$OUTPUT/$file" "$OUTPUT/$profile/$file"
  done
  "$REPO/.venv/bin/python" "$REPO/scripts/pad_uboot.py" "$OUTPUT/$profile/u-boot-dtb.imx" "$OUTPUT/$profile/nand.imx"
done
cmp "$OUTPUT/dual/u-boot-nodtb.bin" "$OUTPUT/simple/u-boot-nodtb.bin"
shasum -a 256 "$OUTPUT"/dual/*.bin "$OUTPUT"/simple/*.bin "$OUTPUT"/dual/*.imx "$OUTPUT"/simple/*.imx > "$OUTPUT/SHA256SUMS"
printf '%s\n' 'Both profiles share exactly the same U-Boot core; only embedded boot-layout configuration differs.'

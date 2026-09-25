#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Build the existing single-slot Prime board, with one-shot U-Boot SDP.
set -eu
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO/build/lefony-uboot-oneshot-src"
OUTPUT="$REPO/build/lefony-uboot-oneshot"
REV=83c84d5e5b7a72855f4455c499b23ee6ead4f74d
if [ ! -d "$SOURCE/.git" ]; then
  git clone --filter=blob:none --no-checkout https://github.com/zephray/uboot.git "$SOURCE"
fi
# This is an exclusively generated checkout, never the user's source tree.
git -C "$SOURCE" fetch --depth 1 origin "$REV"
git -C "$SOURCE" checkout --detach "$REV"
git -C "$SOURCE" reset --hard "$REV"
git -C "$SOURCE" clean -fdx
git -C "$SOURCE" apply "$REPO/native/prime_g2/u-boot-lefony-oneshot-sdp.patch"
mkdir -p "$OUTPUT"
docker image inspect lefony-prime-g2-u-boot >/dev/null 2>&1 ||
  docker build -f "$REPO/vm/Dockerfile.u-boot" -t lefony-prime-g2-u-boot "$REPO/vm"
docker run --rm -v "$REPO:/work" -w /work/build/lefony-uboot-oneshot-src \
  lefony-prime-g2-u-boot sh -ec '
  make O=../lefony-uboot-oneshot HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
  make -j8 O=../lefony-uboot-oneshot HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi-
'
python3 "$REPO/scripts/pad_uboot.py" "$OUTPUT/u-boot-dtb.imx" "$OUTPUT/lefony-oneshot-nand.imx"
# Deliberately do not modify NAND layout/default environment or auto-flash.
shasum -a 256 "$OUTPUT/u-boot-dtb.imx" "$OUTPUT/u-boot-dtb.bin" "$OUTPUT/lefony-oneshot-nand.imx" > "$OUTPUT/SHA256SUMS"
printf '%s\n' "zephray/uboot $REV + u-boot-lefony-oneshot-sdp.patch" > "$OUTPUT/UPSTREAM"

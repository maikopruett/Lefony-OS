#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Separate candidate: preserve the known one-shot build and never flash here.
set -eu
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO/build/lefony-uboot-bootmenu-src"
OUTPUT="$REPO/build/lefony-uboot-bootmenu"
REV=83c84d5e5b7a72855f4455c499b23ee6ead4f74d
if [ ! -d "$SOURCE/.git" ]; then
  git clone --filter=blob:none --no-checkout https://github.com/zephray/uboot.git "$SOURCE"
fi
git -C "$SOURCE" fetch --depth 1 origin "$REV"
git -C "$SOURCE" checkout --detach "$REV"
git -C "$SOURCE" reset --hard "$REV"
git -C "$SOURCE" clean -fdx
git -C "$SOURCE" apply "$REPO/native/prime_g2/u-boot-lefony-oneshot-sdp.patch"
"$REPO/.venv/bin/python" "$REPO/scripts/prepare_prime_bootmenu.py" "$SOURCE"
mkdir -p "$OUTPUT"
docker image inspect lefony-prime-g2-u-boot >/dev/null 2>&1 ||
  docker build -f "$REPO/vm/Dockerfile.u-boot" -t lefony-prime-g2-u-boot "$REPO/vm"
docker run --rm -v "$REPO:/work" -w /work/build/lefony-uboot-bootmenu-src \
  lefony-prime-g2-u-boot sh -ec '
  make O=../lefony-uboot-bootmenu HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
  make -j8 O=../lefony-uboot-bootmenu HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi-
'
"$REPO/.venv/bin/python" "$REPO/scripts/pad_uboot.py" "$OUTPUT/u-boot-dtb.imx" "$OUTPUT/lefony-bootmenu-nand.imx"
shasum -a 256 "$OUTPUT/u-boot-dtb.imx" "$OUTPUT/u-boot-dtb.bin" "$OUTPUT/lefony-bootmenu-nand.imx" > "$OUTPUT/SHA256SUMS"
printf '%s\n' "zephray/uboot $REV + one-shot SDP + native/prime_g2/bootmenu" > "$OUTPUT/UPSTREAM"

#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# RAM diagnostic only. Separate artifacts, no signing or device operations.
set -eu
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO/build/lefony-dual-diagnostic-src"
OUTPUT="$REPO/build/lefony-dual-diagnostic"
PRIME_DUAL_SOURCE_DIR="$SOURCE" PRIME_DUAL_OUTPUT_DIR="$OUTPUT" \
  "$REPO/scripts/build_prime_dual_boot.sh"
"$REPO/.venv/bin/python" "$REPO/scripts/prepare_prime_dual_diagnostic.py" "$SOURCE"
docker run --rm -v "$REPO:/work" -v "$SOURCE:/hp-src" -v "$OUTPUT:/hp-out" -w /hp-src \
  lefony-prime-g2-u-boot sh -ec '
  make O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
  make -j8 O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi-
'
shasum -a 256 "$OUTPUT/u-boot-dtb.bin" "$OUTPUT/u-boot-dtb.imx" > "$OUTPUT/SHA256SUMS"

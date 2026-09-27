#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Separate dual candidate. No key creation, signing or device access.
set -eu
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE=${PRIME_DUAL_SOURCE_DIR:-"$REPO/build/lefony-uboot-dual5-src"}
OUTPUT=${PRIME_DUAL_OUTPUT_DIR:-"$REPO/build/lefony-uboot-dual5"}
PUBLIC_KEY=${LEFONY_DUAL_PUBLIC_KEY:-"$REPO/build/lefony-update-signing/release-public.pem"}
test -s "$PUBLIC_KEY"
# Reuse the pinned preparation/build path; all modifications remain in the
# checked-in preparation script. The second make compiles the dual additions.
PRIME_HP_HANDOFF_SOURCE_DIR="$SOURCE" PRIME_HP_HANDOFF_OUTPUT_DIR="$OUTPUT" \
  "$REPO/scripts/build_prime_hp_handoff.sh"
"$REPO/.venv/bin/python" "$REPO/scripts/prepare_prime_dual_boot.py" "$SOURCE" --public-key "$PUBLIC_KEY"
docker run --rm -v "$REPO:/work" -v "$SOURCE:/hp-src" -v "$OUTPUT:/hp-out" -w /hp-src \
  lefony-prime-g2-u-boot sh -ec '
  make O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
  make -j8 O=/hp-out HOSTCFLAGS="-O2 -fcommon" CROSS_COMPILE=arm-none-eabi-
'
shasum -a 256 "$OUTPUT/u-boot-dtb.bin" "$OUTPUT/u-boot-dtb.imx" > "$OUTPUT/SHA256SUMS"

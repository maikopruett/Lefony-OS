#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Experimental RAM recovery only. No USB or NAND operations.
# Usage: script /private/config.gz /private/u-boot-dtb.bin expected-uboot-sha256
set -eu
[ "$#" -eq 3 ] || { echo "Expected config.gz, U-Boot binary, exact SHA-256" >&2; exit 2; }
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT="$REPO/build/prime-hp-ram-recovery"
mkdir -p "$OUTPUT"
"$REPO/.venv/bin/python" - "$1" "$2" "$3" "$OUTPUT" <<'PY'
import gzip, hashlib, pathlib, re, sys
config, payload, expected, output = sys.argv[1:]
output = pathlib.Path(output)
data = pathlib.Path(payload).read_bytes()
if not re.fullmatch('[0-9a-f]{64}', expected) or hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit('U-Boot identity mismatch')
if not 0x100 <= len(data) <= 0xff000 or data[3] != 0xea:
    raise SystemExit('Expected complete ARM U-Boot/DTB binary')
text = gzip.decompress(pathlib.Path(config).read_bytes()).decode()
for required in ('# CONFIG_KEXEC is not set', 'CONFIG_ARCH_MXC=y',
                 'CONFIG_MTD_NAND_GPMI_NAND=y', 'CONFIG_CPU_V7=y'):
    if required not in text.splitlines():
        raise SystemExit('Unexpected baseline recovery configuration: ' + required)
(output / 'input.config').write_text(text.replace('# CONFIG_KEXEC is not set', 'CONFIG_KEXEC=y'))
(output / 'u-boot-dtb.bin').write_bytes(data)
(output / 'UBOOT-SHA256').write_text(expected + '\n')
PY
REV=5d6cbeafb80c52af322a45985aa7b41f9b9ec66c
ARCHIVE="$OUTPUT/linux-imx.tar.gz"
if [ ! -f "$ARCHIVE" ]; then
  curl -fL --retry 2 --max-time 180 "https://codeload.github.com/nxp-imx/linux-imx/tar.gz/$REV" -o "$ARCHIVE"
fi
ACTUAL=$(shasum -a 256 "$ARCHIVE" | cut -d ' ' -f 1)
[ "$ACTUAL" = dd3156a447230188af2f28afb52fae9b3c54110ff65ab4abb1e48a1227ddd7b0 ] ||
  { echo 'Pinned kernel archive identity mismatch' >&2; exit 1; }
docker image inspect lefony-prime-g2-u-boot >/dev/null 2>&1 ||
  docker build -f "$REPO/vm/Dockerfile.u-boot" -t lefony-prime-g2-u-boot "$REPO/vm"
# Linux source contains case-distinct filenames; build in the container's Linux
# filesystem, not the commonly case-insensitive host checkout. lzop is required
# by the unchanged original kernel compression setting.
docker run --rm -v "$OUTPUT:/out" -v "$REPO/native/prime_g2/hp_handoff:/helper:ro" \
  lefony-prime-g2-u-boot sh -ec '
  apt-get update -qq
  apt-get install -y --no-install-recommends lzop
  mkdir /src
  tar -xzf /out/linux-imx.tar.gz --strip-components=1 -C /src
  cd /src
  cp /out/input.config .config
  make ARCH=arm CROSS_COMPILE=arm-none-eabi- HOSTCFLAGS="-O2 -fcommon" olddefconfig
  make -j8 ARCH=arm CROSS_COMPILE=arm-none-eabi- HOSTCFLAGS="-O2 -fcommon" zImage
  cp arch/arm/boot/zImage /out/recovery-kexec-zImage
  cp .config /out/recovery-kexec.config
  cp System.map /out/recovery-kexec-System.map
  cd /out
  arm-none-eabi-gcc -Os -marm -march=armv7-a -nostdlib -static -fno-builtin \
    -Wall -Wextra -Werror -Wl,-e,_start -Wl,--build-id=none -Wl,-z,noexecstack \
    -DUBOOT_PAYLOAD=\"u-boot-dtb.bin\" /helper/kexec_uboot.c /helper/kexec_uboot.S \
    -lgcc -o kexec-uboot
  sha256sum recovery-kexec-zImage kexec-uboot u-boot-dtb.bin > SHA256SUMS
'
printf '%s\n' "NXP linux-imx $REV; original recovery configuration plus CONFIG_KEXEC" > "$OUTPUT/UPSTREAM"

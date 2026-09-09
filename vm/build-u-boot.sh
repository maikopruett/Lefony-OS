#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_DIR=${UBOOT_SOURCE_DIR:-"$REPO_DIR/build/u-boot-prime-g2-vm"}
OUTPUT_DIR=${UBOOT_OUTPUT_DIR:-"$REPO_DIR/build/prime-g2-native-vm/u-boot"}
UBOOT_REPOSITORY=${UBOOT_REPOSITORY:-"https://source.denx.de/u-boot/u-boot.git"}
UBOOT_REVISION=${UBOOT_REVISION:-"ece349ade2973e220f524ce59e59711cc919263f"}
BOOT_FORMAT=${UBOOT_BOOT_FORMAT:-elf}

case "$BOOT_FORMAT" in
  elf)
    BOOTCOMMAND='echo Lefony OS: loading native payload from mmc 0:1; if mmc dev 0; then if fatload mmc 0:1 0x87ff0000 upsilon.env; then if env import -t 0x87ff0000 ${filesize}; then if fatload mmc 0:1 0x88000000 lefony-os.elf; then if test ${filesize} = ${upsilon_size}; then hash sha256 0x88000000 ${filesize} upsilon_actual; if test ${upsilon_actual} = ${upsilon_sha256}; then echo Lefony OS: verified native payload; echo Lefony OS: starting from boot media; setenv autostart yes; bootelf -p 0x88000000; else echo ERROR: lefony-os.elf checksum mismatch; fi; else echo ERROR: lefony-os.elf length mismatch; fi; else echo ERROR: lefony-os.elf missing or unreadable; fi; else echo ERROR: invalid upsilon.env manifest; fi; else echo ERROR: upsilon.env missing or unreadable; fi; else echo ERROR: boot media unavailable; fi'
    ;;
  capsule)
    BOOTCOMMAND='echo Lefony OS: loading Prime NAND capsule from mmc 0:1; if mmc dev 0; then if fatload mmc 0:1 0x87ff0000 upsilon.env; then if env import -t 0x87ff0000 ${filesize}; then if fatload mmc 0:1 0x80800000 lefony-os.zImage; then if test ${filesize} = ${upsilon_size}; then hash sha256 0x80800000 ${filesize} upsilon_actual; if test ${upsilon_actual} = ${upsilon_sha256}; then echo Lefony OS: verified Prime NAND capsule; echo Lefony OS: entering capsule through bootz; bootz 0x80800000; else echo ERROR: lefony-os.zImage checksum mismatch; fi; else echo ERROR: lefony-os.zImage length mismatch; fi; else echo ERROR: lefony-os.zImage missing or unreadable; fi; else echo ERROR: invalid upsilon.env manifest; fi; else echo ERROR: upsilon.env missing or unreadable; fi; else echo ERROR: boot media unavailable; fi'
    ;;
  ab)
    BOOTCOMMAND='if lefony_ab boot; then bootz 0x80800000; else echo Lefony A/B: loading factory capsule from mmc 0:1; if mmc dev 0; then if fatload mmc 0:1 0x87fe0000 upsilon.env; then if env import -t 0x87fe0000 ${filesize}; then if fatload mmc 0:1 0x80800000 lefony-os.zImage; then if test ${filesize} = ${upsilon_size}; then hash sha256 0x80800000 ${filesize} upsilon_actual; if test ${upsilon_actual} = ${upsilon_sha256}; then if lefony_ab seed 0x80800000 ${filesize}; then bootz 0x80800000; else echo ERROR: Lefony A/B factory seed failed; fi; else echo ERROR: lefony-os.zImage checksum mismatch; fi; else echo ERROR: lefony-os.zImage length mismatch; fi; else echo ERROR: lefony-os.zImage missing or unreadable; fi; else echo ERROR: invalid upsilon.env manifest; fi; else echo ERROR: upsilon.env missing or unreadable; fi; else echo ERROR: boot media unavailable; fi; fi'
    ;;
  *)
    echo "UBOOT_BOOT_FORMAT must be elf, capsule, or ab." >&2
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "A running Docker engine is required to build U-Boot." >&2
  exit 1
fi

mkdir -p "$REPO_DIR/build" "$OUTPUT_DIR"
if [ ! -d "$SOURCE_DIR/.git" ]; then
  git clone --filter=blob:none "$UBOOT_REPOSITORY" "$SOURCE_DIR"
fi
git -C "$SOURCE_DIR" fetch --depth 1 origin "$UBOOT_REVISION"
git -C "$SOURCE_DIR" checkout --detach "$UBOOT_REVISION"
git -C "$SOURCE_DIR" reset --hard "$UBOOT_REVISION"
git -C "$SOURCE_DIR" clean -fdx
git -C "$SOURCE_DIR" apply "$REPO_DIR/vm/patches/u-boot-qemu-memory.patch"
if [ "$BOOT_FORMAT" = ab ]; then
  git -C "$SOURCE_DIR" apply "$REPO_DIR/vm/patches/u-boot-lefony-ab-command.patch"
  cp "$REPO_DIR/vm/u-boot/lefony_ab.c" "$SOURCE_DIR/cmd/lefony_ab.c"
fi

docker build -f "$REPO_DIR/vm/Dockerfile.u-boot" \
  -t lefony-prime-g2-u-boot "$REPO_DIR/vm"
docker run --rm \
  -e BOOTCOMMAND="$BOOTCOMMAND" \
  -v "$SOURCE_DIR:/src" -w /src \
  lefony-prime-g2-u-boot sh -ec '
    make CROSS_COMPILE=arm-none-eabi- mx6ull_14x14_evk_defconfig
    scripts/config --enable OF_EMBED --disable OF_SEPARATE \
      --disable FSL_DCP_RNG \
      --disable NET --disable FEC_MXC \
      --enable CMD_HASH --enable SHA256 \
      --enable SUPPORT_PASSING_ATAGS \
      --disable ENV_IS_IN_MMC --enable ENV_IS_NOWHERE \
      --set-val BOOTDELAY 0 \
      --set-str BOOTCOMMAND "$BOOTCOMMAND"
    make CROSS_COMPILE=arm-none-eabi- olddefconfig
    make CROSS_COMPILE=arm-none-eabi- -j"${JOBS:-4}"
  '

test -s "$SOURCE_DIR/u-boot"
test -s "$SOURCE_DIR/u-boot.bin"
cp "$SOURCE_DIR/u-boot" "$OUTPUT_DIR/u-boot.elf"
cp "$SOURCE_DIR/u-boot.bin" "$OUTPUT_DIR/u-boot.bin"
echo "$OUTPUT_DIR/u-boot.elf"

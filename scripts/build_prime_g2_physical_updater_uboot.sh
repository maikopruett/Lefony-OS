#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_DIR=${LEFONY_UBOOT_SOURCE_DIR:-"$REPO_DIR/build/lefony-prime-g2-u-boot"}
OUTPUT_DIR=${LEFONY_UBOOT_OUTPUT_DIR:-"$REPO_DIR/build/lefony-prime-g2-u-boot-output"}
REPOSITORY=${LEFONY_UBOOT_REPOSITORY:-"https://github.com/zephray/uboot.git"}
REVISION=${LEFONY_UBOOT_REVISION:-"83c84d5e5b7a72855f4455c499b23ee6ead4f74d"}

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "A running Docker engine is required to build physical U-Boot." >&2
  exit 1
fi

mkdir -p "$REPO_DIR/build" "$OUTPUT_DIR"
if [ ! -d "$SOURCE_DIR/.git" ]; then
  git clone --filter=blob:none "$REPOSITORY" "$SOURCE_DIR"
fi
git -C "$SOURCE_DIR" fetch --depth 1 origin "$REVISION"
git -C "$SOURCE_DIR" checkout --detach "$REVISION"
git -C "$SOURCE_DIR" reset --hard "$REVISION"
git -C "$SOURCE_DIR" clean -fdx
git -C "$SOURCE_DIR" apply "$REPO_DIR/native/prime_g2/u-boot-lefony-ab.patch"
cp "$REPO_DIR/native/prime_g2/lefony_ab_physical.c" "$SOURCE_DIR/cmd/lefony_ab.c"

docker build -f "$REPO_DIR/vm/Dockerfile.u-boot" \
  -t lefony-prime-g2-u-boot "$REPO_DIR/vm" >/dev/null
docker run --rm -v "$SOURCE_DIR:/src" -w /src \
  lefony-prime-g2-u-boot sh -ec '
    make HOSTCFLAGS=-fcommon CROSS_COMPILE=arm-none-eabi- mx6ull_prime_defconfig
    make HOSTCFLAGS=-fcommon CROSS_COMPILE=arm-none-eabi- -j"${JOBS:-4}"
  '

test -s "$SOURCE_DIR/u-boot-dtb.imx"
cp "$SOURCE_DIR/u-boot-dtb.imx" "$OUTPUT_DIR/u-boot-dtb-lefony-ab.imx"
python3 "$REPO_DIR/scripts/patch_uboot_env.py" nandboot \
  "$OUTPUT_DIR/u-boot-dtb-lefony-ab.imx" \
  "$OUTPUT_DIR/u-boot-dtb-lefony-ab-nandboot.imx"
python3 "$REPO_DIR/scripts/pad_uboot.py" \
  "$OUTPUT_DIR/u-boot-dtb-lefony-ab-nandboot.imx" \
  "$OUTPUT_DIR/u-boot-dtb-lefony-ab-nandboot-pad.imx"

python3 "$REPO_DIR/scripts/lefony_uboot_history.py" record \
  --artifact "$OUTPUT_DIR/u-boot-dtb-lefony-ab-nandboot-pad.imx" \
  --source "$REPO_DIR" \
  --upstream-revision "$REVISION" \
  --status unverified \
  --notes "${LEFONY_UBOOT_BUILD_NOTES:-Physical A/B U-Boot build; awaiting NAND readback and cold-boot qualification.}"

shasum -a 256 "$OUTPUT_DIR"/*.imx
echo "$OUTPUT_DIR/u-boot-dtb-lefony-ab-nandboot-pad.imx"

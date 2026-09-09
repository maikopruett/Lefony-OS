#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PAYLOAD=${1:-"$REPO_DIR/dist/lefony-os-prime-g2-native.bin"}
OUTPUT=${2:-"$REPO_DIR/build/lefony-os-native-nand/lefony-os-native.zImage"}
BUILD_DIR=$(dirname -- "$OUTPUT")
LOADER_SOURCE="$REPO_DIR/native/prime_g2/nand_boot_capsule.S"
LINKER_SCRIPT="$REPO_DIR/native/prime_g2/nand_boot_capsule.ld"
MAX_CAPSULE_BYTES=$((8 * 1024 * 1024))
PAYLOAD_OFFSET=4096

if [ ! -s "$PAYLOAD" ]; then
  echo "Native payload is missing: $PAYLOAD" >&2
  exit 2
fi

PAYLOAD_BYTES=$(wc -c <"$PAYLOAD" | tr -d ' ')
if [ $((PAYLOAD_BYTES % 4)) -ne 0 ]; then
  echo "Native payload size must be a multiple of four bytes." >&2
  exit 2
fi
if [ $((PAYLOAD_OFFSET + 4 + PAYLOAD_BYTES)) -gt "$MAX_CAPSULE_BYTES" ]; then
  echo "Native capsule exceeds the 8 MiB NAND kernel slot." >&2
  exit 2
fi
mkdir -p "$BUILD_DIR"
if command -v arm-none-eabi-gcc >/dev/null 2>&1 &&
    command -v arm-none-eabi-ld >/dev/null 2>&1 &&
    command -v arm-none-eabi-objcopy >/dev/null 2>&1; then
  arm-none-eabi-gcc -c -mcpu=cortex-a7 -marm -ffreestanding \
    -DNATIVE_PAYLOAD_BYTES="$PAYLOAD_BYTES" \
    -o "${OUTPUT}.loader.o" "$LOADER_SOURCE"
  arm-none-eabi-ld -T "$LINKER_SCRIPT" -o "${OUTPUT}.loader.elf" "${OUTPUT}.loader.o"
  arm-none-eabi-objcopy -O binary "${OUTPUT}.loader.elf" "${OUTPUT}.loader.bin"
else
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Need the ARM bare-metal toolchain or a running Docker engine to build the NAND capsule." >&2
  exit 1
fi

docker image inspect lefony-prime-g2-u-boot >/dev/null 2>&1 || \
  docker build -f "$REPO_DIR/vm/Dockerfile.u-boot" \
    -t lefony-prime-g2-u-boot "$REPO_DIR/vm" >/dev/null

docker run --rm \
  -v "$REPO_DIR:/work" -w /work \
  -e LOADER_SOURCE="/work/${LOADER_SOURCE#"$REPO_DIR/"}" \
  -e LINKER_SCRIPT="/work/${LINKER_SCRIPT#"$REPO_DIR/"}" \
  -e OUTPUT="/work/${OUTPUT#"$REPO_DIR/"}" \
  -e PAYLOAD_BYTES="$PAYLOAD_BYTES" \
  lefony-prime-g2-u-boot sh -ec '
    object=${OUTPUT}.loader.o
    elf=${OUTPUT}.loader.elf
    binary=${OUTPUT}.loader.bin
    arm-none-eabi-gcc -c -mcpu=cortex-a7 -marm -ffreestanding \
      -DNATIVE_PAYLOAD_BYTES="$PAYLOAD_BYTES" \
      -o "$object" "$LOADER_SOURCE"
    arm-none-eabi-ld -T "$LINKER_SCRIPT" -o "$elf" "$object"
    arm-none-eabi-objcopy -O binary "$elf" "$binary"
  '
fi

LOADER_BINARY="${OUTPUT}.loader.bin"
LOADER_BYTES=$(wc -c <"$LOADER_BINARY" | tr -d ' ')
if [ "$LOADER_BYTES" -ne "$PAYLOAD_OFFSET" ]; then
  echo "Unexpected loader size: $LOADER_BYTES" >&2
  exit 2
fi

cp "$LOADER_BINARY" "$OUTPUT"
dd if="$PAYLOAD" of="$OUTPUT" bs=4096 seek=1 conv=notrunc 2>/dev/null

CAPSULE_BYTES=$(wc -c <"$OUTPUT" | tr -d ' ')
# Record the complete capsule size in the zImage end field at offset 0x2c.
perl -e 'print pack("V", $ARGV[0])' "$CAPSULE_BYTES" | \
  dd of="$OUTPUT" bs=1 seek=44 conv=notrunc 2>/dev/null
MAGIC=$(dd if="$OUTPUT" bs=1 skip=36 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')
if [ "$MAGIC" != "18286f01" ]; then
  echo "Invalid zImage magic in generated capsule: $MAGIC" >&2
  exit 2
fi
if [ "$CAPSULE_BYTES" -ne $((PAYLOAD_OFFSET + PAYLOAD_BYTES)) ]; then
  echo "Unexpected capsule size: $CAPSULE_BYTES" >&2
  exit 2
fi

{
  echo "capsule_bytes=$CAPSULE_BYTES"
  echo "payload_bytes=$PAYLOAD_BYTES"
  echo "capsule_sha256=$(shasum -a 256 "$OUTPUT" | awk '{print $1}')"
  echo "payload_sha256=$(shasum -a 256 "$PAYLOAD" | awk '{print $1}')"
} >"${OUTPUT}.manifest"

python3 "$REPO_DIR/scripts/lefony_build_history.py" record \
  --artifact "$OUTPUT" \
  --kind recovery-capsule \
  --notes "${LEFONY_BUILD_NOTES:-}"

echo "$OUTPUT"
cat "${OUTPUT}.manifest"

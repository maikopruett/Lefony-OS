#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO_DIR/native/prime_g2/rom_recovery_stub.S"
LINKER="$REPO_DIR/native/prime_g2/rom_recovery_stub.ld"
OUTPUT=${1:-"$REPO_DIR/build/prime-g2-rom-recovery/rom-recovery.bin"}
OUTPUT_DIR=$(dirname -- "$OUTPUT")

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "A running Docker engine is required to build the ROM recovery stub." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
docker image inspect lefony-prime-g2-u-boot >/dev/null 2>&1 || \
  docker build -f "$REPO_DIR/vm/Dockerfile.u-boot" \
    -t lefony-prime-g2-u-boot "$REPO_DIR/vm" >/dev/null

docker run --rm \
  -v "$REPO_DIR:/work" -w /work \
  -e SOURCE="/work/${SOURCE#"$REPO_DIR/"}" \
  -e LINKER="/work/${LINKER#"$REPO_DIR/"}" \
  -e OUTPUT="/work/${OUTPUT#"$REPO_DIR/"}" \
  lefony-prime-g2-u-boot sh -ec '
    object=${OUTPUT}.o
    elf=${OUTPUT}.elf
    arm-none-eabi-gcc -c -mcpu=cortex-a7 -marm -ffreestanding \
      -fno-pic -fno-pie -o "$object" "$SOURCE"
    arm-none-eabi-ld -T "$LINKER" -o "$elf" "$object"
    arm-none-eabi-objcopy -O binary "$elf" "$OUTPUT"
    arm-none-eabi-size "$elf"
  '

BYTES=$(wc -c <"$OUTPUT" | tr -d ' ')
if [ "$BYTES" -gt 4096 ]; then
  echo "ROM recovery stub exceeds one page: $BYTES bytes" >&2
  exit 2
fi
echo "$OUTPUT ($BYTES bytes)"

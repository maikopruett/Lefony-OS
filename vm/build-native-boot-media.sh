#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PAYLOAD=${NATIVE_ELF:-"$REPO_DIR/dist/lefony-os-prime-g2-vm-native.elf"}
PAYLOAD_FILENAME=${NATIVE_BOOT_PAYLOAD_FILENAME:-lefony-os.elf}
OUTPUT=${NATIVE_BOOT_MEDIA:-"$REPO_DIR/build/prime-g2-native-vm/lefony-os-boot.img"}
MEDIA_SIZE_MIB=${NATIVE_BOOT_MEDIA_SIZE_MIB:-128}
PARTITION_SIZE_MIB=63
PARTITION_START=2048
TOTAL_SECTORS=$((MEDIA_SIZE_MIB * 2048))
PARTITION_SECTORS=$((PARTITION_SIZE_MIB * 2048))
PARTITION_SIZE_KIB=$((PARTITION_SIZE_MIB * 1024))
SOURCE_EPOCH=${NATIVE_BOOT_MEDIA_EPOCH:-1704067200}
MAX_PAYLOAD_BYTES=$((8 * 1024 * 1024))

if [ "$MEDIA_SIZE_MIB" -lt 65 ]; then
  echo "Native boot media must be at least 65 MiB." >&2
  exit 2
fi
if [ ! -s "$PAYLOAD" ]; then
  "$REPO_DIR/scripts/build_lefony_prime_g2_vm.sh"
fi
PAYLOAD_BYTES=$(wc -c <"$PAYLOAD" | tr -d ' ')
if [ "$PAYLOAD_BYTES" -gt "$MAX_PAYLOAD_BYTES" ]; then
  echo "Native payload exceeds the 8 MiB staging window." >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "A running Docker engine is required to build native boot media." >&2
  exit 1
fi

mkdir -p "$(dirname -- "$OUTPUT")"
docker build -f "$REPO_DIR/vm/Dockerfile.u-boot" \
  -t lefony-prime-g2-u-boot "$REPO_DIR/vm" >/dev/null
docker run --rm \
  -e PAYLOAD=/work/${PAYLOAD#"$REPO_DIR/"} \
  -e PAYLOAD_FILENAME="$PAYLOAD_FILENAME" \
  -e OUTPUT=/work/${OUTPUT#"$REPO_DIR/"} \
  -e MEDIA_SIZE_MIB="$MEDIA_SIZE_MIB" \
  -e PARTITION_SECTORS="$PARTITION_SECTORS" \
  -e PARTITION_SIZE_KIB="$PARTITION_SIZE_KIB" \
  -e SOURCE_EPOCH="$SOURCE_EPOCH" \
  -v "$REPO_DIR:/work" -w /work \
  lefony-prime-g2-u-boot sh -ec '
    rm -f "$OUTPUT"
    truncate -s "${MEDIA_SIZE_MIB}M" "$OUTPUT"
    sfdisk "$OUTPUT" <<EOF
label: dos
label-id: 0x4d414841
unit: sectors
first-lba: 2048

start=2048, size=$PARTITION_SECTORS, type=c, bootable
EOF
    mkfs.fat --invariant -F 32 -n LEFONYBOOT --offset=2048 \
      "$OUTPUT" "$PARTITION_SIZE_KIB"
    stage=$(mktemp -d)
    cp "$PAYLOAD" "$stage/$PAYLOAD_FILENAME"
    payload_hash=$(sha256sum "$stage/$PAYLOAD_FILENAME" | cut -d " " -f 1)
    payload_size=$(wc -c <"$stage/$PAYLOAD_FILENAME" | tr -d " ")
    printf "upsilon_size=%x\nupsilon_sha256=%s\n" \
      "$payload_size" "$payload_hash" >"$stage/upsilon.env"
    touch -d "@$SOURCE_EPOCH" "$stage/$PAYLOAD_FILENAME" "$stage/upsilon.env"
    mcopy -m -i "$OUTPUT@@1048576" "$stage/$PAYLOAD_FILENAME" ::/"$PAYLOAD_FILENAME"
    mcopy -m -i "$OUTPUT@@1048576" "$stage/upsilon.env" ::/upsilon.env
    rm -rf "$stage"
  '

test -s "$OUTPUT"
echo "$OUTPUT"

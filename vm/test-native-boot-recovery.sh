#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=${NATIVE_BOOT_RECOVERY_DIR:-"$REPO_DIR/build/prime-g2-native-recovery"}
case "$TEST_DIR" in
  /*) ;;
  *) TEST_DIR="$REPO_DIR/$TEST_DIR" ;;
esac
case "$TEST_DIR" in
  "$REPO_DIR"/*) TEST_DIR_REL=${TEST_DIR#"$REPO_DIR/"} ;;
  *)
    echo "NATIVE_BOOT_RECOVERY_DIR must be inside the repository." >&2
    exit 2
    ;;
esac
BASE_IMAGE="$TEST_DIR/repro-a.img"
SECOND_IMAGE="$TEST_DIR/repro-b.img"
MISSING_IMAGE="$TEST_DIR/missing-payload.img"
TRUNCATED_IMAGE="$TEST_DIR/truncated-payload.img"
CORRUPT_IMAGE="$TEST_DIR/corrupt-payload.img"
INVALID_ELF_IMAGE="$TEST_DIR/invalid-elf-segment.img"
VM_PID=

cleanup_vm() {
  if [ -n "$VM_PID" ]; then
    kill "$VM_PID" 2>/dev/null || true
    wait "$VM_PID" 2>/dev/null || true
    VM_PID=
  fi
}
trap cleanup_vm EXIT HUP INT TERM

run_failure_case() {
  case_name=$1
  case_image=$2
  expected_message=$3
  case_dir="$TEST_DIR/$case_name"
  runner_log="$case_dir/runner.log"
  uart_log="$case_dir/uart.log"

  mkdir -p "$case_dir"
  NATIVE_VM_BUILD_DIR="$case_dir" NATIVE_BOOT_MEDIA="$case_image" \
    NATIVE_STORAGE_MODE=ephemeral \
    "$REPO_DIR/vm/run-native-vm.sh" --headless --u-boot \
    >"$runner_log" 2>&1 &
  VM_PID=$!

  attempt=0
  until [ "$attempt" -ge 80 ]; do
    if [ -f "$uart_log" ] && grep -q "$expected_message" "$uart_log"; then
      break
    fi
    if ! kill -0 "$VM_PID" 2>/dev/null; then
      echo "$case_name VM exited before the expected recovery message:" >&2
      sed -n '1,200p' "$runner_log" >&2
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 0.25
  done
  if [ "$attempt" -ge 80 ]; then
    echo "$case_name did not report: $expected_message" >&2
    exit 1
  fi
  grep -q '=> ' "$uart_log"
  if grep -q 'Lefony OS: entering calculator runtime' "$uart_log"; then
    echo "$case_name unexpectedly started native Upsilon" >&2
    exit 1
  fi
  cleanup_vm
  echo "PASS: $case_name"
}

mkdir -p "$TEST_DIR"
NATIVE_BOOT_MEDIA="$BASE_IMAGE" "$REPO_DIR/vm/build-native-boot-media.sh" >/dev/null
NATIVE_BOOT_MEDIA="$SECOND_IMAGE" "$REPO_DIR/vm/build-native-boot-media.sh" >/dev/null
if ! cmp -s "$BASE_IMAGE" "$SECOND_IMAGE"; then
  echo "Native boot-media builds are not byte-for-byte reproducible" >&2
  exit 1
fi
echo "PASS: reproducible boot media"

cp "$BASE_IMAGE" "$MISSING_IMAGE"
cp "$BASE_IMAGE" "$TRUNCATED_IMAGE"
cp "$BASE_IMAGE" "$CORRUPT_IMAGE"
cp "$BASE_IMAGE" "$INVALID_ELF_IMAGE"

docker run --rm -e TEST_DIR_REL="$TEST_DIR_REL" \
  -v "$REPO_DIR:/work" -w /work \
  lefony-prime-g2-u-boot sh -ec '
    offset=1048576
    test_dir=$TEST_DIR_REL
    mdel -i "$test_dir/missing-payload.img@@$offset" ::/lefony-os.elf

    mcopy -o -i "$test_dir/truncated-payload.img@@$offset" \
      ::/lefony-os.elf "$test_dir/truncated.elf"
    truncate -s 1048576 "$test_dir/truncated.elf"
    mcopy -o -i "$test_dir/truncated-payload.img@@$offset" \
      "$test_dir/truncated.elf" ::/lefony-os.elf

    mcopy -o -i "$test_dir/corrupt-payload.img@@$offset" \
      ::/lefony-os.elf "$test_dir/corrupt.elf"
    printf "\001" | dd of="$test_dir/corrupt.elf" bs=1 seek=4096 \
      conv=notrunc status=none
    mcopy -o -i "$test_dir/corrupt-payload.img@@$offset" \
      "$test_dir/corrupt.elf" ::/lefony-os.elf

    mcopy -o -i "$test_dir/invalid-elf-segment.img@@$offset" \
      ::/lefony-os.elf "$test_dir/invalid-segment.elf"
    printf "\000\000\360\217" | dd of="$test_dir/invalid-segment.elf" \
      bs=1 seek=64 conv=notrunc status=none
    invalid_hash=$(sha256sum "$test_dir/invalid-segment.elf" | cut -d " " -f 1)
    invalid_size=$(wc -c <"$test_dir/invalid-segment.elf" | tr -d " ")
    printf "upsilon_size=%x\nupsilon_sha256=%s\n" \
      "$invalid_size" "$invalid_hash" >"$test_dir/invalid-segment.env"
    mcopy -o -i "$test_dir/invalid-elf-segment.img@@$offset" \
      "$test_dir/invalid-segment.elf" ::/lefony-os.elf
    mcopy -o -i "$test_dir/invalid-elf-segment.img@@$offset" \
      "$test_dir/invalid-segment.env" ::/upsilon.env
  '

run_failure_case missing "$MISSING_IMAGE" \
  'ERROR: lefony-os.elf missing or unreadable'
run_failure_case truncated "$TRUNCATED_IMAGE" \
  'ERROR: lefony-os.elf length mismatch'
run_failure_case corrupt "$CORRUPT_IMAGE" \
  'ERROR: lefony-os.elf checksum mismatch'
run_failure_case invalid-elf "$INVALID_ELF_IMAGE" \
  'ELF load segment outside native memory map'

echo "PASS: native boot-media recovery suite"
echo "Artifacts: $TEST_DIR"

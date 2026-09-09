#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LEFONY_NATIVE_PLATFORM=prime_g2_vm \
LEFONY_NATIVE_DIST_NAME=lefony-os-prime-g2-vm-native \
  exec "$SCRIPT_DIR/build_lefony_prime_g2.sh"

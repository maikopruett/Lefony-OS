#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VM_BUILD_DIR=${VM_BUILD_DIR:-"$REPO_DIR/build/prime-g2-vm"}
CONSOLE_SOCKET="$VM_BUILD_DIR/console.sock"

if [ ! -S "$CONSOLE_SOCKET" ]; then
  echo "Prime VM console is not available: $CONSOLE_SOCKET" >&2
  exit 1
fi

exec nc -U "$CONSOLE_SOCKET"

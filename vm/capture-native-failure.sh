#!/bin/sh
# Best-effort semantic and visual snapshot while a failing native VM is alive.
set -u

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ARTIFACT_DIR=$1
INPUT_SOCKET=$2
QMP_SOCKET=$3
FAILURE_DIR="$ARTIFACT_DIR/failure"
mkdir -p "$FAILURE_DIR"

if [ -S "$INPUT_SOCKET" ] || [ -L "$INPUT_SOCKET" ]; then
  for command in "INFO" "STATE" "MOD STATE" "EVENT LAST" \
      "DISPLAY GUARDS" "BRIGHTNESS GET" "BATTERY LEVEL" "POWER STATE" \
      "STACK SAFE"; do
    printf '%s: ' "$command" >>"$FAILURE_DIR/guest-state.log"
    python3 "$REPO_DIR/vm/prime-control.py" --socket "$INPUT_SOCKET" \
      raw "$command" >>"$FAILURE_DIR/guest-state.log" 2>&1 || true
  done
fi

if [ -S "$QMP_SOCKET" ] || [ -L "$QMP_SOCKET" ]; then
  python3 "$REPO_DIR/vm/qmp-screendump.py" "$QMP_SOCKET" \
    "$FAILURE_DIR/framebuffer.ppm" >"$FAILURE_DIR/qmp-capture.log" 2>&1 || true
fi

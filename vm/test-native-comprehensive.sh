#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$REPO_DIR/vm/native-suite.py" --suite "${1:-all}"

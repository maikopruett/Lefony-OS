#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$REPO_DIR/build/lefony-prime-g2"
IMAGE=lefony-upstream-tests
PATCH="$REPO_DIR/ports/lefony-prime-g2/patches/upstream-tests-linux-arm64.patch"

test -d "$SOURCE/.git"
if git -C "$SOURCE" apply --check "$PATCH" 2>/dev/null; then
  git -C "$SOURCE" apply "$PATCH"
fi
docker build \
  -f "$REPO_DIR/ports/lefony-prime-g2/Dockerfile.upstream-tests" \
  -t "$IMAGE" "$REPO_DIR/ports/lefony-prime-g2"
docker run --rm \
  -v "$REPO_DIR:/work" -w /work/build/lefony-prime-g2 \
  "$IMAGE" sh -ec '
    make PLATFORM=simulator clean
    make PLATFORM=simulator -j"${JOBS:-4}" test.bin
    ./output/release/simulator/linux/test.bin --headless
  '

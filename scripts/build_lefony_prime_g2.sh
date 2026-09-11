#!/bin/sh
set -eu

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PORT="$REPO/ports/lefony-prime-g2"
SOURCE="$REPO/build/lefony-prime-g2"
DIST="$REPO/dist"
NATIVE_PLATFORM=${LEFONY_NATIVE_PLATFORM:-prime_g2}
DIST_NAME=${LEFONY_NATIVE_DIST_NAME:-lefony-os-prime-g2-native}

case "$NATIVE_PLATFORM" in
  prime_g2|prime_g2_vm) ;;
  *)
    echo "Unsupported native platform: $NATIVE_PLATFORM" >&2
    exit 2
    ;;
esac

. "$PORT/UPSTREAM"

mkdir -p "$REPO/build" "$DIST"
if [ ! -d "$SOURCE/.git" ]; then
    git clone --filter=blob:none "$UPSILON_REPOSITORY" "$SOURCE"
fi

git -C "$SOURCE" fetch --depth 1 origin "$UPSILON_COMMIT"
git -C "$SOURCE" checkout --detach "$UPSILON_COMMIT"
git -C "$SOURCE" reset --hard "$UPSILON_COMMIT"
git -C "$SOURCE" clean -fdx
git -C "$SOURCE" submodule update --init --recursive
patch -d "$SOURCE" -p1 < "$PORT/patches/unaligned-storage.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/storage-rename-cache.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/physical-boot-progress.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/physical-event-progress.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-single-step-dpad.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/native-memory-telemetry.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/lefony-branding.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-dedicated-navigation.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-alpha-layout.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-keyboard-layout.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-shift-shortcuts.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-math-template-palette.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-template-insertion-redraw.patch"
patch -d "$SOURCE" -p1 < "$PORT/patches/prime-g2-power-status.patch"
LC_ALL=C perl -pi -e 's/AppsCapital = "UPSILON"/AppsCapital = "LEFONY"/' \
    "$SOURCE/apps/home/base.hu.i18n"

cp -R "$PORT/build/." "$SOURCE/build/"
if [ -d "$PORT/themes" ]; then
    cp -R "$PORT/themes/." "$SOURCE/themes/"
fi
mkdir -p "$SOURCE/ion/src/prime_g2"
cp -R "$PORT/ion/src/prime_g2/." "$SOURCE/ion/src/prime_g2/"
mkdir -p "$SOURCE/ion/src/prime_g2_vm"
cp -R "$PORT/ion/src/prime_g2_vm/." "$SOURCE/ion/src/prime_g2_vm/"
if [ -d "$PORT/apps" ]; then
    cp -R "$PORT/apps/." "$SOURCE/apps/"
fi
python3 "$REPO/scripts/prepare_prime_touch.py" "$SOURCE"
python3 "$REPO/scripts/prepare_prime_display.py" "$SOURCE"

if [ "$NATIVE_PLATFORM" = prime_g2 ]; then
    KEY_DIR=${LEFONY_UPDATE_KEY_DIR:-"$REPO/build/lefony-update-signing"}
    if [ -n "${LEFONY_UPDATE_PUBLIC_KEY:-}" ]; then
        RELEASE_PUBLIC_KEY=$LEFONY_UPDATE_PUBLIC_KEY
        test -s "$RELEASE_PUBLIC_KEY"
    else
        RELEASE_PRIVATE_KEY="$KEY_DIR/release-private.pem"
        RELEASE_PUBLIC_KEY="$KEY_DIR/release-public.pem"
        python3 "$REPO/scripts/prime_g2_update_key.py" ensure \
            "$RELEASE_PRIVATE_KEY" "$RELEASE_PUBLIC_KEY"
        echo "Local release signing key: $RELEASE_PRIVATE_KEY" >&2
    fi
    python3 "$REPO/scripts/prime_g2_update_key.py" header \
        "$RELEASE_PUBLIC_KEY" "$SOURCE/ion/src/prime_g2/update_trust_root.h"
fi

if [ -n "${LEFONY_APP_PUBLIC_KEYS:-}" ]; then
    python3 "$REPO/scripts/configure_native_app_keys.py" \
        "$LEFONY_APP_PUBLIC_KEYS" "$SOURCE/ion/src/prime_g2/app_trust_roots.h"
fi

python3 "$REPO/scripts/prepare_prime_settings.py" "$SOURCE"
python3 "$REPO/scripts/prepare_prime_brightness.py" "$SOURCE"

build_native() {
    make -C "$SOURCE" PLATFORM="$NATIVE_PLATFORM" clean
    make -C "$SOURCE" PLATFORM="$NATIVE_PLATFORM" -j"${JOBS:-4}" \
        epsilon.elf epsilon.u-boot.elf epsilon.bin
}

if command -v arm-none-eabi-g++ >/dev/null 2>&1; then
    build_native
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker build -f "$PORT/Dockerfile.baremetal" -t lefony-baremetal "$PORT"
    docker run --rm \
        -e NATIVE_PLATFORM="$NATIVE_PLATFORM" \
        -v "$REPO:/work" -w /work/build/lefony-prime-g2 \
        lefony-baremetal sh -ec '
          make PLATFORM="$NATIVE_PLATFORM" clean
          make PLATFORM="$NATIVE_PLATFORM" -j"${JOBS:-4}" \
            epsilon.elf epsilon.u-boot.elf epsilon.bin
        '
else
    echo "Need arm-none-eabi-g++ or a running Docker/Colima engine." >&2
    exit 1
fi

OUTPUT="$SOURCE/output/release/$NATIVE_PLATFORM"
test -s "$OUTPUT/epsilon.elf"
test -s "$OUTPUT/epsilon.u-boot.elf"
test -s "$OUTPUT/epsilon.bin"
cp "$OUTPUT/epsilon.u-boot.elf" "$DIST/$DIST_NAME.elf"
cp "$OUTPUT/epsilon.elf" "$DIST/$DIST_NAME-debug.elf"
cp "$OUTPUT/epsilon.bin" "$DIST/$DIST_NAME.bin"

python3 "$REPO/scripts/lefony_build_history.py" record \
    --artifact "$DIST/$DIST_NAME.bin" \
    --kind native \
    --notes "${LEFONY_BUILD_NOTES:-}" \
    --upstream-revision "$UPSILON_COMMIT"

if command -v arm-none-eabi-size >/dev/null 2>&1; then
    arm-none-eabi-size "$DIST/$DIST_NAME.elf"
fi

echo "$DIST/$DIST_NAME.elf"

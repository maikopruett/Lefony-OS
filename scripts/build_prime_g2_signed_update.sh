#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=${1:?usage: build_prime_g2_signed_update.sh VERSION [zImage] [output.lfu]}
PAYLOAD=${2:-"$REPO_DIR/build/lefony-os-native-nand/lefony-os-native.zImage"}
OUTPUT=${3:-"$REPO_DIR/build/lefony-os-native-nand/lefony-os-native.lfu"}
KEY_DIR=${LEFONY_UPDATE_KEY_DIR:-"$REPO_DIR/build/lefony-update-signing"}
PRIVATE_KEY=${LEFONY_UPDATE_PRIVATE_KEY:-"$KEY_DIR/release-private.pem"}
PUBLIC_KEY=${LEFONY_UPDATE_PUBLIC_KEY:-"$KEY_DIR/release-public.pem"}

if [ ! -s "$PRIVATE_KEY" ] || [ ! -s "$PUBLIC_KEY" ]; then
  if [ -n "${LEFONY_UPDATE_PRIVATE_KEY:-}" ] || [ -n "${LEFONY_UPDATE_PUBLIC_KEY:-}" ]; then
    echo "Both configured release key files must already exist." >&2
    exit 2
  fi
  python3 "$REPO_DIR/scripts/prime_g2_update_key.py" ensure \
    "$PRIVATE_KEY" "$PUBLIC_KEY"
fi

python3 "$REPO_DIR/scripts/prime_g2_update_capsule.py" create \
  "$PAYLOAD" "$OUTPUT" --version "$VERSION" --private-key "$PRIVATE_KEY"
python3 "$REPO_DIR/scripts/prime_g2_update_capsule.py" inspect \
  "$OUTPUT" --public-key "$PUBLIC_KEY"
python3 "$REPO_DIR/scripts/lefony_build_history.py" record \
  --artifact "$OUTPUT" \
  --kind signed-update \
  --version "$VERSION" \
  --notes "${LEFONY_BUILD_NOTES:-}"

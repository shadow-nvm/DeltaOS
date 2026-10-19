#!/usr/bin/env bash
# Build the DeltaOS ISO inside WSL2 (Ubuntu or Debian) without Docker.
#
#   wsl bash /mnt/c/path/to/DeltaOS/build/wsl-build.sh core
#
# WSL2 exposes the Windows drive as /mnt/c, and that filesystem cannot hold the
# ownership and device nodes a Debian chroot needs, so debootstrap fails there.
# This helper copies the sources onto the Linux filesystem, builds there, and
# copies the finished ISO back to build/output/ in the Windows checkout.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$SELF_DIR/.." && pwd)"
PROFILE="${1:-core}"
case "$PROFILE" in
    core|full) ;;
    *) echo "profile must be 'core' or 'full'" >&2; exit 2 ;;
esac
if (($#)); then shift; fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "==> DeltaOS needs root for debootstrap, chroot mounts and apt"
    exec sudo -E bash "$SELF_DIR/wsl-build.sh" "$PROFILE" "$@"
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: this helper expects a Debian or Ubuntu WSL distribution." >&2
    echo "       From Windows run: wsl --install -d Debian" >&2
    exit 1
fi

DEPS="live-build debootstrap debian-archive-keyring squashfs-tools xorriso
      mtools dosfstools cpio rsync zstd xz-utils python3 python3-pil
      grub-common grub-pc-bin grub-efi-amd64-bin fonts-dejavu-core
      ca-certificates curl"

missing=""
for package in $DEPS; do
    if ! dpkg-query -W -f='${db:Status-Abbrev}' "$package" 2>/dev/null | grep -q '^ii'; then
        missing="$missing $package"
    fi
done
if [[ -n "$missing" ]]; then
    echo "==> installing build dependencies:$missing"
    apt-get update -y
    apt-get install -y --no-install-recommends $missing
fi

BUILD_ROOT="${DELTAOS_WSL_DIR:-$HOME/deltaos-build}"
mkdir -p "$BUILD_ROOT"

echo "==> syncing sources to $BUILD_ROOT (Linux filesystem)"
rsync -a --delete \
    --exclude 'build/work' \
    --exclude 'build/output' \
    --exclude '.cache' \
    --exclude '.git' \
    --exclude '__pycache__' \
    "$SRC/" "$BUILD_ROOT/"

echo "==> building the $PROFILE image"
cd "$BUILD_ROOT"
bash ./build/build-iso.sh "$PROFILE" "$@"

echo "==> copying the ISO back to the Windows checkout"
mkdir -p "$SRC/build/output"
cp -f "$BUILD_ROOT"/build/output/*.iso "$SRC/build/output/"
cp -f "$BUILD_ROOT"/build/output/*.sha256 "$SRC/build/output/" 2>/dev/null || true
chmod 0644 "$SRC/build/output"/*.iso "$SRC/build/output"/*.sha256 2>/dev/null || true
[[ -n "${SUDO_UID:-}" ]] && chown -R "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$BUILD_ROOT" 2>/dev/null || true

ls -lh "$SRC/build/output"
if command -v wslpath >/dev/null 2>&1; then
    echo "==> ISO folder on Windows: $(wslpath -w "$SRC/build/output")"
fi

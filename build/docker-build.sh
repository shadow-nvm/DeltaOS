#!/usr/bin/env bash
# Build the DeltaOS ISO inside Docker/Podman so no host packages are needed.
# Works on Windows (Docker Desktop / Podman), macOS and Linux.
#
#   bash ./build/docker-build.sh [core|full] [--refresh-packages] [--clean]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-core}"; shift || true

if command -v docker >/dev/null 2>&1; then
    ENGINE=docker
elif command -v podman >/dev/null 2>&1; then
    ENGINE=podman
else
    echo "ERROR: neither docker nor podman found." >&2
    echo "Install Docker Desktop, or build natively: sudo bash ./build/build-iso.sh $PROFILE" >&2
    exit 1
fi

echo "==> building builder image with $ENGINE"
"$ENGINE" build -t deltaos-builder "$REPO/build" >/dev/null

echo "==> building DeltaOS ISO in a container (profile: $PROFILE)"
# --privileged: live-build needs loop devices and mount(2) for the chroot.
# build/work is a Docker volume rather than a bind mount: on Windows and macOS
# the host filesystem cannot carry the device nodes and permissions debootstrap
# creates. Only the finished ISO is written back to the bind-mounted repo.
"$ENGINE" volume create deltaos-build-work >/dev/null
"$ENGINE" run --rm --privileged \
    -v "$REPO:/work" \
    -v deltaos-build-work:/work/build/work \
    -w /work \
    deltaos-builder \
    bash ./build/build-iso.sh "$PROFILE" "$@"

echo "==> done; see build/output/"
ls -lh "$REPO/build/output" 2>/dev/null || true
echo "note: the reusable build tree lives in the docker volume 'deltaos-build-work';"
echo "      pass --clean to start it from scratch."

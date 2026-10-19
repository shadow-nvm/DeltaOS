#!/usr/bin/env bash
# Check a Linux build machine before starting a long DeltaOS build.
#
#   bash build/preflight.sh [build-directory]
#
# Every check prints PASS, WARN or FAIL. WARN items are optional (the GRUB
# theme is skipped without fonts, for example). FAIL items stop the ISO build
# in `lb chroot` or, worse, at the very end in `lb binary`, so fixing them first
# saves an hour. Exit status is 0 when nothing failed.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$REPO/build/work}"
FAILED=0
WARNED=0

pass() { printf '\033[1;32mPASS\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN\033[0m %s\n' "$*"; WARNED=$((WARNED + 1)); }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*"; FAILED=$((FAILED + 1)); }
info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

info "DeltaOS build preflight"

# --- operating system ------------------------------------------------------
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    pass "host is ${PRETTY_NAME:-unknown Linux}"
    case " ${ID:-} ${ID_LIKE:-} " in
        *" debian "*|*" ubuntu "*) ;;
        *) warn "live-build is tested on Debian and Ubuntu; ${ID:-this distribution} may work but is unsupported" ;;
    esac
else
    fail "no /etc/os-release: this does not look like a Linux host"
fi

if [ "$(id -u)" -eq 0 ]; then
    pass "running as root"
elif command -v sudo >/dev/null 2>&1; then
    pass "not root; build-iso.sh will need sudo (sudo is available)"
else
    fail "not root and sudo is missing: run the build as root"
fi

# --- programs --------------------------------------------------------------
info "checking host tools"
check_command() { # <command> <package> <required|optional>
    if command -v "$1" >/dev/null 2>&1; then
        pass "$1 found"
    elif [ "$3" = "optional" ]; then
        warn "$1 missing (package: $2); the related feature is skipped"
    else
        fail "$1 missing: sudo apt install $2"
    fi
}

for entry in \
    "lb:live-build" \
    "debootstrap:debootstrap" \
    "xorriso:xorriso" \
    "mksquashfs:squashfs-tools" \
    "mcopy:mtools" \
    "mkfs.fat:dosfstools" \
    "cpio:cpio" \
    "rsync:rsync" \
    "python3:python3" \
    "grub-mkimage:grub-common"
do
    check_command "${entry%%:*}" "${entry#*:}" required
done

for entry in "grub-mkfont:grub-common"; do
    check_command "${entry%%:*}" "${entry#*:}" optional
done

# Files the binary stage reads from the host, not from the chroot.
for file in /usr/lib/grub/i386-pc/boot_hybrid.img; do
    if [ -e "$file" ]; then
        pass "$file present"
    else
        fail "$file missing: sudo apt install grub-pc-bin (the hybrid ISO needs it)"
    fi
done
if [ -e /usr/lib/shim/shimx64.efi.signed ] || [ -e /usr/lib/grub/x86_64-efi ]; then
    pass "EFI GRUB modules present"
else
    warn "grub-efi-amd64-bin is missing; the EFI part of the ISO may fail"
fi

if python3 -c 'import PIL' >/dev/null 2>&1; then
    pass "Python Pillow available (artwork generation)"
else
    fail "Python Pillow missing: sudo apt install python3-pil"
fi

if command -v grub-mkfont >/dev/null 2>&1 && \
   ls /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf >/dev/null 2>&1; then
    pass "fonts available for the GRUB theme"
elif command -v grub-mkfont >/dev/null 2>&1; then
    warn "no DejaVu/Liberation fonts: install fonts-dejavu-core for the GRUB theme"
else
    warn "grub-mkfont missing: the GRUB menu keeps its stock look"
fi

# --- resources -------------------------------------------------------------
info "checking resources"
mkdir -p "$WORK" 2>/dev/null || true
if df -Pk "$WORK" >/dev/null 2>&1; then
    FREE_GB=$(( $(df -Pk "$WORK" | awk 'NR==2 {print $4}') / 1024 / 1024 ))
    if [ "$FREE_GB" -ge 20 ]; then
        pass "$FREE_GB GB free for the build tree"
    elif [ "$FREE_GB" -ge 12 ]; then
        warn "only $FREE_GB GB free: a full build wants about 20 GB"
    else
        fail "only $FREE_GB GB free: the build needs at least 12 GB"
    fi
else
    warn "could not read free space for $WORK"
fi

MEM_MB=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$MEM_MB" -ge 3500 ]; then
    pass "${MEM_MB} MB RAM"
elif [ "$MEM_MB" -ge 1800 ]; then
    warn "${MEM_MB} MB RAM: the build works but swapping makes it slow"
else
    fail "${MEM_MB} MB RAM: live-build needs at least 2 GB"
fi

# --- network ---------------------------------------------------------------
info "checking the package mirror"
if command -v curl >/dev/null 2>&1; then
    if curl -fsSL --max-time 15 -o /dev/null https://deb.debian.org/debian/dists/trixie/Release; then
        pass "deb.debian.org reachable"
    else
        fail "cannot reach https://deb.debian.org: check the network or proxy settings"
    fi
else
    warn "curl missing: cannot test the mirror before the build"
fi

# --- summary ---------------------------------------------------------------
echo
if [ "$FAILED" -eq 0 ]; then
    printf '\033[1;32mPreflight passed\033[0m (%d warning(s)).\n' "$WARNED"
    echo "Next: sudo bash ./build/build-iso.sh core --clean"
    exit 0
fi
printf '\033[1;31mPreflight found %d problem(s) and %d warning(s).\033[0m\n' "$FAILED" "$WARNED"
echo "Fix the FAIL lines above before starting the build."
exit 1

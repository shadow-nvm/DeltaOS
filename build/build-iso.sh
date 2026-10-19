#!/usr/bin/env bash
# Build a bootable DeltaOS live ISO with Debian live-build.
#
#   sudo bash ./build/build-iso.sh [core|full] [--refresh-packages] [--clean]
#
# The core image includes the desktop, everyday tools, gaming support and
# DeltaHub. The full profile adds the optional research and creative stack.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-core}"
case "$PROFILE" in
    core|full) ;;
    *) echo "profile must be 'core' or 'full'" >&2; exit 2 ;;
esac
if (($#)); then shift; fi

REFRESH=0
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --refresh-packages) REFRESH=1 ;;
        --clean) CLEAN=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

VERSION="$(tr -d '\357\273\277 \r\n\t' < "$REPO/VERSION")"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]] || {
    echo "ERROR: VERSION must contain a version such as 0.1.0" >&2
    exit 2
}

WORK="$REPO/build/work"
OUT="$REPO/build/output"
IMAGE="deltaos-${VERSION}"
PKGCHECK="$REPO/tools/pkgcheck.py"

log() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || die "live-build needs root for chroot setup; use sudo on Linux."
for tool in lb debootstrap python3 mksquashfs xorriso; do
    command -v "$tool" >/dev/null 2>&1 || die "missing $tool (install live-build debootstrap squashfs-tools xorriso python3-pil)"
done
python3 -c 'import PIL' 2>/dev/null || \
    die "Python Pillow is missing; the DeltaOS artwork cannot be generated (install python3-pil)"

if [[ "$CLEAN" -eq 1 ]]; then
    log "cleaning the previous build tree"
    mkdir -p "$WORK"
    find "$WORK" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
fi
mkdir -p "$WORK" "$OUT"
cd "$WORK"

# A build that runs out of disk space fails after an hour, in the binary stage,
# with an error that does not mention disk space at all. Check it up front.
FREE_GB="$(df -Pk "$WORK" | awk 'NR==2 { print int($4 / 1024 / 1024) }')"
if [[ "${FREE_GB:-0}" -lt 12 ]]; then
    die "only ${FREE_GB:-0} GB free under $WORK; a full build needs at least 12 GB (20 GB recommended)"
elif [[ "${FREE_GB:-0}" -lt 20 ]]; then
    log "warning: only ${FREE_GB} GB free; 20 GB is recommended"
fi

# "persistence" tells live-boot to look for a disk volume labelled
# "persistence" holding a persistence.conf file (see deltaos-persistence).
# Without such a volume the session stays read-only, exactly as before.
log "configuring the Debian 13 live image ($PROFILE profile)"
lb config \
    --distribution trixie \
    --architecture amd64 \
    --binary-image iso-hybrid \
    --archive-areas "main contrib non-free non-free-firmware" \
    --apt-recommends false \
    --backports true \
    --bootloaders "grub-efi,grub-pc" \
    --uefi-secure-boot auto \
    --debian-installer none \
    --memtest none \
    --iso-application "DeltaOS" \
    --iso-preparer "DeltaOS Project" \
    --iso-publisher "DeltaOS Project" \
    --iso-volume "DELTAOS" \
    --image-name "$IMAGE" \
    --bootappend-live "boot=live components quiet splash persistence hostname=deltaos username=live locales=en_US.UTF-8 keyboard-layouts=us" \
    --bootappend-live-failsafe "boot=live components memtest noapic noapm nodma nomce nolapic nomodeset nosmp nosplash vga=normal" \
    --linux-flavours amd64 \
    --apt-options "--yes --option Acquire::Retries=5" \
    >/dev/null

log "merging the DeltaOS configuration"
cp -a "$REPO/config/." "$WORK/config/"

mkdir -p "$WORK/config/includes.chroot/usr/share/deltaos"
printf 'VERSION=%s\nPROFILE=%s\n' "$VERSION" "$PROFILE" \
    > "$WORK/config/includes.chroot/usr/share/deltaos/release"

BRANDING="$WORK/config/includes.chroot/usr/share/deltaos/calamares-branding/branding.desc"
sed -i \
    -e "s/^    version: .*/    version: ${VERSION}/" \
    -e "s/^    shortVersion: .*/    shortVersion: ${VERSION}/" \
    -e "s/^    versionedName: .*/    versionedName: DeltaOS ${VERSION} Aurora/" \
    -e "s/^    shortVersionedName: .*/    shortVersionedName: DeltaOS ${VERSION}/" \
    "$BRANDING"

# Windows checkouts may not retain Unix execute bits. live-build runs hook
# scripts and DeltaHub only when they are executable, so set them explicitly
# instead of trusting whatever the checkout carried over.
find "$WORK/config/hooks" -type f -name '*.hook.chroot' -exec chmod 0755 {} +
find "$WORK/config/includes.chroot/usr/bin" -type f -exec chmod 0755 {} + 2>/dev/null || true
[[ -f "$WORK/config/includes.chroot/usr/bin/deltahub" ]] || \
    die "config/includes.chroot/usr/bin/deltahub is missing"

log "checking package names against Debian 13"
PKGCHECK_ARGS=(--emit "$WORK/config/package-lists")
[[ "$REFRESH" -eq 1 ]] && PKGCHECK_ARGS+=(--refresh)
python3 "$PKGCHECK" "${PKGCHECK_ARGS[@]}" || die "package lists reference unavailable required packages"

if [[ "$PROFILE" == "core" ]]; then
    # Keep the standard image useful for study and daily work while leaving
    # the large creative and scientific applications for the full profile.
    for list in 20-apps 50-research; do
        awk '!/^(libreoffice-impress|libreoffice-kf6|thunderbird|gimp|inkscape|audacity|obs-studio|telegram-desktop|qbittorrent|keepassxc|handbrake|celluloid|gnome-disk-utility|simple-scan|cheese|gnome-calculator|python3-scipy|python3-matplotlib|python3-pandas|python3-sympy|jupyter-notebook|jupyter-console|r-base|gnuplot|octave|texlive-.*|texstudio|jabref|anki|kalgebra|kgeography|kstars|stellarium|geogebra|musescore3|blender)([[:space:]]|$)/' \
            "$WORK/config/package-lists/${list}.list.chroot" > "$WORK/config/.tmp"
        mv "$WORK/config/.tmp" "$WORK/config/package-lists/${list}.list.chroot"
    done
fi

# The chroot hook reads the backports selection at this fixed path. Stage it
# explicitly instead of depending on live-build's internal package-list copy.
mkdir -p "$WORK/config/includes.chroot/usr/share/live/build/package-lists"
cp "$WORK/config/package-lists/backports-packages.txt" \
    "$WORK/config/includes.chroot/usr/share/live/build/package-lists/backports-packages.txt"

log "generating the DeltaOS artwork"
python3 "$REPO/tools/make_assets.py" \
    --out "$WORK/config/includes.chroot" \
    --binary "$WORK/config/includes.binary"

log "staging the optional GRUB theme"
bash "$REPO/build/apply-grub-theme.sh" "$WORK"

# live-build's binary stage checks for xorriso, isolinux, dctrl-tools and
# librsvg2-bin inside the chroot. They are listed in packages/00-base.list so
# the stage never needs a late network install; apt indices are kept as well
# (see config/hooks/live/10-deltaos-backports.hook.chroot).
log "building the ISO; allow about 20 GB of free disk space"
lb build 2>&1 | tee "$WORK/build.log"

ISO_BUILT="$(find "$WORK" -maxdepth 1 -type f -name "${IMAGE}-amd64*.iso" -print -quit)"
[[ -n "$ISO_BUILT" ]] || die "ISO not produced; check $WORK/build.log"

mv -f "$ISO_BUILT" "$OUT/${IMAGE}-amd64.iso"
SIZE="$(du -h "$OUT/${IMAGE}-amd64.iso" | cut -f1)"
sha256sum "$OUT/${IMAGE}-amd64.iso" > "$OUT/${IMAGE}-amd64.iso.sha256"
log "ISO ready: $OUT/${IMAGE}-amd64.iso ($SIZE)"
log "SHA-256: $(cut -d' ' -f1 "$OUT/${IMAGE}-amd64.iso.sha256")"

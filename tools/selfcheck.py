#!/usr/bin/env python3
"""Offline consistency checks for the DeltaOS source tree.

    python3 tools/selfcheck.py

Nothing is built or downloaded. This catches the mistakes that otherwise only
appear late in a live-build run: unparseable YAML, branding files Calamares
refuses to load, artwork a theme references but nobody generates, package list
typos, desktop entries pointing at missing programs, shell scripts with syntax
errors, and the package-list entries live-build's binary stage checks for.

It runs in about a second on any OS. A shell (bash or sh) is used for
`bash -n` syntax checks when one is available; otherwise that check is skipped
with a note instead of failing.
"""

from __future__ import annotations

import configparser
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
INCLUDES = CONFIG / "includes.chroot"
BRANDING = INCLUDES / "usr/share/deltaos/calamares-branding"
PLYMOUTH = INCLUDES / "usr/share/plymouth/themes/deltaos"
GRUB_THEME = CONFIG / "includes.binary/boot/grub/themes/deltaos"
ARTWORK = INCLUDES / "usr/share/deltaos/artwork"
HOOKS = CONFIG / "hooks/live"

errors: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    notes.append(message)


def read_list(path: Path) -> dict[str, str]:
    """Package name -> original kind marker (required/optional/backports)."""
    entries: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        kind = "required"
        if line[0] in "?!^":
            kind = {"?": "optional", "!": "forbidden", "^": "backports"}[line[0]]
            line = line[1:].strip()
        if line:
            entries[line] = kind
    return entries


def all_packages() -> dict[str, tuple[str, str]]:
    """package -> (kind, list file name) across every list."""
    merged: dict[str, tuple[str, str]] = {}
    for path in sorted((ROOT / "packages").glob("*.list")):
        for name, kind in read_list(path).items():
            merged.setdefault(name, (kind, path.name))
    return merged


def check_yaml() -> None:
    try:
        import yaml
    except ImportError:
        fail("PyYAML is not installed (python3-yaml); cannot validate Calamares config")
        return

    files = sorted(CONFIG.rglob("*.conf")) + sorted(CONFIG.rglob("*.desc"))
    for path in files:
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - report, never crash
            fail(f"YAML does not parse: {path.relative_to(ROOT)}: {exc}")
    ok(f"parsed {len(files)} YAML files")


def check_branding() -> None:
    try:
        import yaml
    except ImportError:
        return
    desc_path = BRANDING / "branding.desc"
    if not desc_path.is_file():
        fail("calamares branding.desc is missing")
        return
    desc = yaml.safe_load(desc_path.read_text(encoding="utf-8")) or {}

    # Calamares requires these groups; a missing one aborts the installer.
    for key in ("componentName", "strings", "images", "style"):
        if key not in desc:
            fail(f"branding.desc lacks the required '{key}' section")
    strings = desc.get("strings") or {}
    for key in ("productName", "version", "shortVersion", "versionedName",
                "bootloaderEntryName"):
        if not strings.get(key):
            fail(f"branding.desc strings.{key} is missing")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip().lstrip("\ufeff")
    if strings.get("version") != version:
        fail(f"branding.desc version {strings.get('version')!r} does not match "
             f"VERSION {version!r}")

    # Only these style keys are recognised; others are logged as errors.
    allowed_style = {"SidebarBackground", "SidebarBackgroundCurrent",
                     "SidebarText", "SidebarTextCurrent"}
    for key in (desc.get("style") or {}):
        if key not in allowed_style:
            fail(f"branding.desc style.{key} is not a Calamares style key")

    for key, value in (desc.get("images") or {}).items():
        if not isinstance(value, str):
            continue
        if not (BRANDING / value).is_file():
            fail(f"branding image '{value}' ({key}) does not exist")

    slideshow = desc.get("slideshow")
    if not slideshow:
        fail("branding.desc has no slideshow entry")
    else:
        qml = BRANDING / str(slideshow)
        if not qml.is_file():
            fail(f"branding slideshow '{slideshow}' does not exist")
        else:
            for source in re.findall(r'source:\s*"([^"]+)"', qml.read_text(encoding="utf-8")):
                if ":" in source or source.startswith("/"):
                    continue
                if not (BRANDING / source).is_file():
                    fail(f"slideshow references missing image '{source}'")
    if "slideshowAPI" not in desc:
        fail("branding.desc is missing slideshowAPI")
    ok("calamares branding is structurally complete")


def check_calamares_wiring() -> None:
    settings = INCLUDES / "etc/calamares/settings.conf"
    if not settings.is_file():
        fail("calamares settings.conf is missing")
        return
    text = settings.read_text(encoding="utf-8")
    match = re.search(r"^branding:\s*(\S+)", text, re.MULTILINE)
    if not match:
        fail("settings.conf does not name a branding component")
    hook = HOOKS / "30-deltaos-services.hook.chroot"
    if hook.is_file():
        hook_text = hook.read_text(encoding="utf-8")
        if "calamares-branding" not in hook_text:
            fail("30-deltaos-services does not install the calamares branding")
        if "deltaos-install.desktop" not in hook_text:
            fail("30-deltaos-services does not stage the installer menu entry")
    else:
        fail("30-deltaos-services.hook.chroot is missing")

    entry = INCLUDES / "usr/share/deltaos/deltaos-install.desktop"
    if not entry.is_file():
        fail("usr/share/deltaos/deltaos-install.desktop is missing")
    else:
        body = entry.read_text(encoding="utf-8")
        match = re.search(r"^Exec=(/usr/bin/\S+)", body, re.MULTILINE)
        if not match:
            fail("deltaos-install.desktop has no absolute Exec line")
        elif not (INCLUDES / match.group(1).lstrip("/")).is_file():
            fail(f"deltaos-install.desktop Exec points at missing file {match.group(1)}")
    ok("calamares settings, branding and installer entry are wired together")


def check_desktop_entries() -> None:
    count = 0
    for path in sorted(INCLUDES.rglob("*.desktop")):
        count += 1
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str  # keep keys like X-GNOME-Autostart-enabled
        try:
            parser.read_string(path.read_text(encoding="utf-8"))
        except configparser.Error as exc:
            fail(f"{path.relative_to(INCLUDES)} is not a valid desktop entry: {exc}")
            continue
        if not parser.has_section("Desktop Entry"):
            fail(f"{path.relative_to(INCLUDES)} has no [Desktop Entry] section")
            continue
        section = parser["Desktop Entry"]
        for key in ("Type", "Name"):
            if not section.get(key):
                fail(f"{path.relative_to(INCLUDES)} lacks {key}=")
        executable = (section.get("Exec") or "").split()
        if executable and executable[0].startswith("/usr/"):
            if not (INCLUDES / executable[0].lstrip("/")).is_file():
                fail(f"{path.relative_to(INCLUDES)} runs {executable[0]}, "
                     f"which is not shipped in the image")
    ok(f"checked {count} desktop entries")


def find_shell() -> str | None:
    """A working POSIX shell, or None.

    On Windows, `bash` on PATH is usually the WSL stub in WindowsApps: it
    exists but prints "no installed distributions" and exits non-zero. Every
    candidate is therefore verified with a smoke test before it is trusted.
    """
    candidates = [shutil.which("bash"), shutil.which("sh"),
                  r"C:\Program Files\Git\bin\bash.exe",
                  r"C:\Program Files\Git\usr\bin\bash.exe"]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run([candidate, "-c", "echo deltaos-shell"],
                                    capture_output=True, text=True,
                                    timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and "deltaos-shell" in result.stdout:
            return candidate
    return None


def check_scripts() -> None:
    for script in sorted((INCLUDES / "usr/bin").iterdir()):
        if not script.is_file():
            continue
        text = script.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("#!"):
            fail(f"usr/bin/{script.name} has no shebang")
            continue
        if "python" in text.splitlines()[0]:
            try:
                compile(text, str(script), "exec")
            except SyntaxError as exc:
                fail(f"usr/bin/{script.name} does not compile: {exc}")

    shell = find_shell()
    shell_targets = sorted(HOOKS.glob("*.hook.chroot")) + \
        sorted((ROOT / "build").glob("*.sh")) + \
        [INCLUDES / "usr/bin/deltaos-install", INCLUDES / "usr/bin/deltaos-layout"]
    for target in shell_targets:
        if not target.is_file():
            fail(f"missing script {target.relative_to(ROOT)}")
            continue
        body = target.read_text(encoding="utf-8", errors="replace")
        if not body.startswith("#!"):
            fail(f"{target.relative_to(ROOT)} has no shebang")
            continue
        if body.startswith("#!/bin/sh") and "set -u" not in body and "set -eu" not in body:
            pass  # style only, not an error
        if shell:
            # Git Bash wants forward slashes for a Windows path.
            result = subprocess.run([shell, "-n", str(target).replace("\\", "/")],
                                    capture_output=True, text=True, check=False)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().splitlines()
                fail(f"{target.relative_to(ROOT)} has a shell syntax error: "
                     f"{detail[-1] if detail else 'unknown'}")
    if shell:
        ok(f"shell syntax checked with {Path(shell).name} ({len(shell_targets)} scripts)")
    else:
        ok("no bash/sh available; shell syntax check skipped")


def check_plymouth() -> None:
    theme = PLYMOUTH / "deltaos.plymouth"
    script = PLYMOUTH / "deltaos.script"
    if not theme.is_file() or not script.is_file():
        fail("plymouth theme files are missing")
        return
    text = theme.read_text(encoding="utf-8")
    if "ModuleName=script" not in text:
        fail("plymouth theme must use ModuleName=script")
    for line in text.splitlines():
        if line.startswith("ScriptFile="):
            referenced = line.split("=", 1)[1].strip()
            if not referenced.startswith("/usr/share/plymouth/themes/deltaos/"):
                fail(f"plymouth ScriptFile points outside the theme: {referenced}")
    body = script.read_text(encoding="utf-8")
    for image in re.findall(r'Image\("([^"]+)"\)', body):
        if not (PLYMOUTH / image).is_file():
            fail(f"plymouth art '{image}' referenced by deltaos.script is missing")
    ok("plymouth theme references only existing assets")


def check_grub_theme() -> None:
    theme_txt = GRUB_THEME / "theme.txt"
    if not theme_txt.is_file():
        fail("GRUB theme.txt is missing")
        return
    text = theme_txt.read_text(encoding="utf-8")
    for image in re.findall(r'"([A-Za-z0-9_.-]+\.png)"', text):
        if "*" in image:
            continue
        if not (GRUB_THEME / image).is_file():
            fail(f"GRUB theme references missing image '{image}'")
    styles = re.findall(r'selected_item_pixmap_style\s*=\s*"([^"]+)"', text)
    for style in styles:
        # "highlight_*.png" -> prefix "highlight_"
        prefix = style.split("*")[0]
        if not any(p.name.startswith(prefix) for p in GRUB_THEME.glob("*.png")):
            fail(f"GRUB pixmap style '{style}' has no matching images")
    ok("GRUB theme references only existing assets")


def check_artwork() -> None:
    for name in ("wallpaper-aurora.jpg", "wallpaper-dark.jpg", "logo-128.png",
                 "deltaos.svg", "grub-background.png"):
        if not (ARTWORK / name).is_file():
            fail(f"artwork '{name}' is missing (run tools/make_assets.py)")
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon = INCLUDES / f"usr/share/icons/hicolor/{size}x{size}/apps/deltaos.png"
        if not icon.is_file():
            fail(f"application icon {size}x{size} is missing")
    ok("artwork and icon set are present")


def check_packages() -> None:
    pattern = re.compile(r"^[a-z0-9][a-z0-9+.-]*(:[a-z0-9]+)?$")
    seen: dict[str, str] = {}
    total = 0
    for path in sorted((ROOT / "packages").glob("*.list")):
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            total += 1
            name = line.lstrip("?!^")
            if not pattern.match(name):
                fail(f"{path.name}:{number}: invalid package name '{name}'")
            if name in seen:
                fail(f"{path.name}:{number}: '{name}' already listed in {seen[name]}")
            else:
                seen[name] = path.name
    ok(f"validated {total} package entries across the lists")


def check_binary_stage_packages() -> None:
    """live-build's binary stage checks these inside the chroot.

    If any is missing, live-build tries to apt-install it after the chroot work
    is finished -- a late network step that fails whenever the apt lists are
    gone. Keeping them listed makes the build deterministic.
    """
    required = all_packages()
    base_needed = ("xorriso", "isolinux", "dctrl-tools", "librsvg2-bin",
                   "grub-common", "grub-pc-bin", "grub-efi-amd64-bin",
                   "squashfs-tools")
    desktop_needed = ("sddm-theme-breeze", "xserver-xorg", "xserver-xorg-input-libinput",
                      "polkit-kde-agent-1", "pkexec", "plasma-desktop", "sddm")
    for name in base_needed + desktop_needed:
        if name not in required:
            fail(f"{name} is required for a working image/binary stage but is "
                 f"not in packages/*.list")
        elif required[name][0] != "required":
            fail(f"{name} must be a required entry, not '{required[name][0]}' "
                 f"({required[name][1]})")
    ok("binary-stage and desktop essentials are listed as required packages")


def check_persistence() -> None:
    script = INCLUDES / "usr/bin/deltaos-persistence"
    if not script.is_file():
        fail("live persistence helper is missing: "
             "config/includes.chroot/usr/bin/deltaos-persistence")
        return
    source = script.read_text(encoding="utf-8")
    if not source.startswith("#!"):
        fail("deltaos-persistence has no shebang")
    try:
        compile(source, str(script), "exec")
    except SyntaxError as exc:
        fail(f"deltaos-persistence does not compile: {exc}")
        return
    if "/ union" not in source:
        fail("deltaos-persistence does not write the '/ union' persistence.conf entry")

    build = (ROOT / "build/build-iso.sh").read_text(encoding="utf-8")
    match = re.search(r'--bootappend-live "([^"]*)"', build)
    if not match:
        fail("build/build-iso.sh has no --bootappend-live line")
    else:
        tokens = match.group(1).split()
        if "boot=live" not in tokens:
            fail("the live boot line lacks boot=live, so live-boot never activates")
        if "persistence" not in tokens:
            fail("the live boot line does not request persistence")
        if "nopersistence" in tokens:
            fail("the live boot line disables persistence with nopersistence")

    base = (ROOT / "packages/00-base.list").read_text().splitlines()
    present = {line.split("#", 1)[0].strip().lstrip("?!^") for line in base}
    for package in ("python3", "e2fsprogs"):
        if package not in present:
            fail(f"{package} is required by deltaos-persistence but not in 00-base.list")
    ok("live persistence helper and boot parameter are consistent")


def check_line_endings() -> None:
    """Windows line endings and BOMs break shell shebangs and YAML on Linux.

    The repository is often edited on Windows, so this is checked explicitly
    instead of being discovered by a failing build an hour later.
    """
    suffixes = {".sh", ".chroot", ".py", ".list", ".conf", ".desc", ".qml",
                ".plymouth", ".desktop", ".txt", ".md"}
    skipped = {".git", ".cache", ".freebuff", "work", "output", "__pycache__"}
    checked = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in skipped for part in relative.parts):
            continue
        data = path.read_bytes()
        text_file = path.suffix.lower() in suffixes or data.startswith(b"#!")
        if not text_file:
            continue
        checked += 1
        if data.startswith(b"\xef\xbb\xbf"):
            fail(f"{relative} starts with a UTF-8 BOM; Linux tools will misread it")
        elif b"\r\n" in data:
            fail(f"{relative} uses Windows CRLF line endings; "
                 f"shell scripts and YAML will break on Linux")
    ok(f"line endings checked in {checked} text files")


def check_build_inputs() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip().lstrip("\ufeff")
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", version):
        fail(f"VERSION is not a semantic version: {version!r}")
    for script in ("build/build-iso.sh", "build/wsl-build.sh",
                   "build/apply-grub-theme.sh", "build/build-windows.ps1",
                   "build/docker-build.sh", "build/preflight.sh",
                   "build/Dockerfile"):
        if not (ROOT / script).is_file():
            fail(f"build entry point missing: {script}")
    for hook in sorted(HOOKS.glob("*.hook.chroot")):
        body = hook.read_text(encoding="utf-8")
        if not body.startswith("#!"):
            fail(f"{hook.name} has no shebang")
    dockerfile = (ROOT / "build/Dockerfile").read_text(encoding="utf-8")
    for package in ("live-build", "debootstrap", "squashfs-tools", "xorriso",
                    "python3-pil", "grub-common", "fonts-dejavu-core"):
        if package not in dockerfile:
            fail(f"build/Dockerfile does not install build dependency {package}")
    ok("build inputs are present")


def main() -> int:
    check_yaml()
    check_branding()
    check_calamares_wiring()
    check_desktop_entries()
    check_scripts()
    check_plymouth()
    check_grub_theme()
    check_artwork()
    check_packages()
    check_binary_stage_packages()
    check_persistence()
    check_line_endings()
    check_build_inputs()

    for line in notes:
        print(f"  ok   {line}")
    if errors:
        print()
        for line in errors:
            print(f"  FAIL {line}")
        print(f"\n{len(errors)} problem(s) found")
        return 1
    print("\nselfcheck passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

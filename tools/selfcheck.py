#!/usr/bin/env python3
"""Offline consistency checks for the DeltaOS source tree.

    python3 tools/selfcheck.py

Nothing is built or downloaded. This catches the mistakes that otherwise only
appear late in a live-build run: unparseable YAML, branding files Calamares
refuses to load, artwork a theme references but nobody generates, and package
list typos. It runs in a second on any OS.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
INCLUDES = CONFIG / "includes.chroot"
BRANDING = INCLUDES / "usr/share/deltaos/calamares-branding"
PLYMOUTH = INCLUDES / "usr/share/plymouth/themes/deltaos"
GRUB_THEME = CONFIG / "includes.binary/boot/grub/themes/deltaos"
ARTWORK = INCLUDES / "usr/share/deltaos/artwork"

errors: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    notes.append(message)


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
    elif not (BRANDING / str(slideshow)).is_file():
        fail(f"branding slideshow '{slideshow}' does not exist")
    if "slideshowAPI" not in desc:
        fail("branding.desc is missing slideshowAPI")
    ok("calamares branding is structurally complete")


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


def check_build_inputs() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", version):
        fail(f"VERSION is not a semantic version: {version!r}")
    for script in ("build/build-iso.sh", "build/docker-build.sh",
                   "build/apply-grub-theme.sh", "build/wsl-build.sh",
                   "build/build-windows.ps1"):
        if not (ROOT / script).is_file():
            fail(f"build entry point missing: {script}")
    for hook in sorted((CONFIG / "hooks/live").glob("*.hook.chroot")):
        body = hook.read_text(encoding="utf-8")
        if not body.startswith("#!"):
            fail(f"{hook.name} has no shebang")
    ok("build inputs are present")


def main() -> int:
    check_yaml()
    check_branding()
    check_plymouth()
    check_grub_theme()
    check_artwork()
    check_packages()
    check_persistence()
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

#!/usr/bin/env python3
"""Validate DeltaOS package lists against the real Debian 13 (trixie) archive.

Package list format (packages/*.list):

    # comment
    package-name                 required
    package-name:i386            package from an explicitly named architecture
    ?package-name                optional, silently dropped if unavailable
    ^package-name                backports only; dropped from the apt list and
                                 written to <name>-backports.txt so an install
                                 hook can pull it with `apt-get install -t`
    !package-name                forbidden, fails if it EXISTS (guards against
                                 packages that would break a live image)

The tool reads the Packages indexes for main/contrib/non-free/non-free-firmware
straight from deb.debian.org, caches them, and either reports (--check) or
writes live-build package lists (-—emit DIR).

Architecture-qualified entries are checked against that architecture's Debian
index. live-build then enables the foreign architecture before installing the
queued package list.

No third-party dependencies; runs on Windows, macOS and Linux.
"""

from __future__ import annotations

import argparse
import gzip
import lzma
import sys
import time
import urllib.request
from pathlib import Path

MIRRORS = (
    "https://deb.debian.org/debian",
    "https://ftp.debian.org/debian",
    "https://mirrors.kernel.org/debian",
)
DIST = "trixie"
ARCH = "amd64"
COMPONENTS = ("main", "contrib", "non-free", "non-free-firmware")
BACKPORTS = "trixie-backports"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "pkgcheck"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _index_paths(dist: str, component: str, architecture: str) -> list[str]:
    paths = []
    for mirror in MIRRORS:
        base = f"{mirror}/dists/{dist}/{component}/binary-{architecture}/Packages"
        paths += [base + ".xz", base + ".gz", base]
    return paths


def fetch_index(component: str, refresh: bool = False,
                architecture: str = ARCH, optional: bool = False) -> set[str]:
    """Return every binary package name in one component (e.g. 'main' or
    'trixie-backports/main').

    Debian keeps a partial i386 archive, so a secondary architecture can be
    missing a component. ``optional`` reports that and yields an empty index
    instead of aborting the build."""
    if "/" in component:
        dist, comp = component.split("/", 1)
    else:
        dist, comp = DIST, component
    CACHE.mkdir(parents=True, exist_ok=True)
    # component may be 'main' or 'trixie-backports/main' -- keep it one file
    cached = CACHE / f"{component.replace('/', '_')}-{architecture}.names"

    if cached.exists() and not refresh:
        age = time.time() - cached.stat().st_mtime
        if age < 7 * 24 * 3600:
            return set(cached.read_text().split())

    last_error: Exception | None = None
    for attempt in range(3):
        for url in _index_paths(dist, comp, architecture):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "DeltaOS-pkgcheck/1.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    raw = resp.read()
                if url.endswith(".xz"):
                    raw = lzma.decompress(raw)
                elif url.endswith(".gz"):
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", "replace")
                names = {line[9:].strip() for line in text.splitlines()
                         if line.startswith("Package: ")}
                if not names:
                    raise ValueError("index contained no Package: fields")
                cached.write_text("\n".join(sorted(names)) + "\n")
                print(f"{DIM}indexed {dist}/{comp}/{architecture}: "
                      f"{len(names)} packages{RESET}")
                return names
            except Exception as exc:  # next mirror / compression
                last_error = exc
        print(f"{YELLOW}retrying {dist}/{comp} after: {last_error!r}{RESET}")
        time.sleep(2 * (attempt + 1))
    if optional:
        print(f"{YELLOW}{dist}/{comp}/{architecture} has no package index; "
              f"treating it as empty{RESET}")
        return set()
    raise SystemExit(f"could not download {component} index: {last_error}")


def read_lists(packages_dir: Path) -> list[tuple[Path, int, str, str]]:
    """(file, line number, kind, package) for every entry."""
    entries: list[tuple[Path, int, str, str]] = []
    for path in sorted(packages_dir.glob("*.list")):
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            kind = "required"
            if line[0] in "?!^":
                kind = {"?": "optional", "!": "forbidden", "^": "backports"}[line[0]]
                line = line[1:].strip()
            if not line:
                continue
            if " " in line or "\t" in line:
                raise SystemExit(f"{path}:{lineno}: one package per line please: {raw!r}")
            entries.append((path, lineno, kind, line))
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packages-dir", default=str(ROOT / "packages"))
    ap.add_argument("--emit", metavar="DIR",
                    help="write filtered .list.chroot files for live-build")
    ap.add_argument("--refresh", action="store_true", help="ignore index cache")
    ap.add_argument("--allow-missing", action="store_true",
                    help="report missing required packages without failing")
    args = ap.parse_args()

    packages_dir = Path(args.packages_dir)
    entries = read_lists(packages_dir)
    if not entries:
        raise SystemExit(f"no package lists found in {packages_dir}")

    index_targets = list(COMPONENTS) + [f"{BACKPORTS}/{c}" for c in ("main", "contrib")]
    architectures = {ARCH}
    for _, _, _, package in entries:
        if ":" in package:
            name, separator, architecture = package.partition(":")
            if not name or not separator or not architecture or ":" in architecture:
                raise SystemExit(f"invalid architecture-qualified package: {package!r}")
            architectures.add(architecture)

    stable_by_arch: dict[str, set[str]] = {}
    backports_by_arch: dict[str, set[str]] = {}
    for architecture in sorted(architectures):
        foreign = architecture != ARCH
        available: dict[str, set[str]] = {
            c: fetch_index(c, args.refresh, architecture, optional=foreign)
            for c in index_targets
        }
        stable_by_arch[architecture] = set().union(*(available[c] for c in COMPONENTS))
        backports_by_arch[architecture] = set().union(
            *(available[f"{BACKPORTS}/{c}"] for c in ("main", "contrib")))

    missing_required: list[str] = []
    missing_optional: list[str] = []
    present_forbidden: list[str] = []
    backports_only: list[str] = []
    resolved: dict[str, list[str]] = {}
    duplicates: dict[str, Path] = {}

    for path, lineno, kind, package in entries:
        pkg, separator, architecture = package.partition(":")
        architecture = architecture if separator else ARCH
        stable = stable_by_arch[architecture]
        backports = backports_by_arch[architecture]
        every = stable | backports
        known = pkg in every
        if package in duplicates and known:
            print(f"{YELLOW}duplicate{RESET} {package} ({path.name}:{lineno}, "
                  f"first in {duplicates[package].name})")
        duplicates.setdefault(package, path)

        if kind == "forbidden":
            if known:
                present_forbidden.append(f"{package} ({path.name}:{lineno})")
            continue
        if kind == "backports":
            if pkg in backports:
                backports_only.append(package)
            else:
                missing_optional.append(f"^ {package} ({path.name}:{lineno})")
            continue
        if pkg in backports and pkg not in stable:
            # A plain name that only exists in backports: warn and treat as optional.
            missing_optional.append(f"(backports only) {package} ({path.name}:{lineno})")
        elif pkg in stable:
            resolved.setdefault(path.stem, []).append(package)
        elif kind == "required":
            missing_required.append(f"{package} ({path.name}:{lineno})")
        else:
            missing_optional.append(f"{package} ({path.name}:{lineno})")

    if args.emit:
        out = Path(args.emit)
        out.mkdir(parents=True, exist_ok=True)
        for stale in out.glob("*.list.chroot"):
            stale.unlink()
        for stem, pkgs in resolved.items():
            (out / f"{stem}.list.chroot").write_text("\n".join(pkgs) + "\n")
        (out / "backports-packages.txt").write_text("\n".join(sorted(set(backports_only))) + "\n")
        print(f"wrote {len(resolved)} lists to {out} "
              f"({len(set(backports_only))} backports packages)")

    if backports_only:
        print(f"\n{DIM}backports, installed by hook:{RESET} "
              f"{', '.join(sorted(set(backports_only)))}")
    if missing_optional:
        print(f"\n{YELLOW}optional, not in trixie (dropped):{RESET}")
        for item in missing_optional:
            print(f"  - {item}")
    if present_forbidden:
        print(f"\n{RED}forbidden but present:{RESET}")
        for item in present_forbidden:
            print(f"  ! {item}")
    if missing_required:
        print(f"\n{RED}required, NOT in trixie:{RESET}")
        for item in missing_required:
            print(f"  x {item}")
    else:
        print(f"\n{GREEN}all required packages exist in Debian {DIST}{RESET}")

    if present_forbidden:
        return 1
    if missing_required and not args.allow_missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

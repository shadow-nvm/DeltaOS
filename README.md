# DeltaOS Aurora

DeltaOS is a custom Debian-based Linux distribution project for x86-64 PCs. It uses Debian 13 (Trixie), KDE Plasma, a DeltaOS welcome/control-center app, and a Calamares live installer. This is a branded and configured Linux distribution built on the Linux kernel; it is not a new kernel or a Windows/macOS replacement written from scratch.

The goal is a familiar, polished desktop that remains usable on modest computers. The core profile keeps the everyday desktop, browser, office basics, gaming/runtime tools, and DeltaHub. The full profile also includes the larger research and creative applications. ZRAM is configured to help when memory is tight, but real performance depends on the PC, graphics driver, and workload.

## What the current source is set up to provide

- A Debian live image that can boot from USB or a virtual DVD, with UEFI and legacy BIOS boot support.
- KDE Plasma with DeltaOS wallpapers, icons, boot splash, and GRUB menu theme (rendered during the build; the stock menu is used if font tools are missing).
- DeltaHub pages for system information, gaming, Wine/Windows programs, Android/Waydroid, software, and appearance.
- Wi-Fi, GPU and audio firmware plus CPU microcode in the base image, so laptops boot with working wireless and graphics.
- Steam, Lutris, Wine, and 32-bit i386 package support for compatibility libraries (live-build enables the i386 architecture and refreshes APT automatically).
- Waydroid as an optional Android container, installed from Debian backports when available.
- Calamares for installing the live system onto a computer.

Compatibility is not universal. Wine and Proton run many Windows programs, but applications that require Windows kernel drivers, some anti-cheat systems, or particular GPU features may not work. Waydroid needs compatible kernel binder support and a working Wayland graphics session; some Android apps are ARM-only or depend on Google services. The ISO configuration has not yet been built or boot-tested, so treat this as an early development image.

## Build an ISO on Windows

Install and start [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with its Linux container engine enabled. WSL 2 is the simplest Windows backend; Docker Desktop can build Linux images without a separate Ubuntu or Debian distribution installed. Leave at least 20 GB free for the build and make sure Docker Desktop has enough disk space. Open PowerShell in the DeltaOS folder and run:

```powershell
Set-Location 'C:\Users\abhin\Documents\Comp\The Delta Project\DeltaOS'
.\build\build-windows.ps1 -Profile core
```

Use `-Profile full` for the larger research/creative image. Add `-Clean` for a fresh build or `-RefreshPackages` to refresh the cached Debian package-name indexes. The ISO and SHA-256 file are written to `build\output\`.

The equivalent build from a Debian 13 host with the listed build dependencies installed is:

```bash
sudo bash ./build/build-iso.sh core --clean
```

### Build inside WSL2 without Docker

If you have WSL2 but not Docker, build natively. Start WSL in the project folder and run:

```bash
cd "/mnt/c/Users/abhin/Documents/Comp/The Delta Project/DeltaOS"
sudo bash build/wsl-build.sh core
```

The helper installs the build dependencies, copies the sources to `~/deltaos-build`, builds there, and copies the ISO back to `build/output/`. It must build on the Linux filesystem: the Windows drive (`/mnt/c`) cannot hold the ownership and device nodes a Debian chroot needs, so building in place fails with obscure `debootstrap` errors.

The first run downloads several hundred megabytes of packages. Use `sudo bash build/wsl-build.sh full` for the larger profile, and pass `--clean` to rebuild from scratch. Keep at least 20 GB free inside the WSL distribution (`df -h ~`).

The container recipe is in `build/Dockerfile`. The Windows helper uses Docker Desktop to run that Linux build environment. Debian live-build needs root privileges and Linux filesystem/mount features, so a normal Windows shell alone cannot produce the ISO.

The output name follows `VERSION`; with the current version it is `deltaos-0.1.0-amd64.iso`. In PowerShell, verify the downloaded or copied image with:

```powershell
Get-FileHash .\build\output\deltaos-0.1.0-amd64.iso -Algorithm SHA256
```

Compare the displayed hash to the matching `.sha256` file.

## Try the ISO in VMware Workstation

1. Create a new 64-bit Debian Linux virtual machine and choose the DeltaOS ISO as its virtual DVD.
2. Allocate 2 virtual CPUs, 4 GB of memory, and a 30 GB virtual disk for a comfortable first run. A smaller live session may start with less memory, but performance will be limited.
3. Start the VM and choose the live DeltaOS entry. The live desktop does not save session changes when you shut down.
4. To install it inside the VM, choose **Install DeltaOS** in the welcome window or application menu and follow Calamares. The virtual disk is the installation target; double-check it before confirming partition changes.

If the display is blank or unstable, turn off 3D acceleration in the VM settings and retry. VM graphics do not represent native gaming performance.

## Try the ISO in Hyper-V

1. Create a **Generation 2** virtual machine, attach the ISO to its virtual DVD drive, and create a 30 GB or larger VHDX.
2. Assign 2 virtual CPUs and 4 GB of startup memory for a comfortable first run.
3. In **Security**, leave Secure Boot enabled and select the **Microsoft UEFI Certificate Authority** template. The image is built with `--uefi-secure-boot auto`, which ships Debian's signed shim when it is available; a custom image is not signed by Microsoft, so if the VM refuses to boot, disable Secure Boot for this test VM and try again. The same applies to a physical PC with Secure Boot enabled.
4. Start the VM, boot the live DeltaOS entry, then use **Install DeltaOS** if you want to install into the VHDX.

## Make a bootable USB drive

Use a spare USB drive of at least 16 GB. Writing the image erases the selected USB drive. In Rufus or balenaEtcher, select the DeltaOS ISO and the correct USB device. If Rufus asks whether to write in ISO or DD mode, choose **DD image mode** for the hybrid live image. Wait for the write to finish, safely eject the USB, then use the computer's one-time boot menu to select it. The boot-menu key varies by manufacturer (often F12, F9, Esc, or Del).

Choose the live entry to try DeltaOS without installing it. By default, the live session is not persistent: files and settings created during that session disappear after shutdown. To install, choose **Install DeltaOS** in the welcome window or application menu and carefully select the destination drive. Confirming partition changes can erase data on the selected drive; back up important files first.

Debian's live manual describes the hybrid ISO and raw USB writing approach: <https://live-team.pages.debian.net/live-manual/html/live-manual.en.html>.

## Current development limits

- Only amd64/x86-64 is configured. ARM PCs are not supported by this image.
- No live-USB persistence, encryption flow, rollback system, DeltaOS update service, or signed DeltaOS package repository is configured yet.
- Secure Boot, virtual machines, graphics, wireless devices, suspend, and the installer still need real boot/install testing on target hardware.
- Windows and Android compatibility layers provide compatibility, not a guarantee that every app or game works.
- The build helper downloads Debian packages. Review package sources and license obligations before distributing an image publicly; Debian's archive areas include firmware and other non-free packages.

## Project layout

- `build/build-iso.sh` — Linux live-build workflow.
- `build/build-windows.ps1` — Windows PowerShell wrapper using Docker Desktop.
- `build/Dockerfile` — Linux builder image.
- `packages/` — package lists for base, desktop, applications, gaming, Android, research, and installer components.
- `config/` — live system hooks, branding, installer settings, and artwork overlays.
- `build/wsl-build.sh` — native WSL2 build helper (no Docker needed).
- `tools/pkgcheck.py` — checks package names against Debian archive indexes (including the i386 subset used by Steam and Wine) and emits live-build package lists.
- `tools/make_assets.py` — prepares DeltaOS artwork for the live image.
- `tools/selfcheck.py` — offline check of the YAML, branding, theme assets and package lists.
- `tools/smoke_test_deltahub.py` — headless PyQt6 test that builds every DeltaHub page.

## Check the tree before a long build

Two commands catch almost every mistake in under a second, and neither needs root:

```bash
python3 tools/selfcheck.py            # YAML, branding, themes, package lists
python3 tools/pkgcheck.py             # package names against the live Debian archive
```

After installing `python3-pyqt6` on a Linux host (WSL or a VM), the desktop app can be checked without a display:

```bash
python3 tools/smoke_test_deltahub.py
```

## If the build fails

The full log is written to `build/work/build.log` inside the build tree (`/work/build/work/build.log` in the Docker container, `~/deltaos-build/build/work/build.log` for the WSL helper). Common causes:

- **Package name moved between Debian releases** — `python3 tools/pkgcheck.py` names the exact list and line.
- **Docker engine is in Windows-container mode** — switch Docker Desktop to Linux containers.
- **Out of disk space** — a full build needs roughly 12 GB of free space while it runs.
- **Stale container state** — rebuild with `--clean`, or remove the `deltaos-build-work` volume and the `deltaos-builder` image.

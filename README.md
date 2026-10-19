# DeltaOS Aurora

DeltaOS is a custom operating system distribution for x86-64 PCs, built on the
Debian 13 ("trixie") foundation with KDE Plasma 6, a DeltaOS control centre, a
branded boot experience and a Calamares installer.

It is not a new kernel written from scratch. It is a complete, installable
Linux distribution: the same engineering approach used by Ubuntu, Linux Mint,
Kali and hundreds of other systems. That is what makes it possible to ship a
real desktop with drivers, Wi-Fi, Steam, Wine and Android support instead of a
demonstration that boots to a text prompt.

## What DeltaOS provides

- **A live system** that boots from a USB stick or a virtual DVD, without
  touching the internal disk, with UEFI and legacy BIOS support (GRUB, and shim
  + signed GRUB for UEFI Secure Boot).
- **An installer** (Calamares) started from the desktop or the application
  menu, with disk partitioning, user creation and bootloader setup, in the
  same way Ubuntu's installer works.
- **KDE Plasma 6** with the DeltaOS look: Breeze Dark colour scheme, Papirus
  Dark icons, Inter UI font, JetBrains Mono for code, DeltaOS wallpapers, a
  branded boot splash (Plymouth) and a branded boot menu.
- **DeltaHub**, the DeltaOS control centre: system overview, gaming tools,
  Windows applications through Wine, Android through Waydroid, software
  sources, wallpapers, an optional dock layout, and a live installer shortcut.
- **Gaming**: Steam, Lutris, GameMode, MangoHud and the 32-bit (i386) graphics
  libraries that most Steam games need. Gamescope is installed from Debian
  backports when available.
- **Windows programs**: Wine, wine64 and wine32 with winetricks. Many
  applications work; kernel drivers, some anti-cheat systems and Microsoft
  Store apps cannot.
- **Android applications**: Waydroid from Debian backports, which runs a real
  Android system image in a container on the Linux kernel. It needs binder
  support and a Wayland session; some apps are ARM-only.
- **Low-resource tuning**: ZRAM compressed swap, a tuned memory profile,
  file indexing off by default, and a desktop that stays usable on 2 GB of RAM.
  Plasma 6 itself is happiest with 4 GB.
- **Study and research tools**: LibreOffice, Firefox, PDF and document
  viewers, Python, a C/C++ toolchain, Node.js, editors; the `full` profile adds
  the scientific Python stack, R, LaTeX, Octave and Blender.
- **Live persistence** (opt-in): keep files and installed packages on the USB
  stick across reboots.

## What you need before you build

A Linux environment is required. Debian's `live-build` creates a chroot with
device nodes, mounts and root-owned files, which Windows cannot provide.

Choose one:

1. **Docker Desktop on Windows** (simplest). It needs WSL 2, which needs
   hardware virtualisation enabled in the BIOS/UEFI ("Intel VT-x", "SVM",
   "Virtualization Technology"). If Docker says WSL 2 cannot start, enable that
   firmware setting first.
2. **WSL 2 with a Debian or Ubuntu distribution**, no Docker. Install it from
   an administrator PowerShell with `wsl --install -d Debian`, then reboot.
3. **Any Debian 13 or Ubuntu machine or virtual machine**, native build.

Budget about 20 GB of free disk space, 4 GB of RAM (8 GB is comfortable) and a
fast internet connection. The first build downloads roughly 1.5–2.5 GB of
Debian packages and takes 30–90 minutes depending on the machine.

## Check the build machine first

Inside the Linux environment (WSL, Docker, or a Debian/Ubuntu host), run:

```bash
bash build/preflight.sh
```

It checks the host tools live-build needs (`lb`, `debootstrap`, `xorriso`,
`mksquashfs`, `grub-pc-bin`, Pillow), free disk space, memory and whether the
Debian mirror is reachable, and prints PASS/WARN/FAIL for each. Fixing a FAIL
here saves a build that would otherwise die in the last stage.

## Build the ISO

### Windows, with Docker Desktop

```powershell
Set-Location 'C:\Users\abhin\Documents\Comp\The Delta Project\DeltaOS'
.\build\build-windows.ps1 -Profile core
```

Use `-Profile full` for the larger research/creative image, `-Clean` to start
from scratch, and `-RefreshPackages` to refresh the cached Debian package
index. The finished image and its checksum land in `build\output\`:

```text
build\output\deltaos-0.2.0-amd64.iso
build\output\deltaos-0.2.0-amd64.iso.sha256
```

### Windows, with WSL 2 only

```bash
cd "/mnt/c/Users/abhin/Documents/Comp/The Delta Project/DeltaOS"
sudo bash build/wsl-build.sh core
```

The helper installs the build dependencies, copies the sources to
`~/deltaos-build` (a Linux filesystem — building on `/mnt/c` fails with
debootstrap permission errors), builds there and copies the ISO back.

### Debian 13 / Ubuntu host

```bash
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso mtools \
                 dosfstools cpio rsync python3 python3-pil grub-common \
                 grub-pc-bin grub-efi-amd64-bin fonts-dejavu-core
sudo bash ./build/build-iso.sh core --clean
```

`build/build-iso.sh` also accepts `full`, `--refresh-packages` and `--clean`.
The full build log is written to `build/work/build.log`.

### Check the tree before a long build

Two commands catch almost every mistake in a second and need no root:

```bash
python3 tools/selfcheck.py    # YAML, branding, themes, desktop entries, scripts
python3 tools/pkgcheck.py     # every package name against the Debian archive
```

## Run the ISO in VMware Workstation

1. **Create a new virtual machine** → *Typical* → install from an ISO image →
   select `build\output\deltaos-0.2.0-amd64.iso`.
2. Guest operating system: **Linux**, version **Debian 13.x 64-bit** (any
   Debian 12/13 entry works; the ISO provides its own kernel).
3. Name it `DeltaOS`, choose a location, give it a **30 GB** disk (split into
   multiple files is fine).
4. **Customize hardware**: 2 CPUs (4 if your PC allows), **4 GB RAM**, and
   under *Display* turn **3D acceleration off** for the first boot. Virtual
   display drivers are not representative of real gaming performance.
5. Start the VM. The GRUB menu appears; choose **Live system (amd64)**.
6. The live desktop logs in automatically as `live`. Explore it, then click
   **Install DeltaOS** in the welcome window, on DeltaHub's Overview page, or in
   the application menu.
7. In the installer choose **Erase disk** (the virtual disk) or manual
   partitioning, create your user, and install. When it finishes, shut the VM
   down, **detach the ISO** from the virtual DVD drive, and start it again: it
   boots from the virtual disk into the installed system.

If the screen stays black, reboot and choose the **fail-safe** GRUB entry, or
add `nomodeset` to the kernel command line.

## Run the ISO in Hyper-V

1. **Hyper-V Manager → New → Virtual Machine**.
2. Choose **Generation 2** (UEFI).
3. Assign **4096 MB** of startup memory (dynamic memory is fine after install).
4. **Connection**: *Default Switch* for internet access.
5. **Connect a virtual hard disk** → *Create a virtual hard disk* → **30 GB**.
6. **Installation options** → *Install an operating system from a bootable
   image file* → select the DeltaOS ISO.
7. Finish, open the VM settings → **Security** → keep **Enable Secure Boot**
   and select the **Microsoft UEFI Certificate Authority** template. DeltaOS
   ships Debian's Microsoft-signed shim and GRUB, so it boots with Secure Boot
   enabled. If your firmware or Hyper-V build refuses it, disable Secure Boot
   for this VM; DeltaOS still boots.
8. Start the VM → **Action → Connect** → choose the live entry → install as in
   VMware.

Hyper-V does not pass through a physical GPU, so games run poorly there. Use
Hyper-V to test the installer and the desktop, and a real machine for gaming.

## Write a bootable USB stick

Use a USB stick of **at least 16 GB**. Writing the image erases the whole
stick, so copy anything you need off it first.

**Rufus (Windows)** — recommended:

1. Open Rufus, select the DeltaOS ISO under *Boot selection*.
2. Leave *Partition scheme* as **GPT** and *Target system* as **UEFI** (this
   also boots on legacy BIOS machines through the hybrid image).
3. Start, confirm the warning, and wait for "READY".
   If Rufus asks about ISO vs DD mode, choose **DD image mode**.

**balenaEtcher (Windows/macOS/Linux)**: *Flash from file* → the ISO → the USB
stick → *Flash*. Etcher always writes in DD mode.

**Ventoy (optional)**: install Ventoy on the stick, then simply copy the ISO
onto it. You can keep several ISOs on the same stick and boot them from
Ventoy's menu.

**Linux command line**:

```bash
sudo dd if=build/output/deltaos-0.2.0-amd64.iso of=/dev/sdX bs=8M status=progress oflag=sync
```

Replace `/dev/sdX` with the whole disk of the stick (not a partition such as
`/dev/sdX1`). `lsblk` shows which one it is — get this wrong and you erase your
own disk.

Then reboot the PC, open the one-time boot menu (often **F12**, **F9**,
**F11**, **Esc** or **Del**), and pick the USB stick.

## Install DeltaOS on a real PC

1. Boot the stick and choose **Live system (amd64)**. Try the desktop first:
   check Wi-Fi, sound, graphics and your keyboard layout.
2. Start the installer from the welcome window, from DeltaHub's Overview
   page, or from **Install DeltaOS** in the application menu.
3. Choose language, keyboard, timezone, the target disk, and your user account.
4. Read the partitioning summary carefully. **Erasing a disk deletes
   everything on it.** Dual boot works, but shrinking an existing Windows
   partition is safest when done from Windows' disk management first.
5. When the installer finishes, remove the stick and boot from the internal
   disk. Open the firmware boot menu if DeltaOS did not become the default.
6. Secure Boot can stay enabled on UEFI machines: the installer registers
   shim + signed GRUB.

## Make the live USB persistent

The live boot line already includes `persistence`, so a disk volume labelled
`persistence` containing a `persistence.conf` file with the single line
`/ union` is picked up automatically. Without one, nothing is saved.

```bash
sudo deltaos-persistence --status          # is this session persistent?
sudo deltaos-persistence --check /dev/sdX  # describe a stick, change nothing
sudo deltaos-persistence --wizard          # pick a removable disk
sudo deltaos-persistence --make /dev/sdX   # add the volume to a stick
sudo deltaos-persistence --format /dev/sdX2  # use an existing partition
```

`--make` adds one new partition in the free space after the DeltaOS image,
formats it ext4, labels it `persistence` and writes `/ union`. It refuses a
disk that holds the running system or has mounted partitions.

A running live session cannot re-read the partition table of the stick it
booted from, so either prepare the stick before booting it, or boot DeltaOS
from one stick and use `--wizard` to put persistence on a second one. The
volume is **not encrypted**; anybody with the stick can read it. Rewriting the
ISO erases the volume.

## Known limits (read this)

- **No ISO has been built or boot-tested in this workspace.** The configuration
  is complete and internally checked, but graphics, wireless devices, suspend,
  Secure Boot and the installer still need a real build and a real boot on your
  hardware. Expect to iterate.
- Only **amd64/x86-64** is configured. ARM PCs are not supported.
- **Wine** runs many Windows programs, not all of them: kernel drivers, some
  anti-cheat systems and Microsoft Store apps need Windows itself.
- **Waydroid** needs binder support in the kernel and a Wayland session. Some
  Android apps are ARM-only, and apps that require Google services need extra
  setup.
- **Performance claims are hardware-dependent.** ZRAM and the tuned defaults
  help on small machines; they do not turn a 2 GB laptop into a gaming PC.
- There is **no update service, no signed DeltaOS package repository and no
  rollback system yet**. Updates come from Debian's archive through Discover or
  `apt`, as on any Debian system.
- The image ships Debian's `main`, `contrib`, `non-free` and
  `non-free-firmware` components, including firmware. Review Debian's licence
  terms before distributing an image publicly.

## Project layout

| Path | Purpose |
| --- | --- |
| `build/build-iso.sh` | Linux live-build workflow: config, artwork, hooks, ISO |
| `build/preflight.sh` | Verifies a build machine before a long build |
| `build/build-windows.ps1` | Windows PowerShell wrapper using Docker Desktop |
| `build/docker-build.sh` | Docker/Podman wrapper for any host |
| `build/Dockerfile` | Reproducible Debian 13 builder image |
| `build/wsl-build.sh` | Native WSL 2 build without Docker |
| `build/apply-grub-theme.sh` | Renders GRUB fonts and stages the boot-menu theme |
| `packages/*.list` | Package lists: base, desktop, apps, gaming, Android, research, installer |
| `config/hooks/live/` | Chroot hooks: backports, tuning, services |
| `config/includes.chroot/` | Files placed in the live filesystem |
| `config/includes.chroot/usr/bin/deltahub` | DeltaHub control centre (PyQt6) |
| `config/includes.chroot/usr/bin/deltaos-install` | Live installer launcher |
| `config/includes.chroot/usr/bin/deltaos-layout` | Optional dock layout / reset |
| `config/includes.chroot/usr/bin/deltaos-persistence` | Live persistence helper |
| `config/includes.chroot/etc/calamares/` | Installer settings and module configuration |
| `tools/make_assets.py` | Generates every image: wallpapers, icons, splash, GRUB art |
| `tools/selfcheck.py` | Offline consistency checks |
| `tools/pkgcheck.py` | Validates package names against the real Debian archive |
| `tools/smoke_test_deltahub.py` | Headless PyQt6 test of every DeltaHub page |
| `tools/test_persistence.py` | Unit tests for the persistence planner |

## If the build fails

The log is at `build/work/build.log` (`/work/build/work/build.log` inside the
Docker container, `~/deltaos-build/build/work/build.log` for the WSL helper).

- **`Unable to locate package`** — run `python3 tools/pkgcheck.py`; it names the
  list and line. Debian renames packages between releases.
- **`docker: command not found` / "WSL 2 is unable to start"** — enable
  virtualisation in the firmware, install WSL 2, and set Docker Desktop to
  Linux containers.
- **Out of disk space** — a full build needs about 20 GB while it runs.
- **`debootstrap` permission errors** — you are building on `/mnt/c` or another
  Windows filesystem. Use `build/wsl-build.sh`, which builds on the Linux
  filesystem.
- **Stale tree** — rebuild with `--clean`, or remove the Docker volume
  `deltaos-build-work` and the image `deltaos-builder`.
- **No display after boot** — choose the fail-safe GRUB entry or add
  `nomodeset`; on a VM, disable 3D acceleration.

## Verify a finished ISO

```powershell
Get-FileHash .\build\output\deltaos-0.2.0-amd64.iso -Algorithm SHA256
```

Compare it with the `.sha256` file written next to the ISO. On Linux use
`sha256sum -c deltaos-0.2.0-amd64.iso.sha256`. DeltaOS also adds a "Verify
integrity of the boot medium" entry to the GRUB menu, which runs
`verify-checksums` from the live boot system.

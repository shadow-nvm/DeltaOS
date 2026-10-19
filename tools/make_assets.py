#!/usr/bin/env python3
"""Generate every piece of DeltaOS artwork into a live-build includes tree.

    python3 tools/make_assets.py --out config/includes.chroot

Writes (relative to --out):
    usr/share/deltaos/artwork/            wallpapers, GRUB background, logos
    usr/share/deltaos/calamares-branding/ installer images
    usr/share/plymouth/themes/deltaos/    boot splash logo
    usr/share/icons/hicolor/<size>/apps/  app icons
    usr/share/pixmaps/                    .desktop icon fallback

The repository therefore contains no binary artwork: every image is a pure
function of the palette and the drawing code below. Requires Pillow
(apt install python3-pil, or pip install pillow).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("error: Pillow is required (apt install python3-pil / pip install pillow)")

# --- palette ---------------------------------------------------------------
INK = (9, 13, 26)          # deepest background
DEEP = (17, 25, 56)        # background partner for the diagonal gradient
TEAL = (43, 224, 200)      # accent 1: freshness, low-resource calm
BLUE = (76, 141, 255)      # accent 2: trust, work
VIOLET = (124, 92, 255)    # accent 3: creativity, gaming
WHITE = (240, 245, 255)    # glyph colour
MUTED = (168, 182, 216)    # secondary text

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


# --- primitives ------------------------------------------------------------
def mesh(w: int, h: int, c_tl=INK, c_br=DEEP, glows=(), vignette: float = 0.0,
         lowres: bool = True) -> Image.Image:
    """Smooth multi-point gradient background.

    Computed at a small resolution (pure Python is too slow for 4K) and
    upsampled with bicubic filtering -- gradients are smooth, so this is
    visually lossless.
    """
    lw = min(w, 360) if lowres else w
    lh = max(1, round(lw * h / w))
    aspect = w / h
    data = []
    for j in range(lh):
        fy = j / max(1, lh - 1)
        for i in range(lw):
            fx = i / max(1, lw - 1)
            t = fx * 0.55 + fy * 0.45
            r = c_tl[0] + (c_br[0] - c_tl[0]) * t
            g = c_tl[1] + (c_br[1] - c_tl[1]) * t
            b = c_tl[2] + (c_br[2] - c_tl[2]) * t
            for (cx, cy, rad, col, strength) in glows:
                dx = (fx - cx) * aspect
                dy = fy - cy
                k = strength * math.exp(-(dx * dx + dy * dy) / (rad * rad))
                r += col[0] * k
                g += col[1] * k
                b += col[2] * k
            if vignette:
                dx, dy = fx - 0.5, fy - 0.5
                fall = 1.0 - vignette * (dx * dx + dy * dy) * 4.0
                r *= fall
                g *= fall
                b *= fall
            data.append((min(255, max(0, int(r))),
                         min(255, max(0, int(g))),
                         min(255, max(0, int(b)))))
    img = Image.new("RGB", (lw, lh))
    img.putdata(data)
    if (lw, lh) != (w, h):
        img = img.resize((w, h), Image.BICUBIC)
    return img


def delta_mask(size: int, ss: int = 4, slit: bool = True, margin: float = 0.08) -> Image.Image:
    """Anti-aliased DeltaOS mark: an equilateral delta with a horizontal slit.

    The slit reads as a cut through the letterform, giving the mark its
    identity at 16 px as well as at 4096 px.
    """
    s = size * ss
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    apex = (s * 0.5, s * margin)
    bl = (s * margin, s * (1 - margin))
    br = (s * (1 - margin), s * (1 - margin))
    d.polygon([apex, bl, br], fill=255)
    if slit:
        d.rectangle([0, s * 0.62, s, s * 0.70], fill=0)
    return m.resize((size, size), Image.LANCZOS)


def rounded_mask(size: int, radius_frac: float = 0.26, ss: int = 4) -> Image.Image:
    s = size * ss
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, s - 1, s - 1],
                                        radius=int(s * radius_frac), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def colorize(mask: Image.Image, color, alpha: float = 1.0) -> Image.Image:
    layer = Image.new("RGBA", mask.size, color + (255,))
    layer.putalpha(mask.point(lambda v: int(v * alpha)))
    return layer


def glow_layer(mask: Image.Image, blur: float, color, strength: float) -> Image.Image:
    a = mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * strength))
    layer = Image.new("RGBA", mask.size, color + (255,))
    layer.putalpha(a)
    return layer


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    suffix = "Bold" if bold else ""
    cands = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{suffix or 'Regular'}.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in cands:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def paste_center(canvas: Image.Image, layer: Image.Image, cx: float, cy: float) -> None:
    x = int(cx - layer.width / 2)
    y = int(cy - layer.height / 2)
    canvas.alpha_composite(layer, (max(0, x), max(0, y)))


# --- artefacts -------------------------------------------------------------
def make_icon(size: int) -> Image.Image:
    """Rounded-square app icon with a glowing delta mark."""
    bg = mesh(size, size,
              c_tl=(13, 18, 38), c_br=(28, 17, 66),
              glows=[(0.18, 0.86, 0.60, TEAL, 0.50),
                     (0.82, 0.18, 0.55, VIOLET, 0.48),
                     (0.55, 0.55, 0.80, BLUE, 0.14)],
              vignette=0.25)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if size >= 32:
        out.paste(bg, (0, 0), rounded_mask(size, 0.24))
    else:
        out.paste(bg, (0, 0))

    gsz = max(8, int(size * 0.58))
    glyph = delta_mask(gsz, ss=4 if size >= 64 else 2)
    cx = cy = size / 2
    if size >= 64:
        paste_center(out, glow_layer(glyph, size * 0.045, TEAL, 0.55), cx, cy)
        paste_center(out, glow_layer(glyph, size * 0.09, VIOLET, 0.40), cx, cy)
    paste_center(out, colorize(glyph, WHITE), cx, cy)
    return out


def make_wallpaper(w: int, h: int, variant: str = "dark") -> Image.Image:
    if variant == "aurora":
        bg = mesh(w, h, c_tl=(9, 24, 44), c_br=(15, 17, 42),
                  glows=[(0.30, 0.72, 0.75, TEAL, 0.55),
                         (0.72, 0.28, 0.70, VIOLET, 0.55),
                         (0.50, 0.50, 0.95, BLUE, 0.20)],
                  vignette=0.35)
    else:
        bg = mesh(w, h, c_tl=(7, 11, 24), c_br=(15, 21, 50),
                  glows=[(0.12, 0.88, 0.70, TEAL, 0.50),
                         (0.88, 0.12, 0.65, VIOLET, 0.55),
                         (0.50, 0.52, 1.00, BLUE, 0.16)],
                  vignette=0.40)
    img = bg.convert("RGBA")
    gsz = int(min(w, h) * 0.82)
    glyph = delta_mask(gsz, ss=3).point(lambda v: int(v * 0.14))
    layer = colorize(glyph, WHITE)
    paste_center(img, layer, w * 0.66, h * 0.50)
    # accent hairlines top and bottom, echoing the panel
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, max(2, h // 480)], fill=TEAL + (110,))
    return img.convert("RGB")


def make_grub_background(w: int = 1920, h: int = 1080) -> Image.Image:
    bg = mesh(w, h, c_tl=(6, 9, 20), c_br=(12, 17, 42),
              glows=[(0.86, 0.78, 0.70, TEAL, 0.34),
                     (0.14, 0.18, 0.62, VIOLET, 0.34)],
              vignette=0.45)
    img = bg.convert("RGBA")
    gsz = int(h * 0.55)
    glyph = delta_mask(gsz, ss=3).point(lambda v: int(v * 0.12))
    paste_center(img, colorize(glyph, WHITE), w * 0.78, h * 0.55)
    return img.convert("RGB")


def make_welcome(w: int = 1600, h: int = 500) -> Image.Image:
    """Calamares welcome banner: mark, wordmark, tagline."""
    bg = mesh(w, h, c_tl=(8, 12, 26), c_br=(16, 22, 54),
              glows=[(0.14, 0.80, 0.65, TEAL, 0.45),
                     (0.86, 0.20, 0.60, VIOLET, 0.45)],
              vignette=0.30)
    img = bg.convert("RGBA")
    gsz = int(h * 0.52)
    glyph = delta_mask(gsz, ss=4)
    left = int(h * 0.22)
    paste_center(img, glow_layer(glyph, gsz * 0.06, TEAL, 0.5), left + gsz / 2, h / 2)
    paste_center(img, colorize(glyph, WHITE), left + gsz / 2, h / 2)

    d = ImageDraw.Draw(img)
    tx = left + gsz + int(h * 0.10)
    title = find_font(int(h * 0.20), bold=True)
    sub = find_font(int(h * 0.062))
    d.text((tx, h * 0.40), "DeltaOS", font=title, fill=WHITE, anchor="lm")
    d.text((tx, h * 0.62), "Aurora 0.1  \u2014  fast, beautiful, yours",
           font=sub, fill=MUTED, anchor="lm")
    return img.convert("RGB")


def make_splash_logo(size: int = 512) -> Image.Image:
    """Transparent boot-splash mark for Plymouth."""
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gsz = int(size * 0.80)
    glyph = delta_mask(gsz, ss=4)
    paste_center(out, glow_layer(glyph, size * 0.05, TEAL, 0.60), size / 2, size / 2)
    paste_center(out, glow_layer(glyph, size * 0.10, VIOLET, 0.45), size / 2, size / 2)
    paste_center(out, colorize(glyph, WHITE), size / 2, size / 2)
    return out


def make_progress_bar(w: int = 560, h: int = 8) -> tuple[Image.Image, Image.Image]:
    """Plymouth progress bar: dark track + gradient fill (scaled at boot)."""
    def bar(colors) -> Image.Image:
        img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=h, fill=colors[0])
        if len(colors) == 2:
            grad = Image.new("RGB", (w * 2, h * 2))
            data = []
            for j in range(h * 2):
                for i in range(w * 2):
                    t = i / max(1, w * 2 - 1)
                    data.append((
                        int(colors[0][0] + (colors[1][0] - colors[0][0]) * t),
                        int(colors[0][1] + (colors[1][1] - colors[0][1]) * t),
                        int(colors[0][2] + (colors[1][2] - colors[0][2]) * t)))
            grad.putdata(data)
            img = grad.convert("RGBA")
            ImageDraw.Draw(img).rounded_rectangle(
                [0, 0, w * 2 - 1, h * 2 - 1], radius=h, outline=(0, 0, 0, 0))
            mask = Image.new("L", (w * 2, h * 2), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1],
                                                   radius=h, fill=255)
            img.putalpha(mask)
        return img.resize((w, h), Image.LANCZOS)

    return bar([(255, 255, 255, 46)]), bar([(43, 224, 200, 255), (124, 92, 255, 255)])


def make_highlight_slices(directory: Path, color=TEAL) -> None:
    """Nine-slice selection highlight for the GRUB menu
    (highlight_{nw,n,ne,w,c,e,sw,s,se}.png)."""
    radius = 14
    full_w, full_h = 640, 40
    base = Image.new("RGBA", (full_w, full_h), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle([0, 0, full_w - 1, full_h - 1],
                                           radius=radius,
                                           fill=color + (60,),
                                           outline=color + (150,), width=2)
    cw, ch = radius, radius
    parts = {
        "nw": (0, 0, cw, ch), "n": (cw, 0, full_w - 2 * cw, ch),
        "ne": (full_w - cw, 0, cw, ch), "w": (0, ch, cw, full_h - 2 * ch),
        "c": (cw, ch, full_w - 2 * cw, full_h - 2 * ch),
        "e": (full_w - cw, ch, cw, full_h - 2 * ch),
        "sw": (0, full_h - ch, cw, ch), "s": (cw, full_h - ch, full_w - 2 * cw, ch),
        "se": (full_w - cw, full_h - ch, cw, ch),
    }
    directory.mkdir(parents=True, exist_ok=True)
    for name, (x, y, w, h) in parts.items():
        base.crop((x, y, x + w, y + h)).save(directory / f"highlight_{name}.png",
                                             optimize=True)


def save(img: Image.Image, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        img.convert("RGB").save(path, quality=quality, optimize=True, progressive=True)
    else:
        img.save(path, optimize=True)
    kb = path.stat().st_size / 1024
    print(f"    {path}  ({kb:.0f} KB)")


def write_svg_logo(path: Path) -> None:
    """Vector version of the mark for scalable icon slots."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="#0d1226"/>
      <stop offset="0.55" stop-color="#161a3c"/>
      <stop offset="1" stop-color="#1c1140"/>
    </linearGradient>
    <linearGradient id="mark" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="#2be0c8"/>
      <stop offset="0.55" stop-color="#4c8dff"/>
      <stop offset="1" stop-color="#7c5cff"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="120" fill="url(#bg)"/>
  <path fill="url(#mark)" fill-rule="evenodd"
        d="M256 60 L456 442 L56 442 Z M148 356 L364 356 L393 398 L119 398 Z"/>
</svg>
""", encoding="utf-8")
    print(f"    {path}  ({path.stat().st_size / 1024:.0f} KB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="config/includes.chroot",
                    help="live-build includes.chroot tree to write into")
    ap.add_argument("--binary", default="config/includes.binary",
                    help="live-build includes.binary tree (ISO-level GRUB theme)")
    args = ap.parse_args()
    root = Path(args.out)
    binary = Path(args.binary)

    art = root / "usr/share/deltaos/artwork"
    brand = root / "usr/share/deltaos/calamares-branding"
    ply = root / "usr/share/plymouth/themes/deltaos"
    pix = root / "usr/share/pixmaps"

    print("==> generating DeltaOS artwork")
    for size in ICON_SIZES:
        save(make_icon(size), art / f"logo-{size}.png")
    save(make_icon(256), pix / "deltaos.png")
    for size in ICON_SIZES:
        save(make_icon(size),
             root / f"usr/share/icons/hicolor/{size}x{size}/apps/deltaos.png")
    write_svg_logo(art / "deltaos.svg")
    write_svg_logo(root / "usr/share/icons/hicolor/scalable/apps/deltaos.svg")

    save(make_wallpaper(3840, 2160), art / "wallpaper-dark.jpg")
    save(make_wallpaper(2560, 1440), art / "wallpaper-aurora.jpg")
    save(make_grub_background(), art / "grub-background.png")

    save(make_welcome(), brand / "deltaos-welcome.png")
    save(make_icon(512), brand / "deltaos-logo.png")
    save(make_splash_logo(512), ply / "deltaos-logo.png")

    track, fill = make_progress_bar()
    save(track, ply / "bar-track.png")
    save(fill, ply / "bar-fill.png")

    # ISO-level GRUB theme assets (theme.txt already lives in includes.binary)
    theme_dir = binary / "boot/grub/themes/deltaos"
    save(make_grub_background(), theme_dir / "background.png")
    make_highlight_slices(theme_dir)
    print("==> artwork written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Generate favicons, app icons and social share cards for Kennedy Applied Sciences.

Sources
  assets/logo-mark-source.jpg   the bird mark alone on a near-black field (2048x2048)
  assets/logo-source.jpg        bird + wordmark lockup; only used if the mark-only file is missing

Outputs (overwritten on each run)
  assets/logo-mark.png                      512x512, transparent field, used in the page chrome
  assets/icons/favicon.ico                  16 / 32 / 48 multi-resolution
  assets/icons/favicon-{16,32,48,96,192}.png rounded dark tile, strokes thickened at tiny sizes
  assets/icons/apple-touch-icon.png         180x180, opaque (iOS applies its own corner mask)
  assets/icons/android-chrome-{192,512}.png
  assets/icons/maskable-512.png             mark kept inside the 80% safe zone
  assets/icons/mstile-150.png
  assets/share/card-1200x630.png            Open Graph / Twitter / iMessage / Slack
  assets/share/card-1200x900.png            4:3 for structured data
  assets/share/card-1200x1200.png           1:1 for structured data and Google's result thumbnail

The cards are laid out as a centred vertical lockup on purpose: Google, LinkedIn and
iMessage all crop share images towards a square, so anything pushed to the left or
right edge gets cut off.

Typeface: DM Sans, the site's own face. The TTFs are fetched from Google Fonts into
scripts/.fonts/ on first run (git-ignored). Without network access the script falls
back to Inter or DejaVu and says so.

Run: python3 scripts/generate-icons.py
"""
from __future__ import annotations

import math
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = ASSETS / "icons"
SHARE = ASSETS / "share"
FONT_CACHE = ROOT / "scripts" / ".fonts"

MARK_SRC = ASSETS / "logo-mark-source.jpg"
LOCKUP_SRC = ASSETS / "logo-source.jpg"

# Palette mirrors the CSS custom properties in index.html
OB = (12, 12, 12)        # --ob   page background
CU = (200, 121, 65)      # --cu   copper
ASH = (248, 247, 245)    # --ash
ASHD = (212, 209, 204)   # --ashd
TG = (138, 138, 138)     # --tg

SITE = "kennedyappliedsciences.com"
TAGLINE = "Independent applied AI research"

# Thinnest stroke in the 2048px source (the gray wing outline), in source pixels.
MIN_STROKE_SRC = 24.0

GF_CSS = "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap"


# --------------------------------------------------------------------------- mark

def load_mark_rgb() -> tuple[Image.Image, int]:
    """Square RGB crop of the bird on its native dark field, padded ~8%.
    Returns the crop and the field's gray level."""
    if MARK_SRC.exists():
        src = Image.open(MARK_SRC).convert("RGB")
        print(f"  mark source: {MARK_SRC.relative_to(ROOT)}")
    elif LOCKUP_SRC.exists():
        src = Image.open(LOCKUP_SRC).convert("RGB")
        w, h = src.size
        src = src.crop((0, 0, w, int(h * 0.72)))  # drop the wordmark
        print(f"  mark source: {LOCKUP_SRC.relative_to(ROOT)} (top 72%, wordmark dropped)")
    else:
        sys.exit("no logo source found: add assets/logo-mark-source.jpg")

    field = int(np.median(np.asarray(src.convert("L"))[:8, :8]))
    mask = src.convert("L").point(lambda p: 255 if p > field + 28 else 0)
    bbox = mask.getbbox()
    if not bbox:
        sys.exit("no mark content found in source image")
    x0, y0, x1, y1 = bbox
    side = int(max(x1 - x0, y1 - y0) * 1.08)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    canvas = Image.new("RGB", (side, side), (field, field, field))
    canvas.paste(src, (side // 2 - cx, side // 2 - cy))
    return canvas, field


def key_mark(rgb: Image.Image, field: int, lo: int = 24, hi: int = 92) -> Image.Image:
    """Bird-on-dark -> RGBA with a transparent field.
    Alpha ramps 0..1 on the brightest channel between `lo` and `hi`; colours are
    un-premultiplied against the field so anti-aliased edges keep their copper."""
    arr = np.asarray(rgb, dtype=np.float32)
    mx = arr.max(axis=2)
    a = np.clip((mx - lo) / float(hi - lo), 0.0, 1.0)
    safe = np.where(a > 0.02, a, 1.0)[..., None]
    true = (arr - field * (1.0 - a[..., None])) / safe
    true = np.where(a[..., None] > 0.02, true, 0.0)
    out = np.dstack([np.clip(true, 0, 255), a[..., None] * 255.0]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def mark_at(px: int, mark: Image.Image, field: int, min_stroke: float = 0.0) -> Image.Image:
    """RGBA bird whose bounding square is `px` wide.
    For small sizes the strokes are thickened first (at 8x the target) so the
    thin gray lines survive the shrink instead of dissolving."""
    M = mark.size[0]
    inter = min(px * 8, M)
    im = mark if inter == M else mark.resize((inter, inter), Image.LANCZOS)
    if min_stroke:
        now = MIN_STROKE_SRC * inter / M
        want = min_stroke * inter / px
        grow = want - now
        if grow > 0.75:
            k = int(math.ceil(grow)) + 1
            k += (k % 2 == 0)
            im = im.filter(ImageFilter.MaxFilter(k))
    rgba = key_mark(im, field)
    return rgba.convert("RGBa").resize((px, px), Image.LANCZOS).convert("RGBA")


# --------------------------------------------------------------------------- icons

def rounded_mask(size: int, radius: int) -> Image.Image:
    ss = 4
    m = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size * ss - 1, size * ss - 1), radius=radius * ss, fill=255)
    return m.resize((size, size), Image.LANCZOS)


def icon(size: int, mark: Image.Image, field: int, *, inset: float, radius: float = 0.0,
         min_stroke: float = 0.0) -> Image.Image:
    """Dark tile with the bird centred. `radius` is a fraction of `size` (0 = square)."""
    tile = Image.new("RGBA", (size, size), (*OB, 255))
    inner = max(1, int(round(size * inset)))
    bird = mark_at(inner, mark, field, min_stroke)
    tile.alpha_composite(bird, ((size - inner) // 2, (size - inner) // 2))
    if radius:
        tile.putalpha(rounded_mask(size, int(round(size * radius))))
    return tile


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    print(f"  -> {path.relative_to(ROOT)}  {img.size[0]}x{img.size[1]}  {path.stat().st_size:,} B")


# --------------------------------------------------------------------------- fonts

def ensure_fonts() -> dict[int, Path | None]:
    FONT_CACHE.mkdir(exist_ok=True)
    want = {w: FONT_CACHE / f"DMSans-{w}.ttf" for w in (400, 500, 700)}
    if all(p.exists() for p in want.values()):
        return want
    try:
        req = urllib.request.Request(GF_CSS, headers={"User-Agent": "kas-icon-gen/1.0"})
        css = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
        for w_str, url in re.findall(r"font-weight:\s*(\d+);.*?url\((https://[^)]+\.ttf)\)", css, re.S):
            w = int(w_str)
            if w in want and not want[w].exists():
                want[w].write_bytes(urllib.request.urlopen(url, timeout=30).read())
                print(f"  fetched DM Sans {w}")
    except Exception as exc:  # network is optional
        print(f"  ! could not fetch DM Sans ({exc}); using a fallback face")
    return {w: (p if p.exists() else None) for w, p in want.items()}


FALLBACKS = {
    400: ["/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    500: ["/usr/share/fonts/opentype/inter/Inter-Medium.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    700: ["/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


def font(fonts: dict[int, Path | None], weight: int, size: int) -> ImageFont.FreeTypeFont:
    candidates = ([str(fonts[weight])] if fonts.get(weight) else []) + FALLBACKS[weight]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


# --------------------------------------------------------------------------- cards

def glow(img: Image.Image, cx: float, cy: float, radius: float, peak: float) -> Image.Image:
    """Soft copper radial glow, like --glow-cu behind the hero."""
    W, H = img.size
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (radius * radius)
    a = (peak * np.exp(-2.4 * d2))[..., None]
    base = np.asarray(img, dtype=np.float32)
    out = base * (1 - a) + np.array(CU, dtype=np.float32) * a
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def text_size(draw: ImageDraw.ImageDraw, s: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    x0, y0, x1, y1 = draw.textbbox((0, 0), s, font=f, anchor="lt")
    return x1 - x0, y1 - y0


def card(W: int, H: int, mark: Image.Image, field: int, fonts: dict[int, Path | None]) -> Image.Image:
    s = H / 630.0
    img = Image.new("RGB", (W, H), OB)
    img = glow(img, W / 2, H * 0.40, max(W, H) * 0.42, 0.16)
    draw = ImageDraw.Draw(img)

    f_name = font(fonts, 700, int(88 * s))
    f_sub = font(fonts, 400, int(52 * s))
    f_tag = font(fonts, 500, int(26 * s))
    f_url = font(fonts, 400, int(20 * s))

    bird_px = int(236 * s)
    bird = mark_at(bird_px, mark, field)

    name_w, name_h = text_size(draw, "Kennedy", f_name)
    sub_w, sub_h = text_size(draw, "Applied Sciences", f_sub)
    tag_w, tag_h = text_size(draw, TAGLINE, f_tag)
    url_w, url_h = text_size(draw, SITE, f_url)

    g1, g2, g3, g4, g5 = (int(v * s) for v in (18, 10, 34, 24, 16))
    rule_h = max(2, int(2 * s))
    total = bird_px + g1 + name_h + g2 + sub_h + g3 + rule_h + g4 + tag_h + g5 + url_h
    y = (H - total) // 2
    cx = W // 2

    img.paste(bird, (cx - bird_px // 2, y), bird)
    y += bird_px + g1
    draw.text((cx, y), "Kennedy", font=f_name, fill=CU, anchor="mt")
    y += name_h + g2
    draw.text((cx, y), "Applied Sciences", font=f_sub, fill=ASH, anchor="mt")
    y += sub_h + g3
    rw = int(56 * s)
    draw.rectangle((cx - rw // 2, y, cx + rw // 2, y + rule_h - 1), fill=CU)
    y += rule_h + g4
    draw.text((cx, y), TAGLINE, font=f_tag, fill=ASHD, anchor="mt")
    y += tag_h + g5
    draw.text((cx, y), SITE, font=f_url, fill=TG, anchor="mt")
    return img


# --------------------------------------------------------------------------- main

def main() -> int:
    print("Generating icons and share cards…")
    mark, field = load_mark_rgb()
    fonts = ensure_fonts()

    print("· page chrome")
    save(mark_at(512, mark, field), ASSETS / "logo-mark.png")

    print("· favicons (rounded dark tile)")
    fav = {}
    for size, inset in ((16, 0.92), (32, 0.88), (48, 0.84), (96, 0.82), (192, 0.82)):
        fav[size] = icon(size, mark, field, inset=inset, radius=0.2, min_stroke=1.35 if size <= 96 else 0)
        save(fav[size], ICONS / f"favicon-{size}.png")
    ico = ICONS / "favicon.ico"
    fav[48].save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[fav[16], fav[32]])
    print(f"  -> {ico.relative_to(ROOT)}  16/32/48  {ico.stat().st_size:,} B")

    print("· app icons (square dark tile)")
    save(icon(180, mark, field, inset=0.78), ICONS / "apple-touch-icon.png")
    save(icon(192, mark, field, inset=0.80), ICONS / "android-chrome-192.png")
    save(icon(512, mark, field, inset=0.80), ICONS / "android-chrome-512.png")
    save(icon(512, mark, field, inset=0.70), ICONS / "maskable-512.png")
    save(icon(150, mark, field, inset=0.80), ICONS / "mstile-150.png")

    print("· share cards")
    for W, H in ((1200, 630), (1200, 900), (1200, 1200)):
        save(card(W, H, mark, field, fonts), SHARE / f"card-{W}x{H}.png")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

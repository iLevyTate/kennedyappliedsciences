#!/usr/bin/env python3
"""
Generate favicon and social-share icons for Kennedy Applied Sciences.

Source resolution order:
  1. assets/logo-source.png     (preferred: real brand asset, any square size >= 512)
  2. assets/logo-source.jpg/jpeg
  3. procedural fallback        (draws an approximation of the crane mark)

Outputs (overwritten on each run):
  assets/icons/favicon.ico                  (16, 32, 48 multi-resolution)
  assets/icons/favicon-16.png
  assets/icons/favicon-32.png
  assets/icons/favicon-48.png
  assets/icons/favicon-96.png
  assets/icons/apple-touch-icon.png         (180x180)
  assets/icons/android-chrome-192.png
  assets/icons/android-chrome-512.png
  assets/icons/maskable-512.png             (with safe-zone padding for PWA mask)
  assets/icons/mstile-150.png               (Windows tile)
  assets/icons/og-image.png                 (1200x630 Open Graph / Twitter card)
  assets/icons/og-square.png                (1080x1080 for LinkedIn/Instagram)

Run: python3 scripts/generate-icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT = ASSETS / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (12, 12, 12, 255)
ORANGE = (200, 121, 65, 255)
GRAY = (122, 122, 122, 255)
ASH = (248, 247, 245, 255)


def find_source() -> Path | None:
    for name in ("logo-source.png", "logo-source.jpg", "logo-source.jpeg", "logo-source.webp"):
        p = ASSETS / name
        if p.exists():
            return p
    return None


def load_source() -> Image.Image | None:
    src = find_source()
    if src is None:
        return None
    print(f"  using source: {src.relative_to(ROOT)}")
    return Image.open(src).convert("RGBA")


def to_square(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), BG)
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img if img.mode == "RGBA" else None)
    return canvas.resize((size, size), Image.LANCZOS)


def crop_mark(img: Image.Image) -> Image.Image:
    """Auto-crop to non-background pixels, then if the result is taller than
    wide (logo + wordmark layout), keep only the top square so small icons
    render the bird mark cleanly."""
    rgb = img.convert("RGB")
    luma = rgb.convert("L")
    bbox = None
    for thresh in (40, 60, 90):
        mask = luma.point(lambda p, t=thresh: 255 if p > t else 0)
        bbox = mask.getbbox()
        if bbox:
            break
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    pad = int(0.04 * max(x1 - x0, y1 - y0))
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(img.size[0], x1 + pad); y1 = min(img.size[1], y1 + pad)
    cropped = img.crop((x0, y0, x1, y1))
    cw, ch = cropped.size
    if ch > cw * 1.15:
        cropped = cropped.crop((0, 0, cw, cw))
    return cropped


def load_master(size: int = 1024, mark_only: bool = False) -> Image.Image:
    """Return a square RGBA master at `size` px. mark_only crops to the bird."""
    src = load_source()
    if src is None:
        print("  no source PNG found at assets/logo-source.* — drawing procedural fallback")
        return draw_procedural(size)
    if mark_only:
        src = crop_mark(src)
    return to_square(src, size)


def draw_procedural(size: int) -> Image.Image:
    """Approximation of the two-crane mark. Used only until logo-source.png is added."""
    s = size
    img = Image.new("RGBA", (s, s), BG)
    d = ImageDraw.Draw(img, "RGBA")

    def sc(x):
        return int(x * s / 512)

    gray_wing = [
        (sc(70), sc(360)),
        (sc(180), sc(240)),
        (sc(300), sc(130)),
        (sc(460), sc(70)),
        (sc(430), sc(95)),
        (sc(320), sc(175)),
        (sc(250), sc(230)),
        (sc(200), sc(280)),
    ]
    d.polygon(gray_wing, fill=GRAY)

    orange_body = [
        (sc(90), sc(180)),
        (sc(170), sc(200)),
        (sc(240), sc(240)),
        (sc(290), sc(280)),
        (sc(340), sc(320)),
        (sc(380), sc(360)),
        (sc(420), sc(410)),
        (sc(395), sc(405)),
        (sc(350), sc(380)),
        (sc(300), sc(350)),
        (sc(260), sc(320)),
        (sc(200), sc(280)),
        (sc(150), sc(240)),
        (sc(90), sc(180)),
    ]
    d.polygon(orange_body, fill=ORANGE)

    d.line(
        [
            (sc(285), sc(280)),
            (sc(320), sc(310)),
            (sc(360), sc(350)),
            (sc(405), sc(395)),
            (sc(455), sc(425)),
        ],
        fill=ORANGE,
        width=max(2, sc(8)),
        joint="curve",
    )
    d.polygon(
        [(sc(448), sc(420)), (sc(470), sc(432)), (sc(452), sc(426))],
        fill=ORANGE,
    )
    r = max(2, sc(5))
    d.ellipse(
        [(sc(405) - r, sc(395) - r), (sc(405) + r, sc(395) + r)],
        fill=ORANGE,
    )

    return img.filter(ImageFilter.SMOOTH)


def export_png(master: Image.Image, size: int, name: str) -> None:
    out = master.resize((size, size), Image.LANCZOS)
    out.save(OUT / name, "PNG", optimize=True)
    print(f"  → {(OUT / name).relative_to(ROOT)}")


def export_ico(master: Image.Image, name: str = "favicon.ico") -> None:
    sizes = [(16, 16), (32, 32), (48, 48)]
    base = master.resize((256, 256), Image.LANCZOS)
    base.save(OUT / name, format="ICO", sizes=sizes)
    print(f"  → {(OUT / name).relative_to(ROOT)}")


def export_maskable(master: Image.Image, size: int = 512) -> None:
    """PWA maskable icon needs a safe zone — keep mark within central 80%."""
    inner = int(size * 0.78)
    canvas = Image.new("RGBA", (size, size), BG)
    mark = master.resize((inner, inner), Image.LANCZOS)
    canvas.paste(mark, ((size - inner) // 2, (size - inner) // 2), mark)
    canvas.save(OUT / "maskable-512.png", "PNG", optimize=True)
    print(f"  → {(OUT / 'maskable-512.png').relative_to(ROOT)}")


def find_font(preferred: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = preferred + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def export_og(full_logo: Image.Image) -> None:
    """1200x630 Open Graph: full logo on left (has wordmark built in),
    tagline + URL on right."""
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    for y in range(H):
        a = int(32 * (1 - y / H))
        d.line([(0, y), (W, y)], fill=(200, 121, 65, a))

    logo_size = 520
    logo = full_logo.resize((logo_size, logo_size), Image.LANCZOS)
    img.paste(logo, (40, (H - logo_size) // 2), logo)

    text_x = 40 + logo_size + 40
    tag_font = find_font([], 42)
    sub_font = find_font([], 24)
    url_font = find_font([], 20)

    d.line([(text_x, 240), (text_x + 56, 240)], fill=ORANGE, width=3)
    d.text((text_x, 268), "Intelligence", font=tag_font, fill=ASH)
    d.text((text_x, 316), "applied.", font=tag_font, fill=ORANGE)
    d.text((text_x, 364), "Privacy", font=tag_font, fill=ASH)
    d.text((text_x, 412), "prioritized.", font=tag_font, fill=ORANGE)
    d.text(
        (text_x, 478),
        "Private AI for high-trust organizations.",
        font=sub_font,
        fill=(138, 138, 138, 255),
    )
    d.text(
        (text_x, 530),
        "kennedyappliedsciences.com",
        font=url_font,
        fill=(212, 209, 204, 255),
    )

    img.convert("RGB").save(OUT / "og-image.png", "PNG", optimize=True)
    print(f"  → {(OUT / 'og-image.png').relative_to(ROOT)}")


def export_og_square(full_logo: Image.Image) -> None:
    """1080x1080 square share — centered full logo, tagline below."""
    S = 1080
    img = Image.new("RGBA", (S, S), BG)

    logo_size = 820
    logo = full_logo.resize((logo_size, logo_size), Image.LANCZOS)
    img.paste(logo, ((S - logo_size) // 2, 70), logo)

    d = ImageDraw.Draw(img, "RGBA")
    sub_font = find_font([], 32)
    sub = "Intelligence applied. Privacy prioritized."
    bbox = d.textbbox((0, 0), sub, font=sub_font)
    sw = bbox[2] - bbox[0]
    d.text(((S - sw) // 2, 960), sub, font=sub_font, fill=ORANGE)

    img.convert("RGB").save(OUT / "og-square.png", "PNG", optimize=True)
    print(f"  → {(OUT / 'og-square.png').relative_to(ROOT)}")


def main() -> int:
    print("Generating icons…")
    print("· mark-only master (for small icons / favicon / app icons):")
    mark = load_master(1024, mark_only=True)
    print("· full-logo master (for OG / social / square share):")
    full = load_master(1024, mark_only=False)

    export_png(mark, 16, "favicon-16.png")
    export_png(mark, 32, "favicon-32.png")
    export_png(mark, 48, "favicon-48.png")
    export_png(mark, 96, "favicon-96.png")
    export_png(mark, 180, "apple-touch-icon.png")
    export_png(mark, 192, "android-chrome-192.png")
    export_png(mark, 512, "android-chrome-512.png")
    export_png(mark, 150, "mstile-150.png")
    export_ico(mark)
    export_maskable(mark)
    export_og(full)
    export_og_square(full)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

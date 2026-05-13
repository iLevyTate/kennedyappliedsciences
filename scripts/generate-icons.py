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


def load_master(size: int = 1024) -> Image.Image:
    """Return a square RGBA master at `size` px."""
    src = find_source()
    if src is not None:
        print(f"  using source: {src.relative_to(ROOT)}")
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        side = max(w, h)
        canvas = Image.new("RGBA", (side, side), BG)
        canvas.paste(img, ((side - w) // 2, (side - h) // 2), img if img.mode == "RGBA" else None)
        return canvas.resize((size, size), Image.LANCZOS)
    print("  no source PNG found at assets/logo-source.* — drawing procedural fallback")
    return draw_procedural(size)


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


def export_og(master: Image.Image) -> None:
    """1200x630 Open Graph image: mark on left, wordmark + tagline on right."""
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    for y in range(H):
        a = int(28 * (1 - y / H))
        d.line([(0, y), (W, y)], fill=(200, 121, 65, a))

    mark_size = 360
    mark = master.resize((mark_size, mark_size), Image.LANCZOS)
    img.paste(mark, (90, (H - mark_size) // 2), mark)

    text_x = 90 + mark_size + 60
    title_font = find_font([], 76)
    sub_font = find_font([], 30)
    tag_font = find_font([], 22)

    d.text((text_x, 200), "Kennedy", font=title_font, fill=ORANGE)
    d.text((text_x, 290), "Applied Sciences", font=title_font, fill=ASH)
    d.text(
        (text_x, 400),
        "Intelligence applied. Privacy prioritized.",
        font=sub_font,
        fill=(212, 209, 204, 255),
    )
    d.text(
        (text_x, 450),
        "Private AI systems and consulting for high-trust organizations.",
        font=tag_font,
        fill=(138, 138, 138, 255),
    )

    d.line([(text_x, 380), (text_x + 60, 380)], fill=ORANGE, width=2)

    img.convert("RGB").save(OUT / "og-image.png", "PNG", optimize=True)
    print(f"  → {(OUT / 'og-image.png').relative_to(ROOT)}")


def export_og_square(master: Image.Image) -> None:
    S = 1080
    img = Image.new("RGBA", (S, S), BG)
    mark_size = 620
    mark = master.resize((mark_size, mark_size), Image.LANCZOS)
    img.paste(mark, ((S - mark_size) // 2, 140), mark)

    d = ImageDraw.Draw(img, "RGBA")
    title_font = find_font([], 72)
    sub_font = find_font([], 28)

    title = "Kennedy Applied Sciences"
    bbox = d.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    d.text(((S - tw) // 2, 820), title, font=title_font, fill=ASH)

    sub = "Intelligence applied. Privacy prioritized."
    bbox = d.textbbox((0, 0), sub, font=sub_font)
    sw = bbox[2] - bbox[0]
    d.text(((S - sw) // 2, 920), sub, font=sub_font, fill=ORANGE)

    img.convert("RGB").save(OUT / "og-square.png", "PNG", optimize=True)
    print(f"  → {(OUT / 'og-square.png').relative_to(ROOT)}")


def main() -> int:
    print("Generating icons…")
    master = load_master(1024)

    export_png(master, 16, "favicon-16.png")
    export_png(master, 32, "favicon-32.png")
    export_png(master, 48, "favicon-48.png")
    export_png(master, 96, "favicon-96.png")
    export_png(master, 180, "apple-touch-icon.png")
    export_png(master, 192, "android-chrome-192.png")
    export_png(master, 512, "android-chrome-512.png")
    export_png(master, 150, "mstile-150.png")
    export_ico(master)
    export_maskable(master)
    export_og(master)
    export_og_square(master)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Re-compress every PNG in assets/ and assets/icons/ in place.

Strategy per file:
  - try palette (P) mode with adaptive quantization (32, 64, 128, 256 colors)
  - keep the smallest result that visually round-trips (PSNR within tolerance)
  - never enlarge an already-smaller file

Lossless-leaning: quantization is applied only when the perceptual delta is
negligible (the bird-mark icons are effectively 3 flat colors plus antialias,
so palette mode is well below threshold). OG images stay RGB.
"""
from __future__ import annotations
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

TARGETS = sorted({
    *ROOT.glob("assets/icons/*.png"),
    *ROOT.glob("assets/*.png"),
})

# OG images have gradients; keep RGB
KEEP_RGB = {"og-image.png", "og-square.png", "logo-source.jpg"}


def psnr(a: Image.Image, b: Image.Image) -> float:
    if a.size != b.size:
        b = b.resize(a.size)
    a_rgb = a.convert("RGB")
    b_rgb = b.convert("RGB")
    pa = a_rgb.load()
    pb = b_rgb.load()
    w, h = a.size
    se = 0
    n = 0
    step = max(1, min(w, h) // 64)
    for y in range(0, h, step):
        for x in range(0, w, step):
            r1, g1, b1 = pa[x, y]
            r2, g2, b2 = pb[x, y]
            se += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
            n += 3
    if n == 0 or se == 0:
        return 99.0
    mse = se / n
    return 10 * math.log10((255 ** 2) / mse)


def try_palette(img: Image.Image, colors: int) -> bytes:
    pal = img.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
    if "A" in img.mode:
        pal.info["transparency"] = pal.getpixel((0, 0))
    import io
    buf = io.BytesIO()
    pal.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def best_recompress(path: Path) -> tuple[int, int, str]:
    original_size = path.stat().st_size
    img = Image.open(path)
    img.load()

    if path.name in KEEP_RGB:
        # Just re-optimize as RGB
        import io
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "PNG", optimize=True)
        candidate = buf.getvalue()
        chosen = ("rgb-opt", candidate)
    else:
        # Try palette modes
        candidates = []
        for n_colors in (16, 32, 64, 128, 256):
            try:
                data = try_palette(img, n_colors)
            except Exception:
                continue
            test = Image.open(__import__("io").BytesIO(data))
            quality = psnr(img, test)
            if quality >= 38:  # virtually indistinguishable
                candidates.append((len(data), n_colors, data, quality))

        # Also try RGB optimized
        import io
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        candidates.append((len(buf.getvalue()), -1, buf.getvalue(), 99.0))

        candidates.sort(key=lambda c: c[0])
        size, ncols, data, q = candidates[0]
        label = f"pal-{ncols}@psnr={q:.1f}" if ncols > 0 else "rgb-opt"
        chosen = (label, data)

    label, data = chosen
    if len(data) < original_size:
        path.write_bytes(data)
        new_size = len(data)
    else:
        new_size = original_size
        label = "kept-original"
    return original_size, new_size, label


def main() -> int:
    total_before = 0
    total_after = 0
    print(f"Compressing {len(TARGETS)} files…")
    for p in TARGETS:
        before, after, label = best_recompress(p)
        total_before += before
        total_after += after
        pct = (1 - after / before) * 100 if before else 0
        print(f"  {p.relative_to(ROOT)}: {before:>7,} → {after:>7,} bytes  ({pct:+.1f}%)  [{label}]")
    saved = total_before - total_after
    pct = (saved / total_before * 100) if total_before else 0
    print(f"\nTotal: {total_before:,} → {total_after:,} bytes  (saved {saved:,}, {pct:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

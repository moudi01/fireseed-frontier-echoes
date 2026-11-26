"""Generate 1600x900 shared CITADEL_RING backdrop (citadel_ring_ink.png) in P04B warm borderland
storybook style for #14 finale battles (compatible with BOTH DEMON and subsequent ADMIN).

Features:
- Portable CLI: --out <path>, defaulting relative to this script's repo root
  (原型/P06_首章/assets/citadel_ring/citadel_ring_ink.png).
- P04B warm parchment-sandstone & hand-inked borderland palette: warm atmospheric horizon,
  layered outer stone tiers (边缘石阶), weathered threshold slabs (门槛), chipped mortar wear (磨损),
  and aged-bronze ceremonial inlays.
- Clean, calm warm-ivory limestone center floor so 90-cell hex grid, orange/crimson warnings,
  6 terrain props, DEMON, EN04/EN17, players, and future ADMIN remain crisp at 1280x720.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1600, 900
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "原型/P06_首章/assets/citadel_ring/citadel_ring_ink.png"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build P04B warm storybook CITADEL_RING backdrop.")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output PNG path.")
    return p.parse_args()


def _ink_poly(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], fill: tuple[int, int, int],
              outline: tuple[int, int, int] = (72, 58, 46), width: int = 2) -> None:
    draw.polygon(pts, fill=fill)
    if width > 0:
        draw.line(pts + [pts[0]], fill=outline, width=width, joint="curve")


def build_backdrop(out_path: Path) -> Path:
    rng = random.Random(20261126)
    img = Image.new("RGB", (W, H), (222, 212, 196))
    draw = ImageDraw.Draw(img)

    # 1. Warm borderland parchment sky gradient (0..248)
    for y in range(252):
        t = y / 251.0
        r = int(226 - 24 * t)
        g = int(214 - 28 * t)
        b = int(194 - 30 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Subtle hand-drawn warm horizon wash bands
    for y0, y1, col in [(28, 72, (220, 206, 184)), (84, 124, (212, 198, 178))]:
        draw.rectangle([0, y0, W, y1], fill=col)

    # 2. Far layered borderland ridges (warm umber-ochre)
    far_ridge = [(0, 196)]
    for x in range(0, W + 1, 24):
        y = 162 - 22 * math.sin(math.pi * x / W) - 8 * math.cos(2.5 * math.pi * x / W)
        far_ridge.append((x, int(y)))
    far_ridge += [(W, 250), (0, 250)]
    draw.polygon(far_ridge, fill=(176, 160, 142))

    near_ridge = [(0, 214)]
    for x in range(0, W + 1, 20):
        y = 188 - 16 * math.sin(math.pi * x / W) + 5 * math.sin(4.0 * math.pi * x / W)
        near_ridge.append((x, int(y)))
    near_ridge += [(W, 252), (0, 252)]
    draw.polygon(near_ridge, fill=(150, 134, 118))

    # 3. Monumental weathered sandstone ring pylons (rooted cleanly behind parapet)
    pylons = [
        (160, 56, 44, 240),
        (425, 82, 34, 240),
        (800, 38, 56, 240),
        (1175, 82, 34, 240),
        (1440, 56, 44, 240),
    ]
    for cx, top, hw, bot in pylons:
        # Sunlit left face + shaded right face for P04B hand-painted volume
        pts_full = [(cx - hw * 0.72, top), (cx + hw * 0.72, top), (cx + hw, bot), (cx - hw, bot)]
        _ink_poly(draw, pts_full, fill=(138, 122, 106), outline=(74, 58, 46), width=2)
        pts_shade = [(cx + hw * 0.10, top), (cx + hw * 0.72, top), (cx + hw, bot), (cx + hw * 0.18, bot)]
        draw.polygon(pts_shade, fill=(116, 101, 88))
        # Stepped stone cap + aged-bronze ceremonial band
        _ink_poly(draw, [(cx - hw * 0.82, top - 6), (cx + hw * 0.82, top - 6),
                         (cx + hw * 0.76, top + 8), (cx - hw * 0.76, top + 8)],
                  fill=(166, 148, 126), outline=(74, 58, 46), width=2)
        draw.rectangle([cx - hw * 0.76, top + 18, cx + hw * 0.76, top + 28], fill=(182, 138, 84), outline=(88, 64, 42))
        # Subtle weathered stone horizontal courses
        for cy in range(top + 48, bot - 16, 28):
            draw.line([(cx - hw * 0.82, cy), (cx + hw * 0.82, cy)], fill=(98, 84, 72), width=1)

    # 4. Rear circular citadel colonnade arches (3 recessed bays with warm stone voussoirs)
    for ax, aw, ah in [(310, 128, 102), (800, 162, 118), (1290, 128, 102)]:
        by = 246
        _ink_poly(draw, [(ax - aw // 2, by - ah), (ax + aw // 2, by - ah),
                         (ax + aw // 2, by), (ax - aw // 2, by)],
                  fill=(124, 108, 94), outline=(68, 54, 44), width=2)
        # Crown cornice
        _ink_poly(draw, [(ax - aw // 2 - 8, by - ah - 10), (ax + aw // 2 + 8, by - ah - 10),
                         (ax + aw // 2 + 4, by - ah), (ax - aw // 2 - 4, by - ah)],
                  fill=(162, 144, 122), outline=(68, 54, 44), width=2)
        in_w = int(aw * 0.66)
        in_h = int(ah * 0.78)
        draw.pieslice([ax - in_w // 2, by - in_h, ax + in_w // 2, by + in_h // 2], 180, 360, fill=(76, 66, 58))
        draw.rectangle([ax - in_w // 2, by - in_h // 2, ax + in_w // 2, by], fill=(76, 66, 58))
        draw.arc([ax - in_w // 2 + 5, by - in_h + 5, ax + in_w // 2 - 5, by + in_h // 2 - 5],
                 180, 360, fill=(186, 146, 94), width=3)

    # 5. Stepped outer stone ring tiers (边缘石阶) & carved threshold slabs (门槛)
    parapet_pts = [(x, int(252 - 14 * math.sin(math.pi * x / W))) for x in range(0, W + 1, 20)]
    step_pts = [(x, y + 18) for x, y in parapet_pts]
    # Main warm sandstone combat floor (clean, calm, high contrast for warnings & units)
    floor_poly = [(0, H)] + parapet_pts + [(W, H)]
    draw.polygon(floor_poly, fill=(224, 217, 204))

    # Upper stepped curb & weathered block parapet along rear rim
    for i in range(len(parapet_pts) - 1):
        x0, y0 = parapet_pts[i]
        x1, y1 = parapet_pts[i + 1]
        tone = 166 + rng.randint(-6, 6)
        _ink_poly(draw, [(x0, y0 - 20), (x1, y1 - 20), (x1, y1 + 4), (x0, y0 + 4)],
                  fill=(tone, tone - 14, tone - 28), outline=(86, 72, 58), width=1)
        # Lower riser step (石阶)
        _ink_poly(draw, [(x0, y0 + 4), (x1, y1 + 4), (x1, y1 + 17), (x0, y0 + 17)],
                  fill=(196, 186, 170), outline=(124, 110, 96), width=1)

    # Carved rear threshold slab (门槛) centered below main arch
    _ink_poly(draw, [(715, 240), (885, 240), (902, 266), (698, 266)],
              fill=(186, 172, 152), outline=(92, 76, 60), width=2)
    draw.line([(724, 252), (876, 252)], fill=(166, 134, 92), width=2)

    # Subtle warm concentric ring inlays & radial joints on the combat floor (kept very light!)
    cx, cy = W // 2, 548
    for rx, ry, col, w in [
        (710, 290, (196, 186, 170), 2),
        (686, 280, (206, 198, 184), 1),
        (520, 210, (202, 193, 178), 2),
        (336, 134, (200, 190, 174), 2),
    ]:
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col, width=w)

    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        x0, y0 = cx + int(336 * math.cos(rad)), cy + int(134 * math.sin(rad))
        x1, y1 = cx + int(710 * math.cos(rad)), cy + int(290 * math.sin(rad))
        if y0 > 266 and y1 > 266:
            draw.line([(x0, y0), (x1, y1)], fill=(205, 196, 182), width=1)

    # Subtle weathered stone chips & hairline cracks strictly along the outer margin (磨损)
    for _ in range(42):
        angle = rng.uniform(0.12, math.pi - 0.12)
        side = rng.choice((-1, 1))
        rad_mul = rng.uniform(0.92, 1.06)
        px = cx + int(710 * rad_mul * math.cos(angle) * side)
        py = cy + int(290 * rad_mul * math.sin(angle))
        if 275 < py < H - 40 and 24 < px < W - 24:
            dx, dy = rng.randint(8, 22), rng.randint(-6, 6)
            draw.line([(px, py), (px + dx, py + dy)], fill=(184, 173, 158), width=1)
            draw.line([(px + dx, py + dy), (px + dx + rng.randint(4, 10), py + dy + rng.randint(-5, 5))],
                      fill=(192, 182, 168), width=1)

    # 6. Layered foreground stepped stone rim & thresholds framing bottom corners (边缘石阶 + 门槛)
    # Left foreground steps
    _ink_poly(draw, [(0, H - 142), (420, H), (336, H), (0, H - 112)],
              fill=(178, 166, 148), outline=(92, 78, 64), width=2)
    _ink_poly(draw, [(0, H - 112), (336, H), (0, H)],
              fill=(128, 116, 102), outline=(72, 60, 48), width=2)
    # Right foreground steps
    _ink_poly(draw, [(W, H - 142), (W - 420, H), (W - 336, H), (W, H - 112)],
              fill=(178, 166, 148), outline=(92, 78, 64), width=2)
    _ink_poly(draw, [(W, H - 112), (W - 336, H), (W, H)],
              fill=(128, 116, 102), outline=(72, 60, 48), width=2)

    # Subtle weathered stone mortar ticks on foreground ledges
    for k in range(5):
        lx = 48 + k * 64
        ly = H - 122 + int(k * 21)
        draw.line([(lx, ly), (lx - 14, ly + 18)], fill=(86, 72, 58), width=1)
        rx = W - lx
        draw.line([(rx, ly), (rx + 14, ly + 18)], fill=(86, 72, 58), width=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, optimize=True)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    print(f"CITADEL_BACKDROP_OK: {out_path} bytes={out_path.stat().st_size} sha256={digest}")
    return out_path


if __name__ == "__main__":
    build_backdrop(parse_args().out)

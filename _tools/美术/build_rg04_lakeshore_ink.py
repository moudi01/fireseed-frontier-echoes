"""Deterministic P04B wet-ink lakeshore battle backdrop for #15 RG04 ordinary & elite fields.

Generates `res://assets/salt_crossing/rg04_lakeshore_ink.png` (1600x900 landscape ortho),
shared across RG04 ordinary/elite board layouts (SALT_CROSSING 90-hex, DRY_ISLAND, MIRROR_COURT, OPEN)
while keeping G-site's existing `salt_crossing_ink.png` untouched and visually distinct.

Design & gameplay-safety guarantees:
- 100% local procedural PIL + NumPy (zero external assets, zero paid/networked generation).
- Center ~70% x 65% combat zone (x in [240..1360], y in [158..742]):
  * Low texture frequency, cool-neutral cold salt-silt watercolor grain, stable luminance
    for crisp terrain_id tiles, orange/red danger warnings, and skill outlines.
  * ZERO pre-drawn walkable waterlines/bridges, obstacles, hex grids, units, text, or
    rocks that could be misread as blocking obstacles.
- Natural asymmetric outer perimeter:
  * Multi-layered asymmetric distant misty headlands (far-left ridge + mid-right reed spit)
    over tranquil 沉息湖 water with soft reflections and low horizon mist.
  * Organic, varied-density clusters of wind-bent marsh reeds & tide-sheared grass (NO
    equidistant repeating border stamps) and clustered flat wet slate ledges with soft
    water-sheen reflections and broken wet-ink brushwork (NO harsh uniform border lines).
- Writes 1280x720 & 1600x900 board-composition previews and a JSON QA report to local evidence/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 900
SEED = 2026112605


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--out-png", required=True)
    p.add_argument("--out-evidence", required=True)
    return p.parse_args()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def value_noise_2d(h: int, w: int, grid_y: int, grid_x: int, rng: np.random.Generator) -> np.ndarray:
    coarse = rng.random((grid_y, grid_x), dtype=np.float32)
    img = Image.fromarray((coarse * 255.0).astype(np.uint8), mode="L").resize((w, h), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def shore_curve_y(nx: np.ndarray | float) -> np.ndarray | float:
    """Gentle asymmetric natural shoreline curve across upper edge (strictly above y=156)."""
    return (
        134.0
        + 13.0 * np.sin(nx * math.pi * 1.65 + 0.85)
        - 7.0 * np.cos(nx * math.pi * 3.1 - 0.4)
        + 4.0 * np.sin(nx * math.pi * 5.8 + 1.1)
    )


def build_base_wash(rng: np.random.Generator) -> Image.Image:
    """Create cool-neutral cold salt-silt wash, asymmetric multi-layer distant lake, and mist."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = xx / float(W)
    ny = yy / float(H)

    # Multi-scale watercolor & cold salt-silt micro-texture (calm in center, richer on outer banks)
    n_broad = value_noise_2d(H, W, 9, 16, rng)
    n_mid = value_noise_2d(H, W, 28, 48, rng)
    n_fine = value_noise_2d(H, W, 96, 168, rng)
    n_grain = value_noise_2d(H, W, 220, 380, rng)
    mineral = 0.45 * n_broad + 0.30 * n_mid + 0.15 * n_fine + 0.10 * n_grain - 0.50

    # Smooth asymmetric perimeter factor outside the central 70% x 65% combat zone
    dx_out = np.maximum(0.0, np.maximum(0.15 - nx, nx - 0.85)) / 0.15
    dy_out = np.maximum(0.0, np.maximum(0.175 - ny, ny - 0.825)) / 0.175
    perim = np.clip(np.hypot(dx_out, dy_out) + (n_broad - 0.5) * 0.22 * np.clip(dx_out + dy_out, 0.0, 1.0), 0.0, 1.2)
    perim_s = np.clip(perim * perim * (3.0 - 2.0 * np.clip(perim, 0.0, 1.0)), 0.0, 1.0)

    # Central cold salt-silt ground: calm cool-neutral sage-slate (~RGB 196, 203, 201)
    # Outer damp marsh/shoreline edges: cooler wet ink grey-teal (~RGB 148, 164, 166)
    r = 197.0 - 46.0 * perim_s + mineral * (9.5 + 22.0 * perim_s)
    g = 204.0 - 38.0 * perim_s + mineral * (9.5 + 21.0 * perim_s)
    b = 202.0 - 33.0 * perim_s + mineral * (9.0 + 19.0 * perim_s)

    # Uniform subtle cold salt-silt mineral efflorescence (no waterlines, no fake tiles!)
    salt_fleck = np.clip((n_fine - 0.60) / 0.40, 0.0, 1.0) * (0.22 + 0.45 * perim_s)
    r = r * (1.0 - salt_fleck * 0.16) + 224.0 * (salt_fleck * 0.16)
    g = g * (1.0 - salt_fleck * 0.16) + 229.0 * (salt_fleck * 0.16)
    b = b * (1.0 - salt_fleck * 0.16) + 227.0 * (salt_fleck * 0.16)

    # Subtle damp wet-silt tint along asymmetric left-upper cove and lower-right bank
    cove_ul = np.exp(-(((nx - 0.05) / 0.13) ** 2 + ((ny - 0.20) / 0.14) ** 2))
    bank_lr = np.exp(-(((nx - 0.93) / 0.14) ** 2 + ((ny - 0.92) / 0.12) ** 2))
    damp_bias = np.clip(cove_ul * 0.55 + bank_lr * 0.50, 0.0, 0.7) * perim_s
    r -= 16.0 * damp_bias
    g -= 11.0 * damp_bias
    b -= 8.0 * damp_bias

    # Upper tranquil 沉息湖 water band with soft feathered shoreline transition (NO harsh single line!)
    shore_y = shore_curve_y(nx) + (n_mid - 0.5) * 9.0
    in_lake = np.clip((shore_y - yy) / 18.0, 0.0, 1.0)
    lake_t = np.clip(yy / np.maximum(1.0, shore_y), 0.0, 1.0)
    lake_r = 216.0 - 78.0 * (lake_t ** 1.10) + mineral * 12.0
    lake_g = 222.0 - 62.0 * (lake_t ** 1.10) + mineral * 12.0
    lake_b = 220.0 - 54.0 * (lake_t ** 1.10) + mineral * 12.0

    r = r * (1.0 - in_lake) + lake_r * in_lake
    g = g * (1.0 - in_lake) + lake_g * in_lake
    b = b * (1.0 - in_lake) + lake_b * in_lake

    # Layer 1 (Far-back, left-biased misty mountain/shore silhouette, fades out toward right)
    far_fade = np.clip((0.78 - nx) / 0.45, 0.0, 1.0)
    far_top = 46.0 - 22.0 * np.sin(np.clip(nx / 0.72, 0.0, 1.0) * math.pi) - 6.0 * np.sin(nx * 14.0)
    in_far = np.clip((yy - far_top) / 8.0, 0.0, 1.0) * np.clip((76.0 - yy) / 10.0, 0.0, 1.0) * far_fade
    r = r * (1.0 - 0.30 * in_far) + 144.0 * (0.30 * in_far)
    g = g * (1.0 - 0.30 * in_far) + 160.0 * (0.30 * in_far)
    b = b * (1.0 - 0.30 * in_far) + 164.0 * (0.30 * in_far)

    # Layer 2 (Mid-distance, right-biased low mist-shrouded lakeshore spit, x in [0.54..1.0])
    spit_fade = np.clip((nx - 0.50) / 0.18, 0.0, 1.0)
    spit_top = 74.0 - 11.0 * np.sin(np.clip((nx - 0.50) / 0.50, 0.0, 1.0) * math.pi * 1.15) - 4.0 * np.cos(nx * 22.0)
    in_spit = np.clip((yy - spit_top) / 5.0, 0.0, 1.0) * np.clip((92.0 - yy) / 8.0, 0.0, 1.0) * spit_fade
    r = r * (1.0 - 0.44 * in_spit) + 114.0 * (0.44 * in_spit)
    g = g * (1.0 - 0.44 * in_spit) + 132.0 * (0.44 * in_spit)
    b = b * (1.0 - 0.44 * in_spit) + 136.0 * (0.44 * in_spit)

    # Soft inverted water reflection beneath the mid-right spit (y in [90..114])
    refl_spit = np.clip((yy - 90.0) / 4.0, 0.0, 1.0) * np.clip((114.0 - yy) / 18.0, 0.0, 1.0) * spit_fade * (0.45 + 0.55 * n_mid)
    r = r * (1.0 - 0.24 * refl_spit) + 112.0 * (0.24 * refl_spit)
    g = g * (1.0 - 0.24 * refl_spit) + 130.0 * (0.24 * refl_spit)
    b = b * (1.0 - 0.24 * refl_spit) + 134.0 * (0.24 * refl_spit)

    # Layer 3 (Near-left low misty bank bar, x in [0.0..0.34], y in [86..106])
    bar_fade = np.clip((0.36 - nx) / 0.16, 0.0, 1.0)
    bar_top = 90.0 - 8.0 * np.sin(np.clip(nx / 0.34, 0.0, 1.0) * math.pi)
    in_bar = np.clip((yy - bar_top) / 5.0, 0.0, 1.0) * np.clip((106.0 - yy) / 8.0, 0.0, 1.0) * bar_fade
    r = r * (1.0 - 0.38 * in_bar) + 118.0 * (0.38 * in_bar)
    g = g * (1.0 - 0.38 * in_bar) + 136.0 * (0.38 * in_bar)
    b = b * (1.0 - 0.38 * in_bar) + 138.0 * (0.38 * in_bar)

    # Low drifting mist ribbons hugging the distant lake horizon (asymmetric density)
    mist_a = np.exp(-0.5 * ((yy - 68.0) / 22.0) ** 2) * (0.28 + 0.42 * n_broad)
    mist_b = np.exp(-0.5 * ((yy - 108.0) / 16.0) ** 2) * (0.14 + 0.32 * n_mid) * np.clip(0.3 + 0.7 * nx, 0.0, 1.0)
    mist = np.clip(mist_a + mist_b, 0.0, 0.62)
    r = r * (1.0 - mist) + 225.0 * mist
    g = g * (1.0 - mist) + 230.0 * mist
    b = b * (1.0 - mist) + 228.0 * mist

    # Feathered pale salt-crust tide foam gently hugging the upper shoreline edge
    foam_band = np.exp(-0.5 * ((yy - (shore_y + 5.0)) / 5.5) ** 2) * (0.25 + 0.55 * n_mid)
    r = r * (1.0 - 0.42 * foam_band) + 228.0 * (0.42 * foam_band)
    g = g * (1.0 - 0.42 * foam_band) + 233.0 * (0.42 * foam_band)
    b = b * (1.0 - 0.42 * foam_band) + 230.0 * (0.42 * foam_band)

    rgb = np.stack([np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)], axis=-1).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB").convert("RGBA")


def quad_bezier(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], steps: int = 8) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / float(steps)
        mt = 1.0 - t
        x = mt * mt * p0[0] + 2.0 * mt * t * p1[0] + t * t * p2[0]
        y = mt * mt * p0[1] + 2.0 * mt * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def draw_natural_perimeter(base: Image.Image, py_rng: random.Random) -> Image.Image:
    """Paint soft broken wet-ink shorelines, misty distant reeds, wet slate ledges with reflections,
    and wind-bent reed beds strictly in asymmetric outer margins (zero uniform border repetition!)."""
    wash_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ink_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dw = ImageDraw.Draw(wash_layer, "RGBA")
    di = ImageDraw.Draw(ink_layer, "RGBA")

    # 1. Broken, feathery wet-ink shoreline strokes (replaces rigid continuous line!)
    x = 0.0
    while x < W:
        seg_len = py_rng.uniform(45, 165)
        gap = py_rng.uniform(14, 55)
        pts = []
        steps = max(4, int(seg_len / 12))
        for i in range(steps + 1):
            px = min(float(W), x + seg_len * (i / steps))
            py = float(shore_curve_y(px / float(W))) + py_rng.uniform(-1.2, 1.2)
            pts.append((px, py))
        di.line(pts, fill=(66, 82, 86, py_rng.randint(75, 135)), width=py_rng.choice([1, 1, 2]))
        x += seg_len + gap

    # Soft broken lake-water light glints & reflections (y in [74..128])
    for _ in range(44):
        rx = py_rng.uniform(20, W - 140)
        ry = py_rng.uniform(76, 126)
        rw = py_rng.uniform(24, 135)
        dw.line([(rx, ry), (rx + rw, ry)], fill=(232, 238, 236, py_rng.randint(42, 92)), width=1)
        if py_rng.random() < 0.45:
            dw.line([(rx + 8, ry + 3), (rx + rw * 0.72, ry + 3)], fill=(110, 128, 132, py_rng.randint(35, 65)), width=1)

    # 2. Distant misty reeds along the mid-right spit (x in [1040..1580], y ~ 78..92) + soft reflections
    for _ in range(42):
        rx = py_rng.uniform(1020, 1585)
        base_y = 82.0 + py_rng.uniform(-4, 6)
        rh = py_rng.uniform(10, 26)
        lean = py_rng.uniform(-10, -3)
        alpha = int(py_rng.uniform(45, 95) * min(1.0, (rx - 980.0) / 260.0))
        pts = quad_bezier((rx, base_y), (rx + lean * 0.4, base_y - rh * 0.6), (rx + lean, base_y - rh), 5)
        dw.line(pts, fill=(88, 108, 110, alpha), width=1)
        # Soft reflection downward in water
        rpts = quad_bezier((rx, base_y + 2), (rx + lean * 0.3, base_y + rh * 0.45), (rx + lean * 0.7, base_y + rh * 0.75), 4)
        dw.line(rpts, fill=(96, 114, 118, int(alpha * 0.45)), width=1)

    # 3. Clustered wet flat slate-rock shelves with soft water-sheen reflections (asymmetric!)
    def draw_wet_slate_cluster(cx: float, cy: float, count: int, scale: float, has_water_refl: bool = True) -> None:
        for idx in range(count):
            ox = cx + py_rng.uniform(-42, 42) * scale
            oy = cy + py_rng.uniform(-16, 16) * scale
            rx = py_rng.uniform(26, 62) * scale * (1.0 - idx * 0.14)
            ry = py_rng.uniform(9, 20) * scale * (1.0 - idx * 0.12)
            ang = py_rng.uniform(-0.22, 0.22)
            pts = []
            n_v = 11
            for i in range(n_v):
                a = (i / n_v) * math.tau + ang
                rad_j = 0.80 + 0.30 * math.sin(i * 2.7 + ox * 0.05) + 0.10 * math.cos(i * 4.1)
                pts.append((ox + math.cos(a) * rx * rad_j, oy + math.sin(a) * ry * rad_j))
            # Soft damp water-reflection bleed downward
            if has_water_refl:
                refl_pts = [(px, oy + (py - oy) * 1.45 + ry * 0.65) for px, py in pts]
                dw.polygon(refl_pts, fill=(84, 100, 104, 52))
            # Main wet slate wash (soft, no harsh dark border!)
            base_v = py_rng.randint(114, 136)
            dw.polygon(pts, fill=(base_v, base_v + 12, base_v + 14, 195))
            # Delicate partial ink contour along lower/shaded rim only
            rim_pts = pts[1:6]
            di.line(rim_pts, fill=(58, 72, 76, 125), width=1)
            # Soft pale wet specular highlight across upper face
            di.line([(ox - rx * 0.45, oy - ry * 0.25), (ox + rx * 0.30, oy - ry * 0.20)], fill=(224, 232, 230, 88), width=2)

    # Asymmetric organic rock clusters (strictly outside 70%x65% center [240..1360, 158..742])
    draw_wet_slate_cluster(92, 162, 3, 0.95, has_water_refl=True)      # Upper-left cove shelf
    draw_wet_slate_cluster(1495, 168, 2, 0.80, has_water_refl=True)    # Upper-right wet spit stones
    draw_wet_slate_cluster(118, 845, 4, 1.15, has_water_refl=False)    # Lower-left foreground tidal rocks
    draw_wet_slate_cluster(1445, 842, 4, 1.10, has_water_refl=False)   # Lower-right foreground tidal rocks
    draw_wet_slate_cluster(1538, 690, 2, 0.72, has_water_refl=False)   # Far-right sparse wet pebble shelf

    # 4. Wind-bent marsh reeds & tide-sheared grass (varied length, density, smooth curved stalks!)
    def draw_windswept_reed_bed(cx: float, cy: float, spread_x: float, spread_y: float, count: int,
                                wind_x: float, h_min: float, h_max: float, with_refl: bool = False) -> None:
        for _ in range(count):
            # Organic clumped distribution (Gaussian-like around cluster core)
            bx = cx + py_rng.gauss(0.0, spread_x * 0.45)
            by = cy + py_rng.gauss(0.0, spread_y * 0.45)
            h = py_rng.uniform(h_min, h_max)
            bend = wind_x * (h / h_max) * py_rng.uniform(0.75, 1.35)
            p0 = (bx, by)
            p1 = (bx + bend * 0.32, by - h * 0.62)
            p2 = (bx + bend, by - h * py_rng.uniform(0.84, 1.0))
            pts = quad_bezier(p0, p1, p2, steps=7)
            tone_shift = py_rng.randint(-12, 14)
            col = (
                max(52, min(124, 78 + tone_shift)),
                max(68, min(142, 98 + tone_shift)),
                max(64, min(134, 94 + tone_shift)),
                py_rng.randint(115, 198),
            )
            w_px = 2 if h > (h_min + h_max) * 0.52 else 1
            di.line(pts, fill=col, width=w_px)
            # Soft seed-plume tip on ~28% of taller reeds
            if h > h_min + (h_max - h_min) * 0.65 and py_rng.random() < 0.28:
                dw.ellipse([p2[0] - 4, p2[1] - 3, p2[0] + 5, p2[1] + 4], fill=(164, 174, 166, 130))
            # Soft downward water reflection for shoreline reeds
            if with_refl:
                rpts = quad_bezier((bx, by + 2), (bx + bend * 0.25, by + h * 0.35), (bx + bend * 0.65, by + h * 0.55), 5)
                dw.line(rpts, fill=(82, 100, 102, 58), width=1)

    # Natural asymmetric reed beds (NO equidistant side-border repeats!)
    # Rich windswept cove reed-bed in upper-left (leaning right with lake breeze)
    draw_windswept_reed_bed(96, 152, 115, 22, 34, wind_x=34.0, h_min=22, h_max=68, with_refl=True)
    draw_windswept_reed_bed(52, 232, 48, 38, 16, wind_x=26.0, h_min=18, h_max=48, with_refl=False)
    # Sparse windswept reed fringe on upper-right spit
    draw_windswept_reed_bed(1475, 148, 110, 18, 22, wind_x=28.0, h_min=16, h_max=48, with_refl=True)
    # Asymmetric foreground marsh grass: lush cluster on lower-right, lighter cluster on lower-left
    draw_windswept_reed_bed(1435, 862, 165, 28, 42, wind_x=38.0, h_min=24, h_max=76, with_refl=False)
    draw_windswept_reed_bed(1525, 765, 55, 42, 14, wind_x=28.0, h_min=18, h_max=46, with_refl=False)
    draw_windswept_reed_bed(145, 868, 120, 24, 24, wind_x=32.0, h_min=20, h_max=58, with_refl=False)

    # 5. Subtle damp foreground ink-wash vignette along extreme bottom edge (y > 838)
    for y in range(838, H):
        a = int(46 * ((y - 838) / 62.0) ** 1.6)
        dw.line([(0, y), (W, y)], fill=(54, 68, 72, a), width=1)

    # Soft wet-ink bleed for wash layer + delicate crispness for wind-bent reeds
    wash_soft = wash_layer.filter(ImageFilter.GaussianBlur(radius=1.8))
    ink_soft = ink_layer.filter(ImageFilter.GaussianBlur(radius=0.5))
    out = Image.alpha_composite(base, wash_soft)
    out = Image.alpha_composite(out, ink_soft)
    out = Image.alpha_composite(out, ink_layer)
    return out.convert("RGB")


def render_previews(backdrop: Image.Image, out_ev: Path) -> dict:
    out_ev.mkdir(parents=True, exist_ok=True)

    p1280 = backdrop.resize((1280, 720), Image.Resampling.LANCZOS).convert("RGBA")
    ov1 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(ov1, "RGBA")
    x0, y0, x1, y1 = int(1280 * 0.15), int(720 * 0.175), int(1280 * 0.85), int(720 * 0.825)
    d1.rectangle([x0, y0, x1, y1], outline=(48, 86, 94, 140), width=2)
    cols, rows = 10, 9
    rad = 26.0
    dx, dy = rad * 1.732, rad * 1.5 * 0.72
    cx0, cy0 = 640 - (cols - 1) * dx * 0.5, 380 - (rows - 1) * dy * 0.5
    for r in range(rows):
        for c in range(cols):
            hx = cx0 + c * dx + (dx * 0.5 if r % 2 else 0.0)
            hy = cy0 + r * dy
            pts = [(hx + rad * math.cos(math.tau * (i / 6.0 + 0.25)),
                    hy + rad * 0.72 * math.sin(math.tau * (i / 6.0 + 0.25))) for i in range(6)]
            fill = None
            if (c, r) in ((3, 3), (4, 3), (5, 4)):
                fill = (224, 108, 46, 110)
            elif (c, r) in ((1, 2), (2, 2), (7, 6), (8, 6)):
                fill = (76, 146, 168, 95)
            d1.polygon(pts, fill=fill, outline=(62, 78, 82, 82))
    d1.rectangle([16, 12, 540, 38], fill=(32, 42, 46, 190))
    d1.text((24, 19), "PREVIEW ONLY: 1280x720 P04B + SALT_CROSSING 90-hex & Warning/Water Contrast", fill=(236, 240, 238, 255))
    p1_path = out_ev / "rg04_lakeshore_preview_1280x720_salt90.png"
    Image.alpha_composite(p1280, ov1).convert("RGB").save(p1_path)

    p1600 = backdrop.convert("RGBA")
    ov2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(ov2, "RGBA")
    zx0, zy0, zx1, zy1 = int(W * 0.15), int(H * 0.175), int(W * 0.85), int(H * 0.825)
    d2.rectangle([zx0, zy0, zx1, zy1], outline=(42, 92, 104, 165), width=3)
    d2.rectangle([zx0 + 48, zy0 + 32, zx1 - 48, zy1 - 32], outline=(188, 96, 48, 115), width=2)
    d2.rectangle([20, 16, 700, 44], fill=(32, 42, 46, 190))
    d2.text((30, 24), "PREVIEW ONLY: 1600x900 Native Framing | Outer 70%x65% Safe Zone (SALT/DRY_ISLAND/MIRROR_COURT/OPEN)", fill=(236, 240, 238, 255))
    p2_path = out_ev / "rg04_lakeshore_preview_1600x900_layouts.png"
    Image.alpha_composite(p1600, ov2).convert("RGB").save(p2_path)

    return {"preview_1280x720": str(p1_path.resolve()), "preview_1600x900": str(p2_path.resolve())}


def compute_center_stats(img: Image.Image) -> dict:
    arr = np.asarray(img, dtype=np.float32)
    zx0, zy0, zx1, zy1 = int(W * 0.15), int(H * 0.175), int(W * 0.85), int(H * 0.825)
    center = arr[zy0:zy1, zx0:zx1, :]
    luma = 0.299 * center[:, :, 0] + 0.587 * center[:, :, 1] + 0.114 * center[:, :, 2]
    return {
        "zone_rect": [zx0, zy0, zx1, zy1],
        "zone_pct": [70.0, 65.0],
        "mean_rgb": [round(float(center[:, :, i].mean()), 2) for i in range(3)],
        "luma_mean": round(float(luma.mean()), 2),
        "luma_std": round(float(luma.std()), 2),
        "luma_min": round(float(luma.min()), 2),
        "luma_max": round(float(luma.max()), 2),
    }


def main() -> None:
    args = parse_args()
    out_png = Path(args.out_png)
    out_ev = Path(args.out_evidence)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_ev.mkdir(parents=True, exist_ok=True)

    np_rng = np.random.default_rng(SEED)
    py_rng = random.Random(SEED)

    base = build_base_wash(np_rng)
    final_img = draw_natural_perimeter(base, py_rng)
    final_img.save(out_png, format="PNG", optimize=True)

    previews = render_previews(final_img, out_ev)
    stats = compute_center_stats(final_img)
    report = {
        "asset": "res://assets/salt_crossing/rg04_lakeshore_ink.png",
        "out_png": str(out_png.resolve()),
        "width": final_img.width,
        "height": final_img.height,
        "bytes": out_png.stat().st_size,
        "sha256": sha256_file(out_png),
        "seed": SEED,
        "layouts_supported": ["SALT_CROSSING (90-hex)", "DRY_ISLAND", "MIRROR_COURT", "OPEN"],
        "center_combat_zone_stats": stats,
        "previews": previews,
    }
    (out_ev / "rg04_lakeshore_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("RG04_LAKESHORE_OK:", json.dumps({
        "size": [final_img.width, final_img.height],
        "bytes": report["bytes"],
        "sha256": report["sha256"],
        "center": stats,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

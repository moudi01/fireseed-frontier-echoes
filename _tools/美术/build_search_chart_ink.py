"""Deterministic P04B warm frontier storybook base map generator for search_chart_ink.png.

Generates a 1536x1024 RGB aged parchment survey chart with organic topographic
contours, a winding frontier watercourse, subtle marsh/oak marginalia, an
8-point ink compass rose, and a double-line cartographic frame.

All dynamic place names, CAP ids, routes, and clue nodes are rendered at runtime
by `原型/P06_首章/search_chart.gd` so no locked data is baked into the texture.
"""

from __future__ import annotations

import hashlib
import math
import pathlib
import sys
from typing import Iterable, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


WIDTH = 1536
HEIGHT = 1024
SEED = 20261125


def _value_noise(h: int, w: int, grid_y: int, grid_x: int, rng: np.random.Generator) -> np.ndarray:
    grid = rng.random((grid_y + 1, grid_x + 1), dtype=np.float32)
    ys = np.linspace(0.0, grid_y, h, endpoint=False, dtype=np.float32)
    xs = np.linspace(0.0, grid_x, w, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = ys - y0
    fx = xs - x0
    # Smoothstep
    sy = fy * fy * (3.0 - 2.0 * fy)
    sx = fx * fx * (3.0 - 2.0 * fx)

    v00 = grid[y0[:, None], x0[None, :]]
    v10 = grid[y0[:, None], x0[None, :] + 1]
    v01 = grid[y0[:, None] + 1, x0[None, :]]
    v11 = grid[y0[:, None] + 1, x0[None, :] + 1]

    top = v00 * (1.0 - sx[None, :]) + v10 * sx[None, :]
    bot = v01 * (1.0 - sx[None, :]) + v11 * sx[None, :]
    return top * (1.0 - sy[:, None]) + bot * sy[:, None]


def _fbm(h: int, w: int, octaves: Iterable[Tuple[int, int, float]], rng: np.random.Generator) -> np.ndarray:
    acc = np.zeros((h, w), dtype=np.float32)
    total = 0.0
    for gy, gx, amp in octaves:
        acc += _value_noise(h, w, gy, gx, rng) * amp
        total += amp
    return acc / max(total, 1e-6)


def _build_parchment(rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    nx = (xx / WIDTH) * 2.0 - 1.0
    ny = (yy / HEIGHT) * 2.0 - 1.0

    # Multi-scale organic parchment mottling + fine fiber grain
    mottle = _fbm(HEIGHT, WIDTH, [(4, 6, 0.50), (10, 15, 0.30), (24, 36, 0.20)], rng)
    grain = _fbm(HEIGHT, WIDTH, [(64, 96, 0.65), (140, 210, 0.35)], rng)
    fiber_h = _value_noise(HEIGHT, WIDTH, 180, 18, rng)
    fiber_v = _value_noise(HEIGHT, WIDTH, 18, 220, rng)

    # Warm tea-stained edge vignette (keeps center bright and legible)
    edge_dist = np.maximum(np.abs(nx) ** 2.3, np.abs(ny) ** 2.3)
    radial = np.sqrt(nx * nx * 0.78 + ny * ny * 0.88)
    vignette = np.clip(0.55 * edge_dist + 0.38 * np.clip(radial - 0.35, 0.0, 1.2), 0.0, 1.0)

    # Base warm parchment RGB (P04B frontier storybook palette)
    base_r = 224.0
    base_g = 204.0
    base_b = 167.0

    r = base_r + (mottle - 0.5) * 22.0 + (grain - 0.5) * 10.0 + (fiber_h - 0.5) * 4.5 - vignette * 54.0
    g = base_g + (mottle - 0.5) * 20.0 + (grain - 0.5) * 9.0 + (fiber_v - 0.5) * 4.0 - vignette * 58.0
    b = base_b + (mottle - 0.5) * 16.0 + (grain - 0.5) * 8.0 - vignette * 56.0

    # Subtle antique fold creases (vertical center-ish and horizontal)
    fold_x = np.exp(-((xx - WIDTH * 0.505) ** 2) / 14.0)
    fold_x_hi = np.exp(-((xx - (WIDTH * 0.505 + 3.0)) ** 2) / 12.0)
    fold_y = np.exp(-((yy - HEIGHT * 0.51) ** 2) / 16.0)
    fold_y_hi = np.exp(-((yy - (HEIGHT * 0.51 + 3.0)) ** 2) / 12.0)
    crease = -9.0 * (fold_x + fold_y * 0.75) + 6.0 * (fold_x_hi + fold_y_hi * 0.75)

    r += crease
    g += crease * 0.92
    b += crease * 0.78

    # Subtle watercolor land washes (olive-ochre northwest upland, soft sage marsh southeast)
    upland = np.exp(-(((nx + 0.62) / 0.55) ** 2 + ((ny + 0.56) / 0.52) ** 2))
    ridge_se = np.exp(-(((nx - 0.68) / 0.50) ** 2 + ((ny - 0.60) / 0.48) ** 2))
    marsh_sw = np.exp(-(((nx + 0.45) / 0.52) ** 2 + ((ny - 0.58) / 0.45) ** 2))

    r = r - upland * 12.0 - ridge_se * 10.0 - marsh_sw * 18.0
    g = g - upland * 9.0 - ridge_se * 12.0 - marsh_sw * 8.0
    b = b - upland * 16.0 - ridge_se * 18.0 - marsh_sw * 4.0

    rgb = np.stack([np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)], axis=-1).astype(np.uint8)
    return rgb


def _build_elevation_field(rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    nx = xx / WIDTH
    ny = yy / HEIGHT

    # Compose smooth frontier terrain: NW ridge, NE hillock, SE bluff, central valley
    h = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    hills = [
        (0.14, 0.16, 0.24, 0.20, 0.92),  # NW highland
        (0.32, 0.12, 0.18, 0.14, 0.58),  # N spur
        (0.84, 0.22, 0.20, 0.18, 0.64),  # NE hill
        (0.86, 0.80, 0.24, 0.20, 0.86),  # SE bluff
        (0.62, 0.88, 0.18, 0.14, 0.48),  # S rise
        (0.12, 0.78, 0.19, 0.17, 0.55),  # SW knoll
    ]
    for cx, cy, sx, sy, amp in hills:
        h += amp * np.exp(-(((nx - cx) / sx) ** 2 + ((ny - cy) / sy) ** 2))

    # Carve gentle central river/marsh basin so center stays calm for map pins
    river_y = 0.54 + 0.08 * np.sin((nx - 0.15) * math.pi * 1.65) + 0.03 * np.cos(nx * math.pi * 3.1)
    basin = np.exp(-(((ny - river_y) / 0.14) ** 2))
    h -= 0.32 * basin

    warp = _fbm(HEIGHT, WIDTH, [(5, 7, 0.6), (12, 18, 0.4)], rng)
    h += (warp - 0.5) * 0.26
    return h


def _apply_contours_and_water(rgb: np.ndarray, elev: np.ndarray) -> Image.Image:
    out = rgb.astype(np.float32)

    # Topographic contour bands using gradient-normalized distance to iso-levels
    gy, gx = np.gradient(elev)
    grad = np.sqrt(gx * gx + gy * gy) + 1e-5

    levels = [0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.94]
    # Keep contour lines softer in the central interactive zone
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    nx = xx / WIDTH
    ny = yy / HEIGHT
    center_calm = np.exp(-(((nx - 0.48) / 0.34) ** 2 + ((ny - 0.50) / 0.26) ** 2))
    contour_alpha = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    for idx, lv in enumerate(levels):
        dist_px = np.abs(elev - lv) / grad
        width_px = 1.45 if idx % 2 == 0 else 1.05
        strength = (0.42 if idx % 2 == 0 else 0.26) * (1.0 - 0.45 * center_calm)
        line = np.clip(1.0 - dist_px / width_px, 0.0, 1.0) * strength
        contour_alpha = np.maximum(contour_alpha, line)

    # Suppress contours right on the outer frame margin
    margin_mask = (xx > 44) & (xx < WIDTH - 44) & (yy > 40) & (yy < HEIGHT - 40)
    contour_alpha *= margin_mask.astype(np.float32)

    # Warm sepia ink for contours
    ink_r, ink_g, ink_b = 112.0, 86.0, 58.0
    out[..., 0] = out[..., 0] * (1.0 - contour_alpha) + ink_r * contour_alpha
    out[..., 1] = out[..., 1] * (1.0 - contour_alpha) + ink_g * contour_alpha
    out[..., 2] = out[..., 2] * (1.0 - contour_alpha) + ink_b * contour_alpha

    # Soft frontier watercourse ribbon meandering through the lower-mid basin
    river_y = (
        HEIGHT * (0.61 + 0.075 * np.sin((nx - 0.08) * math.pi * 1.55) - 0.025 * np.cos(nx * math.pi * 3.0))
    )
    river_half = 17.0 + 7.0 * np.sin(nx * math.pi * 2.2 + 0.6)
    d_river = np.abs(yy - river_y)
    water_fill = np.clip((river_half - d_river) / 5.5, 0.0, 1.0) * 0.42 * margin_mask
    bank_line = np.clip(1.0 - np.abs(d_river - river_half) / 1.7, 0.0, 1.0) * 0.42 * margin_mask

    # Muted slate-sage watercolor wash
    w_r, w_g, w_b = 132.0, 151.0, 145.0
    out[..., 0] = out[..., 0] * (1.0 - water_fill) + w_r * water_fill
    out[..., 1] = out[..., 1] * (1.0 - water_fill) + w_g * water_fill
    out[..., 2] = out[..., 2] * (1.0 - water_fill) + w_b * water_fill

    # Bank ink lines
    b_r, b_g, b_b = 90.0, 74.0, 54.0
    out[..., 0] = out[..., 0] * (1.0 - bank_line) + b_r * bank_line
    out[..., 1] = out[..., 1] * (1.0 - bank_line) + b_g * bank_line
    out[..., 2] = out[..., 2] * (1.0 - bank_line) + b_b * bank_line

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="RGB")


def _draw_tree_cluster(draw: ImageDraw.ImageDraw, cx: float, cy: float, count: int, rng: np.random.Generator) -> None:
    ink = (96, 74, 50, 140)
    fill = (128, 134, 96, 72)
    for _ in range(count):
        ox = cx + float(rng.uniform(-34, 34))
        oy = cy + float(rng.uniform(-18, 18))
        r = float(rng.uniform(7.5, 13.0))
        # Canopy puffs
        draw.ellipse((ox - r, oy - r * 1.15, ox + r, oy + r * 0.55), fill=fill, outline=ink, width=1)
        draw.ellipse((ox - r * 0.72, oy - r * 1.55, ox + r * 0.72, oy - r * 0.25), fill=fill, outline=ink, width=1)
        # Trunk
        draw.line((ox, oy + r * 0.45, ox, oy + r * 1.15), fill=(86, 63, 42, 165), width=2)


def _draw_reed_tuft(draw: ImageDraw.ImageDraw, cx: float, cy: float, rng: np.random.Generator) -> None:
    ink = (94, 86, 62, 135)
    for i in range(-2, 3):
        lean = i * 4.2 + float(rng.uniform(-1.5, 1.5))
        h = float(rng.uniform(13.0, 22.0))
        draw.line((cx + i * 2.0, cy, cx + i * 2.0 + lean, cy - h), fill=ink, width=1)
    draw.line((cx - 10, cy + 2, cx + 10, cy + 2), fill=(94, 86, 62, 100), width=1)


def _draw_compass_rose(draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float) -> None:
    ink = (84, 61, 39, 175)
    soft = (118, 92, 62, 115)
    gold = (176, 132, 66, 150)

    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=soft, width=2)
    draw.ellipse((cx - radius * 0.84, cy - radius * 0.84, cx + radius * 0.84, cy + radius * 0.84), outline=soft, width=1)

    # Minor diagonal points
    for deg in (45, 135, 225, 315):
        rad = math.radians(deg)
        p_tip = (cx + math.cos(rad) * radius * 0.76, cy + math.sin(rad) * radius * 0.76)
        p_l = (cx + math.cos(rad + 0.35) * radius * 0.19, cy + math.sin(rad + 0.35) * radius * 0.19)
        p_r = (cx + math.cos(rad - 0.35) * radius * 0.19, cy + math.sin(rad - 0.35) * radius * 0.19)
        draw.polygon([p_tip, p_l, (cx, cy)], fill=soft, outline=ink)
        draw.polygon([p_tip, (cx, cy), p_r], fill=(215, 194, 154, 140), outline=ink)

    # Major cardinal points (N/E/S/W)
    for deg in (0, 90, 180, 270):
        rad = math.radians(deg)
        scale = 1.18 if deg == 270 else 1.0
        p_tip = (cx + math.cos(rad) * radius * scale, cy + math.sin(rad) * radius * scale)
        p_l = (cx + math.cos(rad + 0.28) * radius * 0.22, cy + math.sin(rad + 0.28) * radius * 0.22)
        p_r = (cx + math.cos(rad - 0.28) * radius * 0.22, cy + math.sin(rad - 0.28) * radius * 0.22)
        draw.polygon([p_tip, p_l, (cx, cy)], fill=ink if deg == 270 else gold, outline=ink)
        draw.polygon([p_tip, (cx, cy), p_r], fill=(228, 209, 173, 170), outline=ink)

    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(228, 209, 173, 210), outline=ink, width=2)


def _draw_overlays(base: Image.Image, rng: np.random.Generator) -> Image.Image:
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Faint surveyor graticule & rhumb lines
    grid_col = (108, 84, 56, 36)
    for x in range(192, WIDTH - 100, 192):
        draw.line((x, 42, x, HEIGHT - 42), fill=grid_col, width=1)
    for y in range(170, HEIGHT - 80, 170):
        draw.line((44, y, WIDTH - 44, y), fill=grid_col, width=1)

    # Subtle rhumb lines radiating from compass center
    comp_x, comp_y = WIDTH - 134, 134
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        x2 = comp_x + math.cos(rad) * 1400
        y2 = comp_y + math.sin(rad) * 1400
        draw.line((comp_x, comp_y, x2, y2), fill=(112, 86, 56, 20), width=1)

    # Delicate river ripple strokes
    for step in range(8, 92, 4):
        nx = step / 100.0
        rx = WIDTH * nx
        ry = HEIGHT * (0.61 + 0.075 * math.sin((nx - 0.08) * math.pi * 1.55) - 0.025 * math.cos(nx * math.pi * 3.0))
        ripple_len = float(rng.uniform(16.0, 34.0))
        dy = float(rng.uniform(-6.0, 6.0))
        draw.line((rx - ripple_len * 0.5, ry + dy, rx + ripple_len * 0.5, ry + dy), fill=(96, 114, 108, 92), width=1)

    # Faint antique frontier road/footpath traces in outer hills (strictly decorative background)
    hill_path = [
        (82, 278), (156, 260), (234, 248), (318, 255), (412, 240), (496, 224),
    ]
    for i in range(len(hill_path) - 1):
        draw.line((hill_path[i], hill_path[i + 1]), fill=(120, 92, 62, 58), width=2)

    # Storybook marginalia: oak clusters in uplands, reeds near watercourse
    for cx, cy, n in [
        (146, 198, 6), (224, 168, 5), (124, 296, 4),
        (1264, 232, 5), (1368, 286, 4),
        (1322, 818, 6), (1216, 864, 5),
        (164, 824, 4),
    ]:
        _draw_tree_cluster(draw, cx, cy, n, rng)

    for rx, ry in [
        (268, 686), (344, 718), (522, 692), (734, 622),
        (932, 636), (1126, 704), (1236, 738),
    ]:
        _draw_reed_tuft(draw, rx, ry, rng)

    # Compass rose in upper-right corner
    _draw_compass_rose(draw, comp_x, comp_y, 50.0)

    # Double-line cartographic border with corner brass brackets & margin ticks
    frame_outer = (74, 52, 34, 210)
    frame_inner = (102, 74, 48, 175)
    m1, m2 = 22, 34
    draw.rectangle((m1, m1, WIDTH - m1, HEIGHT - m1), outline=frame_outer, width=3)
    draw.rectangle((m2, m2, WIDTH - m2, HEIGHT - m2), outline=frame_inner, width=2)

    # Margin latitude/longitude ticks
    for x in range(112, WIDTH - 96, 96):
        draw.line((x, m1, x, m2), fill=frame_inner, width=2)
        draw.line((x, HEIGHT - m2, x, HEIGHT - m1), fill=frame_inner, width=2)
    for y in range(112, HEIGHT - 96, 96):
        draw.line((m1, y, m2, y), fill=frame_inner, width=2)
        draw.line((WIDTH - m2, y, WIDTH - m1, y), fill=frame_inner, width=2)

    # Corner ink rosettes
    for cx, cy in ((m2, m2), (WIDTH - m2, m2), (m2, HEIGHT - m2), (WIDTH - m2, HEIGHT - m2)):
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(214, 189, 146, 220), outline=frame_outer, width=2)
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=frame_outer)

    # Slight softening of ink overlay to blend into parchment grain
    soft_overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.35))
    return Image.alpha_composite(base.convert("RGBA"), soft_overlay).convert("RGB")


def generate(output_path: pathlib.Path) -> str:
    rng = np.random.default_rng(SEED)
    parchment = _build_parchment(rng)
    elev = _build_elevation_field(rng)
    terrain = _apply_contours_and_water(parchment, elev)
    final_img = _draw_overlays(terrain, rng)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(output_path, format="PNG", optimize=True)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return digest


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    default_out = repo_root / "原型" / "P06_首章" / "assets" / "town" / "search_chart_ink.png"
    out_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else default_out
    digest = generate(out_path)
    print(f"Generated {out_path} ({out_path.stat().st_size} bytes) sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

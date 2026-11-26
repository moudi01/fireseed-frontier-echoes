"""Deterministic P04B wet-ink lakeshore battle backdrop for #15 RG04 ordinary & elite fields.

Generates `res://assets/salt_crossing/rg04_lakeshore_ink.png` (1600x900 landscape ortho),
shared across RG04 ordinary/elite board layouts (SALT_CROSSING 90-hex, DRY_ISLAND, MIRROR_COURT, OPEN)
while keeping G-site's existing `salt_crossing_ink.png` untouched and visually distinct.

Design & gameplay-safety guarantees:
- 100% local procedural PIL + NumPy (zero external assets, zero paid/networked generation).
- Center ~70% x 65% combat zone (x in [240..1360], y in [158..742]):
  * Low texture frequency, cool-neutral cold salt-silt hue, stable luminance for crisp
    terrain_id tiles, orange/red danger warnings, and skill outlines.
  * ZERO pre-drawn walkable waterlines/bridges, obstacles, hex grids, units, text, or
    rocks that could be misread as blocking obstacles.
- Outer perimeter only:
  * Distant tranquil 沉息湖 (Still-Tide Lake) & low horizon mist along upper band (y < 148).
  * Wet ink grey-teal shoreline edges, subtle pale salt-crust tide-line, tide-sheared marsh
    reeds/grass (剪潮岸草), and low wet slate-stone rim (湿石边缘) tucked strictly into outer borders.
- Also writes two composition previews (1280x720 SALT_CROSSING 90-hex & 1600x900 multi-layout
  safe-zone check) and a JSON QA report into the local evidence directory.
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
SEED = 2026112604

# Ink palette (cool wet-ink slate, matching P04B storybook line weight)
INK_DARK = (46, 56, 60, 235)
INK_MID = (64, 78, 82, 185)
INK_SOFT = (88, 104, 108, 120)
SALT_CRUST = (226, 232, 228, 130)


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
    """Smooth bilinearly upsampled 2D value noise in [0, 1]."""
    coarse = rng.random((grid_y, grid_x), dtype=np.float32)
    img = Image.fromarray((coarse * 255.0).astype(np.uint8), mode="L").resize((w, h), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def build_base_wash(rng: np.random.Generator) -> Image.Image:
    """Create the cool-neutral cold salt-silt base, distant misty lake, and wet perimeter gradient."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = xx / float(W)
    ny = yy / float(H)

    # Multi-octave gentle mineral/paper wash (strictly low amplitude in combat zone!)
    n_low = value_noise_2d(H, W, 10, 18, rng)
    n_mid = value_noise_2d(H, W, 24, 42, rng)
    n_fine = value_noise_2d(H, W, 72, 128, rng)
    mineral = 0.55 * n_low + 0.30 * n_mid + 0.15 * n_fine - 0.5  # [-0.5, +0.5]

    # Distance outside the central 70% x 65% clean combat zone (x in [0.15..0.85], y in [0.175..0.825])
    dx_out = np.maximum(0.0, np.maximum(0.15 - nx, nx - 0.85)) / 0.15
    dy_out = np.maximum(0.0, np.maximum(0.175 - ny, ny - 0.825)) / 0.175
    perim = np.clip(np.hypot(dx_out, dy_out), 0.0, 1.2)
    perim_s = np.clip(perim * perim * (3.0 - 2.0 * np.clip(perim, 0.0, 1.0)), 0.0, 1.0)

    # Center combat ground: calm cool-neutral salt-silt (~RGB 196, 203, 201), super low variance
    # Perimeter ground: slightly cooler/damper wet ink grey-teal (~RGB 156, 170, 171)
    r = 197.0 - 38.0 * perim_s + mineral * (7.5 + 16.0 * perim_s)
    g = 204.0 - 31.0 * perim_s + mineral * (7.5 + 16.0 * perim_s)
    b = 202.0 - 27.0 * perim_s + mineral * (7.0 + 15.0 * perim_s)

    # Subtle cold salt-efflorescence patches (extremely gentle in center, slightly crisper near edges)
    salt_mask = np.clip((n_mid - 0.62) / 0.38, 0.0, 1.0) * (0.28 + 0.55 * perim_s)
    r = r * (1.0 - salt_mask * 0.22) + 224.0 * (salt_mask * 0.22)
    g = g * (1.0 - salt_mask * 0.22) + 229.0 * (salt_mask * 0.22)
    b = b * (1.0 - salt_mask * 0.22) + 226.0 * (salt_mask * 0.22)

    # Upper distant 沉息湖 (Still-Tide Lake) & low horizon mist strictly above y ~ 142 (ny < 0.158)
    shore_y = 136.0 + 10.0 * np.sin(nx * math.pi * 2.4 + 0.6) + 5.0 * np.sin(nx * math.pi * 6.0) + (n_low[0] - 0.5) * 8.0
    in_lake = np.clip((shore_y - yy) / 14.0, 0.0, 1.0)
    # Lake water gradient: deeper cool grey-teal near shoreline -> misty pale sky-fog at top
    lake_t = np.clip(yy / np.maximum(1.0, shore_y), 0.0, 1.0)
    lake_r = 212.0 - 72.0 * (lake_t ** 1.15) + mineral * 10.0
    lake_g = 218.0 - 58.0 * (lake_t ** 1.15) + mineral * 10.0
    lake_b = 216.0 - 52.0 * (lake_t ** 1.15) + mineral * 10.0

    r = r * (1.0 - in_lake) + lake_r * in_lake
    g = g * (1.0 - in_lake) + lake_g * in_lake
    b = b * (1.0 - in_lake) + lake_b * in_lake

    # Distant misty ridge silhouette tucked into top sky (y in [22..68])
    ridge_y = 58.0 - 16.0 * np.sin(nx * math.pi * 1.7 + 0.4) - 8.0 * np.sin(nx * math.pi * 4.2 + 1.2)
    in_ridge = np.clip((yy - ridge_y) / 6.0, 0.0, 1.0) * np.clip((76.0 - yy) / 10.0, 0.0, 1.0)
    r = r * (1.0 - 0.28 * in_ridge) + 148.0 * (0.28 * in_ridge)
    g = g * (1.0 - 0.28 * in_ridge) + 162.0 * (0.28 * in_ridge)
    b = b * (1.0 - 0.28 * in_ridge) + 164.0 * (0.28 * in_ridge)

    # Soft low-mist veil hugging the horizon (y in [42..118])
    mist_band = np.exp(-0.5 * ((yy - 78.0) / 26.0) ** 2) * (0.35 + 0.35 * n_low)
    r = r * (1.0 - mist_band) + 224.0 * mist_band
    g = g * (1.0 - mist_band) + 229.0 * mist_band
    b = b * (1.0 - mist_band) + 227.0 * mist_band

    rgb = np.stack([np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)], axis=-1).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB").convert("RGBA")


def draw_perimeter_details(base: Image.Image, py_rng: random.Random) -> Image.Image:
    """Draw wet-ink shoreline contour, tide-sheared marsh reeds, and low wet slate rim strictly on borders."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # 1. Upper tranquil lake ripples & delicate ink shoreline contour (y <= 146)
    shore_pts = []
    for x in range(0, W + 16, 16):
        nx = x / float(W)
        sy = 136.0 + 10.0 * math.sin(nx * math.pi * 2.4 + 0.6) + 5.0 * math.sin(nx * math.pi * 6.0)
        shore_pts.append((x, sy))
    # Pale salt-efflorescence tide-line wash just below shoreline
    salt_pts = [(x, y + 6.0) for x, y in shore_pts]
    draw.line(salt_pts, fill=(228, 234, 230, 125), width=8)
    draw.line(shore_pts, fill=INK_MID, width=2)
    draw.line([(x, y + 3.0) for x, y in shore_pts], fill=INK_SOFT, width=1)

    # Gentle horizontal distant lake water ripples (y in [78..126])
    for _ in range(34):
        rx = py_rng.randint(30, W - 150)
        ry = py_rng.randint(80, 124)
        rw = py_rng.randint(36, 118)
        draw.line([(rx, ry), (rx + rw, ry)], fill=(230, 236, 235, py_rng.randint(55, 105)), width=1)

    # 2. Low wet smooth slate-stone edges tucked STRICTLY in outer margins (never inside 70%x65% combat zone!)
    def draw_flat_wet_slate(cx: float, cy: float, rx: float, ry: float, ang_deg: float, tone: tuple[int, int, int]) -> None:
        pts = []
        n_v = 9
        for i in range(n_v):
            a = (i / n_v) * math.tau + math.radians(ang_deg)
            rad_j = 0.86 + 0.24 * math.sin(i * 2.3 + cx * 0.03)
            px = cx + math.cos(a) * rx * rad_j
            py = cy + math.sin(a) * ry * rad_j
            pts.append((px, py))
        # Soft wet reflection shadow underneath
        sh_pts = [(x + 2, y + 3) for x, y in pts]
        draw.polygon(sh_pts, fill=(78, 92, 95, 70))
        draw.polygon(pts, fill=(tone[0], tone[1], tone[2], 215), outline=INK_MID)
        # Subtle top salt-sheen highlight
        hi = [(cx - rx * 0.45, cy - ry * 0.35), (cx + rx * 0.35, cy - ry * 0.30)]
        draw.line(hi, fill=(218, 226, 224, 95), width=2)

    # Bottom-left & bottom-right damp foreground slate rim (y in [790..896])
    slate_specs = [
        # Bottom corners & lower edge
        (95, 845, 78, 28, -10, (118, 132, 134)),
        (210, 868, 64, 22, -6, (128, 141, 142)),
        (340, 882, 58, 18, -3, (134, 146, 146)),
        (1505, 848, 82, 28, 10, (116, 130, 133)),
        (1385, 870, 66, 22, 6, (126, 139, 141)),
        (1255, 884, 56, 17, 3, (134, 146, 146)),
        # Far-left & far-right shoreline flat wet stones (x < 135 or x > 1465)
        (64, 235, 52, 22, 14, (126, 140, 142)),
        (52, 520, 46, 20, -8, (122, 136, 138)),
        (78, 725, 58, 24, -12, (120, 134, 136)),
        (1536, 240, 54, 22, -14, (126, 140, 142)),
        (1548, 535, 48, 20, 8, (122, 136, 138)),
        (1522, 730, 58, 24, 12, (120, 134, 136)),
    ]
    for cx, cy, rx, ry, ang, tone in slate_specs:
        draw_flat_wet_slate(cx, cy, rx, ry, ang, tone)

    # 3. Tide-sheared shoreline reeds / sedge grass (剪潮的岸草) strictly on outer banks!
    def draw_sheared_reed_tuft(bx: float, by: float, count: int, lean_x: float, height: float) -> None:
        for _ in range(count):
            ox = bx + py_rng.uniform(-22, 22)
            oy = by + py_rng.uniform(-8, 8)
            h = height * py_rng.uniform(0.65, 1.15)
            # Clean diagonal tide-sheared top blade
            mx = ox + lean_x * 0.45 + py_rng.uniform(-6, 6)
            my = oy - h * 0.55
            tx = ox + lean_x + py_rng.uniform(-8, 8)
            ty = oy - h
            col = (
                py_rng.randint(76, 98),
                py_rng.randint(96, 118),
                py_rng.randint(92, 110),
                py_rng.randint(155, 215),
            )
            draw.line([(ox, oy), (mx, my), (tx, ty)], fill=col, width=py_rng.choice([2, 2, 3]))
            draw.line([(ox + 1, oy), (mx + 1, my)], fill=INK_SOFT, width=1)

    reed_clusters = [
        # Upper-left & upper-right shore edges (y ~ 138..165, x < 210 or x > 1390)
        (88, 152, 10, 18.0, 44.0),
        (168, 148, 8, 16.0, 36.0),
        (1432, 146, 8, -16.0, 36.0),
        (1514, 154, 10, -18.0, 44.0),
        # Far-left & far-right wet banks (x < 145 or x > 1455)
        (68, 345, 9, 16.0, 42.0),
        (74, 625, 9, 15.0, 40.0),
        (1532, 360, 9, -16.0, 42.0),
        (1526, 640, 9, -15.0, 40.0),
        # Bottom-left & bottom-right corners (y > 820)
        (135, 858, 12, 20.0, 52.0),
        (265, 876, 8, 16.0, 38.0),
        (1335, 876, 8, -16.0, 38.0),
        (1465, 858, 12, -20.0, 52.0),
    ]
    for bx, by, cnt, lx, rh in reed_clusters:
        draw_sheared_reed_tuft(bx, by, cnt, lx, rh)

    # 4. Subtle foreground damp ink wash vignette along extreme bottom edge (y > 835)
    for y in range(835, H):
        a = int(52 * ((y - 835) / 65.0) ** 1.5)
        draw.line([(0, y), (W, y)], fill=(54, 66, 70, a), width=1)

    # Slight soft blur on a duplicate pass for authentic wet-ink bleed, then crisp ink overlay
    soft_bleed = overlay.filter(ImageFilter.GaussianBlur(radius=1.2))
    out = Image.alpha_composite(base, soft_bleed)
    out = Image.alpha_composite(out, overlay)
    return out.convert("RGB")


def render_previews(backdrop: Image.Image, out_ev: Path) -> dict:
    """Render two board-composition verification previews (never baked into the deliverable PNG)."""
    out_ev.mkdir(parents=True, exist_ok=True)

    # Preview 1: 1280x720 P04B ortho framing with 90-hex SALT_CROSSING safe-zone & warning/water contrast swatches
    p1280 = backdrop.resize((1280, 720), Image.Resampling.LANCZOS).convert("RGBA")
    ov1 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(ov1, "RGBA")
    # Draw 70%x65% clean combat zone boundary (dashed look)
    x0, y0, x1, y1 = int(1280 * 0.15), int(720 * 0.175), int(1280 * 0.85), int(720 * 0.825)
    d1.rectangle([x0, y0, x1, y1], outline=(48, 86, 94, 150), width=2)
    # Draw representative 90-hex SALT_CROSSING silhouette + sample warning & shallow-water cells (preview only!)
    cols, rows = 10, 9
    rad = 26.0
    dx = rad * 1.732
    dy = rad * 1.5 * 0.72
    cx0 = 640 - (cols - 1) * dx * 0.5
    cy0 = 380 - (rows - 1) * dy * 0.5
    for r in range(rows):
        for c in range(cols):
            hx = cx0 + c * dx + (dx * 0.5 if r % 2 else 0.0)
            hy = cy0 + r * dy
            pts = [(hx + rad * math.cos(math.tau * (i / 6.0 + 0.25)),
                    hy + rad * 0.72 * math.sin(math.tau * (i / 6.0 + 0.25))) for i in range(6)]
            fill = None
            if (c, r) in ((3, 3), (4, 3), (5, 4)):
                fill = (224, 108, 46, 110)  # Danger warning cell contrast check
            elif (c, r) in ((1, 2), (2, 2), (7, 6), (8, 6)):
                fill = (76, 146, 168, 95)   # Shallow-water terrain_id contrast check
            d1.polygon(pts, fill=fill, outline=(62, 78, 82, 85))
    d1.rectangle([16, 12, 540, 38], fill=(32, 42, 46, 195))
    d1.text((24, 19), "PREVIEW ONLY: 1280x720 P04B + SALT_CROSSING 90-hex & Warning/Water Contrast", fill=(236, 240, 238, 255))
    p1_path = out_ev / "rg04_lakeshore_preview_1280x720_salt90.png"
    Image.alpha_composite(p1280, ov1).convert("RGB").save(p1_path)

    # Preview 2: 1600x900 native full-frame showing 70%x65% clean combat zone + DRY_ISLAND / MIRROR_COURT / OPEN bounds
    p1600 = backdrop.convert("RGBA")
    ov2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(ov2, "RGBA")
    zx0, zy0, zx1, zy1 = int(W * 0.15), int(H * 0.175), int(W * 0.85), int(H * 0.825)
    d2.rectangle([zx0, zy0, zx1, zy1], outline=(42, 92, 104, 175), width=3)
    d2.rectangle([zx0 + 48, zy0 + 32, zx1 - 48, zy1 - 32], outline=(188, 96, 48, 120), width=2)
    d2.rectangle([20, 16, 700, 44], fill=(32, 42, 46, 195))
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
    final_img = draw_perimeter_details(base, py_rng)
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

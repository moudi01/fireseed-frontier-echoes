"""Deterministic P04B warm picture-book backdrops for two ordinary DUAL_FLANK fields (issue #13).

RG06 雾痕林缘 (forest edge, beast trails and a fork) and RG08 炉灰荒径 (escort / reclamation road with
old furnace ash, stone walls and repair marks).  100% local procedural PIL + numpy, zero paid or networked
generation.  Both are painted for the REAL DUAL_FLANK board (79 cells, 3 HIGH_OBSTACLE) that two real R03
saves carry (B1/RG06-N01 v46 and B1/RG08-N01 v113).  The projection mirrors hex_board.gd `_layout()` in
sideways battle mode (SIDE_TURN -60deg, SIDE_PITCH 44deg) inside the 1041x669 board node, and the art is
stretched into Rect2(4, 4, size - 8) exactly as `_field_art_rect()` does for field art.

Detail stays on the borders / empty triangles outside the cell union; the floor under the cells is a calm
mid-value wash so grid lines, orange warning cells, anchors and cyan/teal markers keep their contrast.

Usage:  python build_dual_flank_regional_backdrops.py [--out DIR] [--preview-out DIR] [--source-root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RECIPE_VERSION = "dual-flank-regional-1.0"
BOARD_NODE = (1041, 669)          # real board viewport size reported by the Windows runs
ART_INSET = 4                     # _field_art_rect(): Rect2(4, 4, size - 8)
ART_RECT = (BOARD_NODE[0] - 2 * ART_INSET, BOARD_NODE[1] - 2 * ART_INSET)   # 1033 x 661
SS = 1.5
W, H = int(round(ART_RECT[0] * SS)), int(round(ART_RECT[1] * SS))             # 1550 x 992
SIDE_PITCH = math.pi * 44.0 / 180.0
SIDE_TURN = -math.pi / 3.0
INK = (48, 42, 38, 255)
INK_SOFT = (62, 56, 50, 190)
INK_FAINT = (86, 80, 72, 110)

DEFAULT_SOURCE = Path("D:/Personal_dev-wt/issue15-region-windows-matrix")
REGIONS = {
    "RG06": {"file": "rg06_mist_edge_ink.png", "name": "雾痕林缘", "seed": 2026112606, "lift": ((226, 230, 204), 0.88)},
    "RG08": {"file": "rg08_ash_road_ink.png", "name": "炉灰荒径", "seed": 2026112608, "lift": ((228, 218, 200), 0.88)},
}


# ---------------------------------------------------------------- real board geometry
def project_ground(x: float, y: float) -> tuple[float, float]:
    c, s = math.cos(SIDE_TURN), math.sin(SIDE_TURN)
    return x * c - y * s, (x * s + y * c) * math.sin(SIDE_PITCH)


def grid(q: float, r: float) -> tuple[float, float]:
    return project_ground(1.73205 * (q + r / 2.0), 1.5 * r)


def layout(cells: list[dict], size=BOARD_NODE) -> tuple[float, dict]:
    g = [grid(c["q"], c["r"]) for c in cells]
    lo = (min(p[0] for p in g), min(p[1] for p in g))
    hi = (max(p[0] for p in g), max(p[1] for p in g))
    span = (hi[0] - lo[0], hi[1] - lo[1])
    sp = math.sin(SIDE_PITCH)
    top = size[1] * 0.13
    bot = max(top + 40.0, size[1] - 10.0)
    sc = max(1.0, min(60.0, (size[0] - 16.0) / (span[0] + 1.73205), (bot - top) / (span[1] + 2.0 * sp)))
    free = max(0.0, (bot - top) - (span[1] + 2.0 * sp) * sc)
    mid = (size[0] * 0.5, (top + bot) * 0.5 + free * 0.25)
    ctr = (mid[0] - (lo[0] + hi[0]) * 0.5 * sc, mid[1] - (lo[1] + hi[1]) * 0.5 * sc)
    out = {}
    for c in cells:
        gx, gy = grid(c["q"], c["r"])
        out[(c["q"], c["r"])] = (gx * sc + ctr[0], gy * sc + ctr[1])
    return sc, out


def hex_poly(center, radius):
    pts = []
    for i in range(6):
        a = math.tau * (i / 6.0 + 0.25)
        px, py = project_ground(math.cos(a), math.sin(a))
        pts.append((center[0] + px * radius, center[1] + py * radius))
    return pts


def to_img(p):
    return ((p[0] - ART_INSET) * SS, (p[1] - ART_INSET) * SS)


# ---------------------------------------------------------------- fixtures (read only)
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_anchor(source_root: Path, region: str, anchors: dict) -> dict:
    meta = anchors[region]
    src = Path(meta["source"])
    if not src.is_dir():
        src = source_root / "r03-native-final" / "checkpoints" / f"{region}-tick-0.0"
    save = src / "save.json"
    digest = sha256_file(save)
    if digest != meta["hash"]["save.json"]:
        raise SystemExit(f"{region}: save.json hash mismatch {digest}")
    data = json.loads(save.read_bytes())
    b = data["battle"]
    assert b["board_id"] == "DUAL_FLANK" and data["region"] == region and b["tick"] == 0, region
    assert data["site"] == meta["site"] and b["encounter_id"] == meta["encounter"], region
    return {
        "region": region, "site": data["site"], "encounter": b["encounter_id"], "version": data["version"],
        "game_id": data["id"], "save": str(save), "save_sha256": digest,
        "board_id": b["board_id"], "cells": b["board_cells"],
        "actors": [{"id": a["id"], "side": a["side"], "pos": tuple(a["pos"])} for a in b["actors"]],
    }


# ---------------------------------------------------------------- painting helpers
def fbm(rng: np.random.Generator, octaves) -> np.ndarray:
    acc = np.zeros((H, W), np.float32)
    total = 0.0
    for cells_x, weight in octaves:
        cells_y = max(2, int(cells_x * H / W))
        grid_ = rng.random((cells_y, cells_x)).astype(np.float32)
        im = Image.fromarray(grid_, "F").resize((W, H), Image.BICUBIC)
        acc += np.asarray(im) * weight
        total += weight
    acc /= total
    lo, hi = float(acc.min()), float(acc.max())
    return (acc - lo) / max(1e-6, hi - lo)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def blend_field(colors, weights):
    """colors: list[3], weights: list[HxW float] -> float image."""
    out = np.zeros((H, W, 3), np.float32)
    total = np.zeros((H, W), np.float32)
    for col, w in zip(colors, weights):
        out += np.asarray(col, np.float32)[None, None, :] * w[..., None]
        total += w
    return out / np.maximum(total[..., None], 1e-6)


class Scene:
    def __init__(self, anchor: dict, seed: int):
        self.anchor = anchor
        self.rng = random.Random(seed)
        self.np = np.random.default_rng(seed)
        self.sc, self.pos = layout(anchor["cells"])
        self.cells = {(c["q"], c["r"]): c["terrain_id"] for c in anchor["cells"]}
        self.post = []                    # whisper layers composited after the floor lift
        radius = self.sc * 0.96
        mask = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(mask)
        self.cell_img = {}
        for k, p in self.pos.items():
            self.cell_img[k] = to_img(p)
            d.polygon([to_img(q) for q in hex_poly(p, radius)], fill=255)
        self.mask_img = mask
        self.play = np.asarray(mask, np.float32) / 255.0
        near = mask.filter(ImageFilter.GaussianBlur(26))
        self.near = np.asarray(near, np.float32) / 255.0
        wide = mask.filter(ImageFilter.GaussianBlur(120))
        self.wide = np.asarray(wide, np.float32) / 255.0
        self.xs = [v[0] for v in self.cell_img.values()]
        self.ys = [v[1] for v in self.cell_img.values()]

    def free(self, x, y, r=0, limit=0.10) -> bool:
        """True when a detail may sit at this image point (outside the cell footprints)."""
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
            ix, iy = int(x + dx), int(y + dy)
            if ix < 0 or iy < 0 or ix >= W or iy >= H:
                continue
            if self.near[iy, ix] > limit:
                return False
        return True

    def free_column(self, x, y, h, limit=0.03) -> bool:
        """Base point plus the whole crown above it must stay off the cells."""
        r = h * 0.30
        return all(self.free(x, y - h * k, r, limit) for k in (0.0, 0.35, 0.7, 1.0))

    def lane(self, cells):
        return [self.cell_img[c] for c in cells if c in self.cell_img]


def finish(img: Image.Image, scene: Scene, rng_np, grain=3.0) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), np.float32)
    g = rng_np.normal(0, grain, (H, W, 1)).astype(np.float32)
    g = np.asarray(Image.fromarray(np.clip(g[..., 0] * 8 + 128, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32)
    arr += ((g - 128.0) / 8.0)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def clearing_lift(img: Image.Image, scene: Scene, tone, strength) -> Image.Image:
    """Pale the combat floor (cleared ground / swept road) so orange warnings, teal anchors and markers keep
    luminance contrast; the border painting outside the cell footprints is untouched."""
    soft = np.asarray(scene.mask_img.filter(ImageFilter.GaussianBlur(34)), np.float32) / 255.0
    k = (np.clip(soft * 1.45, 0.0, 1.0) * strength)[..., None]
    arr = np.asarray(img.convert("RGB"), np.float32)
    arr = arr * (1.0 - k) + np.asarray(tone, np.float32)[None, None, :] * k
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def soft_layer(draw_fn, blur):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer, "RGBA"))
    return layer.filter(ImageFilter.GaussianBlur(blur)) if blur else layer


def comp(img, layer):
    return Image.alpha_composite(img, layer)


def polyline_soft(d, pts, color, width, jitter, rng, steps=10):
    """Wobbly hand-drawn polyline through (Chaikin-smoothed) points."""
    for _ in range(2):
        sm = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            sm += [(a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25), (a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75)]
        pts = sm + [pts[-1]]
    out = []
    for a, b in zip(pts, pts[1:]):
        for i in range(steps):
            t = i / steps
            out.append((a[0] + (b[0] - a[0]) * t + rng.uniform(-jitter, jitter),
                        a[1] + (b[1] - a[1]) * t + rng.uniform(-jitter, jitter)))
    out.append(pts[-1])
    d.line(out, fill=color, width=width, joint="curve")


# ---------------------------------------------------------------- RG06 雾痕林缘
FOREST_DARK = (53, 72, 63)
MOSS = (119, 133, 105)
OCHRE = (154, 121, 85)
LIME_STONE = (145, 144, 128)


def tree(d, x, y, h, rng, tone):
    bark = (92, 76, 60, 255)
    d.line([(x, y), (x + rng.uniform(-3, 3), y - h * 0.5)], fill=INK_SOFT, width=max(4, int(h * 0.09)))
    d.line([(x, y), (x + rng.uniform(-3, 3), y - h * 0.5)], fill=bark, width=max(2, int(h * 0.055)))
    cx, cy = x, y - h * 0.68
    for i in range(6):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(0, h * 0.20)
        rx = h * rng.uniform(0.20, 0.30)
        ry = rx * rng.uniform(0.78, 0.98)
        px, py = cx + math.cos(ang) * dist, cy + math.sin(ang) * dist * 0.7
        col = lerp(FOREST_DARK, MOSS, tone * rng.uniform(0.35, 1.0))
        d.ellipse([px - rx, py - ry, px + rx, py + ry], fill=col + (255,), outline=INK_FAINT, width=2)
    # lit crown highlight (warm light from upper-left)
    d.ellipse([cx - h * 0.18, cy - h * 0.24, cx + h * 0.02, cy - h * 0.08],
              fill=lerp(MOSS, (176, 176, 128), 0.55) + (120,))


def paint_rg06(scene: Scene) -> Image.Image:
    n = scene.np
    rng = scene.rng
    base_n = fbm(n, ((5, 1.0), (13, 0.6), (34, 0.3)))
    ground = blend_field(
        [MOSS, lerp(MOSS, OCHRE, 0.45), lerp(MOSS, (186, 180, 134), 0.40), FOREST_DARK],
        [0.9 + 0.0 * base_n, np.clip(base_n - 0.35, 0, 1) * 1.1, np.clip(0.75 - base_n, 0, 1) * 0.6 + scene.play * 0.9,
         np.clip(0.60 - scene.wide, 0, 1) ** 1.3 * 1.6])
    img = Image.fromarray(np.clip(ground, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # hazy sky (top band) behind the tree line
    sky = np.zeros((H, W, 4), np.uint8)
    for y in range(0, 300):
        t = y / 299.0
        col = lerp((210, 218, 200), (172, 190, 164), t ** 1.3)
        sky[y, :, :3] = col
        sky[y, :, 3] = int(255 * (1.0 - t ** 2.2))
    img = comp(img, Image.fromarray(sky, "RGBA"))

    # distant tree layers (low contrast, fog tinted)
    def far_trees(d):
        for layer, (base, hmin, hmax, tone, alpha) in enumerate(((176, 70, 120, 0.9, 120), (212, 90, 150, 0.65, 175))):
            x = -40
            while x < W + 40:
                tree(d, x, base + rng.uniform(-6, 6), rng.uniform(hmin, hmax), rng, tone)
                x += rng.uniform(34, 70)
    layer = soft_layer(far_trees, 0)
    fog_far = Image.new("RGBA", (W, H), (210, 220, 204, 0))
    arr = np.asarray(layer, np.float32)
    arr[..., :3] = arr[..., :3] * 0.55 + np.array([196, 208, 190], np.float32) * 0.45
    arr[..., 3] = arr[..., 3] * 0.72
    img = comp(img, Image.fromarray(arr.astype(np.uint8), "RGBA"))

    # mid fog bank across the horizon
    def fog_bank(d):
        for cx in range(-100, W + 100, 150):
            cy = 238 + rng.uniform(-14, 10)
            d.ellipse([cx - 220, cy - 28, cx + 220, cy + 34], fill=(226, 232, 220, 118))
    img = comp(img, soft_layer(fog_bank, 20))

    # worn animal trails that fork around the obstacle cluster: bold outside the cells, whisper inside
    north = scene.lane([(5, -1), (5, 0), (5, 1), (5, 2), (4, 3), (4, 4), (4, 5)])
    south = scene.lane([(3, 0), (3, 1), (2, 2), (2, 3), (2, 4), (2, 5)])
    fork_in = (scene.cell_img[(4, 0)][0] - 190, scene.cell_img[(4, 0)][1] - 28)
    spur_out_n = [(scene.cell_img[(5, 5)][0] + 120, scene.cell_img[(5, 5)][1] - 10), (scene.cell_img[(5, 5)][0] + 220, scene.cell_img[(5, 5)][1] + 70)]
    spur_out_s = [(scene.cell_img[(1, 6)][0] - 40, scene.cell_img[(1, 6)][1] + 110), (scene.cell_img[(1, 6)][0] - 140, scene.cell_img[(1, 6)][1] + 190)]

    def trails(d, strong):
        rr = random.Random(77)
        a = 150 if strong else 52
        dirt = lerp(OCHRE, (176, 148, 104), 0.5) + (a,)
        edge = (110, 88, 62, int(a * 0.8))
        for pts in ([fork_in] + north + spur_out_n, [fork_in] + south + spur_out_s):
            polyline_soft(d, pts, edge, 22, 3, rr)
            polyline_soft(d, pts, dirt, 14, 2.5, rr)
    outer = soft_layer(lambda d: trails(d, True), 3)
    ar = np.asarray(outer, np.float32)
    ar[..., 3] *= np.clip(1.15 - scene.near * 1.15, 0, 1)
    img = comp(img, Image.fromarray(ar.astype(np.uint8), "RGBA"))
    scene.post.append(soft_layer(lambda d: trails(d, False), 6))

    # grass tufts, ferns, small stones and mushrooms: borders only
    def small(d):
        for _ in range(900):
            x, y = rng.uniform(0, W), rng.uniform(150, H)
            if not scene.free(x, y, 16, 0.04):
                continue
            kind = rng.random()
            if kind < 0.62:
                tone = lerp(MOSS, FOREST_DARK, rng.uniform(0.1, 0.8)) + (210,)
                for k in range(4):
                    dx = rng.uniform(-9, 9)
                    d.line([(x, y), (x + dx, y - rng.uniform(8, 20))], fill=tone, width=2)
            elif kind < 0.82:
                rx, ry = rng.uniform(5, 13), rng.uniform(3, 7)
                d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=LIME_STONE + (230,), outline=INK_FAINT, width=1)
                d.ellipse([x - rx * 0.6, y - ry * 0.9, x + rx * 0.3, y - ry * 0.2], fill=(176, 174, 156, 190))
            elif kind < 0.92:
                d.line([(x, y), (x, y - 8)], fill=(222, 214, 190, 235), width=3)
                d.ellipse([x - 6, y - 14, x + 6, y - 5], fill=(170, 96, 72, 235), outline=INK_FAINT, width=1)
                d.ellipse([x - 2, y - 11, x, y - 9], fill=(238, 224, 200, 240))
            else:
                for k in range(5):
                    ang = math.radians(-90 + k * 36 - 72)
                    d.line([(x, y), (x + math.cos(ang) * 22, y + math.sin(ang) * 14)], fill=lerp(MOSS, FOREST_DARK, 0.4) + (230,), width=3)
    img = comp(img, soft_layer(small, 0))

    # near tree clusters at left / right / bottom borders and in the empty corner triangles
    def near_trees(d):
        spots = []
        for _ in range(900):
            x, y = rng.uniform(-30, W + 30), rng.uniform(210, H + 40)
            h0 = rng.uniform(120, 215)
            if scene.free_column(x, y + 30, h0 * (0.80 + (y / H) * 0.45)) and all(math.hypot(x - sx, y - sy) > 74 for sx, sy, _ in spots):
                spots.append((x, y, h0))
        spots.sort(key=lambda s: s[1])
        for x, y, h in spots[:46]:
            tree(d, x, y + 30, h * (0.80 + (y / H) * 0.45), rng, 0.62)
    img = comp(img, soft_layer(near_trees, 0))

    # drifting ground mist, kept away from the cells
    def mist(d):
        for _ in range(30):
            x, y = rng.uniform(-100, W + 100), rng.uniform(300, H + 40)
            rx, ry = rng.uniform(140, 300), rng.uniform(18, 38)
            d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=(228, 234, 222, 92))
    ml = soft_layer(mist, 26)
    ma = np.asarray(ml, np.float32)
    ma[..., 3] *= np.clip(1.0 - scene.near * 1.05, 0, 1)
    img = comp(img, Image.fromarray(ma.astype(np.uint8), "RGBA"))
    return img


# ---------------------------------------------------------------- RG08 炉灰荒径
ASH = (156, 146, 130)
SLAG = (98, 91, 84)
SOOT = (62, 56, 52)
BRICK = (132, 118, 104)
NEW_STONE = (176, 164, 142)
PLANK = (124, 94, 64)


def wall(d, x0, y0, x1, y1, rng, rows, tone=1.0, repair=0.10):
    d.rectangle([x0, y0, x1, y1], fill=lerp(BRICK, (110, 100, 92), 0.3) + (255,), outline=INK_SOFT, width=2)
    rh = (y1 - y0) / rows
    for r in range(rows):
        yy = y0 + r * rh
        x = x0 - rng.uniform(0, 30) * (r % 2)
        while x < x1:
            bw = rng.uniform(34, 62)
            xa, xb = max(x, x0), min(x + bw, x1)
            if xb - xa > 6:
                col = lerp(BRICK, (150, 138, 122), rng.uniform(0, 1) * tone * 0.7)
                if rng.random() < repair:
                    col = NEW_STONE
                d.rectangle([xa + 1, yy + 1, xb - 1, yy + rh - 1], fill=col + (255,), outline=INK_FAINT, width=1)
                if rng.random() < 0.18:
                    d.line([(xa + 4, yy + rh * 0.3), (xb - 6, yy + rh * 0.6)], fill=SOOT + (110,), width=2)
            x += bw
    d.rectangle([x0 - 4, y0 - 8, x1 + 4, y0 + 4], fill=(168, 156, 138, 255), outline=INK_SOFT, width=2)  # cap


def brace(d, x, y, length, tilt, rng):
    """Repair: plank brace with iron straps."""
    dx, dy = math.cos(tilt) * length, math.sin(tilt) * length
    d.line([(x, y), (x + dx, y + dy)], fill=INK_SOFT, width=11)
    d.line([(x, y), (x + dx, y + dy)], fill=PLANK + (255,), width=7)
    for t in (0.25, 0.75):
        px, py = x + dx * t, y + dy * t
        d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(70, 64, 58, 255))


def cart(d, x, y, s, rng):
    d.polygon([(x - 42 * s, y - 20 * s), (x + 44 * s, y - 26 * s), (x + 34 * s, y + 6 * s), (x - 34 * s, y + 8 * s)],
              fill=PLANK + (255,), outline=INK_SOFT)
    d.line([(x - 40 * s, y - 14 * s), (x + 40 * s, y - 18 * s)], fill=(160, 126, 90, 255), width=3)
    d.line([(x - 42 * s, y - 20 * s), (x - 78 * s, y - 36 * s)], fill=INK_SOFT, width=5)
    wx, wy, wr = x - 2 * s, y + 10 * s, 20 * s
    d.ellipse([wx - wr, wy - wr, wx + wr, wy + wr], fill=(98, 80, 60, 255), outline=INK_SOFT, width=3)
    d.ellipse([wx - wr * 0.7, wy - wr * 0.7, wx + wr * 0.7, wy + wr * 0.7], outline=(60, 52, 46, 255), width=2)
    for k in range(4):
        a = k * math.pi / 4
        d.line([(wx + math.cos(a) * wr * 0.7, wy + math.sin(a) * wr * 0.7),
                (wx - math.cos(a) * wr * 0.7, wy - math.sin(a) * wr * 0.7)], fill=(60, 52, 46, 255), width=2)
    for k in range(3):
        cx = x - 22 * s + k * 20 * s
        d.polygon([(cx, y - 24 * s), (cx + 10 * s, y - 34 * s), (cx + 20 * s, y - 22 * s)], fill=SLAG + (255,), outline=INK_SOFT)


def crate(d, x, y, s, rng):
    d.rectangle([x, y, x + 46 * s, y + 38 * s], fill=(142, 108, 72, 255), outline=INK_SOFT, width=2)
    d.line([(x, y + 19 * s), (x + 46 * s, y + 19 * s)], fill=(104, 78, 52, 255), width=3)
    d.line([(x, y), (x + 46 * s, y + 38 * s)], fill=(104, 78, 52, 255), width=3)
    d.rectangle([x - 3, y - 7 * s, x + 49 * s, y], fill=(172, 140, 98, 255), outline=INK_SOFT, width=1)


def ash_pile(d, x, y, rx, ry, rng):
    d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=lerp(SLAG, ASH, 0.25) + (240,))
    d.ellipse([x - rx * 0.75, y - ry * 0.95, x + rx * 0.35, y - ry * 0.25], fill=lerp(ASH, (196, 186, 170), 0.5) + (210,))
    for _ in range(int(rx / 6)):
        px, py = x + rng.uniform(-rx * 0.8, rx * 0.8), y + rng.uniform(-ry * 0.4, ry * 0.6)
        sr = rng.uniform(3, 7)
        d.polygon([(px - sr, py), (px, py - sr * 0.8), (px + sr, py - sr * 0.2), (px + sr * 0.5, py + sr * 0.7)],
                  fill=SOOT + (255,), outline=INK_FAINT)


def paint_rg08(scene: Scene) -> Image.Image:
    n = scene.np
    rng = scene.rng
    nz = fbm(n, ((4, 1.0), (11, 0.6), (30, 0.3)))
    ground = blend_field(
        [ASH, lerp(ASH, (176, 150, 112), 0.5), lerp(ASH, (190, 180, 164), 0.5), lerp(SLAG, SOOT, 0.4)],
        [0.9 + 0.0 * nz, np.clip(nz - 0.45, 0, 1) * 1.0, np.clip(0.60 - nz, 0, 1) * 0.5 + scene.play * 0.9,
         np.clip(0.55 - scene.wide, 0, 1) ** 1.2 * 1.3])
    img = Image.fromarray(np.clip(ground, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # smoky warm-grey sky and a hazy skyline of dead chimneys (dim ember glow stays far away and high)
    sky = np.zeros((H, W, 4), np.uint8)
    for y in range(0, 330):
        t = y / 329.0
        sky[y, :, :3] = lerp((206, 196, 182), (178, 166, 150), t ** 1.2)
        sky[y, :, 3] = int(255 * (1.0 - t ** 2.0))
    img = comp(img, Image.fromarray(sky, "RGBA"))

    def skyline(d):
        x = -20
        while x < W + 20:
            h = rng.uniform(30, 70)
            d.rectangle([x, 150 - h, x + rng.uniform(34, 70), 160], fill=(140, 130, 120, 140))
            if rng.random() < 0.34:
                cx = x + 18
                d.rectangle([cx, 80 - rng.uniform(0, 26), cx + 20, 160], fill=(118, 108, 100, 170))
            x += rng.uniform(50, 110)
    img = comp(img, soft_layer(skyline, 2))

    def glow(d):
        for cx in (330, 1020, 1400):
            d.ellipse([cx - 26, 72, cx + 26, 96], fill=(214, 150, 96, 90))
    img = comp(img, soft_layer(glow, 16))

    # rear service wall band and its repair work
    def back_wall(d):
        wall(d, -10, 146, W + 10, 236, rng, 4, repair=0.12)
        gap = (640, 760)           # collapsed section patched by timber and heaped rubble
        d.rectangle([gap[0], 138, gap[1], 244], fill=(166, 154, 138, 255))
        for _ in range(26):
            px, py = rng.uniform(gap[0], gap[1]), rng.uniform(190, 242)
            sr = rng.uniform(7, 18)
            d.polygon([(px - sr, py), (px - sr * 0.3, py - sr), (px + sr, py - sr * 0.4), (px + sr * 0.6, py + sr * 0.5)],
                      fill=lerp(BRICK, SLAG, rng.uniform(0, 0.6)) + (255,), outline=INK_FAINT, width=1)
        brace(d, gap[0] - 8, 150, 100, math.radians(62), rng)
        brace(d, gap[1] + 8, 150, 100, math.radians(118), rng)
        d.line([(gap[0] - 8, 146), (gap[1] + 8, 146)], fill=INK_SOFT, width=11)
        d.line([(gap[0] - 8, 146), (gap[1] + 8, 146)], fill=PLANK + (255,), width=7)
        for cx in (230, 1180, 1430):       # chalk tally / repair tags on the face
            for k in range(5):
                d.line([(cx + k * 8, 176), (cx + k * 8, 202)], fill=(226, 218, 200, 220), width=3)
            d.line([(cx - 4, 196), (cx + 38, 182)], fill=(226, 218, 200, 220), width=3)
    img = comp(img, soft_layer(back_wall, 0))

    # shadow and soot below the wall (still above the cells)
    def soot(d):
        d.rectangle([0, 232, W, 262], fill=(70, 62, 56, 70))
    sl = soft_layer(soot, 12)
    sa = np.asarray(sl, np.float32)
    sa[..., 3] *= np.clip(1.0 - scene.near * 1.2, 0, 1)
    img = comp(img, Image.fromarray(sa.astype(np.uint8), "RGBA"))

    # cart ruts through both flank lanes (strong outside the cells, faint inside)
    north = scene.lane([(5, -1), (5, 0), (5, 1), (5, 2), (4, 3), (4, 4), (4, 5)])
    south = scene.lane([(3, 0), (3, 1), (2, 2), (2, 3), (2, 4), (2, 5)])
    ent = (scene.cell_img[(4, 0)][0] - 190, scene.cell_img[(4, 0)][1] - 30)
    ext_n = [(scene.cell_img[(5, 5)][0] + 120, scene.cell_img[(5, 5)][1] - 6), (scene.cell_img[(5, 5)][0] + 230, scene.cell_img[(5, 5)][1] + 80)]
    ext_s = [(scene.cell_img[(1, 6)][0] - 40, scene.cell_img[(1, 6)][1] + 100), (scene.cell_img[(1, 6)][0] - 150, scene.cell_img[(1, 6)][1] + 170)]

    def ruts(d, alpha):
        rr = random.Random(88)
        for pts in ([ent] + north + ext_n, [ent] + south + ext_s):
            for off in (-10, 10):
                shifted = [(p[0] + off * 0.5, p[1] + off) for p in pts]
                polyline_soft(d, shifted, lerp(SLAG, SOOT, 0.4) + (alpha,), 6, 2.0, rr)
    ro = soft_layer(lambda d: ruts(d, 150), 2)
    ra = np.asarray(ro, np.float32)
    ra[..., 3] *= np.clip(1.15 - scene.near * 1.15, 0, 1)
    img = comp(img, Image.fromarray(ra.astype(np.uint8), "RGBA"))
    scene.post.append(soft_layer(lambda d: ruts(d, 56), 4))

    # ash drifts, slag, crates, carts, braces: borders only
    def clutter(d):
        for _ in range(60):
            x, y = rng.uniform(-30, W + 30), rng.uniform(260, H + 20)
            if scene.free(x, y, 70, 0.03):
                ash_pile(d, x, y, rng.uniform(34, 100), rng.uniform(12, 30), rng)
        for _ in range(300):
            x, y = rng.uniform(0, W), rng.uniform(250, H)
            if scene.free(x, y, 10, 0.03):
                sr = rng.uniform(3, 8)
                d.polygon([(x - sr, y), (x, y - sr), (x + sr, y - sr * 0.2), (x + sr * 0.4, y + sr * 0.7)],
                          fill=lerp(SOOT, SLAG, rng.random()) + (240,), outline=INK_FAINT)
        placed = []
        for _ in range(500):
            x, y = rng.uniform(30, W - 30), rng.uniform(280, H - 20)
            if scene.free(x, y, 70, 0.03) and all(math.hypot(x - a, y - b) > 150 for a, b in placed) and len(placed) < 12:
                placed.append((x, y))
        for i, (x, y) in enumerate(sorted(placed, key=lambda p: p[1])):
            if i % 3 == 0:
                cart(d, x, y, rng.uniform(0.9, 1.2), rng)
            elif i % 3 == 1:
                crate(d, x, y, rng.uniform(0.9, 1.3), rng)
                crate(d, x + 54, y + 4, rng.uniform(0.8, 1.0), rng)
            else:
                brace(d, x, y, 90, math.radians(rng.choice([-62, 118, 70])), rng)
                brace(d, x + 60, y, 90, math.radians(rng.choice([-118, 62])), rng)
    img = comp(img, soft_layer(clutter, 0))

    # low side wall stubs in the empty corner triangles
    def side_walls(d):
        for x0, y0, x1, y1 in ((-10, 330, 200, 392), (1360, 640, W + 10, 706), (-10, 790, 260, 850)):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if scene.free(cx, cy, 40, 0.03):
                wall(d, x0, y0, x1, y1, rng, 3, repair=0.16)
        # forbid anything over the cells afterwards
    img = comp(img, soft_layer(side_walls, 0))

    # drifting furnace smoke / ash haze
    def haze(d):
        for _ in range(26):
            x, y = rng.uniform(-100, W + 100), rng.uniform(260, H)
            rx, ry = rng.uniform(140, 300), rng.uniform(16, 34)
            d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=(200, 192, 180, 78))
    hz = soft_layer(haze, 24)
    ha = np.asarray(hz, np.float32)
    ha[..., 3] *= np.clip(1.0 - scene.near * 1.05, 0, 1)
    img = comp(img, Image.fromarray(ha.astype(np.uint8), "RGBA"))
    return img


PAINTERS = {"RG06": paint_rg06, "RG08": paint_rg08}


# ---------------------------------------------------------------- measurements
def luminance(arr):
    return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]


def contrast(a, b):
    def lin(c):
        c = c / 255.0
        return np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    la = 0.2126 * lin(a[0]) + 0.7152 * lin(a[1]) + 0.0722 * lin(a[2])
    lb = 0.2126 * lin(b[0]) + 0.7152 * lin(b[1]) + 0.0722 * lin(b[2])
    hi, lo = max(la, lb), min(la, lb)
    return float((hi + 0.05) / (lo + 0.05))


def measure(img: Image.Image, scene: Scene) -> dict:
    arr = np.asarray(img, np.float32)
    inside = scene.play > 0.5
    outside = scene.near < 0.02
    lum = luminance(arr)
    floor = arr[inside].mean(axis=0)
    gy, gx = np.gradient(lum)
    grad = np.hypot(gx, gy)
    ks = {"orange_warning": (232, 140, 60), "cyan_anchor": (60, 125, 140), "player_marker": (74, 163, 154),
          "enemy_marker": (204, 96, 74), "grid_line_light": (236, 228, 204), "ink": (48, 42, 38)}
    return {
        "floor_mean_rgb": [round(float(v), 1) for v in floor],
        "floor_luma_mean": round(float(lum[inside].mean()), 1),
        "floor_luma_std": round(float(lum[inside].std()), 2),
        "floor_gradient_mean": round(float(grad[inside].mean()), 2),
        "border_gradient_mean": round(float(grad[outside].mean()), 2),
        "border_to_floor_detail_ratio": round(float(grad[outside].mean() / max(0.01, grad[inside].mean())), 2),
        "contrast_vs_floor_mean": {k: round(contrast(v, floor), 2) for k, v in ks.items()},
    }


# ---------------------------------------------------------------- 1280x720 preview with the real projection
def preview(img: Image.Image, scene: Scene, out: Path, label: str, font_path: str | None) -> dict:
    win = (1280, 720)
    k = 0.8                                  # real window: board node 1041x669 drawn at 1280/1600
    origin = (82, 78)                        # board node origin measured on the 1280x720 contact sheet
    canvas = Image.new("RGB", win, (20, 17, 14))
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle([origin[0] - 2, origin[1] - 2, origin[0] + BOARD_NODE[0] * k + 2, origin[1] + BOARD_NODE[1] * k + 2], fill=(34, 28, 24), outline=(60, 50, 42))
    art = img.resize((int(round(ART_RECT[0] * k)), int(round(ART_RECT[1] * k))), Image.LANCZOS)
    canvas.paste(art, (int(origin[0] + ART_INSET * k), int(origin[1] + ART_INSET * k)))
    d = ImageDraw.Draw(canvas, "RGBA")

    def bp(p):
        return (origin[0] + p[0] * k, origin[1] + p[1] * k)
    try:
        font = ImageFont.truetype(font_path, 11) if font_path else ImageFont.load_default()
        big = ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()
    except OSError:
        font = big = ImageFont.load_default()
    rad = scene.sc * 0.96 * k
    warn = {(4, 3), (4, 4), (3, 2), (2, 3)}
    for key, p in scene.pos.items():
        poly = [bp(q) for q in hex_poly(p, scene.sc * 0.96)]
        t = scene.cells[key]
        if t == "HIGH_OBSTACLE":
            d.polygon(poly, fill=(40, 36, 32, 170))
            c = bp(p)
            d.rectangle([c[0] - 13, c[1] - 30, c[0] + 13, c[1] + 6], fill=(78, 72, 66, 255), outline=(30, 26, 24, 255), width=2)
        elif key in warn:
            d.polygon(poly, fill=(232, 140, 60, 90))
        d.line(poly + [poly[0]], fill=(70, 62, 52, 120), width=1)
        if key in warn:
            d.line(poly + [poly[0]], fill=(232, 140, 60, 255), width=2)
    occupied = {tuple(a["pos"]): a for a in scene.anchor["actors"]}
    for pos, a in occupied.items():
        c = bp(scene.pos[pos])
        col = (74, 163, 154, 255) if a["side"] == "player" else (204, 96, 74, 255)
        d.ellipse([c[0] - 9, c[1] - 7, c[0] + 9, c[1] + 7], fill=col, outline=(20, 17, 14, 255), width=2)
        d.rectangle([c[0] - 6, c[1] - 24, c[0] + 6, c[1] - 6], fill=col, outline=(20, 17, 14, 255), width=1)
    d.text((origin[0], 18), f"{label} · DUAL_FLANK · 79格 · 1280×720 实锚投影预览", fill=(240, 224, 190), font=big)
    d.text((origin[0], 44), "叠加仅为核对：格线/障碍/占位按真存档与 hex_board 侧视投影；橙格为示意预警；非游戏截图", fill=(190, 176, 150), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", compress_level=6)
    return {"window": list(win), "board_origin": list(origin), "scale": k}


def find_font():
    for p in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"):
        if Path(p).is_file():
            return p
    return None


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    here = Path(__file__).resolve()
    p06 = here.parents[2] / "原型" / "P06_首章"
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out", type=Path, default=p06 / "assets" / "dual_flank")
    ap.add_argument("--preview-out", type=Path, default=p06 / "evidence" / "issue13-rg06-rg08")
    ap.add_argument("--regions", nargs="*", default=list(REGIONS))
    args = ap.parse_args(argv)
    started = time.time()
    anchors = json.loads((args.source_root / "anchors.json").read_bytes())
    report = {"recipe": RECIPE_VERSION, "script": str(here), "script_sha256": sha256_file(here),
              "python": sys.version.split()[0], "numpy": np.__version__, "pillow": Image.__version__ if hasattr(Image, "__version__") else "",
              "image_size": [W, H], "board_node": list(BOARD_NODE), "art_rect": list(ART_RECT), "regions": {}}
    args.out.mkdir(parents=True, exist_ok=True)
    font = find_font()
    for region in args.regions:
        t0 = time.time()
        meta = REGIONS[region]
        anchor = load_anchor(args.source_root, region, anchors)
        scene = Scene(anchor, meta["seed"])
        img = PAINTERS[region](scene)
        img = clearing_lift(img, scene, *meta["lift"]).convert("RGBA")
        for layer in scene.post:
            img = comp(img, layer)
        final = finish(img, scene, np.random.default_rng(meta["seed"] + 1))
        png = args.out / meta["file"]
        final.save(png, "PNG", compress_level=6)
        prev = args.preview_out / f"{meta['file'].replace('_ink.png', '')}_1280x720_preview.png"
        pinfo = preview(final, scene, prev, f"{region} {meta['name']}", font)
        report["regions"][region] = {
            "name": meta["name"], "seed": meta["seed"], "anchor": {k: anchor[k] for k in ("site", "encounter", "version", "game_id", "board_id", "save", "save_sha256")},
            "cells": len(anchor["cells"]), "terrain": {t: sum(1 for c in anchor["cells"] if c["terrain_id"] == t) for t in sorted({c["terrain_id"] for c in anchor["cells"]})},
            "obstacle_cells": [[c["q"], c["r"]] for c in anchor["cells"] if c["terrain_id"] != "GROUND"],
            "actors": [{"id": a["id"], "side": a["side"], "pos": list(a["pos"])} for a in anchor["actors"]],
            "layout_scale": round(scene.sc, 4), "background": {"path": str(png), "size": list(final.size), "sha256": sha256_file(png), "bytes": png.stat().st_size},
            "preview": {"path": str(prev), "sha256": sha256_file(prev), **pinfo},
            "measure": measure(final, scene), "seconds": round(time.time() - t0, 2),
        }
    report["seconds_total"] = round(time.time() - started, 2)
    args.preview_out.mkdir(parents=True, exist_ok=True)
    (args.preview_out / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({r: report["regions"][r]["background"]["sha256"] for r in report["regions"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

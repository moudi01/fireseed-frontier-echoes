"""Deterministically paint the P04B warm ink-and-wash FORGE_CROSSING backdrop (1600x900).

100% local procedural picture-book ink & wash (zero paid generation, reproducible).
Designed for RG05 · G · 铸律工场 (FORGE_CROSSING, 90 cells):
  - Rear horizon ONLY carries muted warm amber forge-kiln glow inside furnace arches,
    flanked by weathered limestone kiln chimneys and iron foundry gantries.
  - Center combat floor is calm, cool-warm desaturated slate-limestone (low texture density,
    NO orange/red floor glow!) so orange MG04-A/C warning hexes, [1,4]/[3,4] bronze floor
    anchors, MG04, EN04, and EN17 stay high-contrast and readable at 1280x720.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


W, H = 1600, 900
INK = (48, 42, 38, 255)
INK_SOFT = (74, 66, 60, 205)
INK_FAINT = (104, 96, 88, 125)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lerp_color(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(len(c1)))


def paint_backdrop(out_path: Path) -> dict:
    rng = random.Random(2026112604)
    img = Image.new("RGBA", (W, H), (198, 192, 182, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. Warm smoky foundry sky (top 0..240px)
    sky_top = (196, 188, 178, 255)
    sky_mid = (212, 200, 186, 255)
    sky_hor = (192, 180, 168, 255)
    for y in range(245):
        t = y / 244.0
        col = lerp_color(sky_top, sky_mid, t * 1.4) if t < 0.6 else lerp_color(sky_mid, sky_hor, (t - 0.6) / 0.4)
        draw.line([(0, y), (W, y)], fill=col)

    # Soft kiln smoke plumes in upper sky (RGB matched with alpha=0 -> zero dark halo)
    smoke = Image.new("RGBA", (W, H), (222, 214, 204, 0))
    sd = ImageDraw.Draw(smoke, "RGBA")
    for cx, cy, rx, ry in [(340, 48, 180, 26), (920, 40, 240, 24), (1280, 56, 200, 26)]:
        sd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(228, 220, 210, 95))
    smoke = smoke.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, smoke)
    draw = ImageDraw.Draw(img, "RGBA")

    # 2. Distant foundry ridge & heavy stone kiln silhouettes (rear horizon)
    far_ridge = [(0, 215)]
    for x in range(0, W + 40, 40):
        h = 158 + int(16 * math.sin(x * 0.005) + 10 * math.cos(x * 0.013))
        far_ridge.append((x, h))
    far_ridge += [(W, 245), (0, 245)]
    draw.polygon(far_ridge, fill=(134, 128, 122, 235))

    # Rear kiln chimneys & foundry gable silhouettes
    for kx, ky, kw, kh in [(270, 74, 58, 170), (540, 96, 46, 148), (1190, 68, 66, 176)]:
        draw.polygon([(kx, ky + kh), (kx + 8, ky), (kx + kw - 8, ky), (kx + kw, ky + kh)],
                     fill=(108, 102, 96, 255), outline=INK_SOFT)
        draw.rectangle([kx + 2, ky - 8, kx + kw - 2, ky + 6], fill=(128, 120, 112, 255), outline=INK_SOFT)

    # 3. Rear Foundry Wall & Twin Recessed Furnace Arches (forge fire stays STRICTLY inside rear arches!)
    wall_top = [(0, 252), (240, 236), (620, 228), (980, 228), (1360, 238), (W, 254)]
    draw.polygon(wall_top + [(W, 286), (0, 286)], fill=(122, 116, 108, 255))

    # Recessed forge furnace arches (muted warm amber glow kept strictly in rear wall)
    forge_glow = Image.new("RGBA", (W, H), (228, 138, 64, 0))
    fgd = ImageDraw.Draw(forge_glow, "RGBA")
    for ax in (410, 800, 1090):
        # Outer stone arch frame
        draw.rectangle([ax - 58, 162, ax + 58, 246], fill=(104, 98, 92, 255), outline=INK, width=2)
        draw.pieslice([ax - 44, 172, ax + 44, 248], start=180, end=360, fill=(76, 56, 46, 255), outline=INK, width=2)
        draw.rectangle([ax - 44, 208, ax + 44, 246], fill=(76, 56, 46, 255), outline=INK, width=1)
        # Warm forge ember core strictly inside furnace mouth
        draw.pieslice([ax - 30, 192, ax + 30, 246], start=180, end=360, fill=(214, 128, 58, 220))
        draw.rectangle([ax - 30, 218, ax + 30, 244], fill=(228, 152, 74, 225))
        fgd.ellipse([ax - 48, 184, ax + 48, 252], fill=(228, 138, 64, 72))
    forge_glow = forge_glow.filter(ImageFilter.GaussianBlur(12))
    img = Image.alpha_composite(img, forge_glow)
    draw = ImageDraw.Draw(img, "RGBA")

    # Weathered masonry blocks along rear foundry parapet
    for i in range(28):
        bx = i * 58 - 8
        if any(abs(bx + 26 - ax) < 62 for ax in (410, 800, 1090)):
            continue
        by = 224 + int(20 * ((bx - 800) / 820.0) ** 2)
        bw = 54 + rng.randint(-4, 4)
        bh = 22 + rng.randint(-2, 4)
        shade = rng.choice([(136, 130, 122, 255), (124, 118, 110, 255), (148, 140, 130, 255)])
        draw.rectangle([bx, by, bx + bw, by + bh], fill=shade, outline=INK_SOFT, width=2)

    # 4. Main Combat Floor — calm, cool-warm desaturated slate-limestone (HIGH contrast for orange warnings!)
    floor_poly = [(0, 272), (240, 254), (620, 246), (980, 246), (1360, 256), (W, 274), (W, H), (0, H)]
    draw.polygon(floor_poly, fill=(198, 192, 182, 255))
    draw.line(floor_poly[:6], fill=INK_SOFT, width=2)

    # Gentle sunlit neutral center wash (RGB matched with alpha=0 -> zero dark halo, zero orange cast)
    wash = Image.new("RGBA", (W, H), (214, 208, 198, 0))
    wd = ImageDraw.Draw(wash, "RGBA")
    wd.ellipse([180, 285, 1420, 825], fill=(214, 208, 198, 125))
    wd.ellipse([360, 355, 1240, 745], fill=(222, 216, 206, 95))
    wash = wash.filter(ImageFilter.GaussianBlur(46))
    img = Image.alpha_composite(img, wash)
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle inlaid foundry stone slabs only near outer perimeter
    for fx, fy, fw, fh in [(150, 298, 72, 20), (1370, 302, 76, 20), (760, 262, 82, 20)]:
        draw.rectangle([fx, fy, fx + fw, fy + fh], fill=(184, 178, 168, 145), outline=INK_FAINT, width=1)

    # Very light stone grain (RGB matched with alpha=0)
    grain = Image.new("RGBA", (W, H), (202, 196, 186, 0))
    gd = ImageDraw.Draw(grain, "RGBA")
    for _ in range(600):
        gx = rng.randint(0, W - 1)
        gy = rng.randint(270, H - 1)
        gr = rng.randint(14, 38)
        c = (188, 182, 172, 18) if rng.random() < 0.5 else (222, 216, 206, 18)
        gd.ellipse([gx - gr, gy - gr // 2, gx + gr, gy + gr // 2], fill=c)
    grain = grain.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, grain)
    draw = ImageDraw.Draw(img, "RGBA")

    # 5. Faceted basalt/slag foreground corner blocks (bottom-left & bottom-right only)
    fg_left = [(0, 752), (88, 780), (186, 826), (318, 868), (408, H), (0, H)]
    draw.polygon(fg_left, fill=(102, 98, 94, 255), outline=INK)
    draw.polygon([(0, 778), (86, 810), (180, 854), (284, H), (0, H)], fill=(76, 72, 68, 255), outline=INK_SOFT)

    fg_right = [(W, 756), (1508, 784), (1412, 830), (1280, 872), (1192, H), (W, H)]
    draw.polygon(fg_right, fill=(102, 98, 94, 255), outline=INK)
    draw.polygon([(W, 782), (1500, 814), (1408, 856), (1308, H), (W, H)], fill=(76, 72, 68, 255), outline=INK_SOFT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, format="PNG", optimize=True)
    return {
        "path": str(out_path),
        "size": [W, H],
        "bytes": out_path.stat().st_size,
        "sha256": sha256_file(out_path),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--report", default="")
    args = p.parse_args()
    info = paint_backdrop(Path(args.out))
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FORGE_CROSSING_BACKDROP_OK:", json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()

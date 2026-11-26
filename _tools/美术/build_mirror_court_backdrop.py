"""Deterministically paint the P04B warm ink-and-wash MIRROR_COURT backdrop (1600x900).

100% local procedural picture-book ink & wash (zero paid generation, reproducible).
Matches the palette, horizon framing, low-texture center courtyard, and orthographic
board readability of assets/fortress/keep_ink_court.png.
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
INK = (54, 45, 38, 255)
INK_SOFT = (74, 64, 54, 210)
INK_FAINT = (96, 86, 74, 130)


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
    rng = random.Random(20261126)
    img = Image.new("RGBA", (W, H), (222, 206, 184, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. Warm pale sky + distant mist gradient (top 0..240px)
    sky_top = (224, 216, 202, 255)
    sky_mid = (232, 222, 204, 255)
    sky_hor = (212, 206, 192, 255)
    for y in range(260):
        t = y / 259.0
        col = lerp_color(sky_top, sky_mid, t * 1.4) if t < 0.6 else lerp_color(sky_mid, sky_hor, (t - 0.6) / 0.4)
        draw.line([(0, y), (W, y)], fill=col)

    # Soft cloud wisps in upper sky (RGB matched to cloud tone with alpha=0 so GaussianBlur has zero dark halo)
    cloud_layer = Image.new("RGBA", (W, H), (244, 237, 224, 0))
    cd = ImageDraw.Draw(cloud_layer, "RGBA")
    for cx, cy, rx, ry in [(260, 58, 210, 24), (720, 42, 260, 22), (1240, 66, 230, 26), (980, 94, 180, 18)]:
        cd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(246, 240, 228, 105))
    cloud_layer = cloud_layer.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, cloud_layer)
    draw = ImageDraw.Draw(img, "RGBA")

    # 2. Distant Echo Forest ridge & low-frequency tree silhouettes (warm slate-sage & limestone grey)
    far_ridge = [(0, 220)]
    for x in range(0, W + 32, 32):
        h = 148 + int(22 * math.sin(x * 0.0045) + 12 * math.cos(x * 0.011 + 0.7))
        far_ridge.append((x, h))
    far_ridge += [(W, 250), (0, 250)]
    draw.polygon(far_ridge, fill=(148, 152, 140, 235))

    # Mid-distance Echo Forest canopy silhouettes (low-frequency rounded clusters)
    mid_canopy = [(0, 260)]
    for x in range(0, W + 20, 20):
        arch_gap = max(0.0, 1.0 - abs(x - 1030) / 185.0)
        canopy_bump = 10 * abs(math.sin(x * 0.038))
        base_y = 176 + int(16 * math.sin(x * 0.009 + 1.2) - canopy_bump + 32 * arch_gap)
        mid_canopy.append((x, base_y))
    mid_canopy += [(W, 275), (0, 275)]
    draw.polygon(mid_canopy, fill=(112, 118, 106, 242))
    draw.line(mid_canopy[1:-2], fill=(82, 86, 76, 170), width=2)

    # Rear-only atmospheric mist band (RGB matched with alpha=0, strictly in rear horizon)
    mist = Image.new("RGBA", (W, H), (228, 222, 210, 0))
    md = ImageDraw.Draw(mist, "RGBA")
    for y in range(155, 252):
        alpha = int(78 * math.sin(math.pi * (y - 155) / 97.0))
        md.line([(0, y), (W, y)], fill=(228, 222, 210, alpha))
    mist = mist.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, mist)
    draw = ImageDraw.Draw(img, "RGBA")

    # 3. Mid-rear horizon stone wall & Old Mirror Dais (旧镜台) + Stone Road (石路)
    # Curved low courtyard boundary wall along y ~ 205..265
    wall_top = [
        (0, 248), (110, 230), (240, 220), (410, 214), (620, 210),
        (820, 210), (1190, 212), (1380, 222), (1510, 236), (W, 252),
    ]
    wall_poly = wall_top + [(W, 286), (1350, 270), (800, 260), (240, 268), (0, 290)]
    draw.polygon(wall_poly, fill=(138, 128, 112, 255))

    # Individual weathered limestone courses along back wall
    for i in range(28):
        bx = i * 58 - 10
        if 890 <= bx <= 1130:
            continue  # Leave opening for Old Mirror Dais & Stone Road
        by = 214 + int(22 * ((bx - 760) / 820.0) ** 2)
        bw = 54 + rng.randint(-4, 4)
        bh = 24 + rng.randint(-3, 5)
        shade = rng.choice([(148, 138, 121, 255), (134, 124, 108, 255), (160, 149, 130, 255)])
        draw.rectangle([bx, by, bx + bw, by + bh], fill=shade, outline=INK_SOFT, width=2)
        draw.rectangle([bx + 4, by + bh, bx + bw - 2, by + bh + 20], fill=(116, 108, 94, 255), outline=INK_SOFT, width=2)

    # Old Stone Road (石路) winding gently from behind the Mirror Dais into distant forest
    road_pts = [(970, 246), (1010, 210), (1055, 192), (1095, 198), (1065, 222), (1070, 248)]
    draw.polygon(road_pts, fill=(196, 182, 158, 255), outline=INK_FAINT)

    # Old Mirror Dais (旧镜台) landmark on upper-right-center (x ~ 920..1130, y ~ 95..258)
    # Stepped limestone base
    draw.rectangle([905, 236, 1145, 260], fill=(154, 143, 124, 255), outline=INK, width=2)
    draw.rectangle([925, 220, 1125, 238], fill=(168, 157, 138, 255), outline=INK, width=2)
    # Twin carved stone mirror pillars
    for px in (938, 1074):
        draw.rectangle([px, 122, px + 38, 222], fill=(138, 128, 112, 255), outline=INK, width=2)
        draw.rectangle([px - 6, 112, px + 44, 124], fill=(166, 154, 134, 255), outline=INK, width=2)
        # Stone joints
        for jy in (148, 174, 198):
            draw.line([(px + 2, jy), (px + 36, jy)], fill=INK_SOFT, width=2)
    # Fractured bronze mirror arch & matte pale silver-slate mirror plate (low contrast, non-distracting)
    draw.arc([952, 86, 1098, 196], start=180, end=360, fill=(112, 92, 66, 255), width=12)
    draw.pieslice([964, 98, 1086, 206], start=180, end=360, fill=(168, 174, 172, 215), outline=INK_SOFT, width=2)
    draw.rectangle([964, 150, 1086, 220], fill=(164, 170, 168, 205), outline=INK_SOFT, width=2)
    # Subtle fracture lines on old mirror face
    draw.line([(1012, 116), (1034, 154), (1018, 192)], fill=(96, 100, 98, 180), width=2)
    draw.line([(1034, 154), (1068, 170)], fill=(96, 100, 98, 150), width=1)

    # Secondary weathered bronze lantern post on left-center horizon (echoing keep_ink_court balance)
    draw.rectangle([504, 216, 540, 242], fill=(152, 141, 122, 255), outline=INK, width=2)
    draw.rectangle([518, 128, 526, 218], fill=(92, 78, 60, 255), outline=INK, width=1)
    draw.rectangle([514, 134, 544, 140], fill=(92, 78, 60, 255), outline=INK, width=1)
    draw.polygon([(534, 140), (546, 140), (543, 160), (537, 160)], fill=(224, 182, 114, 235), outline=INK)

    # 4. Main Combat Courtyard — calm, warm, LOW-TEXTURE-DENSITY limestone/parchment wash (y ~ 256..860)
    court_poly = [
        (0, 286), (220, 266), (560, 256), (1040, 256), (1380, 268), (W, 288),
        (W, H), (0, H),
    ]
    draw.polygon(court_poly, fill=(214, 197, 171, 255))

    # Gentle warm sunlit center wash (RGB matched with alpha=0 so GaussianBlur produces zero dark ring)
    wash = Image.new("RGBA", (W, H), (232, 218, 194, 0))
    wd = ImageDraw.Draw(wash, "RGBA")
    wd.ellipse([160, 285, 1440, 825], fill=(230, 215, 190, 120))
    wd.ellipse([340, 350, 1260, 745], fill=(236, 222, 198, 95))
    wash = wash.filter(ImageFilter.GaussianBlur(48))
    img = Image.alpha_composite(img, wash)
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle inlaid limestone flagstones ONLY near outer perimeter & approach road (center stays clean!)
    for fx, fy, fw, fh in [
        (955, 266, 78, 22), (1040, 270, 68, 20), (920, 292, 86, 22),
        (1015, 295, 76, 20), (140, 310, 64, 18), (1390, 316, 70, 18),
    ]:
        draw.rectangle([fx, fy, fx + fw, fy + fh], fill=(204, 188, 162, 145), outline=INK_FAINT, width=1)

    # Very light watercolor paper grain (RGB matched with alpha=0 -> zero dark outlines)
    grain = Image.new("RGBA", (W, H), (218, 202, 176, 0))
    gd = ImageDraw.Draw(grain, "RGBA")
    for _ in range(700):
        gx = rng.randint(0, W - 1)
        gy = rng.randint(268, H - 1)
        gr = rng.randint(14, 42)
        c = (204, 187, 160, 22) if rng.random() < 0.5 else (238, 226, 204, 22)
        gd.ellipse([gx - gr, gy - gr // 2, gx + gr, gy + gr // 2], fill=c)
    grain = grain.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, grain)
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle warm dry grass tufts tucked strictly along back wall base
    for tx in (125, 275, 430, 665, 860, 1185, 1345, 1485):
        ty = 262 + int(18 * ((tx - 780) / 800.0) ** 2)
        for dx, dy in [(-10, -10), (-4, -14), (2, -12), (9, -9)]:
            draw.line([(tx, ty), (tx + dx, ty + dy)], fill=(158, 128, 72, 210), width=2)

    # 5. Faceted stepped foreground corner rocks (bottom-left and bottom-right only, clear of board & HUD)
    fg_left = [(0, 748), (78, 772), (125, 804), (195, 824), (265, 858), (345, 876), (415, H), (0, H)]
    draw.polygon(fg_left, fill=(116, 108, 95, 255), outline=INK)
    draw.polygon([(0, 774), (92, 806), (175, 848), (290, H), (0, H)], fill=(88, 82, 73, 255), outline=INK_SOFT)

    fg_right = [(W, 752), (1515, 778), (1455, 810), (1380, 832), (1305, 864), (1225, 880), (1180, H), (W, H)]
    draw.polygon(fg_right, fill=(116, 108, 95, 255), outline=INK)
    draw.polygon([(W, 780), (1495, 814), (1410, 854), (1305, H), (W, H)], fill=(88, 82, 73, 255), outline=INK_SOFT)

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
    print("MIRROR_COURT_BACKDROP_OK:", json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()

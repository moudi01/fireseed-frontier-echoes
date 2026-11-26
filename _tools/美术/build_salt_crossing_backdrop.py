"""Deterministically paint the P04B warm ink-and-wash SALT_CROSSING backdrop (1600x900).

100% local procedural picture-book ink & wash (zero paid generation, reproducible).
Designed for RG04 · 沉息湖区 · 盐渡 (SALT_CROSSING, 63 cells):
  - Rear horizon: low-frequency silent salt-lake ridge, pale lake mist (rear only),
    weathered timber ferry pier (盐渡旧栈桥) & salt-crust stone bell-marker.
  - Center combat area: calm, low-texture-density pale salt-limestone banks & subtle
    shallow ford band so hex grid lines, orange warning hexes, MG03, and both guards
    (EN06 / EN15) read with maximum clarity at 1280x720.
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
INK = (52, 46, 42, 255)
INK_SOFT = (78, 70, 62, 200)
INK_FAINT = (108, 98, 86, 125)


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
    rng = random.Random(2026112603)
    img = Image.new("RGBA", (W, H), (222, 214, 198, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. Warm pale salt-mist sky (top 0..235px)
    sky_top = (218, 218, 212, 255)
    sky_mid = (232, 226, 212, 255)
    sky_hor = (214, 216, 210, 255)
    for y in range(245):
        t = y / 244.0
        col = lerp_color(sky_top, sky_mid, t * 1.4) if t < 0.6 else lerp_color(sky_mid, sky_hor, (t - 0.6) / 0.4)
        draw.line([(0, y), (W, y)], fill=col)

    # Soft clouds (RGB matched with alpha=0 -> zero dark halo)
    cloud = Image.new("RGBA", (W, H), (242, 238, 228, 0))
    cd = ImageDraw.Draw(cloud, "RGBA")
    for cx, cy, rx, ry in [(300, 52, 230, 20), (820, 44, 280, 22), (1320, 62, 220, 20)]:
        cd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(244, 240, 230, 95))
    cloud = cloud.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, cloud)
    draw = ImageDraw.Draw(img, "RGBA")

    # 2. Distant Silent Lake (沉息湖) horizon & pale slate salt-flats
    far_ridge = [(0, 205)]
    for x in range(0, W + 32, 32):
        h = 148 + int(16 * math.sin(x * 0.004 + 0.5) + 9 * math.cos(x * 0.012))
        far_ridge.append((x, h))
    far_ridge += [(W, 235), (0, 235)]
    draw.polygon(far_ridge, fill=(154, 162, 158, 230))

    # Calm distant lake band behind the north salt-bank (y ~ 185..248)
    draw.rectangle([0, 185, W, 250], fill=(166, 178, 174, 255))
    for rx, ry, rw in [(160, 206, 140), (540, 214, 180), (1120, 204, 160), (1380, 218, 120)]:
        draw.line([(rx, ry), (rx + rw, ry)], fill=(208, 216, 210, 150), width=2)

    # Rear-only lake mist band (strictly in rear horizon, never touching combat board)
    mist = Image.new("RGBA", (W, H), (226, 224, 216, 0))
    md = ImageDraw.Draw(mist, "RGBA")
    for y in range(150, 242):
        alpha = int(84 * math.sin(math.pi * (y - 150) / 92.0))
        md.line([(0, y), (W, y)], fill=(226, 224, 216, alpha))
    mist = mist.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, mist)
    draw = ImageDraw.Draw(img, "RGBA")

    # 3. Mid-rear Landmarks: Weathered Timber Salt-Ferry Pier (盐渡旧栈桥) & Salt-Crust Bell-Marker
    # Left-rear weathered pier extending out into the distant lake (x ~ 220..520, y ~ 168..252)
    draw.polygon([(220, 242), (495, 210), (518, 220), (255, 256)], fill=(128, 108, 86, 255), outline=INK_SOFT)
    for px in (250, 310, 370, 430, 488):
        py = 246 - int((px - 250) * 0.12)
        draw.rectangle([px, py - 38, px + 11, py + 12], fill=(94, 78, 62, 255), outline=INK, width=1)
        # Pale salt crust at water base of piling
        draw.rectangle([px - 2, py + 2, px + 13, py + 10], fill=(224, 218, 204, 220))

    # Right-rear Salt-Crust Bell-Marker Stele (沉息石标, x ~ 1060..1195, y ~ 118..252)
    draw.rectangle([1060, 232, 1205, 254], fill=(166, 158, 144, 255), outline=INK, width=2)
    draw.rectangle([1082, 216, 1183, 234], fill=(182, 174, 158, 255), outline=INK, width=2)
    draw.rectangle([1114, 126, 1152, 218], fill=(154, 146, 132, 255), outline=INK, width=2)
    draw.polygon([(1106, 126), (1133, 106), (1160, 126)], fill=(176, 168, 152, 255), outline=INK)
    # Small tarnished bell hanging from side bracket
    draw.line([(1152, 148), (1178, 148)], fill=INK, width=3)
    draw.polygon([(1170, 150), (1182, 150), (1185, 166), (1167, 166)], fill=(158, 134, 92, 255), outline=INK)

    # Low salt-crust north embankment wall framing the top of the crossing (y ~ 236..270)
    bank_pts = [(0, 262), (240, 246), (620, 240), (980, 240), (1360, 248), (W, 264), (W, H), (0, H)]
    draw.polygon(bank_pts, fill=(216, 206, 186, 255))
    draw.line(bank_pts[:6], fill=INK_SOFT, width=2)

    # Salt-crust rim stones along north shoreline
    for i in range(24):
        sx = i * 68 + rng.randint(-6, 6)
        sy = 240 + int(18 * ((sx - 800) / 820.0) ** 2)
        sw = 52 + rng.randint(-6, 8)
        sh = 16 + rng.randint(-2, 4)
        shade = rng.choice([(198, 190, 174, 255), (212, 204, 188, 255), (186, 178, 164, 255)])
        draw.rectangle([sx, sy, sx + sw, sy + sh], fill=shade, outline=INK_FAINT, width=1)

    # 4. Calm, LOW-TEXTURE-DENSITY center salt-crossing ground + subtle shallow ford wash
    # Warm pale sunlit center wash (RGB matched with alpha=0 -> zero dark ring)
    wash = Image.new("RGBA", (W, H), (232, 224, 206, 0))
    wd = ImageDraw.Draw(wash, "RGBA")
    wd.ellipse([180, 280, 1420, 820], fill=(232, 224, 206, 115))
    wash = wash.filter(ImageFilter.GaussianBlur(46))
    img = Image.alpha_composite(img, wash)
    draw = ImageDraw.Draw(img, "RGBA")

    # Gentle horizontal shallow salt-water ford hint across mid-board (very low contrast so hex overlay owns exact cells)
    ford = Image.new("RGBA", (W, H), (168, 186, 182, 0))
    fd = ImageDraw.Draw(ford, "RGBA")
    fd.polygon([(0, 485), (420, 470), (800, 466), (1180, 470), (W, 485),
                (W, 565), (1180, 578), (800, 582), (420, 576), (0, 562)], fill=(162, 182, 178, 72))
    ford = ford.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, ford)
    draw = ImageDraw.Draw(img, "RGBA")

    # Very light salt-grain watercolor texture (RGB matched with alpha=0)
    grain = Image.new("RGBA", (W, H), (220, 212, 194, 0))
    gd = ImageDraw.Draw(grain, "RGBA")
    for _ in range(600):
        gx = rng.randint(0, W - 1)
        gy = rng.randint(268, H - 1)
        gr = rng.randint(14, 38)
        c = (206, 198, 182, 18) if rng.random() < 0.5 else (238, 232, 218, 18)
        gd.ellipse([gx - gr, gy - gr // 2, gx + gr, gy + gr // 2], fill=c)
    grain = grain.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, grain)
    draw = ImageDraw.Draw(img, "RGBA")

    # 5. Faceted salt-encrusted foreground corner stones (bottom-left & bottom-right only)
    fg_left = [(0, 756), (90, 784), (185, 828), (315, 868), (405, H), (0, H)]
    draw.polygon(fg_left, fill=(138, 132, 122, 255), outline=INK)
    draw.polygon([(0, 782), (88, 814), (182, 856), (285, H), (0, H)], fill=(104, 98, 90, 255), outline=INK_SOFT)

    fg_right = [(W, 760), (1505, 788), (1410, 832), (1280, 872), (1195, H), (W, H)]
    draw.polygon(fg_right, fill=(138, 132, 122, 255), outline=INK)
    draw.polygon([(W, 786), (1505, 818), (1410, 858), (1310, H), (W, H)], fill=(104, 98, 90, 255), outline=INK_SOFT)

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
    print("SALT_CROSSING_BACKDROP_OK:", json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()

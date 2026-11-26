"""Generate 1600x900 shared CITADEL_RING backdrop (citadel_ring_ink.png) for #14 finale battles.

Compatible with BOTH 初生魔王 (DEMON) and subsequent 管理员 (ADMIN) on the same 90-cell ring court:
- Rear upper band: monumental concentric stone-and-bronze citadel colonnade, central ceremonial arch,
  and restrained bronze ring inlays (no noisy saturated fire/glow on the combat floor).
- Combat floor: clean pale-limestone / cool-ivory circular court so orange/crimson warning hexes
  (DEMON-A front axis, DEMON-D radius-3 threat circle), 6 terrain pieces, DEMON, EN04/EN17, and
  player squad silhouettes remain razor-sharp at 1280x720 orthogonal P04B view.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1600, 900
OUT = Path(r"D:\Personal_dev-wt\issue-14-agy-demon\原型\P06_首章\assets\citadel_ring\citadel_ring_ink.png")


def build_backdrop() -> Path:
    img = Image.new("RGB", (W, H), (206, 204, 200))
    draw = ImageDraw.Draw(img)

    # 1. Soft atmospheric sky-to-stone horizon gradient (top 0..240)
    for y in range(250):
        t = y / 249.0
        r = int(202 - 22 * t)
        g = int(201 - 21 * t)
        b = int(198 - 17 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # 2. Distant citadel ring silhouette & obelisk towers (cool slate, low contrast)
    ridge = [(0, 210)]
    for x in range(0, W + 1, 20):
        curve = 178 - 22 * math.sin(math.pi * x / W) - 6 * math.cos(3.0 * math.pi * x / W)
        ridge.append((x, int(curve)))
    ridge += [(W, 250), (0, 250)]
    draw.polygon(ridge, fill=(142, 140, 138))

    # Distant monumental citadel obelisks / ring pylons (compatible with DEMON & ADMIN)
    pylons = [
        (175, 58, 42, 235),
        (430, 82, 34, 235),
        (800, 42, 54, 235),
        (1170, 82, 34, 235),
        (1425, 58, 42, 235),
    ]
    for cx, top, half_w, bot in pylons:
        poly = [(cx - half_w * 0.72, top), (cx + half_w * 0.72, top), (cx + half_w, bot), (cx - half_w, bot)]
        draw.polygon(poly, fill=(116, 114, 112), outline=(74, 72, 70))
        # Subtle aged-bronze band near crown
        draw.rectangle([cx - half_w * 0.78, top + 16, cx + half_w * 0.78, top + 24], fill=(164, 134, 96))

    # 3. Rear circular citadel colonnade arches (3 monumental recessed bays)
    for ax, aw, ah in [(330, 118, 96), (800, 148, 112), (1270, 118, 96)]:
        base_y = 242
        draw.rectangle([ax - aw // 2, base_y - ah, ax + aw // 2, base_y], fill=(102, 99, 96), outline=(66, 63, 60), width=2)
        in_w = int(aw * 0.68)
        in_h = int(ah * 0.78)
        # Arch interior (cool deep slate-bronze recess — subtle, never competing with orange warnings)
        draw.pieslice([ax - in_w // 2, base_y - in_h, ax + in_w // 2, base_y + in_h // 2], 180, 360, fill=(76, 74, 73))
        draw.rectangle([ax - in_w // 2, base_y - in_h // 2, ax + in_w // 2, base_y], fill=(76, 74, 73))
        # Subtle bronze inner ring rim on central bay
        draw.arc([ax - in_w // 2 + 6, base_y - in_h + 6, ax + in_w // 2 - 6, base_y + in_h // 2 - 6],
                 180, 360, fill=(176, 146, 106), width=3)

    # 4. Concentric stone parapet wall separating rear colonnade from combat ring
    parapet_pts = []
    for x in range(0, W + 1, 16):
        y = int(248 - 14 * math.sin(math.pi * x / W))
        parapet_pts.append((x, y))
    for i in range(len(parapet_pts) - 1):
        x0, y0 = parapet_pts[i]
        x1, y1 = parapet_pts[i + 1]
        draw.polygon([(x0, y0 - 22), (x1, y1 - 22), (x1, y1 + 8), (x0, y0 + 8)], fill=(156, 152, 146), outline=(88, 84, 79))

    # 5. Clean neutral pale-limestone circular combat floor (y = 240..900)
    floor_poly = [(0, H)] + parapet_pts + [(W, H)]
    draw.polygon(floor_poly, fill=(214, 212, 206))

    # Subtle concentric ring stone seams on the floor (very low contrast so hexes & warnings dominate)
    cx, cy = W // 2, 540
    for rx, ry, col in [
        (680, 275, (190, 187, 180)),
        (510, 205, (194, 190, 182)),
        (330, 132, (196, 191, 181)),
    ]:
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col, width=2)

    # Subtle radial stone joints
    for deg in range(0, 360, 30):
        rad = math.radians(deg)
        x0, y0 = cx + int(330 * math.cos(rad)), cy + int(132 * math.sin(rad))
        x1, y1 = cx + int(680 * math.cos(rad)), cy + int(275 * math.sin(rad))
        if y0 > 246 and y1 > 246:
            draw.line([(x0, y0), (x1, y1)], fill=(196, 193, 186), width=1)

    # Foreground dark stone rim framing bottom corners (keeps 1280x720 composition grounded)
    draw.polygon([(0, H - 115), (340, H), (0, H)], fill=(106, 102, 98), outline=(68, 65, 62))
    draw.polygon([(W, H - 115), (W - 340, H), (W, H)], fill=(106, 102, 98), outline=(68, 65, 62))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"CITADEL_BACKDROP_OK: {OUT} bytes={OUT.stat().st_size} sha256={digest}")
    return OUT


if __name__ == "__main__":
    build_backdrop()

"""Procedurally build EN19 (哥布林劫掠者) and EN20 (哥布林弩手) from a shared goblin body/rig recipe.

Original local procedural recipe (zero external mesh/image/motion donors):
- Shared compact hunched goblin base body & 14-bone armature (forward = -Y / glTF +Z, left = +X, up = +Z).
- Unmistakable role distinction at 1280x720 ortho board scale:
  * EN19 (哥布林劫掠者): low coiled crouch, rust-crimson raider scarf/shoulder, broad curved short-blade
    cocked wide to the side (EN19-A 侧袭短刀 W1, strictly in-place — zero fake forward dash).
  * EN20 (哥布林弩手): braced archer stance, ochre-brass hood & hip quiver, wide two-handed T-profile
    crossbow with explicit `CrossbowMuzzle` socket node (EN20-A 钉脚弩 W2, no fabricated projectile).
- Non-degenerate pole UVs on all primitives (uv_zero_area_faces = 0, uv_oob_pct = 0.0).
- Strictly <=4 normalized weights, 0 degenerate faces, 0 root XY drift.
- Each unit exports 10 in-place clips (6 core + 4 skill clips), verifies first_frame_z, last_frame_z,
  half_frame_min_z, weapon-hand contact, and clean-blend GLB re-import, and renders 8-pose proofs,
  Down f30 Z=0 side/3Q ground-contact proofs, small-scale readability, and EN19 vs EN20 pair comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

SPECS = {
    "EN19": {
        "name": "哥布林劫掠者",
        "move": "EN19-A 侧袭短刀 (W1, adjacent flank lock; strictly in-place, zero fake dash)",
        "accent": "crimson",
        "clips": [
            ("EN19Idle", 48),
            ("EN19Walk", 24),
            ("EN19Stop", 18),
            ("EN19Attack", 24),
            ("EN19Hit", 18),
            ("EN19Down", 30),
            ("EN19FlankRaise", 18),
            ("EN19FlankHold", 36),
            ("EN19FlankRelease", 24),
            ("EN19FlankCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EN19Idle", 12),
            ("1_walk", "EN19Walk", 6),
            ("2_attack", "EN19Attack", 12),
            ("3_A_raise", "EN19FlankRaise", 14),
            ("4_A_hold", "EN19FlankHold", 18),
            ("5_A_release", "EN19FlankRelease", 11),
            ("6_A_cancel", "EN19FlankCancel", 9),
            ("7_down_end", "EN19Down", 30),
        ],
    },
    "EN20": {
        "name": "哥布林弩手",
        "move": "EN20-A 钉脚弩 (W2, 1-hex ray lock; explicit CrossbowMuzzle socket, no fabricated projectile)",
        "accent": "ochre",
        "clips": [
            ("EN20Idle", 48),
            ("EN20Walk", 24),
            ("EN20Stop", 18),
            ("EN20Attack", 24),
            ("EN20Hit", 18),
            ("EN20Down", 30),
            ("EN20PinRaise", 18),
            ("EN20PinHold", 36),
            ("EN20PinRelease", 24),
            ("EN20PinCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EN20Idle", 12),
            ("1_walk", "EN20Walk", 6),
            ("2_attack", "EN20Attack", 12),
            ("3_A_raise", "EN20PinRaise", 14),
            ("4_A_hold", "EN20PinHold", 18),
            ("5_A_release", "EN20PinRelease", 11),
            ("6_A_cancel", "EN20PinCancel", 9),
            ("7_down_end", "EN20Down", 30),
        ],
    },
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out-enemies-dir", required=True)
    p.add_argument("--out-evidence-dir", required=True)
    return p.parse_args(argv)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def activate_action(arm_obj, act) -> None:
    ad = arm_obj.animation_data or arm_obj.animation_data_create()
    ad.action = act
    if hasattr(ad, "action_slot") and getattr(act, "slots", None) and len(act.slots) > 0:
        try:
            ad.action_slot = act.slots[0]
        except Exception:
            pass


def write_png_rgb(path: Path, width: int, height: int, rgb_bytes: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb_bytes[y * stride:(y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def generate_goblin_texture(out_path: Path, accent: str, size: int = 512) -> str:
    """Generate a P04B warm-frontier 4-band goblin atlas (PNG row 0 = UV v=1.0).
    Bands:
      v in [0.00, 0.25): Mossy-olive goblin skin + warm amber eyes near u=0.75, v=0.14
      v in [0.25, 0.52): Scavenged frontier leather tunic, boots & dark straps
      v in [0.52, 0.76): Role accent cloth/hood/scarf (EN19 rust-crimson / EN20 warm ochre-brass)
      v in [0.76, 1.00]: Weapon materials — worn timber stock (0.76..0.86) + bright forged steel (0.86..1.00)
    """
    buf = bytearray(size * size * 3)
    for py in range(size):
        v = 1.0 - (py / (size - 1))
        for px in range(size):
            u = px / (size - 1)
            grain = 0.5 + 0.3 * math.sin(u * 48.0 + v * 36.0) + 0.2 * math.cos(u * 90.0 - v * 72.0)

            if v < 0.25:
                # Mossy-olive goblin skin
                k = v / 0.25
                r = 98 + 26 * k + 10 * grain
                g = 120 + 28 * k + 12 * grain
                b = 64 + 14 * k + 8 * grain
                # Glowing amber-yellow goblin eyes facing -Y (u near 0.70 & 0.80)
                for eye_u in (0.69, 0.81):
                    du = ((u - eye_u + 0.5) % 1.0) - 0.5
                    dv = (v - 0.14) * 1.5
                    ed = math.hypot(du * 4.5, dv * 4.5)
                    if ed < 0.16:
                        ek = max(0.0, 1.0 - ed / 0.16) ** 1.2
                        r = r * (1.0 - ek) + 246 * ek
                        g = g * (1.0 - ek) + 196 * ek
                        b = b * (1.0 - ek) + 54 * ek
            elif v < 0.52:
                # Worn brown leather tunic, straps & boots
                k = (v - 0.25) / 0.27
                seam = 0.86 if abs(math.sin(u * math.pi * 8.0)) < 0.08 or abs(k - 0.45) < 0.06 else 1.0
                r = (76 + 34 * k + 12 * grain) * seam
                g = (58 + 24 * k + 10 * grain) * seam
                b = (44 + 16 * k + 8 * grain) * seam
            elif v < 0.76:
                # Distinct role accent: EN19 rust-crimson raider scarf vs EN20 ochre-brass crossbowman hood/quiver
                k = (v - 0.52) / 0.24
                weave = 0.90 + 0.16 * math.sin(u * math.pi * 24.0 + v * 40.0)
                if accent == "crimson":
                    r = (156 + 38 * k) * weave
                    g = (52 + 18 * k) * weave
                    b = (42 + 14 * k) * weave
                else:
                    r = (178 + 34 * k) * weave
                    g = (138 + 28 * k) * weave
                    b = (64 + 18 * k) * weave
            else:
                # Weapon band: timber handle/stock (v < 0.86) + bright forged steel blade/prod (v >= 0.86)
                if v < 0.86:
                    k = (v - 0.76) / 0.10
                    r = 104 + 28 * k + 10 * grain
                    g = 72 + 20 * k + 8 * grain
                    b = 46 + 12 * k + 6 * grain
                else:
                    k = (v - 0.86) / 0.14
                    r = 178 + 56 * k
                    g = 184 + 52 * k
                    b = 190 + 48 * k

            idx = (py * size + px) * 3
            buf[idx] = max(0, min(255, int(r)))
            buf[idx + 1] = max(0, min(255, int(g)))
            buf[idx + 2] = max(0, min(255, int(b)))

    write_png_rgb(out_path, size, size, bytes(buf))
    return sha256_file(out_path)


def add_lathe_part(
    bm: bmesh.types.BMesh,
    uv_layer,
    profile: list[tuple[float, float]],
    center: Vector,
    v_min: float,
    v_max: float,
    n_rad: int = 12,
    squish_x: float = 1.0,
    squish_y: float = 1.0,
    rot_euler: Euler | None = None,
    part_tag: str = "hips",
    vert_tags: dict[int, str] | None = None,
) -> None:
    """Closed watertight lathe solid with guaranteed non-zero pole cap UV triangles."""
    rot_m = rot_euler.to_matrix() if rot_euler else None
    n_rings = len(profile)
    v_span = v_max - v_min
    v_margin = min(0.014, v_span * 0.10)
    v_lo = v_min + v_margin
    v_hi = v_max - v_margin

    def xform(pt: Vector) -> Vector:
        p = rot_m @ pt if rot_m else pt
        return center + p

    rings = []
    for ri, (rad, lz) in enumerate(profile):
        frac = ri / max(1, n_rings - 1)
        vv = v_lo + frac * (v_hi - v_lo)
        ring = []
        for j in range(n_rad):
            u = j / n_rad
            ang = u * math.pi * 2.0
            pt = Vector((rad * math.cos(ang) * squish_x, rad * math.sin(ang) * squish_y, lz))
            v = bm.verts.new(xform(pt))
            if vert_tags is not None:
                bm.verts.index_update()
                vert_tags[v.index] = part_tag
            ring.append((v, u, vv))
        rings.append(ring)

    for ri in range(n_rings - 1):
        r0, r1 = rings[ri], rings[ri + 1]
        for j in range(n_rad):
            jn = (j + 1) % n_rad
            v00, u00, vv0 = r0[j]
            v01, u01, _ = r0[jn]
            v11, u11, vv1 = r1[jn]
            v10, u10, _ = r1[j]
            u01_w = 1.0 if jn == 0 else u01
            u11_w = 1.0 if jn == 0 else u11
            f = bm.faces.new((v00, v01, v11, v10))
            for loop, uv in zip(f.loops, [(u00, vv0), (u01_w, vv0), (u11_w, vv1), (u10, vv1)]):
                loop[uv_layer].uv = uv

    bot_v = bm.verts.new(xform(Vector((0.0, 0.0, profile[0][1] - 0.005))))
    top_v = bm.verts.new(xform(Vector((0.0, 0.0, profile[-1][1] + 0.005))))
    if vert_tags is not None:
        bm.verts.index_update()
        vert_tags[bot_v.index] = part_tag
        vert_tags[top_v.index] = part_tag
    for j in range(n_rad):
        jn = (j + 1) % n_rad
        v0, u0, vv0 = rings[0][j]
        v1, u1, vv1 = rings[0][jn]
        u1_w = 1.0 if jn == 0 else u1
        f = bm.faces.new((bot_v, v1, v0))
        for loop, uv in zip(f.loops, [(0.5 * (u0 + u1_w), v_min + 0.002), (u1_w, vv1), (u0, vv0)]):
            loop[uv_layer].uv = uv

        v0t, u0t, vv0t = rings[-1][j]
        v1t, u1t, vv1t = rings[-1][jn]
        u1t_w = 1.0 if jn == 0 else u1t
        ft = bm.faces.new((top_v, v0t, v1t))
        for loop, uv in zip(ft.loops, [(0.5 * (u0t + u1t_w), v_max - 0.002), (u0t, vv0t), (u1t_w, vv1t)]):
            loop[uv_layer].uv = uv


def add_box_part(
    bm: bmesh.types.BMesh,
    uv_layer,
    center: Vector,
    size: tuple[float, float, float],
    v_min: float,
    v_max: float,
    rot_euler: Euler | None = None,
    part_tag: str = "weapon",
    vert_tags: dict[int, str] | None = None,
) -> None:
    """Closed watertight box with guaranteed non-zero face UVs."""
    hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    rot_m = rot_euler.to_matrix() if rot_euler else None
    corners = [
        Vector((-hx, -hy, -hz)), Vector((hx, -hy, -hz)), Vector((hx, hy, -hz)), Vector((-hx, hy, -hz)),
        Vector((-hx, -hy, hz)), Vector((hx, -hy, hz)), Vector((hx, hy, hz)), Vector((-hx, hy, hz)),
    ]
    verts = []
    for c in corners:
        p = (rot_m @ c) if rot_m else c
        v = bm.verts.new(center + p)
        if vert_tags is not None:
            bm.verts.index_update()
            vert_tags[v.index] = part_tag
        verts.append(v)
    quads = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    for q in quads:
        f = bm.faces.new([verts[i] for i in q])
        for loop, uv in zip(f.loops, [(0.1, v_min + 0.004), (0.9, v_min + 0.004), (0.9, v_max - 0.004), (0.1, v_max - 0.004)]):
            loop[uv_layer].uv = uv


def add_limb_between(
    bm: bmesh.types.BMesh,
    uv_layer,
    p0: Vector,
    p1: Vector,
    r0: float,
    r1: float,
    v_min: float,
    v_max: float,
    n_rad: int = 10,
    squish_x: float = 1.0,
    squish_y: float = 1.0,
    part_tag: str = "hips",
    vert_tags: dict[int, str] | None = None,
) -> None:
    """Build a seamless capped capsule-like limb segment strictly from p0 to p1."""
    vec = p1 - p0
    length = vec.length
    if length < 1e-5:
        return
    rot_q = Vector((0.0, 0.0, 1.0)).rotation_difference(vec.normalized())
    prof = [
        (r0 * 0.72, -r0 * 0.35),
        (r0, 0.0),
        (0.5 * (r0 + r1), length * 0.5),
        (r1, length),
        (r1 * 0.72, length + r1 * 0.35),
    ]
    add_lathe_part(
        bm, uv_layer, prof, p0, v_min, v_max, n_rad=n_rad,
        squish_x=squish_x, squish_y=squish_y, rot_euler=rot_q.to_euler("XYZ"),
        part_tag=part_tag, vert_tags=vert_tags,
    )


def build_goblin_mesh(kind: str, tex_path: Path) -> tuple[bpy.types.Object, dict[int, str]]:
    """Build shared goblin base body + distinct role gear/weapon for EN19 or EN20.
    Every limb segment is built directly between exact joint coordinates so zero gaps exist.
    Rest pose coordinates (meters):
      Feet at Z=0.0, hips at Z=0.44, chest at Z=0.72, head at Z=0.98, top ~1.18 m.
      Forward = -Y, Left = +X, Right = -X.
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    vert_tags: dict[int, str] = {}

    # Exact shared joint coordinates (also used verbatim by build_goblin_armature!)
    sh_l, el_l, wr_l = Vector((0.19, -0.02, 0.78)), Vector((0.26, -0.10, 0.60)), Vector((0.24, -0.28, 0.58))
    sh_r, el_r, wr_r = Vector((-0.19, -0.02, 0.78)), Vector((-0.26, -0.10, 0.60)), Vector((-0.24, -0.28, 0.58))
    if kind == "EN20":
        # Two-handed crossbow rest grip: right hand on rear stock, left hand forward on fore-stock!
        wr_r = Vector((-0.06, -0.26, 0.62))
        wr_l = Vector((0.04, -0.44, 0.61))
        el_r = Vector((-0.22, -0.12, 0.60))
        el_l = Vector((0.20, -0.20, 0.59))

    # === 1. SHARED GOBLIN BASE BODY ===
    # Pelvis / hips & belted tunic skirt
    add_lathe_part(
        bm, uv_layer, [(0.13, 0.36), (0.16, 0.44), (0.15, 0.54)],
        Vector((0.0, 0.0, 0.0)), 0.26, 0.50, n_rad=12, squish_x=1.12, squish_y=0.92,
        part_tag="hips", vert_tags=vert_tags,
    )
    # Hunched wiry torso / chest
    add_lathe_part(
        bm, uv_layer, [(0.14, 0.52), (0.17, 0.64), (0.18, 0.78), (0.13, 0.86)],
        Vector((0.0, -0.02, 0.0)), 0.26, 0.50, n_rad=12, squish_x=1.18, squish_y=0.90,
        part_tag="spine", vert_tags=vert_tags,
    )
    # Goblin head (slightly forward-jutting skull)
    add_lathe_part(
        bm, uv_layer, [(0.08, 0.87), (0.145, 0.96), (0.155, 1.05), (0.12, 1.13), (0.06, 1.17)],
        Vector((0.0, -0.05, 0.0)), 0.01, 0.24, n_rad=14, squish_x=0.96, squish_y=1.10,
        part_tag="head", vert_tags=vert_tags,
    )
    # Hooked goblin nose (-Y)
    add_limb_between(
        bm, uv_layer, Vector((0.0, -0.18, 1.02)), Vector((0.0, -0.27, 0.99)),
        0.036, 0.010, 0.02, 0.14, n_rad=8, part_tag="head", vert_tags=vert_tags,
    )
    # Iconic long swept-back pointed goblin ears protruding clearly on both sides (+X / -X)
    for side in (1.0, -1.0):
        add_limb_between(
            bm, uv_layer, Vector((side * 0.12, -0.04, 1.02)), Vector((side * 0.34, 0.06, 1.06)),
            0.044, 0.010, 0.02, 0.20, n_rad=8, squish_y=0.55, part_tag="head", vert_tags=vert_tags,
        )

    # Legs & boots (seamlessly joined hip -> knee -> boot)
    for side, u_tag, l_tag in ((1.0, "leg_u.L", "leg_l.L"), (-1.0, "leg_u.R", "leg_l.R")):
        hip_p = Vector((side * 0.11, 0.0, 0.44))
        knee_p = Vector((side * 0.12, -0.02, 0.22))
        ank_p = Vector((side * 0.12, -0.02, 0.05))
        add_limb_between(bm, uv_layer, hip_p, knee_p, 0.075, 0.064, 0.27, 0.48, n_rad=10, part_tag=u_tag, vert_tags=vert_tags)
        add_limb_between(bm, uv_layer, knee_p, ank_p, 0.062, 0.056, 0.27, 0.48, n_rad=10, part_tag=l_tag, vert_tags=vert_tags)
        # Boot foot grounded flat at Z=0
        add_lathe_part(
            bm, uv_layer, [(0.068, 0.006), (0.072, 0.045), (0.058, 0.085)],
            Vector((side * 0.12, -0.05, 0.0)), 0.27, 0.48, n_rad=10, squish_y=1.45,
            part_tag=l_tag, vert_tags=vert_tags,
        )

    # Seamless Arms & Hands (shoulder -> elbow -> wrist -> hand)
    for sh, el, wr, au, al, hd in (
        (sh_l, el_l, wr_l, "arm_u.L", "arm_l.L", "hand.L"),
        (sh_r, el_r, wr_r, "arm_u.R", "arm_l.R", "hand.R"),
    ):
        add_limb_between(bm, uv_layer, sh, el, 0.054, 0.048, 0.02, 0.22, n_rad=10, part_tag=au, vert_tags=vert_tags)
        add_limb_between(bm, uv_layer, el, wr, 0.046, 0.040, 0.02, 0.22, n_rad=10, part_tag=al, vert_tags=vert_tags)
        add_lathe_part(
            bm, uv_layer, [(0.040, -0.038), (0.050, 0.0), (0.040, 0.038)],
            wr, 0.02, 0.22, n_rad=10, part_tag=hd, vert_tags=vert_tags,
        )

    # === 2. ROLE-SPECIFIC GEAR & WEAPON ===
    if kind == "EN19":
        # Raider rust-crimson scarf collar & trailing tail
        add_lathe_part(
            bm, uv_layer, [(0.16, 0.78), (0.19, 0.84), (0.16, 0.90)],
            Vector((0.0, -0.03, 0.0)), 0.53, 0.74, n_rad=12, squish_x=1.18,
            part_tag="spine", vert_tags=vert_tags,
        )
        add_box_part(
            bm, uv_layer, Vector((0.06, 0.18, 0.76)), (0.12, 0.26, 0.045),
            0.53, 0.74, rot_euler=Euler((math.radians(-26.0), 0.0, math.radians(-10.0)), "XYZ"),
            part_tag="spine", vert_tags=vert_tags,
        )
        # Left raider shoulder pauldron
        add_lathe_part(
            bm, uv_layer, [(0.07, -0.05), (0.11, 0.02), (0.08, 0.08)],
            sh_l + Vector((0.02, 0.0, 0.03)), 0.53, 0.74, n_rad=10,
            part_tag="arm_u.L", vert_tags=vert_tags,
        )
        # Broad curved raider short-blade firmly gripped inside hand.R (wr_r)
        grip = wr_r
        add_limb_between(
            bm, uv_layer, grip + Vector((0.0, 0.08, -0.01)), grip + Vector((0.0, -0.09, 0.01)),
            0.024, 0.028, 0.77, 0.85, n_rad=8, part_tag="weapon", vert_tags=vert_tags,
        )
        add_box_part(
            bm, uv_layer, grip + Vector((0.0, -0.09, 0.01)), (0.13, 0.035, 0.045),
            0.53, 0.74, part_tag="weapon", vert_tags=vert_tags,
        )
        add_box_part(
            bm, uv_layer, grip + Vector((0.0, -0.27, 0.02)), (0.026, 0.34, 0.095),
            0.87, 0.99, rot_euler=Euler((math.radians(5.0), 0.0, 0.0), "XYZ"),
            part_tag="weapon", vert_tags=vert_tags,
        )
        add_limb_between(
            bm, uv_layer, grip + Vector((0.0, -0.43, 0.035)), grip + Vector((0.0, -0.60, 0.05)),
            0.046, 0.008, 0.87, 0.99, n_rad=8, squish_x=0.35, part_tag="weapon", vert_tags=vert_tags,
        )
    else:
        # EN20: Warm ochre-brass archer hood/visor + left hip bolt quiver
        add_lathe_part(
            bm, uv_layer, [(0.155, 1.05), (0.175, 1.12), (0.13, 1.19), (0.05, 1.24)],
            Vector((0.0, -0.03, 0.0)), 0.53, 0.74, n_rad=12, squish_y=1.18,
            part_tag="head", vert_tags=vert_tags,
        )
        add_lathe_part(
            bm, uv_layer, [(0.055, -0.14), (0.068, 0.0), (0.075, 0.14)],
            Vector((0.20, 0.08, 0.48)), 0.53, 0.74, n_rad=10,
            rot_euler=Euler((math.radians(-22.0), math.radians(16.0), 0.0), "XYZ"),
            part_tag="hips", vert_tags=vert_tags,
        )
        # Wide T-profile frontier crossbow centered cleanly forward (-Y) across both hands!
        # Rear grip at wr_r (-0.06, -0.26, 0.62), fore-stock resting directly in wr_l (0.04, -0.44, 0.61)
        grip = wr_r
        tiller_x = 0.0
        # Wooden tiller stock running straight forward along -Y from grip to prod nose
        add_box_part(
            bm, uv_layer, Vector((tiller_x, grip.y - 0.19, grip.z + 0.02)), (0.070, 0.54, 0.072),
            0.77, 0.85, part_tag="weapon", vert_tags=vert_tags,
        )
        # Pistol grip inside hand.R
        add_box_part(
            bm, uv_layer, Vector((grip.x + 0.03, grip.y, grip.z - 0.02)), (0.055, 0.065, 0.12),
            0.77, 0.85, rot_euler=Euler((math.radians(16.0), 0.0, 0.0), "XYZ"),
            part_tag="weapon", vert_tags=vert_tags,
        )
        # Wide horizontal curved steel crossbow prod spanning ~0.76 m across X!
        prod_c = Vector((tiller_x, grip.y - 0.44, grip.z + 0.04))
        for side in (1.0, -1.0):
            add_box_part(
                bm, uv_layer, prod_c + Vector((side * 0.19, 0.05, 0.0)), (0.40, 0.058, 0.044),
                0.87, 0.99, rot_euler=Euler((0.0, 0.0, math.radians(-side * 18.0)), "XYZ"),
                part_tag="weapon", vert_tags=vert_tags,
            )
            # Drawn taut bowstring back to tiller latch
            add_limb_between(
                bm, uv_layer,
                prod_c + Vector((side * 0.36, 0.11, 0.0)),
                Vector((tiller_x, grip.y - 0.14, grip.z + 0.055)),
                0.012, 0.012, 0.53, 0.74, n_rad=6, part_tag="weapon", vert_tags=vert_tags,
            )
        # Loaded bright steel bolt resting on top of tiller pointing straight -Y
        add_box_part(
            bm, uv_layer, Vector((tiller_x, grip.y - 0.34, grip.z + 0.072)), (0.026, 0.44, 0.026),
            0.87, 0.99, part_tag="weapon", vert_tags=vert_tags,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)

    me = bpy.data.meshes.new(f"SK_{kind}_Mesh")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new(f"SK_{kind}", me)
    bpy.context.scene.collection.objects.link(obj)

    mat = bpy.data.materials.new(f"Mat_{kind}_Goblin")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(tex_path), check_existing=True)
    img.name = f"{kind}_Goblin_Image"
    img.pack()
    tex_node.image = img
    nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.64
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.34
    obj.data.materials.append(mat)
    return obj, vert_tags


def build_goblin_armature(kind: str, mesh_obj: bpy.types.Object, vert_tags: dict[int, str]) -> bpy.types.Object:
    """Create shared 14-bone goblin rig + explicit CrossbowMuzzle socket for EN20."""
    arm_data = bpy.data.armatures.new(f"RIG_{kind}_Data")
    arm = bpy.data.objects.new(f"RIG_{kind}", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def add_bone(name: str, head: tuple, tail: tuple, parent: str | None = None):
        b = eb.new(name)
        b.head = Vector(head)
        b.tail = Vector(tail)
        if parent:
            b.parent = eb[parent]
        return b

    add_bone("root", (0.0, 0.0, 0.0), (0.0, -0.20, 0.0), None)
    add_bone("hips", (0.0, 0.0, 0.44), (0.0, 0.0, 0.56), "root")
    add_bone("spine", (0.0, 0.0, 0.56), (0.0, -0.02, 0.86), "hips")
    add_bone("head", (0.0, -0.04, 0.86), (0.0, -0.08, 1.16), "spine")

    add_bone("leg_u.L", (0.12, 0.0, 0.44), (0.12, 0.0, 0.22), "hips")
    add_bone("leg_l.L", (0.12, 0.0, 0.22), (0.13, -0.02, 0.02), "leg_u.L")
    add_bone("leg_u.R", (-0.12, 0.0, 0.44), (-0.12, 0.0, 0.22), "hips")
    add_bone("leg_l.R", (-0.12, 0.0, 0.22), (-0.13, -0.02, 0.02), "leg_u.R")

    sh_l, el_l, wr_l = (0.19, -0.02, 0.78), (0.26, -0.10, 0.60), (0.24, -0.28, 0.58)
    sh_r, el_r, wr_r = (-0.19, -0.02, 0.78), (-0.26, -0.10, 0.60), (-0.24, -0.28, 0.58)
    w_tail = (-0.24, -0.82, 0.62)
    if kind == "EN20":
        wr_r = (-0.06, -0.26, 0.62)
        wr_l = (0.04, -0.44, 0.61)
        el_r = (-0.22, -0.12, 0.60)
        el_l = (0.20, -0.20, 0.59)
        w_tail = (0.0, -0.78, 0.68)

    add_bone("arm_u.L", sh_l, el_l, "spine")
    add_bone("arm_l.L", el_l, wr_l, "arm_u.L")
    add_bone("hand.L", wr_l, (wr_l[0], wr_l[1] - 0.08, wr_l[2]), "arm_l.L")

    add_bone("arm_u.R", sh_r, el_r, "spine")
    add_bone("arm_l.R", el_r, wr_r, "arm_u.R")
    add_bone("hand.R", wr_r, (wr_r[0], wr_r[1] - 0.08, wr_r[2]), "arm_l.R")
    add_bone("weapon", wr_r, w_tail, "hand.R")

    bpy.ops.object.mode_set(mode="OBJECT")

    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    vgs = {b.name: mesh_obj.vertex_groups.new(name=b.name) for b in arm.data.bones}
    for v in mesh_obj.data.vertices:
        tag = vert_tags.get(v.index, "hips")
        vgs[tag if tag in vgs else "hips"].add([v.index], 1.0, "REPLACE")

    # Explicit CrossbowMuzzle socket node parented to `weapon` bone for EN20
    if kind == "EN20":
        muzzle = bpy.data.objects.new("CrossbowMuzzle", None)
        muzzle.empty_display_type = "ARROWS"
        muzzle.empty_display_size = 0.08
        bpy.context.scene.collection.objects.link(muzzle)
        muzzle.parent = arm
        muzzle.parent_type = "BONE"
        muzzle.parent_bone = "weapon"
        # Tip of bolt at crossbow prod nose (local to bone tail = (0, 0, 0) in Blender bone parenting!)
        muzzle.location = Vector((0.0, 0.02, 0.02))

    return arm


def set_goblin_pose(arm: bpy.types.Object, kind: str, clip: str, t: float) -> None:
    """In-place animations for EN19 (low side-raised dagger) and EN20 (two-handed crossbow).
    Strictly ZERO root/hips world XY drift across all clips!
    """
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")

    s2 = math.sin(t * math.pi * 2.0)
    c2 = math.cos(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)

    def r(bn: str, x: float, y: float = 0.0, z: float = 0.0) -> None:
        pbs[bn].rotation_euler = Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ")

    if kind == "EN19":
        # Base low coiled raider stance: hunched forward, right dagger cocked out to the right side!
        def base_raider(breath: float = 0.0) -> None:
            r("hips", 16.0 + 2.0 * breath, 0.0, -14.0)
            r("spine", 22.0 + 3.0 * breath, 0.0, -12.0)
            r("head", -26.0 - 2.0 * breath, 0.0, 22.0)
            r("leg_u.L", -26.0, 0.0, 8.0)
            r("leg_l.L", 28.0, 0.0, 0.0)
            r("leg_u.R", -20.0, 0.0, -10.0)
            r("leg_l.R", 24.0, 0.0, 0.0)
            # Left arm balanced forward-out, right arm holding dagger cocked wide out to side!
            r("arm_u.L", -18.0, 0.0, -18.0)
            r("arm_l.L", -12.0, 0.0, 14.0)
            r("arm_u.R", 14.0 + 4.0 * breath, 18.0, 42.0)
            r("arm_l.R", -8.0, 0.0, -24.0)
            r("weapon", 0.0, 0.0, -16.0)

        if clip == "EN19Idle":
            base_raider(s2)
        elif clip == "EN19Walk":
            base_raider(0.0)
            r("hips", 18.0, 0.0, 8.0 * s2)
            r("leg_u.L", -26.0 + 28.0 * s2, 0.0, 4.0)
            r("leg_l.L", 26.0 + 16.0 * max(0.0, -s2), 0.0, 0.0)
            r("leg_u.R", -26.0 - 28.0 * s2, 0.0, -4.0)
            r("leg_l.R", 26.0 + 16.0 * max(0.0, s2), 0.0, 0.0)
            r("arm_u.L", -18.0 - 18.0 * s2, 0.0, -14.0)
            r("arm_u.R", 12.0 + 14.0 * s2, 16.0, 38.0)
        elif clip == "EN19Stop":
            w = (1.0 - t) ** 1.5
            base_raider(0.0)
            r("spine", 22.0 + 12.0 * w, 0.0, -12.0 - 8.0 * w)
        elif clip == "EN19Attack":
            base_raider(0.0)
            slash = math.sin(min(1.0, t / 0.55) * math.pi)
            r("spine", 22.0 + 12.0 * slash, 0.0, -12.0 + 48.0 * slash)
            r("arm_u.R", 14.0 - 44.0 * slash, 18.0 - 20.0 * slash, 42.0 - 86.0 * slash)
            r("weapon", 10.0 * slash, 0.0, -16.0 + 28.0 * slash)
        elif clip == "EN19Hit":
            base_raider(0.0)
            r("spine", 22.0 - 28.0 * s1, 0.0, -12.0 - 18.0 * s1)
            r("head", -26.0 - 16.0 * s1, 0.0, 22.0)
            r("arm_u.L", -18.0 - 24.0 * s1, 0.0, -26.0)
            r("arm_u.R", 14.0 + 20.0 * s1, 22.0, 48.0)
        elif clip == "EN19Down":
            # Flat face-down/side slump on Z=0; weapon arm sweeps back/out parallel to ground (no blade-tip stand!)
            w = min(1.0, t * 1.15)
            w = w * w * (3.0 - 2.0 * w)
            r("hips", 86.0 * w, 14.0 * w, 10.0 * w)
            r("spine", 6.0 * w, 0.0, 6.0 * w)
            r("head", -14.0 * w, 0.0, -18.0 * w)
            r("leg_u.L", -6.0 * w, 0.0, 10.0 * w)
            r("leg_l.L", 8.0 * w, 0.0, 0.0)
            r("leg_u.R", -6.0 * w, 0.0, -10.0 * w)
            r("leg_l.R", 8.0 * w, 0.0, 0.0)
            r("arm_u.L", -56.0 * w, 0.0, -34.0 * w)
            r("arm_u.R", -64.0 * w, 0.0, 42.0 * w)
            r("arm_l.R", -32.0 * w, 0.0, 0.0)
            r("weapon", -24.0 * w, 0.0, -12.0 * w)
        elif clip == "EN19FlankRaise":
            # EN19-A 侧袭短刀起蓄 (低身侧举短刀): deeper crouch, dagger raised high & wide to right side
            w = min(1.0, t * 1.15)
            w = w * w * (3.0 - 2.0 * w)
            base_raider(0.0)
            r("hips", 16.0 + 10.0 * w, 0.0, -14.0 - 18.0 * w)
            r("spine", 22.0 + 10.0 * w, 0.0, -12.0 - 16.0 * w)
            r("head", -26.0 - 10.0 * w, 0.0, 22.0 + 28.0 * w)
            r("arm_u.R", 14.0 + 28.0 * w, 18.0 + 24.0 * w, 42.0 + 26.0 * w)
            r("arm_l.R", -8.0 - 18.0 * w, 0.0, -24.0)
            r("weapon", -14.0 * w, 0.0, -28.0 * w)
        elif clip == "EN19FlankHold":
            # EN19-A 侧袭短刀蓄势保持 (W1): taut low coiled side-raised blade
            base_raider(0.0)
            r("hips", 26.0 + 2.0 * s2, 0.0, -32.0 + 3.0 * c2)
            r("spine", 32.0 + 2.0 * s2, 0.0, -28.0)
            r("head", -36.0, 0.0, 50.0)
            r("arm_u.R", 42.0 + 4.0 * s2, 42.0, 68.0 + 4.0 * c2)
            r("arm_l.R", -26.0, 0.0, -24.0)
            r("weapon", -14.0, 0.0, -28.0)
        elif clip == "EN19FlankRelease":
            # EN19-A 侧袭短刀释放: explosive wide in-place horizontal sweep (ZERO root XY dash!)
            base_raider(0.0)
            if t < 0.22:
                k = t / 0.22
                yaw = -32.0 - 12.0 * k
                arm_z = 68.0 + 10.0 * k
                arm_x = 42.0
            elif t < 0.62:
                k = (t - 0.22) / 0.40
                ks = k * k * (3.0 - 2.0 * k)
                yaw = -44.0 + 102.0 * ks  # -44 -> +58 deg wide slash!
                arm_z = 78.0 - 134.0 * ks
                arm_x = 42.0 - 74.0 * ks
            else:
                k = (t - 0.62) / 0.38
                yaw = 58.0 * (1.0 - k) - 14.0 * k
                arm_z = -56.0 * (1.0 - k) + 42.0 * k
                arm_x = -32.0 * (1.0 - k) + 14.0 * k
            r("hips", 22.0, 0.0, yaw * 0.45)
            r("spine", 28.0, 0.0, yaw * 0.65)
            r("head", -32.0, 0.0, -yaw * 0.65)
            r("arm_u.R", arm_x, 22.0, arm_z)
            r("arm_l.R", -14.0, 0.0, -18.0)
            r("weapon", 8.0, 0.0, -10.0)
        elif clip == "EN19FlankCancel":
            w = 1.0 - t
            w = w * w * (3.0 - 2.0 * w)
            base_raider(0.0)
            r("hips", 16.0 + 10.0 * w, 0.0, -14.0 - 18.0 * w)
            r("spine", 22.0 + 10.0 * w, 0.0, -12.0 - 16.0 * w)
            r("head", -26.0 - 10.0 * w, 0.0, 22.0 + 28.0 * w)
            r("arm_u.R", 14.0 + 28.0 * w, 18.0 + 24.0 * w, 42.0 + 26.0 * w)
            r("arm_l.R", -8.0 - 18.0 * w, 0.0, -24.0)
            r("weapon", -14.0 * w, 0.0, -28.0 * w)

    else:
        # EN20: Braced upright archer stance holding wide T-crossbow cleanly level with BOTH hands!
        def base_xbow(breath: float = 0.0, aim_lift: float = 0.0) -> None:
            r("hips", 6.0 + 1.5 * breath, 0.0, 4.0)
            r("spine", 4.0 + 1.5 * breath - 4.0 * aim_lift, 0.0, 4.0)
            r("head", -6.0 + 4.0 * aim_lift, 0.0, -6.0)
            r("leg_u.L", -12.0, 0.0, 6.0)
            r("leg_l.L", 14.0, 0.0, 0.0)
            r("leg_u.R", -10.0, 0.0, -8.0)
            r("leg_l.R", 12.0, 0.0, 0.0)
            # Keep arms & crossbow level and horizontal (-Y forward) so both hands stay on stock!
            r("arm_u.R", -6.0 * aim_lift + 1.5 * breath, 0.0, 0.0)
            r("arm_l.R", 4.0 * aim_lift, 0.0, 0.0)
            r("arm_u.L", -6.0 * aim_lift + 1.5 * breath, 0.0, 0.0)
            r("arm_l.L", 4.0 * aim_lift, 0.0, 0.0)
            r("weapon", 2.0 * aim_lift, 0.0, 0.0)

        if clip == "EN20Idle":
            base_xbow(s2, 0.25)
        elif clip == "EN20Walk":
            base_xbow(0.0, 0.15)
            r("hips", 8.0, 0.0, 6.0 * s2)
            r("leg_u.L", -14.0 + 24.0 * s2, 0.0, 4.0)
            r("leg_l.L", 16.0 + 14.0 * max(0.0, -s2), 0.0, 0.0)
            r("leg_u.R", -14.0 - 24.0 * s2, 0.0, -4.0)
            r("leg_l.R", 16.0 + 14.0 * max(0.0, s2), 0.0, 0.0)
        elif clip == "EN20Stop":
            w = (1.0 - t) ** 1.5
            base_xbow(0.0, 0.25)
            r("spine", 4.0 + 8.0 * w, 0.0, 4.0)
        elif clip == "EN20Attack":
            kick = math.sin(min(1.0, max(0.0, (t - 0.25) / 0.35)) * math.pi)
            base_xbow(0.0, 0.85)
            r("spine", -12.0 * kick, 0.0, 4.0)
            r("arm_u.R", -6.0 - 12.0 * kick, 0.0, 0.0)
            r("arm_u.L", -6.0 - 10.0 * kick, 0.0, 0.0)
            r("weapon", 2.0 + 8.0 * kick, 0.0, 0.0)
        elif clip == "EN20Hit":
            base_xbow(0.0, 0.2)
            r("spine", 4.0 - 22.0 * s1, 0.0, 4.0 - 14.0 * s1)
            r("head", -6.0 - 14.0 * s1, 0.0, -6.0)
        elif clip == "EN20Down":
            # Flat supine fall resting solidly on back, head & heels on Z=0
            w = min(1.0, t * 1.15)
            w = w * w * (3.0 - 2.0 * w)
            r("hips", -88.0 * w, 6.0 * w, -8.0 * w)
            r("spine", -2.0 * w, 0.0, -4.0 * w)
            r("head", 6.0 * w, 0.0, 8.0 * w)
            r("leg_u.L", 4.0 * w, 0.0, 10.0 * w)
            r("leg_l.L", 4.0 * w, 0.0, 0.0)
            r("leg_u.R", 4.0 * w, 0.0, -10.0 * w)
            r("leg_l.R", 4.0 * w, 0.0, 0.0)
            r("arm_u.L", 22.0 * w, 0.0, -18.0 * w)
            r("arm_u.R", 26.0 * w, 0.0, 18.0 * w)
            r("weapon", -14.0 * w, 0.0, 0.0)
        elif clip == "EN20PinRaise":
            w = min(1.0, t * 1.15)
            w = w * w * (3.0 - 2.0 * w)
            base_xbow(0.0, 0.25 + 0.75 * w)
            r("leg_u.L", -12.0 - 10.0 * w, 0.0, 8.0)
            r("leg_l.L", 14.0 + 10.0 * w, 0.0, 0.0)
        elif clip == "EN20PinHold":
            base_xbow(s2 * 0.5, 1.0)
            r("leg_u.L", -22.0, 0.0, 8.0)
            r("leg_l.L", 24.0, 0.0, 0.0)
        elif clip == "EN20PinRelease":
            if t < 0.20:
                kick, aim = 0.0, 1.0
            elif t < 0.55:
                k = (t - 0.20) / 0.35
                kick, aim = math.sin(k * math.pi), 1.0
            else:
                k = (t - 0.55) / 0.45
                kick, aim = 0.0, 1.0 - 0.75 * k
            base_xbow(0.0, aim)
            r("spine", -14.0 * kick, 0.0, 4.0)
            r("arm_u.R", -6.0 * aim - 12.0 * kick, 0.0, 0.0)
            r("arm_u.L", -6.0 * aim - 10.0 * kick, 0.0, 0.0)
            r("weapon", 2.0 * aim + 10.0 * kick, 0.0, 0.0)
        elif clip == "EN20PinCancel":
            w = 1.0 - t
            w = w * w * (3.0 - 2.0 * w)
            base_xbow(0.0, 0.25 + 0.75 * w)
            r("leg_u.L", -12.0 - 10.0 * w, 0.0, 8.0)
            r("leg_l.L", 14.0 + 10.0 * w, 0.0, 0.0)


def measure_clip_floor(arm, mesh, deps, scene, hips_rest_head: Vector, f0: float, f1: float) -> dict:
    hf_min, hf_worst, sub_3cm, max_xy, degen = 999.0, f0, 0, 0.0, 0

    def eval_frame(frame_val: float, check_degen: bool = False) -> tuple[float, float]:
        nonlocal degen
        fi = int(math.floor(frame_val))
        scene.frame_set(fi, subframe=frame_val - fi)
        bpy.context.view_layer.update()
        eo = mesh.evaluated_get(deps)
        me = eo.to_mesh()
        mz = min((mesh.matrix_world @ v.co).z for v in me.vertices)
        if check_degen:
            degen = sum(1 for p in me.polygons if p.area < 1e-8)
        eo.to_mesh_clear()
        hh_w = arm.matrix_world @ arm.pose.bones["hips"].head
        xy = math.hypot(hh_w.x - hips_rest_head.x, hh_w.y - hips_rest_head.y)
        return mz, xy

    first_z, xy0 = eval_frame(f0, check_degen=True)
    max_xy = max(max_xy, xy0)
    cur = f0
    while cur <= f1 + 1e-4:
        mz, xy = eval_frame(cur)
        max_xy = max(max_xy, xy)
        if mz < hf_min:
            hf_min, hf_worst = mz, cur
        if mz < -0.03:
            sub_3cm += 1
        cur += 0.5
    last_z, xy1 = eval_frame(f1)
    max_xy = max(max_xy, xy1)
    if last_z < hf_min:
        hf_min, hf_worst = last_z, f1
    if last_z < -0.03:
        sub_3cm += 1

    return {
        "frame_range": [round(f0, 2), round(f1, 2)],
        "first_frame_z": round(first_z, 6),
        "last_frame_z": round(last_z, 6),
        "half_frame_min_z": round(hf_min, 6),
        "half_frame_worst": round(hf_worst, 2),
        "samples_below_neg_3cm": sub_3cm,
        "max_root_xy_drift_m": round(max_xy, 6),
        "degenerate_faces": degen,
    }


def render_unit_proofs(kind: str, arm, out_dir: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 520
    scene.render.resolution_y = 360
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ProofWorld")
    scene.world.color = (0.86, 0.83, 0.78)

    cam_data = bpy.data.cameras.new("ProofCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.05
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.5, -2.8, 1.75))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.55)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in SPECS[kind]["proof_panels"]:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"{kind}_panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)

    # Z=0 ground-plane contact proof for Down f30
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.02))
    floor_slab = bpy.context.active_object
    floor_slab.scale = (4.0, 4.0, 0.04)
    fmat = bpy.data.materials.new("ProofFloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor_slab.data.materials.append(fmat)

    scene.render.resolution_x = 720
    scene.render.resolution_y = 400
    cam_data.ortho_scale = 2.1
    cam.location = Vector((3.2, 0.0, 0.36))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.28)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions[f"{kind}Down"])
    scene.frame_set(30)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / f"{kind}_down_ground_contact_side.png")
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(floor_slab, do_unlink=True)


def build_single_goblin(kind: str, out_enemies_dir: Path, out_evidence_dir: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24

    spec = SPECS[kind]
    out_blend = out_evidence_dir / f"{kind}_Board.blend"
    out_glb = out_enemies_dir / f"{kind}_Board.glb"
    tex_path = out_evidence_dir / f"{kind}_Goblin_Tex.png"
    tex_sha = generate_goblin_texture(tex_path, spec["accent"], size=512)

    mesh, vert_tags = build_goblin_mesh(kind, tex_path)
    arm = build_goblin_armature(kind, mesh, vert_tags)

    bpy.context.view_layer.update()
    zs = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    if abs(min(zs)) > 1e-4:
        arm.location.z -= min(zs)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    verts_over4 = sum(1 for v in mesh.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4)
    unweighted = sum(1 for v in mesh.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) == 0)
    tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    bbox_ws = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    rest_dims = {
        "x_span_m": round(max(p.x for p in bbox_ws) - min(p.x for p in bbox_ws), 4),
        "y_span_m": round(max(p.y for p in bbox_ws) - min(p.y for p in bbox_ws), 4),
        "z_span_m": round(max(p.z for p in bbox_ws) - min(p.z for p in bbox_ws), 4),
        "min_z_m": round(min(p.z for p in bbox_ws), 5),
        "forward_axis": "-Y (glTF +Z)",
        "left_axis": "+X",
    }

    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"

    h_rest = (arm.matrix_world @ arm.data.bones["hips"].matrix_local).to_3x3().normalized()
    r_rest = (arm.matrix_world @ arm.data.bones["root"].matrix_local).to_3x3().normalized()
    hips_rest_head = arm.matrix_world @ arm.data.bones["hips"].head_local

    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()
    bone_names = [b.name for b in arm.data.bones]

    for cname, n_frames in spec["clips"]:
        act = bpy.data.actions.new(name=cname)
        act.use_fake_user = True
        activate_action(arm, act)
        for f in range(1, n_frames + 1):
            t = (f - 1) / max(1, n_frames - 1)
            scene.frame_set(f)
            set_goblin_pose(arm, kind, cname, t)
            bpy.context.view_layer.update()

            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            eo.to_mesh_clear()
            if abs(min_z) > 1e-5:
                pb_h = arm.pose.bones["hips"]
                parent_pose_w = (arm.matrix_world @ pb_h.parent.matrix).to_3x3().normalized()
                inherited_w = parent_pose_w @ r_rest.inverted() @ h_rest
                pb_h.location += inherited_w.inverted() @ Vector((0.0, 0.0, -min_z))
                bpy.context.view_layer.update()

            for bn in bone_names:
                pb = arm.pose.bones[bn]
                pb.keyframe_insert(data_path="rotation_euler", frame=f)
                if bn in ("root", "hips"):
                    pb.keyframe_insert(data_path="location", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = cname
        strip = tr.strips.new(cname, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = n_frames

    # Floor & weapon-grip contact QA on .blend
    clip_qa = {}
    worst_min_z, worst_clip, worst_fr, total_sub3, max_xy_all = 999.0, "", 0.0, 0, 0.0
    max_grip_gap = 0.0
    for cname, n_frames in spec["clips"]:
        activate_action(arm, bpy.data.actions[cname])
        q = measure_clip_floor(arm, mesh, deps, scene, hips_rest_head, 1.0, float(n_frames))
        clip_qa[cname] = q
        if q["half_frame_min_z"] < worst_min_z:
            worst_min_z, worst_clip, worst_fr = q["half_frame_min_z"], cname, q["half_frame_worst"]
        total_sub3 += q["samples_below_neg_3cm"]
        max_xy_all = max(max_xy_all, q["max_root_xy_drift_m"])
        # Check weapon-to-hand.R head distance (should be 0.000 m!)
        scene.frame_set(max(1, n_frames // 2))
        bpy.context.view_layer.update()
        w_h = arm.matrix_world @ arm.pose.bones["weapon"].head
        hr_h = arm.matrix_world @ arm.pose.bones["hand.R"].head
        max_grip_gap = max(max_grip_gap, (w_h - hr_h).length)

    hf_summary = {
        "worst_min_z": round(worst_min_z, 6),
        "worst_clip": worst_clip,
        "worst_frame": worst_fr,
        "samples_below_neg_3cm": total_sub3,
        "max_root_xy_drift_m": round(max_xy_all, 6),
        "max_weapon_grip_gap_m": round(max_grip_gap, 6),
    }

    activate_action(arm, bpy.data.actions[f"{kind}Idle"])
    scene.frame_set(1)
    bpy.context.view_layer.update()
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        export_animations=True,
        export_nla_strips=True,
        export_nla_strips_merged_animation_name="",
        export_animation_mode="NLA_TRACKS",
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_all_influences=False,
        export_apply=False,
        export_yup=True,
    )

    render_unit_proofs(kind, arm, out_evidence_dir)

    # Clean-blend round-trip re-import verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_scene = bpy.context.scene
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 2), round(a.frame_range[1], 2)] for a in bpy.data.actions}
    re_over4 = {o.name: sum(1 for v in o.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4) for o in re_meshes}
    muzzle_present = any(o.name == "CrossbowMuzzle" for o in bpy.data.objects)
    re_floor = {}
    if re_arm and re_meshes:
        re_deps = bpy.context.evaluated_depsgraph_get()
        re_body = next((o for o in re_meshes if o.name == f"SK_{kind}"), re_meshes[0])
        re_hips_rest = re_arm.matrix_world @ re_arm.data.bones["hips"].head_local
        for a in sorted(bpy.data.actions, key=lambda x: x.name):
            activate_action(re_arm, a)
            re_floor[a.name] = measure_clip_floor(
                re_arm, re_body, re_deps, re_scene, re_hips_rest,
                float(a.frame_range[0]), float(a.frame_range[1])
            )

    expected_names = {n for n, _ in spec["clips"]}
    roundtrip = {
        "armature": re_arm.name if re_arm else None,
        "bone_count": len(re_arm.data.bones) if re_arm else 0,
        "mesh_names": sorted(o.name for o in re_meshes),
        "total_tris": re_tris,
        "verts_over_4_influences": re_over4,
        "material_count": len(bpy.data.materials),
        "image_count": len(bpy.data.images),
        "action_count": len(re_actions),
        "expected_clips_present": expected_names.issubset(set(re_actions.keys())),
        "crossbow_muzzle_present": muzzle_present if kind == "EN20" else None,
        "actions": dict(sorted(re_actions.items())),
        "clip_floor": re_floor,
    }

    return {
        "kind": kind,
        "name": spec["name"],
        "move": spec["move"],
        "rest_dimensions": rest_dims,
        "embedded_texture": {
            "name": f"{kind}_Goblin_Image",
            "local_png": str(tex_path.resolve()),
            "sha256": tex_sha,
        },
        "out_glb": str(out_glb.resolve()),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend.resolve()),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "skin_limit_4": {"tris": tris, "over_4": verts_over4, "unweighted": unweighted},
        "half_frame_summary": hf_summary,
        "clip_qa": clip_qa,
        "roundtrip": roundtrip,
    }


def render_pair_comparison(en19_glb: Path, en20_glb: Path, out_evidence_dir: Path) -> None:
    """Render EN19 (low side-raised dagger) vs EN20 (two-handed crossbow) side-by-side."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("CompareWorld")
    scene.world.color = (0.86, 0.83, 0.78)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.02))
    floor = bpy.context.active_object
    floor.scale = (6.0, 4.0, 0.04)
    fmat = bpy.data.materials.new("FloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor.data.materials.append(fmat)

    for glb_p, x_off, clip_name, fr in (
        (en19_glb, -0.82, "EN19FlankHold", 18),
        (en20_glb, 0.82, "EN20PinHold", 18),
    ):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb_p))
        added = [o for o in bpy.data.objects if o not in before]
        for o in added:
            if o.parent is None:
                o.location.x += x_off
            if o.type == "ARMATURE":
                act = bpy.data.actions.get(clip_name)
                if act:
                    activate_action(o, act)
        scene.frame_set(fr)
        bpy.context.view_layer.update()

    cam_data = bpy.data.cameras.new("CmpCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.4
    cam = bpy.data.objects.new("CmpCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -4.6, 2.4))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.55)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    scene.render.resolution_x = 960
    scene.render.resolution_y = 480
    scene.render.filepath = str(out_evidence_dir / "Goblin_pair_silhouette_compare.png")
    bpy.ops.render.render(write_still=True)

    # Small board-scale ortho readability (1280x720 equivalent scale)
    cam_data.ortho_scale = 13.0
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.filepath = str(out_evidence_dir / "Goblin_pair_small_scale_readability.png")
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = parse_args()
    out_enemies = Path(args.out_enemies_dir)
    out_ev = Path(args.out_evidence_dir)
    out_ev.mkdir(parents=True, exist_ok=True)

    rep_19 = build_single_goblin("EN19", out_enemies, out_ev)
    rep_20 = build_single_goblin("EN20", out_enemies, out_ev)
    render_pair_comparison(out_enemies / "EN19_Board.glb", out_enemies / "EN20_Board.glb", out_ev)

    full = {
        "batch": "#15 goblin pair (EN19 & EN20)",
        "recipe_origin": "100% local procedural Blender Python shared goblin body/rig recipe",
        "EN19": rep_19,
        "EN20": rep_20,
    }
    (out_ev / "goblin_pair_build_report.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("GOBLIN_PAIR_BUILD_OK:", json.dumps({
        "EN19": {
            "tris": rep_19["roundtrip"]["total_tris"],
            "actions": rep_19["roundtrip"]["action_count"],
            "hf": rep_19["half_frame_summary"],
            "down_blend_last_z": rep_19["clip_qa"]["EN19Down"]["last_frame_z"],
            "down_glb_last_z": rep_19["roundtrip"]["clip_floor"]["EN19Down"]["last_frame_z"],
        },
        "EN20": {
            "tris": rep_20["roundtrip"]["total_tris"],
            "actions": rep_20["roundtrip"]["action_count"],
            "muzzle": rep_20["roundtrip"]["crossbow_muzzle_present"],
            "hf": rep_20["half_frame_summary"],
            "down_blend_last_z": rep_20["clip_qa"]["EN20Down"]["last_frame_z"],
            "down_glb_last_z": rep_20["roundtrip"]["clip_floor"]["EN20Down"]["last_frame_z"],
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

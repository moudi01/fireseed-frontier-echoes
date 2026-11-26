"""Procedurally build EN07 (葬铃鹭) and EL04 (剪潮鹭) from a shared heron body/rig recipe.

Original local procedural recipe (zero external mesh/image/motion donors):
- Shared grounded wading-heron anatomy & 14-bone rig (forward = -Y / glTF +Z, left = +X, up = +Z).
  Always grounded — NO flying!
- Unmistakable Normal vs. Elite distinction at 1280x720 ortho board scale:
  * EN07 (葬铃鹭, ~1.58 m): low-saturation wet slate-ash plumage, dull bronze hanging funeral-bell
    throat sac, soft rounded tail, calm hunched stalking silhouette.
    10 in-place clips: 6 core + EN07SweepRaise/Hold/Release/Cancel (EN07-A 扫喙, no target push).
  * EL04 (剪潮鹭, Elite, ~1.76 m): deep tidal-indigo/teal plumage with sharp pale seafoam-ivory
    shear-stripes, swept-back twin blade crown crest, broader scythe-edged wings, and V-forked
    scissor-blade twin tail.
    14 in-place clips: 6 core + EL04SweepRaise/Hold/Release/Cancel + EL04StepRaise/Hold/Release/Cancel
    (EL04-B 公开侧步: strictly ground-stepping crane-step telegraph in-place, NO beak sweep inside Step!).
- Non-degenerate pole UVs on every solid (uv_zero_area_faces = 0, uv_oob_pct = 0.0).
- Strictly <=4 normalized weights, 0 degenerate faces, 0 root XY drift.
- Verifies first_frame_z, last_frame_z, half_frame_min_z on ALL clips in both .blend and clean-imported .glb,
  and renders 8-pose proofs, Down f30 Z=0 side contact proofs, and ortho board-scale pair comparison
  (EN07 SweepHold vs EL04 SweepHold vs EL04 StepHold).
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
from mathutils import Euler, Vector

SPECS = {
    "EN07": {
        "name": "葬铃鹭",
        "move": "EN07-A 扫喙 (W1, front 3 adj hexes max 1 target; strictly in-place, no push fabrication)",
        "scale": 1.0,
        "clips": [
            ("EN07Idle", 48),
            ("EN07Walk", 24),
            ("EN07Stop", 18),
            ("EN07Attack", 24),
            ("EN07Hit", 18),
            ("EN07Down", 30),
            ("EN07SweepRaise", 18),
            ("EN07SweepHold", 36),
            ("EN07SweepRelease", 24),
            ("EN07SweepCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EN07Idle", 12),
            ("1_walk", "EN07Walk", 6),
            ("2_attack", "EN07Attack", 12),
            ("3_sweep_raise", "EN07SweepRaise", 14),
            ("4_sweep_hold", "EN07SweepHold", 18),
            ("5_sweep_release", "EN07SweepRelease", 11),
            ("6_sweep_cancel", "EN07SweepCancel", 9),
            ("7_down_end", "EN07Down", 30),
        ],
    },
    "EL04": {
        "name": "剪潮鹭",
        "move": "EL04-B 公开侧步 (ground step in-place) -> EN07-A 扫喙 (separate sweep clips)",
        "scale": 1.11,
        "clips": [
            ("EL04Idle", 48),
            ("EL04Walk", 24),
            ("EL04Stop", 18),
            ("EL04Attack", 24),
            ("EL04Hit", 18),
            ("EL04Down", 30),
            ("EL04SweepRaise", 18),
            ("EL04SweepHold", 36),
            ("EL04SweepRelease", 24),
            ("EL04SweepCancel", 18),
            ("EL04StepRaise", 18),
            ("EL04StepHold", 36),
            ("EL04StepRelease", 24),
            ("EL04StepCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EL04Idle", 12),
            ("1_walk", "EL04Walk", 6),
            ("2_step_hold", "EL04StepHold", 18),
            ("3_step_release", "EL04StepRelease", 11),
            ("4_sweep_hold", "EL04SweepHold", 18),
            ("5_sweep_release", "EL04SweepRelease", 11),
            ("6_step_cancel", "EL04StepCancel", 9),
            ("7_down_end", "EL04Down", 30),
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


def generate_heron_texture(out_path: Path, kind: str, size: int = 512) -> str:
    """Generate P04B warm-frontier 4-band heron atlas (PNG row 0 = UV v=1.0).
    Bands:
      v in [0.00, 0.25): Wading legs & feet (dark marsh-slate scales)
      v in [0.25, 0.54): Body & neck plumage (EN07 wet slate-ash vs EL04 deep tidal-indigo + ivory collar)
      v in [0.54, 0.80): Wings, tail & crest plumes (EN07 muted wet-grey vs EL04 deep tidal + seafoam shear-stripes)
      v in [0.80, 1.00]: Beak, eyes & EN07 bronze funeral-bell sac (0.80..0.90 bronze/amber, 0.90..1.00 sharp beak)
    """
    buf = bytearray(size * size * 3)
    is_elite = (kind == "EL04")
    for py in range(size):
        v = 1.0 - (py / (size - 1))
        for px in range(size):
            u = px / (size - 1)
            feather = 0.5 + 0.3 * math.sin(u * math.pi * 22.0 + v * 34.0) + 0.2 * math.cos(v * 52.0)

            if v < 0.25:
                # Wading legs: damp marsh-slate (EN07) vs dark tidal-bronze (EL04)
                k = v / 0.25
                if is_elite:
                    r, g, b = 52 + 24 * k, 64 + 26 * k, 68 + 22 * k
                else:
                    r, g, b = 74 + 24 * k, 76 + 22 * k, 70 + 20 * k
            elif v < 0.54:
                # Torso, neck & head plumage
                k = (v - 0.25) / 0.29
                if is_elite:
                    # Deep tidal-indigo/teal back with crisp pale seafoam breast accent
                    r = 36 + 34 * k + 14 * feather
                    g = 64 + 48 * k + 16 * feather
                    b = 78 + 42 * k + 14 * feather
                    if 0.62 < u < 0.88 and k > 0.35:
                        # Pale seafoam throat/breast stripe facing -Y
                        r = r * 0.35 + 216 * 0.65
                        g = g * 0.35 + 224 * 0.65
                        b = b * 0.35 + 212 * 0.65
                else:
                    # Low-saturation wet slate-ash & damp parchment
                    r = 104 + 46 * k + 14 * feather
                    g = 110 + 44 * k + 14 * feather
                    b = 106 + 38 * k + 12 * feather
                # Glowing amber-gold avian eyes near u=0.67 & 0.83, v=0.47
                for eye_u in (0.67, 0.83):
                    du = ((u - eye_u + 0.5) % 1.0) - 0.5
                    dv = (v - 0.47) * 1.6
                    ed = math.hypot(du * 4.8, dv * 4.8)
                    if ed < 0.14:
                        ek = max(0.0, 1.0 - ed / 0.14) ** 1.2
                        r = r * (1.0 - ek) + 244 * ek
                        g = g * (1.0 - ek) + 190 * ek
                        b = b * (1.0 - ek) + 64 * ek
            elif v < 0.80:
                # Wings, tail & crest plumes
                k = (v - 0.54) / 0.26
                if is_elite:
                    # Deep tidal slate with sharp high-contrast pale seafoam-ivory shear-edge!
                    if k > 0.72:
                        r, g, b = 224 + 18 * feather, 232 + 14 * feather, 218 + 14 * feather
                    else:
                        r = 28 + 26 * k + 12 * feather
                        g = 54 + 38 * k + 14 * feather
                        b = 68 + 38 * k + 12 * feather
                else:
                    # Wet ash-grey wing feathers with darker damp tips
                    r = 92 + 34 * (1.0 - k) + 12 * feather
                    g = 98 + 32 * (1.0 - k) + 12 * feather
                    b = 96 + 28 * (1.0 - k) + 10 * feather
            else:
                # v >= 0.80: bronze bell sac (0.80..0.90) & long sweeping beak (0.90..1.00)
                if v < 0.90:
                    k = (v - 0.80) / 0.10
                    # Oxidized funeral bronze bell sac (EN07) / warm brass ornament (EL04)
                    r = 126 + 52 * k + 10 * feather
                    g = 104 + 42 * k + 10 * feather
                    b = 66 + 26 * k + 8 * feather
                else:
                    k = (v - 0.90) / 0.10
                    if is_elite:
                        # Sharp ivory-brass shear-beak
                        r, g, b = 186 + 44 * k, 168 + 40 * k, 114 + 34 * k
                    else:
                        # Pale bone-ochre & dark-tipped heron beak
                        r, g, b = 154 + 36 * (1.0 - k), 140 + 30 * (1.0 - k), 104 + 22 * (1.0 - k)

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
    rot_m = rot_euler.to_matrix() if rot_euler else None
    n_rings = len(profile)
    v_span = v_max - v_min
    v_margin = min(0.014, v_span * 0.10)
    v_lo, v_hi = v_min + v_margin, v_max - v_margin

    def xform(pt: Vector) -> Vector:
        return center + (rot_m @ pt if rot_m else pt)

    rings = []
    for ri, (rad, lz) in enumerate(profile):
        vv = v_lo + (ri / max(1, n_rings - 1)) * (v_hi - v_lo)
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
    vec = p1 - p0
    length = vec.length
    if length < 1e-5:
        return
    rot_q = Vector((0.0, 0.0, 1.0)).rotation_difference(vec.normalized())
    prof = [
        (r0 * 0.72, -r0 * 0.30),
        (r0, 0.0),
        (0.5 * (r0 + r1), length * 0.5),
        (r1, length),
        (r1 * 0.72, length + r1 * 0.30),
    ]
    add_lathe_part(
        bm, uv_layer, prof, p0, v_min, v_max, n_rad=n_rad,
        squish_x=squish_x, squish_y=squish_y, rot_euler=rot_q.to_euler("XYZ"),
        part_tag=part_tag, vert_tags=vert_tags,
    )


def build_heron_mesh(kind: str, tex_path: Path) -> tuple[bpy.types.Object, dict[int, str], dict[str, Vector]]:
    """Build shared wading-heron base + EN07 bell-sac OR EL04 scissor-tail/crest/scythe-wings."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    vert_tags: dict[int, str] = {}
    sc = SPECS[kind]["scale"]
    is_elite = (kind == "EL04")

    def S(x: float, y: float, z: float) -> Vector:
        return Vector((x * sc, y * sc, z * sc))

    # Exact shared heron joint coordinates
    j = {
        "hips": S(0.0, 0.04, 0.76),
        "body": S(0.0, -0.06, 0.90),
        "neck_01": S(0.0, -0.18, 1.02),
        "neck_02": S(0.0, -0.10, 1.24),
        "head": S(0.0, -0.22, 1.44),
        "beak_tip": S(0.0, -0.78 if is_elite else -0.68, 1.38),
        "hip_l": S(0.11, 0.04, 0.76),
        "knee_l": S(0.12, 0.08, 0.42),
        "foot_l": S(0.12, 0.02, 0.03),
        "hip_r": S(-0.11, 0.04, 0.76),
        "knee_r": S(-0.12, 0.08, 0.42),
        "foot_r": S(-0.12, 0.02, 0.03),
        "wing_l": S(0.18, -0.04, 0.96),
        "wing_l_tip": S(0.36 if is_elite else 0.28, 0.48 if is_elite else 0.36, 0.78 if is_elite else 0.72),
        "wing_r": S(-0.18, -0.04, 0.96),
        "wing_r_tip": S(-0.36 if is_elite else -0.28, 0.48 if is_elite else 0.36, 0.78 if is_elite else 0.72),
        "tail": S(0.0, 0.24, 0.80),
        "tail_tip": S(0.0, 0.76 if is_elite else 0.56, 0.66 if is_elite else 0.68),
    }

    # 1. Long slender wading heron legs + 3-toe wading feet planted on Z=0
    for side, hk, kk, fk, ut, lt in (
        (1.0, "hip_l", "knee_l", "foot_l", "leg_u.L", "leg_l.L"),
        (-1.0, "hip_r", "knee_r", "foot_r", "leg_u.R", "leg_l.R"),
    ):
        add_limb_between(bm, uv_layer, j[hk], j[kk], 0.055 * sc, 0.030 * sc, 0.02, 0.23, n_rad=10, part_tag=ut, vert_tags=vert_tags)
        add_limb_between(bm, uv_layer, j[kk], j[fk], 0.028 * sc, 0.024 * sc, 0.02, 0.23, n_rad=10, part_tag=lt, vert_tags=vert_tags)
        # Splayed 3-toe wading foot flat at Z=0 (tiny Z/offset stagger prevents coplanar cap z-fighting)
        fp = j[fk]
        for ti, (dx, dy) in enumerate(((0.0, -0.15), (0.09, -0.11), (-0.09, -0.11), (0.0, 0.10))):
            z_off = (0.014 + ti * 0.0025) * sc
            add_limb_between(
                bm, uv_layer,
                Vector((fp.x + dx * 0.14 * sc, fp.y + dy * 0.14 * sc, z_off)),
                Vector((fp.x + dx * sc, fp.y + dy * sc, z_off - 0.002 * sc)),
                0.016 * sc, 0.009 * sc, 0.02, 0.23, n_rad=6, part_tag=lt, vert_tags=vert_tags,
            )

    # 2. Feathered ovoid heron torso (angled gracefully forward-up)
    add_limb_between(
        bm, uv_layer, j["tail"], j["neck_01"],
        0.13 * sc, 0.20 * sc, 0.26, 0.52, n_rad=14, squish_x=0.92, squish_y=1.18,
        part_tag="body", vert_tags=vert_tags,
    )

    # 3. Iconic S-folded articulated heron neck (`neck_01` -> `neck_02` -> `head`)
    add_limb_between(bm, uv_layer, j["neck_01"], j["neck_02"], 0.095 * sc, 0.072 * sc, 0.26, 0.52, n_rad=12, part_tag="neck_01", vert_tags=vert_tags)
    add_limb_between(bm, uv_layer, j["neck_02"], j["head"], 0.070 * sc, 0.068 * sc, 0.26, 0.52, n_rad=12, part_tag="neck_02", vert_tags=vert_tags)

    # 4. Sculpted avian head + long sharp sweeping beak (-Y)
    add_lathe_part(
        bm, uv_layer,
        [(0.055 * sc, -0.06 * sc), (0.098 * sc, 0.0), (0.092 * sc, 0.07 * sc), (0.045 * sc, 0.12 * sc)],
        j["head"], 0.26, 0.53, n_rad=12, squish_x=0.88, squish_y=1.22,
        part_tag="head", vert_tags=vert_tags,
    )
    add_limb_between(
        bm, uv_layer, j["head"] + S(0.0, -0.08, 0.01), j["beak_tip"],
        0.046 * sc, 0.008 * sc, 0.91, 0.99, n_rad=8, squish_x=0.65,
        part_tag="beak", vert_tags=vert_tags,
    )

    # 5. Folded/flaring feathered wings (`wing.L` / `wing.R`)
    for side, wk, wtk, tag in ((1.0, "wing_l", "wing_l_tip", "wing.L"), (-1.0, "wing_r", "wing_r_tip", "wing.R")):
        # Main wing blade
        add_limb_between(
            bm, uv_layer, j[wk], j[wtk],
            0.13 * sc if is_elite else 0.11 * sc,
            0.032 * sc, 0.55, 0.79, n_rad=10, squish_x=0.38, squish_y=1.35,
            part_tag=tag, vert_tags=vert_tags,
        )
        if is_elite:
            # EL04 sharp upper scythe-feather edge flaring outward!
            add_limb_between(
                bm, uv_layer, j[wk] + S(side * 0.04, 0.06, 0.06),
                j[wtk] + S(side * 0.18, 0.14, 0.14),
                0.085 * sc, 0.014 * sc, 0.68, 0.79, n_rad=8, squish_x=0.28,
                part_tag=tag, vert_tags=vert_tags,
            )

    # 6. Role-specific signature silhouette features!
    if not is_elite:
        # EN07 (葬铃鹭): Hanging oxidized-bronze funeral-bell throat sac + soft rounded tail
        bell_top = j["neck_01"] + S(0.0, -0.08, -0.04)
        add_lathe_part(
            bm, uv_layer,
            [(0.095 * sc, -0.22 * sc), (0.115 * sc, -0.14 * sc), (0.085 * sc, -0.04 * sc), (0.045 * sc, 0.02 * sc)],
            bell_top, 0.81, 0.89, n_rad=12, part_tag="bell_sac", vert_tags=vert_tags,
        )
        # Soft rounded tail fan
        add_limb_between(
            bm, uv_layer, j["tail"], j["tail_tip"],
            0.10 * sc, 0.04 * sc, 0.55, 0.76, n_rad=10, squish_x=1.4, squish_y=0.45,
            part_tag="tail", vert_tags=vert_tags,
        )
    else:
        # EL04 (剪潮鹭, Elite): Swept-back twin blade crown crest + V-forked scissor-blade twin tail!
        for side in (1.0, -1.0):
            # Sharp twin blade crown plumes sweeping back from head
            add_limb_between(
                bm, uv_layer,
                j["head"] + S(side * 0.04, 0.02, 0.09),
                j["head"] + S(side * 0.16, 0.34, 0.24),
                0.042 * sc, 0.008 * sc, 0.68, 0.79, n_rad=8, squish_x=0.35,
                part_tag="head", vert_tags=vert_tags,
            )
            # Twin V-forked scissor-tail blades extending cleanly back (+Y)
            add_limb_between(
                bm, uv_layer,
                j["tail"] + S(side * 0.03, 0.02, 0.0),
                j["tail_tip"] + S(side * 0.24, 0.12, 0.06),
                0.068 * sc, 0.012 * sc, 0.66, 0.79, n_rad=8, squish_x=0.35,
                part_tag="tail", vert_tags=vert_tags,
            )
        # Chest tide-blade crest plate
        add_limb_between(
            bm, uv_layer, j["neck_01"] + S(0.0, -0.10, -0.02), j["neck_01"] + S(0.0, -0.16, -0.22),
            0.065 * sc, 0.020 * sc, 0.81, 0.89, n_rad=8, part_tag="body", vert_tags=vert_tags,
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

    mat = bpy.data.materials.new(f"Mat_{kind}_Heron")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(tex_path), check_existing=True)
    img.name = f"{kind}_Heron_Image"
    img.pack()
    tex_node.image = img
    nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.62
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.34
    obj.data.materials.append(mat)
    return obj, vert_tags, j


def build_heron_armature(kind: str, mesh_obj: bpy.types.Object, vert_tags: dict[int, str], j: dict[str, Vector]) -> bpy.types.Object:
    """Create shared 14-bone wading-heron armature."""
    arm_data = bpy.data.armatures.new(f"RIG_{kind}_Data")
    arm = bpy.data.objects.new(f"RIG_{kind}", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def add_bone(name: str, head: Vector, tail: Vector, parent: str | None = None):
        b = eb.new(name)
        b.head = head
        b.tail = tail
        if parent:
            b.parent = eb[parent]
        return b

    add_bone("root", Vector((0.0, 0.0, 0.0)), Vector((0.0, -0.20, 0.0)), None)
    add_bone("hips", j["hips"], j["body"], "root")
    add_bone("body", j["body"], j["neck_01"], "hips")
    add_bone("neck_01", j["neck_01"], j["neck_02"], "body")
    add_bone("neck_02", j["neck_02"], j["head"], "neck_01")
    add_bone("head", j["head"], j["head"] + Vector((0.0, -0.14, 0.02)), "neck_02")
    add_bone("beak", j["head"] + Vector((0.0, -0.08, 0.01)), j["beak_tip"], "head")

    add_bone("wing.L", j["wing_l"], j["wing_l_tip"], "body")
    add_bone("wing.R", j["wing_r"], j["wing_r_tip"], "body")
    add_bone("tail", j["tail"], j["tail_tip"], "body")

    add_bone("leg_u.L", j["hip_l"], j["knee_l"], "hips")
    add_bone("leg_l.L", j["knee_l"], j["foot_l"], "leg_u.L")
    add_bone("leg_u.R", j["hip_r"], j["knee_r"], "hips")
    add_bone("leg_l.R", j["knee_r"], j["foot_r"], "leg_u.R")

    if kind == "EN07":
        add_bone("bell_sac", j["neck_01"] + Vector((0.0, -0.08, -0.04)), j["neck_01"] + Vector((0.0, -0.08, -0.26)), "body")

    bpy.ops.object.mode_set(mode="OBJECT")

    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    vgs = {b.name: mesh_obj.vertex_groups.new(name=b.name) for b in arm.data.bones}
    for v in mesh_obj.data.vertices:
        tag = vert_tags.get(v.index, "body")
        vgs[tag if tag in vgs else "body"].add([v.index], 1.0, "REPLACE")

    return arm


def set_heron_pose(arm: bpy.types.Object, kind: str, clip: str, t: float) -> None:
    """Strictly grounded in-place animations for EN07 and EL04 (ZERO flying, ZERO root XY drift)."""
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")

    s2 = math.sin(t * math.pi * 2.0)
    c2 = math.cos(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)
    is_elite = (kind == "EL04")
    suffix = clip[4:]  # Idle, Walk, Stop, Attack, Hit, Down, SweepRaise/Hold/Release/Cancel, StepRaise/Hold/Release/Cancel

    def r(bn: str, x: float, y: float = 0.0, z: float = 0.0) -> None:
        if bn in pbs:
            pbs[bn].rotation_euler = Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ")

    def base_stance(breath: float = 0.0) -> None:
        # Elite holds wings slightly flared & proud; Normal stalks slightly hunched with swinging bell sac
        w_flare = 16.0 if is_elite else 5.0
        r("body", (4.0 if not is_elite else -2.0) + 2.0 * breath, 0.0, 0.0)
        r("neck_01", (8.0 if not is_elite else 2.0) + 3.0 * breath, 0.0, 0.0)
        r("neck_02", -6.0 - 2.0 * breath, 0.0, 0.0)
        r("head", -4.0, 0.0, 0.0)
        r("wing.L", 0.0, 0.0, w_flare + 3.0 * breath)
        r("wing.R", 0.0, 0.0, -w_flare - 3.0 * breath)
        r("tail", -4.0 * breath, 0.0, 0.0)
        r("bell_sac", 6.0 * breath, 0.0, 4.0 * c2)

    if suffix == "Idle":
        base_stance(s2)

    elif suffix == "Walk":
        base_stance(0.0)
        r("hips", 4.0, 5.0 * s2, 4.0 * c2)
        r("neck_01", 8.0 + 10.0 * c2, 0.0, 0.0)
        r("head", -8.0 - 8.0 * c2, 0.0, 0.0)
        r("leg_u.L", 22.0 * s2, 0.0, 0.0)
        r("leg_l.L", -24.0 * max(0.0, s2), 0.0, 0.0)
        r("leg_u.R", -22.0 * s2, 0.0, 0.0)
        r("leg_l.R", -24.0 * max(0.0, -s2), 0.0, 0.0)
        r("bell_sac", 12.0 * s2, 0.0, 10.0 * c2)

    elif suffix == "Stop":
        w = (1.0 - t) ** 1.5
        base_stance(0.0)
        r("body", 10.0 * w, 0.0, 0.0)
        r("neck_01", 12.0 * w, 0.0, 0.0)

    elif suffix == "Attack":
        # Crisp forward heron beak-jab lunge
        coil = math.sin(min(1.0, t / 0.35) * math.pi) if t < 0.35 else 0.0
        jab = math.sin(min(1.0, max(0.0, (t - 0.25) / 0.45)) * math.pi)
        base_stance(0.0)
        r("body", -10.0 * coil + 18.0 * jab, 0.0, 0.0)
        r("neck_01", -24.0 * coil + 32.0 * jab, 0.0, 0.0)
        r("neck_02", 26.0 * coil - 26.0 * jab, 0.0, 0.0)
        r("head", -10.0 * coil + 8.0 * jab, 0.0, 0.0)
        r("wing.L", 0.0, 0.0, 24.0 * jab + 10.0)
        r("wing.R", 0.0, 0.0, -24.0 * jab - 10.0)

    elif suffix == "Hit":
        base_stance(0.0)
        r("body", -18.0 * s1, 0.0, 12.0 * s2)
        r("neck_01", -22.0 * s1, 0.0, -14.0 * s2)
        r("wing.L", 0.0, 0.0, 32.0 * s1)
        r("wing.R", 0.0, 0.0, -32.0 * s1)

    elif suffix == "Down":
        # Grounded flat collapse onto belly/side on Z=0; neck & beak angled horizontal so torso rests flat!
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        r("hips", 86.0 * w, 10.0 * w, 8.0 * w)
        r("body", 4.0 * w, 0.0, 6.0 * w)
        r("neck_01", -34.0 * w, 0.0, 14.0 * w)
        r("neck_02", -28.0 * w, 0.0, 12.0 * w)
        r("head", -22.0 * w, 0.0, 14.0 * w)
        r("beak", -12.0 * w, 0.0, 0.0)
        r("leg_u.L", -64.0 * w, 0.0, 12.0 * w)
        r("leg_l.L", 78.0 * w, 0.0, 0.0)
        r("leg_u.R", -60.0 * w, 0.0, -12.0 * w)
        r("leg_l.R", 74.0 * w, 0.0, 0.0)
        r("wing.L", 0.0, 0.0, 26.0 * w)
        r("wing.R", 0.0, 0.0, -26.0 * w)

    elif suffix == "SweepRaise":
        # EN07-A 扫喙起蓄: coils neck back & right (-X), crouches slightly, wings flare low for balance
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        base_stance(0.0)
        r("hips", 10.0 * w, 0.0, -18.0 * w)
        r("body", 10.0 * w, 0.0, -16.0 * w)
        r("neck_01", -28.0 * w, 0.0, -22.0 * w)
        r("neck_02", 24.0 * w, 0.0, -14.0 * w)
        r("head", 12.0 * w, 0.0, 14.0 * w)
        r("wing.L", 0.0, 0.0, 34.0 * w + (16.0 if is_elite else 5.0))
        r("wing.R", 0.0, 0.0, -34.0 * w - (16.0 if is_elite else 5.0))
        r("bell_sac", 16.0 * w, 0.0, -16.0 * w)

    elif suffix == "SweepHold":
        # EN07-A 扫喙蓄势保持: taut coiled S-neck cocked right, wide balance wings
        base_stance(0.0)
        r("hips", 10.0 + 2.0 * s2, 0.0, -18.0 + 2.0 * c2)
        r("body", 10.0, 0.0, -16.0)
        r("neck_01", -28.0 + 3.0 * s2, 0.0, -22.0)
        r("neck_02", 24.0 - 2.0 * s2, 0.0, -14.0)
        r("head", 12.0, 0.0, 14.0)
        r("wing.L", 0.0, 0.0, 34.0 + 4.0 * s2 + (16.0 if is_elite else 5.0))
        r("wing.R", 0.0, 0.0, -34.0 - 4.0 * s2 - (16.0 if is_elite else 5.0))
        r("bell_sac", 16.0, 0.0, -16.0 + 6.0 * s2)

    elif suffix == "SweepRelease":
        # EN07-A 扫喙释放: explosive wide horizontal beak sweep across front 3 hexes (-X -> +X, in-place!)
        base_stance(0.0)
        if t < 0.18:
            k = t / 0.18
            yaw = -18.0 - 10.0 * k
            pitch = 10.0
        elif t < 0.62:
            k = (t - 0.18) / 0.44
            ks = k * k * (3.0 - 2.0 * k)
            yaw = -28.0 + 88.0 * ks  # -28 -> +60 deg wide beak sweep!
            pitch = 10.0 + 18.0 * math.sin(k * math.pi)
        else:
            k = (t - 0.62) / 0.38
            yaw = 60.0 * (1.0 - k)
            pitch = 10.0 * (1.0 - k)
        r("hips", pitch * 0.5, 0.0, yaw * 0.45)
        r("body", pitch * 0.8, 0.0, yaw * 0.60)
        r("neck_01", 18.0 * (1.0 - abs(yaw) / 70.0), 0.0, yaw * 0.55)
        r("neck_02", -12.0, 0.0, yaw * 0.40)
        r("head", -6.0, 0.0, yaw * 0.20)
        r("wing.L", 0.0, 0.0, 38.0 + (16.0 if is_elite else 5.0))
        r("wing.R", 0.0, 0.0, -38.0 - (16.0 if is_elite else 5.0))
        r("bell_sac", 12.0, 0.0, yaw * 0.6)

    elif suffix == "SweepCancel":
        w = 1.0 - t
        w = w * w * (3.0 - 2.0 * w)
        base_stance(0.0)
        r("hips", 10.0 * w, 0.0, -18.0 * w)
        r("body", 10.0 * w, 0.0, -16.0 * w)
        r("neck_01", -28.0 * w, 0.0, -22.0 * w)
        r("neck_02", 24.0 * w, 0.0, -14.0 * w)
        r("head", 12.0 * w, 0.0, 14.0 * w)
        r("wing.L", 0.0, 0.0, 34.0 * w + (16.0 if is_elite else 5.0))
        r("wing.R", 0.0, 0.0, -34.0 * w - (16.0 if is_elite else 5.0))

    elif suffix == "StepRaise":
        # EL04-B 公开侧步起蓄: poised lateral crane-step (left leg abducts outward + lifts cleanly, NO sweep!)
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        base_stance(0.0)
        r("hips", 4.0 * w, -10.0 * w, 0.0)
        r("body", -4.0 * w, 8.0 * w, 0.0)
        r("leg_u.L", -46.0 * w, -24.0 * w, -18.0 * w)
        r("leg_l.L", 62.0 * w, 0.0, 0.0)
        r("wing.L", 0.0, -10.0 * w, 24.0 * w + 16.0)
        r("wing.R", 0.0, 10.0 * w, -24.0 * w - 16.0)

    elif suffix == "StepHold":
        # EL04-B 公开侧步蓄势保持: unmistakable poised one-legged lateral ground-step stance
        base_stance(0.0)
        r("hips", 4.0, -10.0 + 2.0 * s2, 0.0)
        r("body", -4.0, 8.0 - 2.0 * s2, 0.0)
        r("leg_u.L", -46.0 + 4.0 * s2, -24.0, -18.0)
        r("leg_l.L", 62.0 - 4.0 * s2, 0.0, 0.0)
        r("wing.L", 0.0, -10.0, 40.0 + 3.0 * s2)
        r("wing.R", 0.0, 10.0, -40.0 - 3.0 * s2)

    elif suffix == "StepRelease":
        # EL04-B 公开侧步释放: crisp ground-step plant & lateral weight-shift recovery in-place (NO sweep!)
        base_stance(0.0)
        if t < 0.45:
            k = t / 0.45
            ks = k * k * (3.0 - 2.0 * k)
            lift = 1.0 - ks
            lean = -10.0 * (1.0 - ks) + 10.0 * ks
        else:
            k = (t - 0.45) / 0.55
            lift = 0.0
            lean = 10.0 * (1.0 - k)
        r("hips", 4.0 * lift, lean, 0.0)
        r("body", -4.0 * lift, -lean * 0.8, 0.0)
        r("leg_u.L", -46.0 * lift, -24.0 * lift, -18.0 * lift)
        r("leg_l.L", 62.0 * lift, 0.0, 0.0)
        r("leg_u.R", -14.0 * max(0.0, lean / 10.0), 0.0, -10.0 * max(0.0, lean / 10.0))
        r("leg_l.R", 18.0 * max(0.0, lean / 10.0), 0.0, 0.0)
        r("wing.L", 0.0, 0.0, 16.0 + 22.0 * lift)
        r("wing.R", 0.0, 0.0, -16.0 - 22.0 * lift)

    elif suffix == "StepCancel":
        w = 1.0 - t
        w = w * w * (3.0 - 2.0 * w)
        base_stance(0.0)
        r("hips", 4.0 * w, -10.0 * w, 0.0)
        r("body", -4.0 * w, 8.0 * w, 0.0)
        r("leg_u.L", -46.0 * w, -24.0 * w, -18.0 * w)
        r("leg_l.L", 62.0 * w, 0.0, 0.0)
        r("wing.L", 0.0, -10.0 * w, 24.0 * w + 16.0)
        r("wing.R", 0.0, 10.0 * w, -24.0 * w - 16.0)


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
    cam_data.ortho_scale = 2.65
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((2.0, -3.2, 2.05))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.78)) - cam.location).to_track_quat("-Z", "Y").to_euler()
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
    floor_slab.scale = (4.2, 4.2, 0.04)
    fmat = bpy.data.materials.new("ProofFloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor_slab.data.materials.append(fmat)

    scene.render.resolution_x = 720
    scene.render.resolution_y = 400
    cam_data.ortho_scale = 2.45
    cam.location = Vector((3.4, 0.0, 0.42))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.34)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions[f"{kind}Down"])
    scene.frame_set(30)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / f"{kind}_down_ground_contact_side.png")
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(floor_slab, do_unlink=True)


def build_single_heron(kind: str, out_enemies_dir: Path, out_evidence_dir: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24

    spec = SPECS[kind]
    out_blend = out_evidence_dir / f"{kind}_Board.blend"
    out_glb = out_enemies_dir / f"{kind}_Board.glb"
    tex_path = out_evidence_dir / f"{kind}_Heron_Tex.png"
    tex_sha = generate_heron_texture(tex_path, kind, size=512)

    mesh, vert_tags, j = build_heron_mesh(kind, tex_path)
    arm = build_heron_armature(kind, mesh, vert_tags, j)

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
            set_heron_pose(arm, kind, cname, t)
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

    clip_qa = {}
    worst_min_z, worst_clip, worst_fr, total_sub3, max_xy_all = 999.0, "", 0.0, 0, 0.0
    for cname, n_frames in spec["clips"]:
        activate_action(arm, bpy.data.actions[cname])
        q = measure_clip_floor(arm, mesh, deps, scene, hips_rest_head, 1.0, float(n_frames))
        clip_qa[cname] = q
        if q["half_frame_min_z"] < worst_min_z:
            worst_min_z, worst_clip, worst_fr = q["half_frame_min_z"], cname, q["half_frame_worst"]
        total_sub3 += q["samples_below_neg_3cm"]
        max_xy_all = max(max_xy_all, q["max_root_xy_drift_m"])

    hf_summary = {
        "worst_min_z": round(worst_min_z, 6),
        "worst_clip": worst_clip,
        "worst_frame": worst_fr,
        "samples_below_neg_3cm": total_sub3,
        "max_root_xy_drift_m": round(max_xy_all, 6),
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
        "actions": dict(sorted(re_actions.items())),
        "clip_floor": re_floor,
    }

    return {
        "kind": kind,
        "name": spec["name"],
        "move": spec["move"],
        "rest_dimensions": rest_dims,
        "embedded_texture": {
            "name": f"{kind}_Heron_Image",
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


def render_herons_comparison(en07_glb: Path, el04_glb: Path, out_evidence_dir: Path) -> None:
    """Render 3-way ortho board comparison: EN07 (SweepHold) | EL04 (SweepHold) | EL04 (StepHold)."""
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
    floor.scale = (8.5, 4.5, 0.04)
    fmat = bpy.data.materials.new("FloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor.data.materials.append(fmat)

    for glb_p, x_off, clip_name, fr in (
        (en07_glb, -1.75, "EN07SweepHold", 18),
        (el04_glb, 0.0, "EL04SweepHold", 18),
        (el04_glb, 1.75, "EL04StepHold", 18),
    ):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb_p))
        added = [o for o in bpy.data.objects if o not in before]
        for o in added:
            if o.parent is None:
                o.location.x += x_off
            if o.type == "ARMATURE":
                act = next((a for a in bpy.data.actions if a.name.startswith(clip_name)), None)
                if act:
                    activate_action(o, act)
        scene.frame_set(fr)
        bpy.context.view_layer.update()

    cam_data = bpy.data.cameras.new("CmpCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 5.2
    cam = bpy.data.objects.new("CmpCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -5.6, 3.0))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.82)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    scene.render.resolution_x = 1080
    scene.render.resolution_y = 480
    scene.render.filepath = str(out_evidence_dir / "Herons_pair_silhouette_compare.png")
    bpy.ops.render.render(write_still=True)

    # Small board-scale ortho readability (1280x720 P04B equivalent)
    cam_data.ortho_scale = 13.0
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.filepath = str(out_evidence_dir / "Herons_pair_small_scale_readability.png")
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = parse_args()
    out_enemies = Path(args.out_enemies_dir)
    out_ev = Path(args.out_evidence_dir)
    out_ev.mkdir(parents=True, exist_ok=True)

    rep_07 = build_single_heron("EN07", out_enemies, out_ev)
    rep_04 = build_single_heron("EL04", out_enemies, out_ev)
    render_herons_comparison(out_enemies / "EN07_Board.glb", out_enemies / "EL04_Board.glb", out_ev)

    full = {
        "batch": "#15 lake herons (EN07 & EL04)",
        "recipe_origin": "100% local procedural Blender Python shared heron body/rig recipe",
        "EN07": rep_07,
        "EL04": rep_04,
    }
    (out_ev / "herons_build_report.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("HERONS_BUILD_OK:", json.dumps({
        "EN07": {
            "tris": rep_07["roundtrip"]["total_tris"],
            "actions": rep_07["roundtrip"]["action_count"],
            "hf": rep_07["half_frame_summary"],
            "down_blend_last_z": rep_07["clip_qa"]["EN07Down"]["last_frame_z"],
            "down_glb_last_z": rep_07["roundtrip"]["clip_floor"]["EN07Down"]["last_frame_z"],
        },
        "EL04": {
            "tris": rep_04["roundtrip"]["total_tris"],
            "actions": rep_04["roundtrip"]["action_count"],
            "hf": rep_04["half_frame_summary"],
            "down_blend_last_z": rep_04["clip_qa"]["EL04Down"]["last_frame_z"],
            "down_glb_last_z": rep_04["roundtrip"]["clip_floor"]["EL04Down"]["last_frame_z"],
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

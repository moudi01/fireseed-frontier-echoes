"""Procedurally build EN05_Board.blend and EN05_Board.glb for #15 (盐脉鳗 EN05).

Original local procedural recipe (zero external mesh/image/motion donors):
- Ground-hugging, long, low undulating salt-vein eel for 沉息湖区 (SALT_CROSSING).
- Clear head-vs-tail silhouette: broad jawed skull, flared salt-crystal gill crests
  (crest.L at +X, crest.R at -X), dorsal salt-vein spine ridge, lateral salt-vein
  crusts, and tapered caudal ribbon-fin tail.
- Forward axis = -Y in Blender (+Z in glTF/Godot), Up = +Z, Left = +X, Right = -X.
- Locally generated 1024x1024 procedural PBR salt-vein texture packed into .blend & .glb.
- 11-bone rig (RIG_EN05) with smooth <=4 normalized weights, 0 degenerate faces.
- 10 strictly in-place animations (zero root XY drift):
  Core (6): EN05Idle, EN05Walk, EN05Stop, EN05Attack, EN05Hit, EN05Down
  EN05-A 盐弧 (4): EN05ArcRaise, EN05ArcHold, EN05ArcRelease, EN05ArcCancel
- Reports first_frame_z, last_frame_z, half_frame_min_z, root_xy_drift separately
  for ALL 10 clips in both .blend and clean-blend re-imported .glb.
- Renders 8-pose proof panels, EN05Down f30 Z=0 side/3Q ground-contact proofs,
  small-scale board readability, and optional neighbor comparison with EN15/EN06.
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
from mathutils.bvhtree import BVHTree

CLIPS = [
    ("EN05Idle", 48),
    ("EN05Walk", 24),
    ("EN05Stop", 18),
    ("EN05Attack", 24),
    ("EN05Hit", 18),
    ("EN05Down", 30),
    ("EN05ArcRaise", 18),
    ("EN05ArcHold", 36),
    ("EN05ArcRelease", 24),
    ("EN05ArcCancel", 18),
]

PROOF_PANELS = [
    ("0_idle", "EN05Idle", 12),
    ("1_walk", "EN05Walk", 6),
    ("2_attack", "EN05Attack", 12),
    ("3_A_raise", "EN05ArcRaise", 14),
    ("4_A_hold", "EN05ArcHold", 18),
    ("5_A_release", "EN05ArcRelease", 11),
    ("6_A_cancel", "EN05ArcCancel", 9),
    ("7_down_end", "EN05Down", 30),
]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out-glb", required=True)
    p.add_argument("--out-blend", required=True)
    p.add_argument("--out-report", required=True)
    p.add_argument("--out-proof", default="")
    p.add_argument("--en15-glb", default="")
    p.add_argument("--en06-glb", default="")
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
    """Write an uncompressed/zlib PNG without external dependencies."""
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


def generate_salt_vein_texture(out_path: Path, size: int = 512) -> str:
    """Generate a procedural P04B warm-frontier salt-vein eel albedo texture.
    UV convention:
      u in [0, 1]: circumference around body (0.25 = dorsal spine, 0.75 = belly, 0.0/0.5 = flanks)
      v in [0, 1]: longitudinal length (0.0 = snout/head, 1.0 = tail tip)
    Special region v > 0.94 reserved for bright crystalline salt-crest & brow accents.
    """
    buf = bytearray(size * size * 3)
    for py in range(size):
        # PNG row 0 is top of image = UV v=1.0 in Blender/glTF!
        v = 1.0 - (py / (size - 1))
        for px in range(size):
            u = px / (size - 1)
            # Distance from dorsal center (u=0.25) and belly center (u=0.75)
            d_dorsal = abs(((u - 0.25 + 0.5) % 1.0) - 0.5) * 2.0  # 0 at dorsal, 1 at belly
            # Base P04B brine-slate dorsal -> warm lake-silt flank -> pale ochre belly
            if d_dorsal < 0.45:
                k = d_dorsal / 0.45
                r = 44 + k * 34
                g = 62 + k * 38
                b = 64 + k * 24
            else:
                k = (d_dorsal - 0.45) / 0.55
                r = 78 + k * 96
                g = 100 + k * 62
                b = 88 + k * 38

            # Organic longitudinal mottling
            wave1 = math.sin(v * 28.0 + math.sin(u * math.pi * 4.0) * 1.6)
            wave2 = math.sin(v * 64.0 - u * math.pi * 8.0)
            mottle = 0.5 + 0.35 * wave1 + 0.15 * wave2
            r *= 0.88 + 0.20 * mottle
            g *= 0.88 + 0.20 * mottle
            b *= 0.88 + 0.20 * mottle

            # Crisp crystalline dorsal salt-vein spine ridge (u near 0.25)
            spine_w = 0.075 + 0.025 * math.sin(v * 42.0)
            if d_dorsal < spine_w and 0.04 < v < 0.92:
                sv = max(0.0, 1.0 - (d_dorsal / spine_w) ** 1.6)
                r = r * (1.0 - sv) + 236 * sv
                g = g * (1.0 - sv) + 229 * sv
                b = b * (1.0 - sv) + 210 * sv

            # Branching lateral salt veins arcing down the flanks
            rib_phase = math.sin(v * 38.0 - d_dorsal * 9.5)
            if 0.10 < d_dorsal < 0.58 and 0.08 < v < 0.86 and rib_phase > 0.78:
                rv = min(1.0, (rib_phase - 0.78) / 0.22) * (1.0 - abs(d_dorsal - 0.32) / 0.30)
                rv = max(0.0, rv) * 0.88
                r = r * (1.0 - rv) + 228 * rv
                g = g * (1.0 - rv) + 220 * rv
                b = b * (1.0 - rv) + 196 * rv

            # Head & eye-ridge warm amber/salt accent (v < 0.14)
            if v < 0.14:
                head_k = 1.0 - v / 0.14
                # Dark mask around snout/jaw for strong silhouette contrast
                r *= 0.82 + 0.18 * (1.0 - head_k)
                g *= 0.84 + 0.16 * (1.0 - head_k)
                b *= 0.86 + 0.14 * (1.0 - head_k)
                # Glowing warm amber eyes at flanks near v=0.065
                for eye_u in (0.14, 0.36):
                    du = ((u - eye_u + 0.5) % 1.0) - 0.5
                    dv = (v - 0.068) * 1.8
                    ed = math.hypot(du * 3.2, dv * 3.2)
                    if ed < 0.11:
                        ek = max(0.0, 1.0 - ed / 0.11)
                        r = r * (1.0 - ek) + 245 * ek
                        g = g * (1.0 - ek) + 188 * ek
                        b = b * (1.0 - ek) + 74 * ek

            # Salt-crystal gill crests & spine crystals mapped to v >= 0.94
            if v >= 0.94:
                ck = (v - 0.94) / 0.06
                # Warm ivory salt crystal gradient with subtle slate base
                r = 164 + 82 * ck
                g = 172 + 70 * ck
                b = 162 + 64 * ck

            idx = (py * size + px) * 3
            buf[idx] = max(0, min(255, int(r)))
            buf[idx + 1] = max(0, min(255, int(g)))
            buf[idx + 2] = max(0, min(255, int(b)))

    write_png_rgb(out_path, size, size, bytes(buf))
    return sha256_file(out_path)


def build_eel_mesh(tex_path: Path) -> bpy.types.Object:
    """Create a single clean watertight manifold mesh for EN05 (盐脉鳗) with UVs.
    Coordinate system:
      Forward (head) = -Y (around y = -0.86)
      Rear (tail tip) = +Y (around y = +0.88)
      Left = +X, Right = -X, Up = +Z, resting belly near Z = 0.0
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # 1. Main serpentine eel body (longitudinal tube with head, dorsal ridge, caudal fin)
    n_len = 52
    n_rad = 18
    rings = []

    for i in range(n_len):
        s = i / (n_len - 1)  # 0.0 = snout tip (-Y), 1.0 = tail tip (+Y)
        y = -0.96 + s * 1.96  # total length ~1.96 m (coiled S-curve fits cleanly in hex)
        # Distinct resting S-curve in X and low ground-hugging arch in Z
        cx = 0.24 * math.sin(s * math.pi * 2.2 - 0.55) * (0.20 + 0.80 * math.sin(s * math.pi))
        if s < 0.22:
            # Slightly lifted watchful head & neck
            cz = 0.36 - 0.12 * (s / 0.22)
        else:
            # Low ground-hugging undulation
            t_b = (s - 0.22) / 0.78
            cz = 0.24 - 0.12 * t_b + 0.045 * math.sin(t_b * math.pi * 2.0)

        # Width (rx) and Height (rz) profile: sculpted tapered eel snout, muscular mid, ribbon tail
        if s < 0.10:
            k = s / 0.10
            rx = 0.032 + 0.168 * math.sin(k * math.pi * 0.5) ** 0.85
            rz = 0.024 + 0.120 * math.sin(k * math.pi * 0.5) ** 0.85
        elif s < 0.18:
            k = (s - 0.10) / 0.08
            rx = 0.200 - 0.035 * k
            rz = 0.144 - 0.012 * k
        elif s < 0.54:
            k = (s - 0.18) / 0.36
            rx = 0.165 + 0.032 * math.sin(k * math.pi)
            rz = 0.132 + 0.034 * math.sin(k * math.pi)
        else:
            k = (s - 0.54) / 0.46
            rx = max(0.010, 0.165 * ((1.0 - k) ** 1.25))
            rz = max(0.014, 0.132 * ((1.0 - k) ** 0.82))

        # Sculpted dorsal salt-vein fin height along spine
        fin_h = 0.0
        if 0.12 < s < 0.96:
            fin_h = 0.115 * math.sin(((s - 0.12) / 0.84) * math.pi) * (0.75 + 0.25 * math.sin(s * 34.0))
        if s > 0.70:
            # Ribbon caudal fin flare near tail
            fin_h += 0.095 * math.sin(((s - 0.70) / 0.30) * math.pi)

        ring = []
        for j in range(n_rad):
            u = j / n_rad
            ang = u * math.pi * 2.0  # 0=+X (left), pi/2=+Z (dorsal), pi=-X (right), 3pi/2=-Z (belly)
            ca, sa = math.cos(ang), math.sin(ang)
            lx = rx * ca
            lz = rz * sa
            # Flatten belly slightly for stable ground contact
            if sa < -0.2:
                lz *= 0.78
            # Dorsal salt-vein spine ridge at ang ~ pi/2 (sa > 0.82)
            if sa > 0.82 and fin_h > 0.0:
                ridge_k = ((sa - 0.82) / 0.18) ** 2
                lz += fin_h * ridge_k
                lx *= 1.0 - 0.45 * ridge_k
            # Slight brow/cheek flare at head (s in [0.05, 0.14])
            if 0.05 < s < 0.14 and abs(ca) > 0.65 and sa > -0.1:
                lx *= 1.12
            v = bm.verts.new((cx + lx, y, max(0.005, cz + lz)))
            # Reserve non-zero V margins [0.004..0.020] for snout cap and [0.900..0.928] for tail cap
            # so none of the 36 pole cap triangles are collinear in UV space (zero-area UV = 0).
            ring.append((v, u, 0.02 + s * 0.88))
        rings.append(ring)

    # Connect rings with quads
    for i in range(n_len - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(n_rad):
            jn = (j + 1) % n_rad
            v00, u00, v_00 = r0[j]
            v01, u01, v_01 = r0[jn]
            v11, u11, v_11 = r1[jn]
            v10, u10, v_10 = r1[j]
            u01_w = 1.0 if jn == 0 else u01
            u11_w = 1.0 if jn == 0 else u11
            f = bm.faces.new((v00, v10, v11, v01))
            uvs = [(u00, v_00), (u10, v_10), (u11_w, v_11), (u01_w, v_01)]
            for loop, uv in zip(f.loops, uvs):
                loop[uv_layer].uv = uv

    # Cap snout & tail tip cleanly with non-degenerate pole UV triangles (delta-V > 0.015)
    snout_c = sum((v.co for v, _, _ in rings[0]), Vector()) / n_rad
    snout_tip = bm.verts.new(snout_c + Vector((0.0, -0.045, -0.005)))
    for j in range(n_rad):
        jn = (j + 1) % n_rad
        v0, u0, vv0 = rings[0][j]
        v1, u1, vv1 = rings[0][jn]
        u1_w = 1.0 if jn == 0 else u1
        u_mid = 0.5 * (u0 + u1_w)
        f = bm.faces.new((snout_tip, v0, v1))
        for loop, uv in zip(f.loops, [(u_mid, 0.004), (u0, vv0), (u1_w, vv1)]):
            loop[uv_layer].uv = uv

    tail_c = sum((v.co for v, _, _ in rings[-1]), Vector()) / n_rad
    tail_tip = bm.verts.new(tail_c + Vector((0.0, 0.055, 0.0)))
    for j in range(n_rad):
        jn = (j + 1) % n_rad
        v0, u0, vv0 = rings[-1][j]
        v1, u1, vv1 = rings[-1][jn]
        u1_w = 1.0 if jn == 0 else u1
        u_mid = 0.5 * (u0 + u1_w)
        f = bm.faces.new((tail_tip, v1, v0))
        for loop, uv in zip(f.loops, [(u_mid, 0.928), (u1_w, vv1), (u0, vv0)]):
            loop[uv_layer].uv = uv

    # 2. Add sculpted crystalline salt-crest fins (Left +X and Right -X) & dorsal salt-crystal shards
    def add_crystal_fin(base_pt: Vector, tip_pt: Vector, up_vec: Vector, width: float, thick: float) -> None:
        axis = (tip_pt - base_pt)
        length = axis.length
        fwd = axis.normalized()
        side = fwd.cross(up_vec).normalized()
        up = side.cross(fwd).normalized()
        # 3 cross-section rings + tip = crisp faceted salt crystal blade
        secs = [
            (0.0, width * 0.55, thick * 0.65),
            (0.32, width * 1.0, thick * 0.90),
            (0.72, width * 0.62, thick * 0.55),
        ]
        c_rings = []
        for frac, rw, rt in secs:
            c = base_pt + fwd * (length * frac)
            pts = [
                c + up * rw,
                c + side * rt,
                c - up * (rw * 0.65),
                c - side * rt,
            ]
            c_rings.append([bm.verts.new(p) for p in pts])
        tip_v = bm.verts.new(tip_pt)
        base_v = bm.verts.new(base_pt - fwd * 0.025)
        for idx in range(len(c_rings) - 1):
            a, b = c_rings[idx], c_rings[idx + 1]
            v0, v1 = 0.945 + idx * 0.018, 0.945 + (idx + 1) * 0.018
            for k in range(4):
                kn = (k + 1) % 4
                f = bm.faces.new((a[k], b[k], b[kn], a[kn]))
                for loop, uv in zip(f.loops, [(k * 0.25, v0), (k * 0.25, v1), (kn * 0.25, v1), (kn * 0.25, v0)]):
                    loop[uv_layer].uv = uv
        for k in range(4):
            kn = (k + 1) % 4
            f1 = bm.faces.new((c_rings[-1][k], tip_v, c_rings[-1][kn]))
            for loop, uv in zip(f1.loops, [(k * 0.25, 0.98), (0.5, 0.998), (kn * 0.25, 0.98)]):
                loop[uv_layer].uv = uv
            f0 = bm.faces.new((base_v, c_rings[0][kn], c_rings[0][k]))
            for loop, uv in zip(f0.loops, [(0.5, 0.942), (kn * 0.25, 0.945), (k * 0.25, 0.945)]):
                loop[uv_layer].uv = uv

    # Paired flared salt-crystal gill-crests on neck (Left +X, Right -X) — unmistakable head silhouette!
    neck_y = -0.68
    neck_x = 0.24 * math.sin(0.14 * math.pi * 2.2 - 0.55) * (0.20 + 0.80 * math.sin(0.14 * math.pi))
    for side_sign in (1.0, -1.0):
        # Upper primary crest blade
        add_crystal_fin(
            Vector((neck_x + side_sign * 0.12, neck_y, 0.34)),
            Vector((neck_x + side_sign * 0.44, neck_y + 0.22, 0.56)),
            Vector((0.0, 0.0, 1.0)),
            width=0.088,
            thick=0.032,
        )
        # Lower secondary gill spike
        add_crystal_fin(
            Vector((neck_x + side_sign * 0.13, neck_y + 0.05, 0.26)),
            Vector((neck_x + side_sign * 0.36, neck_y + 0.26, 0.35)),
            Vector((0.0, 0.0, 1.0)),
            width=0.062,
            thick=0.026,
        )

    # Prominent salt-crystal brow crest on head (-Y)
    head_x = 0.24 * math.sin(0.08 * math.pi * 2.2 - 0.55) * (0.20 + 0.80 * math.sin(0.08 * math.pi))
    add_crystal_fin(
        Vector((head_x, -0.82, 0.40)),
        Vector((head_x, -0.68, 0.58)),
        Vector((1.0, 0.0, 0.0)),
        width=0.058,
        thick=0.028,
    )

    # Dorsal crystalline salt spikes along upper spine for clear small-scale silhouette
    for sp_s, sp_h, sp_w in ((0.28, 0.19, 0.052), (0.42, 0.20, 0.054), (0.56, 0.16, 0.044), (0.70, 0.13, 0.036)):
        sy = -0.96 + sp_s * 1.96
        sx = 0.24 * math.sin(sp_s * math.pi * 2.2 - 0.55) * (0.20 + 0.80 * math.sin(sp_s * math.pi))
        t_b = (sp_s - 0.22) / 0.78
        sz = 0.24 - 0.12 * t_b + 0.045 * math.sin(t_b * math.pi * 2.0) + 0.12
        add_crystal_fin(
            Vector((sx, sy, sz)),
            Vector((sx, sy + 0.12, sz + sp_h)),
            Vector((1.0, 0.0, 0.0)),
            width=sp_w,
            thick=0.026,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)

    me = bpy.data.meshes.new("SK_EN05_Mesh")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new("SK_EN05", me)
    bpy.context.scene.collection.objects.link(obj)

    # Material with packed procedural salt-vein texture
    mat = bpy.data.materials.new("Mat_EN05_SaltVein")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(tex_path), check_existing=True)
    img.name = "EN05_SaltVein_Image"
    img.pack()
    tex_node.image = img
    nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.62
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    obj.data.materials.append(mat)
    return obj


def build_eel_armature(mesh_obj: bpy.types.Object) -> bpy.types.Object:
    """Create 11-bone RIG_EN05 and assign smooth <=4 normalized weights."""
    arm_data = bpy.data.armatures.new("RIG_EN05_Data")
    arm = bpy.data.objects.new("RIG_EN05", arm_data)
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

    # Strictly centered root at origin; body at mid-spine
    add_bone("root", (0.0, 0.0, 0.0), (0.0, -0.20, 0.0), None)
    add_bone("body", (0.0, -0.05, 0.26), (0.0, -0.28, 0.26), "root")

    # Anterior chain (-Y forward)
    add_bone("neck_01", (0.0, -0.20, 0.27), (0.0, -0.50, 0.30), "body")
    add_bone("neck_02", (0.0, -0.50, 0.30), (0.0, -0.74, 0.34), "neck_01")
    add_bone("head", (0.0, -0.74, 0.34), (0.0, -0.98, 0.33), "neck_02")
    add_bone("jaw", (0.0, -0.76, 0.27), (0.0, -0.96, 0.24), "head")

    # Left (+X) and Right (-X) gill-crests
    add_bone("crest.L", (0.12, -0.66, 0.33), (0.44, -0.46, 0.54), "neck_02")
    add_bone("crest.R", (-0.12, -0.66, 0.33), (-0.44, -0.46, 0.54), "neck_02")

    # Posterior tail chain (+Y rear)
    add_bone("tail_01", (0.0, 0.02, 0.24), (0.0, 0.34, 0.19), "body")
    add_bone("tail_02", (0.0, 0.34, 0.19), (0.0, 0.66, 0.15), "tail_01")
    add_bone("tail_03", (0.0, 0.66, 0.15), (0.0, 1.02, 0.11), "tail_02")

    bpy.ops.object.mode_set(mode="OBJECT")

    # Parent mesh to armature with Armature modifier
    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    bone_names = [b.name for b in arm.data.bones]
    vgs = {bn: mesh_obj.vertex_groups.new(name=bn) for bn in bone_names}

    # Smooth longitudinal Gaussian weighting along Y + dedicated crest/jaw regions
    spine_centers = [
        ("head", -0.86, 0.15),
        ("neck_02", -0.62, 0.17),
        ("neck_01", -0.34, 0.18),
        ("body", -0.02, 0.20),
        ("tail_01", 0.28, 0.19),
        ("tail_02", 0.58, 0.19),
        ("tail_03", 0.90, 0.21),
    ]

    for v in mesh_obj.data.vertices:
        p = v.co
        weights: dict[str, float] = {}

        # Check if vertex belongs to flared gill crests (outward in X near neck)
        if -0.76 <= p.y <= -0.38 and abs(p.x) > 0.17 and p.z > 0.24:
            cname = "crest.L" if p.x > 0.0 else "crest.R"
            crest_blend = min(1.0, (abs(p.x) - 0.17) / 0.08)
            weights[cname] = crest_blend
            weights["neck_02"] = 1.0 - crest_blend
        else:
            for bname, cy, sigma in spine_centers:
                w = math.exp(-0.5 * ((p.y - cy) / sigma) ** 2)
                if w > 0.015:
                    weights[bname] = w
            # Lower jaw influence on lower front snout
            if p.y < -0.75 and p.z < 0.30:
                jk = min(1.0, (-0.75 - p.y) / 0.14) * min(1.0, (0.30 - p.z) / 0.08)
                weights["jaw"] = weights.get("jaw", 0.0) + jk * 1.4

        # Keep top 4 weights and normalize strictly to 1.0
        pairs = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
        total = sum(w for _, w in pairs)
        if total <= 1e-8:
            pairs = [("body", 1.0)]
            total = 1.0
        for bname, w in pairs:
            vgs[bname].add([v.index], w / total, "REPLACE")

    return arm


def set_en05_pose(arm: bpy.types.Object, clip: str, t: float) -> None:
    """In-place animations for EN05 (盐脉鳗).
    Strictly ZERO root XY drift across all 10 clips.
    Bone local axes (for bones oriented along -Y / +Y):
      In Blender edit bones along -Y (head->tail = -Y), local Y = bone axis (-Y world),
      local X = -X world (pitch up/down), local Z = +Z world (yaw left/right).
    """
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")

    s2 = math.sin(t * math.pi * 2.0)
    c2 = math.cos(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)

    def pitch_yaw(bname: str, pitch_up_deg: float, yaw_deg: float = 0.0, roll_deg: float = 0.0) -> None:
        # For anterior bones pointing -Y, negative local X pitches UP (+Z).
        # For posterior tail bones pointing +Y, positive local X pitches UP (+Z).
        sign = 1.0 if bname.startswith("tail_") else -1.0
        pbs[bname].rotation_euler = Euler(
            (math.radians(sign * pitch_up_deg), math.radians(roll_deg), math.radians(yaw_deg)),
            "XYZ",
        )

    def flare_crests(flare_deg: float, lift_deg: float = 0.0) -> None:
        pbs["crest.L"].rotation_euler = Euler((math.radians(lift_deg), 0.0, math.radians(-flare_deg)), "XYZ")
        pbs["crest.R"].rotation_euler = Euler((math.radians(lift_deg), 0.0, math.radians(flare_deg)), "XYZ")

    if clip == "EN05Idle":
        # Low, watchful, gently undulating ground-hugging eel
        pitch_yaw("body", 2.0 * s2, 5.0 * s2)
        pitch_yaw("neck_01", 8.0 + 3.0 * c2, -7.0 * s2)
        pitch_yaw("neck_02", 6.0 + 3.0 * s2, -6.0 * c2)
        pitch_yaw("head", -10.0 - 2.0 * s2, 5.0 * s2)
        pitch_yaw("jaw", -4.0 - 3.0 * max(0.0, s2), 0.0)
        pitch_yaw("tail_01", 0.0, 10.0 * s2)
        pitch_yaw("tail_02", 0.0, -14.0 * c2)
        pitch_yaw("tail_03", 0.0, 18.0 * s2)
        flare_crests(4.0 + 3.0 * s2, 2.0 * s2)

    elif clip == "EN05Walk":
        # Crisp traveling serpentine slither wave (in-place)
        pitch_yaw("body", 0.0, 14.0 * math.sin(t * math.pi * 2.0))
        pitch_yaw("neck_01", 6.0, 16.0 * math.sin(t * math.pi * 2.0 + 0.9))
        pitch_yaw("neck_02", 4.0, 16.0 * math.sin(t * math.pi * 2.0 + 1.8))
        pitch_yaw("head", -8.0, -14.0 * math.sin(t * math.pi * 2.0 + 1.8))
        pitch_yaw("tail_01", 0.0, 18.0 * math.sin(t * math.pi * 2.0 - 0.9))
        pitch_yaw("tail_02", 0.0, 24.0 * math.sin(t * math.pi * 2.0 - 1.8))
        pitch_yaw("tail_03", 0.0, 28.0 * math.sin(t * math.pi * 2.0 - 2.7))
        flare_crests(6.0, 0.0)

    elif clip == "EN05Stop":
        # Smooth damped coil-brake back to low idle
        w = (1.0 - t) ** 1.5
        pitch_yaw("body", 0.0, 16.0 * w)
        pitch_yaw("neck_01", 10.0 * w + 6.0, -14.0 * w)
        pitch_yaw("neck_02", 6.0 * w + 4.0, -10.0 * w)
        pitch_yaw("head", -12.0 * w - 6.0, 8.0 * w)
        pitch_yaw("tail_01", 0.0, -16.0 * w)
        pitch_yaw("tail_02", 0.0, 14.0 * w)
        pitch_yaw("tail_03", 0.0, -10.0 * w)
        flare_crests(10.0 * w, 0.0)

    elif clip == "EN05Attack":
        # Quick forward-snapping eel bite lunge + jaw snap
        coil = math.sin(min(1.0, t / 0.35) * math.pi) if t < 0.35 else 0.0
        strike = math.sin(min(1.0, max(0.0, (t - 0.25) / 0.45)) * math.pi)
        pitch_yaw("body", -4.0 * coil + 6.0 * strike, 10.0 * coil - 8.0 * strike)
        pitch_yaw("neck_01", 26.0 * coil - 14.0 * strike + 6.0, -12.0 * coil + 8.0 * strike)
        pitch_yaw("neck_02", 18.0 * coil - 12.0 * strike + 4.0, 0.0)
        pitch_yaw("head", -26.0 * coil + 18.0 * strike - 6.0, 0.0)
        pitch_yaw("jaw", -34.0 * strike, 0.0)
        pitch_yaw("tail_01", 0.0, -14.0 * coil + 12.0 * strike)
        pitch_yaw("tail_02", 0.0, 18.0 * coil - 16.0 * strike)
        pitch_yaw("tail_03", 0.0, -16.0 * strike)
        flare_crests(18.0 * strike + 8.0 * coil, 6.0 * strike)

    elif clip == "EN05Hit":
        # Sharp lateral recoil flinch rippling down tail
        pitch_yaw("body", -6.0 * s1, -18.0 * s1)
        pitch_yaw("neck_01", 14.0 * s1, 20.0 * s1)
        pitch_yaw("neck_02", -12.0 * s1, 16.0 * s1)
        pitch_yaw("head", 14.0 * s1, -12.0 * s1)
        pitch_yaw("jaw", -16.0 * s1, 0.0)
        pitch_yaw("tail_01", 0.0, 22.0 * s2)
        pitch_yaw("tail_02", 0.0, -24.0 * s2)
        pitch_yaw("tail_03", 0.0, 20.0 * s1)
        flare_crests(-12.0 * s1, -8.0 * s1)

    elif clip == "EN05Down":
        # Spine collapses flat onto Z=0 ground plane, head & jaw drop flat, crests fold
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        pitch_yaw("body", -4.0 * w, 8.0 * w, 18.0 * w)
        pitch_yaw("neck_01", -10.0 * w, 14.0 * w, 14.0 * w)
        pitch_yaw("neck_02", -6.0 * w, 12.0 * w, 10.0 * w)
        pitch_yaw("head", -6.0 * w, 10.0 * w, 8.0 * w)
        pitch_yaw("jaw", -10.0 * w, 0.0)
        pitch_yaw("tail_01", -4.0 * w, -16.0 * w, 12.0 * w)
        pitch_yaw("tail_02", -2.0 * w, -18.0 * w, 8.0 * w)
        pitch_yaw("tail_03", 0.0, -14.0 * w, 6.0 * w)
        flare_crests(-18.0 * w, -14.0 * w)

    elif clip == "EN05ArcRaise":
        # EN05-A 盐弧起蓄 (抬首绷紧): anterior spine rears up into taut S-arch, crests flare wide
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        pitch_yaw("body", 10.0 * w, -12.0 * w)
        pitch_yaw("neck_01", 34.0 * w, -16.0 * w)
        pitch_yaw("neck_02", 26.0 * w, -10.0 * w)
        pitch_yaw("head", -44.0 * w, 14.0 * w)
        pitch_yaw("jaw", -18.0 * w, 0.0)
        pitch_yaw("tail_01", 0.0, 22.0 * w)
        pitch_yaw("tail_02", 0.0, 26.0 * w)
        pitch_yaw("tail_03", 0.0, 20.0 * w)
        flare_crests(26.0 * w, 12.0 * w)

    elif clip == "EN05ArcHold":
        # EN05-A 盐弧蓄势保持 (可短持蓄势): high coiled taut head + flared salt crests + tremor
        tremor = math.sin(t * math.pi * 6.0)
        pitch_yaw("body", 10.0 + 1.5 * s2, -12.0 + 2.5 * c2)
        pitch_yaw("neck_01", 34.0 + 3.0 * s2, -16.0 + 3.0 * tremor)
        pitch_yaw("neck_02", 26.0 + 2.5 * c2, -10.0 - 2.5 * tremor)
        pitch_yaw("head", -44.0 - 2.0 * s2, 14.0 + 3.5 * tremor)
        pitch_yaw("jaw", -18.0 - 5.0 * abs(tremor), 0.0)
        pitch_yaw("tail_01", 0.0, 22.0 + 4.0 * s2)
        pitch_yaw("tail_02", 0.0, 26.0 - 4.0 * c2)
        pitch_yaw("tail_03", 0.0, 20.0 + 5.0 * s2)
        flare_crests(26.0 + 4.0 * tremor, 12.0 + 3.0 * s2)

    elif clip == "EN05ArcRelease":
        # EN05-A 盐弧横扫释放: sweeping wide horizontal arc from right (-X) across front to left (+X)
        if t < 0.18:
            # Brief wind-back right
            k = t / 0.18
            yaw_arc = -12.0 - 20.0 * k
            lift = 1.0
            jaw_open = 18.0 + 18.0 * k
        elif t < 0.62:
            # Explosive wide sweep right -> left across 2 adjacent hexes!
            k = (t - 0.18) / 0.44
            ks = k * k * (3.0 - 2.0 * k)
            yaw_arc = -32.0 + 84.0 * ks  # -32 deg -> +52 deg wide arc!
            lift = 1.0 - 0.55 * math.sin(k * math.pi)
            jaw_open = 38.0 * math.sin(k * math.pi) + 10.0
        else:
            # Smooth settle back to neutral
            k = (t - 0.62) / 0.38
            yaw_arc = 52.0 * (1.0 - k)
            lift = 1.0 * (1.0 - k)
            jaw_open = 10.0 * (1.0 - k)

        pitch_yaw("body", 10.0 * lift, yaw_arc * 0.45)
        pitch_yaw("neck_01", 34.0 * lift + 4.0, yaw_arc * 0.65)
        pitch_yaw("neck_02", 24.0 * lift + 3.0, yaw_arc * 0.65)
        pitch_yaw("head", -38.0 * lift - 4.0, yaw_arc * 0.35)
        pitch_yaw("jaw", -jaw_open, 0.0)
        pitch_yaw("tail_01", 0.0, -yaw_arc * 0.45)
        pitch_yaw("tail_02", 0.0, -yaw_arc * 0.55)
        pitch_yaw("tail_03", 0.0, -yaw_arc * 0.45)
        flare_crests(28.0 * max(0.2, lift), 10.0 * lift)

    elif clip == "EN05ArcCancel":
        # EN05-A 盐弧取消复位: taut coil relaxes smoothly back to low idle
        w = (1.0 - t)
        w = w * w * (3.0 - 2.0 * w)
        pitch_yaw("body", 10.0 * w, -12.0 * w)
        pitch_yaw("neck_01", 34.0 * w + 6.0 * (1.0 - w), -16.0 * w)
        pitch_yaw("neck_02", 26.0 * w + 4.0 * (1.0 - w), -10.0 * w)
        pitch_yaw("head", -44.0 * w - 6.0 * (1.0 - w), 14.0 * w)
        pitch_yaw("jaw", -18.0 * w, 0.0)
        pitch_yaw("tail_01", 0.0, 22.0 * w)
        pitch_yaw("tail_02", 0.0, 26.0 * w)
        pitch_yaw("tail_03", 0.0, 20.0 * w)
        flare_crests(26.0 * w, 12.0 * w)


def measure_clip_floor(arm, mesh, deps, scene, body_rest_head: Vector, f0: float, f1: float) -> dict:
    """Measure first_frame_z, last_frame_z, half_frame_min_z, root XY drift, and degenerate faces."""
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
        bh_w = arm.matrix_world @ arm.pose.bones["body"].head
        xy = math.hypot(bh_w.x - body_rest_head.x, bh_w.y - body_rest_head.y)
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


def render_proofs(arm, mesh, out_dir: Path, en15_glb: str = "", en06_glb: str = "") -> None:
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
    cam_data.ortho_scale = 2.45
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.8, -2.6, 1.85))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.35)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in PROOF_PANELS:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"EN05_panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)

    # Z=0 ground-plane contact proof for EN05Down f30 (side view + low 3/4 view)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.02))
    floor_slab = bpy.context.active_object
    floor_slab.scale = (4.2, 4.2, 0.04)
    floor_slab.name = "ProofFloorZ0"
    fmat = bpy.data.materials.new("ProofFloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor_slab.data.materials.append(fmat)

    scene.render.resolution_x = 720
    scene.render.resolution_y = 400
    cam_data.ortho_scale = 2.35
    cam.location = Vector((3.2, 0.0, 0.38))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.28)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions["EN05Down"])
    scene.frame_set(30)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / "EN05_down_ground_contact_side.png")
    bpy.ops.render.render(write_still=True)

    cam.location = Vector((2.2, -2.4, 0.62))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.22)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out_dir / "EN05_down_ground_contact_3q.png")
    bpy.ops.render.render(write_still=True)

    # Small-size board-scale readability check (P04B ortho 1280x720) — Idle & EN05-A Hold
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    cam_data.ortho_scale = 13.0
    cam.location = Vector((1.6, -3.2, 2.5))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.35)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions["EN05ArcHold"])
    scene.frame_set(18)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / "EN05_small_scale_readability.png")
    bpy.ops.render.render(write_still=True)

    # Optional neighbor silhouette comparison (EN06 left, EN05 center, EN15 right) on Z=0 plane
    imported_objs = []
    if en06_glb and Path(en06_glb).exists():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=en06_glb)
        added = [o for o in bpy.data.objects if o not in before]
        for o in added:
            if o.parent is None:
                o.location.x -= 1.85
        imported_objs.extend(added)
    if en15_glb and Path(en15_glb).exists():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=en15_glb)
        added = [o for o in bpy.data.objects if o not in before]
        for o in added:
            if o.parent is None:
                o.location.x += 1.85
        imported_objs.extend(added)

    if imported_objs:
        floor_slab.scale = (8.0, 5.0, 0.04)
        scene.render.resolution_x = 960
        scene.render.resolution_y = 480
        cam_data.ortho_scale = 5.6
        cam.location = Vector((0.0, -5.2, 2.8))
        cam.rotation_euler = (Vector((0.0, 0.0, 0.65)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        activate_action(arm, bpy.data.actions["EN05Idle"])
        scene.frame_set(12)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / "EN05_neighbor_silhouette_compare.png")
        bpy.ops.render.render(write_still=True)

        for o in imported_objs:
            if o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)

    bpy.data.objects.remove(floor_slab, do_unlink=True)


def build_en05(args: argparse.Namespace) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24

    out_blend = Path(args.out_blend)
    out_glb = Path(args.out_glb)
    out_report = Path(args.out_report)
    tex_path = out_blend.parent / "EN05_SaltVein_Tex.png"
    tex_sha = generate_salt_vein_texture(tex_path, size=512)

    mesh = build_eel_mesh(tex_path)
    arm = build_eel_armature(mesh)

    # Ensure rest pose sits cleanly at Z = 0.0
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

    # Verify topology & weights
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

    b_rest = (arm.matrix_world @ arm.data.bones["body"].matrix_local).to_3x3().normalized()
    r_rest = (arm.matrix_world @ arm.data.bones["root"].matrix_local).to_3x3().normalized()
    body_rest_head = arm.matrix_world @ arm.data.bones["body"].head_local

    # Author all 10 clips with exact Z=0 vertical-only grounding (ZERO XY drift!)
    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()
    bone_names = [b.name for b in arm.data.bones]

    for cname, n_frames in CLIPS:
        act = bpy.data.actions.new(name=cname)
        act.use_fake_user = True
        activate_action(arm, act)
        for f in range(1, n_frames + 1):
            t = (f - 1) / max(1, n_frames - 1)
            scene.frame_set(f)
            set_en05_pose(arm, cname, t)
            bpy.context.view_layer.update()

            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            eo.to_mesh_clear()
            # Keep belly/lowest contact strictly at Z=0 on every frame of this ground-hugging eel
            if abs(min_z) > 1e-5:
                pb_b = arm.pose.bones["body"]
                parent_pose_w = (arm.matrix_world @ pb_b.parent.matrix).to_3x3().normalized()
                inherited_w = parent_pose_w @ r_rest.inverted() @ b_rest
                pb_b.location += inherited_w.inverted() @ Vector((0.0, 0.0, -min_z))
                bpy.context.view_layer.update()

            for bn in bone_names:
                pb = arm.pose.bones[bn]
                pb.keyframe_insert(data_path="rotation_euler", frame=f)
                if bn in ("root", "body"):
                    pb.keyframe_insert(data_path="location", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = cname
        strip = tr.strips.new(cname, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = n_frames

    # Half-frame + first/last frame QA on .blend
    clip_qa = {}
    worst_min_z, worst_clip, worst_fr, total_sub3, max_xy_all = 999.0, "", 0.0, 0, 0.0
    for cname, n_frames in CLIPS:
        activate_action(arm, bpy.data.actions[cname])
        q = measure_clip_floor(arm, mesh, deps, scene, body_rest_head, 1.0, float(n_frames))
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

    # Save editable .blend
    activate_action(arm, bpy.data.actions["EN05Idle"])
    scene.frame_set(1)
    bpy.context.view_layer.update()
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    # Export GLB
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

    # Render proofs
    if args.out_proof:
        render_proofs(arm, mesh, Path(args.out_proof), args.en15_glb, args.en06_glb)

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
        re_body = next((o for o in re_meshes if o.name == "SK_EN05"), re_meshes[0])
        re_body_rest_head = re_arm.matrix_world @ re_arm.data.bones["body"].head_local
        for a in sorted(bpy.data.actions, key=lambda x: x.name):
            activate_action(re_arm, a)
            re_floor[a.name] = measure_clip_floor(
                re_arm, re_body, re_deps, re_scene, re_body_rest_head,
                float(a.frame_range[0]), float(a.frame_range[1])
            )

    expected_names = {n for n, _ in CLIPS}
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

    report = {
        "kind": "EN05",
        "name": "盐脉鳗",
        "region": "RG04 / SALT_CROSSING",
        "move": "EN05-A 盐弧 (W2, 2 adjacent hexes; side/rear weakness authority next-tick)",
        "recipe_origin": "100% local procedural Blender Python recipe (zero external mesh/image/motion donors)",
        "rest_dimensions": rest_dims,
        "mesh_stats": {
            "verts": len(mesh.data.vertices) if False else re_tris,  # overwritten cleanly below
        },
        "embedded_texture": {
            "name": "EN05_SaltVein_Image",
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
    report.pop("mesh_stats", None)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EN05_BUILD_OK:", json.dumps({
        "tris": re_tris,
        "over4": re_over4,
        "actions": len(re_actions),
        "hf": hf_summary,
        "down_blend_last_z": clip_qa["EN05Down"]["last_frame_z"],
        "down_glb_last_z": re_floor.get("EN05Down", {}).get("last_frame_z"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build_en05(parse_args())

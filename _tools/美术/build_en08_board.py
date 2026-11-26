"""Procedurally build EN08_Board.blend and EN08_Board.glb for #15 (雾袋孢母 EN08).

Original local procedural recipe (zero external mesh/image/motion donors):
- Squat, wide, clustered mist-sacs & layered mushroom caps for 沉息湖区 (SALT_CROSSING).
- Clearly distinct from EN15 (tall 3-pipe upright), EN05 (low long horizontal eel),
  and EN06 (tall domed brown bell-snail).
- Forward axis = -Y in Blender (+Z in glTF/Godot), Left = +X, Right = -X, Up = +Z.
- Locally generated 512x512 P04B warm-frontier storybook PBR texture packed into .blend & .glb.
- Non-degenerate pole UVs on every dome/sac/cap (uv_zero_area_faces = 0, uv_oob_pct = 0.0).
- 10-bone rig (RIG_EN08) with <=4 normalized weights, 0 degenerate faces.
- 10 strictly in-place animations (zero root XY drift):
  Core (6): EN08Idle, EN08Walk, EN08Stop, EN08Attack, EN08Hit, EN08Down
  EN08-A 结雾 (4): EN08VeilRaise, EN08VeilHold, EN08VeilRelease, EN08VeilCancel
  (expressed purely via crown/shoulder mist-sac inflation, clench, puff-release, and relaxation;
   no full-screen fog, no damage zone, no fabricated stealth/reveal simulation).
- Reports first_frame_z, last_frame_z, half_frame_min_z, root_xy_drift separately for ALL 10 clips
  in both .blend and clean-blend re-imported .glb, plus 8-pose proof, Z=0 ground-contact proofs,
  small-scale readability, and 4-enemy lake silhouette comparison (EN06, EN05, EN08, EN15).
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

CLIPS = [
    ("EN08Idle", 48),
    ("EN08Walk", 24),
    ("EN08Stop", 18),
    ("EN08Attack", 24),
    ("EN08Hit", 18),
    ("EN08Down", 30),
    ("EN08VeilRaise", 18),
    ("EN08VeilHold", 36),
    ("EN08VeilRelease", 24),
    ("EN08VeilCancel", 18),
]

PROOF_PANELS = [
    ("0_idle", "EN08Idle", 12),
    ("1_walk", "EN08Walk", 6),
    ("2_attack", "EN08Attack", 12),
    ("3_A_raise", "EN08VeilRaise", 14),
    ("4_A_hold", "EN08VeilHold", 18),
    ("5_A_release", "EN08VeilRelease", 11),
    ("6_A_cancel", "EN08VeilCancel", 9),
    ("7_down_end", "EN08Down", 30),
]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out-glb", required=True)
    p.add_argument("--out-blend", required=True)
    p.add_argument("--out-report", required=True)
    p.add_argument("--out-proof", default="")
    p.add_argument("--en06-glb", default="")
    p.add_argument("--en05-glb", default="")
    p.add_argument("--en15-glb", default="")
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


def generate_spore_mother_texture(out_path: Path, size: int = 512) -> str:
    """Generate a procedural P04B warm-frontier 3-band fungal & mist-sac texture.
    PNG row 0 = UV v=1.0, row size-1 = UV v=0.0.
    Bands:
      v in [0.00, 0.32): mossy-umber mycelial stalk & root-feet (+ warm amber eyes near u=0.75, v=0.22)
      v in [0.32, 0.66): tiered mushroom caps (rich lichen-olive/umber top with pale ochre spots, pale pleated gills below)
      v in [0.66, 1.00]: pearlescent mist-ivory / pale celadon mist-sacs with subtle mist-veins & dark spore-vent rim at v > 0.93
    """
    buf = bytearray(size * size * 3)
    for py in range(size):
        v = 1.0 - (py / (size - 1))
        for px in range(size):
            u = px / (size - 1)
            grain = 0.5 + 0.3 * math.sin(u * 44.0 + v * 31.0) + 0.2 * math.cos(u * 82.0 - v * 67.0)

            if v < 0.32:
                # Mycelial stalk & root-feet: dark damp soil base -> warm mossy umber -> pale collar
                k = v / 0.32
                r = 68 + 64 * k
                g = 62 + 54 * k
                b = 50 + 40 * k
                # Vertical fibrous stalk flutes
                flute = 0.5 + 0.5 * math.sin(u * math.pi * 24.0)
                r *= 0.88 + 0.18 * flute
                g *= 0.88 + 0.18 * flute
                b *= 0.88 + 0.18 * flute
                # Subtle warm-amber spore-ocelli facing -Y (u = 0.75 in standard atan2/cos-sin)
                for eye_u in (0.70, 0.80):
                    du = ((u - eye_u + 0.5) % 1.0) - 0.5
                    dv = (v - 0.22) * 1.4
                    ed = math.hypot(du * 4.5, dv * 4.5)
                    if ed < 0.14:
                        ek = max(0.0, 1.0 - ed / 0.14) ** 1.3
                        r = r * (1.0 - ek) + 242 * ek
                        g = g * (1.0 - ek) + 186 * ek
                        b = b * (1.0 - ek) + 76 * ek

            elif v < 0.66:
                # Layered fungal caps: underside gills (v < 0.44) -> rim -> spotted lichen-umber dome (v >= 0.44)
                k = (v - 0.32) / 0.34
                if k < 0.35:
                    # Pale creamy-sage pleated underside gills
                    pleat = 0.5 + 0.5 * math.sin(u * math.pi * 48.0)
                    r = 178 + 26 * pleat
                    g = 174 + 22 * pleat
                    b = 148 + 18 * pleat
                else:
                    # Warm mossy-olive & umber cap surface with storybook pale lichen spots
                    dk = (k - 0.35) / 0.65
                    r = 104 - 22 * dk + 16 * grain
                    g = 96 - 14 * dk + 14 * grain
                    b = 72 - 12 * dk + 10 * grain
                    # Organic lichen spots
                    sp1 = math.sin(u * math.pi * 16.0 + math.sin(dk * 9.0) * 1.2) * math.sin(dk * math.pi * 5.0)
                    if sp1 > 0.68:
                        sk = min(1.0, (sp1 - 0.68) / 0.32) * 0.85
                        r = r * (1.0 - sk) + 206 * sk
                        g = g * (1.0 - sk) + 196 * sk
                        b = b * (1.0 - sk) + 162 * sk
            else:
                # Mist-sacs: pearlescent celadon-ivory translucent-look bulbs + subtle mist veins + dark spore-vent top
                k = (v - 0.66) / 0.34
                # Soft warm-sage base -> bright pearlescent mist-ivory -> dark slate-teal pore aperture at apex
                r = 166 + 68 * math.sin(min(1.0, k * 1.15) * math.pi * 0.72)
                g = 188 + 54 * math.sin(min(1.0, k * 1.15) * math.pi * 0.72)
                b = 178 + 56 * math.sin(min(1.0, k * 1.15) * math.pi * 0.72)
                # Delicate vertical mist-sac ribs/veins
                vein = abs(math.sin(u * math.pi * 12.0 + math.sin(k * 6.0) * 0.4))
                if vein < 0.14:
                    vk = (1.0 - vein / 0.14) * 0.32
                    r = r * (1.0 - vk) + 112 * vk
                    g = g * (1.0 - vk) + 142 * vk
                    b = b * (1.0 - vk) + 136 * vk
                # Dark spore-vent aperture rim at very top (k > 0.84)
                if k > 0.84:
                    ak = (k - 0.84) / 0.16
                    r = r * (1.0 - ak) + 52 * ak
                    g = g * (1.0 - ak) + 66 * ak
                    b = b * (1.0 - ak) + 64 * ak

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
    n_rad: int = 20,
    squish_x: float = 1.0,
    squish_y: float = 1.0,
    flute_amp: float = 0.0,
    flute_freq: int = 8,
    tilt_euler: Euler | None = None,
    part_tag: str = "body",
    vert_tags: dict[int, str] | None = None,
) -> None:
    """Build a closed watertight lathe solid with guaranteed non-zero pole cap UV triangles.
    profile: list of (radius, local_z) from bottom ring to top ring (all radius > 0).
    Pole caps reserve non-zero delta-V margins at both ends so uv_zero_area_faces == 0!
    """
    rot_m = tilt_euler.to_matrix() if tilt_euler else None
    n_rings = len(profile)
    # Reserve 0.014 V margin at bottom and top for non-degenerate pole cap triangles
    v_span = v_max - v_min
    v_margin = min(0.016, v_span * 0.09)
    v_ring_lo = v_min + v_margin
    v_ring_hi = v_max - v_margin

    def xform(pt: Vector) -> Vector:
        p = rot_m @ pt if rot_m else pt
        return center + p

    rings = []
    for ri, (rad, lz) in enumerate(profile):
        frac = ri / max(1, n_rings - 1)
        vv = v_ring_lo + frac * (v_ring_hi - v_ring_lo)
        ring = []
        for j in range(n_rad):
            u = j / n_rad
            ang = u * math.pi * 2.0  # 0=+X, pi/2=+Y, pi=-X, 3pi/2=-Y (front!)
            r_eff = rad * (1.0 + flute_amp * math.sin(ang * flute_freq))
            pt = Vector((r_eff * math.cos(ang) * squish_x, r_eff * math.sin(ang) * squish_y, lz))
            v = bm.verts.new(xform(pt))
            if vert_tags is not None:
                bm.verts.index_update()
                vert_tags[v.index] = part_tag
            ring.append((v, u, vv))
        rings.append(ring)

    # Quad sides
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

    # Bottom pole cap (non-collinear isosceles UV triangles with delta-V = v_margin)
    bot_z = profile[0][1] - 0.008
    bot_v = bm.verts.new(xform(Vector((0.0, 0.0, bot_z))))
    if vert_tags is not None:
        bm.verts.index_update()
        vert_tags[bot_v.index] = part_tag
    for j in range(n_rad):
        jn = (j + 1) % n_rad
        v0, u0, vv0 = rings[0][j]
        v1, u1, vv1 = rings[0][jn]
        u1_w = 1.0 if jn == 0 else u1
        u_mid = 0.5 * (u0 + u1_w)
        f = bm.faces.new((bot_v, v1, v0))
        for loop, uv in zip(f.loops, [(u_mid, v_min + 0.002), (u1_w, vv1), (u0, vv0)]):
            loop[uv_layer].uv = uv

    # Top pole cap (non-collinear isosceles UV triangles with delta-V = v_margin)
    top_z = profile[-1][1] + 0.008
    top_v = bm.verts.new(xform(Vector((0.0, 0.0, top_z))))
    if vert_tags is not None:
        bm.verts.index_update()
        vert_tags[top_v.index] = part_tag
    for j in range(n_rad):
        jn = (j + 1) % n_rad
        v0, u0, vv0 = rings[-1][j]
        v1, u1, vv1 = rings[-1][jn]
        u1_w = 1.0 if jn == 0 else u1
        u_mid = 0.5 * (u0 + u1_w)
        f = bm.faces.new((top_v, v0, v1))
        for loop, uv in zip(f.loops, [(u_mid, v_max - 0.002), (u0, vv0), (u1_w, vv1)]):
            loop[uv_layer].uv = uv


def build_spore_mother_mesh(tex_path: Path) -> tuple[bpy.types.Object, dict[int, str]]:
    """Build EN08 (雾袋孢母) squat wide clustered fungal & mist-sac mesh."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    vert_tags: dict[int, str] = {}

    # 1. Central squat bulbous mycelial stalk (v in [0.01, 0.31])
    stalk_prof = [
        (0.28, 0.02), (0.38, 0.08), (0.42, 0.20), (0.36, 0.34), (0.30, 0.48), (0.22, 0.56),
    ]
    add_lathe_part(
        bm, uv_layer, stalk_prof, Vector((0.0, 0.0, 0.0)),
        0.01, 0.31, n_rad=20, squish_x=1.06, squish_y=1.02, flute_amp=0.05, flute_freq=6,
        part_tag="body", vert_tags=vert_tags,
    )

    # 2. Four stubby creeping root-feet grounded at Z=0 (front-left, front-right, back-left, back-right)
    foot_prof = [(0.13, 0.008), (0.16, 0.06), (0.14, 0.14), (0.09, 0.21)]
    feet_specs = [
        ("foot_fl", Vector((0.30, -0.26, 0.0))),
        ("foot_fr", Vector((-0.30, -0.26, 0.0))),
        ("foot_bl", Vector((0.32, 0.26, 0.0))),
        ("foot_br", Vector((-0.32, 0.26, 0.0))),
    ]
    for ftag, fpos in feet_specs:
        add_lathe_part(
            bm, uv_layer, foot_prof, fpos,
            0.01, 0.20, n_rad=12, squish_x=1.15, squish_y=1.20,
            part_tag=ftag, vert_tags=vert_tags,
        )

    # 3. Lower wide tiered fungal skirt-cap (broad squat silhouette!)
    lower_cap_prof = [
        (0.26, 0.22), (0.58, 0.24), (0.64, 0.28), (0.56, 0.36), (0.38, 0.42), (0.24, 0.44),
    ]
    add_lathe_part(
        bm, uv_layer, lower_cap_prof, Vector((0.0, 0.0, 0.0)),
        0.33, 0.65, n_rad=24, squish_x=1.06, squish_y=0.98, flute_amp=0.055, flute_freq=9,
        part_tag="body", vert_tags=vert_tags,
    )

    # 4. Main middle tiered mushroom cap (layered dome with warm spotted top & pleated gills)
    main_cap_prof = [
        (0.22, 0.44), (0.52, 0.45), (0.60, 0.50), (0.52, 0.62), (0.36, 0.72), (0.18, 0.76),
    ]
    add_lathe_part(
        bm, uv_layer, main_cap_prof, Vector((0.0, 0.0, 0.0)),
        0.33, 0.65, n_rad=24, squish_x=1.05, squish_y=1.02, flute_amp=0.045, flute_freq=8,
        part_tag="cap_main", vert_tags=vert_tags,
    )

    # 5. Prominent central crown mist-sac (sac_top) — apex breathing & veil-release focal point!
    crown_sac_prof = [
        (0.14, 0.70), (0.26, 0.77), (0.31, 0.87), (0.27, 0.98), (0.16, 1.05), (0.08, 1.07),
    ]
    add_lathe_part(
        bm, uv_layer, crown_sac_prof, Vector((0.0, 0.0, 0.0)),
        0.67, 0.99, n_rad=20, squish_x=1.04, squish_y=1.04, flute_amp=0.03, flute_freq=6,
        part_tag="sac_top", vert_tags=vert_tags,
    )

    # 6. Paired lateral shoulder mist-sacs (sac.L at +X, sac.R at -X) — unmistakable wide clustered sacs!
    shoulder_sac_prof = [
        (0.10, -0.14), (0.21, -0.06), (0.25, 0.04), (0.21, 0.14), (0.12, 0.21), (0.06, 0.23),
    ]
    add_lathe_part(
        bm, uv_layer, shoulder_sac_prof, Vector((0.46, -0.04, 0.46)),
        0.67, 0.99, n_rad=16, squish_x=1.05, squish_y=1.08,
        tilt_euler=Euler((0.0, math.radians(24.0), 0.0), "XYZ"),
        part_tag="sac.L", vert_tags=vert_tags,
    )
    add_lathe_part(
        bm, uv_layer, shoulder_sac_prof, Vector((-0.46, -0.04, 0.46)),
        0.67, 0.99, n_rad=16, squish_x=1.05, squish_y=1.08,
        tilt_euler=Euler((0.0, math.radians(-24.0), 0.0), "XYZ"),
        part_tag="sac.R", vert_tags=vert_tags,
    )

    # 7. Clustered satellite spore-pods (rear-left, rear-right, front-collar) for rich organic cluster
    pod_prof = [(0.07, -0.08), (0.15, 0.0), (0.16, 0.08), (0.11, 0.15), (0.05, 0.17)]
    add_lathe_part(
        bm, uv_layer, pod_prof, Vector((0.34, 0.34, 0.38)),
        0.67, 0.99, n_rad=14, tilt_euler=Euler((math.radians(-20.0), math.radians(18.0), 0.0), "XYZ"),
        part_tag="sac.L", vert_tags=vert_tags,
    )
    add_lathe_part(
        bm, uv_layer, pod_prof, Vector((-0.34, 0.34, 0.38)),
        0.67, 0.99, n_rad=14, tilt_euler=Euler((math.radians(-20.0), math.radians(-18.0), 0.0), "XYZ"),
        part_tag="sac.R", vert_tags=vert_tags,
    )
    add_lathe_part(
        bm, uv_layer, pod_prof, Vector((0.0, 0.42, 0.56)),
        0.67, 0.99, n_rad=14, tilt_euler=Euler((math.radians(-28.0), 0.0, 0.0), "XYZ"),
        part_tag="cap_main", vert_tags=vert_tags,
    )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)

    me = bpy.data.meshes.new("SK_EN08_Mesh")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new("SK_EN08", me)
    bpy.context.scene.collection.objects.link(obj)

    mat = bpy.data.materials.new("Mat_EN08_SporeMother")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(tex_path), check_existing=True)
    img.name = "EN08_SporeMother_Image"
    img.pack()
    tex_node.image = img
    nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.68
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.28
    obj.data.materials.append(mat)
    return obj, vert_tags


def build_spore_mother_armature(mesh_obj: bpy.types.Object, vert_tags: dict[int, str]) -> bpy.types.Object:
    """Create 10-bone RIG_EN08 with clean <=4 normalized vertex weights."""
    arm_data = bpy.data.armatures.new("RIG_EN08_Data")
    arm = bpy.data.objects.new("RIG_EN08", arm_data)
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
    add_bone("body", (0.0, 0.0, 0.22), (0.0, 0.0, 0.44), "root")
    add_bone("cap_main", (0.0, 0.0, 0.44), (0.0, 0.0, 0.74), "body")
    add_bone("sac_top", (0.0, 0.0, 0.72), (0.0, 0.0, 1.06), "cap_main")
    add_bone("sac.L", (0.34, 0.0, 0.44), (0.58, 0.0, 0.62), "body")
    add_bone("sac.R", (-0.34, 0.0, 0.44), (-0.58, 0.0, 0.62), "body")
    add_bone("foot_fl", (0.28, -0.24, 0.16), (0.32, -0.28, 0.02), "body")
    add_bone("foot_fr", (-0.28, -0.24, 0.16), (-0.32, -0.28, 0.02), "body")
    add_bone("foot_bl", (0.30, 0.24, 0.16), (0.34, 0.28, 0.02), "body")
    add_bone("foot_br", (-0.30, 0.24, 0.16), (-0.34, 0.28, 0.02), "body")

    bpy.ops.object.mode_set(mode="OBJECT")

    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    vgs = {b.name: mesh_obj.vertex_groups.new(name=b.name) for b in arm.data.bones}
    for v in mesh_obj.data.vertices:
        tag = vert_tags.get(v.index, "body")
        if tag in vgs:
            vgs[tag].add([v.index], 1.0, "REPLACE")
        else:
            vgs["body"].add([v.index], 1.0, "REPLACE")

    return arm


def set_en08_pose(arm: bpy.types.Object, clip: str, t: float) -> None:
    """In-place animations for EN08 (雾袋孢母).
    Strictly ZERO root XY drift across all 10 clips.
    Uses organic sac scaling + cap tilt/heave to clearly express crown-sac breathing & EN08-A 结雾.
    """
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
        pb.scale = Vector((1.0, 1.0, 1.0))

    s2 = math.sin(t * math.pi * 2.0)
    c2 = math.cos(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)

    def set_rot(bname: str, rx: float, ry: float, rz: float) -> None:
        pbs[bname].rotation_euler = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ")

    def set_sac_scale(top_s: float, side_s: float) -> None:
        pbs["sac_top"].scale = Vector((top_s, top_s, top_s))
        pbs["sac.L"].scale = Vector((side_s, side_s, side_s))
        pbs["sac.R"].scale = Vector((side_s, side_s, side_s))

    if clip == "EN08Idle":
        # Readable crown mist-sac rhythmic breathing & gentle fungal sway
        set_rot("body", 2.0 * s2, 3.0 * c2, 0.0)
        set_rot("cap_main", -3.0 * s2, -4.0 * c2, 0.0)
        set_sac_scale(1.0 + 0.09 * s2, 1.0 + 0.06 * c2)

    elif clip == "EN08Walk":
        # Squat waddling gait with alternating 4 stubby root-feet + cap bob
        set_rot("body", 5.0, 9.0 * s2, 6.0 * c2)
        set_rot("cap_main", -4.0, -7.0 * s2, 0.0)
        set_rot("foot_fl", 18.0 * s2, 0.0, 0.0)
        set_rot("foot_br", 18.0 * s2, 0.0, 0.0)
        set_rot("foot_fr", -18.0 * s2, 0.0, 0.0)
        set_rot("foot_bl", -18.0 * s2, 0.0, 0.0)
        set_sac_scale(1.0 + 0.06 * c2, 1.0 + 0.05 * s2)

    elif clip == "EN08Stop":
        w = (1.0 - t) ** 1.5
        set_rot("body", 6.0 * w, 8.0 * w, 0.0)
        set_rot("cap_main", -6.0 * w, -6.0 * w, 0.0)
        set_sac_scale(1.0 + 0.08 * w, 1.0 + 0.05 * w)

    elif clip == "EN08Attack":
        # Forward fungal cap heave + quick mist-sac jolt
        coil = math.sin(min(1.0, t / 0.38) * math.pi) if t < 0.38 else 0.0
        heave = math.sin(min(1.0, max(0.0, (t - 0.28) / 0.44)) * math.pi)
        set_rot("body", -12.0 * coil + 18.0 * heave, 0.0, 0.0)
        set_rot("cap_main", -10.0 * coil + 16.0 * heave, 0.0, 0.0)
        set_sac_scale(1.0 + 0.14 * coil - 0.12 * heave, 1.0 + 0.10 * coil - 0.08 * heave)

    elif clip == "EN08Hit":
        # Compressed flinch + tilted cap recoil
        set_rot("body", -14.0 * s1, 12.0 * s2, 0.0)
        set_rot("cap_main", -14.0 * s1, -10.0 * s2, 0.0)
        set_sac_scale(1.0 - 0.16 * s1, 1.0 - 0.12 * s1)

    elif clip == "EN08Down":
        # Caps slump cleanly sideways-forward, mist-sacs deflate flat, resting solidly on Z=0
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        set_rot("body", 32.0 * w, 24.0 * w, 10.0 * w)
        set_rot("cap_main", 26.0 * w, 16.0 * w, 0.0)
        set_rot("sac.L", 0.0, 22.0 * w, 0.0)
        set_rot("sac.R", 0.0, -22.0 * w, 0.0)
        set_rot("foot_fl", -24.0 * w, 0.0, 0.0)
        set_rot("foot_fr", -24.0 * w, 0.0, 0.0)
        set_rot("foot_bl", 20.0 * w, 0.0, 0.0)
        set_rot("foot_br", 20.0 * w, 0.0, 0.0)
        set_sac_scale(1.0 - 0.36 * w, 1.0 - 0.32 * w)

    elif clip == "EN08VeilRaise":
        # EN08-A 结雾起蓄: crown & shoulder mist-sacs swell taut, cap rises & clenches inward
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        set_rot("body", -8.0 * w, 0.0, 0.0)
        set_rot("cap_main", -10.0 * w, 0.0, 0.0)
        set_rot("sac.L", 0.0, -14.0 * w, 0.0)
        set_rot("sac.R", 0.0, 14.0 * w, 0.0)
        set_sac_scale(1.0 + 0.26 * w, 1.0 + 0.20 * w)

    elif clip == "EN08VeilHold":
        # EN08-A 结雾蓄势保持 (W1): taut swollen crown & shoulder sacs with rhythmic breathing pulse
        pulse = math.sin(t * math.pi * 4.0)
        set_rot("body", -8.0 + 2.0 * s2, 3.0 * c2, 0.0)
        set_rot("cap_main", -10.0 - 2.5 * s2, -3.0 * c2, 0.0)
        set_rot("sac.L", 0.0, -14.0 - 3.0 * pulse, 0.0)
        set_rot("sac.R", 0.0, 14.0 + 3.0 * pulse, 0.0)
        set_sac_scale(1.26 + 0.08 * pulse, 1.20 + 0.06 * pulse)

    elif clip == "EN08VeilRelease":
        # EN08-A 结雾释放: crisp sac compression puff-out + shoulder flare + gentle settle
        if t < 0.20:
            k = t / 0.20
            top_s = 1.26 + 0.10 * k
            side_s = 1.20 + 0.08 * k
            body_x = -8.0 - 4.0 * k
            flare = -14.0 - 6.0 * k
        elif t < 0.58:
            k = (t - 0.20) / 0.38
            ks = k * k * (3.0 - 2.0 * k)
            top_s = 1.36 - 0.54 * ks   # dramatic visible puff-deflation (1.36 -> 0.82)!
            side_s = 1.28 - 0.44 * ks
            body_x = -12.0 + 22.0 * ks
            flare = -20.0 + 34.0 * ks
        else:
            k = (t - 0.58) / 0.42
            top_s = 0.82 + 0.18 * k
            side_s = 0.84 + 0.16 * k
            body_x = 10.0 * (1.0 - k)
            flare = 14.0 * (1.0 - k)

        set_rot("body", body_x, 0.0, 0.0)
        set_rot("cap_main", body_x * 0.7, 0.0, 0.0)
        set_rot("sac.L", 0.0, flare, 0.0)
        set_rot("sac.R", 0.0, -flare, 0.0)
        set_sac_scale(top_s, side_s)

    elif clip == "EN08VeilCancel":
        # EN08-A 结雾取消复位: swollen sacs smoothly relax & shoulders drop cleanly back
        w = 1.0 - t
        w = w * w * (3.0 - 2.0 * w)
        set_rot("body", -8.0 * w, 0.0, 0.0)
        set_rot("cap_main", -10.0 * w, 0.0, 0.0)
        set_rot("sac.L", 0.0, -14.0 * w, 0.0)
        set_rot("sac.R", 0.0, 14.0 * w, 0.0)
        set_sac_scale(1.0 + 0.26 * w, 1.0 + 0.20 * w)


def measure_clip_floor(arm, mesh, deps, scene, body_rest_head: Vector, f0: float, f1: float) -> dict:
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


def render_proofs(arm, out_dir: Path, en06_glb: str = "", en05_glb: str = "", en15_glb: str = "") -> None:
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
    cam_data.ortho_scale = 2.25
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.5, -2.8, 1.85))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.50)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in PROOF_PANELS:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"EN08_panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)

    # Z=0 ground-plane contact proofs for EN08Down f30 (side + low 3/4)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.02))
    floor_slab = bpy.context.active_object
    floor_slab.scale = (4.2, 4.2, 0.04)
    floor_slab.name = "ProofFloorZ0"
    fmat = bpy.data.materials.new("ProofFloorMat")
    fmat.diffuse_color = (0.32, 0.29, 0.25, 1.0)
    floor_slab.data.materials.append(fmat)

    scene.render.resolution_x = 720
    scene.render.resolution_y = 400
    cam_data.ortho_scale = 2.2
    cam.location = Vector((3.2, 0.0, 0.42))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.34)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions["EN08Down"])
    scene.frame_set(30)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / "EN08_down_ground_contact_side.png")
    bpy.ops.render.render(write_still=True)

    cam.location = Vector((2.2, -2.4, 0.65))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.32)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out_dir / "EN08_down_ground_contact_3q.png")
    bpy.ops.render.render(write_still=True)

    # Small-size ortho board-scale readability check (EN08VeilHold f18)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    cam_data.ortho_scale = 13.0
    cam.location = Vector((1.6, -3.2, 2.5))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.45)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    activate_action(arm, bpy.data.actions["EN08VeilHold"])
    scene.frame_set(18)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / "EN08_small_scale_readability.png")
    bpy.ops.render.render(write_still=True)

    # 4-way lake neighbor silhouette comparison (EN06, EN05, EN08, EN15)
    imported_objs = []
    for path_str, x_off in ((en06_glb, -2.8), (en05_glb, -1.2), (en15_glb, 1.9)):
        if path_str and Path(path_str).exists():
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=path_str)
            added = [o for o in bpy.data.objects if o not in before]
            for o in added:
                if o.parent is None:
                    o.location.x += x_off
            imported_objs.extend(added)

    if imported_objs:
        floor_slab.scale = (10.5, 5.0, 0.04)
        scene.render.resolution_x = 1120
        scene.render.resolution_y = 480
        cam_data.ortho_scale = 7.4
        cam.location = Vector((-0.3, -5.8, 2.9))
        cam.rotation_euler = (Vector((-0.3, 0.0, 0.65)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        activate_action(arm, bpy.data.actions["EN08Idle"])
        scene.frame_set(12)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / "EN08_neighbor_silhouette_compare.png")
        bpy.ops.render.render(write_still=True)

        for o in imported_objs:
            if o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)

    bpy.data.objects.remove(floor_slab, do_unlink=True)


def build_en08(args: argparse.Namespace) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24

    out_blend = Path(args.out_blend)
    out_glb = Path(args.out_glb)
    out_report = Path(args.out_report)
    tex_path = out_blend.parent / "EN08_SporeMother_Tex.png"
    tex_sha = generate_spore_mother_texture(tex_path, size=512)

    mesh, vert_tags = build_spore_mother_mesh(tex_path)
    arm = build_spore_mother_armature(mesh, vert_tags)

    # Ground rest pose strictly to Z = 0.0
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
            set_en08_pose(arm, cname, t)
            bpy.context.view_layer.update()

            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            eo.to_mesh_clear()
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
                if bn in ("sac_top", "sac.L", "sac.R"):
                    pb.keyframe_insert(data_path="scale", frame=f)

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
    activate_action(arm, bpy.data.actions["EN08Idle"])
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
        render_proofs(arm, Path(args.out_proof), args.en06_glb, args.en05_glb, args.en15_glb)

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
        re_body = next((o for o in re_meshes if o.name == "SK_EN08"), re_meshes[0])
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
        "kind": "EN08",
        "name": "雾袋孢母",
        "region": "RG04 / SALT_CROSSING",
        "move": "EN08-A 结雾 (W1, self & adjacent allies veiled up to 2 ticks; authority-driven)",
        "recipe_origin": "100% local procedural Blender Python recipe (zero external mesh/image/motion donors)",
        "rest_dimensions": rest_dims,
        "embedded_texture": {
            "name": "EN08_SporeMother_Image",
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
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EN08_BUILD_OK:", json.dumps({
        "tris": re_tris,
        "over4": re_over4,
        "actions": len(re_actions),
        "hf": hf_summary,
        "down_blend_last_z": clip_qa["EN08Down"]["last_frame_z"],
        "down_glb_last_z": re_floor.get("EN08Down", {}).get("last_frame_z"),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    build_en08(parse_args())

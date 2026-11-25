"""Generate warm frontier storybook 3D facilities for Mouting Muster Yard (Issue #7).

Produces locally authored, deterministically textured GLB assets matching P04B v0.1
and `muster_yard_ink.png`:
  - 原型/P06_首章/assets/town/T_Town_Facilities_BaseColor.png (1024x1024 hand-painted atlas)
  - 原型/P06_首章/assets/town/SM_Town_Muster.glb  (整备台)
  - 原型/P06_首章/assets/town/SM_Town_Store.glb   (仓储棚)
  - 原型/P06_首章/assets/town/SM_Town_Gate.glb    (出发门)

Run with Blender 5.3:
  blender --background --python _tools/美术/build_town_facilities.py -- --out 原型/P06_首章/assets/town
"""

import argparse
import hashlib
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector


# ---------------------------------------------------------------------------
# 1. Deterministic Hand-Painted Warm-Ink Storybook Texture Atlas (1024x1024)
# ---------------------------------------------------------------------------
# Atlas layout (4x4 grid of 256x256 swatches):
#   (0,0) stone_masonry    (1,0) timber_warm     (2,0) timber_dark     (3,0) slate_roof
#   (0,1) awning_terracotta(1,1) plaster_warm    (2,1) crate_wood      (3,1) parchment_map
#   (0,2) linen_sack       (1,2) wrought_iron    (2,2) brass_trim      (3,2) barrel_staves
#   (0,3) banner_cloth     (1,3) stone_cap       (2,3) window_frame    (3,3) wood_shield

SWATCHES = {
    "stone_masonry":     (0, 0),
    "timber_warm":       (1, 0),
    "timber_dark":       (2, 0),
    "slate_roof":        (3, 0),
    "awning_terracotta": (0, 1),
    "plaster_warm":      (1, 1),
    "crate_wood":        (2, 1),
    "parchment_map":     (3, 1),
    "linen_sack":        (0, 2),
    "wrought_iron":      (1, 2),
    "brass_trim":        (2, 2),
    "barrel_staves":     (3, 2),
    "banner_cloth":      (0, 3),
    "stone_cap":         (1, 3),
    "window_frame":      (2, 3),
    "wood_shield":       (3, 3),
}


def _hash_noise(x, y, seed=0):
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def _value_noise(u, v, freq, seed=0):
    fx = u * freq
    fy = v * freq
    ix = int(math.floor(fx))
    iy = int(math.floor(fy))
    tx = fx - ix
    ty = fy - iy
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    c00 = _hash_noise(ix, iy, seed)
    c10 = _hash_noise(ix + 1, iy, seed)
    c01 = _hash_noise(ix, iy + 1, seed)
    c11 = _hash_noise(ix + 1, iy + 1, seed)
    a = c00 + (c10 - c00) * tx
    b = c01 + (c11 - c01) * tx
    return a + (b - a) * ty


def _fbm(u, v, base_freq=6, seed=0):
    val = 0.0
    amp = 0.55
    freq = base_freq
    for i in range(3):
        val += _value_noise(u, v, freq, seed + i * 31) * amp
        freq *= 2
        amp *= 0.48
    return val


def _hex_rgb(code):
    return (int(code[0:2], 16) / 255.0, int(code[2:4], 16) / 255.0, int(code[4:6], 16) / 255.0)


def _mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t)


def generate_atlas(atlas_path):
    """Build a 1024x1024 hand-painted warm-ink watercolor atlas using Blender's Image API."""
    size = 1024
    tile = 256
    img = bpy.data.images.new("T_Town_Facilities_BaseColor", width=size, height=size, alpha=False)
    pixels = [0.0] * (size * size * 4)

    ink = _hex_rgb("3a3026")
    # Paint each 256x256 swatch
    for name, (gx, gy) in SWATCHES.items():
        # Blender image y=0 is bottom; map gy=0 to top row in UV space -> y0 = (3 - gy)*tile
        x0 = gx * tile
        y0 = (3 - gy) * tile
        for ly in range(tile):
            v = ly / float(tile - 1)
            py = y0 + ly
            row_off = py * size
            for lx in range(tile):
                u = lx / float(tile - 1)
                n = _fbm(u, v, 7, gx * 17 + gy * 43)
                fine = _value_noise(u, v, 32, gx * 7 + gy * 11)
                c = _eval_swatch(name, u, v, n, fine, ink)
                # Subtle warm watercolor paper grain
                grain = (fine - 0.5) * 0.045
                # Subtle inked border near swatch edge for crisp face definition
                edge_d = min(u, 1.0 - u, v, 1.0 - v)
                if edge_d < 0.018:
                    c = _mix(c, ink, 0.35 * (1.0 - edge_d / 0.018))
                idx = (row_off + x0 + lx) * 4
                pixels[idx + 0] = max(0.0, min(1.0, c[0] + grain))
                pixels[idx + 1] = max(0.0, min(1.0, c[1] + grain * 0.9))
                pixels[idx + 2] = max(0.0, min(1.0, c[2] + grain * 0.8))
                pixels[idx + 3] = 1.0

    img.pixels.foreach_set(pixels)
    img.filepath_raw = atlas_path
    img.file_format = "PNG"
    img.save()
    return img


def _eval_swatch(name, u, v, n, fine, ink):
    if name == "stone_masonry":
        light = _hex_rgb("c6ba9f")
        dark = _hex_rgb("877c69")
        rows = 4
        ry = v * rows
        row_i = int(math.floor(ry))
        fy = ry - row_i
        cols = 3
        rx = (u * cols) + (0.5 if row_i % 2 == 1 else 0.0)
        col_i = int(math.floor(rx))
        fx = rx - col_i
        stone_var = _hash_noise(col_i, row_i, 9)
        c = _mix(dark, light, 0.34 + 0.48 * stone_var + (n - 0.5) * 0.22)
        if fy > 0.78 and fy < 0.94:
            c = _mix(c, light, 0.38)
        if fy < 0.09 or fx < 0.06 or fx > 0.94:
            c = _mix(c, ink, 0.65)
        return c

    if name == "stone_cap":
        base = _hex_rgb("bfb39c")
        light = _hex_rgb("d8ccb4")
        c = _mix(base, light, 0.30 + 0.50 * n)
        if abs(u - 0.5) < 0.025:
            c = _mix(c, ink, 0.48)
        return c

    if name == "timber_warm":
        hi = _hex_rgb("c99d6e")
        lo = _hex_rgb("856040")
        streak = _value_noise(u * 0.6, v * 3.5, 8, 21)
        c = _mix(lo, hi, 0.36 + 0.48 * streak + (n - 0.5) * 0.18)
        for seam in (0.25, 0.50, 0.75):
            if abs(u - seam) < 0.014:
                c = _mix(c, ink, 0.62)
        return c

    if name == "timber_dark":
        hi = _hex_rgb("8f6e52")
        lo = _hex_rgb("5c4432")
        streak = _value_noise(u * 0.7, v * 3.2, 9, 33)
        c = _mix(lo, hi, 0.34 + 0.48 * streak)
        if abs(u - 0.5) < 0.015:
            c = _mix(c, ink, 0.58)
        return c

    if name == "slate_roof":
        # Matches the warm weathered slate shingles of muster_yard_ink.png
        hi = _hex_rgb("8a8c7e")
        lo = _hex_rgb("55584e")
        rows = 6
        ry = v * rows
        row_i = int(math.floor(ry))
        fy = ry - row_i
        cols = 6
        rx = u * cols + (0.5 if row_i % 2 == 1 else 0.0)
        col_i = int(math.floor(rx))
        fx = rx - col_i
        tile_var = _hash_noise(col_i, row_i, 77)
        c = _mix(lo, hi, 0.26 + 0.50 * tile_var + (n - 0.5) * 0.20)
        if fy > 0.75:
            c = _mix(c, hi, 0.34)
        if fy < 0.11:
            c = _mix(c, ink, 0.72)
        elif fx < 0.06 or fx > 0.94:
            c = _mix(c, ink, 0.50)
        return c

    if name == "awning_terracotta":
        # Warm sunlit terracotta-ochre canvas awning with woven cream trim
        hi = _hex_rgb("df8868")
        lo = _hex_rgb("a4523e")
        fold = 0.5 + 0.5 * math.sin(u * math.tau * 4.0)
        c = _mix(lo, hi, 0.32 + 0.44 * fold + (n - 0.5) * 0.20)
        if 0.08 < v < 0.16:
            c = _mix(c, _hex_rgb("f0dec0"), 0.65)
        if abs(v - 0.08) < 0.012 or abs(v - 0.16) < 0.012:
            c = _mix(c, ink, 0.52)
        for seam in (0.25, 0.50, 0.75):
            if abs(u - seam) < 0.010:
                c = _mix(c, ink, 0.42)
        return c

    if name == "plaster_warm":
        # Warm sunlit frontier plaster matching muster_yard_ink.png cottages
        hi = _hex_rgb("eadbc0")
        lo = _hex_rgb("b8a588")
        c = _mix(lo, hi, 0.44 + 0.40 * n)
        if v < 0.22:
            c = _mix(c, _hex_rgb("9e8d73"), (0.22 - v) * 2.0)
        return c

    if name == "crate_wood":
        hi = _hex_rgb("d6ac7a")
        lo = _hex_rgb("946d49")
        c = _mix(lo, hi, 0.38 + 0.44 * n)
        for sy in (0.33, 0.67):
            if abs(v - sy) < 0.018:
                c = _mix(c, ink, 0.65)
        if u < 0.11 or u > 0.89 or v < 0.11 or v > 0.89:
            c = _mix(c, lo, 0.34)
            if abs(u - 0.11) < 0.015 or abs(u - 0.89) < 0.015 or abs(v - 0.11) < 0.015 or abs(v - 0.89) < 0.015:
                c = _mix(c, ink, 0.58)
        return c

    if name == "parchment_map":
        base = _hex_rgb("f2e2c2")
        edge = _hex_rgb("cfb68e")
        c = _mix(edge, base, 0.58 + 0.32 * n)
        dist_curve = abs(v - (0.5 + 0.16 * math.sin(u * math.tau)))
        if 0.15 < u < 0.85 and dist_curve < 0.018:
            c = _mix(c, _hex_rgb("8c4d3a"), 0.75)
        if (u - 0.30) ** 2 + (v - 0.56) ** 2 < 0.0025 or (u - 0.72) ** 2 + (v - 0.42) ** 2 < 0.0025:
            c = _mix(c, ink, 0.78)
        return c

    if name == "linen_sack":
        base = _hex_rgb("e2d3b5")
        lo = _hex_rgb("b8a586")
        weave = 0.5 + 0.5 * math.sin(u * 40.0) * math.sin(v * 40.0)
        c = _mix(lo, base, 0.48 + 0.34 * n + 0.10 * weave)
        if abs(v - 0.72) < 0.025:
            c = _mix(c, _hex_rgb("7e5f42"), 0.72)
        return c

    if name == "wrought_iron":
        base = _hex_rgb("5b5852")
        hi = _hex_rgb("7a766d")
        return _mix(base, hi, 0.28 + 0.44 * n)

    if name == "brass_trim":
        base = _hex_rgb("d2ad68")
        hi = _hex_rgb("eed08d")
        return _mix(base, hi, 0.38 + 0.44 * n)

    if name == "barrel_staves":
        base = _hex_rgb("a47852")
        lo = _hex_rgb("745338")
        c = _mix(lo, base, 0.42 + 0.44 * n)
        for sx in (0.2, 0.4, 0.6, 0.8):
            if abs(u - sx) < 0.015:
                c = _mix(c, ink, 0.62)
        for band in (0.24, 0.76):
            if abs(v - band) < 0.055:
                c = _mix(_hex_rgb("55524b"), _hex_rgb("736e64"), fine)
        return c

    if name == "banner_cloth":
        base = _hex_rgb("ca6e52")
        gold = _hex_rgb("f0c87c")
        c = _mix(base, _hex_rgb("a0503c"), 0.22 + 0.30 * (1.0 - v))
        if abs(u - 0.5) < 0.09 and 0.30 < v < 0.82:
            c = _mix(c, gold, 0.85)
        if abs(v - 0.16) < 0.04:
            c = _mix(c, gold, 0.75)
        return c

    if name == "window_frame":
        return _hex_rgb("644d3b")

    if name == "wood_shield":
        base = _hex_rgb("a27652")
        rim = _hex_rgb("7a8284")
        r = math.hypot(u - 0.5, v - 0.5)
        c = _mix(base, _hex_rgb("bd8f67"), 0.38 + 0.44 * n)
        if r > 0.36:
            c = rim
        elif r < 0.12:
            c = _hex_rgb("dec078")
        return c

    return _hex_rgb("9e9482")


# ---------------------------------------------------------------------------
# 2. Mesh Building Utilities (Box/Cylinder/Prism with Clean Atlas UVs)
# ---------------------------------------------------------------------------
def _swatch_uv_bounds(swatch_name):
    gx, gy = SWATCHES[swatch_name]
    pad = 0.008
    u0 = gx * 0.25 + pad
    u1 = (gx + 1) * 0.25 - pad
    # In Blender UV space v=0 is bottom, v=1 is top; gy=0 is top row
    v0 = (3 - gy) * 0.25 + pad
    v1 = (4 - gy) * 0.25 - pad
    return u0, v0, u1, v1


def _assign_box_uvs(bm, faces, swatch_name):
    uv_layer = bm.loops.layers.uv.verify()
    u0, v0, u1, v1 = _swatch_uv_bounds(swatch_name)
    du = u1 - u0
    dv = v1 - v0
    for f in faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        coords = []
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                coords.append((co.x, co.y))
            elif ax >= ay:
                coords.append((co.y, co.z))
            else:
                coords.append((co.x, co.z))
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        sx = max(1e-4, max_x - min_x)
        sy = max(1e-4, max_y - min_y)
        for loop, (px, py) in zip(f.loops, coords):
            lu = (px - min_x) / sx
            lv = (py - min_y) / sy
            loop[uv_layer].uv = (u0 + lu * du, v0 + lv * dv)


def _add_box(bm, center, size, swatch, rot_deg=(0.0, 0.0, 0.0), bevel=0.015, mat_index=0):
    """Add a beveled box in Godot-like Y-up coords, converted to Blender Z-up."""
    # Godot (x, y, z) -> Blender (x, -z, y) so glTF export (Y-up) matches Godot exact coords!
    b_center = Vector((center[0], -center[2], center[1]))
    b_size = Vector((size[0], size[2], size[1]))
    # Convert Godot Euler (pitch X, yaw Y, roll Z) to Blender Euler
    rx, ry, rz = [math.radians(a) for a in rot_deg]
    rot_m = Euler((rx, -rz, ry), "XYZ").to_matrix().to_4x4()
    scale_m = Matrix.Diagonal((b_size.x, b_size.y, b_size.z, 1.0))
    xform = Matrix.Translation(b_center) @ rot_m @ scale_m

    existing_faces = set(bm.faces)
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=xform)
    verts = ret["verts"]
    edges = list({e for v in verts for e in v.link_edges})
    if bevel > 0.0 and min(size) > bevel * 2.5:
        bmesh.ops.bevel(
            bm, geom=edges, offset=bevel, segments=1,
            affect="EDGES", clamp_overlap=True
        )
    bm.normal_update()
    faces = [f for f in bm.faces if f not in existing_faces]
    for f in faces:
        f.material_index = mat_index
        f.smooth = False
    if swatch:
        _assign_box_uvs(bm, faces, swatch)
    return faces


def _add_cylinder(bm, center, radius_bottom, radius_top, height, swatch, segs=10, rot_deg=(0.0, 0.0, 0.0), mat_index=0):
    b_center = Vector((center[0], -center[2], center[1]))
    rx, ry, rz = [math.radians(a) for a in rot_deg]
    rot_m = Euler((rx, -rz, ry), "XYZ").to_matrix().to_4x4()
    xform = Matrix.Translation(b_center) @ rot_m
    existing_faces = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segs,
        radius1=radius_bottom, radius2=radius_top, depth=height, matrix=xform
    )
    bm.normal_update()
    faces = [f for f in bm.faces if f not in existing_faces]
    for f in faces:
        f.material_index = mat_index
        f.smooth = False
    if swatch:
        _assign_box_uvs(bm, faces, swatch)
    return faces


def _add_lantern(bm, x, y_base, z, glass_mat_idx):
    """Build a detailed wrought-iron frontier lantern with glowing amber glass panes."""
    # Stone pedestal
    _add_box(bm, (x, y_base + 0.11, z), (0.36, 0.22, 0.36), "stone_masonry", bevel=0.02)
    _add_box(bm, (x, y_base + 0.24, z), (0.40, 0.06, 0.40), "stone_cap", bevel=0.015)
    # Timber post
    _add_box(bm, (x, y_base + 0.56, z), (0.11, 0.60, 0.11), "timber_dark", bevel=0.012)
    # Iron lantern cage base & cap
    _add_box(bm, (x, y_base + 0.87, z), (0.24, 0.05, 0.24), "wrought_iron", bevel=0.008)
    _add_box(bm, (x, y_base + 1.13, z), (0.28, 0.06, 0.28), "wrought_iron", bevel=0.010)
    _add_cylinder(bm, (x, y_base + 1.21, z), 0.15, 0.03, 0.12, "wrought_iron", segs=4, rot_deg=(0, 45, 0))
    # Corner cage ribs
    for dx in (-0.095, 0.095):
        for dz in (-0.095, 0.095):
            _add_box(bm, (x + dx, y_base + 1.00, z + dz), (0.025, 0.24, 0.025), "wrought_iron", bevel=0.0)
    # Glowing amber glass core (unshaded)
    _add_box(bm, (x, y_base + 1.00, z), (0.16, 0.21, 0.16), None, bevel=0.008, mat_index=glass_mat_idx)


def _add_gabled_roof(bm, ridge_y, z_center, width, depth, pitch_deg=24.0):
    """Build a storybook pitched dark-slate roof with timber eaves, rafters, and ridge cap."""
    pitch = math.radians(pitch_deg)
    half_d = depth * 0.5
    slope_len = half_d / math.cos(pitch)
    drop_y = math.tan(pitch) * half_d * 0.5

    for side in (-1.0, 1.0):
        # Timber under-eave deck
        _add_box(
            bm,
            (0.0, ridge_y - drop_y - 0.045, z_center + side * half_d * 0.5),
            (width, 0.065, slope_len),
            "timber_dark",
            rot_deg=(side * pitch_deg, 0.0, 0.0),
            bevel=0.012,
        )
        # Stepped slate shingle courses (3 overlapping tiers for crisp silhouette)
        for tier in range(3):
            t_frac = (tier + 0.5) / 3.0
            dist = t_frac * half_d
            tier_y = ridge_y - math.tan(pitch) * dist + 0.025 + (2 - tier) * 0.012
            _add_box(
                bm,
                (0.0, tier_y, z_center + side * dist),
                (width + 0.04, 0.055, slope_len / 3.0 + 0.05),
                "slate_roof",
                rot_deg=(side * (pitch_deg - 2.0), 0.0, 0.0),
                bevel=0.010,
            )
    # Heavy ridge cap beam
    _add_box(bm, (0.0, ridge_y + 0.065, z_center), (width + 0.09, 0.09, 0.13), "slate_roof", bevel=0.016)
    # Gable fascia trim on left & right ends
    for gx in (-width * 0.49, width * 0.49):
        for side in (-1.0, 1.0):
            _add_box(
                bm,
                (gx, ridge_y - drop_y - 0.02, z_center + side * half_d * 0.5),
                (0.065, 0.11, slope_len + 0.04),
                "timber_warm",
                rot_deg=(side * pitch_deg, 0.0, 0.0),
                bevel=0.008,
            )


def _create_materials(atlas_img):
    # 0: Hand-painted storybook diffuse material
    mat_atlas = bpy.data.materials.new("M_Town_Storybook")
    mat_atlas.use_nodes = True
    nt = mat_atlas.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = atlas_img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.14

    # 1: Warm glowing amber glass (unshaded / emissive)
    mat_glass = bpy.data.materials.new("M_Town_LanternGlass")
    mat_glass.use_nodes = True
    nt_g = mat_glass.node_tree
    bsdf_g = nt_g.nodes.get("Principled BSDF")
    amber = (0.96, 0.77, 0.47, 1.0)
    bsdf_g.inputs["Base Color"].default_value = amber
    bsdf_g.inputs["Roughness"].default_value = 0.4
    if "Emission Color" in bsdf_g.inputs:
        bsdf_g.inputs["Emission Color"].default_value = amber
        bsdf_g.inputs["Emission Strength"].default_value = 1.65

    # 2: Dark warm-brown ink outline material (inverted hull, backface-only in Godot)
    mat_ink = bpy.data.materials.new("M_Town_InkOutline")
    mat_ink.use_nodes = True
    mat_ink.use_backface_culling = True
    nt_i = mat_ink.node_tree
    bsdf_i = nt_i.nodes.get("Principled BSDF")
    bsdf_i.inputs["Base Color"].default_value = (0.14, 0.11, 0.09, 1.0)
    bsdf_i.inputs["Roughness"].default_value = 1.0
    if "Specular IOR Level" in bsdf_i.inputs:
        bsdf_i.inputs["Specular IOR Level"].default_value = 0.0

    return mat_atlas, mat_glass, mat_ink


def _add_ink_outline_object(src_obj, mat_ink, thickness=0.020):
    """Create a subtle inverted-hull warm-ink outline object parented to the facility."""
    bm = bmesh.new()
    bm.from_mesh(src_obj.data)
    # Remove lantern glass faces from outline so glow stays clean
    glass_faces = [f for f in bm.faces if f.material_index == 1]
    if glass_faces:
        bmesh.ops.delete(bm, geom=glass_faces, context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Push vertices along averaged normals and flip faces for inverted-hull outline
    for v in bm.verts:
        v.co += v.normal * thickness
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    for f in bm.faces:
        f.material_index = 0
        f.smooth = False
    mesh = bpy.data.meshes.new(src_obj.name + "_InkOutlineMesh")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat_ink)
    out_obj = bpy.data.objects.new(src_obj.name + "_InkOutline", mesh)
    bpy.context.collection.objects.link(out_obj)
    return out_obj


# ---------------------------------------------------------------------------
# 3. Three Distinct Mouting Facilities
# ---------------------------------------------------------------------------
def build_muster(bm):
    """整备台 (Squad Preparation Pavilion): stone plinth, terracotta awning, war table + map, weapon rack, lantern."""
    # Stepped stone plinth
    _add_box(bm, (0.0, 0.07, 0.0), (2.52, 0.14, 1.40), "stone_masonry", bevel=0.025)
    _add_box(bm, (0.0, 0.155, 0.0), (2.38, 0.05, 1.28), "stone_cap", bevel=0.015)

    # 4 chamfered timber corner posts + diagonal knee braces
    for x in (-1.10, 1.10):
        _add_box(bm, (x, 1.02, -0.52), (0.12, 1.76, 0.12), "timber_dark", bevel=0.015)
        _add_box(bm, (x, 0.94, 0.44), (0.12, 1.60, 0.12), "timber_dark", bevel=0.015)
        # Side top beam
        _add_box(bm, (x, 1.72, -0.04), (0.10, 0.10, 1.12), "timber_warm", rot_deg=(-9.0, 0.0, 0.0), bevel=0.012)
        # Knee braces
        sign = -1.0 if x > 0 else 1.0
        _add_box(bm, (x + sign * 0.18, 1.56, 0.44), (0.34, 0.08, 0.08), "timber_dark", rot_deg=(0.0, 0.0, sign * 40.0), bevel=0.010)
    # Front & rear header beams
    _add_box(bm, (0.0, 1.66, 0.44), (2.34, 0.11, 0.10), "timber_warm", bevel=0.012)
    _add_box(bm, (0.0, 1.84, -0.52), (2.34, 0.11, 0.10), "timber_warm", bevel=0.012)

    # Gently draped terracotta-ochre canvas awning (2 sloped segments + scalloped front valance)
    _add_box(bm, (0.0, 1.85, -0.26), (2.56, 0.06, 0.68), "awning_terracotta", rot_deg=(-12.0, 0.0, 0.0), bevel=0.012)
    _add_box(bm, (0.0, 1.73, 0.25), (2.56, 0.06, 0.64), "awning_terracotta", rot_deg=(-16.0, 0.0, 0.0), bevel=0.012)
    # Scalloped front valance flaps
    for i in range(6):
        vx = -1.05 + i * 0.42
        _add_box(bm, (vx, 1.59, 0.54), (0.38, 0.16, 0.04), "awning_terracotta", bevel=0.010)
    # Timber awning rafters peeking on top
    for rx in (-0.82, 0.0, 0.82):
        _add_box(bm, (rx, 1.81, -0.03), (0.06, 0.05, 1.24), "timber_dark", rot_deg=(-14.0, 0.0, 0.0), bevel=0.008)

    # Heavy oak war-table
    for lx in (-0.82, 0.72):
        _add_box(bm, (lx, 0.50, -0.04), (0.14, 0.68, 0.84), "timber_dark", bevel=0.014)
    _add_box(bm, (-0.05, 0.44, -0.04), (1.58, 0.10, 0.12), "timber_dark", bevel=0.012)
    _add_box(bm, (-0.05, 0.88, -0.04), (1.96, 0.12, 0.96), "timber_warm", bevel=0.018)

    # Tactical parchment map, rolled scroll, brass compass, and supply satchel on table
    _add_box(bm, (-0.22, 0.955, 0.00), (1.02, 0.03, 0.64), "parchment_map", rot_deg=(0.0, 8.0, 0.0), bevel=0.006)
    _add_cylinder(bm, (0.46, 0.985, -0.18), 0.055, 0.055, 0.48, "parchment_map", segs=8, rot_deg=(90.0, 0.0, 22.0))
    _add_cylinder(bm, (-0.54, 0.99, 0.16), 0.06, 0.05, 0.06, "brass_trim", segs=8)
    _add_box(bm, (0.58, 1.04, 0.12), (0.36, 0.20, 0.28), "awning_terracotta", rot_deg=(0.0, -14.0, 0.0), bevel=0.025)

    # Side weapon rack (leaning wooden shield + spear silhouette cue for Squad Prep)
    _add_cylinder(bm, (1.28, 0.56, 0.08), 0.28, 0.28, 0.07, "wood_shield", segs=12, rot_deg=(12.0, -76.0, 0.0))
    _add_cylinder(bm, (1.22, 0.98, -0.22), 0.028, 0.024, 1.62, "timber_dark", segs=6, rot_deg=(0.0, 0.0, -11.0))
    _add_cylinder(bm, (1.38, 1.82, -0.22), 0.045, 0.006, 0.22, "wrought_iron", segs=4, rot_deg=(0.0, 0.0, -11.0))

    # Left-side standing wrought-iron lantern post
    _add_lantern(bm, -1.46, 0.0, 0.06, glass_mat_idx=1)


def build_store(bm):
    """仓储棚 (Supply & Logistics Shed): stone plinth, plaster/timber shed, slate roof, glowing window, crates/barrels/sacks."""
    # Stone foundation plinth
    _add_box(bm, (0.0, 0.09, -0.06), (2.30, 0.18, 1.62), "stone_masonry", bevel=0.025)
    _add_box(bm, (0.0, 0.19, -0.06), (2.20, 0.04, 1.52), "stone_cap", bevel=0.012)

    # Rear and side timber-framed plaster walls
    _add_box(bm, (0.0, 0.80, -0.72), (2.06, 1.24, 0.18), "plaster_warm", bevel=0.015)
    for sx in (-0.95, 0.95):
        _add_box(bm, (sx, 0.80, -0.10), (0.18, 1.24, 1.36), "plaster_warm", bevel=0.015)
        # Corner timber framing posts
        for sz in (-0.72, 0.48):
            _add_box(bm, (sx, 0.82, sz), (0.14, 1.30, 0.14), "timber_dark", bevel=0.012)
    # Right enclosed storefront bay with glowing mullioned window
    _add_box(bm, (0.48, 0.78, 0.44), (0.98, 1.18, 0.14), "plaster_warm", bevel=0.014)
    _add_box(bm, (0.0, 1.38, 0.48), (2.14, 0.14, 0.14), "timber_dark", bevel=0.014)
    # Mullioned window frame + warm glowing amber panes
    _add_box(bm, (0.50, 0.96, 0.51), (0.58, 0.48, 0.07), "window_frame", bevel=0.008)
    _add_box(bm, (0.50, 0.96, 0.535), (0.46, 0.36, 0.03), None, bevel=0.0, mat_index=1)
    # Window cross mullions & timber sill
    _add_box(bm, (0.50, 0.96, 0.555), (0.50, 0.04, 0.025), "window_frame", bevel=0.0)
    _add_box(bm, (0.50, 0.96, 0.555), (0.04, 0.40, 0.025), "window_frame", bevel=0.0)
    _add_box(bm, (0.50, 0.71, 0.55), (0.66, 0.07, 0.13), "timber_warm", bevel=0.010)
    # Small wooden eave awning over the window
    _add_box(bm, (0.50, 1.23, 0.60), (0.68, 0.05, 0.24), "timber_dark", rot_deg=(24.0, 0.0, 0.0), bevel=0.008)

    # Gabled dark-slate tile roof matching muster_yard_ink.png cottages
    _add_gabled_roof(bm, ridge_y=1.84, z_center=-0.10, width=2.48, depth=1.74, pitch_deg=24.0)
    # Gable triangle fill
    for gx in (-0.94, 0.94):
        _add_box(bm, (gx, 1.56, -0.10), (0.14, 0.36, 0.96), "timber_warm", bevel=0.012)

    # Foreground supply goods (crates, barrel, tied linen sacks) on open left bay & apron
    _add_box(bm, (-0.54, 0.42, 0.24), (0.48, 0.44, 0.46), "crate_wood", rot_deg=(0.0, 7.0, 0.0), bevel=0.016)
    _add_box(bm, (-0.06, 0.39, 0.34), (0.42, 0.38, 0.40), "crate_wood", rot_deg=(0.0, -9.0, 0.0), bevel=0.016)
    _add_box(bm, (-0.50, 0.74, 0.18), (0.36, 0.22, 0.32), "linen_sack", rot_deg=(0.0, -15.0, 0.0), bevel=0.040)
    _add_box(bm, (-0.12, 0.66, 0.30), (0.30, 0.18, 0.26), "linen_sack", rot_deg=(0.0, 18.0, 0.0), bevel=0.035)
    # Banded provision barrel standing beside right corner
    _add_cylinder(bm, (1.16, 0.44, 0.36), 0.21, 0.19, 0.56, "barrel_staves", segs=10)
    _add_cylinder(bm, (1.16, 0.73, 0.36), 0.195, 0.185, 0.04, "timber_warm", segs=10)


def build_gate(bm):
    """出发门 (Expedition Departure Archway): stone piers, braced timber gateposts, slate gatehouse roof, twin lanterns, banner."""
    # Cobblestone road threshold slab
    _add_box(bm, (0.0, 0.055, 0.12), (2.10, 0.11, 0.86), "stone_masonry", bevel=0.020)

    # Twin tapered stone pier bases & heavy timber gateposts
    for x in (-1.04, 1.04):
        _add_box(bm, (x, 0.22, 0.0), (0.50, 0.44, 0.58), "stone_masonry", bevel=0.025)
        _add_box(bm, (x, 0.47, 0.0), (0.54, 0.08, 0.62), "stone_cap", bevel=0.018)
        _add_box(bm, (x, 1.06, 0.0), (0.26, 1.14, 0.28), "timber_warm", bevel=0.018)
        # Diagonal timber knee braces under the lintel
        sign = -1.0 if x > 0 else 1.0
        _add_box(bm, (x + sign * 0.26, 1.38, 0.0), (0.48, 0.12, 0.16), "timber_dark", rot_deg=(0.0, 0.0, sign * 38.0), bevel=0.012)
        # Hanging wrought-iron bracket lantern on the front face of each gatepost
        _add_box(bm, (x, 1.32, 0.22), (0.08, 0.07, 0.28), "wrought_iron", bevel=0.008)
        _add_box(bm, (x, 1.24, 0.34), (0.22, 0.05, 0.22), "wrought_iron", bevel=0.008)
        _add_box(bm, (x, 1.11, 0.34), (0.15, 0.20, 0.15), None, bevel=0.006, mat_index=1)
        _add_box(bm, (x, 0.99, 0.34), (0.20, 0.05, 0.20), "wrought_iron", bevel=0.008)
        for dx in (-0.085, 0.085):
            _add_box(bm, (x + dx, 1.11, 0.415), (0.022, 0.22, 0.022), "wrought_iron", bevel=0.0)

    # Heavy carved overhead lintel beam & tie beam
    _add_box(bm, (0.0, 1.56, 0.0), (2.60, 0.22, 0.34), "timber_dark", bevel=0.020)
    _add_box(bm, (0.0, 1.69, 0.0), (2.42, 0.08, 0.28), "timber_warm", bevel=0.014)
    # Brass emblem plaque centered on lintel
    _add_box(bm, (0.0, 1.56, 0.18), (0.34, 0.16, 0.04), "brass_trim", bevel=0.008)

    # Gabled slate-tile gatehouse roof
    _add_gabled_roof(bm, ridge_y=2.04, z_center=0.0, width=2.84, depth=1.08, pitch_deg=26.0)

    # Hanging terracotta-ochre expedition banner beside right post (clear directional affordance)
    _add_box(bm, (1.36, 1.44, 0.04), (0.44, 0.06, 0.06), "timber_dark", bevel=0.008)
    _add_box(bm, (1.42, 1.06, 0.04), (0.34, 0.68, 0.035), "banner_cloth", rot_deg=(0.0, 6.0, 0.0), bevel=0.006)


def export_facility(name, builder_fn, out_dir, mat_atlas, mat_glass, mat_ink):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Recreate materials cleanly in fresh scene? No, keep atlas image & materials by clearing objects only.
    raise RuntimeError("Use export_all()")


def export_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    atlas_path = os.path.join(out_dir, "T_Town_Facilities_BaseColor.png")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    atlas_img = generate_atlas(atlas_path)
    mat_atlas, mat_glass, mat_ink = _create_materials(atlas_img)

    specs = [
        ("SM_Town_Muster", build_muster),
        ("SM_Town_Store", build_store),
        ("SM_Town_Gate", build_gate),
    ]
    report = {"atlas": os.path.basename(atlas_path), "facilities": []}

    for name, fn in specs:
        # Clear previous scene objects
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for m in list(bpy.data.meshes):
            if m.users == 0:
                bpy.data.meshes.remove(m)

        bm = bmesh.new()
        fn(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        mesh = bpy.data.meshes.new(name + "_Mesh")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mat_atlas)
        mesh.materials.append(mat_glass)

        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)

        for o in bpy.context.scene.objects:
            o.select_set(o == obj)
        bpy.context.view_layer.objects.active = obj

        glb_path = os.path.join(out_dir, name + ".glb")
        bpy.ops.export_scene.gltf(
            filepath=glb_path,
            export_format="GLB",
            use_selection=True,
            export_yup=True,
            export_apply=True,
            export_texcoords=True,
            export_normals=True,
            export_materials="EXPORT",
            export_image_format="AUTO",
        )

        # Measure geometry stats & SHA-256
        tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
        with open(glb_path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        report["facilities"].append({
            "name": name,
            "file": os.path.basename(glb_path),
            "bytes": os.path.getsize(glb_path),
            "triangles": tris,
            "sha256": sha,
        })
        print(f"Exported {name}.glb: {tris} tris, {os.path.getsize(glb_path)} bytes, sha256={sha[:12]}")

    with open(atlas_path, "rb") as f:
        report["atlas_sha256"] = hashlib.sha256(f.read()).hexdigest()
        report["atlas_bytes"] = os.path.getsize(atlas_path)
    print("SUMMARY_JSON:", json.dumps(report, ensure_ascii=False))


def main():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    export_all(os.path.abspath(args.out))


if __name__ == "__main__":
    main()

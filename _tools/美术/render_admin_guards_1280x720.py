"""Headless 1280x720 true-position readability proof for EN16 & EN18 on shared 90-cell CITADEL_RING.

Uses true ADMIN tick-72 entry positions (ADMIN [1,7], EN16 [-1,6], EN18 [3,6] + 6 surviving players),
read-only reuses approved ADMIN_Board.glb (f1c7be9) & shared CITADEL_RING backdrop (63e0367)
without modifying or duplicating them into this branch.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HEX_R = 0.84
TERRAIN = {
    "LOW_OBSTACLE": [(2, 3), (5, 3)],
    "HIGH_GROUND": [(0, 4), (5, 4)],
    "HIGH_OBSTACLE": [(2, 4), (3, 4)],
}

# Exact tick-72 admin-entry surviving positions from native-trace-a/checkpoints/admin-entry/save.json
ACTORS_TICK72 = [
    ("ADMIN-STORY-1", "ADMIN", "管理员 ADMIN", "enemy", (1, 7), "AdminIdle", 10),
    ("EN16-STORY-2", "EN16", "校准巡弋体 EN16", "enemy", (-1, 6), "EN16PulseHold", 18),
    ("EN18-STORY-3", "EN18", "界标钳 EN18", "enemy", (3, 6), "EN18ClampHold", 18),
    ("INIT-S01-A", "S01", "盾兵 S01", "player", (2, 1), None, 1),
    ("INIT-S03-A", "S03", "弓兵 S03", "player", (2, -1), None, 1),
    ("N-0001", "M02", "药师 M02", "player", (4, 1), None, 1),
    ("HERO-H08", "H08", "英雄 H08", "player", (5, 1), None, 1),
    ("HERO-H10", "H10", "英雄 H10", "player", (4, 0), None, 1),
    ("HERO-H11", "H11", "英雄 H11", "player", (6, 0), None, 1),
]


def load_citadel_90_cells() -> list[tuple[int, int]]:
    columns, rows, origin = 8, 9, 1
    return ([(col + origin - row // 2, row) for row in range(rows) for col in range(columns)]
            + [(q, r) for r in (-1, -2, -3) for q in range(2, 8)])


def axial_to_world(q: int, r: int, center_xy: tuple[float, float]) -> Vector:
    x = HEX_R * math.sqrt(3.0) * (q + r * 0.5) - center_xy[0]
    y = HEX_R * 1.48 * r - center_xy[1]
    z = 0.24 if (q, r) in TERRAIN["HIGH_GROUND"] else 0.0
    return Vector((x, y, z))


def render_3d_layer(p06_dir: Path, admin_glb: Path, out_rgba: Path) -> dict:
    cells_90 = load_citadel_90_cells()
    raw_xs = [HEX_R * math.sqrt(3.0) * (q + r * 0.5) for q, r in cells_90]
    raw_ys = [HEX_R * 1.48 * r for q, r in cells_90]
    center_xy = ((min(raw_xs) + max(raw_xs)) * 0.5, (min(raw_ys) + max(raw_ys)) * 0.5)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    cam_data = bpy.data.cameras.new("BoardOrtho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 24.5
    cam = bpy.data.objects.new("BoardOrtho", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -16.5, 16.5))
    cam.rotation_euler = (Vector((0.0, 1.2, 0.2)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def make_mat(name: str, rgba: tuple[float, float, float, float]):
        m = bpy.data.materials.new(name)
        m.diffuse_color = rgba
        return m

    mat_umber = make_mat("CitadelUmber", (0.39, 0.34, 0.29, 1.0))
    mat_sand = make_mat("CitadelSand", (0.64, 0.57, 0.48, 1.0))
    mat_cap = make_mat("CitadelCap", (0.75, 0.69, 0.59, 1.0))
    mat_bronze = make_mat("CitadelBronze", (0.71, 0.52, 0.29, 1.0))

    for q, r in TERRAIN["HIGH_OBSTACLE"]:
        p = axial_to_world(q, r, center_xy)
        for sz, dz, mt in [((0.78, 0.78, 0.14), 0.07, mat_umber), ((0.56, 0.56, 1.38), 0.83, mat_umber),
                           ((0.62, 0.62, 0.10), 1.24, mat_bronze), ((0.68, 0.68, 0.14), 1.59, mat_cap)]:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, dz)))
            o = bpy.context.active_object; o.scale = sz; o.data.materials.append(mt)
    for q, r in TERRAIN["LOW_OBSTACLE"]:
        p = axial_to_world(q, r, center_xy)
        for sz, dz, mt in [((0.82, 0.70, 0.14), 0.07, mat_umber), ((0.72, 0.58, 0.32), 0.30, mat_sand),
                           ((0.76, 0.62, 0.06), 0.49, mat_bronze), ((0.78, 0.64, 0.09), 0.565, mat_cap)]:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, dz)))
            o = bpy.context.active_object; o.scale = sz; o.data.materials.append(mt)
    for q, r in TERRAIN["HIGH_GROUND"]:
        p = axial_to_world(q, r, center_xy)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.74, depth=0.28, location=Vector((p.x, p.y, 0.14)))
        bpy.context.active_object.data.materials.append(mat_sand)

    model_map = {
        "ADMIN": admin_glb,
        "EN16": p06_dir / "assets/enemies/EN16_Board.glb",
        "EN18": p06_dir / "assets/enemies/EN18_Board.glb",
        "S01": p06_dir / "assets/S01-M_Shield_Feedback.glb",
        "S03": p06_dir / "assets/S03-M_Meshy_BowRuntime.glb",
        "M02": p06_dir / "assets/M02_Tripo_AidRuntime.glb",
        "H08": p06_dir / "assets/heroes/H08_Runtime.glb",
        "H10": p06_dir / "assets/heroes/H10_Runtime.glb",
        "H11": p06_dir / "assets/heroes/H11_Runtime.glb",
    }

    loaded = []
    for uid, kind, _, side, (q, r), clip_name, fr in ACTORS_TICK72:
        glb = model_map[kind]
        if not glb.is_file():
            continue
        loaded.append(uid)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb))
        added = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in added if o.parent is None]
        arm = next((o for o in added if o.type == "ARMATURE"), None)
        if arm and clip_name and clip_name in bpy.data.actions:
            ad = arm.animation_data or arm.animation_data_create()
            act = bpy.data.actions[clip_name]
            ad.action = act
            if hasattr(ad, "action_slot") and getattr(act, "slots", None) and len(act.slots) > 0:
                try:
                    ad.action_slot = act.slots[0]
                except Exception:
                    pass
            scene.frame_set(fr)
        pos = axial_to_world(q, r, center_xy)
        yaw = 0.0 if side == "enemy" else math.pi
        for rt in roots:
            rt.location = pos
            rt.rotation_euler = (0.0, 0.0, yaw)

    bpy.context.view_layer.update()

    from bpy_extras.object_utils import world_to_camera_view
    proj, offscreen = {}, []
    for q, r in cells_90:
        co = world_to_camera_view(scene, cam, axial_to_world(q, r, center_xy))
        px, py = co.x * 1280.0, (1.0 - co.y) * 720.0
        proj[f"{q},{r}"] = [round(px, 1), round(py, 1)]
        if not (0.0 <= px <= 1280.0 and 0.0 <= py <= 720.0):
            offscreen.append([q, r])

    unit_proj = []
    for uid, kind, label, side, (q, r), _, _ in ACTORS_TICK72:
        p = axial_to_world(q, r, center_xy)
        h = 2.35 if kind == "ADMIN" else (1.72 if kind in ("EN16", "EN18") else 1.85)
        co_base = world_to_camera_view(scene, cam, p)
        co_head = world_to_camera_view(scene, cam, p + Vector((0, 0, h)))
        unit_proj.append({
            "id": uid, "kind": kind, "label": label, "side": side, "cell": [q, r],
            "base": [round(co_base.x * 1280.0, 1), round((1.0 - co_base.y) * 720.0, 1)],
            "head": [round(co_head.x * 1280.0, 1), round((1.0 - co_head.y) * 720.0, 1)],
        })

    out_rgba.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_rgba)
    bpy.ops.render.render(write_still=True)
    return {"cell_count": len(cells_90), "offscreen_cells": offscreen, "loaded": loaded, "hexes": proj, "units": unit_proj}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--p06-dir", type=Path, required=True)
    p.add_argument("--admin-glb", type=Path, required=True)
    p.add_argument("--out-rgba", type=Path, required=True)
    p.add_argument("--out-meta", type=Path, required=True)
    args = p.parse_args(argv)
    meta = render_3d_layer(args.p06_dir, args.admin_glb, args.out_rgba)
    args.out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"GUARDS_RENDER_3D_OK: cells={meta['cell_count']} offscreen={len(meta['offscreen_cells'])} loaded={len(meta['loaded'])}")


if __name__ == "__main__":
    main()

"""Headless 1280x720 standalone readability proof for DEMON + shared CITADEL_RING (90 cells).

Renders REAL DEMON_Board.glb (at [1,7] in DemonCollapseHold), REAL EN04_Board.glb ([3,5]),
REAL EN17_Board.glb ([3,6]), and representative player squad GLBs in Blender Workbench
orthographic camera matching shield_stage.gd, ready to composite onto citadel_ring_ink.png
with exact CITADEL_RING 6 terrain cells (LOW_OBSTACLE [2,3],[5,3]; HIGH_GROUND [0,4],[5,4];
HIGH_OBSTACLE [2,4],[3,4]) and authoritative DEMON-A/D warning hexes.
"""
from __future__ import annotations

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

UNITS = [
    ("DEMON", "初生魔王 DEMON", "enemy", (1, 7), "assets/enemies/DEMON_Board.glb", 1.0, "DemonCollapseHold", 20),
    ("EN04", "环卫 EN04", "enemy", (3, 5), "assets/enemies/EN04_Board.glb", 1.0, None, 1),
    ("EN17", "枪卫 EN17", "enemy", (3, 6), "assets/enemies/EN17_Board.glb", 1.0, None, 1),
    ("S01A", "盾卫 S01", "player", (1, 1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S03A", "弓兵 S03", "player", (0, 2), "assets/S03-M_Meshy_BowRuntime.glb", 1.0, None, 1),
    ("M02", "药师 M02", "player", (2, 1), "assets/M02_Tripo_AidRuntime.glb", 1.0, None, 1),
    ("H08", "英雄 H08", "player", (3, 2), "assets/H08_Runtime.glb", 1.0, None, 1),
    ("H10", "英雄 H10", "player", (4, 1), "assets/H10_Runtime.glb", 1.0, None, 1),
]


def axial_to_world(q: int, r: int) -> Vector:
    dq, dr = q - 2.6, r - 3.8
    x = HEX_R * math.sqrt(3.0) * (dq + dr * 0.5 - 1.0)
    y = HEX_R * 1.48 * dr
    z = 0.22 if (q, r) in TERRAIN["HIGH_GROUND"] else 0.0
    return Vector((x, y, z))


def render_3d_layer(p06_dir: Path, out_rgba: Path) -> dict:
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
    cam_data.ortho_scale = 17.6
    cam = bpy.data.objects.new("BoardOrtho", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -13.5, 11.8))
    cam.rotation_euler = (Vector((0.0, 0.2, 0.4)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def make_mat(name: str, rgba: tuple[float, float, float, float]):
        m = bpy.data.materials.new(name)
        m.diffuse_color = rgba
        return m

    mat_stone = make_mat("CitadelStone", (0.34, 0.33, 0.32, 1.0))
    mat_dais = make_mat("CitadelDais", (0.64, 0.62, 0.57, 1.0))
    mat_bronze = make_mat("CitadelBronze", (0.66, 0.48, 0.28, 1.0))

    for q, r in TERRAIN["HIGH_OBSTACLE"]:
        p = axial_to_world(q, r)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, 0.85)))
        o = bpy.context.active_object
        o.scale = (0.66, 0.66, 1.70)
        o.data.materials.append(mat_stone)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, 1.18)))
        b = bpy.context.active_object
        b.scale = (0.72, 0.72, 0.12)
        b.data.materials.append(mat_bronze)

    for q, r in TERRAIN["LOW_OBSTACLE"]:
        p = axial_to_world(q, r)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, 0.28)))
        o = bpy.context.active_object
        o.scale = (0.76, 0.62, 0.56)
        o.data.materials.append(mat_stone)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, 0.58)))
        b = bpy.context.active_object
        b.scale = (0.80, 0.66, 0.08)
        b.data.materials.append(mat_bronze)

    for q, r in TERRAIN["HIGH_GROUND"]:
        p = axial_to_world(q, r)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.72, depth=0.28, location=Vector((p.x, p.y, 0.14)))
        o = bpy.context.active_object
        o.data.materials.append(mat_dais)

    for uid, _, side, (q, r), rel_glb, sc, clip_name, fr in UNITS:
        glb = p06_dir / rel_glb
        if not glb.is_file():
            continue
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
        pos = axial_to_world(q, r)
        yaw = 0.0 if side == "enemy" else math.pi
        for rt in roots:
            rt.location = pos
            rt.rotation_euler = (0.0, 0.0, yaw)
            rt.scale = (sc, sc, sc)

    bpy.context.view_layer.update()

    from bpy_extras.object_utils import world_to_camera_view
    proj = {}
    for q in range(-2, 9):
        for r in range(0, 9):
            co = world_to_camera_view(scene, cam, axial_to_world(q, r))
            proj[f"{q},{r}"] = [co.x * 1280.0, (1.0 - co.y) * 720.0]

    unit_proj = []
    for uid, label, side, (q, r), _, _, _, _ in UNITS:
        p = axial_to_world(q, r)
        h = 2.25 if uid == "DEMON" else 1.85
        co_base = world_to_camera_view(scene, cam, p)
        co_head = world_to_camera_view(scene, cam, p + Vector((0, 0, h)))
        unit_proj.append({
            "id": uid, "label": label, "side": side, "cell": [q, r],
            "base": [co_base.x * 1280.0, (1.0 - co_base.y) * 720.0],
            "head": [co_head.x * 1280.0, (1.0 - co_head.y) * 720.0],
        })

    out_rgba.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_rgba)
    bpy.ops.render.render(write_still=True)
    return {"hexes": proj, "units": unit_proj}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    meta = render_3d_layer(Path(argv[0]), Path(argv[1]))
    Path(argv[2]).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("CITADEL_RENDER_3D_OK:", argv[1])


if __name__ == "__main__":
    main()

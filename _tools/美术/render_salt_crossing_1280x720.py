"""Headless 1280x720 standalone readability proof for MG03 (Yilei) + SALT_CROSSING (RG04).

Renders the REAL MG03_Board.glb (at [3,7] in Mg03ChantHold), REAL EN06_Runtime.glb (at [1,6]),
and player squad GLBs in Blender Workbench orthographic camera matching shield_stage.gd,
composited onto salt_crossing_ink.png with exact 63-cell (7x9) SALT_CROSSING terrain
(HIGH_GROUND: [1,2],[5,2]; SHALLOW_WATER: row 3 + [3,2],[3,4]; LOW_OBSTACLE: [1,4],[5,4]),
EN15 marker at [5,6], hex grid lines, orange MG03-A/C warning hexes, base rings, and nameplates.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HEX_R = 0.86

TERRAIN = {
    "HIGH_GROUND": [(1, 2), (5, 2)],
    "SHALLOW_WATER": [(3, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (3, 4)],
    "LOW_OBSTACLE": [(1, 4), (5, 4)],
}

# Authoritative BATTLE-MG03 enemy positions ([3,7], [1,6], [5,6]) + representative player deployment
UNITS = [
    ("MG03", "伊蕾 MG03", "enemy", (3, 7), "assets/enemies/MG03_Board.glb", 1.0, "Mg03ChantHold", 20),
    ("EN06", "铃使 EN06", "enemy", (1, 6), "assets/enemies/EN06_Runtime.glb", 1.0, None, 1),
    ("EN15", "护卫 EN15", "enemy", (5, 6), None, 1.0, None, 1),
    ("S01A", "盾卫 S01", "player", (2, 1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S01B", "盾卫 S01", "player", (4, 1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S03A", "弓兵 S03", "player", (1, 2), "assets/S03-M_Meshy_BowRuntime.glb", 1.0, None, 1),
    ("M02", "药师 M02", "player", (5, 2), "assets/M02_Tripo_AidRuntime.glb", 1.0, None, 1),
]


def axial_to_world(q: int, r: int) -> Vector:
    # Center 7x9 board (q=0..6, r=0..8) around (3.0, 4.0)
    dq, dr = q - 3.0, r - 4.0
    x = HEX_R * math.sqrt(3.0) * (dq + (r % 2) * 0.5 - 0.25)
    y = HEX_R * 1.48 * dr
    z = 0.20 if (q, r) in TERRAIN["HIGH_GROUND"] else 0.0
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
    cam_data.ortho_scale = 20.0
    cam = bpy.data.objects.new("BoardOrtho", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -10.0, 13.5))
    cam.rotation_euler = (Vector((0.0, 1.0, 0.2)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    def make_box(name, loc, scale, color):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        o = bpy.context.active_object
        o.name = name
        o.scale = scale
        mat = bpy.data.materials.new(name + "_Mat")
        mat.diffuse_color = color
        o.data.materials.append(mat)
        return o

    # LOW_OBSTACLE: salt-crust bollards at [1,4], [5,4]
    for i, (q, r) in enumerate(TERRAIN["LOW_OBSTACLE"]):
        p = axial_to_world(q, r)
        make_box(f"SaltBollard_{i}", p + Vector((0, 0, 0.22)), (0.94, 0.50, 0.44), (0.56, 0.52, 0.46, 1.0))
        make_box(f"SaltCap_{i}", p + Vector((0, 0, 0.48)), (1.00, 0.54, 0.09), (0.85, 0.82, 0.74, 1.0))

    # HIGH_GROUND: pale salt-limestone hex terraces at [1,2], [5,2]
    for i, (q, r) in enumerate(TERRAIN["HIGH_GROUND"]):
        p = axial_to_world(q, r)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=HEX_R * 0.90, depth=0.20, location=Vector((p.x, p.y, 0.10)))
        pad = bpy.context.active_object
        pad.name = f"SaltDais_{i}"
        mat = bpy.data.materials.new(f"SaltDais_{i}_Mat")
        mat.diffuse_color = (0.89, 0.85, 0.76, 1.0)
        pad.data.materials.append(mat)

    for uid, _lbl, side, (q, r), rel_glb, sc, clip_name, frame in UNITS:
        if not rel_glb:
            continue
        glb_path = p06_dir / rel_glb
        if not glb_path.is_file():
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb_path))
        new_objs = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in new_objs if o.parent is None]
        pos = axial_to_world(q, r)
        for o in new_objs:
            if any(k in o.name for k in ("flying_arrow", "FlightArrow2", "HeldArrow2", "Icosphere")):
                o.hide_render = True
            if o.type == "ARMATURE" and clip_name and clip_name in bpy.data.actions:
                ad = o.animation_data_create()
                act = bpy.data.actions[clip_name]
                ad.action = act
                if getattr(act, "slots", None):
                    ad.action_slot = act.slots[0]
                scene.frame_set(frame)
        yaw = 0.0 if side == "enemy" else math.pi
        for rt in roots:
            rt.location = pos
            rt.rotation_euler = (0.0, 0.0, yaw)
            rt.scale = (sc, sc, sc)

    bpy.context.view_layer.update()

    from bpy_extras.object_utils import world_to_camera_view
    proj = {}
    for q in range(7):
        for r in range(9):
            co = world_to_camera_view(scene, cam, axial_to_world(q, r))
            proj[f"{q},{r}"] = [co.x * 1280.0, (1.0 - co.y) * 720.0]

    unit_proj = []
    for uid, label, side, (q, r), rel_glb, _, _, _ in UNITS:
        p = axial_to_world(q, r)
        h = 2.20 if uid == "MG03" else (1.05 if not rel_glb else 1.85)
        co_base = world_to_camera_view(scene, cam, p)
        co_head = world_to_camera_view(scene, cam, p + Vector((0, 0, h)))
        unit_proj.append({
            "id": uid, "label": label, "side": side, "cell": [q, r],
            "has_3d": bool(rel_glb),
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
    print("SALT_RENDER_3D_OK:", argv[1])


if __name__ == "__main__":
    main()

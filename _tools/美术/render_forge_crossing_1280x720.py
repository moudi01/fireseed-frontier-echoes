"""Headless 1280x720 standalone readability proof for MG04 (Helan) + FORGE_CROSSING (RG05/G).

Renders REAL MG04_Board.glb (at [2,7] in Mg04AnchorHold), REAL EN04_Board.glb ([4,5]),
REAL EN17_Board.glb ([4,6]), and player squad GLBs in Blender Workbench orthographic camera
matching shield_stage.gd, composited onto forge_crossing_ink.png with exact FORGE_CROSSING
terrain (HIGH_OBSTACLE [2,3],[6,3]; HIGH_GROUND [-1,4],[7,4]; LOW_OBSTACLE [2,4],[4,4]),
two public floor anchors ([1,4],[3,4]), orange MG04-A/C warning hexes, base rings, and nameplates.
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
    "HIGH_OBSTACLE": [(2, 3), (6, 3)],
    "HIGH_GROUND": [(-1, 4), (7, 4)],
    "LOW_OBSTACLE": [(2, 4), (4, 4)],
}
ANCHORS = [(1, 4), (3, 4)]

# Real spawn positions from local-handoff.json + representative player deployment
UNITS = [
    ("MG04", "赫岚 MG04", "enemy", (2, 7), "assets/enemies/MG04_Board.glb", 1.0, "Mg04AnchorHold", 20),
    ("EN04", "环卫 EN04", "enemy", (4, 5), "assets/enemies/EN04_Board.glb", 1.0, None, 1),
    ("EN17", "枪卫 EN17", "enemy", (4, 6), "assets/enemies/EN17_Board.glb", 1.0, None, 1),
    ("S01A", "盾卫 S01", "player", (1, 1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S01B", "盾卫 S01", "player", (4, 1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S03A", "弓兵 S03", "player", (0, 2), "assets/S03-M_Meshy_BowRuntime.glb", 1.0, None, 1),
    ("M02", "药师 M02", "player", (3, 1), "assets/M02_Tripo_AidRuntime.glb", 1.0, None, 1),
]


def axial_to_world(q: int, r: int) -> Vector:
    # Center around (q=3.0, r=3.8)
    dq, dr = q - 3.0, r - 3.8
    x = HEX_R * math.sqrt(3.0) * (dq + dr * 0.5 - 1.2)
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
    cam_data.ortho_scale = 22.0
    cam = bpy.data.objects.new("BoardOrtho", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -10.5, 13.8))
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

    # HIGH_OBSTACLE: tall basalt/iron forge pillars at [2,3], [6,3]
    for i, (q, r) in enumerate(TERRAIN["HIGH_OBSTACLE"]):
        p = axial_to_world(q, r)
        make_box(f"ForgePillar_{i}", p + Vector((0, 0, 0.85)), (0.76, 0.54, 1.70), (0.32, 0.30, 0.28, 1.0))
        make_box(f"ForgeBand_{i}", p + Vector((0, 0, 1.18)), (0.82, 0.58, 0.14), (0.64, 0.52, 0.34, 1.0))

    # LOW_OBSTACLE: low iron-bound anvil/trough barriers at [2,4], [4,4]
    for i, (q, r) in enumerate(TERRAIN["LOW_OBSTACLE"]):
        p = axial_to_world(q, r)
        make_box(f"ForgeAnvil_{i}", p + Vector((0, 0, 0.22)), (0.94, 0.48, 0.44), (0.44, 0.42, 0.40, 1.0))
        make_box(f"ForgeAnvilTop_{i}", p + Vector((0, 0, 0.48)), (1.02, 0.52, 0.09), (0.68, 0.65, 0.60, 1.0))

    # HIGH_GROUND: stepped pale foundry gantry pads at [-1,4], [7,4]
    for i, (q, r) in enumerate(TERRAIN["HIGH_GROUND"]):
        p = axial_to_world(q, r)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=HEX_R * 0.90, depth=0.20, location=Vector((p.x, p.y, 0.10)))
        pad = bpy.context.active_object
        pad.name = f"ForgeGantry_{i}"
        mat = bpy.data.materials.new(f"ForgeGantry_{i}_Mat")
        mat.diffuse_color = (0.84, 0.81, 0.76, 1.0)
        pad.data.materials.append(mat)

    for uid, _lbl, side, (q, r), rel_glb, sc, clip_name, frame in UNITS:
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
    for q in range(-2, 9):
        for r in range(0, 9):
            co = world_to_camera_view(scene, cam, axial_to_world(q, r))
            proj[f"{q},{r}"] = [co.x * 1280.0, (1.0 - co.y) * 720.0]

    unit_proj = []
    for uid, label, side, (q, r), _, _, _, _ in UNITS:
        p = axial_to_world(q, r)
        h = 2.42 if uid == "MG04" else 1.85
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
    print("FORGE_RENDER_3D_OK:", argv[1])


if __name__ == "__main__":
    main()

"""Headless 1280x720 standalone readability proof for MG02 + MIRROR_COURT.

Renders the REAL MG02_Board.glb, EN03_Runtime.glb, EN17_Board.glb, and player squad GLBs
in Blender Workbench orthographic camera matching shield_stage.gd (0, 13, 10) -> (0, 0, 0),
composited onto mirror_court_ink.png with exact MIRROR_COURT terrain cells (LOW_OBSTACLE,
HIGH_OBSTACLE, HIGH_GROUND), orange MG02-A/B telegraph warnings, enemy/ally base rings,
and 1280x720 unit nameplates — without occupying the desktop foreground window.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Hex layout (pointy-top axial q, r) centered around the v847 BATTLE-MG02 encounter
HEX_R = 0.86

TERRAIN = {
    "LOW_OBSTACLE": [(1, 4), (4, 4)],
    "HIGH_OBSTACLE": [(2, 4), (3, 4)],
    "HIGH_GROUND": [(1, 3), (6, 3), (0, 5), (5, 5)],
}

# Exact v847 BATTLE-MG02 positions from native-boss/runs/campaign/save.json
UNITS = [
    ("MG02", "赛芙 MG02", "enemy", (0, 7), "assets/enemies/MG02_Board.glb", 1.0, "BowAim", 10),
    ("EN03", "蜂卫 EN03", "enemy", (1, 5), "assets/enemies/EN03_Runtime.glb", 1.0, None, 1),
    ("EN17", "枪卫 EN17", "enemy", (4, 5), "assets/enemies/EN17_Board.glb", 1.0, None, 1),
    ("S03A", "弓兵 S03", "player", (1, 1), "assets/S03-M_Meshy_BowRuntime.glb", 1.0, None, 1),
    ("M02", "药师 M02", "player", (3, 1), "assets/M02_Tripo_AidRuntime.glb", 1.0, None, 1),
    ("S01C", "盾卫 S01", "player", (2, -1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
    ("S01A", "盾卫 S01", "player", (5, -1), "assets/S01-M_Shield_Feedback.glb", 1.0, None, 1),
]

# Representative MG02-A/B diagonal piercing telegraph line from Sev (0,7) toward player front
WARNING_HEXES = [(0, 6), (1, 5), (1, 4), (2, 3), (2, 2), (3, 1)]


def axial_to_world(q: int, r: int) -> Vector:
    # Center around (q=2.5, r=3.0)
    cq, cr = 2.5, 3.0
    dq, dr = q - cq, r - cr
    x = HEX_R * math.sqrt(3.0) * (dq + dr * 0.5)
    y = HEX_R * 1.5 * dr  # +Y = north/back in Blender
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

    # Match shield_stage.gd orthographic camera angle: (0, 13, 10) in Y-up => (0, -10, 13) in Blender Z-up
    cam_data = bpy.data.cameras.new("BoardOrtho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 20.5
    cam = bpy.data.objects.new("BoardOrtho", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -9.2, 13.5))
    direction = Vector((0.0, 2.1, 0.2)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    # Add 3D terrain props for LOW_OBSTACLE (low stone plinth) and HIGH_OBSTACLE (tall fractured mirror stele)
    def make_box(name, loc, scale, color):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.active_object
        obj.name = name
        obj.scale = scale
        mat = bpy.data.materials.new(name + "_Mat")
        mat.diffuse_color = color
        obj.data.materials.append(mat)
        return obj

    for i, (q, r) in enumerate(TERRAIN["LOW_OBSTACLE"]):
        p = axial_to_world(q, r)
        make_box(f"LowCover_{i}", p + Vector((0, 0, 0.22)), (0.96, 0.46, 0.44), (0.58, 0.50, 0.40, 1.0))
        make_box(f"LowCap_{i}", p + Vector((0, 0, 0.47)), (1.04, 0.52, 0.09), (0.76, 0.68, 0.56, 1.0))

    for i, (q, r) in enumerate(TERRAIN["HIGH_OBSTACLE"]):
        p = axial_to_world(q, r)
        make_box(f"HighStele_{i}", p + Vector((0, 0, 0.85)), (0.76, 0.44, 1.70), (0.30, 0.27, 0.24, 1.0))
        make_box(f"HighMirror_{i}", p + Vector((0, -0.23, 0.92)), (0.46, 0.06, 1.02), (0.62, 0.68, 0.66, 1.0))

    for i, (q, r) in enumerate(TERRAIN["HIGH_GROUND"]):
        p = axial_to_world(q, r)
        # Warm pale sandstone hexagonal terrace pad (clearly distinct from stone cover)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=HEX_R * 0.90, depth=0.18, location=Vector((p.x, p.y, 0.09)))
        pad = bpy.context.active_object
        pad.name = f"HighGround_{i}"
        mat = bpy.data.materials.new(f"HighGround_{i}_Mat")
        mat.diffuse_color = (0.89, 0.82, 0.68, 1.0)
        pad.data.materials.append(mat)

    # Import real unit GLBs at exact v847 positions
    for uid, _label, side, (q, r), rel_glb, sc, clip_name, frame in UNITS:
        glb_path = p06_dir / rel_glb
        if not glb_path.is_file():
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb_path))
        new_objs = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in new_objs if o.parent is None]
        pos = axial_to_world(q, r)
        # Hide flying arrow samples & icospheres
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
        # Face enemies toward south (-Y in Blender -> rot_z=0), players toward north (+Y -> rot_z=pi)
        yaw = 0.0 if side == "enemy" else math.pi
        for rt in roots:
            rt.location = pos
            rt.rotation_euler = (0.0, 0.0, yaw)
            rt.scale = (sc, sc, sc)

    bpy.context.view_layer.update()

    # Project hex centers & unit screen positions using camera matrix for 2D hex/warning/nameplate overlay
    from bpy_extras.object_utils import world_to_camera_view
    proj = {}
    for q in range(-1, 8):
        for r in range(-2, 9):
            co = world_to_camera_view(scene, cam, axial_to_world(q, r))
            proj[f"{q},{r}"] = [co.x * 1280.0, (1.0 - co.y) * 720.0]

    unit_proj = []
    for uid, label, side, (q, r), _, _, _, _ in UNITS:
        p = axial_to_world(q, r)
        h = 2.15 if uid == "MG02" else 1.85
        co_base = world_to_camera_view(scene, cam, p)
        co_head = world_to_camera_view(scene, cam, p + Vector((0, 0, h)))
        unit_proj.append({
            "id": uid,
            "label": label,
            "side": side,
            "cell": [q, r],
            "base": [co_base.x * 1280.0, (1.0 - co_base.y) * 720.0],
            "head": [co_head.x * 1280.0, (1.0 - co_head.y) * 720.0],
        })

    out_rgba.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_rgba)
    bpy.ops.render.render(write_still=True)
    return {"hexes": proj, "units": unit_proj}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p06_dir = Path(argv[0])
    out_rgba = Path(argv[1])
    out_meta = Path(argv[2])
    import json
    meta = render_3d_layer(p06_dir, out_rgba)
    out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RENDER_3D_LAYER_OK:", out_rgba)


if __name__ == "__main__":
    main()

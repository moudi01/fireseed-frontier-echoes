"""Headless 1280x720 standalone readability proof for DEMON + shared CITADEL_RING (exact 90 cells).

Reads the EXACT 90 axial cells of CITADEL_RING from 文档/执灯人_完整设计提案_v4/校验/地图地形.json,
uses real DEMON-A (tick 2, v2610) or DEMON-D (tick 7, v2615) actor positions & authoritative
locked warning cells from issue14-finale-bosses-presentation-baseline, loads real 3D GLBs
for DEMON, EN04, EN17, S01, S03, M02, and heroes H06/H08/H10/H11 (under assets/heroes/),
and guarantees all 90 cell centers stay cleanly inside the 1280x720 orthographic frame.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD_CATALOG = REPO_ROOT / "文档/执灯人_完整设计提案_v4/校验/地图地形.json"
HEX_R = 0.84

TERRAIN = {
    "LOW_OBSTACLE": [(2, 3), (5, 3)],
    "HIGH_GROUND": [(0, 4), (5, 4)],
    "HIGH_OBSTACLE": [(2, 4), (3, 4)],
}

MODEL_BY_KIND = {
    "DEMON": "assets/enemies/DEMON_Board.glb",
    "EN04": "assets/enemies/EN04_Board.glb",
    "EN17": "assets/enemies/EN17_Board.glb",
    "S01": "assets/S01-M_Shield_Feedback.glb",
    "S03": "assets/S03-M_Meshy_BowRuntime.glb",
    "M02": "assets/M02_Tripo_AidRuntime.glb",
    "H06": "assets/heroes/H06_Runtime.glb",
    "H08": "assets/heroes/H08_Runtime.glb",
    "H10": "assets/heroes/H10_Runtime.glb",
    "H11": "assets/heroes/H11_Runtime.glb",
}

LABEL_BY_KIND = {
    "DEMON": "初生魔王 DEMON",
    "EN04": "环卫 EN04",
    "EN17": "枪卫 EN17",
    "S01": "盾兵 S01",
    "S03": "弓兵 S03",
    "M02": "药师 M02",
    "H06": "英雄 H06",
    "H08": "英雄 H08",
    "H10": "英雄 H10",
    "H11": "英雄 H11",
}

# Exact authoritative unit positions from native-trace-a/checkpoints/DEMON-A (tick 2) & DEMON-D (tick 7)
SCENARIOS = {
    "A": {
        "title": "独立预览 · CITADEL_RING 90格 (1280×720) · DEMON-A 临摹号令(11格锁格 · 第2拍真站位)",
        "boss_clip": "DemonOrderHold",
        "boss_frame": 46,
        "actors": [
            ("DEMON-STORY-1", "DEMON", "enemy", (1, 6)),
            ("EN04-STORY-2", "EN04", "enemy", (4, 4)),
            ("EN17-STORY-3", "EN17", "enemy", (5, 4)),
            ("INIT-S01-A", "S01", "player", (1, 3)),
            ("INIT-S03-A", "S03", "player", (2, -1)),
            ("N-0001", "M02", "player", (4, 2)),
            ("HERO-H06", "H06", "player", (4, -1)),
            ("HERO-H08", "H08", "player", (7, -1)),
            ("HERO-H10", "H10", "player", (5, 2)),
            ("HERO-H11", "H11", "player", (4, 5)),
        ],
        "warn_cells": [
            (1, 5), (1, 4), (1, 3), (1, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 6), (2, 4), (2, 5),
        ],
    },
    "D": {
        "title": "独立预览 · CITADEL_RING 90格 (1280×720) · DEMON-D 见证崩流(30格锁区 · 第7拍真站位)",
        "boss_clip": "DemonCollapseHold",
        "boss_frame": 25,
        "actors": [
            ("DEMON-STORY-1", "DEMON", "enemy", (1, 6)),
            ("EN04-STORY-2", "EN04", "enemy", (4, 4)),
            ("EN17-STORY-3", "EN17", "enemy", (5, 4)),
            ("INIT-S01-A", "S01", "player", (1, 4)),
            ("INIT-S03-A", "S03", "player", (1, 2)),
            ("N-0001", "M02", "player", (4, 2)),
            ("HERO-H06", "H06", "player", (4, 0)),
            ("HERO-H08", "H08", "player", (7, 0)),
            ("HERO-H10", "H10", "player", (4, 3)),
            ("HERO-H11", "H11", "player", (6, 3)),
        ],
        "warn_cells": [
            (-2, 6), (-2, 7), (-2, 8), (-1, 5), (-1, 6), (-1, 7), (-1, 8),
            (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (1, 3), (1, 4), (1, 5),
            (1, 6), (1, 7), (1, 8), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8),
            (3, 4), (3, 5), (3, 6), (3, 7), (4, 4), (4, 5), (4, 6),
        ],
    },
}


def load_citadel_90_cells() -> list[tuple[int, int]]:
    """Exact 90-cell CITADEL_RING mask from 原型/火种计划_远征灰盒/board_geometry.py:
    NEAR_SQUARE (8x9 = 72 main cells, origin=1) + 3 rear deployment rows x 6 rear cols (18 cells) = 90 cells.
    """
    columns, rows, origin = 8, 9, 1
    main_cells = [(col + origin - row // 2, row) for row in range(rows) for col in range(columns)]
    rear_cells = [(q, r) for r in (-1, -2, -3) for q in range(2, 8)]
    return main_cells + rear_cells


def axial_to_world(q: int, r: int, center_xy: tuple[float, float]) -> Vector:
    x = HEX_R * math.sqrt(3.0) * (q + r * 0.5) - center_xy[0]
    y = HEX_R * 1.48 * r - center_xy[1]
    z = 0.24 if (q, r) in TERRAIN["HIGH_GROUND"] else 0.0
    return Vector((x, y, z))


def render_3d_layer(p06_dir: Path, scenario_key: str, out_rgba: Path) -> dict:
    sc_cfg = SCENARIOS[scenario_key]
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

    # Orthographic camera framed so ALL 90 real cells sit comfortably inside 1280x720
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
        for sz, dz, mt in [
            ((0.78, 0.78, 0.14), 0.07, mat_umber),
            ((0.56, 0.56, 1.38), 0.83, mat_umber),
            ((0.62, 0.62, 0.10), 1.24, mat_bronze),
            ((0.68, 0.68, 0.14), 1.59, mat_cap),
        ]:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, dz)))
            o = bpy.context.active_object
            o.scale = sz
            o.data.materials.append(mt)

    for q, r in TERRAIN["LOW_OBSTACLE"]:
        p = axial_to_world(q, r, center_xy)
        for sz, dz, mt in [
            ((0.82, 0.70, 0.14), 0.07, mat_umber),
            ((0.72, 0.58, 0.32), 0.30, mat_sand),
            ((0.76, 0.62, 0.06), 0.49, mat_bronze),
            ((0.78, 0.64, 0.09), 0.565, mat_cap),
        ]:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=p + Vector((0, 0, dz)))
            o = bpy.context.active_object
            o.scale = sz
            o.data.materials.append(mt)

    for q, r in TERRAIN["HIGH_GROUND"]:
        p = axial_to_world(q, r, center_xy)
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.74, depth=0.28, location=Vector((p.x, p.y, 0.14)))
        o = bpy.context.active_object
        o.data.materials.append(mat_sand)

    loaded_models = []
    missing_models = []
    for uid, kind, side, (q, r) in sc_cfg["actors"]:
        glb = p06_dir / MODEL_BY_KIND[kind]
        if not glb.is_file():
            missing_models.append((uid, str(glb)))
            continue
        loaded_models.append(uid)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(glb))
        added = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in added if o.parent is None]
        arm = next((o for o in added if o.type == "ARMATURE"), None)
        if arm and kind == "DEMON" and sc_cfg["boss_clip"] in bpy.data.actions:
            ad = arm.animation_data or arm.animation_data_create()
            act = bpy.data.actions[sc_cfg["boss_clip"]]
            ad.action = act
            if hasattr(ad, "action_slot") and getattr(act, "slots", None) and len(act.slots) > 0:
                try:
                    ad.action_slot = act.slots[0]
                except Exception:
                    pass
            scene.frame_set(sc_cfg["boss_frame"])
        pos = axial_to_world(q, r, center_xy)
        yaw = 0.0 if side == "enemy" else math.pi
        for rt in roots:
            rt.location = pos
            rt.rotation_euler = (0.0, 0.0, yaw)

    bpy.context.view_layer.update()

    from bpy_extras.object_utils import world_to_camera_view
    proj = {}
    offscreen = []
    for q, r in cells_90:
        co = world_to_camera_view(scene, cam, axial_to_world(q, r, center_xy))
        px, py = co.x * 1280.0, (1.0 - co.y) * 720.0
        proj[f"{q},{r}"] = [round(px, 1), round(py, 1)]
        if not (0.0 <= px <= 1280.0 and 0.0 <= py <= 720.0):
            offscreen.append([q, r])

    unit_proj = []
    for uid, kind, side, (q, r) in sc_cfg["actors"]:
        p = axial_to_world(q, r, center_xy)
        h = 2.20 if kind == "DEMON" else 1.85
        co_base = world_to_camera_view(scene, cam, p)
        co_head = world_to_camera_view(scene, cam, p + Vector((0, 0, h)))
        unit_proj.append({
            "id": uid, "kind": kind, "label": LABEL_BY_KIND[kind], "side": side, "cell": [q, r],
            "base": [round(co_base.x * 1280.0, 1), round((1.0 - co_base.y) * 720.0, 1)],
            "head": [round(co_head.x * 1280.0, 1), round((1.0 - co_head.y) * 720.0, 1)],
        })

    out_rgba.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_rgba)
    bpy.ops.render.render(write_still=True)
    return {
        "scenario": scenario_key,
        "title": sc_cfg["title"],
        "boss_clip": sc_cfg["boss_clip"],
        "cell_count": len(cells_90),
        "offscreen_cells": offscreen,
        "loaded_models": loaded_models,
        "missing_models": missing_models,
        "warn_cells": [f"{q},{r}" for q, r in sc_cfg["warn_cells"]],
        "hexes": proj,
        "units": unit_proj,
    }


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--p06-dir", type=Path, required=True)
    p.add_argument("--scenario", choices=["A", "D"], default="A")
    p.add_argument("--out-rgba", type=Path, required=True)
    p.add_argument("--out-meta", type=Path, required=True)
    args = p.parse_args(argv)
    meta = render_3d_layer(args.p06_dir, args.scenario, args.out_rgba)
    args.out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CITADEL_RENDER_3D_OK[{args.scenario}]: cells={meta['cell_count']} offscreen={len(meta['offscreen_cells'])} loaded={len(meta['loaded_models'])} missing={len(meta['missing_models'])}")


if __name__ == "__main__":
    main()

"""Add a shared rest skeleton and initial skin weights without animation clips."""

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


# Shoulder and hip elevation in fractions of the model bounds. Tall hats,
# hoods and hair change these landmarks without changing skeletal proportions.
LANDMARKS = {
    "H01": (.742, .474), "H02": (.720, .459), "H03": (.732, .470),
    "H04": (.741, .473), "H05": (.742, .495), "H06": (.735, .491),
    "H07": (.725, .456), "H08": (.755, .484), "H09": (.735, .480),
    "H10": (.762, .492), "H11": (.724, .471), "H12": (.655, .424),
    "L01": (.739, .464), "L02": (.739, .464), "M01": (.744, .470),
    "M02": (.719, .470), "M03": (.756, .483), "M04": (.710, .465),
    "M05": (.738, .476), "M06": (.713, .471), "M07": (.730, .466),
    "M08": (.749, .475), "S01-M": (.736, .474), "S01-F": (.729, .472),
    "S02-M": (.733, .465), "S02-F": (.735, .466), "S03-M": (.733, .465),
    "S03-F": (.730, .464),
}


def skeleton(code, xyz):
    height = xyz[:, 2].max()
    shoulder, hip = LANDMARKS[code]
    points = {}

    def add(name, parent, head, tail):
        points[name] = (parent, np.array(head) * height, np.array(tail) * height)

    neck = shoulder + .043
    trunk = [hip, hip + .065, shoulder - .095, shoulder - .044, neck, neck + .036]
    parent = None
    for name, lo, hi in zip(("Hips", "Spine02", "Spine01", "Spine", "neck"), trunk, trunk[1:]):
        add(name, parent, (0, 0, lo), (0, 0, hi))
        parent = name
    add("Head", "neck", (0, 0, trunk[-1]), (0, 0, .94))
    add("head_end", "Head", (0, 0, .94), (0, 0, .98))
    add("headfront", "Head", (0, -.055, .89), (0, -.095, .89))

    for side, sign in (("Left", 1), ("Right", -1)):
        hand_out = .193
        knee_x = .078
        if code in {"H01", "H05", "H10", "M01", "M03", "M05"}:
            hand_out += .024
            knee_x += .021
        wrist = (hand_out, -.022, shoulder - .218)
        elbow = (hand_out - .039, .002, shoulder - .120)
        hand_tip = (hand_out + .011, -.033, shoulder - .263)
        if side == "Right" and code in {"M07", "M08"}:
            elbow = (hand_out - .028, -.023, shoulder - .104)
            wrist = (hand_out + .020, -.119, shoulder - .024)
            hand_tip = (hand_out + .020, -.145, shoulder + .028)
        if side == "Left" and code in {"H01", "H09"}:
            elbow = (hand_out - .034, -.005, shoulder - .107)
            wrist = (hand_out - .020, -.104, shoulder - .126)
            hand_tip = (hand_out - .025, -.149, shoulder - .122)

        arm = [(hand_out - .075, 0, shoulder), elbow, wrist, hand_tip]
        leg = [(knee_x - .019, 0, hip), (knee_x, -.010, hip * .53),
               (knee_x + .008, .006, .085), (knee_x + .008, -.046, .034),
               (knee_x + .008, -.085, .030)]

        def mirror(point):
            return (sign * point[0], point[1], point[2])

        add(side + "Shoulder", "Spine", mirror((.030, 0, shoulder)), mirror(arm[0]))
        parent = side + "Shoulder"
        for label, a, b in zip(("Arm", "ForeArm", "Hand"), arm, arm[1:]):
            add(side + label, parent, mirror(a), mirror(b))
            parent = side + label
        parent = "Hips"
        for label, a, b in zip(("UpLeg", "Leg", "Foot", "ToeBase"), leg, leg[1:]):
            add(side + label, parent, mirror(a), mirror(b))
            parent = side + label
    return points


def weights_for(xyz, bones, code):
    height = xyz[:, 2].max()
    shoulder, hip = LANDMARKS[code]
    x, _, z = (xyz / height).T
    names = [n for n in bones if n not in {"head_end", "headfront"}]
    scores = []
    for name in names:
        _, a, b = bones[name]
        segment = b - a
        t = np.clip(np.sum((xyz - a) * segment, axis=1) / np.dot(segment, segment), 0, 1)
        d = np.linalg.norm(xyz - (a + t[:, None] * segment), axis=1) / height
        if name.startswith(("Left", "Right")):
            sided = x if name.startswith("Left") else -x
            d += np.maximum(0, -sided) * 2
            if name.endswith(("Arm", "Hand", "Shoulder")):
                d += np.maximum(0, .105 - sided) * 1.8
                d += np.maximum(0, hip - z) * 2
            else:
                d += np.maximum(0, z - hip) * 1.7
        if name == "Head":
            d += np.maximum(0, shoulder + .05 - z) * 2
        if name == "neck":
            d += np.abs(x) * .4
        if name.startswith(("Spine", "Hips")):
            d += np.maximum(0, np.abs(x) - .105) * 1.45
        scores.append(d)
    distance = np.stack(scores, axis=1)
    best = np.argsort(distance, axis=1)[:, :4]
    nearest = np.take_along_axis(distance, best, axis=1)
    value = np.exp(-(nearest - nearest[:, :1]) / .019)
    value[value < .04] = 0
    value /= value.sum(axis=1, keepdims=True)
    return names, best, value


def bind(source, target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source), merge_vertices=True)
    body, = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    data = bpy.data.armatures.new("FireseedHumanoid")
    arm = bpy.data.objects.new("FireseedHumanoid", data)
    bpy.context.collection.objects.link(arm)
    code = source.stem.split("_")[0]
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    coords = np.array([tuple(v.co) for v in body.data.vertices])
    layout = skeleton(code, coords)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (parent, head, tail) in layout.items():
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = Vector(head), Vector(tail)
        if parent is not None:
            bone.parent = data.edit_bones[parent]
        bone.use_deform = name not in {"head_end", "headfront"}
        bone.align_roll(Vector((0, 1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")

    names, indices, values = weights_for(coords, layout, code)
    groups = [body.vertex_groups.new(name=name) for name in names]
    for vertex, (row, weights) in enumerate(zip(indices, values)):
        for index, weight in zip(row, weights):
            if weight:
                groups[index].add([vertex], float(weight), "REPLACE")
    modifier = body.modifiers.new("Skin", "ARMATURE")
    modifier.object = arm
    body.parent = arm
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    arm.select_set(True)
    tmp = target.with_suffix(".building.glb")
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(tmp), export_format="GLB", use_selection=True,
            export_animations=False, export_image_format="AUTO",
        )
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    source_dir, output_dir = map(Path, sys.argv[sys.argv.index("--") + 1:])
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(source_dir.glob("*.json"))
    for report in sources:
        record = json.loads(report.read_text(encoding="utf-8"))
        source = source_dir / record["file"]
        target = output_dir / source.name
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            continue
        bind(source, target)
        print("BOUND", target.name, flush=True)


if __name__ == "__main__":
    main()

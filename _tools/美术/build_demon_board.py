"""Build DEMON_Board.blend and DEMON_Board.glb for #14 (初生魔王 DEMON / CITADEL_RING).

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/DEMON_skinned.blend
(single watertight mesh with bronze halo arcs + solid collar-mount struts, shoulder cape,
and left bronze wrist cuff) and retargets project-owned animations from
S02-M_Meshy_24_Keyframe_Actions.blend + M04_Meshy_Mist_Cast.blend.

Outputs:
- Editable .blend (DEMON_Board.blend)
- Game-ready GLB (DEMON_Board.glb) with 26 clips:
  Core (6): DemonIdle, DemonWalk, DemonStop, DemonAttack, DemonHit, DemonDown
  DEMON-A 临摹号令·扩域 (4): DemonOrderRaise/Hold/Release/Cancel
  DEMON-B 样本回声·扩域 (4): DemonEchoRaise/Hold/Release/Cancel (archive-only move, not fabricated as A-line sample)
  DEMON-C 未解之问 (4): DemonShieldRaise/Hold/Release/Cancel
  DEMON-D 见证崩流 (4): DemonCollapseRaise/Hold/Release/Cancel (supports tick-44 real interrupt)
  Mirror-Learn / Adapted Skill (4): DemonMimicRaise/Hold/Release/Cancel
- JSON QA & clean-blend round-trip report
- Optional 6-panel orthogonal silhouette proof renders (Idle, A, B, C, D, Mimic)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

# RIG_DEMON (21 bones) <- S02-M_Meshy / M04_Meshy donor bones
BONE_MAP = [
    ("root", "Root", "delta"),
    ("pelvis", "Hips", "delta"),
    ("spine_01", "Spine", "delta"),
    ("spine_02", "Spine01", "delta"),
    ("chest", "Spine02", "delta"),
    ("neck", "neck", "delta"),
    ("head", "Head", "delta"),
    ("clavicle.L", "LeftShoulder", "align"),
    ("upper_arm.L", "LeftArm", "align"),
    ("forearm.L", "LeftForeArm", "align"),
    ("hand.L", "LeftHand", "align"),
    ("clavicle.R", "RightShoulder", "align"),
    ("upper_arm.R", "RightArm", "align"),
    ("forearm.R", "RightForeArm", "align"),
    ("hand.R", "RightHand", "align"),
    ("thigh.L", "LeftUpLeg", "align"),
    ("shin.L", "LeftLeg", "align"),
    ("foot.L", "LeftFoot", "align"),
    ("thigh.R", "RightUpLeg", "align"),
    ("shin.R", "RightLeg", "align"),
    ("foot.R", "RightFoot", "align"),
]

BASE_CLIPS = [
    ("DemonIdle", "S02-M_Meshy_01_Idle", "idle", "base"),
    ("DemonWalk", "S02-M_Meshy_02_Walk", "walk", "base"),
    ("DemonStop", "S02-M_Meshy_08_WalkStop", "stop", "base"),
    ("DemonAttack", "S02-M_Meshy_04_LowCut", "attack", "base"),
    ("DemonHit", "S02-M_Meshy_13_HitLight", "hit", "base"),
    ("DemonDown", "S02-M_Meshy_06_Down", "down", "base"),
]

SKILL_CLIPS = [
    # DEMON-A: 临摹号令·扩域 (physical front-axis command point)
    ("DemonOrderRaise", "S02-M_Meshy_17_RaiseGuard", "A_raise", "base"),
    ("DemonOrderHold", "S02-M_Meshy_05_GuardHold", "A_hold", "base"),
    ("DemonOrderRelease", "S02-M_Meshy_19_HeavyCut", "A_release", "base"),
    ("DemonOrderCancel", "S02-M_Meshy_18_LowerGuard", "A_cancel", "base"),
    # DEMON-B: 样本回声·扩域 (magic spell echo — archive-only, never fabricated as A-line sample)
    ("DemonEchoRaise", "M04_Meshy_01_RaisePalm", "B_raise", "cast"),
    ("DemonEchoHold", "M04_Meshy_02_AimHold", "B_hold", "cast"),
    ("DemonEchoRelease", "M04_Meshy_03_MistRelease", "B_release", "cast"),
    ("DemonEchoCancel", "M04_Meshy_04_MistCancel", "B_cancel", "cast"),
    # DEMON-C: 未解之问 (self-shield 52, empty lock, crossed-arm chest guard)
    ("DemonShieldRaise", "S02-M_Meshy_17_RaiseGuard", "C_raise", "base"),
    ("DemonShieldHold", "S02-M_Meshy_05_GuardHold", "C_hold", "base"),
    ("DemonShieldRelease", "S02-M_Meshy_21_BlockImpact", "C_release", "base"),
    ("DemonShieldCancel", "S02-M_Meshy_18_LowerGuard", "C_cancel", "base"),
    # DEMON-D: 见证崩流 (radius-3 AoE threat circle, W3, interruptible at tick 44!)
    ("DemonCollapseRaise", "M04_Meshy_01_RaisePalm", "D_raise", "cast"),
    ("DemonCollapseHold", "M04_Meshy_02_AimHold", "D_hold", "cast"),
    ("DemonCollapseRelease", "M04_Meshy_03_MistRelease", "D_release", "cast"),
    ("DemonCollapseCancel", "M04_Meshy_04_MistCancel", "D_cancel", "cast"),
    # Mirror-Learn / Adapted Skill (MIMIC-* generic presentation)
    ("DemonMimicRaise", "M04_Meshy_01_RaisePalm", "M_raise", "cast"),
    ("DemonMimicHold", "M04_Meshy_02_AimHold", "M_hold", "cast"),
    ("DemonMimicRelease", "M04_Meshy_03_MistRelease", "M_release", "cast"),
    ("DemonMimicCancel", "M04_Meshy_04_MistCancel", "M_cancel", "cast"),
]

TARGET_HEIGHT = 2.08
DECIMATE_RATIO = 0.32


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--donor-base", required=True)
    p.add_argument("--donor-cast", required=True)
    p.add_argument("--out-glb", required=True)
    p.add_argument("--out-blend", required=True)
    p.add_argument("--out-report", required=True)
    p.add_argument("--out-proof", default="")
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


def sample_donor_file(blend_path: str, needed_actions: list[str]) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    rest_rot, rest_dir, rest_head = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        rest_rot[b.name] = m.to_3x3().normalized()
        rest_head[b.name] = arm.matrix_world @ b.head_local
        rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - rest_head[b.name]).normalized()

    clips = {}
    for act_name in sorted(set(needed_actions)):
        act = bpy.data.actions[act_name]
        activate_action(arm, act)
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        step = 2 if (f1 - f0) > 40 else 1
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        samples = []
        for f in frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            bdata = {}
            for _, d_bn, _ in BONE_MAP:
                pb = arm.pose.bones[d_bn]
                mw = arm.matrix_world @ pb.matrix
                bdata[d_bn] = (
                    arm.matrix_world @ pb.head,
                    arm.matrix_world @ pb.tail,
                    mw.to_3x3().normalized(),
                )
            samples.append({"frame": f, "bones": bdata})
        clips[act_name] = {"f0": f0, "f1": f1, "frames": samples}
    return {
        "fps": scene.render.fps,
        "hips_z": rest_head["Hips"].z,
        "rest_rot": rest_rot,
        "rest_dir": rest_dir,
        "rest_head": rest_head,
        "clips": clips,
    }


def enforce_max_4_weights(mesh_obj) -> dict:
    me = mesh_obj.data
    before_over = 0
    for v in me.vertices:
        pairs = [(g.group, g.weight) for g in v.groups if g.weight > 1e-6]
        if len(pairs) > 4:
            before_over += 1
        if not pairs:
            continue
        pairs.sort(key=lambda kv: kv[1], reverse=True)
        keep = pairs[:4]
        total = sum(w for _, w in keep)
        if total <= 1e-8:
            continue
        keep_ids = {gid for gid, _ in keep}
        for g in list(v.groups):
            if g.group not in keep_ids:
                mesh_obj.vertex_groups[g.group].remove([v.index])
        for gid, w in keep:
            mesh_obj.vertex_groups[gid].add([v.index], w / total, "REPLACE")
    after_over = sum(1 for v in me.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4)
    unweighted = sum(1 for v in me.vertices if len([g for g in v.groups if g.weight > 1e-6]) == 0)
    return {
        "verts": len(me.vertices),
        "before_over_4": before_over,
        "after_over_4": after_over,
        "unweighted": unweighted,
    }


def clean_body_topology(mesh_obj) -> dict:
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    wires = [e for e in bm.edges if len(e.link_faces) == 0]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES")
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    visited = set()
    islands = []
    for v in bm.verts:
        if v.index in visited:
            continue
        st, comp = [v], []
        visited.add(v.index)
        while st:
            c = st.pop()
            comp.append(c)
            for e in c.link_edges:
                o = e.other_vert(c)
                if o.index not in visited:
                    visited.add(o.index)
                    st.append(o)
        islands.append(len(comp))
    islands.sort(reverse=True)
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()
    return {"wires_removed": len(wires), "loose_removed": len(loose), "islands": islands}


def skill_pose_overlay(tag: str, progress: float) -> tuple[dict[str, tuple[float, float, float]], dict[str, tuple[Vector, float]]]:
    """Unmistakable non-color-dependent 1280x720 silhouettes (character faces -Y, right=-X, left=+X, up=+Z):
    A (Order):   Right arm extended sharply forward-high pointing along front axis; left cuff arm braced back.
    B (Echo):    Left bronze-cuff arm swept wide & forward-low echoing witnessed cells; right hand poised at chest.
    C (Shield):  Both forearms crossed tightly over chest medallion (X-guard self-shield 52).
    D (Collapse):BOTH arms raised HIGH & WIDE framing the two bronze halo arcs (W3 AoE; sharp recoil on cancel).
    M (Mimic):   Left bronze-cuff arm raised vertically beside halo arc, right arm mirroring forward-outward.
    """
    if tag.endswith("_raise"):
        w = min(1.0, progress * 1.25)
    elif tag.endswith("_hold"):
        w = 0.94 + 0.06 * math.sin(progress * math.pi * 2.0)
    elif tag.endswith("_release"):
        w = 1.0 - 0.55 * max(0.0, (progress - 0.35) / 0.65)
    elif tag.endswith("_cancel"):
        w = max(0.0, 1.0 - progress * 1.15)
    else:
        return {}, {}

    if tag.startswith("A_"):
        # DEMON-A 临摹号令·扩域: sharp right-hand forward command point along front axis
        surge = math.sin(min(1.0, progress / 0.50) * math.pi) if tag == "A_release" else 0.0
        return (
            {"spine_02": (8.0 * w + 10.0 * surge, 12.0 * w, 0.0)},
            {
                "upper_arm.R": (Vector((-0.34, -0.86, 0.38 - 0.35 * surge)).normalized(), w),
                "forearm.R": (Vector((-0.18, -0.96, 0.22 - 0.42 * surge)).normalized(), w),
                "upper_arm.L": (Vector((0.64, 0.32, -0.70)).normalized(), 0.90 * w),
                "forearm.L": (Vector((0.46, 0.14, -0.88)).normalized(), 0.90 * w),
            },
        )
    if tag.startswith("B_"):
        # DEMON-B 样本回声·扩域: left bronze-cuff arm swept wide & low echoing cells; right hand poised at chest
        surge = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "B_release" else 0.0
        return (
            {"spine_02": (6.0 * w, -16.0 * w, 0.0)},
            {
                "upper_arm.L": (Vector((0.78, -0.52, -0.35 + 0.28 * surge)).normalized(), w),
                "forearm.L": (Vector((0.62, -0.74, -0.26 + 0.36 * surge)).normalized(), w),
                "upper_arm.R": (Vector((-0.36, -0.44, -0.82)).normalized(), w),
                "forearm.R": (Vector((0.28, -0.78, 0.56)).normalized(), w),
            },
        )
    if tag.startswith("C_"):
        # DEMON-C 未解之问 (self-shield 52): crossed forearms bracing over chest medallion
        pulse = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "C_release" else 0.0
        return (
            {"spine_01": (-8.0 * w - 4.0 * pulse, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.44, -0.68, -0.58)).normalized(), w),
                "forearm.L": (Vector((-0.52, -0.72, 0.46)).normalized(), w),
                "upper_arm.R": (Vector((-0.44, -0.68, -0.58)).normalized(), w),
                "forearm.R": (Vector((0.52, -0.72, 0.46)).normalized(), w),
            },
        )
    if tag.startswith("D_"):
        # DEMON-D 见证崩流 (radius-3 AoE, W3, interruptible): BOTH arms raised HIGH & WIDE framing the bronze arcs!
        if tag == "D_release":
            slam = math.sin(min(1.0, progress / 0.55) * math.pi)
            return (
                {"spine_02": (16.0 * slam, 0.0, 0.0)},
                {
                    "upper_arm.L": (Vector((0.70, -0.64, 0.32 - 0.72 * slam)).normalized(), w),
                    "forearm.L": (Vector((0.52, -0.76, 0.38 - 0.85 * slam)).normalized(), w),
                    "upper_arm.R": (Vector((-0.70, -0.64, 0.32 - 0.72 * slam)).normalized(), w),
                    "forearm.R": (Vector((-0.52, -0.76, 0.38 - 0.85 * slam)).normalized(), w),
                },
            )
        if tag == "D_cancel":
            # Sharp interrupt recoil (tick-44 hero_interrupt)
            return (
                {"spine_02": (-16.0 * w, 0.0, 0.0)},
                {
                    "upper_arm.L": (Vector((0.68, 0.24, -0.69)).normalized(), w),
                    "forearm.L": (Vector((0.55, -0.38, -0.74)).normalized(), w),
                    "upper_arm.R": (Vector((-0.68, 0.24, -0.69)).normalized(), w),
                    "forearm.R": (Vector((-0.55, -0.38, -0.74)).normalized(), w),
                },
            )
        return (
            {"spine_02": (-10.0 * w, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.76, -0.18, 0.62)).normalized(), w),
                "forearm.L": (Vector((0.52, -0.26, 0.81)).normalized(), w),
                "upper_arm.R": (Vector((-0.76, -0.18, 0.62)).normalized(), w),
                "forearm.R": (Vector((-0.52, -0.26, 0.81)).normalized(), w),
            },
        )
    if tag.startswith("M_"):
        # Mirror-Learning / Adapted Skill (MIMIC-*): left bronze-cuff arm lifted toward halo arc, right mirroring out
        surge = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "M_release" else 0.0
        return (
            {"spine_02": (-4.0 * w + 8.0 * surge, -14.0 * w, 0.0)},
            {
                "upper_arm.L": (Vector((0.62, -0.32, 0.72)).normalized(), w),
                "forearm.L": (Vector((0.28, -0.44, 0.85)).normalized(), w),
                "upper_arm.R": (Vector((-0.68, -0.58, -0.45 + 0.35 * surge)).normalized(), w),
                "forearm.R": (Vector((-0.44, -0.86, -0.26 + 0.45 * surge)).normalized(), w),
            },
        )
    return {}, {}


def apply_world_dir_target(arm, bn: str, target_dir_w: Vector, blend: float, t_rest_rot: dict) -> None:
    if blend <= 1e-4:
        return
    pb = arm.pose.bones.get(bn)
    if not pb:
        return
    bpy.context.view_layer.update()
    cur_m = (arm.matrix_world @ pb.matrix).to_3x3().normalized()
    cur_dir_w = (cur_m @ Vector((0.0, 1.0, 0.0))).normalized()
    q_delta_w = cur_dir_w.rotation_difference(target_dir_w.normalized())
    q_step_w = Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(q_delta_w, min(1.0, max(0.0, blend)))
    desired_w = q_step_w.to_matrix() @ cur_m
    if pb.parent:
        parent_pose_w = (arm.matrix_world @ pb.parent.matrix).to_3x3().normalized()
        inherited_w = parent_pose_w @ t_rest_rot[pb.parent.name].inverted() @ t_rest_rot[bn]
    else:
        inherited_w = t_rest_rot[bn]
    pb.rotation_quaternion = (inherited_w.inverted() @ desired_w).to_quaternion().normalized()
    bpy.context.view_layer.update()


def build_demon(args: argparse.Namespace) -> dict:
    base_actions = [d for _, d, _, src in BASE_CLIPS + SKILL_CLIPS if src == "base"]
    cast_actions = [d for _, d, _, src in BASE_CLIPS + SKILL_CLIPS if src == "cast"]
    donors = {
        "base": sample_donor_file(args.donor_base, base_actions),
        "cast": sample_donor_file(args.donor_cast, cast_actions),
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    scene.render.fps = donors["base"]["fps"]

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA" or obj.name == "Icosphere":
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    arm = bpy.data.objects["RIG_DEMON"]
    mesh = bpy.data.objects["SK_DEMON"]

    # 1. Scale cleanly to TARGET_HEIGHT (2.08m) and ground Z=0
    zs = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    scale_fac = TARGET_HEIGHT / (max(zs) - min(zs))
    arm.scale = (scale_fac, scale_fac, scale_fac)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    zs2 = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    if abs(min(zs2)) > 1e-4:
        arm.location.z -= min(zs2)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    # 2. Decimate SK_DEMON + clean topology + enforce max-4 normalized weights
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Decimate_P06", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    topo_stats = clean_body_topology(mesh)
    skin_limit_stats = enforce_max_4_weights(mesh)
    body_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    # 3. Precompute DEMON rest data
    bpy.context.view_layer.update()
    t_rest_rot, t_rest_dir, t_rest_head = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        t_rest_rot[b.name] = m.to_3x3().normalized()
        t_rest_head[b.name] = arm.matrix_world @ b.head_local
        t_rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - t_rest_head[b.name]).normalized()

    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # 4. Retarget all 26 clips
    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()
    all_specs = BASE_CLIPS + SKILL_CLIPS
    for out_name, donor_act_name, tag, src_key in all_specs:
        donor = donors[src_key]
        clip_data = donor["clips"][donor_act_name]
        hips_ratio = t_rest_head["pelvis"].z / max(donor["hips_z"], 1e-4)
        act = bpy.data.actions.new(name=out_name)
        act.use_fake_user = True
        activate_action(arm, act)

        f_start, f_end = clip_data["f0"], clip_data["f1"]
        span = max(1, f_end - f_start)

        for sample in clip_data["frames"]:
            f = sample["frame"]
            progress = (f - f_start) / span
            scene.frame_set(f)

            for pb in arm.pose.bones:
                pb.location = Vector((0.0, 0.0, 0.0))
                pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
                pb.scale = Vector((1.0, 1.0, 1.0))

            for t_bn, d_bn, mode in BONE_MAP:
                pb = arm.pose.bones[t_bn]
                d_head, _, d_rot = sample["bones"][d_bn]
                if mode == "delta":
                    d_delta = d_rot @ donor["rest_rot"][d_bn].inverted()
                    desired_w = d_delta @ t_rest_rot[t_bn]
                else:
                    q_align = t_rest_dir[t_bn].rotation_difference(donor["rest_dir"][d_bn]).to_matrix()
                    d_delta = d_rot @ donor["rest_rot"][d_bn].inverted()
                    desired_w = d_delta @ q_align @ t_rest_rot[t_bn]

                if pb.parent:
                    parent_pose_w = (arm.matrix_world @ pb.parent.matrix).to_3x3().normalized()
                    inherited_w = parent_pose_w @ t_rest_rot[pb.parent.name].inverted() @ t_rest_rot[t_bn]
                else:
                    inherited_w = t_rest_rot[t_bn]

                pb.rotation_quaternion = (inherited_w.inverted() @ desired_w).to_quaternion().normalized()
                if t_bn == "pelvis":
                    d_disp = (d_head - donor["rest_head"][d_bn]) * hips_ratio
                    pb.location = inherited_w.inverted() @ d_disp
                bpy.context.view_layer.update()

            overlays, world_targets = skill_pose_overlay(tag, progress)
            for bn, deg_xyz in overlays.items():
                pb_o = arm.pose.bones.get(bn)
                if pb_o:
                    q_add = Euler(tuple(math.radians(a) for a in deg_xyz), "XYZ").to_quaternion()
                    pb_o.rotation_quaternion = (pb_o.rotation_quaternion @ q_add).normalized()
            for bn in ("upper_arm.R", "forearm.R", "upper_arm.L", "forearm.L"):
                if bn in world_targets:
                    target_dir_w, blend = world_targets[bn]
                    apply_world_dir_target(arm, bn, target_dir_w, blend, t_rest_rot)
            bpy.context.view_layer.update()

            if out_name != "DemonDown":
                eo = mesh.evaluated_get(deps)
                me = eo.to_mesh()
                min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
                eo.to_mesh_clear()
                if min_z < 0.0:
                    pb_p = arm.pose.bones["pelvis"]
                    lift_w = Vector((0.0, 0.0, -min_z))
                    parent_pose_w = (arm.matrix_world @ pb_p.parent.matrix).to_3x3().normalized()
                    inherited_w = parent_pose_w @ t_rest_rot["root"].inverted() @ t_rest_rot["pelvis"]
                    pb_p.location += inherited_w.inverted() @ lift_w
                    bpy.context.view_layer.update()

            for t_bn, _, _ in BONE_MAP:
                pb = arm.pose.bones[t_bn]
                pb.keyframe_insert(data_path="rotation_quaternion", frame=f)
                if t_bn in ("root", "pelvis"):
                    pb.keyframe_insert(data_path="location", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = out_name
        strip = tr.strips.new(out_name, f_start, act)
        strip.action_frame_start = f_start
        strip.action_frame_end = f_end

    # 5. QA audit across representative clips
    qa_audit = audit_demon_qa(arm, mesh)

    activate_action(arm, bpy.data.actions["DemonIdle"])
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # 6. Save editable .blend
    out_blend = Path(args.out_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    # 7. Export GLB
    out_glb = Path(args.out_glb)
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

    # 8. Render 6 orthogonal pose proof panels (Idle, A, B, C, D, Mimic)
    if args.out_proof:
        render_pose_proof(arm, Path(args.out_proof))

    # 9. Clean-blend round-trip re-import verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 1), round(a.frame_range[1], 1)] for a in bpy.data.actions}
    re_bones = [b.name for b in re_arm.data.bones] if re_arm else []
    re_over4 = {
        o.name: sum(1 for v in o.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4)
        for o in re_meshes
    }
    expected_names = {n for n, _, _, _ in all_specs}
    roundtrip = {
        "armature": re_arm.name if re_arm else None,
        "bone_count": len(re_bones),
        "mesh_names": sorted(o.name for o in re_meshes),
        "total_tris": re_tris,
        "verts_over_4_influences": re_over4,
        "material_count": len(bpy.data.materials),
        "image_count": len(bpy.data.images),
        "action_count": len(re_actions),
        "expected_clips_present": expected_names.issubset(set(re_actions.keys())),
        "actions": dict(sorted(re_actions.items())),
    }

    report = {
        "source_blend": str(Path(args.source).resolve()),
        "source_blend_sha256": sha256_file(Path(args.source)),
        "donor_base_blend": str(Path(args.donor_base).resolve()),
        "donor_base_sha256": sha256_file(Path(args.donor_base)),
        "donor_cast_blend": str(Path(args.donor_cast).resolve()),
        "donor_cast_sha256": sha256_file(Path(args.donor_cast)),
        "out_glb": str(out_glb.resolve()),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend.resolve()),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "target_height": TARGET_HEIGHT,
        "decimated_body_tris": body_tris,
        "topology": topo_stats,
        "skin_limit_4": skin_limit_stats,
        "qa_audit": qa_audit,
        "roundtrip": roundtrip,
    }
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DEMON_BUILD_OK:", json.dumps(roundtrip, ensure_ascii=False))
    return report


def audit_demon_qa(arm, mesh) -> dict:
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    clips = {}
    for cname in [
        "DemonIdle", "DemonWalk", "DemonAttack", "DemonDown",
        "DemonOrderHold", "DemonEchoHold", "DemonShieldHold",
        "DemonCollapseHold", "DemonCollapseCancel", "DemonMimicHold",
    ]:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        f_mid = int(round((act.frame_range[0] + act.frame_range[1]) * 0.5))
        scene.frame_set(f_mid)
        bpy.context.view_layer.update()
        eo = mesh.evaluated_get(deps)
        me = eo.to_mesh()
        min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
        max_z = max((mesh.matrix_world @ v.co).z for v in me.vertices)
        degen = sum(1 for p in me.polygons if p.area < 1e-8)
        eo.to_mesh_clear()

        hr_z = (arm.matrix_world @ arm.pose.bones["hand.R"].tail).z
        hl_z = (arm.matrix_world @ arm.pose.bones["hand.L"].tail).z
        clips[cname] = {
            "sample_frame": f_mid,
            "body_min_z": round(min_z, 4),
            "body_max_z": round(max_z, 3),
            "right_hand_z": round(hr_z, 3),
            "left_hand_z": round(hl_z, 3),
            "degenerate_faces": degen,
        }
    return {"clips": clips}


def render_pose_proof(arm, out_dir: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 560
    scene.render.resolution_y = 360
    scene.render.film_transparent = False
    if scene.world:
        scene.world.color = (0.86, 0.84, 0.81)

    cam_data = bpy.data.cameras.new("ProofCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.85
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.4, -3.2, 2.3))
    cam.rotation_euler = (Vector((0.0, 0.0, 1.05)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in [
        ("0_idle", "DemonIdle", 10),
        ("1_A_order", "DemonOrderHold", 20),
        ("2_B_echo", "DemonEchoHold", 20),
        ("3_C_shield", "DemonShieldHold", 20),
        ("4_D_collapse", "DemonCollapseHold", 20),
        ("5_M_mimic", "DemonMimicHold", 20),
    ]:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_demon(parse_args())

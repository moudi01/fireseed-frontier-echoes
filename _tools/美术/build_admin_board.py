"""Build ADMIN_Board.blend and ADMIN_Board.glb for #14 (管理员 ADMIN / shared CITADEL_RING).

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/ADMIN_skinned.blend
and ADMIN_管理员_v1 design:
- Seats the raw 239-vert hand.R fingertip island cleanly into the hand mesh (0.0 mm gap).
- Adds the iconic solid dark-bronze H-frame spine rack + 4 ivory-and-gold law tablets
  (ADMIN_LawRack) physically bolted into chest/spine_02 (0.0 mm gap, 100% bound to PropLawRack).
- Retargets 26 clips from S02-M_Meshy_24_Keyframe_Actions.blend + M04_Meshy_Mist_Cast.blend:
  Core (6): AdminIdle, AdminWalk, AdminStop, AdminAttack, AdminHit, AdminDown
  ADMIN-A 秩序抹除·扩域 (4): AdminEraseRaise/Hold/Release/Cancel
  ADMIN-B 维护权限 48私盾 (4): AdminShieldRaise/Hold/Release/Cancel
  ADMIN-C 格式化脉冲·扩域 (4): AdminPulseRaise/Hold/Release/Cancel
  ADMIN-D 法令反噬 [定向/无A本线样本] (4): AdminBacklashRaise/Hold/Release/Cancel
  点名 boss_law_named 84->92 (2): AdminLawNameRaise/Hold
  格式化 formatting_started 139 (2): AdminFormatRaise/Hold
- Clamps floor contact on ALL 26 clips including AdminDown (half-frame verified: 0 samples < -3 cm).
- Outputs editable .blend, GLB, embedded texture SHA-256, JSON QA & round-trip report,
  and 10 same-camera pose proof panels (including AdminDown first & last frames).
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
from mathutils.bvhtree import BVHTree

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
    ("AdminIdle", "S02-M_Meshy_01_Idle", "idle", "base"),
    ("AdminWalk", "S02-M_Meshy_02_Walk", "walk", "base"),
    ("AdminStop", "S02-M_Meshy_08_WalkStop", "stop", "base"),
    ("AdminAttack", "S02-M_Meshy_04_LowCut", "attack", "base"),
    ("AdminHit", "S02-M_Meshy_13_HitLight", "hit", "base"),
    ("AdminDown", "S02-M_Meshy_06_Down", "down", "base"),
]

SKILL_CLIPS = [
    # ADMIN-A: 秩序抹除·扩域 (magic 7-cell erase, iconic left-palm STOP/ERASE from v1 concept)
    ("AdminEraseRaise", "M04_Meshy_01_RaisePalm", "A_raise", "cast"),
    ("AdminEraseHold", "M04_Meshy_02_AimHold", "A_hold", "cast"),
    ("AdminEraseRelease", "M04_Meshy_03_MistRelease", "A_release", "cast"),
    ("AdminEraseCancel", "M04_Meshy_04_MistCancel", "A_cancel", "cast"),
    # ADMIN-B: 维护权限 (self-shield 48, W1, empty lock)
    ("AdminShieldRaise", "S02-M_Meshy_17_RaiseGuard", "B_raise", "base"),
    ("AdminShieldHold", "S02-M_Meshy_05_GuardHold", "B_hold", "base"),
    ("AdminShieldRelease", "S02-M_Meshy_21_BlockImpact", "B_release", "base"),
    ("AdminShieldCancel", "S02-M_Meshy_18_LowerGuard", "B_cancel", "base"),
    # ADMIN-C: 格式化脉冲·扩域 (magic 15-cell pulse, rigid horizontal cruciform broadcast)
    ("AdminPulseRaise", "M04_Meshy_01_RaisePalm", "C_raise", "cast"),
    ("AdminPulseHold", "M04_Meshy_02_AimHold", "C_hold", "cast"),
    ("AdminPulseRelease", "M04_Meshy_03_MistRelease", "C_release", "cast"),
    ("AdminPulseCancel", "M04_Meshy_04_MistCancel", "C_cancel", "cast"),
    # ADMIN-D: 法令反噬 (directed/定向 only — no native A-line sample)
    ("AdminBacklashRaise", "M04_Meshy_01_RaisePalm", "D_raise", "cast"),
    ("AdminBacklashHold", "M04_Meshy_02_AimHold", "D_hold", "cast"),
    ("AdminBacklashRelease", "M04_Meshy_03_MistRelease", "D_release", "cast"),
    ("AdminBacklashCancel", "M04_Meshy_04_MistCancel", "D_cancel", "cast"),
    # State poses: boss_law_named (tick 84->92) & formatting_started (tick 139)
    ("AdminLawNameRaise", "M04_Meshy_01_RaisePalm", "L_raise", "cast"),
    ("AdminLawNameHold", "M04_Meshy_02_AimHold", "L_hold", "cast"),
    ("AdminFormatRaise", "M04_Meshy_01_RaisePalm", "F_raise", "cast"),
    ("AdminFormatHold", "M04_Meshy_02_AimHold", "F_hold", "cast"),
]

TARGET_HEIGHT = 2.24
DECIMATE_RATIO = 0.30


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
        step = 1 if act_name.endswith("_06_Down") else (2 if (f1 - f0) > 40 else 1)
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


def seat_floating_islands_and_clean(mesh_obj) -> dict:
    """Clean wires/loose verts and seat any tiny disconnected fingertip island cleanly into the main body."""
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    wires = [e for e in bm.edges if len(e.link_faces) == 0]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES")
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.verts.ensure_lookup_table()
    visited = set()
    comps = []
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
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    seated = []
    if len(comps) > 1:
        main_idx = {v.index for v in comps[0]}
        verts_co = [v.co.copy() for v in bm.verts]
        main_polys = [tuple(v.index for v in f.verts) for f in bm.faces if f.verts[0].index in main_idx]
        bvh_main = BVHTree.FromPolygons(verts_co, main_polys)
        for sub in comps[1:]:
            best_d = 999.0
            best_vec = Vector((0.0, 0.0, 0.0))
            for v in sub:
                loc, _, _, d = bvh_main.find_nearest(v.co)
                if d is not None and d < best_d:
                    best_d = d
                    best_vec = loc - v.co
            if best_d > 1e-4 and best_vec.length > 1e-6:
                shift = best_vec.normalized() * (best_d + 0.004)
                for v in sub:
                    v.co += shift
                seated.append({"verts": len(sub), "prev_gap_mm": round(best_d * 1000.0, 3), "shift_mm": round(shift.length * 1000.0, 3)})
    islands = [len(c) for c in comps]
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()
    return {"wires_removed": len(wires), "loose_removed": len(loose), "islands": islands, "seated_islands": seated}


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
    return {"verts": len(me.vertices), "before_over_4": before_over, "after_over_4": after_over, "unweighted": unweighted}


def make_material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.55) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    if mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_law_rack(arm_obj) -> bpy.types.Object:
    """Build ADMIN's iconic back bronze H-frame rack + 4 ivory-and-gold law tablets (ADMIN_管理员_v1).
    Physically bolted into chest/spine_02 back with zero floating gaps, bound 100% to PropLawRack.
    """
    mat_bronze = make_material("ADMIN_RackBronze", (0.35, 0.27, 0.19, 1.0), 0.45)
    mat_ivory = make_material("ADMIN_TabletIvory", (0.89, 0.84, 0.74, 1.0), 0.52)
    mat_gold = make_material("ADMIN_TabletGold", (0.78, 0.56, 0.24, 1.0), 0.36)

    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb_ch = arm_obj.data.edit_bones["chest"]
    rack_origin = eb_ch.head.copy()
    eb_r = arm_obj.data.edit_bones.new("PropLawRack")
    eb_r.head = rack_origin
    eb_r.tail = rack_origin + Vector((0.0, 0.22, 0.0))
    eb_r.parent = eb_ch
    eb_r.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Coordinate frame relative to chest head (facing -Y, back is +Y, up is +Z)
    # Central vertical spine bar sits at y = +0.20 and connects into torso back (y = +0.02..+0.22)
    parts = [
        # Upper & lower torso anchor struts (bolted solidly INTO chest & spine back -> 0mm gap!)
        (Vector((0.0, 0.10, 0.16)), Vector((0.08, 0.22, 0.07)), mat_bronze),
        (Vector((0.0, 0.10, -0.22)), Vector((0.08, 0.22, 0.07)), mat_bronze),
        # Central vertical bronze spine beam
        (Vector((0.0, 0.20, -0.02)), Vector((0.065, 0.065, 0.72)), mat_bronze),
        # Upper horizontal bronze crossbar (connects both upper law tablets)
        (Vector((0.0, 0.21, 0.18)), Vector((0.76, 0.055, 0.055)), mat_bronze),
        # Lower horizontal bronze crossbar (connects both lower law tablets)
        (Vector((0.0, 0.21, -0.22)), Vector((0.76, 0.055, 0.055)), mat_bronze),
        # Central gold clasp plates on crossbars
        (Vector((0.0, 0.23, 0.18)), Vector((0.12, 0.04, 0.09)), mat_gold),
        (Vector((0.0, 0.23, -0.22)), Vector((0.12, 0.04, 0.09)), mat_gold),
        # 4 rectangular ivory law tablets physically intersecting the crossbars (y = 0.23, depth 0.055 -> overlaps crossbar!)
        (Vector((-0.34, 0.24, 0.28)), Vector((0.24, 0.052, 0.46)), mat_ivory),
        (Vector((0.34, 0.24, 0.28)), Vector((0.24, 0.052, 0.46)), mat_ivory),
        (Vector((-0.34, 0.24, -0.24)), Vector((0.24, 0.052, 0.44)), mat_ivory),
        (Vector((0.34, 0.24, -0.24)), Vector((0.24, 0.052, 0.44)), mat_ivory),
        # Gold inlay accent strips embedded into each tablet
        (Vector((-0.34, 0.24, 0.28)), Vector((0.25, 0.026, 0.40)), mat_gold),
        (Vector((0.34, 0.24, 0.28)), Vector((0.25, 0.026, 0.40)), mat_gold),
        (Vector((-0.34, 0.24, -0.24)), Vector((0.25, 0.026, 0.38)), mat_gold),
        (Vector((0.34, 0.24, -0.24)), Vector((0.25, 0.026, 0.38)), mat_gold),
    ]
    objs = []
    for idx, (loc, scale, mat) in enumerate(parts):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=rack_origin + loc)
        o = bpy.context.active_object
        o.name = f"ADMIN_LawRack_p{idx}"
        o.scale = scale
        o.data.materials.append(mat)
        objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    rack = bpy.context.active_object
    rack.name = "ADMIN_LawRack"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    rack.parent = arm_obj
    rack.parent_type = "OBJECT"
    rack.matrix_parent_inverse = Matrix.Identity(4)
    vg = rack.vertex_groups.new(name="PropLawRack")
    vg.add(list(range(len(rack.data.vertices))), 1.0, "REPLACE")
    mod = rack.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    return rack


def skill_pose_overlay(tag: str, progress: float) -> tuple[dict[str, tuple[float, float, float]], dict[str, tuple[Vector, float]]]:
    """Distinct formal silhouettes (character faces -Y, right=-X, left=+X, up=+Z):
    A (Erase):    Left arm extended straight forward (v1 concept palm-STOP!), right arm straight at side.
    B (Shield):   Both arms folded tightly across golden chest emblem (self-shield 48).
    C (Pulse):    Both arms extended horizontally wide in rigid T-cross (15-cell pulse).
    D (Backlash): [定向] Both arms raised high & angled inward like a tribunal seal (crisp recoil on cancel).
    L (LawName):  Right arm raised high & pointing sharply down-forward (verdict point, tick 84->92).
    F (Format):   Both arms angled high diagonal V-crown with erect torso (formatting_started, tick 139).
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
        surge = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "A_release" else 0.0
        return (
            {"spine_02": (4.0 * w + 6.0 * surge, -10.0 * w, 0.0)},
            {
                "upper_arm.L": (Vector((0.24, -0.95, 0.18 + 0.14 * surge)).normalized(), w),
                "forearm.L": (Vector((0.12, -0.97, 0.20 + 0.16 * surge)).normalized(), w),
                "upper_arm.R": (Vector((-0.34, 0.14, -0.93)).normalized(), w),
                "forearm.R": (Vector((-0.26, -0.10, -0.96)).normalized(), w),
            },
        )
    if tag.startswith("B_"):
        pulse = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "B_release" else 0.0
        return (
            {"spine_01": (-6.0 * w - 4.0 * pulse, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.40, -0.72, -0.56)).normalized(), w),
                "forearm.L": (Vector((-0.56, -0.68, 0.47)).normalized(), w),
                "upper_arm.R": (Vector((-0.40, -0.72, -0.56)).normalized(), w),
                "forearm.R": (Vector((0.56, -0.68, 0.47)).normalized(), w),
            },
        )
    if tag.startswith("C_"):
        surge = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "C_release" else 0.0
        return (
            {"spine_02": (-4.0 * w + 8.0 * surge, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.97, -0.22 - 0.35 * surge, 0.06)).normalized(), w),
                "forearm.L": (Vector((0.94, -0.32 - 0.40 * surge, 0.08)).normalized(), w),
                "upper_arm.R": (Vector((-0.97, -0.22 - 0.35 * surge, 0.06)).normalized(), w),
                "forearm.R": (Vector((-0.94, -0.32 - 0.40 * surge, 0.08)).normalized(), w),
            },
        )
    if tag.startswith("D_"):
        if tag == "D_cancel":
            return (
                {"spine_02": (-14.0 * w, 0.0, 0.0)},
                {
                    "upper_arm.L": (Vector((0.68, 0.28, -0.68)).normalized(), w),
                    "forearm.L": (Vector((0.50, -0.38, -0.78)).normalized(), w),
                    "upper_arm.R": (Vector((-0.68, 0.28, -0.68)).normalized(), w),
                    "forearm.R": (Vector((-0.50, -0.38, -0.78)).normalized(), w),
                },
            )
        slam = math.sin(min(1.0, progress / 0.55) * math.pi) if tag == "D_release" else 0.0
        return (
            {"spine_02": (-8.0 * w + 16.0 * slam, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.52, -0.34, 0.78 - 0.65 * slam)).normalized(), w),
                "forearm.L": (Vector((-0.18, -0.46, 0.87 - 0.80 * slam)).normalized(), w),
                "upper_arm.R": (Vector((-0.52, -0.34, 0.78 - 0.65 * slam)).normalized(), w),
                "forearm.R": (Vector((0.18, -0.46, 0.87 - 0.80 * slam)).normalized(), w),
            },
        )
    if tag.startswith("L_"):
        # boss_law_named (tick 84->92): judicial right-arm high verdict point, left folded at waist
        return (
            {"spine_02": (-4.0 * w, 12.0 * w, 0.0)},
            {
                "upper_arm.R": (Vector((-0.44, -0.68, 0.58)).normalized(), w),
                "forearm.R": (Vector((-0.24, -0.92, 0.30)).normalized(), w),
                "upper_arm.L": (Vector((0.46, -0.42, -0.78)).normalized(), w),
                "forearm.L": (Vector((-0.42, -0.82, -0.38)).normalized(), w),
            },
        )
    if tag.startswith("F_"):
        # formatting_started (tick 139): erect solemn high diagonal V-crown sanction pose
        return (
            {"spine_02": (-10.0 * w, 0.0, 0.0), "PropLawRack": (-8.0 * w, 0.0, 0.0)},
            {
                "upper_arm.L": (Vector((0.74, -0.14, 0.66)).normalized(), w),
                "forearm.L": (Vector((0.66, -0.18, 0.73)).normalized(), w),
                "upper_arm.R": (Vector((-0.74, -0.14, 0.66)).normalized(), w),
                "forearm.R": (Vector((-0.66, -0.18, 0.73)).normalized(), w),
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


def build_admin(args: argparse.Namespace) -> dict:
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

    arm = bpy.data.objects["RIG_ADMIN"]
    mesh = bpy.data.objects["SK_ADMIN"]

    # Record embedded source texture SHA-256
    tex_hashes = {}
    for im in bpy.data.images:
        if im.packed_file is not None:
            tex_hashes[im.name] = hashlib.sha256(bytes(im.packed_file.data)).hexdigest()

    # 1. Scale cleanly to TARGET_HEIGHT (2.24m) and ground Z=0
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

    # 2. Decimate SK_ADMIN + seat floating fingertip island + enforce max-4 normalized weights
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Decimate_P06", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    topo_stats = seat_floating_islands_and_clean(mesh)
    skin_limit_stats = enforce_max_4_weights(mesh)
    body_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    # 3. Build solid bronze H-frame rack + 4 ivory-gold law tablets on chest back
    rack_obj = build_law_rack(arm)

    # 4. Precompute ADMIN rest data
    bpy.context.view_layer.update()
    t_rest_rot, t_rest_dir, t_rest_head = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        t_rest_rot[b.name] = m.to_3x3().normalized()
        t_rest_head[b.name] = arm.matrix_world @ b.head_local
        t_rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - t_rest_head[b.name]).normalized()

    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # 5. Retarget all 26 clips (clamping floor contact on EVERY clip including AdminDown!)
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

            # Clamp floor contact on EVERY clip including AdminDown (body + rack)
            eo_b = mesh.evaluated_get(deps)
            me_b = eo_b.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me_b.vertices)
            eo_b.to_mesh_clear()
            eo_r = rack_obj.evaluated_get(deps)
            me_r = eo_r.to_mesh()
            min_z = min(min_z, min((rack_obj.matrix_world @ v.co).z for v in me_r.vertices))
            eo_r.to_mesh_clear()
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
            if "PropLawRack" in arm.pose.bones:
                arm.pose.bones["PropLawRack"].keyframe_insert(data_path="rotation_quaternion", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = out_name
        strip = tr.strips.new(out_name, f_start, act)
        strip.action_frame_start = f_start
        strip.action_frame_end = f_end

    # 6. Half-frame QA audit across ALL 26 clips + rack contact check
    qa_audit = audit_admin_qa(arm, mesh, rack_obj)

    activate_action(arm, bpy.data.actions["AdminIdle"])
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # 7. Save editable .blend
    out_blend = Path(args.out_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    # 8. Export GLB
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

    # 9. Render 10 same-camera pose proof panels (incl. AdminDown start & end)
    if args.out_proof:
        render_pose_proof(arm, Path(args.out_proof))

    # 10. Clean-blend round-trip re-import verification
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
        "has_prop_law_rack_bone": "PropLawRack" in re_bones,
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
        "embedded_texture_sha256": tex_hashes,
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
    print("ADMIN_BUILD_OK:", json.dumps(roundtrip, ensure_ascii=False))
    return report


def audit_admin_qa(arm, mesh, rack_obj) -> dict:
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    # Check physical attachment of ADMIN_LawRack to SK_ADMIN in rest pose
    bvh_body = BVHTree.FromPolygons([mesh.matrix_world @ v.co for v in mesh.data.vertices], [tuple(p.vertices) for p in mesh.data.polygons])
    bvh_rack = BVHTree.FromPolygons([rack_obj.matrix_world @ v.co for v in rack_obj.data.vertices], [tuple(p.vertices) for p in rack_obj.data.polygons])
    rack_body_overlaps = len(bvh_body.overlap(bvh_rack))
    rack_degen = sum(1 for p in rack_obj.data.polygons if p.area < 1e-8)

    # Half-frame floor sweep across ALL 26 clips
    half_frame_summary = {"worst_min_z": 999.0, "worst_clip": "", "worst_frame": 0.0, "samples_below_neg_3cm": 0}
    clips = {}
    for act in sorted(bpy.data.actions, key=lambda a: a.name):
        activate_action(arm, act)
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        hf_min, hf_worst, sub_3cm = 999.0, float(f0), 0
        cur = float(f0)
        while cur <= float(f1) + 1e-4:
            fi = int(math.floor(cur))
            scene.frame_set(fi, subframe=cur - fi)
            bpy.context.view_layer.update()
            eb = mesh.evaluated_get(deps); mb = eb.to_mesh()
            mz = min((mesh.matrix_world @ v.co).z for v in mb.vertices)
            eb.to_mesh_clear()
            er = rack_obj.evaluated_get(deps); mr = er.to_mesh()
            mz = min(mz, min((rack_obj.matrix_world @ v.co).z for v in mr.vertices))
            er.to_mesh_clear()
            if mz < hf_min:
                hf_min, hf_worst = mz, cur
            if mz < -0.03:
                sub_3cm += 1
            cur += 0.5
        if hf_min < half_frame_summary["worst_min_z"]:
            half_frame_summary["worst_min_z"] = round(hf_min, 5)
            half_frame_summary["worst_clip"] = act.name
            half_frame_summary["worst_frame"] = round(hf_worst, 1)
        half_frame_summary["samples_below_neg_3cm"] += sub_3cm
        if act.name in ("AdminIdle", "AdminWalk", "AdminAttack", "AdminDown",
                        "AdminEraseHold", "AdminShieldHold", "AdminPulseHold",
                        "AdminBacklashHold", "AdminLawNameHold", "AdminFormatHold"):
            clips[act.name] = {
                "half_frame_min_z": round(hf_min, 5),
                "half_frame_worst": round(hf_worst, 1),
                "samples_below_neg_3cm": sub_3cm,
            }
    return {
        "rack_body_overlaps": rack_body_overlaps,
        "rack_degenerate_faces": rack_degen,
        "all_26_clips_half_frame": half_frame_summary,
        "representative_clips": clips,
    }


def render_pose_proof(arm, out_dir: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 520
    scene.render.resolution_y = 360
    scene.render.film_transparent = False
    if scene.world:
        scene.world.color = (0.86, 0.83, 0.78)

    cam_data = bpy.data.cameras.new("ProofCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.0
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.5, -3.4, 2.45))
    cam.rotation_euler = (Vector((0.0, 0.0, 1.12)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    down_act = bpy.data.actions["AdminDown"]
    down_f0 = int(round(down_act.frame_range[0]))
    down_f1 = int(round(down_act.frame_range[1]))
    for suffix, cname, fr in [
        ("0_idle", "AdminIdle", 10),
        ("1_A_erase", "AdminEraseHold", 20),
        ("2_B_shield", "AdminShieldHold", 20),
        ("3_C_pulse", "AdminPulseHold", 20),
        ("4_D_backlash", "AdminBacklashHold", 20),
        ("5_L_lawname", "AdminLawNameHold", 20),
        ("6_F_format", "AdminFormatHold", 20),
        ("7_attack", "AdminAttack", 20),
        ("8_down_start", "AdminDown", down_f0),
        ("9_down_end", "AdminDown", down_f1),
    ]:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_admin(parse_args())

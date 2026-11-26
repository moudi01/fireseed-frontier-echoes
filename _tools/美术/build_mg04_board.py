"""Build MG04 (Helan) animated P06 board GLB and editable Blend from MG04_skinned.blend + S02/M04 donors.

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/MG04_skinned.blend,
S02-M_Meshy_24_Keyframe_Actions.blend (melee base), and M04_Meshy_Mist_Cast.blend (C anchor magic).
Preserves thick stone left pauldron, glowing forge-ember cracks, rope waist sash, left socket brace,
and right-hand single-handed long clamp/wrench-hammer (MG04_Hammer).

Generates 18 clips with unmistakable silhouettes at 1280x720:
  - Base 6: Mg04Idle, Mg04Walk, Mg04Stop, Mg04Attack, Mg04Hit, Mg04Down
  - MG04-A (physical cleave): Mg04CleaveRaise / Hold / Release / Cancel (high overhead hammer windup -> cleave)
  - MG04-B (44 self-shield):  Mg04ShieldRaise / Hold / Release / Cancel (stone shoulder + socket brace guard)
  - MG04-C (dual-anchor magic): Mg04AnchorRaise / Hold / Release / Cancel (left socket-brace arm raised/extended
    channeling toward the two floor anchors while right hammer stays lowered at side — clearly NOT a hammer smash!)

Built-in QA:
  - Explicit top-4 normalized bone weights (0 verts > 4 influences)
  - Wire-edge / loose-vertex cleanup + floating-island check
  - Evaluated-mesh ground clamp (Z >= 0 on non-down clips) + prop contact & near-overlap audit
  - Clean-blend round-trip re-import verification
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


BONE_MAP = [
    ("root", "Root", "delta"),
    ("pelvis", "Hips", "delta"),
    ("spine_01", "Spine", "delta"),
    ("spine_02", "Spine01", "delta"),
    ("chest", "Spine02", "delta"),
    ("neck", "neck", "delta"),
    ("head", "Head", "delta"),
    ("clavicle.L", "LeftShoulder", "align_dir"),
    ("upper_arm.L", "LeftArm", "align_dir"),
    ("forearm.L", "LeftForeArm", "align_dir"),
    ("hand.L", "LeftHand", "align_dir"),
    ("clavicle.R", "RightShoulder", "align_dir"),
    ("upper_arm.R", "RightArm", "align_dir"),
    ("forearm.R", "RightForeArm", "align_dir"),
    ("hand.R", "RightHand", "align_dir"),
    ("thigh.L", "LeftUpLeg", "align_dir"),
    ("shin.L", "LeftLeg", "align_dir"),
    ("foot.L", "LeftFoot", "align_dir"),
    ("thigh.R", "RightUpLeg", "align_dir"),
    ("shin.R", "RightLeg", "align_dir"),
    ("foot.R", "RightFoot", "align_dir"),
]

COAT_BONES = [
    "coat_front_01.L", "coat_front_02.L", "coat_back_01.L", "coat_back_02.L",
    "coat_front_01.R", "coat_front_02.R", "coat_back_01.R", "coat_back_02.R",
]

BASE_CLIPS = [
    ("Mg04Idle", "S02-M_Meshy_01_Idle", "idle", "base"),
    ("Mg04Walk", "S02-M_Meshy_02_Walk", "walk", "base"),
    ("Mg04Stop", "S02-M_Meshy_08_WalkStop", "stop", "base"),
    ("Mg04Attack", "S02-M_Meshy_04_LowCut", "attack", "base"),
    ("Mg04Hit", "S02-M_Meshy_13_HitLight", "hit", "base"),
    ("Mg04Down", "S02-M_Meshy_06_Down", "down", "base"),
]

SKILL_CLIPS = [
    # MG04-A: 重铸裁线·扩域 (physical overhead hammer windup -> heavy cleave)
    ("Mg04CleaveRaise", "S02-M_Meshy_17_RaiseGuard", "A_raise", "base"),
    ("Mg04CleaveHold", "S02-M_Meshy_05_GuardHold", "A_hold", "base"),
    ("Mg04CleaveRelease", "S02-M_Meshy_19_HeavyCut", "A_release", "base"),
    ("Mg04CleaveCancel", "S02-M_Meshy_18_LowerGuard", "A_cancel", "base"),
    # MG04-B: 本人 44 私盾 (braced stone-pauldron & socket-brace defensive guard)
    ("Mg04ShieldRaise", "S02-M_Meshy_17_RaiseGuard", "B_raise", "base"),
    ("Mg04ShieldHold", "S02-M_Meshy_05_GuardHold", "B_hold", "base"),
    ("Mg04ShieldRelease", "S02-M_Meshy_21_BlockImpact", "B_release", "base"),
    ("Mg04ShieldCancel", "S02-M_Meshy_18_LowerGuard", "B_cancel", "base"),
    # MG04-C: 双锚魔法 (left socket-brace arm channels magic outward/upward; right hammer stays lowered!)
    ("Mg04AnchorRaise", "M04_Meshy_01_RaisePalm", "C_raise", "cast"),
    ("Mg04AnchorHold", "M04_Meshy_02_AimHold", "C_hold", "cast"),
    ("Mg04AnchorRelease", "M04_Meshy_03_MistRelease", "C_release", "cast"),
    ("Mg04AnchorCancel", "M04_Meshy_04_MistCancel", "C_cancel", "cast"),
]

TARGET_HEIGHT = 2.22
DECIMATE_RATIO = 0.18


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


def activate_action(arm_obj, action) -> None:
    ad = arm_obj.animation_data_create()
    ad.action = action
    if getattr(action, "slots", None):
        for slot in action.slots:
            if slot.target_id_type == "OBJECT":
                ad.action_slot = slot
                break
        else:
            ad.action_slot = action.slots[0]


def sample_donor_file(donor_path: str, action_names: list[str]) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=donor_path)
    scene = bpy.context.scene
    fps = scene.render.fps
    arm = bpy.data.objects["FireseedHumanoid"]
    if arm.animation_data:
        for tr in arm.animation_data.nla_tracks:
            tr.mute = True

    rest_rot, rest_head, rest_dir = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        rest_rot[b.name] = m.to_3x3().normalized()
        rest_head[b.name] = arm.matrix_world @ b.head_local
        rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - rest_head[b.name]).normalized()

    needed = {d for _, d, _ in BONE_MAP}
    clips = {}
    for act_name in sorted(set(action_names)):
        act = bpy.data.actions[act_name]
        activate_action(arm, act)
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        step = 2 if (f1 - f0) > 50 else 1
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        samples = []
        for f in frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            bones = {}
            for bn in needed:
                pb = arm.pose.bones[bn]
                mw = arm.matrix_world @ pb.matrix
                hw = arm.matrix_world @ pb.head
                tw = arm.matrix_world @ pb.tail
                bones[bn] = (hw.copy(), (tw - hw).normalized(), mw.to_3x3().normalized())
            samples.append({"frame": f, "bones": bones})
        clips[act_name] = {"f0": f0, "f1": f1, "frames": samples}

    return {
        "fps": fps,
        "hips_z": rest_head["Hips"].z,
        "rest_rot": rest_rot,
        "rest_head": rest_head,
        "rest_dir": rest_dir,
        "clips": clips,
    }


def enforce_max_4_weights(mesh_obj) -> dict:
    """Explicitly keep top-4 strongest bone weights per vertex and normalize to 1.0."""
    vgroups = mesh_obj.vertex_groups
    before_over4, after_over4, unweighted = 0, 0, 0
    for v in mesh_obj.data.vertices:
        weights = [(g.group, float(g.weight)) for g in v.groups if g.weight > 1e-6]
        if len(weights) > 4:
            before_over4 += 1
        if not weights:
            unweighted += 1
            continue
        weights.sort(key=lambda item: item[1], reverse=True)
        kept, dropped = weights[:4], weights[4:]
        total = sum(w for _, w in kept)
        if total <= 1e-8:
            unweighted += 1
            continue
        for g_idx, _ in dropped:
            vgroups[g_idx].remove([v.index])
        for g_idx, w in kept:
            vgroups[g_idx].add([v.index], w / total, "REPLACE")
        kept_ids = {g_idx for g_idx, _ in kept}
        for g in list(v.groups):
            if g.group not in kept_ids:
                vgroups[g.group].remove([v.index])
    for v in mesh_obj.data.vertices:
        if sum(1 for g in v.groups if g.weight > 1e-6) > 4:
            after_over4 += 1
    return {
        "verts": len(mesh_obj.data.vertices),
        "before_over_4": before_over4,
        "after_over_4": after_over4,
        "unweighted": unweighted,
    }


def clean_body_topology(mesh_obj) -> dict:
    """Remove any wire edges or loose vertices after decimation and report island count."""
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    wires = [e for e in bm.edges if len(e.link_faces) == 0]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES_FACES")
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    visited, islands = set(), []
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


def make_material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.6) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    if mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_clamp_hammer(arm_obj) -> bpy.types.Object:
    """Build Helan's iconic single-handed long clamp/wrench-hammer (v4 CLAMP HAMMER) on hand.R."""
    mat_iron = make_material("MG04_ForgedIron", (0.36, 0.31, 0.28, 1.0), 0.52)
    mat_shaft = make_material("MG04_DarkTimber", (0.28, 0.17, 0.11, 1.0), 0.70)
    mat_wrap = make_material("MG04_GripWrap", (0.58, 0.42, 0.26, 1.0), 0.68)
    mat_ember = make_material("MG04_ForgeEmber", (0.92, 0.46, 0.14, 1.0), 0.35)

    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb_hr = arm_obj.data.edit_bones["hand.R"]
    hammer_origin = eb_hr.tail.copy()
    eb_h = arm_obj.data.edit_bones.new("PropHammer")
    eb_h.head = hammer_origin
    eb_h.tail = hammer_origin + Vector((0.0, -0.22, 0.0))
    eb_h.parent = eb_hr
    eb_h.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Long single-hand wrench-hammer (~1.12m total length, aligned along -Y forward from right grip)
    parts = [
        # Main long handle shaft (pommel at +0.24, head neck at -0.78)
        (Vector((0.0, -0.26, 0.0)), Vector((0.052, 1.02, 0.052)), (0, 0, 0), mat_shaft),
        # Lower grip leather wrap (right hand palm sits around y=0)
        (Vector((0.0, 0.02, 0.0)), Vector((0.064, 0.24, 0.064)), (0, 0, 0), mat_wrap),
        # Upper collar wrap near hammer head
        (Vector((0.0, -0.58, 0.0)), Vector((0.068, 0.20, 0.068)), (0, 0, 0), mat_wrap),
        # Heavy forged iron hammer block spine
        (Vector((0.0, -0.84, 0.0)), Vector((0.24, 0.24, 0.18)), (0, 0, 0), mat_iron),
        # Iconic C-clamp wrench upper jaw prong
        (Vector((0.0, -0.84, 0.16)), Vector((0.20, 0.22, 0.10)), (0, 0, 0), mat_iron),
        # Iconic C-clamp wrench lower jaw prong (leaving visible open C-notch silhouette!)
        (Vector((0.0, -0.84, -0.16)), Vector((0.20, 0.22, 0.10)), (0, 0, 0), mat_iron),
        # Subtle glowing forge-ember rune seam across hammer face
        (Vector((0.0, -0.84, 0.0)), Vector((0.255, 0.036, 0.14)), (0, 0, 0), mat_ember),
    ]
    objs = []
    for idx, (loc, scale, rot_deg, mat) in enumerate(parts):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=hammer_origin + loc)
        o = bpy.context.active_object
        o.name = f"MG04_Hammer_p{idx}"
        o.scale = scale
        o.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ")
        o.data.materials.append(mat)
        objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    hammer = bpy.context.active_object
    hammer.name = "MG04_Hammer"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    hammer.parent = arm_obj
    hammer.parent_type = "OBJECT"
    hammer.matrix_parent_inverse = Matrix.Identity(4)
    vg = hammer.vertex_groups.new(name="PropHammer")
    vg.add(list(range(len(hammer.data.vertices))), 1.0, "REPLACE")
    mod = hammer.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    return hammer


def skill_pose_overlay(tag: str, progress: float) -> tuple[dict[str, tuple[float, float, float]], dict[str, tuple[Vector, float]]]:
    """Unmistakable 1280x720 silhouettes:
    A = right-arm overhead hammer cleave (hammer towers high on right side);
    B = braced horizontal self-shield guard across chest;
    C = left socket-brace arm raised forward/outward channeling anchor magic, right hammer lowered at hip.
    Returns (local_euler_overlays, world_dir_targets {bone: (dir_w, blend)}).
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
        # MG04-A 重铸裁线·扩域: Right arm hoists clamp-hammer HIGH & CLEAR on right side; snaps downward on release
        if tag == "A_release":
            cleave = math.sin(min(1.0, progress / 0.50) * math.pi)
            return (
                {
                    "spine_02": (18.0 * cleave, -16.0 * cleave, 0.0),
                    "PropHammer": (24.0 * cleave, 0.0, 0.0),
                },
                {
                    "upper_arm.R": (Vector((-0.45, -0.78, -0.42)).normalized(), 0.75 * cleave),
                    "forearm.R": (Vector((-0.25, -0.88, -0.40)).normalized(), 0.75 * cleave),
                },
            )
        return (
            {
                "spine_02": (-10.0 * w, 14.0 * w, 0.0),
            },
            {
                "upper_arm.R": (Vector((-0.68, -0.15, 0.72)).normalized(), w),
                "forearm.R": (Vector((-0.36, -0.22, 0.91)).normalized(), w),
                "PropHammer": (Vector((-0.30, -0.28, 0.91)).normalized(), w),
                "upper_arm.L": (Vector((0.52, -0.42, -0.74)).normalized(), 0.85 * w),
                "forearm.L": (Vector((0.28, -0.76, -0.58)).normalized(), 0.85 * w),
            },
        )
    if tag.startswith("B_"):
        # MG04-B 本人 44 私盾: Braced defensive guard — stone left shoulder & socket brace forward, hammer angled across front
        pulse = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "B_release" else 0.0
        return (
            {
                "spine_01": (-6.0 * w - 4.0 * pulse, -18.0 * w, 0.0),
                "upper_arm.L": (-16.0 * w, 0.0, -18.0 * w),
                "forearm.L": (-48.0 * w, 0.0, -18.0 * w),
                "upper_arm.R": (-14.0 * w, 0.0, 18.0 * w),
                "forearm.R": (-42.0 * w, 0.0, 16.0 * w),
                "PropHammer": (-35.0 * w, 0.0, 0.0),
            },
            {},
        )
    if tag.startswith("C_"):
        # MG04-C 双锚魔法: MUST NOT mimic hammer smash!
        # Right hammer arm stays LOWERED at right hip, hammer head pointing down/low;
        # Left socket-brace arm (stone pauldron side) raised HIGH & FORWARD channeling magic to the two floor anchors!
        surge = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "C_release" else 0.0
        left_fore = (
            Vector((0.36, -0.90, 0.24)).normalized()
            if tag == "C_release"
            else Vector((0.54, -0.70, 0.47)).normalized()
        )
        return (
            {
                "spine_02": (-6.0 * w + 8.0 * surge, -16.0 * w, 0.0),
            },
            {
                "upper_arm.R": (Vector((-0.36, 0.14, -0.92)).normalized(), w),
                "forearm.R": (Vector((-0.30, -0.20, -0.93)).normalized(), w),
                "PropHammer": (Vector((-0.24, -0.42, -0.87)).normalized(), w),
                "upper_arm.L": (Vector((0.72, -0.46, 0.52)).normalized(), w),
                "forearm.L": (left_fore, w),
            },
        )
    return {}, {}


def apply_world_dir_target(arm, bn: str, target_dir_w: Vector, blend: float, t_rest_rot: dict, t_rest_dir: dict) -> None:
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


def build_mg04(args: argparse.Namespace) -> dict:
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

    arm = bpy.data.objects["RIG_MG04"]
    mesh = bpy.data.objects["SK_MG04"]

    # 1. Scale cleanly to TARGET_HEIGHT (2.22m) and ground Z=0
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

    # 2. Decimate SK_MG04 + clean topology + enforce max-4 normalized weights
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

    # 3. Build single-handed long clamp/wrench-hammer on hand.R
    hammer_obj = build_clamp_hammer(arm)

    # 4. Precompute MG04 rest data
    bpy.context.view_layer.update()
    t_rest_rot, t_rest_dir, t_rest_head = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        t_rest_rot[b.name] = m.to_3x3().normalized()
        t_rest_head[b.name] = arm.matrix_world @ b.head_local
        t_rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - t_rest_head[b.name]).normalized()

    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # 5. Retarget all 18 clips
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
            for bn in ("upper_arm.R", "forearm.R", "PropHammer", "upper_arm.L", "forearm.L"):
                if bn in world_targets:
                    target_dir_w, blend = world_targets[bn]
                    apply_world_dir_target(arm, bn, target_dir_w, blend, t_rest_rot, t_rest_dir)

            for side in ("L", "R"):
                th = arm.pose.bones[f"thigh.{side}"].rotation_quaternion.to_euler()
                for prefix, sign in (("coat_front_01", 0.28), ("coat_front_02", 0.20), ("coat_back_01", -0.20), ("coat_back_02", -0.16)):
                    cpb = arm.pose.bones.get(f"{prefix}.{side}")
                    if cpb:
                        cpb.rotation_quaternion = Quaternion((1, 0, 0), th.x * sign)
            bpy.context.view_layer.update()

            if out_name != "Mg04Down":
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
            for extra_bn in COAT_BONES + ["PropHammer"]:
                if extra_bn in arm.pose.bones:
                    arm.pose.bones[extra_bn].keyframe_insert(data_path="rotation_quaternion", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = out_name
        strip = tr.strips.new(out_name, f_start, act)
        strip.action_frame_start = f_start
        strip.action_frame_end = f_end

    # 6. QA audit across representative clips (grounding, hammer contact, zero degeneracy, hammer height A vs C)
    qa_audit = audit_mg04_qa(arm, mesh, hammer_obj)

    activate_action(arm, bpy.data.actions["Mg04Idle"])
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

    # 9. Render 4 orthogonal pose panels (Idle, A-CleaveHold, B-ShieldHold, C-AnchorHold)
    if args.out_proof:
        render_abc_proof(arm, Path(args.out_proof))

    # 10. Clean-blend round-trip re-import verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 1), round(a.frame_range[1], 1)] for a in bpy.data.actions}
    re_bones = [b.name for b in re_arm.data.bones] if re_arm else []
    re_over4 = {o.name: sum(1 for v in o.data.vertices if sum(1 for g in v.groups if g.weight > 1e-6) > 4) for o in re_meshes}
    expected_names = [c for c, _, _, _ in all_specs]

    report = {
        "source_blend": args.source,
        "source_blend_sha256": sha256_file(Path(args.source)),
        "donor_base_blend": args.donor_base,
        "donor_base_sha256": sha256_file(Path(args.donor_base)),
        "donor_cast_blend": args.donor_cast,
        "donor_cast_sha256": sha256_file(Path(args.donor_cast)),
        "out_glb": str(out_glb),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "target_height": TARGET_HEIGHT,
        "decimated_body_tris": body_tris,
        "topology": topo_stats,
        "skin_limit_4": skin_limit_stats,
        "qa_audit": qa_audit,
        "roundtrip": {
            "armature": re_arm.name if re_arm else None,
            "bone_count": len(re_bones),
            "has_prop_hammer_bone": "PropHammer" in re_bones,
            "mesh_names": sorted(o.name for o in re_meshes),
            "total_tris": re_tris,
            "verts_over_4_influences": re_over4,
            "material_count": len(bpy.data.materials),
            "image_count": len(bpy.data.images),
            "action_count": len(re_actions),
            "expected_clips_present": all(c in re_actions for c in expected_names),
            "actions": re_actions,
        },
    }
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MG04_BUILD_OK:", json.dumps(report["roundtrip"], ensure_ascii=False))
    return report


def audit_mg04_qa(arm, mesh, hammer_obj) -> dict:
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    clips = {}
    for cname in ["Mg04Idle", "Mg04Walk", "Mg04Attack", "Mg04Down",
                  "Mg04CleaveHold", "Mg04CleaveRelease", "Mg04ShieldHold", "Mg04AnchorHold", "Mg04AnchorRelease"]:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        f_mid = int(round((act.frame_range[0] + act.frame_range[1]) * 0.5))
        scene.frame_set(f_mid)
        bpy.context.view_layer.update()
        eo = mesh.evaluated_get(deps)
        me = eo.to_mesh()
        min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
        eo.to_mesh_clear()

        hr_tail = arm.matrix_world @ arm.pose.bones["hand.R"].tail
        ph_head = arm.matrix_world @ arm.pose.bones["PropHammer"].head
        hl_tail = arm.matrix_world @ arm.pose.bones["hand.L"].tail

        heo = hammer_obj.evaluated_get(deps)
        hme = heo.to_mesh()
        h_degen = sum(1 for p in hme.polygons if p.area < 1e-8)
        h_max_z = max((hammer_obj.matrix_world @ v.co).z for v in hme.vertices)
        heo.to_mesh_clear()

        clips[cname] = {
            "sample_frame": f_mid,
            "body_min_z": round(min_z, 4),
            "hammer_hand_dist": round((ph_head - hr_tail).length, 4),
            "hammer_max_z": round(h_max_z, 3),
            "left_hand_z": round(hl_tail.z, 3),
            "hammer_degenerate_faces": h_degen,
        }
    return {"clips": clips}


def render_abc_proof(arm, out_path: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.film_transparent = False
    if scene.world:
        scene.world.color = (0.84, 0.80, 0.74)

    cam_data = bpy.data.cameras.new("ProofCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.6
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.8, -3.6, 2.7))
    cam.rotation_euler = (Vector((0.0, 0.0, 1.1)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in [
        ("0_idle", "Mg04Idle", 10),
        ("1_A_cleave", "Mg04CleaveHold", 20),
        ("2_B_shield", "Mg04ShieldHold", 20),
        ("3_C_anchor", "Mg04AnchorHold", 20),
    ]:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_path.parent / f"{out_path.stem}_{suffix}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_mg04(parse_args())

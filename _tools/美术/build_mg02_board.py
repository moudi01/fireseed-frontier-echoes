"""Build MG02 (Sev) animated P06 board GLB and editable Blend from MG02_skinned.blend + S03-F bow donor.

Run with Blender 5.3 headless:
  blender --background --python _tools/美术/build_mg02_board.py -- \
    --source "D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/MG02_skinned.blend" \
    --donor  "D:/Personal_dev-assets/设计整理/角色模型_v1/弓类完整动作_v10/S03-F_Meshy/S03-F_Meshy_bow_complete.blend" \
    --out-glb "原型/P06_首章/assets/enemies/MG02_Board.glb" \
    --out-blend "原型/P06_首章/evidence/issue12-mg02/MG02_Board.blend" \
    --out-report "原型/P06_首章/evidence/issue12-mg02/mg02_build_report.json" \
    --out-proof "原型/P06_首章/evidence/issue12-mg02/mg02_poses_proof.png"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


# Ordered parent-before-child mapping: (target MG02 bone, donor FireseedHumanoid bone, mode)
# mode: "delta" = world delta from rest; "align_dir" = match posed bone axis directly (handles T-pose vs A-pose)
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

WEAPON_BONES = ["Weapon", "StringTop", "StringBottom", "HeldArrow", "FlightArrow"]
# Distinct rest-pose offsets above Z=0 so unmodified rest meshes have zero z-fighting and ground_z=0.
# Animated keyframes subtract each bone's rest head so runtime world transforms are 100% preserved.
WEAPON_REST_OFFSETS = {
    "Weapon": Vector((0.0, 0.0, 1.18)),
    "StringTop": Vector((0.0, 0.08, 1.36)),
    "StringBottom": Vector((0.0, 0.08, 0.96)),
    "HeldArrow": Vector((0.12, 0.0, 1.18)),
    "FlightArrow": Vector((-0.12, 0.0, 1.18)),
}
WEAPON_MESH_BONE = {
    "Combat_bow": "Weapon",
    "Combat_String_0": "StringTop",
    "Combat_String_1": "StringBottom",
    "Combat_arrow": "HeldArrow",
    "Combat_flying_arrow": "FlightArrow",
}
WEAPON_MESHES = [
    "Combat_bow",
    "Combat_arrow",
    "Combat_flying_arrow",
    "Combat_String_0",
    "Combat_String_1",
]

# Export clip name -> donor action name
CLIP_MAP = [
    ("BowGuard", "BowGuard-loop"),
    ("BowWalk", "BowWalk-loop"),
    ("BowStop", "BowStop"),
    ("BowAttack", "BowAttack"),
    ("BowHitFront", "BowHitFront"),
    ("BowDown", "BowDown"),
    ("BowLoad", "BowLoad"),
    ("BowAim", "BowAim-loop"),
    ("BowRelease", "BowRelease"),
    ("BowCancelLoaded", "BowCancelLoaded"),
]

TARGET_HEIGHT = 1.92
DECIMATE_RATIO = 0.18


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--donor", required=True)
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


def sample_donor(donor_path: str) -> dict:
    """Read donor rest poses and per-frame world matrices for every needed action."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=donor_path)
    scene = bpy.context.scene
    fps = scene.render.fps
    arm = bpy.data.objects["FireseedHumanoid"]
    if arm.animation_data:
        for tr in arm.animation_data.nla_tracks:
            tr.mute = True

    rest_rot = {}
    rest_head = {}
    rest_dir = {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        rest_rot[b.name] = m.to_3x3().normalized()
        rest_head[b.name] = arm.matrix_world @ b.head_local
        rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - rest_head[b.name]).normalized()

    hips_z = rest_head["Hips"].z
    hand_l_rest = rest_head["LeftHand"]

    clips = {}
    needed_bones = {d for _, d, _ in BONE_MAP} | set(WEAPON_BONES)
    for out_name, donor_action_name in CLIP_MAP:
        act = bpy.data.actions[donor_action_name]
        activate_action(arm, act)
        f0 = int(round(act.frame_range[0]))
        f1 = int(round(act.frame_range[1]))
        # Subsample step=2 for long loops (>90 frames) to keep GLB compact while smooth
        step = 2 if (f1 - f0) > 90 else 1
        frames = list(range(f0, f1 + 1, step))
        if frames[-1] != f1:
            frames.append(f1)
        samples = []
        for f in frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            row = {"frame": f, "bones": {}, "weapons": {}}
            for bn in needed_bones:
                pb = arm.pose.bones[bn]
                mw = arm.matrix_world @ pb.matrix
                if bn in WEAPON_BONES:
                    row["weapons"][bn] = (
                        mw.to_translation().copy(),
                        mw.to_3x3().normalized().to_quaternion(),
                        mw.to_scale().copy(),
                    )
                else:
                    head_w = arm.matrix_world @ pb.head
                    tail_w = arm.matrix_world @ pb.tail
                    row["bones"][bn] = (
                        head_w.copy(),
                        (tail_w - head_w).normalized(),
                        mw.to_3x3().normalized(),
                    )
            samples.append(row)
        clips[out_name] = {"f0": f0, "f1": f1, "frames": samples}

    return {
        "fps": fps,
        "hips_z": hips_z,
        "hand_l_rest": hand_l_rest,
        "rest_rot": rest_rot,
        "rest_head": rest_head,
        "rest_dir": rest_dir,
        "clips": clips,
    }


def style_weapon_materials() -> None:
    """Re-style donor bow/arrow meshes in Sev's dark-wood + bone-inlay palette (v3/v4)."""
    wood_mat = bpy.data.materials.new("MG02_BowWood")
    wood_mat.diffuse_color = (0.28, 0.13, 0.07, 1.0)
    bsdf = wood_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.28, 0.13, 0.07, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.62

    bone_mat = bpy.data.materials.new("MG02_BoneArrow")
    bone_mat.diffuse_color = (0.78, 0.67, 0.50, 1.0)
    bsdf2 = bone_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf2:
        bsdf2.inputs["Base Color"].default_value = (0.78, 0.67, 0.50, 1.0)
        bsdf2.inputs["Roughness"].default_value = 0.55

    string_mat = bpy.data.materials.new("MG02_BowString")
    string_mat.diffuse_color = (0.86, 0.79, 0.65, 1.0)
    bsdf3 = string_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf3:
        bsdf3.inputs["Base Color"].default_value = (0.86, 0.79, 0.65, 1.0)
        bsdf3.inputs["Roughness"].default_value = 0.45

    for name in WEAPON_MESHES:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "MESH":
            continue
        obj.data.materials.clear()
        if "bow" in name.lower():
            obj.data.materials.append(wood_mat)
        elif "string" in name.lower():
            obj.data.materials.append(string_mat)
        else:
            obj.data.materials.append(bone_mat)


def enforce_max_4_weights(mesh_obj) -> dict:
    """Explicitly keep top-4 strongest bone weights per vertex and normalize to 1.0."""
    vgroups = mesh_obj.vertex_groups
    before_over4 = 0
    after_over4 = 0
    unweighted = 0
    for v in mesh_obj.data.vertices:
        weights = [(g.group, float(g.weight)) for g in v.groups if g.weight > 1e-6]
        if len(weights) > 4:
            before_over4 += 1
        if not weights:
            unweighted += 1
            continue
        weights.sort(key=lambda item: item[1], reverse=True)
        kept = weights[:4]
        dropped = weights[4:]
        total = sum(w for _, w in kept)
        if total <= 1e-8:
            unweighted += 1
            continue
        for g_idx, _ in dropped:
            vgroups[g_idx].remove([v.index])
        for g_idx, w in kept:
            vgroups[g_idx].add([v.index], w / total, "REPLACE")
        # Remove any tiny residual entries <= 1e-6
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


def build_mg02(args: argparse.Namespace) -> dict:
    donor = sample_donor(args.donor)

    # Open MG02_skinned.blend
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    scene.render.fps = donor["fps"]

    # Remove old QA camera & QA action
    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    arm = bpy.data.objects["RIG_MG02"]
    mesh = bpy.data.objects["SK_MG02"]

    # 1. Scale MG02 cleanly to TARGET_HEIGHT and ground Z=0
    zs = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    cur_h = max(zs) - min(zs)
    scale_fac = TARGET_HEIGHT / cur_h
    arm.scale = (scale_fac, scale_fac, scale_fac)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Re-ground if min Z shifted
    zs2 = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    min_z = min(zs2)
    if abs(min_z) > 1e-4:
        arm.location.z -= min_z
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    # 2. Decimate SK_MG02 for real-time P06 performance while keeping silhouette & weights
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Decimate_P06", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Ensure vertex normals / smooth shading clean and cap skinning to top-4 normalized weights
    skin_limit_stats = enforce_max_4_weights(mesh)
    mesh_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    # 3. Append weapon meshes from donor and add weapon bones to RIG_MG02
    with bpy.data.libraries.load(args.donor, link=False) as (data_from, data_to):
        data_to.objects = [n for n in WEAPON_MESHES if n in data_from.objects]
    weapon_objs = []
    for obj in data_to.objects:
        if obj is not None:
            scene.collection.objects.link(obj)
            weapon_objs.append(obj)

    # Add 5 weapon bones under root in Edit Mode at distinct non-overlapping rest offsets above Z=0
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb_root = arm.data.edit_bones["root"]
    for wb in WEAPON_BONES:
        eb = arm.data.edit_bones.new(wb)
        off = WEAPON_REST_OFFSETS[wb]
        eb.head = off.copy()
        eb.tail = off + Vector((0.0, 0.1, 0.0))
        eb.parent = eb_root
        eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Rebind appended weapon meshes to RIG_MG02, translating rest vertices to match each bone's rest head
    weapon_scale = TARGET_HEIGHT / 1.72
    for wobj in weapon_objs:
        wobj.parent = arm
        wobj.parent_type = "OBJECT"
        wobj.matrix_parent_inverse = Matrix.Identity(4)
        off = WEAPON_REST_OFFSETS[WEAPON_MESH_BONE[wobj.name]]
        wobj.location = off.copy()
        wobj.rotation_euler = (0.0, 0.0, 0.0)
        wobj.scale = (weapon_scale, weapon_scale, weapon_scale)
        # Apply location & scale to mesh data so rest pose has zero overlap and bone skinning matches 1:1
        bpy.ops.object.select_all(action="DESELECT")
        wobj.select_set(True)
        bpy.context.view_layer.objects.active = wobj
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
        # Point existing armature modifier to RIG_MG02
        found_arm_mod = False
        for m in wobj.modifiers:
            if m.type == "ARMATURE":
                m.object = arm
                found_arm_mod = True
        if not found_arm_mod:
            m = wobj.modifiers.new("Armature", "ARMATURE")
            m.object = arm

    style_weapon_materials()

    # 4. Precompute MG02 rest data for retargeting
    bpy.context.view_layer.update()
    t_rest_rot = {}
    t_rest_dir = {}
    t_rest_head = {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        t_rest_rot[b.name] = m.to_3x3().normalized()
        t_rest_head[b.name] = arm.matrix_world @ b.head_local
        t_rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - t_rest_head[b.name]).normalized()

    hips_ratio = t_rest_head["pelvis"].z / max(donor["hips_z"], 1e-4)

    # Set quaternion mode on all pose bones
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # 5. Retarget all 10 actions onto RIG_MG02
    ad = arm.animation_data_create()
    for out_name, _ in CLIP_MAP:
        clip_data = donor["clips"][out_name]
        act = bpy.data.actions.new(name=out_name)
        act.use_fake_user = True
        activate_action(arm, act)

        # Reset pose
        for pb in arm.pose.bones:
            pb.location = Vector((0.0, 0.0, 0.0))
            pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
            pb.scale = Vector((1.0, 1.0, 1.0))

        for sample in clip_data["frames"]:
            f = sample["frame"]
            scene.frame_set(f)

            # Reset pose before solving parent->child
            for pb in arm.pose.bones:
                pb.location = Vector((0.0, 0.0, 0.0))
                pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))

            # Solve body bones parent-first
            for t_bn, d_bn, mode in BONE_MAP:
                pb = arm.pose.bones[t_bn]
                d_head, d_dir, d_rot = sample["bones"][d_bn]

                if mode == "delta":
                    d_delta = d_rot @ donor["rest_rot"][d_bn].inverted()
                    desired_w = d_delta @ t_rest_rot[t_bn]
                else:
                    # Align target bone's rest axis to donor's rest axis first, then apply donor world delta
                    q_rest_align = t_rest_dir[t_bn].rotation_difference(donor["rest_dir"][d_bn]).to_matrix()
                    d_delta = d_rot @ donor["rest_rot"][d_bn].inverted()
                    desired_w = d_delta @ q_rest_align @ t_rest_rot[t_bn]

                # Convert desired world rotation into bone-local quaternion
                if pb.parent:
                    parent_pose_w = (arm.matrix_world @ pb.parent.matrix).to_3x3().normalized()
                    parent_rest_w = t_rest_rot[pb.parent.name]
                    inherited_w = parent_pose_w @ parent_rest_w.inverted() @ t_rest_rot[t_bn]
                else:
                    inherited_w = t_rest_rot[t_bn]

                local_mat = inherited_w.inverted() @ desired_w
                pb.rotation_quaternion = local_mat.to_quaternion().normalized()

                # Pelvis translation scaled by hips height ratio
                if t_bn == "pelvis":
                    d_disp = (d_head - donor["rest_head"][d_bn]) * hips_ratio
                    # Pelvis local basis
                    pelvis_basis = inherited_w.inverted()
                    pb.location = pelvis_basis @ d_disp

                bpy.context.view_layer.update()

            # Clamp SK_MG02 evaluated mesh lowest vertex to Z>=0 on non-down clips (prevents claw sink)
            if out_name != "BowDown":
                deps = bpy.context.evaluated_depsgraph_get()
                eo = mesh.evaluated_get(deps)
                me = eo.to_mesh()
                min_mesh_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
                eo.to_mesh_clear()
                if min_mesh_z < 0.0:
                    pb_p = arm.pose.bones["pelvis"]
                    lift_w = Vector((0.0, 0.0, -min_mesh_z))
                    parent_pose_w = (arm.matrix_world @ pb_p.parent.matrix).to_3x3().normalized()
                    inherited_w = parent_pose_w @ t_rest_rot["root"].inverted() @ t_rest_rot["pelvis"]
                    pb_p.location += inherited_w.inverted() @ lift_w
                    bpy.context.view_layer.update()

            # Subtle coat secondary sway driven by thigh pitch
            for side in ("L", "R"):
                th = arm.pose.bones[f"thigh.{side}"].rotation_quaternion.to_euler()
                for prefix, sign in (("coat_front_01", 0.35), ("coat_front_02", 0.25), ("coat_back_01", -0.25), ("coat_back_02", -0.20)):
                    cpb = arm.pose.bones.get(f"{prefix}.{side}")
                    if cpb:
                        cpb.rotation_quaternion = Quaternion((1, 0, 0), th.x * sign)

            # Position weapon bones relative to posed hand.L, subtracting rest head so world pose is exact!
            d_hand_l_pos = sample["bones"]["LeftHand"][0]
            t_hand_l_pos = arm.matrix_world @ arm.pose.bones["hand.L"].head
            for wb in WEAPON_BONES:
                w_pos, w_quat, w_scale = sample["weapons"][wb]
                rel = (w_pos - d_hand_l_pos) * weapon_scale
                target_w_pos = t_hand_l_pos + rel
                pb_w = arm.pose.bones[wb]
                w_rest_w = t_rest_rot[wb]
                pb_w.location = w_rest_w.inverted() @ (target_w_pos - t_rest_head[wb])
                pb_w.rotation_quaternion = (w_rest_w.inverted() @ w_quat.to_matrix()).to_quaternion().normalized()
                pb_w.scale = w_scale

            bpy.context.view_layer.update()

            # Insert keyframes
            for t_bn, _, _ in BONE_MAP:
                pb = arm.pose.bones[t_bn]
                pb.keyframe_insert(data_path="rotation_quaternion", frame=f)
                if t_bn in ("root", "pelvis"):
                    pb.keyframe_insert(data_path="location", frame=f)
            for cbn in COAT_BONES:
                if cbn in arm.pose.bones:
                    arm.pose.bones[cbn].keyframe_insert(data_path="rotation_quaternion", frame=f)
            for wb in WEAPON_BONES:
                pb = arm.pose.bones[wb]
                pb.keyframe_insert(data_path="location", frame=f)
                pb.keyframe_insert(data_path="rotation_quaternion", frame=f)
                pb.keyframe_insert(data_path="scale", frame=f)

        # Push action to NLA track so glTF exporter includes every clip cleanly
        tr = ad.nla_tracks.new()
        tr.name = out_name
        strip = tr.strips.new(out_name, int(clip_data["f0"]), act)
        strip.action_frame_start = clip_data["f0"]
        strip.action_frame_end = clip_data["f1"]

    # 5b. Audit prepare/hold/release/cancel/guard/attack frames for arrow & string integrity
    bow_state_audit = audit_bow_states(arm)

    # Set default active pose to BowGuard frame 1
    activate_action(arm, bpy.data.actions["BowGuard"])
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

    # 8. Optional pose proof render
    if args.out_proof:
        render_pose_proof(arm, Path(args.out_proof))

    # 9. Clean-blend round-trip re-import verification (per 文档/动作制作流程.md Step 4)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 1), round(a.frame_range[1], 1)] for a in bpy.data.actions}
    re_bones = [b.name for b in re_arm.data.bones] if re_arm else []
    re_over4 = {}
    for o in re_meshes:
        re_over4[o.name] = sum(1 for v in o.data.vertices if sum(1 for g in v.groups if g.weight > 1e-6) > 4)
    report = {
        "source_blend": args.source,
        "source_blend_sha256": sha256_file(Path(args.source)),
        "donor_blend": args.donor,
        "donor_blend_sha256": sha256_file(Path(args.donor)),
        "out_glb": str(out_glb),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "target_height": TARGET_HEIGHT,
        "decimated_body_tris": mesh_tris,
        "skin_limit_4": skin_limit_stats,
        "bow_state_audit": bow_state_audit,
        "roundtrip": {
            "armature": re_arm.name if re_arm else None,
            "bone_count": len(re_bones),
            "has_flight_arrow_bone": "FlightArrow" in re_bones,
            "mesh_names": sorted(o.name for o in re_meshes),
            "has_combat_flying_arrow": any("Combat_flying_arrow" in o.name for o in re_meshes),
            "has_combat_arrow": any(o.name == "Combat_arrow" for o in re_meshes),
            "total_tris": re_tris,
            "verts_over_4_influences": re_over4,
            "material_count": len(bpy.data.materials),
            "image_count": len(bpy.data.images),
            "action_count": len(re_actions),
            "actions": re_actions,
            "expected_clips_present": all(c in re_actions for c, _ in CLIP_MAP),
        },
    }
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MG02_BUILD_OK:", json.dumps(report["roundtrip"], ensure_ascii=False))
    return report


def audit_bow_states(arm) -> dict:
    """Check visible vs intentionally hidden arrow & string geometry across all bow combat clips."""
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    clips_to_check = ["BowLoad", "BowAim", "BowRelease", "BowCancelLoaded", "BowGuard", "BowAttack"]
    out = {}
    for cname in clips_to_check:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        held_vis, held_hid, fly_vis, fly_hid = [], [], [], []
        both_visible = 0
        visible_degen = 0
        string_degen = 0
        held_transitions = 0
        prev_held = None
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            h_sc = arm.pose.bones["HeldArrow"].scale.length
            f_sc = arm.pose.bones["FlightArrow"].scale.length
            h_on = h_sc > 0.1
            f_on = f_sc > 0.1
            if h_on:
                held_vis.append(f)
            else:
                held_hid.append(f)
            if f_on:
                fly_vis.append(f)
            else:
                fly_hid.append(f)
            if h_on and f_on:
                both_visible += 1
            if prev_held is not None and h_on != prev_held:
                held_transitions += 1
            prev_held = h_on

            # Check geometry non-degeneracy on every visible arrow and on both strings
            checks = [("Combat_String_0", True), ("Combat_String_1", True)]
            if h_on:
                checks.append(("Combat_arrow", False))
            if f_on:
                checks.append(("Combat_flying_arrow", False))
            for oname, is_str in checks:
                eo = bpy.data.objects[oname].evaluated_get(deps)
                me = eo.to_mesh()
                degen = sum(1 for p in me.polygons if p.area < 1e-8)
                eo.to_mesh_clear()
                if degen > 0:
                    if is_str:
                        string_degen += degen
                    else:
                        visible_degen += degen
        out[cname] = {
            "frames": [f0, f1],
            "held_visible_count": len(held_vis),
            "held_hidden_count": len(held_hid),
            "flight_visible_count": len(fly_vis),
            "flight_hidden_count": len(fly_hid),
            "both_arrows_visible_frames": both_visible,
            "held_visibility_transitions": held_transitions,
            "visible_arrow_degenerate_faces": visible_degen,
            "string_degenerate_faces": string_degen,
        }
    return out


def render_pose_proof(arm, out_path: Path) -> None:
    """Render a quick 1280x720 orthographic Workbench shot of BowAim pose for visual verification."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.film_transparent = False
    if scene.world:
        scene.world.color = (0.82, 0.77, 0.69)

    cam_data = bpy.data.cameras.new("ProofCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.2
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((2.2, -3.2, 2.6))
    direction = Vector((0.0, 0.0, 0.95)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    # Hide flying arrow sample during held-bow aim proof (same as bow_actor.gd)
    fa = bpy.data.objects.get("Combat_flying_arrow")
    if fa:
        fa.hide_render = True

    # Pose in BowAim mid-frame so bow draw, horns, and hunter legs are clearly visible
    activate_action(arm, bpy.data.actions["BowAim"])
    scene.frame_set(10)
    bpy.context.view_layer.update()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_mg02(parse_args())

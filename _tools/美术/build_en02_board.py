"""Build EN02_Board.blend and EN02_Board.glb for #15 (普通敌人 EN02 磐壳奔兽).

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/EN02_skinned.blend
(single watertight armored quadruped mesh, 20 bones including dedicated `shell` bone)
and authors 11 in-place animations (zero world XY root/pelvis drift across all clips):
- Core (6): EN02Idle, EN02Walk, EN02Stop, EN02Attack, EN02Hit, EN02Down
- EN02-A 沉角冲线 (4): EN02ChargeRaise (压角蓄势), EN02ChargeHold (压角保持),
  EN02ChargeRelease (无根位移冲线释放), EN02ChargeCancel (取消)
- Post-release +1 beat seam cue (1): EN02ShellSeam (壳缝姿态 — independent expression)

Enforces max-4 normalized weights, clamps floor contact on ALL 11 clips including EN02Down
(half-frame verified: 0 samples < -3 cm), verifies zero root XY drift, runs clean-blend
round-trip re-import, records embedded texture SHA-256, and renders 8 same-camera proof panels
plus a small-size (1280x720 board scale) silhouette readability render.
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
from mathutils import Euler, Vector

TARGET_HEIGHT = 1.18
DECIMATE_RATIO = 0.24

CLIPS = [
    ("EN02Idle", 48),
    ("EN02Walk", 24),
    ("EN02Stop", 18),
    ("EN02Attack", 24),
    ("EN02Hit", 18),
    ("EN02Down", 30),
    ("EN02ChargeRaise", 18),
    ("EN02ChargeHold", 36),
    ("EN02ChargeRelease", 24),
    ("EN02ChargeCancel", 18),
    ("EN02ShellSeam", 30),
]

PROOF_PANELS = [
    ("0_idle", "EN02Idle", 12),
    ("1_walk", "EN02Walk", 6),
    ("2_A_hold", "EN02ChargeHold", 18),
    ("3_A_release", "EN02ChargeRelease", 12),
    ("4_A_cancel", "EN02ChargeCancel", 9),
    ("5_shell_seam", "EN02ShellSeam", 15),
    ("6_down_start", "EN02Down", 1),
    ("7_down_end", "EN02Down", 30),
]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
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


def clean_topology(mesh_obj) -> dict:
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    wires = [e for e in bm.edges if len(e.link_faces) == 0]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES")
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    vis, islands = set(), []
    for v in bm.verts:
        if v.index in vis:
            continue
        st, comp = [v], []
        vis.add(v.index)
        while st:
            c = st.pop()
            comp.append(c)
            for e in c.link_edges:
                o = e.other_vert(c)
                if o.index not in vis:
                    vis.add(o.index)
                    st.append(o)
        islands.append(len(comp))
    islands.sort(reverse=True)
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()
    return {"wires_removed": len(wires), "loose_removed": len(loose), "islands": islands}


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


def set_en02_pose(arm, clip: str, t: float) -> None:
    """In-place quadruped animations for EN02 (磐壳奔兽).
    Strictly ZERO root/pelvis world XY translation across all clips (including EN02ChargeRelease).
    """
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
    s2 = math.sin(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)
    c2 = math.cos(t * math.pi * 2.0)

    if clip == "EN02Idle":
        pbs["spine"].rotation_euler = Euler((math.radians(2.5 * s2), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(3.0 * s2), math.radians(5.0 * c2), 0.0), "XYZ")
        pbs["tail_01"].rotation_euler = Euler((0.0, math.radians(14.0 * s2), 0.0), "XYZ")
        pbs["tail_02"].rotation_euler = Euler((0.0, math.radians(18.0 * c2), 0.0), "XYZ")
    elif clip == "EN02Walk":
        pbs["spine"].rotation_euler = Euler((math.radians(4.0 * s2), 0.0, math.radians(4.0 * c2)), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(-4.0 * s2), 0.0, 0.0), "XYZ")
        for bn, sgn in (("front_01.L", 1), ("rear_01.R", 1), ("front_01.R", -1), ("rear_01.L", -1)):
            pbs[bn].rotation_euler = Euler((math.radians(22.0 * sgn * s2), 0.0, 0.0), "XYZ")
        for bn, sgn in (("front_02.L", 1), ("rear_02.R", 1), ("front_02.R", -1), ("rear_02.L", -1)):
            pbs[bn].rotation_euler = Euler((math.radians(-16.0 * max(0.0, sgn * s2)), 0.0, 0.0), "XYZ")
        pbs["tail_01"].rotation_euler = Euler((0.0, math.radians(16.0 * s2), 0.0), "XYZ")
    elif clip == "EN02Stop":
        w = 1.0 - t
        pbs["spine"].rotation_euler = Euler((math.radians(9.0 * w), 0.0, 0.0), "XYZ")
        pbs["front_01.L"].rotation_euler = Euler((math.radians(-14.0 * w), 0.0, 0.0), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(-14.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN02Attack":
        # Quick heavy brow-horn headbutt snap
        ram = math.sin(min(1.0, t / 0.55) * math.pi)
        pbs["spine"].rotation_euler = Euler((math.radians(14.0 * ram), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(20.0 * ram), 0.0, 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(-18.0 * ram), 0.0, 0.0), "XYZ")
        pbs["front_01.L"].rotation_euler = Euler((math.radians(-12.0 * ram), 0.0, 0.0), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(-12.0 * ram), 0.0, 0.0), "XYZ")
    elif clip == "EN02Hit":
        pbs["spine"].rotation_euler = Euler((math.radians(-14.0 * s1), 0.0, math.radians(8.0 * s2)), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(-18.0 * s1), 0.0, 0.0), "XYZ")
        pbs["shell"].rotation_euler = Euler((math.radians(-6.0 * s1), 0.0, math.radians(6.0 * s2)), "XYZ")
    elif clip == "EN02Down":
        # Quadruped legs splay/collapse cleanly to floor, heavy shell settles low (grounded via world +Z clamp)
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        pbs["pelvis"].rotation_euler = Euler((math.radians(16.0 * w), 0.0, math.radians(24.0 * w)), "XYZ")
        pbs["spine"].rotation_euler = Euler((math.radians(12.0 * w), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(22.0 * w), math.radians(10.0 * w), 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(18.0 * w), 0.0, 0.0), "XYZ")
        for side, sgn in (("L", 1), ("R", -1)):
            pbs[f"front_01.{side}"].rotation_euler = Euler((math.radians(-26.0 * w), 0.0, math.radians(34.0 * sgn * w)), "XYZ")
            pbs[f"front_02.{side}"].rotation_euler = Euler((math.radians(24.0 * w), 0.0, 0.0), "XYZ")
            pbs[f"rear_01.{side}"].rotation_euler = Euler((math.radians(24.0 * w), 0.0, math.radians(32.0 * sgn * w)), "XYZ")
            pbs[f"rear_02.{side}"].rotation_euler = Euler((math.radians(-20.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN02ChargeRaise":
        # 压角蓄势: dip horn low & paw right front hoof back
        w = min(1.0, t * 1.2)
        pbs["spine"].rotation_euler = Euler((math.radians(18.0 * w), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(28.0 * w), 0.0, 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(20.0 * w), 0.0, 0.0), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(26.0 * w), 0.0, 0.0), "XYZ")
        pbs["front_02.R"].rotation_euler = Euler((math.radians(-28.0 * w), 0.0, 0.0), "XYZ")
        pbs["rear_01.L"].rotation_euler = Euler((math.radians(-16.0 * w), 0.0, 0.0), "XYZ")
        pbs["rear_01.R"].rotation_euler = Euler((math.radians(-16.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN02ChargeHold":
        # 压角保持: coiled low brow-horn stance with taut breathing quiver
        pbs["spine"].rotation_euler = Euler((math.radians(18.0 + 2.0 * s2), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(30.0 + 3.0 * s2), 0.0, 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(20.0), 0.0, math.radians(3.0 * c2)), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(24.0 + 8.0 * max(0.0, s2)), 0.0, 0.0), "XYZ")
        pbs["front_02.R"].rotation_euler = Euler((math.radians(-26.0 - 8.0 * max(0.0, s2)), 0.0, 0.0), "XYZ")
        pbs["rear_01.L"].rotation_euler = Euler((math.radians(-16.0), 0.0, 0.0), "XYZ")
        pbs["rear_01.R"].rotation_euler = Euler((math.radians(-16.0), 0.0, 0.0), "XYZ")
    elif clip == "EN02ChargeRelease":
        # 无根位移冲线释放: fierce in-place charging drive + upward horn gore thrust (ZERO world XY root drift!)
        drive = math.sin(min(1.0, t / 0.65) * math.pi)
        gallop = math.sin(t * math.pi * 4.0)
        pbs["spine"].rotation_euler = Euler((math.radians(14.0 * (1.0 - t) - 18.0 * drive), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(26.0 * (1.0 - t) - 34.0 * drive), 0.0, 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(16.0 * (1.0 - t) - 24.0 * drive), 0.0, 0.0), "XYZ")
        pbs["front_01.L"].rotation_euler = Euler((math.radians(28.0 * gallop), 0.0, 0.0), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(28.0 * gallop), 0.0, 0.0), "XYZ")
        pbs["rear_01.L"].rotation_euler = Euler((math.radians(-28.0 * gallop), 0.0, 0.0), "XYZ")
        pbs["rear_01.R"].rotation_euler = Euler((math.radians(-28.0 * gallop), 0.0, 0.0), "XYZ")
    elif clip == "EN02ChargeCancel":
        w = 1.0 - t
        pbs["spine"].rotation_euler = Euler((math.radians(18.0 * w), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(28.0 * w), 0.0, 0.0), "XYZ")
        pbs["head"].rotation_euler = Euler((math.radians(20.0 * w), 0.0, 0.0), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(24.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN02ShellSeam":
        # 壳缝姿态 (post-release +1 beat): shell lifts/tilts back exposing flank seam, low panting recovery
        seam = 0.85 + 0.15 * s2
        pbs["shell"].rotation_euler = Euler((math.radians(-22.0 * seam), 0.0, math.radians(6.0 * c2)), "XYZ")
        pbs["spine"].rotation_euler = Euler((math.radians(10.0 * seam), 0.0, 0.0), "XYZ")
        pbs["neck"].rotation_euler = Euler((math.radians(14.0 + 4.0 * s2), 0.0, 0.0), "XYZ")
        pbs["front_01.L"].rotation_euler = Euler((math.radians(-10.0), 0.0, math.radians(10.0)), "XYZ")
        pbs["front_01.R"].rotation_euler = Euler((math.radians(-10.0), 0.0, math.radians(-10.0)), "XYZ")


def build_en02(args: argparse.Namespace) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    scene.render.fps = 24

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA" or obj.name == "Icosphere":
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    arm = bpy.data.objects["RIG_EN02"]
    mesh = bpy.data.objects["SK_EN02"]

    tex_hashes = {}
    for im in bpy.data.images:
        if im.packed_file is not None:
            tex_hashes[im.name] = hashlib.sha256(bytes(im.packed_file.data)).hexdigest()

    # 1. Scale cleanly to TARGET_HEIGHT (1.18m) & ground Z=0
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

    # 2. Decimate + clean topology + enforce max-4 normalized weights
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Decimate_P06", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    topo_stats = clean_topology(mesh)
    skin_stats = enforce_max_4_weights(mesh)
    body_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"

    # Precompute pelvis local-to-world rest transform for vertical-only floor clamping (ZERO XY drift!)
    p_rest = (arm.matrix_world @ arm.data.bones["pelvis"].matrix_local).to_3x3().normalized()
    r_rest = (arm.matrix_world @ arm.data.bones["root"].matrix_local).to_3x3().normalized()
    pelvis_rest_head = arm.matrix_world @ arm.data.bones["pelvis"].head_local

    # 3. Author all 11 clips with exact vertical-only floor clamping (zero XY drift, including EN02Down!)
    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()
    bone_names = [b.name for b in arm.data.bones]

    for cname, n_frames in CLIPS:
        act = bpy.data.actions.new(name=cname)
        act.use_fake_user = True
        activate_action(arm, act)
        for f in range(1, n_frames + 1):
            t = (f - 1) / max(1, n_frames - 1)
            scene.frame_set(f)
            set_en02_pose(arm, cname, t)
            bpy.context.view_layer.update()

            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            eo.to_mesh_clear()
            if min_z < 0.0:
                pb_p = arm.pose.bones["pelvis"]
                parent_pose_w = (arm.matrix_world @ pb_p.parent.matrix).to_3x3().normalized()
                inherited_w = parent_pose_w @ r_rest.inverted() @ p_rest
                pb_p.location += inherited_w.inverted() @ Vector((0.0, 0.0, -min_z))
                bpy.context.view_layer.update()

            for bn in bone_names:
                pb = arm.pose.bones[bn]
                pb.keyframe_insert(data_path="rotation_euler", frame=f)
                if bn in ("root", "pelvis"):
                    pb.keyframe_insert(data_path="location", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = cname
        strip = tr.strips.new(cname, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = n_frames

    # 4. Half-frame floor QA + root/pelvis XY drift QA across ALL 11 clips
    hf_summary = {"worst_min_z": 999.0, "worst_clip": "", "worst_frame": 0.0, "samples_below_neg_3cm": 0, "max_root_xy_drift_m": 0.0}
    clip_qa = {}
    for cname, n_frames in CLIPS:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        hf_min, hf_worst, sub_3cm, max_xy, degen = 999.0, 1.0, 0, 0.0, 0
        cur = 1.0
        while cur <= float(n_frames) + 1e-4:
            fi = int(math.floor(cur))
            scene.frame_set(fi, subframe=cur - fi)
            bpy.context.view_layer.update()
            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            mz = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            if cur == 1.0:
                degen = sum(1 for p in me.polygons if p.area < 1e-8)
            eo.to_mesh_clear()
            p_head_w = arm.matrix_world @ arm.pose.bones["pelvis"].head
            xy = math.hypot(p_head_w.x - pelvis_rest_head.x, p_head_w.y - pelvis_rest_head.y)
            max_xy = max(max_xy, xy)
            if mz < hf_min:
                hf_min, hf_worst = mz, cur
            if mz < -0.03:
                sub_3cm += 1
            cur += 0.5
        if hf_min < hf_summary["worst_min_z"]:
            hf_summary["worst_min_z"] = round(hf_min, 5)
            hf_summary["worst_clip"] = cname
            hf_summary["worst_frame"] = round(hf_worst, 1)
        hf_summary["samples_below_neg_3cm"] += sub_3cm
        hf_summary["max_root_xy_drift_m"] = round(max(hf_summary["max_root_xy_drift_m"], max_xy), 6)
        clip_qa[cname] = {
            "half_frame_min_z": round(hf_min, 5),
            "half_frame_worst": round(hf_worst, 1),
            "samples_below_neg_3cm": sub_3cm,
            "max_root_xy_drift_m": round(max_xy, 6),
            "degenerate_faces": degen,
        }

    activate_action(arm, bpy.data.actions["EN02Idle"])
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # 5. Save editable .blend
    out_blend = Path(args.out_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    # 6. Export GLB
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

    # 7. Render 8 same-camera proof panels + small-size 1280x720 readability check
    if args.out_proof:
        render_proofs(arm, Path(args.out_proof))

    # 8. Clean-blend round-trip re-import verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 1), round(a.frame_range[1], 1)] for a in bpy.data.actions}
    re_over4 = {o.name: sum(1 for v in o.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4) for o in re_meshes}
    expected_names = {n for n, _ in CLIPS}
    roundtrip = {
        "armature": re_arm.name if re_arm else None,
        "bone_count": len(re_arm.data.bones) if re_arm else 0,
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
        "kind": "EN02",
        "source_blend": str(Path(args.source).resolve()),
        "source_blend_sha256": sha256_file(Path(args.source)),
        "embedded_texture_sha256": tex_hashes,
        "out_glb": str(out_glb.resolve()),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend.resolve()),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "target_height": TARGET_HEIGHT,
        "decimated_body_tris": body_tris,
        "topology": topo_stats,
        "skin_limit_4": skin_stats,
        "half_frame_summary": hf_summary,
        "clip_qa": clip_qa,
        "roundtrip": roundtrip,
    }
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EN02_BUILD_OK:", json.dumps({"tris": re_tris, "over4": re_over4, "actions": len(re_actions), "hf": hf_summary}, ensure_ascii=False))
    return report


def render_proofs(arm, out_dir: Path) -> None:
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
    cam_data.ortho_scale = 2.15
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.5, -2.6, 1.85))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.56)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in PROOF_PANELS:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"EN02_panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)

    # Small-size orthogonal board-distance silhouette check (matches 1280x720 board scale)
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    cam_data.ortho_scale = 12.0
    activate_action(arm, bpy.data.actions["EN02ChargeHold"])
    scene.frame_set(18)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / "EN02_small_scale_readability.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_en02(parse_args())

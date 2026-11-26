"""Build EN16_Board.{blend,glb} (校准巡弋体) and EN18_Board.{blend,glb} (界标钳) for #14.

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/{EN16,EN18}_skinned.blend
(single watertight mechanical meshes, zero gaps) and generates crisp mechanical animations directly
on each rig's exact bones (9 bones for EN16 tripod turret, 14 bones for EN18 quadruped boundary clamp):
- EN16 (10 clips): EN16Idle, EN16Walk, EN16Stop, EN16Attack, EN16Hit, EN16Down,
  EN16PulseRaise, EN16PulseHold, EN16PulseRelease, EN16PulseCancel (EN16-A 划界脉冲).
- EN18 (10 clips): EN18Idle, EN18Walk, EN18Stop, EN18Attack, EN18Hit, EN18Down,
  EN18ClampRaise, EN18ClampHold, EN18ClampRelease, EN18ClampCancel (EN18-A 闭合).

Enforces max-4 normalized weights, clamps floor contact on ALL clips including Down
(half-frame verified: 0 samples < -3 cm), runs clean-blend round-trip re-import, records
embedded texture SHA-256, and renders 6-panel same-camera proof panels (incl. Down f1 & end).
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

SPECS = {
    "EN16": {
        "armature": "RIG_EN16",
        "mesh": "SK_EN16",
        "target_height": 1.62,
        "decimate_ratio": 0.24,
        "clips": [
            ("EN16Idle", 48),
            ("EN16Walk", 24),
            ("EN16Stop", 18),
            ("EN16Attack", 24),
            ("EN16Hit", 18),
            ("EN16Down", 30),
            ("EN16PulseRaise", 18),
            ("EN16PulseHold", 36),
            ("EN16PulseRelease", 24),
            ("EN16PulseCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EN16Idle", 12),
            ("1_walk", "EN16Walk", 6),
            ("2_A_hold", "EN16PulseHold", 18),
            ("3_A_release", "EN16PulseRelease", 12),
            ("4_down_start", "EN16Down", 1),
            ("5_down_end", "EN16Down", 30),
        ],
    },
    "EN18": {
        "armature": "RIG_EN18",
        "mesh": "SK_EN18",
        "target_height": 1.58,
        "decimate_ratio": 0.24,
        "clips": [
            ("EN18Idle", 48),
            ("EN18Walk", 24),
            ("EN18Stop", 18),
            ("EN18Attack", 24),
            ("EN18Hit", 18),
            ("EN18Down", 30),
            ("EN18ClampRaise", 18),
            ("EN18ClampHold", 36),
            ("EN18ClampRelease", 24),
            ("EN18ClampCancel", 18),
        ],
        "proof_panels": [
            ("0_idle", "EN18Idle", 12),
            ("1_walk", "EN18Walk", 6),
            ("2_A_hold", "EN18ClampHold", 18),
            ("3_A_release", "EN18ClampRelease", 12),
            ("4_down_start", "EN18Down", 1),
            ("5_down_end", "EN18Down", 30),
        ],
    },
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kind", choices=["EN16", "EN18"], required=True)
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


def set_en16_pose(arm, clip: str, t: float) -> None:
    """Procedural mechanical poses for EN16 (校准巡弋体: tripod + T-bar emitter turret)."""
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
    s2 = math.sin(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)
    if clip == "EN16Idle":
        pbs["body"].location = Vector((0.0, 0.0, 0.02 * s2))
        pbs["turret"].rotation_euler = Euler((0.0, math.radians(16.0 * s2), 0.0), "XYZ")
    elif clip == "EN16Walk":
        pbs["body"].location = Vector((0.0, 0.0, 0.045 * abs(s2)))
        pbs["body"].rotation_euler = Euler((math.radians(5.0), 0.0, math.radians(4.0 * s2)), "XYZ")
        pbs["turret"].rotation_euler = Euler((0.0, math.radians(-6.0 * s2), 0.0), "XYZ")
        for idx, phase in ((1, 0.0), (2, 2.1), (3, 4.2)):
            a = math.sin(t * math.pi * 2.0 + phase)
            pbs[f"leg{idx}_01"].rotation_euler = Euler((math.radians(18.0 * a), 0.0, 0.0), "XYZ")
            pbs[f"leg{idx}_02"].rotation_euler = Euler((math.radians(-14.0 * max(0.0, a)), 0.0, 0.0), "XYZ")
    elif clip == "EN16Stop":
        w = 1.0 - t
        pbs["body"].rotation_euler = Euler((math.radians(7.0 * w), 0.0, 0.0), "XYZ")
        pbs["turret"].rotation_euler = Euler((0.0, math.radians(8.0 * w), 0.0), "XYZ")
    elif clip == "EN16Attack":
        # Quick calibration beam snap forward + recoil
        snap = math.sin(min(1.0, t / 0.55) * math.pi)
        pbs["body"].rotation_euler = Euler((math.radians(-10.0 * snap), 0.0, 0.0), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(16.0 * snap), math.radians(12.0 * s2), 0.0), "XYZ")
    elif clip == "EN16Hit":
        pbs["body"].rotation_euler = Euler((math.radians(-16.0 * s1), 0.0, math.radians(10.0 * s2)), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(-14.0 * s1), math.radians(-18.0 * s1), 0.0), "XYZ")
    elif clip == "EN16Down":
        # Smooth ease-out tripod collapse & dormant tilted T-turret
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        pbs["body"].location = Vector((0.0, 0.0, -0.34 * w))
        pbs["body"].rotation_euler = Euler((math.radians(32.0 * w), 0.0, math.radians(18.0 * w)), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(28.0 * w), math.radians(34.0 * w), math.radians(12.0 * w)), "XYZ")
        for idx in (1, 2, 3):
            pbs[f"leg{idx}_01"].rotation_euler = Euler((math.radians(-34.0 * w), 0.0, 0.0), "XYZ")
            pbs[f"leg{idx}_02"].rotation_euler = Euler((math.radians(24.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN16PulseRaise":
        w = min(1.0, t * 1.2)
        pbs["body"].location = Vector((0.0, 0.0, -0.06 * w))
        pbs["body"].rotation_euler = Euler((math.radians(10.0 * w), 0.0, 0.0), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(-8.0 * w), math.radians(28.0 * w), 0.0), "XYZ")
    elif clip == "EN16PulseHold":
        pbs["body"].location = Vector((0.0, 0.0, -0.06 + 0.015 * s2))
        pbs["body"].rotation_euler = Euler((math.radians(10.0), 0.0, 0.0), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(-10.0), math.radians(28.0 + 10.0 * s2), 0.0), "XYZ")
    elif clip == "EN16PulseRelease":
        surge = math.sin(min(1.0, t / 0.55) * math.pi)
        pbs["body"].location = Vector((0.0, 0.0, -0.04 * (1.0 - t)))
        pbs["body"].rotation_euler = Euler((math.radians(-14.0 * surge), 0.0, 0.0), "XYZ")
        pbs["turret"].rotation_euler = Euler((math.radians(18.0 * surge), math.radians(-22.0 * surge), 0.0), "XYZ")
    elif clip == "EN16PulseCancel":
        w = 1.0 - t
        pbs["body"].location = Vector((0.0, 0.0, -0.06 * w))
        pbs["turret"].rotation_euler = Euler((math.radians(-8.0 * w), math.radians(28.0 * w), 0.0), "XYZ")


def set_en18_pose(arm, clip: str, t: float) -> None:
    """Procedural mechanical poses for EN18 (界标钳: quadruped + twin upright boundary jaws)."""
    pbs = arm.pose.bones
    for pb in pbs:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), "XYZ")
    s2 = math.sin(t * math.pi * 2.0)
    s1 = math.sin(t * math.pi)
    if clip == "EN18Idle":
        pbs["body"].location = Vector((0.0, 0.0, 0.018 * s2))
        pbs["claw_01.L"].rotation_euler = Euler((0.0, 0.0, math.radians(6.0 * s2)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((0.0, 0.0, math.radians(-6.0 * s2)), "XYZ")
    elif clip == "EN18Walk":
        pbs["body"].location = Vector((0.0, 0.0, 0.035 * abs(s2)))
        pbs["body"].rotation_euler = Euler((math.radians(4.0), 0.0, math.radians(5.0 * s2)), "XYZ")
        for bn, sgn in (("leg1_01.L", 1), ("leg2_01.R", 1), ("leg1_01.R", -1), ("leg2_01.L", -1)):
            pbs[bn].rotation_euler = Euler((math.radians(18.0 * sgn * s2), 0.0, 0.0), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(8.0 * s2), 0.0, 0.0), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(-8.0 * s2), 0.0, 0.0), "XYZ")
    elif clip == "EN18Stop":
        w = 1.0 - t
        pbs["body"].rotation_euler = Euler((math.radians(8.0 * w), 0.0, 0.0), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((0.0, 0.0, math.radians(8.0 * w)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((0.0, 0.0, math.radians(-8.0 * w)), "XYZ")
    elif clip == "EN18Attack":
        snap = math.sin(min(1.0, t / 0.55) * math.pi)
        pbs["body"].rotation_euler = Euler((math.radians(12.0 * snap), 0.0, 0.0), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(24.0 * snap), 0.0, math.radians(-22.0 * snap)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(24.0 * snap), 0.0, math.radians(22.0 * snap)), "XYZ")
    elif clip == "EN18Hit":
        pbs["body"].rotation_euler = Euler((math.radians(-14.0 * s1), 0.0, math.radians(8.0 * s2)), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((0.0, 0.0, math.radians(20.0 * s1)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((0.0, 0.0, math.radians(-20.0 * s1)), "XYZ")
    elif clip == "EN18Down":
        # Quadruped legs fold out, heavy boundary jaws slump forward-inward onto ground
        w = min(1.0, t * 1.15)
        w = w * w * (3.0 - 2.0 * w)
        pbs["body"].location = Vector((0.0, 0.0, -0.22 * w))
        pbs["body"].rotation_euler = Euler((math.radians(24.0 * w), 0.0, math.radians(8.0 * w)), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(42.0 * w), 0.0, math.radians(18.0 * w)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(42.0 * w), 0.0, math.radians(-18.0 * w)), "XYZ")
        pbs["claw_02.L"].rotation_euler = Euler((math.radians(26.0 * w), 0.0, 0.0), "XYZ")
        pbs["claw_02.R"].rotation_euler = Euler((math.radians(26.0 * w), 0.0, 0.0), "XYZ")
        for bn in ("leg1_01.L", "leg1_01.R", "leg2_01.L", "leg2_01.R"):
            pbs[bn].rotation_euler = Euler((math.radians(-22.0 * w), 0.0, 0.0), "XYZ")
    elif clip == "EN18ClampRaise":
        # EN18-A 闭合 windup: jaws flare WIDE open!
        w = min(1.0, t * 1.2)
        pbs["body"].location = Vector((0.0, 0.0, -0.05 * w))
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(-10.0 * w), 0.0, math.radians(28.0 * w)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(-10.0 * w), 0.0, math.radians(-28.0 * w)), "XYZ")
    elif clip == "EN18ClampHold":
        pbs["body"].location = Vector((0.0, 0.0, -0.05 + 0.012 * s2))
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(-10.0), 0.0, math.radians(28.0 + 4.0 * s2)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(-10.0), 0.0, math.radians(-28.0 - 4.0 * s2)), "XYZ")
    elif clip == "EN18ClampRelease":
        # EN18-A 闭合 release: massive twin jaws SNAP SHUT together at center!
        shut = math.sin(min(1.0, t / 0.60) * math.pi)
        pbs["body"].rotation_euler = Euler((math.radians(10.0 * shut), 0.0, 0.0), "XYZ")
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(18.0 * shut), 0.0, math.radians(-30.0 * shut)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(18.0 * shut), 0.0, math.radians(30.0 * shut)), "XYZ")
        pbs["claw_02.L"].rotation_euler = Euler((0.0, 0.0, math.radians(-14.0 * shut)), "XYZ")
        pbs["claw_02.R"].rotation_euler = Euler((0.0, 0.0, math.radians(14.0 * shut)), "XYZ")
    elif clip == "EN18ClampCancel":
        w = 1.0 - t
        pbs["body"].location = Vector((0.0, 0.0, -0.05 * w))
        pbs["claw_01.L"].rotation_euler = Euler((math.radians(-10.0 * w), 0.0, math.radians(28.0 * w)), "XYZ")
        pbs["claw_01.R"].rotation_euler = Euler((math.radians(-10.0 * w), 0.0, math.radians(-28.0 * w)), "XYZ")


def build_guard(args: argparse.Namespace) -> dict:
    spec = SPECS[args.kind]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    scene.render.fps = 24

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA" or obj.name == "Icosphere":
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    arm = bpy.data.objects[spec["armature"]]
    mesh = bpy.data.objects[spec["mesh"]]

    tex_hashes = {}
    for im in bpy.data.images:
        if im.packed_file is not None:
            tex_hashes[im.name] = hashlib.sha256(bytes(im.packed_file.data)).hexdigest()

    # 1. Scale cleanly to target_height & ground Z=0
    zs = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    scale_fac = spec["target_height"] / (max(zs) - min(zs))
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
    mod.ratio = spec["decimate_ratio"]
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    topo_stats = clean_topology(mesh)
    skin_stats = enforce_max_4_weights(mesh)
    body_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"

    # 3. Author all 10 clips with exact every-frame floor clamping (including Down!)
    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()
    pose_fn = set_en16_pose if args.kind == "EN16" else set_en18_pose
    bone_names = [b.name for b in arm.data.bones]

    for cname, n_frames in spec["clips"]:
        act = bpy.data.actions.new(name=cname)
        act.use_fake_user = True
        activate_action(arm, act)
        for f in range(1, n_frames + 1):
            t = (f - 1) / max(1, n_frames - 1)
            scene.frame_set(f)
            pose_fn(arm, cname, t)
            bpy.context.view_layer.update()

            # Clamp floor contact on EVERY clip including Down (world +Z -> body bone local space!)
            eo = mesh.evaluated_get(deps)
            me = eo.to_mesh()
            min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
            eo.to_mesh_clear()
            if min_z < 0.0:
                pb_b = arm.pose.bones["body"]
                lift_w = Vector((0.0, 0.0, -min_z))
                if pb_b.parent:
                    parent_pose_w = (arm.matrix_world @ pb_b.parent.matrix).to_3x3().normalized()
                    p_rest = (arm.matrix_world @ arm.data.bones[pb_b.parent.name].matrix_local).to_3x3().normalized()
                    b_rest = (arm.matrix_world @ arm.data.bones["body"].matrix_local).to_3x3().normalized()
                    inherited_w = parent_pose_w @ p_rest.inverted() @ b_rest
                else:
                    inherited_w = (arm.matrix_world @ arm.data.bones["body"].matrix_local).to_3x3().normalized()
                pb_b.location += inherited_w.inverted() @ lift_w
                bpy.context.view_layer.update()

            for bn in bone_names:
                pb = arm.pose.bones[bn]
                pb.keyframe_insert(data_path="rotation_euler", frame=f)
                if bn in ("root", "body"):
                    pb.keyframe_insert(data_path="location", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = cname
        strip = tr.strips.new(cname, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = n_frames

    # 4. Half-frame floor QA sweep across ALL 10 clips
    hf_summary = {"worst_min_z": 999.0, "worst_clip": "", "worst_frame": 0.0, "samples_below_neg_3cm": 0}
    clip_qa = {}
    for cname, n_frames in spec["clips"]:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        hf_min, hf_worst, sub_3cm, degen = 999.0, 1.0, 0, 0
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
        clip_qa[cname] = {"half_frame_min_z": round(hf_min, 5), "half_frame_worst": round(hf_worst, 1),
                          "samples_below_neg_3cm": sub_3cm, "degenerate_faces": degen}

    activate_action(arm, bpy.data.actions[f"{args.kind}Idle"])
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

    # 7. Render 6 same-camera proof panels (incl. Down start & end)
    if args.out_proof:
        render_proof(arm, spec["proof_panels"], Path(args.out_proof), args.kind)

    # 8. Clean-blend round-trip re-import verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    re_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    re_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    re_tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in re_meshes)
    re_actions = {a.name: [round(a.frame_range[0], 1), round(a.frame_range[1], 1)] for a in bpy.data.actions}
    re_over4 = {o.name: sum(1 for v in o.data.vertices if len([g for g in v.groups if g.weight > 1e-6]) > 4) for o in re_meshes}
    expected_names = {n for n, _ in spec["clips"]}
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
        "kind": args.kind,
        "source_blend": str(Path(args.source).resolve()),
        "source_blend_sha256": sha256_file(Path(args.source)),
        "embedded_texture_sha256": tex_hashes,
        "out_glb": str(out_glb.resolve()),
        "out_glb_bytes": out_glb.stat().st_size,
        "out_glb_sha256": sha256_file(out_glb),
        "out_blend": str(out_blend.resolve()),
        "out_blend_bytes": out_blend.stat().st_size,
        "out_blend_sha256": sha256_file(out_blend),
        "target_height": spec["target_height"],
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
    print(f"{args.kind}_BUILD_OK:", json.dumps({"tris": re_tris, "over4": re_over4, "actions": len(re_actions), "hf_worst": hf_summary}, ensure_ascii=False))
    return report


def render_proof(arm, panels: list[tuple[str, str, int]], out_dir: Path, kind: str) -> None:
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
    cam_data.ortho_scale = 2.45
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.4, -3.0, 2.0))
    cam.rotation_euler = (Vector((0.0, 0.0, 0.78)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, cname, fr in panels:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        scene.render.filepath = str(out_dir / f"{kind}_panel_{suffix}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_guard(parse_args())

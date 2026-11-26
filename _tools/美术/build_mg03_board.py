"""Build MG03 (Yilei) animated P06 board GLB and editable Blend from MG03_skinned.blend + M04 caster donors.

Reuses D:/Personal_dev-assets/设计整理/敌人蒙皮权重_20261115/rigged/MG03_skinned.blend,
M04_Meshy_24_Keyframe_Actions.blend, and M04_Meshy_Mist_Cast.blend.
Preserves shoulder/back bone plates (back_horns), deep crimson cloth, right-hand needle wand
(MG03_Needle), and left-hand missing-page ledger (MG03_Ledger).
Generates 18 clips with distinct silhouettes for MG03-A (Chant), MG03-B (Self-Shield),
and MG03-C (Needle Strike) across Raise/Hold/Release/Cancel, plus Idle/Walk/Stop/Attack/Hit/Down.

Built-in QA:
  - Explicit top-4 normalized bone weights on every mesh (0 verts > 4 influences)
  - Zero rest-pose prop overlap and zero zero-scale hidden degeneracy
  - Evaluated-mesh ground clamp (Z >= 0 on non-down clips)
  - Clean-blend round-trip re-import verification + held-prop contact audit
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

# Base clips retargeted from M04_Meshy_24_Keyframe_Actions.blend
BASE_CLIPS = [
    ("Mg03Idle", "M04_Meshy_01_Idle", "idle"),
    ("Mg03Walk", "M04_Meshy_02_Walk", "walk"),
    ("Mg03Stop", "M04_Meshy_08_WalkStop", "stop"),
    ("Mg03Attack", "M04_Meshy_04_Attack", "attack"),
    ("Mg03Hit", "M04_Meshy_13_HitLight", "hit"),
    ("Mg03Down", "M04_Meshy_06_Down", "down"),
]

# Skill clips retargeted from M04_Meshy_Mist_Cast.blend + distinct A/B/C silhouette offsets
SKILL_CLIPS = [
    # MG03-A: 失名诵读 (left hand raises open ledger high/forward; right hand sweeps needle across pages)
    ("Mg03ChantRaise", "M04_Meshy_01_RaisePalm", "A_raise"),
    ("Mg03ChantHold", "M04_Meshy_02_AimHold", "A_hold"),
    ("Mg03ChantRelease", "M04_Meshy_03_MistRelease", "A_release"),
    ("Mg03ChantCancel", "M04_Meshy_04_MistCancel", "A_cancel"),
    # MG03-B: 本人空页私盾 (both arms draw inward crossing torso; open ledger held as chest ward, needle upright)
    ("Mg03ShieldRaise", "M04_Meshy_01_RaisePalm", "B_raise"),
    ("Mg03ShieldHold", "M04_Meshy_02_AimHold", "B_hold"),
    ("Mg03ShieldRelease", "M04_Meshy_03_MistRelease", "B_release"),
    ("Mg03ShieldCancel", "M04_Meshy_04_MistCancel", "B_cancel"),
    # MG03-C: 抹名针 (right arm draws needle high/back over right shoulder, then lunges forward horizontal thrust)
    ("Mg03NeedleRaise", "M04_Meshy_01_RaisePalm", "C_raise"),
    ("Mg03NeedleHold", "M04_Meshy_02_AimHold", "C_hold"),
    ("Mg03NeedleRelease", "M04_Meshy_03_MistRelease", "C_release"),
    ("Mg03NeedleCancel", "M04_Meshy_04_MistCancel", "C_cancel"),
]

TARGET_HEIGHT = 1.96
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


def make_material(name: str, rgba: tuple[float, float, float, float], roughness: float = 0.6) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    if mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
            bsdf.inputs["Roughness"].default_value = roughness
    return mat


def add_box_mesh(name: str, parts: list[tuple[Vector, Vector, Vector, bpy.types.Material]],
                 arm_obj, bone_name: str, rest_origin: Vector) -> bpy.types.Object:
    """Build a clean single-object multi-box prop skinned 100% to bone_name at rest_origin."""
    objs = []
    for idx, (loc, scale, rot_deg, mat) in enumerate(parts):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=rest_origin + loc)
        o = bpy.context.active_object
        o.name = f"{name}_p{idx}"
        o.scale = scale
        o.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ")
        o.data.materials.append(mat)
        objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    prop = bpy.context.active_object
    prop.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Triangulate cleanly for glTF
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode="OBJECT")

    prop.parent = arm_obj
    prop.parent_type = "OBJECT"
    prop.matrix_parent_inverse = Matrix.Identity(4)
    vg = prop.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(prop.data.vertices))), 1.0, "REPLACE")
    mod = prop.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    return prop


def build_held_props(arm_obj) -> tuple[bpy.types.Object, bpy.types.Object]:
    """Create MG03_Needle (right hand) and MG03_Ledger (left hand) matching v3/v4 sheets."""
    mat_silver = make_material("MG03_NeedleSteel", (0.82, 0.80, 0.76, 1.0), 0.32)
    mat_leather = make_material("MG03_Leather", (0.34, 0.19, 0.12, 1.0), 0.68)
    mat_crimson = make_material("MG03_CrimsonRibbon", (0.56, 0.14, 0.14, 1.0), 0.58)
    mat_page = make_material("MG03_ParchmentPage", (0.89, 0.81, 0.66, 1.0), 0.72)
    mat_bronze = make_material("MG03_BronzeClasp", (0.64, 0.48, 0.28, 1.0), 0.45)

    # Add PropNeedle under hand.R and PropBook under hand.L in Edit Mode
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb_hr = arm_obj.data.edit_bones["hand.R"]
    eb_hl = arm_obj.data.edit_bones["hand.L"]

    needle_origin = eb_hr.tail.copy()
    eb_needle = arm_obj.data.edit_bones.new("PropNeedle")
    eb_needle.head = needle_origin
    eb_needle.tail = needle_origin + Vector((0.0, -0.18, 0.0))
    eb_needle.parent = eb_hr
    eb_needle.use_connect = False

    book_origin = eb_hl.tail.copy()
    eb_book = arm_obj.data.edit_bones.new("PropBook")
    eb_book.head = book_origin
    eb_book.tail = book_origin + Vector((0.0, -0.16, 0.0))
    eb_book.parent = eb_hl
    eb_book.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Right-hand Needle Wand (aligned along -Y forward from palm, ~0.72m total length for crisp 1280x720 silhouette)
    needle_parts = [
        # Wrapped leather handle at palm
        (Vector((0.0, 0.04, 0.0)), Vector((0.036, 0.18, 0.036)), (0, 0, 0), mat_leather),
        # Bronze pommel collar
        (Vector((0.0, 0.14, 0.0)), Vector((0.044, 0.03, 0.044)), (0, 0, 0), mat_bronze),
        # Crimson ribbon tail fluttering from handle
        (Vector((0.0, 0.12, -0.09)), Vector((0.014, 0.045, 0.18)), (18, 0, 0), mat_crimson),
        # Long slender bone-silver needle blade
        (Vector((0.0, -0.22, 0.0)), Vector((0.022, 0.36, 0.022)), (0, 0, 0), mat_silver),
        (Vector((0.0, -0.46, 0.0)), Vector((0.012, 0.18, 0.012)), (0, 0, 0), mat_silver),
    ]
    needle = add_box_mesh("MG03_Needle", needle_parts, arm_obj, "PropNeedle", needle_origin)

    # Left-hand Open Missing-Page Ledger (~0.34m wide open book resting on left palm)
    book_parts = [
        # Dark leather cover spine & back
        (Vector((0.0, -0.02, -0.018)), Vector((0.32, 0.24, 0.018)), (0, 0, 0), mat_leather),
        # Left intact parchment page block
        (Vector((-0.075, -0.02, 0.002)), Vector((0.14, 0.21, 0.022)), (0, -8, 0), mat_page),
        # Right missing-page ragged block (visibly shorter/torn corner to read as 缺页簿)
        (Vector((0.070, 0.005, 0.002)), Vector((0.12, 0.16, 0.018)), (0, 8, 0), mat_page),
        # Bronze clasps on outer edges
        (Vector((-0.162, -0.02, -0.004)), Vector((0.024, 0.05, 0.028)), (0, 0, 0), mat_bronze),
        (Vector((0.162, -0.02, -0.004)), Vector((0.024, 0.05, 0.028)), (0, 0, 0), mat_bronze),
        # Crimson ribbon bookmark hanging from bottom spine
        (Vector((0.0, 0.12, -0.05)), Vector((0.022, 0.08, 0.010)), (-35, 0, 0), mat_crimson),
    ]
    ledger = add_box_mesh("MG03_Ledger", book_parts, arm_obj, "PropBook", book_origin)

    # Physical leather/rope shoulder-root harness collars anchoring both crescent bone plates (v4 SHOULDER ROOT DETAIL)
    # Skinned 100% to chest so the mount stays seated against torso/shoulders across all poses
    mount_origin = Vector((0.0, 0.068, 1.425))
    mount_parts = [
        # Right shoulder bone-plate socket collar + crossed lashing straps
        (Vector((-0.098, 0.002, -0.004)), Vector((0.078, 0.072, 0.056)), (12, 16, -8), mat_leather),
        (Vector((-0.096, 0.008, 0.014)), Vector((0.084, 0.076, 0.022)), (18, 22, 14), mat_bronze),
        (Vector((-0.078, 0.010, -0.022)), Vector((0.088, 0.048, 0.024)), (8, -24, 0), mat_crimson),
        # Left shoulder bone-plate socket collar + crossed lashing straps (symmetric reinforcement)
        (Vector((0.098, 0.002, -0.004)), Vector((0.078, 0.072, 0.056)), (12, -16, 8), mat_leather),
        (Vector((0.096, 0.008, 0.014)), Vector((0.084, 0.076, 0.022)), (18, -22, -14), mat_bronze),
        (Vector((0.078, 0.010, -0.022)), Vector((0.088, 0.048, 0.024)), (8, 24, 0), mat_crimson),
    ]
    horn_mount = add_box_mesh("MG03_HornMount", mount_parts, arm_obj, "chest", mount_origin)
    return needle, ledger, horn_mount


def repair_body_mesh_qa(mesh_obj) -> dict:
    """Fix QA findings on SK_MG03 after decimation:
    1. Remove wire edges (edges with 0 linked faces).
    2. Seat the detached 64-vert right back_horns island root cleanly into the right shoulder/back
       socket (preserving the upper crescent silhouette) and blend its root weights to chest+back_horns
       so it never gaps during Idle/A/B/C motion.
    3. Separate any non-adjacent same-normal coplanar tri pairs (cloth-fold z-fighting) by 2.5mm.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 1. Remove wire edges and any resulting loose vertices (0 linked faces)
    wires = [e for e in bm.edges if len(e.link_faces) == 0]
    wire_removed = len(wires)
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="EDGES_FACES")
    loose = [v for v in bm.verts if len(v.link_faces) == 0]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    if wires or loose:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

    # 2. Identify islands and seat the smaller back_horns island root into main shoulder surface
    visited = set()
    islands = []
    for v in bm.verts:
        if v.index in visited:
            continue
        stack = [v]
        comp = []
        visited.add(v.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for e in cur.link_edges:
                o = e.other_vert(cur)
                if o.index not in visited:
                    visited.add(o.index)
                    stack.append(o)
        islands.append(comp)
    islands.sort(key=len, reverse=True)

    seated_verts = 0
    root_blend_verts = []
    if len(islands) >= 2:
        main_island = islands[0]
        for small in islands[1:]:
            small_sorted = sorted(small, key=lambda v: v.co.z)
            low_v = small_sorted[0]
            min_z = low_v.co.z
            # Find nearest vertex on main body island
            best_v = min(main_island, key=lambda mv: (mv.co - low_v.co).length)
            # Push root smoothly into shoulder socket (+1.4cm past surface) over bottom 16cm of horn
            seat_vec = (best_v.co - low_v.co) + Vector((0.010, -0.012, -0.014))
            for sv in small:
                dz = sv.co.z - min_z
                if dz < 0.16:
                    t = (1.0 - dz / 0.16) ** 1.6
                    sv.co += seat_vec * t
                    seated_verts += 1
                    root_blend_verts.append((sv.index, t))

    # 3. Micro-separate any non-adjacent same-normal coplanar tri pairs (<1.8mm plane dist, <1.8cm centroid dist)
    bm.normal_update()
    grid = {}
    for f in bm.faces:
        c = f.calc_center_median()
        key = (round(c.x, 2), round(c.y, 2), round(c.z, 2))
        grid.setdefault(key, []).append(f)
    nudged_verts = set()
    coplanar_fixed = 0
    for flist in grid.values():
        if len(flist) < 2:
            continue
        for i in range(len(flist)):
            f1 = flist[i]
            n1 = f1.normal
            c1 = f1.calc_center_median()
            v1_ids = {v.index for v in f1.verts}
            for j in range(i + 1, len(flist)):
                f2 = flist[j]
                if v1_ids & {v.index for v in f2.verts}:
                    continue
                if n1.dot(f2.normal) > 0.992:
                    c2 = f2.calc_center_median()
                    if abs((c2 - c1).dot(n1)) < 0.0020 and (c2 - c1).length < 0.018:
                        for v in f2.verts:
                            if v.index not in nudged_verts:
                                v.co += f2.normal * 0.0028
                                nudged_verts.add(v.index)
                        coplanar_fixed += 1

    bm.normal_update()
    bm.to_mesh(mesh_obj.data)
    bm.free()
    mesh_obj.data.update()

    # Smoothly anchor horn-root weights toward chest (preserves upper back_horns sway while locking root seam)
    vg_chest = mesh_obj.vertex_groups.get("chest")
    vg_horns = mesh_obj.vertex_groups.get("back_horns")
    if vg_chest and vg_horns and root_blend_verts:
        for v_idx, t in root_blend_verts:
            w_chest = 0.72 * t
            w_horns = max(0.05, 1.0 - w_chest)
            vg_chest.add([v_idx], w_chest, "REPLACE")
            vg_horns.add([v_idx], w_horns, "REPLACE")

    return {
        "wire_edges_removed": wire_removed,
        "horn_root_verts_seated": seated_verts,
        "coplanar_pairs_separated": coplanar_fixed,
    }


def skill_pose_overlay(tag: str, progress: float) -> dict[str, tuple[float, float, float]]:
    """Return bone-local additive Euler (deg) offsets for unmistakable A/B/C silhouettes at 1280x720.

    progress in [0..1] along the clip.
    """
    # Smooth envelope: ramp up on raise, steady breathing on hold, snap on release, ease out on cancel
    if tag.endswith("_raise"):
        w = min(1.0, progress * 1.25)
    elif tag.endswith("_hold"):
        w = 0.92 + 0.08 * math.sin(progress * math.pi * 2.0)
    elif tag.endswith("_release"):
        w = 1.0 - 0.55 * max(0.0, (progress - 0.35) / 0.65)
    elif tag.endswith("_cancel"):
        w = max(0.0, 1.0 - progress * 1.15)
    else:
        return {}

    if tag.startswith("A_"):
        # MG03-A 失名诵读: Left arm extends open ledger forward-outward at chest height; right arm holds needle high-vertical reciting
        thrust = math.sin(min(1.0, progress * 2.2) * math.pi) if tag == "A_release" else 0.0
        return {
            "spine_02": (8.0 * w, 0.0, 0.0),
            "back_horns": (10.0 * w, 0.0, 0.0),
            "upper_arm.L": (-18.0 * w, 0.0, 42.0 * w),
            "forearm.L": (-14.0 * w, 0.0, 12.0 * w),
            "PropBook": (-15.0 * w, 0.0, -18.0 * w),
            "upper_arm.R": (-24.0 * w, 0.0, -28.0 * w + 18.0 * thrust),
            "forearm.R": (-38.0 * w, 0.0, 24.0 * w),
            "PropNeedle": (15.0 * w, 0.0, -20.0 * thrust),
        }
    if tag.startswith("B_"):
        # MG03-B 本人空页私盾: Both arms draw tightly inward across chest; open ledger faces forward as pale ward shield
        pulse = math.sin(min(1.0, progress * 2.0) * math.pi) if tag == "B_release" else 0.0
        return {
            "spine_01": (-8.0 * w, 0.0, 0.0),
            "back_horns": (-16.0 * w - 8.0 * pulse, 0.0, 0.0),
            "upper_arm.L": (-14.0 * w, 0.0, -34.0 * w),
            "forearm.L": (-54.0 * w, 0.0, -22.0 * w),
            "PropBook": (78.0 * w, 25.0 * w, 0.0),  # open pages facing forward as ward
            "upper_arm.R": (-16.0 * w, 0.0, 38.0 * w),
            "forearm.R": (-62.0 * w, 0.0, 28.0 * w),
            "PropNeedle": (-65.0 * w, 0.0, 0.0),
        }
    if tag.startswith("C_"):
        # MG03-C 抹名针: Right arm lifts needle HIGH & WIDE above right shoulder (unmistakable javelin windup); snaps forward on release
        if tag == "C_release":
            strike = math.sin(min(1.0, progress / 0.45) * math.pi)
            return {
                "spine_02": (16.0 * strike, -22.0 * strike, 0.0),
                "back_horns": (14.0 * strike, 0.0, 0.0),
                "upper_arm.R": (25.0 * strike, 0.0, -22.0 * strike),
                "forearm.R": (10.0 * strike, 0.0, 0.0),
                "PropNeedle": (12.0 * strike, 0.0, 0.0),
                "upper_arm.L": (18.0 * strike, 0.0, 24.0 * strike),
                "forearm.L": (-18.0 * strike, 0.0, 0.0),
            }
        return {
            "spine_02": (-10.0 * w, 22.0 * w, 0.0),
            "back_horns": (-12.0 * w, 0.0, 0.0),
            "upper_arm.R": (12.0 * w, 0.0, -88.0 * w),   # lift right arm high & wide above shoulder!
            "forearm.R": (-18.0 * w, 0.0, -22.0 * w),
            "PropNeedle": (-25.0 * w, 0.0, 0.0),         # needle aimed forward-downward from high poise
            "upper_arm.L": (18.0 * w, 0.0, 28.0 * w),    # ledger held low/outward as counterbalance
            "forearm.L": (-16.0 * w, 0.0, 0.0),
        }
    return {}


def build_mg03(args: argparse.Namespace) -> dict:
    base_donor = sample_donor_file(args.donor_base, [d for _, d, _ in BASE_CLIPS])
    cast_donor = sample_donor_file(args.donor_cast, [d for _, d, _ in SKILL_CLIPS])

    # Open MG03_skinned.blend
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    scene.render.fps = base_donor["fps"]

    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)

    arm = bpy.data.objects["RIG_MG03"]
    mesh = bpy.data.objects["SK_MG03"]

    # 1. Scale to TARGET_HEIGHT and ground Z=0
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

    # 2. Decimate SK_MG03 cleanly + enforce max-4 normalized bone weights
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Decimate_P06", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = DECIMATE_RATIO
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # 2b. Repair decimated SK_MG03 QA (wire edge, back_horns shoulder seating, coplanar cloth fold)
    mesh_qa_repairs = repair_body_mesh_qa(mesh)
    skin_limit_stats = enforce_max_4_weights(mesh)
    body_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)

    # 3. Build held needle wand (hand.R), missing-page ledger (hand.L), and shoulder horn mount (chest)
    needle_obj, ledger_obj, mount_obj = build_held_props(arm)

    # 4. Precompute MG03 rest transforms
    bpy.context.view_layer.update()
    t_rest_rot, t_rest_dir, t_rest_head = {}, {}, {}
    for b in arm.data.bones:
        m = arm.matrix_world @ b.matrix_local
        t_rest_rot[b.name] = m.to_3x3().normalized()
        t_rest_head[b.name] = arm.matrix_world @ b.head_local
        t_rest_dir[b.name] = ((arm.matrix_world @ b.tail_local) - t_rest_head[b.name]).normalized()

    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # 5. Retarget all 18 clips (6 base + 12 A/B/C skill clips)
    all_specs = [(out_n, d_n, tag, base_donor) for out_n, d_n, tag in BASE_CLIPS] + \
                [(out_n, d_n, tag, cast_donor) for out_n, d_n, tag in SKILL_CLIPS]
    ad = arm.animation_data_create()
    deps = bpy.context.evaluated_depsgraph_get()

    for out_name, donor_act_name, tag, donor in all_specs:
        clip_data = donor["clips"][donor_act_name]
        hips_ratio = t_rest_head["pelvis"].z / max(donor["hips_z"], 1e-4)
        act = bpy.data.actions.new(name=out_name)
        act.use_fake_user = True
        activate_action(arm, act)

        frames_list = clip_data["frames"]
        f_start, f_end = clip_data["f0"], clip_data["f1"]
        span = max(1, f_end - f_start)

        for sample in frames_list:
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

            # Apply distinct A/B/C silhouette overlays
            overlays = skill_pose_overlay(tag, progress)
            for bn, deg_xyz in overlays.items():
                pb_o = arm.pose.bones.get(bn)
                if pb_o:
                    q_add = Euler(tuple(math.radians(a) for a in deg_xyz), "XYZ").to_quaternion()
                    pb_o.rotation_quaternion = (pb_o.rotation_quaternion @ q_add).normalized()

            # Subtle secondary sway on shoulder bone plates & crimson/shroud coat
            if "back_horns" not in overlays and "back_horns" in arm.pose.bones:
                sway = 2.5 * math.sin(progress * math.pi * 2.0)
                arm.pose.bones["back_horns"].rotation_quaternion = Euler((math.radians(sway), 0.0, 0.0), "XYZ").to_quaternion()
            for side in ("L", "R"):
                th = arm.pose.bones[f"thigh.{side}"].rotation_quaternion.to_euler()
                for prefix, sign in (("coat_front_01", 0.30), ("coat_front_02", 0.22), ("coat_back_01", -0.22), ("coat_back_02", -0.18)):
                    cpb = arm.pose.bones.get(f"{prefix}.{side}")
                    if cpb:
                        cpb.rotation_quaternion = Quaternion((1, 0, 0), th.x * sign)
            bpy.context.view_layer.update()

            # Evaluated-mesh ground clamp (Z >= 0 on non-down clips)
            if out_name != "Mg03Down":
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
            for extra_bn in COAT_BONES + ["back_horns", "PropNeedle", "PropBook"]:
                if extra_bn in arm.pose.bones:
                    arm.pose.bones[extra_bn].keyframe_insert(data_path="rotation_quaternion", frame=f)

        tr = ad.nla_tracks.new()
        tr.name = out_name
        strip = tr.strips.new(out_name, f_start, act)
        strip.action_frame_start = f_start
        strip.action_frame_end = f_end

    # 6. Audit QA (grounding, prop contact, zero degeneracy, zero rest overlap)
    qa_audit = audit_mg03_qa(arm, mesh, needle_obj, ledger_obj)

    # Set default active pose to Mg03Idle frame 1
    activate_action(arm, bpy.data.actions["Mg03Idle"])
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

    # 9. Render 4-panel silhouette proof (Idle / A-ChantHold / B-ShieldHold / C-NeedleHold)
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
    expected_names = [c for c, _, _ in BASE_CLIPS] + [c for c, _, _ in SKILL_CLIPS]

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
        "mesh_qa_repairs": mesh_qa_repairs,
        "skin_limit_4": skin_limit_stats,
        "qa_audit": qa_audit,
        "roundtrip": {
            "armature": re_arm.name if re_arm else None,
            "bone_count": len(re_bones),
            "has_back_horns_bone": "back_horns" in re_bones,
            "has_prop_needle_bone": "PropNeedle" in re_bones,
            "has_prop_book_bone": "PropBook" in re_bones,
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
    print("MG03_BUILD_OK:", json.dumps(report["roundtrip"], ensure_ascii=False))
    return report


def audit_mg03_qa(arm, mesh, needle_obj, ledger_obj) -> dict:
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    # Rest-pose AABB check between MG03_Needle and MG03_Ledger
    def rest_aabb(o):
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
    na, la = rest_aabb(needle_obj), rest_aabb(ledger_obj)
    rest_overlap = all(na[0][i] <= la[1][i] and la[0][i] <= na[1][i] for i in range(3))

    clip_checks = {}
    for cname in ["Mg03Idle", "Mg03Walk", "Mg03Attack", "Mg03Down",
                  "Mg03ChantHold", "Mg03ShieldHold", "Mg03NeedleHold", "Mg03NeedleRelease"]:
        act = bpy.data.actions[cname]
        activate_action(arm, act)
        f_mid = int(round((act.frame_range[0] + act.frame_range[1]) * 0.5))
        scene.frame_set(f_mid)
        bpy.context.view_layer.update()
        eo = mesh.evaluated_get(deps)
        me = eo.to_mesh()
        min_z = min((mesh.matrix_world @ v.co).z for v in me.vertices)
        eo.to_mesh_clear()
        # Prop contact distance from parent hand tail
        hr_tail = arm.matrix_world @ arm.pose.bones["hand.R"].tail
        hl_tail = arm.matrix_world @ arm.pose.bones["hand.L"].tail
        pn_head = arm.matrix_world @ arm.pose.bones["PropNeedle"].head
        pb_head = arm.matrix_world @ arm.pose.bones["PropBook"].head
        prop_degen = 0
        for po in (needle_obj, ledger_obj):
            peo = po.evaluated_get(deps)
            pme = peo.to_mesh()
            prop_degen += sum(1 for p in pme.polygons if p.area < 1e-8)
            peo.to_mesh_clear()
        clip_checks[cname] = {
            "sample_frame": f_mid,
            "body_min_z": round(min_z, 4),
            "needle_hand_dist": round((pn_head - hr_tail).length, 4),
            "book_hand_dist": round((pb_head - hl_tail).length, 4),
            "prop_degenerate_faces": prop_degen,
        }
    return {"rest_prop_aabb_overlap": rest_overlap, "clips": clip_checks}


def render_abc_proof(arm, out_path: Path) -> None:
    """Render 4 orthogonal pose panels (Idle, A-Chant, B-Shield, C-Needle) without external deps."""
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
    cam_data.ortho_scale = 3.2
    cam = bpy.data.objects.new("ProofCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector((1.6, -3.4, 2.5))
    cam.rotation_euler = (Vector((0.0, 0.0, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    out_path.parent.mkdir(parents=True, exist_ok=True)
    panels = [
        ("0_idle", "Mg03Idle", 10),
        ("1_A_chant", "Mg03ChantHold", 20),
        ("2_B_shield", "Mg03ShieldHold", 20),
        ("3_C_needle", "Mg03NeedleHold", 20),
    ]
    for suffix, cname, fr in panels:
        activate_action(arm, bpy.data.actions[cname])
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        panel_path = out_path.parent / f"{out_path.stem}_{suffix}.png"
        scene.render.filepath = str(panel_path)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build_mg03(parse_args())

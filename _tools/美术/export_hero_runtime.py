"""Export and verify P06 runtime hero GLBs from external master Blender projects.

Usage (Blender 5.3 background mode):
    blender --background --python _tools/美术/export_hero_runtime.py -- \
        --assets-root D:\\Personal_dev-assets \
        --out-dir 原型/P06_首章/assets/heroes \
        --heroes H08
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import bpy


HERO_RECIPES = {
    "H08": {
        "name": "陶岑",
        "output": "H08_Runtime.glb",
        "base_blend": r"Rope_LoL_Keyframe_Actions\H08_Meshy\H08_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H08_Meshy_01_Idle",
            "HeroWalk-loop": "H08_Meshy_23_ReadyAdvance",
            "HeroStop": "H08_Meshy_08_WalkStop",
            "HeroAttack": "H08_Meshy_04_Attack",
            "HeroHit": "H08_Meshy_13_HitLight",
            "HeroDown": "H08_Meshy_06_Down",
            "HeroSkillA": "H08_Meshy_21_CableCast",
        },
        "extra_blends": [
            {
                "blend": r"动画\H08_Group_Protection\H08_Meshy_Group_Protection.blend",
                "actions": {
                    "HeroRaise": "H08_Meshy_01_Gather",
                    "HeroHold-loop": "H08_Meshy_02_BraceHold",
                    "HeroRelease": "H08_Meshy_03_ShareProtection",
                    "HeroCancel": "H08_Meshy_04_LowerWithoutRelease",
                },
            }
        ],
    },
    "H01": {
        "name": "洛恩",
        "output": "H01_Runtime.glb",
        "base_blend": r"Shield_Keyframe_Actions\H01_Tripo\H01_Tripo_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H01_Tripo_05_GuardHold",
            "HeroWalk-loop": "H01_Tripo_23_GuardAdvance",
            "HeroStop": "H01_Tripo_08_WalkStop",
            "HeroAttack": "H01_Tripo_04_Attack",
            "HeroHit": "H01_Tripo_13_HitLight",
            "HeroDown": "H01_Tripo_06_Down",
            "HeroBlock": "H01_Tripo_21_ShieldBash",
        },
        "extra_blends": [
            {
                "blend": r"动画\Shield_Combat_Responses\H01_Tripo\H01_Tripo_Shield_Responses.blend",
                "actions": {
                    "HeroSkillA": "H01_Tripo_01_ShieldWard",
                    "HeroRelease": "H01_Tripo_02_Intercept",
                    "HeroCancel": "H01_Tripo_03_InterceptCancel",
                },
            }
        ],
    },
    "H02": {
        "name": "米拉",
        "output": "H02_Runtime.glb",
        "base_blend": r"Mira_Expanded_Keyframe_Actions\Mira_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "Mira_01_Idle",
            "HeroWalk-loop": "Mira_02_Walk",
            "HeroStop": "Mira_08_WalkStop",
            "HeroAttack": "Mira_04_ShootRecover",
            "HeroHit": "Mira_13_HitLight",
            "HeroDown": "Mira_06_Fall",
        },
        "exclude_meshes": ["Combat_flying_arrow"],
        "extra_blends": [
            {
                "blend": r"动画\H02_Signature_Arrows\H02_Meshy_Signature_Arrows.blend",
                "actions": {
                    "HeroSkillA": "H02_Meshy_01_Shadowpierce",
                    "HeroRaise": "H02_Meshy_02_LockDraw",
                    "HeroHold-loop": "H02_Meshy_03_LockHold",
                    "HeroRelease": "H02_Meshy_04_Throughwood",
                    "HeroCancel": "H02_Meshy_05_LockCancel",
                },
            }
        ],
    },
    "H03": {
        "name": "莉安",
        "output": "H03_Runtime.glb",
        "base_blend": r"动画\棋盘视角复验_20261120\H03_Meshy\H03_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H03_Meshy_01_Idle",
            "HeroWalk-loop": "H03_Meshy_23_ReadyAdvance",
            "HeroStop": "H03_Meshy_08_WalkStop",
            "HeroAttack": "H03_Meshy_04_Attack",
            "HeroHit": "H03_Meshy_13_HitLight",
            "HeroDown": "H03_Meshy_06_Down",
        },
        "extra_blends": [
            {
                "blend": r"动画\H03_Healing\H03_Meshy_Return_Warmth.blend",
                "actions": {
                    "HeroSkillA": "H03_Meshy_01_ReturnWarmth",
                    "HeroRaise": "H03_Meshy_01_Prepare",
                    "HeroHold-loop": "H03_Meshy_02_CastHold",
                    "HeroRelease": "H03_Meshy_03_Release",
                    "HeroCancel": "H03_Meshy_04_Cancel",
                },
            }
        ],
    },
    "H04": {
        "name": "薇拉",
        "output": "H04_Runtime.glb",
        "base_blend": r"Archer_Skinning_Fix_v2\H04_Tripo\H04_Tripo_SkinFix_Grounded_24_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H04_Tripo_01_Idle",
            "HeroWalk-loop": "H04_Tripo_02_Walk",
            "HeroStop": "H04_Tripo_08_WalkStop",
            "HeroAttack": "H04_Tripo_04_ShootRecover",
            "HeroHit": "H04_Tripo_13_HitLight",
            "HeroDown": "H04_Tripo_06_Fall",
            "HeroRaise": "H04_Tripo_17_DrawBow",
            "HeroHold-loop": "H04_Tripo_05_AimHold",
            "HeroCancel": "H04_Tripo_18_CancelAim",
        },
        "exclude_meshes": ["Combat_flying_arrow", "Bow_FlightArrow2", "Bow_HeldArrow2"],
        "extra_blends": [
            {
                "blend": r"动画\H04_Thorn_Arrows\H04_Tripo_Thorn_Arrows.blend",
                "actions": {
                    "HeroSkillA": "H04_Tripo_01_Single",
                    "HeroRelease": "H04_Tripo_02_Double",
                },
            }
        ],
    },
    "H05": {
        "name": "赫铎",
        "output": "H05_Runtime.glb",
        "base_blend": r"TwoHand_Attacks_v2\H05_Meshy\H05_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H05_Meshy_05_GuardHold",
            "HeroWalk-loop": "H05_Meshy_02_Walk",
            "HeroStop": "H05_Meshy_08_WalkStop",
            "HeroAttack": "H05_Meshy_04_LowCut",
            "HeroHit": "H05_Meshy_13_HitLight",
            "HeroDown": "H05_Meshy_06_Down",
            "HeroBlock": "H05_Meshy_21_BlockImpact",
        },
        "extra_blends": [
            {
                "blend": r"动画\Heduo_Cleaver_Actions\H05_Meshy_Cleaver_Actions.blend",
                "actions": {
                    "HeroSkillA": "H05_Meshy_01_BreakEdge",
                    "HeroRelease": "H05_Meshy_02_ForgedStance",
                    "HeroCancel": "H05_Meshy_03_WindupCancel",
                },
            }
        ],
    },
    "H06": {
        "name": "赛琳",
        "output": "H06_Runtime.glb",
        "base_blend": r"动画\棋盘视角复验_20261120\H06_Meshy\H06_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H06_Meshy_01_Idle",
            "HeroWalk-loop": "H06_Meshy_23_ReadyAdvance",
            "HeroStop": "H06_Meshy_08_WalkStop",
            "HeroAttack": "H06_Meshy_04_Attack",
            "HeroHit": "H06_Meshy_13_HitLight",
            "HeroDown": "H06_Meshy_06_Down",
            "HeroSkillA": "H06_Meshy_21_Thrust",
        },
        "extra_blends": [
            {
                "blend": r"动画\Staff_Cast_Transitions\H06_Meshy\H06_Meshy_Cast_Transitions.blend",
                "actions": {
                    "HeroRaise": "H06_Meshy_01_Prepare",
                    "HeroHold-loop": "H06_Meshy_02_CastHold",
                    "HeroRelease": "H06_Meshy_03_Release",
                    "HeroCancel": "H06_Meshy_04_Cancel",
                },
            }
        ],
    },
    "H07": {
        "name": "陆衡",
        "output": "H07_Runtime.glb",
        "base_blend": r"TwoHand_Attacks_v2\H07_Tripo\H07_Tripo_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H07_Tripo_05_GuardHold",
            "HeroWalk-loop": "H07_Tripo_02_Walk",
            "HeroStop": "H07_Tripo_08_WalkStop",
            "HeroAttack": "H07_Tripo_04_LowCut",
            "HeroHit": "H07_Tripo_13_HitLight",
            "HeroDown": "H07_Tripo_06_Down",
            "HeroBlock": "H07_Tripo_21_BlockImpact",
        },
        "extra_blends": [
            {
                "blend": r"动画\Luheng_Command_Actions\H07_Tripo_Command_Actions.blend",
                "actions": {
                    "HeroSkillA": "H07_Tripo_01_FocusMark",
                    "HeroRelease": "H07_Tripo_02_VolleyOrder",
                    "HeroCancel": "H07_Tripo_03_CommandCancel",
                },
            }
        ],
    },
    "H09": {
        "name": "闻笺",
        "output": "H09_Runtime.glb",
        "base_blend": r"Paper_LoL_Keyframe_Actions\H09_Meshy\H09_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H09_Meshy_01_Idle",
            "HeroWalk-loop": "H09_Meshy_02_Walk",
            "HeroStop": "H09_Meshy_08_WalkStop",
            "HeroAttack": "H09_Meshy_04_Attack",
            "HeroHit": "H09_Meshy_13_HitLight",
            "HeroDown": "H09_Meshy_06_Down",
        },
        "extra_blends": [
            {
                "blend": r"Paper_Motion_v2\H09_Meshy\H09_Meshy_Natural_Actions.blend",
                "actions": {
                    "HeroIdle-loop": "H09_Meshy_01_Idle",
                    "HeroWalk-loop": "H09_Meshy_02_Walk",
                    "HeroAttack": "H09_Meshy_04_Attack",
                },
            },
            {
                "blend": r"动画\H09_Folio_Skills\H09_Meshy_Folio_Skills.blend",
                "actions": {
                    "HeroRaise": "H09_Meshy_01_FolioReady",
                    "HeroHold-loop": "H09_Meshy_02_FolioHold",
                    "HeroSkillA": "H09_Meshy_03_PairedSeal",
                    "HeroRelease": "H09_Meshy_04_CovenantStrike",
                    "HeroCancel": "H09_Meshy_05_FolioCancel",
                },
            },
        ],
    },
    "H10": {
        "name": "阮钧",
        "output": "H10_Runtime.glb",
        "base_blend": r"动画\动作质检修正_20261120\H10_Meshy\H10_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H10_Meshy_01_Idle",
            "HeroWalk-loop": "H10_Meshy_23_ReadyAdvance",
            "HeroStop": "H10_Meshy_08_WalkStop",
            "HeroAttack": "H10_Meshy_04_Attack",
            "HeroHit": "H10_Meshy_13_HitLight",
            "HeroDown": "H10_Meshy_06_Down",
        },
        "extra_blends": [
            {
                "blend": r"动画\动作质检修正_20261120\H10_专属\H10_Meshy_Hammer_Actions.blend",
                "actions": {
                    "HeroSkillA": "H10_Meshy_01_GroundSlam",
                    "HeroRelease": "H10_Meshy_02_StopCast",
                    "HeroCancel": "H10_Meshy_03_HammerCancel",
                },
            }
        ],
    },
    "H11": {
        "name": "祁岚",
        "output": "H11_Runtime.glb",
        "base_blend": r"Dagger_Attack_v3\H11_Meshy\H11_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H11_Meshy_05_GuardHold",
            "HeroWalk-loop": "H11_Meshy_02_Walk",
            "HeroStop": "H11_Meshy_08_WalkStop",
            "HeroAttack": "H11_Meshy_04_LowCut",
            "HeroHit": "H11_Meshy_13_HitLight",
            "HeroDown": "H11_Meshy_06_Down",
            "HeroBlock": "H11_Meshy_21_BlockImpact",
        },
        "extra_blends": [
            {
                "blend": r"动画\动作质检修正_20261120\H11_Meshy\H11_Meshy_Shadow_and_Flying_Blade.blend",
                "actions": {
                    "HeroRaise": "H11_Meshy_01_ShadowEnter",
                    "HeroSkillA": "H11_Meshy_02_ShadowStrike",
                    "HeroCancel": "H11_Meshy_03_ShadowAbort",
                    "HeroRelease": "H11_Meshy_04_FlyingBlade",
                    "HeroHold-loop": "H11_Meshy_05_BladeWait",
                },
            }
        ],
    },
    "H12": {
        "name": "殷砚",
        "output": "H12_Runtime.glb",
        "base_blend": r"动画\棋盘视角复验_20261120\H12_Meshy\H12_Meshy_24_Keyframe_Actions.blend",
        "base_actions": {
            "HeroIdle-loop": "H12_Meshy_01_Idle",
            "HeroWalk-loop": "H12_Meshy_23_ReadyAdvance",
            "HeroStop": "H12_Meshy_08_WalkStop",
            "HeroAttack": "H12_Meshy_04_Attack",
            "HeroHit": "H12_Meshy_13_HitLight",
            "HeroDown": "H12_Meshy_06_Down",
        },
        "extra_blends": [
            {
                "blend": r"动画\Staff_Cast_Transitions\H12_Meshy\H12_Meshy_Cast_Transitions.blend",
                "actions": {
                    "HeroRaise": "H12_Meshy_01_Prepare",
                    "HeroHold-loop": "H12_Meshy_02_CastHold",
                    "HeroSkillA": "H12_Meshy_03_Release",
                    "HeroCancel": "H12_Meshy_04_Cancel",
                },
            },
            {
                "blend": r"动画\H12_Meteor_Rain\H12_Meshy_Meteor_Rain.blend",
                "actions": {
                    "HeroRelease": "H12_Meshy_Meteor_06_W2_Cast",
                },
            },
        ],
    },
}


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--heroes", nargs="+", default=["H08"])
    parser.add_argument("--report", default="")
    return parser.parse_args(argv)


def _find_armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and "Root" in obj.data.bones:
            return obj
    return next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)


def _collect_export_objects(armature, exclude_meshes):
    excluded = set(exclude_meshes or [])
    result = [armature]
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.name in excluded:
            continue
        if "Floor" in obj.name or "Icosphere" in obj.name:
            continue
        is_bound = obj.parent == armature or any(
            m.type == "ARMATURE" and m.object == armature for m in obj.modifiers
        )
        if is_bound:
            result.append(obj)
    return result


def _strip_object_actions(armature):
    if armature.animation_data is None:
        armature.animation_data_create()
    ad = armature.animation_data
    ad.action = None
    while ad.nla_tracks:
        ad.nla_tracks.remove(ad.nla_tracks[0])


def _append_actions(blend_copy_path, action_map):
    wanted = list(action_map.values())
    with bpy.data.libraries.load(blend_copy_path, link=False) as (data_from, data_to):
        missing = [a for a in wanted if a not in data_from.actions]
        if missing:
            raise RuntimeError(f"Missing actions in {blend_copy_path}: {missing}")
        data_to.actions = list(wanted)
    loaded_by_src = dict(zip(wanted, data_to.actions))
    return {dst: loaded_by_src[src] for dst, src in action_map.items()}


def export_hero(hero_id, recipe, assets_root, out_dir):
    with tempfile.TemporaryDirectory(prefix=f"p06_{hero_id}_") as tmp:
        src_base = os.path.join(assets_root, recipe["base_blend"])
        if not os.path.exists(src_base):
            raise FileNotFoundError(f"{hero_id} base blend missing: {src_base}")
        work_base = os.path.join(tmp, os.path.basename(src_base))
        shutil.copy2(src_base, work_base)

        bpy.ops.wm.open_mainfile(filepath=work_base)
        arm = _find_armature()
        if arm is None:
            raise RuntimeError(f"{hero_id}: no armature found")

        resolved = {}
        for dst, src in recipe["base_actions"].items():
            act = bpy.data.actions.get(src)
            if act is None:
                available = sorted(a.name for a in bpy.data.actions)
                raise RuntimeError(f"{hero_id}: missing base action '{src}'. Available: {available}")
            resolved[dst] = act

        for extra in recipe.get("extra_blends", []):
            src_extra = os.path.join(assets_root, extra["blend"])
            if not os.path.exists(src_extra):
                raise FileNotFoundError(f"{hero_id} extra blend missing: {src_extra}")
            work_extra = os.path.join(tmp, os.path.basename(src_extra))
            shutil.copy2(src_extra, work_extra)
            resolved.update(_append_actions(work_extra, extra["actions"]))

        # Rename selected actions cleanly and mount as NLA strips on the hero armature.
        _strip_object_actions(arm)
        used_actions = set()
        for dst, act in resolved.items():
            # Duplicate if the same source action is mapped twice
            if act in used_actions:
                act = act.copy()
            used_actions.add(act)
            act.name = dst
            act.use_fake_user = True
            f0 = act.frame_range[0]
            if abs(f0) > 1e-4:
                if hasattr(act, "layers") and act.layers:
                    for layer in act.layers:
                        for strip_l in layer.strips:
                            for bag in strip_l.channelbags:
                                for fc in bag.fcurves:
                                    for kp in fc.keyframe_points:
                                        kp.co.x -= f0
                                        kp.handle_left.x -= f0
                                        kp.handle_right.x -= f0
                                    fc.update()
                elif hasattr(act, "fcurves"):
                    for fc in act.fcurves:
                        for kp in fc.keyframe_points:
                            kp.co.x -= f0
                            kp.handle_left.x -= f0
                            kp.handle_right.x -= f0
                        fc.update()
            track = arm.animation_data.nla_tracks.new()
            track.name = dst
            strip = track.strips.new(dst, 0, act)
            strip.name = dst

        # Remove unused actions so glTF exporter only emits intended clips.
        for act in list(bpy.data.actions):
            if act not in used_actions:
                bpy.data.actions.remove(act, do_unlink=True)

        # Select only armature and its bound meshes.
        export_objs = _collect_export_objects(arm, recipe.get("exclude_meshes"))
        bpy.ops.object.select_all(action="DESELECT")
        for obj in export_objs:
            obj.hide_viewport = False
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active = arm

        # Ensure generated/unpacked images have valid pixel data before glTF export.
        for img in bpy.data.images:
            if img.size[0] > 0 and img.packed_file is None and not img.filepath:
                img.pack()
        img_format = "AUTO" if any(img.channels == 4 and img.name != "BaseColor_2K" for img in bpy.data.images) else "JPEG"

        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, recipe["output"])
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format="GLB",
            use_selection=True,
            export_yup=True,
            export_apply=False,
            export_skins=True,
            export_animations=True,
            export_animation_mode="NLA_TRACKS",
            export_nla_strips=True,
            export_optimize_animation_size=True,
            export_materials="EXPORT",
            export_image_format=img_format,
            export_image_quality=85,
            export_lights=False,
            export_cameras=False,
        )

    # Re-import into a blank scene to verify clips, frame ranges, rig, and materials.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=out_path)
    imp_arm = _find_armature()
    if imp_arm is None or "Root" not in imp_arm.data.bones:
        raise RuntimeError(f"{hero_id}: re-import verification failed (missing armature/Root)")
    imp_meshes = [o for o in bpy.data.objects if o.type == "MESH" and "Icosphere" not in o.name]
    total_polys = sum(len(o.data.polygons) for o in imp_meshes)
    materials = sorted({m.name for o in imp_meshes for m in o.data.materials if m})
    images = [(img.name, list(img.size)) for img in bpy.data.images]
    clips = {}
    for act in sorted(bpy.data.actions, key=lambda a: a.name):
        f0, f1 = act.frame_range
        clips[act.name] = [round(f0, 2), round(f1, 2)]
    expected = set(recipe["base_actions"].keys())
    for extra in recipe.get("extra_blends", []):
        expected.update(extra["actions"].keys())
    missing_clips = sorted(expected - set(clips.keys()))
    if missing_clips:
        raise RuntimeError(f"{hero_id}: re-import missing clips {missing_clips}; got {sorted(clips.keys())}")
    size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
    info = {
        "hero_id": hero_id,
        "name": recipe["name"],
        "output": out_path,
        "size_mb": size_mb,
        "bones": len(imp_arm.data.bones),
        "meshes": [o.name for o in imp_meshes],
        "polys": total_polys,
        "materials": materials,
        "images": images,
        "clips": clips,
    }
    print(f"[OK] {hero_id} ({recipe['name']}): {size_mb} MB, {total_polys} polys, {len(clips)} clips -> {out_path}")
    for cname, crange in clips.items():
        print(f"     clip {cname:20s} {crange}")
    return info


def main():
    args = _parse_args()
    heroes = list(HERO_RECIPES.keys()) if "ALL" in args.heroes else args.heroes
    results = []
    for hid in heroes:
        if hid not in HERO_RECIPES:
            raise KeyError(f"Unknown hero id: {hid}")
        results.append(export_hero(hid, HERO_RECIPES[hid], args.assets_root, args.out_dir))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

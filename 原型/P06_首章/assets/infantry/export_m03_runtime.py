"""Combine P06's intended low-poly M03 base with the authored five-part bolt sequence."""

import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / '原型/P06_首章/assets/infantry')]
from export_s02_runtime import assign, deviation, frame_set, live_geometry, rest_vertex_match, retime

BASE = ROOT / '设计整理/角色模型_v1/远程武器动作_v9/M03_Meshy/M03_Meshy_ranged.blend'
SKILL = ROOT / '动画/M03_Breach_Bolt'
RIG, BODY, MUZZLE = 'FireseedHumanoid', 'M03_Body', 'BreachMuzzle'
GEAR = ('Combat_crossbow', 'Combat_arrow', 'Combat_flying_arrow', 'Combat_String_0', 'Combat_String_1')
CLIPS = {
    '01_BreachAim': 'BreachAim',
    '02_BreachHold': 'BreachHold-loop',
    '03_BreachRelease': 'BreachRelease',
    '04_BreachCancel': 'BreachCancel',
    '05_SharedReload': 'BreachReload',
}
EXPORT_RATE, SOURCE_RATE = 150, 30
COMPARE_RATE = 150


def scene_open(path):
    bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
    return bpy.context.scene, bpy.data.objects[RIG]


def snapshot(scene, action, rate, ref=False):
    for index in range(round((action.frame_range[1] - action.frame_range[0]) * COMPARE_RATE / rate) + 1):
        frame_set(scene, action.frame_range[0] + index * rate / COMPARE_RATE)
        if ref:
            socket = bpy.data.objects['M03_Breach_Muzzle'].matrix_world.copy()
            yield {name: live_geometry(name) for name in GEAR}, socket.translation, socket.to_3x3().col[2].normalized()
        else:
            yield {name: live_geometry(name) for name in (*GEAR, BODY)}


def authored(manifest):
    scene, rig = scene_open(SKILL / manifest['master'])
    assert scene.render.fps == SOURCE_RATE and not rig.animation_data.nla_tracks
    reference = {}
    for clip in manifest['clips']:
        action = bpy.data.actions[clip['action']]
        name = CLIPS[clip['id']]
        assign(rig, action)
        reference[name] = list(snapshot(scene, action, SOURCE_RATE, True))
    return reference, {name: live_geometry(name, topology=True) for name in GEAR}


def attach_marker(rig, layout):
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    parent = rig.data.edit_bones[layout['bone']]
    marker = rig.data.edit_bones.new(MUZZLE)
    point = Vector(layout['point_in_bone'])
    axis = Vector(layout['axis_in_bone']).normalized()
    marker.head = parent.matrix @ point
    marker.tail = parent.matrix @ (point + axis * .04)
    marker.parent = parent
    marker.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')


def encode(path, manifest, reference, rest_equipment):
    scene, rig = scene_open(BASE)
    assert scene.render.fps == EXPORT_RATE and not rig.animation_data.nla_tracks
    meshes = {name: live_geometry(name, topology=True) for name in (*GEAR, BODY)}
    gear_lookup = {name: rest_vertex_match(rest_equipment[name][0], meshes[name][0]) for name in GEAR}
    assert all(len(meshes[name][1]) == len(rest_equipment[name][1]) for name in GEAR)
    base_names = {action.name for action in bpy.data.actions}
    with bpy.data.libraries.load(str(SKILL / manifest['master']), link=False) as (_, destination):
        destination.actions = [row['action'] for row in manifest['clips']]
    before_export, gear_source_peak = {}, 0.0
    for clip, action in zip(manifest['clips'], destination.actions):
        length = action.frame_range[1] - 1
        retime(action, EXPORT_RATE / SOURCE_RATE)
        action.frame_start, action.frame_end = 1, 1 + length * EXPORT_RATE / SOURCE_RATE
        action.name = CLIPS[clip['id']]
        assign(rig, action)
        poses = list(snapshot(scene, action, EXPORT_RATE))
        assert len(poses) == len(reference[action.name])
        for current, (source, _, _) in zip(poses, reference[action.name]):
            gear_source_peak = max(gear_source_peak, *(deviation(current[n], source[n], gear_lookup[n]) for n in GEAR))
        before_export[action.name] = poses
    assert gear_source_peak < .0002, gear_source_peak
    attach_marker(rig, manifest['muzzle'])
    assign(rig, bpy.data.actions['RangedGuard-loop'])
    frame_set(scene, 1)
    bpy.ops.object.select_all(action='DESELECT')
    for name in (RIG, BODY, *GEAR):
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True, export_apply=False,
        export_animations=True, export_animation_mode='ACTIONS', export_merge_animation='ACTION',
        export_force_sampling=True, export_frame_step=1, export_frame_range=False, export_anim_slide_to_zero=True,
        export_all_influences=False, export_cameras=False, export_lights=False, export_yup=True,
    ) == {'FINISHED'}
    return meshes, base_names, before_export, float(gear_source_peak)


def verify(path, ref, meshes, base, before_export):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = EXPORT_RATE
    assert bpy.ops.import_scene.gltf(filepath=str(path)) == {'FINISHED'}
    rig = bpy.data.objects[RIG]
    marker = rig.pose.bones[MUZZLE]
    assert marker.parent.name == 'Weapon'
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    lookup, triangles = {}, {}
    for name, (original, original_faces) in meshes.items():
        imported, faces = live_geometry(name, topology=True)
        assert len(faces) == len(original_faces)
        lookup[name] = rest_vertex_match(original, imported)
        triangles[name] = len(faces)
    assert {a.name for a in bpy.data.actions} == base | set(before_export)
    results = {}
    for name, poses in before_export.items():
        action = bpy.data.actions[name]
        assign(rig, action)
        peaks = {mesh: 0.0 for mesh in lookup}
        peak_origin = 0.0
        min_dot = 1.0
        for i, (row, (_, target, direction)) in enumerate(zip(poses, ref[name])):
            frame_set(scene, action.frame_range[0] + i * EXPORT_RATE / COMPARE_RATE)
            for mesh in lookup:
                error = deviation(live_geometry(mesh), row[mesh], lookup[mesh])
                peaks[mesh] = max(peaks[mesh], error)
            point = rig.matrix_world @ marker.head
            axis = (rig.matrix_world.to_3x3() @ (marker.tail - marker.head)).normalized()
            peak_origin = max(peak_origin, (point - target).length)
            min_dot = min(min_dot, axis.dot(direction))
        assert max(peaks.values()) < .0015 and peak_origin < .0003 and min_dot > .9999, (name, peaks, peak_origin, min_dot)
        results[name] = {'mesh_roundtrip_max_m': peaks, 'muzzle_max_m': peak_origin,
                         'min_muzzle_axis_dot': min_dot, 'samples': len(poses)}
    return {'clips': results, 'triangles': triangles, 'base_clips': sorted(base)}


def main():
    output, evidence = map(Path, sys.argv[sys.argv.index('--') + 1:])
    manifest = json.loads((SKILL / 'manifest.json').read_text(encoding='utf-8'))
    refs, source_meshes = authored(manifest)
    meshes, existing, poses, equipment_error = encode(output, manifest, refs, source_meshes)
    proof = verify(output, refs, meshes, existing, poses)
    proof.update(passed=True, export_hz=EXPORT_RATE, compare_hz=COMPARE_RATE, gear_vs_source_max_m=equipment_error,
                 sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    evidence.write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""Export authored M02 clips and verify the skinned body and injector after GLB import."""

import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_s02_runtime import (
    LinearSkin, add_shapes, assign, deviation, fit_shapes, frame_set, live_geometry, rest_vertex_match,
)

ROOT = Path.cwd()
MASTER = ROOT / 'Apothecary_LoL_Keyframe_Actions/M02_Tripo'
SOURCE = MASTER / 'M02_Tripo_24_Keyframe_Actions.blend'
RIG, BODY, GEAR, MUZZLE = 'FireseedHumanoid', 'M02_Tripo_Body', 'MedicineInjector', 'AidMuzzle'
SOURCE_RATE, EXPORT_RATE = 30, 60
RELEASE_FRAME = 24
CLIPS = {
    '01_Idle': 'AidIdle-loop',
    '02_Walk': 'AidWalk-loop',
    '04_Attack': 'AidFire',
    '05_ReadyHold': 'AidHold-loop',
    '06_Down': 'AidDown',
    '08_WalkStop': 'AidStop',
    '13_HitLight': 'AidHit',
    '17_RaiseReady': 'AidRaise',
    '18_CancelReady': 'AidCancel',
}


def fit_timeline(action):
    ratio = EXPORT_RATE / SOURCE_RATE
    end = action.frame_range[1]
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        time, left, right = key.co.x, key.handle_left.x, key.handle_right.x
                        key.co.x = 1 + (time - 1) * ratio
                        key.handle_left.x = 1 + (left - 1) * ratio
                        key.handle_right.x = 1 + (right - 1) * ratio
                    curve.update()
    action.frame_start, action.frame_end = 1, 1 + (end - 1) * ratio


def add_muzzle(rig, position, axis):
    to_rig = rig.matrix_world.inverted()
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    marker = rig.data.edit_bones.new(MUZZLE)
    marker.head = to_rig @ position
    marker.tail = to_rig @ (position + axis * .035)
    marker.parent = rig.data.edit_bones['RightHand']
    marker.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')


def capture(rig, body, clips, rest, nozzle, axis):
    scene = bpy.context.scene
    skin = LinearSkin(rig, body, rest)
    hand_bind = rig.data.bones['RightHand'].matrix_local.inverted()
    samples, residuals = {}, []
    for action in clips:
        assign(rig, action)
        assert action.frame_range[0] == 1
        count = int((action.frame_range[1] - 1) * EXPORT_RATE / SOURCE_RATE) + 1
        poses = []
        for index in range(count):
            frame_set(scene, 1 + index * SOURCE_RATE / EXPORT_RATE)
            body_points, gear_points = live_geometry(BODY), live_geometry(GEAR)
            hand = rig.matrix_world @ rig.pose.bones['RightHand'].matrix @ hand_bind
            poses.append((body_points, gear_points, hand @ nozzle, (hand.to_3x3() @ axis).normalized()))
            residuals.append(skin.residual(body_points))
        samples[action.name] = poses
    return samples, np.asarray(residuals)


def export(path):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
    scene = bpy.context.scene
    rig, body = bpy.data.objects[RIG], bpy.data.objects[BODY]
    assert scene.render.fps == SOURCE_RATE and scene.render.fps_base == 1.0
    assert not rig.animation_data.nla_tracks
    assert not body.data.shape_keys
    original = {name: live_geometry(name, topology=True) for name in (BODY, GEAR)}
    rest = np.array([v.co[:] for v in body.data.vertices], dtype=np.float32)
    mount = json.loads((MASTER / 'injector_mount.json').read_text(encoding='utf-8'))
    assert mount['bone'] == 'RightHand'
    axis = Vector(mount['axis']).normalized()
    nozzle = Vector(mount['rest_grip']) + axis * .15
    clips = [bpy.data.actions['M02_Tripo_' + name] for name in CLIPS]
    for action in list(bpy.data.actions):
        if action not in clips:
            bpy.data.actions.remove(action)
    for action, name in zip(clips, CLIPS.values()):
        action.name = name
    samples, residuals = capture(rig, body, clips, rest, nozzle, axis)
    add_muzzle(rig, nozzle, axis)
    directions, weights, error = fit_shapes(rest, residuals, 'Aid')
    body.modifiers['Armature'].use_deform_preserve_volume = False
    scene.render.fps = EXPORT_RATE
    for action in clips:
        fit_timeline(action)
    add_shapes(body, rest, directions, weights, clips, samples, label='Aid', frame_step=1.0)
    assign(rig, clips[0])
    frame_set(scene, 1)
    bpy.ops.object.select_all(action='DESELECT')
    for name in (RIG, BODY, GEAR):
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True, export_apply=False,
        export_animations=True, export_animation_mode='ACTIONS', export_merge_animation='ACTION',
        export_force_sampling=True, export_frame_step=1, export_frame_range=False, export_anim_slide_to_zero=True,
        export_morph=True, export_morph_animation=True, export_morph_normal=False,
        export_all_influences=False, export_cameras=False, export_lights=False, export_yup=True,
    ) == {'FINISHED'}
    return samples, original, {'rank': len(directions), 'fit_error_m': error}


def verify(path, samples, original):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = EXPORT_RATE
    assert bpy.ops.import_scene.gltf(filepath=str(path)) == {'FINISHED'}
    rig = bpy.data.objects[RIG]
    muzzle = rig.pose.bones[MUZZLE]
    assert muzzle.parent.name == 'RightHand'
    body = next(o for o in scene.objects if o.type == 'MESH' and o.data.shape_keys)
    names = {BODY: body.name, GEAR: GEAR}
    keys = body.data.shape_keys
    for key in keys.key_blocks[1:]:
        key.slider_min, key.slider_max = -1.1, 1.1
    for owner in (rig, keys):
        driver = owner.animation_data_create()
        driver.action = None
        for track in driver.nla_tracks:
            track.mute = True
    counts, lookup = {}, {}
    for name, (vertices, triangles) in original.items():
        imported, faces = live_geometry(names[name], topology=True)
        assert len(triangles) == len(faces)
        counts[name] = len(faces)
        lookup[name] = rest_vertex_match(vertices, imported)
    assert set(a.name for a in bpy.data.actions) == set(CLIPS.values())
    proof = {}
    for name, poses in samples.items():
        action = bpy.data.actions[name]
        assign(rig, action)
        assign(keys, action, 'KEY')
        start = action.frame_range[0]
        peaks = {BODY: 0.0, GEAR: 0.0, MUZZLE: 0.0}
        min_axis_dot = 1.0
        for index, (source_body, source_gear, point, axis) in enumerate(poses):
            frame_set(scene, start + index)
            for item, expected in [(BODY, source_body), (GEAR, source_gear)]:
                peaks[item] = max(peaks[item], deviation(live_geometry(names[item]), expected, lookup[item]))
            actual = rig.matrix_world @ muzzle.head
            direction = (rig.matrix_world.to_3x3() @ (muzzle.tail - muzzle.head)).normalized()
            peaks[MUZZLE] = max(peaks[MUZZLE], (actual - point).length)
            min_axis_dot = min(min_axis_dot, direction.dot(axis))
        assert peaks[BODY] < .003 and peaks[GEAR] < .0002 and peaks[MUZZLE] < .0002, (name, peaks)
        assert min_axis_dot > .9999, (name, min_axis_dot)
        proof[name] = {'peak_error_m': peaks, 'min_muzzle_axis_dot': min_axis_dot, 'frames': len(poses)}
    _, _, launch, direction = samples['AidFire'][(RELEASE_FRAME - 1) * EXPORT_RATE // SOURCE_RATE]
    manifest = json.loads((ROOT / 'Apothecary_Equipment_v2/manifest.json').read_text(encoding='utf-8'))
    aid = next(row for row in manifest if row['id'] == '04_Aid')
    assert aid['release'] == RELEASE_FRAME and aid['flight'] == 8
    assert (launch - Vector(aid['muzzle_at_release'])).length < .0001
    assert direction.dot(Vector(aid['axis_at_release'])) > .9999
    return {'clips': proof, 'triangles': counts, 'release_frame': RELEASE_FRAME, 'flight_frames': aid['flight']}


def main():
    path, report_path = map(Path, sys.argv[sys.argv.index('--') + 1:])
    samples, original, fit = export(path)
    report = verify(path, samples, original)
    report.update(passed=True, sample_hz=EXPORT_RATE, correctives=fit, bytes=path.stat().st_size,
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""Export the palm caster's board clips and its authored four-part mist cast."""

import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np


ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / '原型/P06_首章/assets/infantry'))
from export_m02_runtime import fit_timeline
from export_s02_runtime import (
    LinearSkin, add_shapes, assign, deviation, fit_shapes, frame_set, live_geometry, rest_vertex_match,
)

BASE = ROOT / 'Palm_Arm_Fix_v3/M04_Meshy/M04_Meshy_24_Keyframe_Actions.blend'
SKILL = ROOT / '动画/M04_Mist_Cast'
RIG, BODY, PALM = 'FireseedHumanoid', 'M04_Body', 'MistPalm'
SOURCE_RATE, EXPORT_RATE = 30, 60
BASIC_CLIPS = {
    '01_Idle': 'MistIdle-loop',
    '02_Walk': 'MistWalk-loop',
    '04_Attack': 'MistAttack',
    '06_Down': 'MistDown',
    '08_WalkStop': 'MistStop',
    '13_HitLight': 'MistHit',
}
SKILL_CLIPS = {
    '01_RaisePalm': 'MistRaise',
    '02_AimHold': 'MistHold-loop',
    '03_MistRelease': 'MistRelease',
    '04_MistCancel': 'MistCancel',
}


def add_socket(rig, socket):
    assert socket['axis'] == '+Z' and socket['bone'] == 'RightHand'
    point = Vector(socket['origin_in_bone'])
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    marker = rig.data.edit_bones.new(PALM)
    hand = rig.data.edit_bones['RightHand']
    marker.head = hand.matrix @ point
    marker.tail = hand.matrix @ (point + Vector((0, 0, .035)))
    marker.parent = hand
    marker.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')


def export(path, manifest):
    bpy.ops.wm.open_mainfile(filepath=str(BASE), use_scripts=False)
    scene = bpy.context.scene
    rig, body = bpy.data.objects[RIG], bpy.data.objects[BODY]
    assert scene.render.fps == SOURCE_RATE and scene.render.fps_base == 1.0
    assert not rig.animation_data.nla_tracks and not body.data.shape_keys
    vertices, triangles = live_geometry(BODY, topology=True)
    rest = np.array([vertex.co[:] for vertex in body.data.vertices], dtype=np.float32)
    basic_actions = [bpy.data.actions['M04_Meshy_' + name] for name in BASIC_CLIPS]
    for action in list(bpy.data.actions):
        if action not in basic_actions:
            bpy.data.actions.remove(action)
    with bpy.data.libraries.load(str(SKILL / manifest['master']), link=False) as (_, destination):
        destination.actions = [row['action'] for row in manifest['clips']]
    actions = basic_actions + destination.actions
    for action, name in zip(actions, [*BASIC_CLIPS.values(), *(SKILL_CLIPS[row['id']] for row in manifest['clips'])]):
        action.name = name
    add_socket(rig, manifest['palm_socket'])
    skin = LinearSkin(rig, body, rest)
    expected, residuals = {}, []
    for action in actions:
        assign(rig, action)
        assert action.frame_range[0] == 1
        poses = []
        for i in range(int((action.frame_range[1] - 1) * EXPORT_RATE / SOURCE_RATE) + 1):
            frame_set(scene, 1 + i * SOURCE_RATE / EXPORT_RATE)
            body_points = live_geometry(BODY)
            marker = rig.pose.bones[PALM]
            origin = rig.matrix_world @ marker.head
            axis = (rig.matrix_world.to_3x3() @ (marker.tail - marker.head)).normalized()
            poses.append((body_points, origin, axis))
            residuals.append(skin.residual(body_points))
        expected[action.name] = poses
    directions, weights, error = fit_shapes(rest, np.asarray(residuals), 'Mist')
    body.modifiers['Armature'].use_deform_preserve_volume = False
    scene.render.fps = EXPORT_RATE
    for action in actions:
        fit_timeline(action)
    add_shapes(body, rest, directions, weights, actions, expected, label='Mist', frame_step=1.0)
    assign(rig, actions[0])
    frame_set(scene, 1)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True, export_apply=False,
        export_animations=True, export_animation_mode='ACTIONS', export_merge_animation='ACTION',
        export_force_sampling=True, export_frame_step=1, export_frame_range=False, export_anim_slide_to_zero=True,
        export_morph=True, export_morph_animation=True, export_morph_normal=False,
        export_all_influences=False, export_cameras=False, export_lights=False, export_yup=True,
    ) == {'FINISHED'}
    return expected, vertices, len(triangles), {'rank': len(directions), 'fit_error_m': error}


def verify(path, expected, vertices, triangle_count):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = EXPORT_RATE
    bpy.ops.import_scene.gltf(filepath=str(path))
    rig = bpy.data.objects[RIG]
    marker = rig.pose.bones[PALM]
    assert marker.parent.name == 'RightHand'
    mesh = next(obj for obj in scene.objects if obj.type == 'MESH' and obj.data.shape_keys)
    keys = mesh.data.shape_keys
    for key in keys.key_blocks[1:]:
        key.slider_min, key.slider_max = -1.1, 1.1
    for owner in (rig, keys):
        data = owner.animation_data
        data.action = None
        for track in data.nla_tracks:
            track.mute = True
    points, triangles = live_geometry(mesh.name, topology=True)
    assert len(triangles) == triangle_count and set(expected) == {a.name for a in bpy.data.actions}
    lookup = rest_vertex_match(vertices, points)
    results = {}
    for name, poses in expected.items():
        action = bpy.data.actions[name]
        assign(rig, action)
        assign(keys, action, 'KEY')
        body_peak, palm_peak, axis_dot = 0., 0., 1.
        for i, (body, palm, axis) in enumerate(poses):
            frame_set(scene, action.frame_range[0] + i)
            body_peak = max(body_peak, deviation(live_geometry(mesh.name), body, lookup))
            actual = rig.matrix_world @ marker.head
            palm_peak = max(palm_peak, (palm - actual).length)
            direction = (rig.matrix_world.to_3x3() @ (marker.tail - marker.head)).normalized()
            axis_dot = min(axis_dot, direction.dot(axis))
        assert body_peak < .003 and palm_peak < .0002 and axis_dot > .9999, (name, body_peak, palm_peak, axis_dot)
        results[name] = {'body_max_m': body_peak, 'palm_max_m': palm_peak, 'min_axis_dot': axis_dot, 'samples': len(poses)}
    return results


def main():
    path, proof = map(Path, sys.argv[sys.argv.index('--') + 1:])
    manifest = json.loads((SKILL / 'manifest.json').read_text(encoding='utf-8'))
    expected, verts, triangles, fit = export(path, manifest)
    results = verify(path, expected, verts, triangles)
    event_frame = manifest['palm_socket']['event_frame']
    assert event_frame == 13
    release = expected['MistRelease'][(event_frame - 1) * EXPORT_RATE // SOURCE_RATE]
    proof.write_text(json.dumps({'passed': True, 'clips': results, 'correctives': fit, 'triangles': triangles,
        'release_frame': event_frame, 'palm_at_release': list(release[1]), 'axis_at_release': list(release[2]),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

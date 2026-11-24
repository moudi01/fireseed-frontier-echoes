"""Build and verify a Godot asset with the P06 melee library and the authored S02-A clips."""

import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path.cwd()
BASE = ROOT / '设计整理/角色模型_v1/近战短动作_v8/S02-M_Tripo/S02-M_Tripo_melee.blend'
SKILL = ROOT / '动画/S02_Gap_Strike/S02-M_Tripo_Gap_Strike.blend'
RIG, BODY, SWORD = 'FireseedHumanoid', 'S02-M_Body', 'Combat_sword'
SOURCE_FPS = 30
EXPORT_FPS = 150
COMPARE_FPS = 150
CLIPS = {
    'S02-M_Tripo_01_FindOpening': 'GapSet',
    'S02-M_Tripo_02_OpeningHold': 'GapHold-loop',
    'S02-M_Tripo_03_GapStrike': 'GapStrike',
    'S02-M_Tripo_04_Abort': 'GapAbort',
}
sys.path.insert(0, str(ROOT / '动画/战斗接入准备'))
from export_spear import LinearSkin, deviation, frame_set, live_geometry, rest_vertex_match, retime


def open_blend(path):
    bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
    return bpy.context.scene, bpy.data.objects[RIG], bpy.data.objects[BODY]


def assign(id_block, action, target='OBJECT'):
    driver = id_block.animation_data_create()
    driver.action = action
    driver.action_slot = next(slot for slot in action.slots if slot.target_id_type == target)


def capture():
    scene, rig, _ = open_blend(SKILL)
    assert scene.render.fps == SOURCE_FPS
    assert not rig.animation_data.nla_tracks
    poses = {}
    for source, name in CLIPS.items():
        action = bpy.data.actions[source]
        start, end = action.frame_range
        assert start == 1
        assign(rig, action)
        count = round((end - start) * COMPARE_FPS / SOURCE_FPS) + 1
        frames = []
        for index in range(count):
            frame_set(scene, 1 + index * SOURCE_FPS / COMPARE_FPS)
            frames.append({key: live_geometry(key) for key in (BODY, SWORD)})
        poses[name] = frames
    return poses


def base_geometry():
    return {name: live_geometry(name, topology=True) for name in (BODY, SWORD)}


def collect_residuals(scene, rig, body, actions, poses):
    rest = np.array([v.co[:] for v in body.data.vertices], dtype=np.float32)
    skin = LinearSkin(rig, body, rest)
    residuals = []
    sword_error = 0.0
    for action in actions:
        assign(rig, action)
        for i, source in enumerate(poses[action.name]):
            frame_set(scene, 1 + i * EXPORT_FPS / COMPARE_FPS)
            residuals.append(skin.residual(source[BODY]))
            error = np.linalg.norm(live_geometry(SWORD) - source[SWORD], axis=1).max()
            sword_error = max(sword_error, float(error))
    return rest, np.asarray(residuals), sword_error


def fit_shapes(rest, residuals, label='Gap'):
    residuals = residuals.astype(np.float64)
    values, basis_rows = np.linalg.eigh(residuals @ residuals.T)
    order = np.argsort(values)[::-1]
    basis = (basis_rows[:, order].T @ residuals) / np.sqrt(np.maximum(values[order, None], 1e-12))
    for rank in (12, 18, 24, 32, 48, 64, 96, 128):
        directions = basis[:rank]
        weights = residuals @ directions.T
        error = np.linalg.norm((residuals - weights @ directions).reshape(len(weights), len(rest), 3), axis=2)
        print(label, 'shape fit', rank, float(error.max()), flush=True)
        if float(error.max()) < 0.002:
            scale = np.abs(weights).max(axis=0)
            scale[scale < 1e-12] = 1.0
            return directions * scale[:, None], weights / scale, float(error.max())
    raise ValueError(f'{label} correctives exceeded the deformation fit tolerance')


def add_shapes(body, rest, directions, weights, actions, poses, label='Gap', frame_step=EXPORT_FPS / COMPARE_FPS):
    body.shape_key_add(name='Basis')
    for index, direction in enumerate(directions, 1):
        key = body.shape_key_add(name=f'{label}Corrective_{index:02}')
        key.data.foreach_set('co', (rest + direction.reshape(-1, 3)).ravel().astype(np.float32))
        key.slider_min, key.slider_max = -1.1, 1.1
    keys = body.data.shape_keys
    driver = keys.animation_data_create()
    consumed = 0
    for action in actions:
        driver.action = action
        slot = action.slots.new('KEY', f'{label}Correctives')
        driver.action_slot = slot
        count = len(poses[action.name])
        for i, row in enumerate(weights[consumed:consumed + count]):
            frame = 1 + i * frame_step
            for key, weight in zip(keys.key_blocks[1:], row):
                key.value = float(weight)
                key.keyframe_insert('value', frame=frame, group=f'{label} correctives')
        consumed += count
        for curve in action.layers[0].strips[0].channelbag(slot).fcurves:
            for keyframe in curve.keyframe_points:
                keyframe.interpolation = 'LINEAR'
        track = driver.nla_tracks.new()
        track.name, track.mute = action.name, True
        track.strips.new(action.name, 1, action).action_slot = slot
    driver.action = None
    for key in keys.key_blocks[1:]:
        key.value = 0.0


def export(path, poses):
    scene, rig, body = open_blend(BASE)
    assert scene.render.fps == EXPORT_FPS
    original = base_geometry()
    base_clips = sorted(a.name for a in bpy.data.actions)
    with bpy.data.libraries.load(str(SKILL), link=False) as (source, target):
        assert set(CLIPS) <= set(source.actions)
        target.actions = list(CLIPS)
    actions = target.actions
    for action in actions:
        name = CLIPS[action.name]
        old_end = action.frame_range[1]
        retime(action, EXPORT_FPS / SOURCE_FPS)
        action.frame_end = 1 + (old_end - 1) * EXPORT_FPS / SOURCE_FPS
        action.name = name
    rest, residuals, sword_error = collect_residuals(scene, rig, body, actions, poses)
    assert sword_error < .0002, sword_error
    directions, weights, error = fit_shapes(rest, residuals)
    add_shapes(body, rest, directions, weights, actions, poses)
    assign(rig, bpy.data.actions['MeleeGuard-loop'])
    frame_set(scene, 1)
    bpy.ops.object.select_all(action='DESELECT')
    for name in (RIG, BODY, SWORD):
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True, export_apply=False,
        export_animations=True, export_animation_mode='ACTIONS', export_merge_animation='ACTION',
        export_force_sampling=True, export_frame_step=1, export_frame_range=False, export_anim_slide_to_zero=True,
        export_morph=True, export_morph_animation=True, export_morph_normal=False,
        export_all_influences=False, export_cameras=False, export_lights=False, export_yup=True,
    ) == {'FINISHED'}
    return original, base_clips, {'rank':len(directions),'fit_error_m':error,'baked_gear_error_m':sword_error}


def verify(path, poses, original, base_clips):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = EXPORT_FPS, 1.0
    assert bpy.ops.import_scene.gltf(filepath=str(path)) == {'FINISHED'}
    rig = bpy.data.objects[RIG]
    body = next(o for o in scene.objects if o.type=='MESH' and o.data.shape_keys)
    keys = body.data.shape_keys
    for key in keys.key_blocks[1:]:
        key.slider_min, key.slider_max = -1.1, 1.1
    for owner in (rig, keys):
        driver = owner.animation_data_create()
        driver.action = None
        for track in driver.nla_tracks:
            track.mute = True
    base = base_geometry()
    lookup = {}
    for name in original:
        lookup[name] = rest_vertex_match(original[name][0], base[name][0])
        assert len(original[name][1]) == len(base[name][1])
    assert len(bpy.data.actions)==len(base_clips)+len(poses)
    results = {}
    for name, frames in poses.items():
        action = bpy.data.actions[name]
        assert any(slot.target_id_type=='KEY' for slot in action.slots)
        assign(rig, action)
        assign(keys, action, 'KEY')
        peaks = {key: 0.0 for key in original}
        min_z = float('inf')
        for i, expected in enumerate(frames):
            frame_set(scene, action.frame_range[0] + i * EXPORT_FPS / COMPARE_FPS)
            for item, source in expected.items():
                mesh = live_geometry(item)
                peaks[item] = max(peaks[item], deviation(mesh, source, lookup[item]))
                if item == BODY:
                    min_z = min(min_z, float(mesh[:, 2].min()))
        assert peaks[BODY] <= .003 and peaks[SWORD] <= .002, (name, peaks)
        results[name] = {'peak_surface_error_m':peaks,'min_body_z_m':min_z,'sample_count':len(frames)}
    return {'clips':results,'base_clips':base_clips,'triangles':{n:len(row[1]) for n,row in base.items()}}


def main():
    output, report_path = map(Path, sys.argv[sys.argv.index('--') + 1:])
    poses = capture()
    original, clips, fit = export(output, poses)
    report = verify(output, poses, original, clips)
    report.update(pass_verified=True,bake_hz=EXPORT_FPS,sample_hz=COMPARE_FPS,correctives=fit,
                  sha256=hashlib.sha256(output.read_bytes()).hexdigest(),bytes=output.stat().st_size)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('@@JSON@@', json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

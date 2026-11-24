"""Reduce the checked Ado grip mesh while preserving both hand surfaces."""

import hashlib
import json
from math import radians
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion
from mathutils.kdtree import KDTree


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
SOURCE = HERE / 'MG01_grip.glb'
sys.path.insert(0, str(PROJECT / 'assets/enemies'))
from export_en06_runtime import _error, _surface


HAND_NAMES = {'hand.L', 'hand.R'}
POSES = {
    'rest': {},
    'sweep': {'upper_arm.L': (16, 6, 49), 'forearm.L': (22, 0, 9),
              'upper_arm.R': (33, 36, -17), 'forearm.R': (6, 0, -5), 'chest': (6, 23, -2)},
    'brace': {'upper_arm.L': (53, 4, 34), 'forearm.L': (38, 0, 13),
              'upper_arm.R': (31, 6, -53), 'forearm.R': (29, 0, -17), 'chest': (10, 11, -4)},
    'call': {'upper_arm.L': (13, 4, 59), 'forearm.L': (21, 0, 12),
             'upper_arm.R': (63, 9, -32), 'forearm.R': (13, 0, -9), 'chest': (8, -1, 0)},
}


def _pose(rig, name):
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    for joint, angles in POSES[name].items():
        x, y, z = map(radians, angles)
        rotation = Quaternion((0, 0, 1), y) @ Quaternion((1, 0, 0), x) @ Quaternion((0, -1, 0), z)
        bone = rig.pose.bones[joint]
        reference = bone.bone.matrix_local.to_quaternion()
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = reference.inverted() @ rotation @ reference
    bpy.context.view_layer.update()


def _load_glb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=True) == {'FINISHED'}
    return bpy.data.objects['RIG_MG01'], bpy.data.objects['SK_MG01']


def _weights(v):
    return {group.group: group.weight for group in v.groups if group.weight > 1e-8}


def _preserve_hands(body, ratio):
    hands = {group.index for group in body.vertex_groups if group.name in HAND_NAMES}
    assert len(hands) == 2
    protected = {v.index: (v.co.copy(), _weights(v)) for v in body.data.vertices
                 if any(g.group in hands and g.weight > .01 for g in v.groups)}
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    mask_name = 'Preserve grip surfaces'
    mask = body.vertex_groups.new(name=mask_name)
    mask.add(list(protected), 1.0, 'REPLACE')
    modifier = body.modifiers.new('Ado board triangle budget', 'DECIMATE')
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    modifier.vertex_group = mask_name
    modifier.invert_vertex_group = True
    modifier.vertex_group_factor = 1000.0
    bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=0)
    assert bpy.ops.object.modifier_apply(modifier=modifier.name) == {'FINISHED'}
    mask = body.vertex_groups.get(mask_name)
    if mask is not None:
        body.vertex_groups.remove(mask)
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    tree = KDTree(len(body.data.vertices))
    for vertex in body.data.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    for co, expected in protected.values():
        matches = (_weights(body.data.vertices[index]) for _, index, _ in tree.find_range(co, .000002))
        assert any(weights.keys() == expected.keys() and all(abs(weights[group] - w) < 1e-4
                   for group, w in expected.items()) for weights in matches), (co, expected)
    assert all(0 < len(v.groups) <= 4 and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in body.data.vertices)
    return len(protected)


def main():
    destination = Path(sys.argv[sys.argv.index('--') + 1])
    destination.mkdir(parents=True, exist_ok=True)
    qa = Path('C:/Users/Administrator/.agents/skills/blender-asset-qa/scripts')
    sys.path.insert(0, str(qa))
    import qa_check
    import review_shots

    rig, body = _load_glb(SOURCE)
    source_tris = len(body.data.polygons)
    assert source_tris == 90000 and len(body.material_slots) == 1
    source_qa = qa_check.run(objects=[body.name], profile='game', eps=.0002)
    (destination / 'source.qa.json').write_text(json.dumps(source_qa, indent=2) + '\n', encoding='utf-8')
    sources = {}
    source_poses = {}
    for pose in POSES:
        _pose(rig, pose)
        sources[pose] = _surface(body)
        review = source_qa if pose == 'rest' else qa_check.run(objects=[body.name], profile='game', eps=.0002)
        source_poses[pose] = {key: review[key] for key in ('pass', 'errors', 'warnings')}
    _pose(rig, 'rest')
    hand_vertices = _preserve_hands(body, .36)
    triangles, bones = len(body.data.polygons), len(rig.data.bones)
    assert triangles == 32400
    reduced = {}
    results = {}
    for pose in POSES:
        _pose(rig, pose)
        reduced[pose] = _surface(body)
        results[pose] = {'source_to_runtime': _error(sources[pose], reduced[pose]),
                         'runtime_to_source': _error(reduced[pose], sources[pose])}
        review = qa_check.run(objects=[body.name], profile='game', eps=.0002)
        results[pose]['errors'] = review['errors']
        results[pose]['warnings'] = review['warnings']
        assert review['pass'], review['errors']
        assert all(results[pose][direction]['p95_m'] < .001
                   for direction in ('source_to_runtime', 'runtime_to_source')), results[pose]
        (destination / f'{pose}.qa.json').write_text(json.dumps(review, indent=2)+'\n', encoding='utf-8')
        print(pose, results[pose], flush=True)
    _pose(rig, 'brace')
    for mode in ('random', 'wire'):
        review_shots.run(objects=[body.name], out=str(destination / f'brace-{mode}.png'), mode=mode,
                         views=['front', 'right', 'back'], res=384)
    _pose(rig, 'rest')
    rig.select_set(True)
    glb = destination / 'MG01_Board.glb'
    assert bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
        export_apply=False, export_animations=False, export_all_influences=False) == {'FINISHED'}
    rig, body = _load_glb(glb)
    assert len(body.data.polygons) == triangles and len(rig.data.bones) == bones
    for pose in POSES:
        _pose(rig, pose)
        item = _error(reduced[pose], _surface(body))
        assert item['max_m'] < .0001, (pose, item)
        results[pose]['roundtrip'] = item
    report = {'source_triangles': source_tris, 'runtime_triangles': triangles, 'bones': bones,
              'protected_hand_vertices': hand_vertices, 'sha256': hashlib.sha256(glb.read_bytes()).hexdigest(),
              'source_review': source_poses, 'poses': results}
    (destination / 'assets.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

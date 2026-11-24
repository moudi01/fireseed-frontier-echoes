"""Make and verify a board-scale EN06 mesh from the existing skinned master."""

import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree


ROOT = Path.cwd()
SOURCE = ROOT / '设计整理/敌人蒙皮权重_20261115/rigged/EN06_skinned.blend'
RIG, MESH = 'RIG_EN06', 'SK_EN06'
POSES = {'rest': 0.0, 'windup': -.12, 'release': .14}


def _pose(rig, tilt):
    rig.data.pose_position = 'POSE'
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    shell = rig.pose.bones['shell']
    shell.rotation_mode = 'QUATERNION'
    shell.rotation_quaternion = Quaternion(Vector((1, 0, 0)), tilt)
    for name, side in [('stalk_01.L', -1), ('stalk_01.R', 1)]:
        bone = rig.pose.bones[name]
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = Quaternion(Vector((0, 0, 1)), tilt * side * .6)
    bpy.context.view_layer.update()


def _surface(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ v.co for v in data.vertices]
    faces = [tuple(p.vertices) for p in data.polygons]
    evaluated.to_mesh_clear()
    return vertices, faces


def _error(a, b):
    tree = BVHTree.FromPolygons(b[0], b[1], all_triangles=True)
    stride = max(1, len(a[0]) // 3000)
    errors = sorted(tree.find_nearest(v)[3] for v in a[0][::stride])
    return {'max_m': errors[-1], 'p95_m': errors[math.ceil(len(errors) * .95) - 1]}


def _open():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
    bpy.context.scene.frame_set(1)
    rig, body = bpy.data.objects[RIG], bpy.data.objects[MESH]
    rig.animation_data_clear()
    return rig, body


def _reduce(body, ratio):
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    simplifier = body.modifiers.new('Board triangle budget', 'DECIMATE')
    simplifier.ratio = ratio
    simplifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_move_to_index(modifier=simplifier.name, index=0)
    assert bpy.ops.object.modifier_apply(modifier=simplifier.name) == {'FINISHED'}
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)


def main():
    glb, evidence = map(Path, sys.argv[sys.argv.index('--') + 1:])
    evidence.mkdir(parents=True, exist_ok=True)
    qa = Path('C:/Users/Administrator/.agents/skills/blender-asset-qa/scripts')
    optimization = Path('C:/Users/Administrator/.agents/skills/blender-game-optimization/scripts')
    sys.path[:0] = [str(qa), str(optimization)]
    import mesh_stats
    import qa_check
    import review_shots

    rig, body = _open()
    _pose(rig, 0.0)
    original = mesh_stats.run(objects=[MESH], budget='pc')
    surfaces = {}
    for name, angle in POSES.items():
        _pose(rig, angle)
        surfaces[name] = _surface(body)
    _pose(rig, 0.0)
    _reduce(body, .36)
    results = {}
    runtime_surfaces = {}
    for name, angle in POSES.items():
        _pose(rig, angle)
        reduced = _surface(body)
        runtime_surfaces[name] = reduced
        from_reference = _error(surfaces[name], reduced)
        to_reference = _error(reduced, surfaces[name])
        report = qa_check.run(objects=[MESH], profile='game', eps=.0002)
        (evidence / f'{name}.qa.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print('EN06', name, from_reference, to_reference, report['errors'], report['warnings'], flush=True)
        assert report['pass'], (name, report['errors'])
        assert max(from_reference['p95_m'], to_reference['p95_m']) < .002
        results[name] = {'from_source': from_reference, 'to_source': to_reference}
    for mode in ('random', 'wire'):
        review_shots.run(objects=[MESH], out=str(evidence / f'release-{mode}.png'), mode=mode,
                         views=['front', 'right', 'back'], res=384)
    _pose(rig, 0.0)
    final = mesh_stats.run(objects=[MESH], budget='pc')
    assert 17000 <= final['total_tris'] <= 18000 and final['unique_materials'] == 1 and final['bones'] == 9
    assert all(0 < len(v.groups) <= 4 and abs(sum(g.weight for g in v.groups) - 1) < 1e-4 for v in body.data.vertices)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
        export_apply=False, export_animations=False, export_all_influences=False,
        export_cameras=False, export_lights=False, export_yup=True) == {'FINISHED'}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.gltf(filepath=str(glb)) == {'FINISHED'}
    rig = bpy.data.objects[RIG]
    body = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH'
                and any(mod.type == 'ARMATURE' for mod in obj.modifiers))
    assert len(rig.data.bones) == 9
    for name, angle in POSES.items():
        _pose(rig, angle)
        imported = _surface(body)
        assert len(imported[1]) == final['total_tris']
        roundtrip = _error(runtime_surfaces[name], imported)
        assert roundtrip['max_m'] < .0001, (name, roundtrip)
        results[name]['roundtrip'] = roundtrip
    report = {'pass': True, 'source_mesh': original, 'runtime_mesh': final, 'poses': results,
              'sha256': hashlib.sha256(glb.read_bytes()).hexdigest()}
    (evidence / 'assets.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

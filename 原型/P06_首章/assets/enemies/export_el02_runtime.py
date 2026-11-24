"""Export the dual-sac elite at board resolution while preserving its skin."""

import hashlib
import json
from pathlib import Path
import sys

import bpy


SOURCE = Path.cwd() / '设计整理/敌人蒙皮权重_20261115/rigged/EL02_skinned.blend'
RIG, MESH = 'RIG_EL02', 'SK_EL02'
TRIANGLES = 14000


def check_weights(body):
    for vertex in body.data.vertices:
        assert 0 < len(vertex.groups) <= 4
        assert abs(sum(group.weight for group in vertex.groups) - 1) < .0001


def main():
    glb, evidence = (Path(arg).resolve() for arg in sys.argv[sys.argv.index('--') + 1:])
    from export_en06_runtime import _error, _reduce, _surface

    evidence.mkdir(parents=True, exist_ok=True)
    skills = Path('C:/Users/Administrator/.agents/skills')
    sys.path[:0] = [str(skills / name / 'scripts') for name in ('blender-asset-qa', 'blender-game-optimization')]
    import mesh_stats
    import qa_check
    import review_shots

    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
    rig, body = bpy.data.objects[RIG], bpy.data.objects[MESH]
    rig.animation_data_clear()
    rig.data.pose_position = 'POSE'
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    source = mesh_stats.run(objects=[MESH], budget='pc')
    reference = _surface(body)
    _reduce(body, TRIANGLES / source['total_tris'])
    check_weights(body)
    for image in bpy.data.images:
        if image.packed_file and max(image.size) > 1024:
            image.scale(1024, 1024)
            image.pack()
    stats = mesh_stats.run(objects=[MESH], budget='pc')
    assert 13980 <= stats['total_tris'] <= TRIANGLES
    assert stats['unique_materials'] == 1 and stats['bones'] == 20
    reduced = _surface(body)
    simplification = {'from_source': _error(reference, reduced), 'to_source': _error(reduced, reference)}
    assert max(error['p95_m'] for error in simplification.values()) < .01, simplification
    qa = qa_check.run(objects=[MESH], profile='game', eps=.0002)
    (evidence / 'mesh.qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert qa['pass'], qa['errors']
    for mode in ('texture', 'wire'):
        review_shots.run(objects=[MESH], out=str(evidence / f'board-{mode}.png'), mode=mode,
                         views=['front', 'right', 'back'], res=384)
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
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
    assert len(rig.data.bones) == 20
    assert all(rig.data.bones.get(name) for name in ('sac.L', 'sac.R', 'canopy', 'neck'))
    check_weights(body)
    imported = _surface(body)
    assert len(imported[1]) == stats['total_tris']
    roundtrip = _error(reduced, imported)
    assert roundtrip['max_m'] < .0001, roundtrip
    report = {'pass': True, 'source_mesh': source, 'runtime_mesh': stats, 'simplification': simplification,
              'roundtrip': roundtrip, 'bytes': glb.stat().st_size, 'warnings': qa['warnings'],
              'sha256': hashlib.sha256(glb.read_bytes()).hexdigest()}
    (evidence / 'assets.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    main()

"""Build the board guard and bake its shield and blade contacts."""

import hashlib
import json
from math import cos, pi, sin
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_en06_runtime import _reduce, _surface


ROOT = Path.cwd()
SOURCE = ROOT / '设计整理/敌人蒙皮权重_20261115/rigged/EN04_skinned.blend'
CONTACT = {'L': Vector((.025, .069, -.006)), 'R': Vector((-.025, .069, -.006))}
SOCKET = {'L': 'RoundShieldGrip', 'R': 'ShortBladeGrip'}
# Each key gives the shield and blade grip positions, then shield yaw and blade direction.
POSES = {
    'ready': ((.46, -.34, 1.02), (-.48, -.185, .965), -17, (-.20, -.11, -1)),
    'raised': ((.27, -.52, 1.30), (-.44, -.21, 1.02), -6, (-.28, -.38, -1)),
    'braced': ((.27, -.565, 1.33), (-.46, -.17, 1.01), -1, (-.38, -.30, -1)),
    'recoil': ((.27, -.45, 1.39), (-.43, -.20, .99), -4, (-.24, -.39, -1)),
    'cut_set': ((.48, -.36, 1.12), (-.57, .01, 1.17), -19, (-.78, -.30, .40)),
    'cut': ((.47, -.35, 1.08), (-.33, -.51, 1.18), -18, (.24, -.94, -.32)),
    'hurt': ((.48, -.34, 1.00), (-.47, -.17, .90), -18, (-.12, -.44, -1)),
}
CLIPS = {
    'EN04Ready-loop': [(1, 'ready'), (25, 'ready')],
    'EN04Raise': [(1, 'ready'), (10, 'raised'), (13, 'raised')],
    'EN04Hold-loop': [(1, 'raised'), (25, 'raised')],
    'EN04Brace': [(1, 'raised'), (4, 'braced'), (8, 'recoil'), (14, 'raised')],
    'EN04Cut': [(1, 'ready'), (4, 'cut_set'), (8, 'cut'), (12, 'cut'), (18, 'ready')],
    'EN04GuardedCut': [(1, 'raised'), (4, 'cut_set'), (8, 'cut'), (12, 'cut'), (18, 'raised')],
    'EN04Hurt': [(1, 'ready'), (5, 'hurt'), (11, 'ready')],
}


def material(name, color, metallic):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1.0)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = result.diffuse_color
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = .66
    return result


class EquipmentMesh:
    def __init__(self):
        self.points, self.faces, self.slots = [], [], []

    def rings(self, rings, bands, cap):
        start, count = len(self.points), len(rings[0])
        for ring in rings:
            self.points.extend(ring)
        self.faces.append(tuple(start + n for n in reversed(range(count))))
        self.slots.append(cap[0])
        for layer, slot in enumerate(bands):
            base = start + layer * count
            for n in range(count):
                after = (n + 1) % count
                self.faces.append((base + n, base + after, base + count + after, base + count + n))
                self.slots.append(slot)
        end = start + (len(rings) - 1) * count
        self.faces.append(tuple(end + n for n in range(count)))
        self.slots.append(cap[1])

    def round(self, rows, bands, cap, segments=24, center=(0, 0)):
        self.rings([[(center[0] + r * cos(2*pi*n/segments), depth, center[1] + r * sin(2*pi*n/segments))
                     for n in range(segments)] for r, depth in rows], bands, cap)

    def build(self, name, materials):
        data = bpy.data.meshes.new(name)
        data.from_pydata(self.points, [], self.faces)
        data.update()
        slots = sorted(set(self.slots))
        for slot in slots:
            data.materials.append(materials[slot])
        for polygon, slot in zip(data.polygons, self.slots):
            polygon.material_index = slots.index(slot)
        mesh = bmesh.new()
        mesh.from_mesh(data)
        bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
        bmesh.ops.triangulate(mesh, faces=list(mesh.faces))
        mesh.to_mesh(data)
        mesh.free()
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(island_margin=.015)
        bpy.ops.object.mode_set(mode='OBJECT')
        return obj


def make_props():
    bronze = material('甲环卫 · 铜饰', (.47, .249, .108), .35)
    iron = material('甲环卫 · 深铁', (.123, .095, .078), .24)
    leather = material('甲环卫 · 皮握柄', (.11, .055, .034), .0)
    silver = material('甲环卫 · 刀钢', (.36, .297, .234), .31)

    round_shield = EquipmentMesh()
    round_shield.round([(.354, -.116), (.375, -.139), (.375, -.174), (.360, -.199),
                        (.300, -.209), (.290, -.198), (.116, -.213), (.105, -.220),
                        (.092, -.252), (.058, -.278), (.026, -.282)],
                       [1, 1, 0, 0, 0, 1, 0, 0, 0, 0], (1, 0), segments=32)
    for n in range(8):
        angle = 2*pi*n/8
        round_shield.round([(.019, -.202), (.019, -.214), (.012, -.223)], [0, 0], (0, 0), 8,
                           (.331*cos(angle), .331*sin(angle)))
    # The base of each stand intersects the shield backing. The handle spans the closed glove.
    for z in (-.109, .109):
        round_shield.round([(.029, -.132), (.025, -.020), (.021, .013)], [1, 1], (1, 1), 10, (0, z))
    round_shield.rings([[(.025*cos(2*pi*n/12), .025*sin(2*pi*n/12), z) for n in range(12)]
                        for z in (-.122, .122)], [2], (2, 2))

    sword = EquipmentMesh()
    sword.round([(.031, .118), (.035, .103), (.025, .086), (.026, -.119), (.029, -.142)],
                [0, 0, 2, 0], (0, 0), 12)
    for profile, start, end, slot in [
        ([(.122, .025), (.122, -.025), (-.122, -.025), (-.122, .025)], -.108, -.150, 0),
        ([(0, .037), (.088, 0), (0, -.032), (-.088, 0)], -.143, -.494, 3),
    ]:
        rings = [[(x, depth, z) for x,z in profile] for depth in (start, end)]
        if slot == 3:
            rings.append([(x*.18, -.621, z*.32) for x,z in profile])
        sword.rings(rings, [slot]*(len(rings)-1), (slot, slot))
    materials = [bronze, iron, leather, silver]
    return {'L': round_shield.build('EN04_RoundShield', materials),
            'R': sword.build('EN04_ShortBlade', materials)}


def bind_props(rig, props, sockets=SOCKET):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name in sockets.values():
        bone = rig.data.edit_bones.new(name)
        bone.head, bone.tail = (0, 0, 0), (0, 1, 0)
        bone.parent = rig.data.edit_bones['root']
    bpy.ops.object.mode_set(mode='OBJECT')
    for side, obj in props.items():
        obj.parent = rig
        group = obj.vertex_groups.new(name=sockets[side])
        group.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
        deform = obj.modifiers.new('Rigid accessory', 'ARMATURE')
        deform.object = rig


def set_bone(bone, point, orientation):
    bone.matrix = Matrix.Translation(point) @ orientation.to_matrix().to_4x4()
    bpy.context.view_layer.update()


def aim_bone(bone, start, end):
    rest = bone.bone.matrix_local.to_quaternion()
    aim = (rest @ Vector((0,1,0))).rotation_difference((end-start).normalized())
    set_bone(bone, start, aim @ rest)


def pose_arm(rig, side, grip, across, palm):
    upper, fore, hand = [rig.pose.bones[f'{part}.{side}'] for part in ('upper_arm', 'forearm', 'hand')]
    shoulder = upper.head.copy()
    palm = (palm - palm.project(across)).normalized()
    rotation = Matrix((across, palm, across.cross(palm))).transposed().to_quaternion()
    wrist = grip - rotation @ CONTACT[side]
    axis = (wrist - shoulder).normalized()
    length = (wrist - shoulder).length
    a,b = upper.length, fore.length
    assert abs(a-b) < length < a+b, (side, tuple(grip), length, a+b)
    offset = (a*a - b*b + length*length) / (2*length)
    pole = Vector((.85 if side == 'L' else -.85, .38, -.94))
    bend = (pole - pole.project(axis)).normalized()
    elbow = shoulder + axis*offset + bend*(a*a-offset*offset)**.5
    aim_bone(upper, shoulder, elbow)
    aim_bone(fore, elbow, wrist)
    set_bone(hand, wrist, rotation)


def pose(rig, name, frame):
    keys = CLIPS[name]
    for (start,a), (end,b) in zip(keys,keys[1:]):
        if start <= frame <= end:
            break
    alpha = (frame-start)/(end-start)
    alpha = alpha*alpha*(3-2*alpha)
    l1,r1,turn1,blade1 = POSES[a]
    l2,r2,turn2,blade2 = POSES[b]
    left, right = Vector(l1).lerp(Vector(l2),alpha), Vector(r1).lerp(Vector(r2),alpha)
    if name.endswith('-loop'):
        lift = .007*sin(2*pi*(frame-1)/24)
        left.z += lift
        right.z += lift*.55
    yaw = (turn1*(1-alpha) + turn2*alpha)*pi/180
    if name == 'EN04GuardedCut':
        left = Vector(POSES['raised'][0])
        yaw = POSES['raised'][2]*pi/180
    shield = Matrix.Rotation(yaw, 3, 'Z').to_quaternion()
    aim = Vector(blade1).lerp(Vector(blade2),alpha).normalized()
    knife = Vector((0,-1,0)).rotation_difference(aim)
    for side, grip, axis, palm, rotation in [
        ('L', left, Vector((0,0,1)), left - rig.pose.bones['upper_arm.L'].head, shield),
        ('R', right, -aim, knife @ Vector((-1,0,0)), knife),
    ]:
        pose_arm(rig, side, grip, axis, palm)
        set_bone(rig.pose.bones[SOCKET[side]], grip, rotation)


def bake(rig):
    bones = [b for b in rig.pose.bones if b.name in SOCKET.values()
             or b.name.startswith(('upper_arm.', 'forearm.', 'hand.'))]
    rig.animation_data_create()
    actions = {}
    for name, keys in CLIPS.items():
        action = bpy.data.actions.new(name)
        actions[name] = action
        rig.animation_data.action = action
        previous = {}
        for frame in range(1, keys[-1][0]+1):
            bpy.context.scene.frame_set(frame)
            pose(rig, name, frame)
            for bone in bones:
                rotation = bone.rotation_quaternion.copy()
                if bone.name in previous and rotation.dot(previous[bone.name]) < 0:
                    rotation.negate()
                    bone.rotation_quaternion = rotation
                previous[bone.name] = rotation
                bone.keyframe_insert('rotation_quaternion', frame=frame)
                bone.keyframe_insert('location', frame=frame)
    return actions


def grip_error(rig):
    return max((rig.pose.bones[f'hand.{side}'].matrix @ point - rig.pose.bones[SOCKET[side]].head).length
               for side, point in CONTACT.items())


def inspect(rig, body, props, actions, evidence):
    import qa_check
    import review_shots

    checks = {}
    for name, keys in CLIPS.items():
        rig.animation_data.action = actions[name]
        end = keys[-1][0]
        peak = 0.0
        for sample in range(4, end*4+1):
            bpy.context.scene.frame_set(sample//4, subframe=(sample%4)*.25)
            peak = max(peak, grip_error(rig))
        assert peak < .006, (name, peak)
        checks[name] = {'quarter_frame_samples': (end-1)*4+1, 'max_grip_error_m': peak}
    for label, name, frame in [('ready','EN04Ready-loop',1), ('raised','EN04Raise',10),
                               ('braced','EN04Brace',4), ('cut','EN04Cut',8)]:
        rig.animation_data.action = actions[name]
        bpy.context.scene.frame_set(frame)
        objects = [body.name] + [obj.name for obj in props.values()]
        report = qa_check.run(objects=objects, profile='game', eps=.0002)
        (evidence/f'{label}.qa.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        vertices, faces = _surface(body)
        armor = BVHTree.FromPolygons(vertices, faces, all_triangles=True)
        overlaps = {}
        for side,obj in props.items():
            prop_verts, prop_faces = _surface(obj)
            prop = BVHTree.FromPolygons(prop_verts, prop_faces, all_triangles=True)
            to_grip = rig.pose.bones[SOCKET[side]].matrix.inverted()
            # Only the grip and rear mount are allowed to touch the armored glove.
            overlap_points = [to_grip @ (sum((prop_verts[i] for i in prop_faces[b]),Vector())/3)
                              for _,b in armor.overlap(prop)]
            overlaps[side] = sum(v.y < (-.130 if side == 'L' else -.155) for v in overlap_points)
        print(label, report['errors'], report['warnings'], overlaps, flush=True)
        assert report['pass'] and not any(overlaps.values()), (label, report['errors'], overlaps)
        checks[label] = {'mesh_errors': report['errors'], 'mesh_warnings': report['warnings'],
                         'intersections_outside_grip': overlaps}
        review_shots.run(objects=objects, out=str(evidence/f'{label}.png'), mode='material',
                         views=['front','right','back'], res=360)
    return checks


def main():
    output, evidence = (Path(value).resolve() for value in sys.argv[sys.argv.index('--')+1:])
    evidence.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path('C:/Users/Administrator/.agents/skills/blender-asset-qa/scripts')))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
    rig, body = bpy.data.objects['RIG_EN04'], bpy.data.objects['SK_EN04']
    bpy.context.scene.render.fps = 30
    rig.animation_data_clear()
    rig.data.pose_position = 'POSE'
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    props = make_props()
    bind_props(rig, props)
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
    source_triangles = len(body.data.polygons)
    _reduce(body, .202)
    assert all(0 < len(v.groups) <= 4 and abs(sum(g.weight for g in v.groups)-1) < .0001 for v in body.data.vertices)
    actions = bake(rig)
    checks = inspect(rig, body, props, actions, evidence)
    rig.animation_data.action = None
    for name, action in actions.items():
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        track.mute = True
    # Preserve an inspectable authoring scene while exporting each track independently.
    bpy.context.scene.frame_set(1)
    rig.animation_data.action = actions['EN04Ready-loop']
    bpy.ops.wm.save_as_mainfile(filepath=str(evidence/'EN04_Board.blend'))
    rig.animation_data.action = None
    for track in rig.animation_data.nla_tracks:
        track.mute = False
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (rig, body, *props.values()):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    assert bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB', use_selection=True,
        export_animation_mode='NLA_TRACKS', export_all_influences=False) == {'FINISHED'}
    report = {'source_body_triangles': source_triangles, 'body_triangles': len(body.data.polygons),
              'equipment_triangles': {obj.name:len(obj.data.polygons) for obj in props.values()},
              'bones': len(rig.data.bones), 'checks': checks, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    (evidence/'assets.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()

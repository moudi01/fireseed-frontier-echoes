"""Bake the two skeletons used by the fortress side encounter."""

import hashlib
import json
from math import cos, pi, sin
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_en04_runtime import CONTACT, EquipmentMesh, bind_props, material, pose_arm, set_bone
from export_en06_runtime import _reduce


SOURCE = Path.cwd() / '设计整理/敌人蒙皮权重_20261115/rigged'
UP = Vector((0, 0, 1))
FRONT = Vector((0, -1, 0))
SIDE = Vector((1, 0, 0))
SWORD = 'BoneBladeGrip'
BOW = 'BoneBowGrip'
NOCK = 'BoneBowNock'
SWORD_POSES = {
    # Off hand, grip, and blade direction in the skeletally authored front frame.
    'ready': ((.32, -.07, 1.02), (-.36, -.11, 1.02), (-.20, -.14, -1)),
    'guard': ((.25, -.19, 1.17), (-.27, -.30, 1.32), (.63, -.24, .77)),
    'set': ((.35, -.14, 1.12), (-.43, -.08, 1.21), (-.80, -.38, .52)),
    'cut': ((.30, -.14, 1.12), (-.27, -.37, 1.21), (.33, -.88, -.32)),
}
BOW_POSES = {
    # Bow grip, free hand, bow roll, and string draw in meters.
    'ready': ((.29, -.18, 1.02), (-.28, -.12, 1.03), 23, 0.0),
    'set': ((.12, -.31, 1.30), (-.12, -.21, 1.25), 9, .04),
    'drawn': ((.096, -.403, 1.380), (-.04, -.12, 1.38), 0, .24),
    'loose': ((.096, -.403, 1.380), (-.04, -.117, 1.401), 0, 0.0),
}
CLIPS = {
    'EN21': {
        'Ready-loop': [(1,'ready'),(25,'ready')],
        'Raise': [(1,'ready'),(13,'guard')],
        'Hold-loop': [(1,'guard'),(25,'guard')],
        'Cut': [(1,'ready'),(6,'set'),(11,'cut'),(17,'ready')],
        'GuardCut': [(1,'guard'),(6,'set'),(11,'cut'),(17,'guard')],
    },
    'EN22': {
        'Ready-loop': [(1,'ready'),(25,'ready')],
        'Draw': [(1,'ready'),(7,'set'),(18,'drawn')],
        'Hold-loop': [(1,'drawn'),(25,'drawn')],
        'Release': [(1,'drawn'),(3,'loose'),(7,'loose'),(14,'ready')],
        'Quick': [(1,'ready'),(7,'set'),(18,'drawn'),(21,'loose'),(25,'loose'),(32,'ready')],
    },
}


def make_blade(rig):
    bronze = material('刀兵 · 铜饰', (.44, .233, .097), .24)
    leather = material('刀兵 · 缠柄', (.12, .061, .034), 0.0)
    edge = material('刀兵 · 刀钢', (.39, .342, .297), .37)
    blade = EquipmentMesh()
    blade.round([(.026, .110), (.033, .089), (.026, .063), (.024, -.106), (.027, -.130)],
                [0, 0, 1, 0], (0, 0), 12)
    guard = [(x,z) for x,z in ((.086,.019),(.086,-.019),(-.086,-.019),(-.086,.019))]
    blade.rings([[(x,y,z) for x,z in guard] for y in (-.087,-.119)], [0], (0,0))
    outline = [(.062, -.105, 0, .023), (.070, -.375, .01, .024),
               (.058, -.492, .045, .019), (.007, -.617, .084, .006)]
    blade.rings([[(center,y,z),(center+w,y,0),(center,y,-z),(center-w,y,0)]
                 for w,y,center,z in outline], [2,2,2], (2,2))
    obj = blade.build('EN21_BoneBlade', [bronze, leather, edge])
    bind_props(rig, {'R':obj}, {'R':SWORD})
    return [obj]


def bow_loop(point, tangent, radius, segments=8):
    across = tangent.normalized().cross(SIDE)
    return [point+radius*(cos(2*pi*i/segments)*SIDE + sin(2*pi*i/segments)*across) for i in range(segments)]


def make_bow(rig):
    wood = material('弓手 · 木弓身', (.193, .087, .037), 0.0)
    bone = material('弓手 · 骨弓梢', (.68, .54, .35), .0)
    binding = material('弓手 · 缠柄', (.28, .134, .056), 0.0)
    fiber = material('弓手 · 弓弦', (.43, .347, .207), 0.0)
    profile = [(.090,-.535,.020), (.120,-.490,.036), (.077,-.441,.029), (.017,-.305,.035),
               (-.010,-.158,.049), (0,-.094,.055), (0,.094,.055), (-.011,.161,.047),
               (.021,.311,.034), (.084,.437,.029), (.128,.487,.038), (.099,.544,.019)]
    points = [Vector((0,y,z)) for y,z,_ in profile]
    bow = EquipmentMesh()
    bow.rings([bow_loop(p, points[min(i+1,len(points)-1)]-points[max(i-1,0)], profile[i][2])
               for i,p in enumerate(points)], [1,1,1,0,0,2,0,0,1,1,1], (1,1))
    bow_mesh = bow.build('EN22_BoneBow', [wood,bone,binding])
    string = EquipmentMesh()
    string.rings([bow_loop(Vector((0,y,z)), UP, .008)
                  for y,z in ((.09,-.535),(.079,.035),(.099,.544))], [0,0], (0,0))
    string_mesh = string.build('EN22_BowString', [fiber])
    bind_props(rig, {'bow':bow_mesh,'string':string_mesh}, {'bow':BOW,'string':NOCK})
    string_mesh.vertex_groups[NOCK].remove([v.index for v in string_mesh.data.vertices if abs(v.co.z)>.10])
    tips = string_mesh.vertex_groups.new(name=BOW)
    tips.add([v.index for v in string_mesh.data.vertices if abs(v.co.z)>.10],1.0,'REPLACE')
    return [bow_mesh,string_mesh]


def keys_at(keys, frame):
    for (start,a),(end,b) in zip(keys,keys[1:]):
        if start<=frame<=end:
            amount = (frame-start)/(end-start)
            return a,b,amount*amount*(3-2*amount)
    raise ValueError(frame)


def sword_pose(rig, a, b, t, breathe):
    l1,r1,d1 = SWORD_POSES[a]
    l2,r2,d2 = SWORD_POSES[b]
    left, right = Vector(l1).lerp(Vector(l2),t), Vector(r1).lerp(Vector(r2),t)
    left.z += breathe
    right.z += breathe*.6
    axis = Vector(d1).lerp(Vector(d2),t).normalized()
    blade = FRONT.rotation_difference(axis)
    pose_arm(rig, 'L', left, UP, left-rig.pose.bones['upper_arm.L'].head)
    pose_arm(rig, 'R', right, -axis, blade @ -SIDE)
    set_bone(rig.pose.bones[SWORD], right, blade)


def bow_pose(rig, a, b, t, breathe):
    b1,r1,roll1,pull1 = BOW_POSES[a]
    b2,r2,roll2,pull2 = BOW_POSES[b]
    grip, hand = Vector(b1).lerp(Vector(b2),t), Vector(r1).lerp(Vector(r2),t)
    grip.z += breathe
    hand.z += breathe
    roll = (roll1*(1-t)+roll2*t)*pi/180
    rotation = Quaternion(FRONT, roll)
    string = (pull1*(1-t)+pull2*t)
    nock = grip+rotation@Vector((0,.079+string,.035))
    # The drawing fingers follow the nock until it is released.
    if 'loose' not in (a,b):
        draw = (1-t if a=='drawn' else 0.0)+(t if b=='drawn' else 0.0)
        hand = hand.lerp(nock,draw)
    elif a=='drawn':
        held = grip+rotation@Vector((0,.079+pull1,.035))
        hand = held.lerp(hand,t)
    pose_arm(rig, 'L', grip, rotation@UP, grip-rig.pose.bones['upper_arm.L'].head)
    pose_arm(rig, 'R', hand, SIDE, hand-rig.pose.bones['upper_arm.R'].head)
    set_bone(rig.pose.bones[BOW], grip, rotation)
    set_bone(rig.pose.bones[NOCK], grip+rotation@Vector((0,string,0)), rotation)


def bake(rig, kind):
    joints = [joint for joint in rig.pose.bones if joint.name in {SWORD,BOW,NOCK}
              or joint.name.startswith(('upper_arm.','forearm.','hand.'))]
    rig.animation_data_create()
    actions = {}
    solve = sword_pose if kind == 'EN21' else bow_pose
    for label, keys in CLIPS[kind].items():
        name = kind+label
        action = bpy.data.actions.new(name)
        actions[label] = action
        rig.animation_data.action = action
        previous = {}
        end = keys[-1][0]
        for frame in range(1,end+1):
            bpy.context.scene.frame_set(frame)
            a,b,t = keys_at(keys,frame)
            lift = .005*sin(2*pi*(frame-1)/(end-1)) if label.endswith('-loop') else 0.0
            solve(rig,a,b,t,lift)
            for joint in joints:
                q = joint.rotation_quaternion.copy()
                if joint.name in previous and q.dot(previous[joint.name])<0:
                    q.negate()
                    joint.rotation_quaternion = q
                previous[joint.name] = q
                joint.keyframe_insert('rotation_quaternion',frame=frame)
                joint.keyframe_insert('location',frame=frame)
        rig.animation_data.action = None
    return actions


def verify(rig, body, props, actions, kind, output):
    import qa_check
    import review_shots

    contact = SWORD if kind=='EN21' else BOW
    side = 'R' if kind=='EN21' else 'L'
    peak = {}
    for label, action in actions.items():
        rig.animation_data.action = action
        end = CLIPS[kind][label][-1][0]
        error = 0.0
        for frame in range(4,4*end+1):
            bpy.context.scene.frame_set(frame//4,subframe=frame%4/4)
            actual = rig.pose.bones[f'hand.{side}'].matrix@CONTACT[side]
            error = max(error,(actual-rig.pose.bones[contact].head).length)
        assert error < .008,(kind,label,error)
        peak[label] = error
    checks = [('Ready-loop',1),('Hold-loop',1),('Cut',11)] if kind=='EN21' else [
        ('Ready-loop',1),('Hold-loop',1),('Release',3)]
    geometry = {}
    for label,frame in checks:
        rig.animation_data.action = actions[label]
        bpy.context.scene.frame_set(frame)
        names = [body.name]+[p.name for p in props]
        tested = qa_check.run(objects=names,profile='game',eps=.0002)
        (output/f'{kind}-{label}.qa.json').write_text(json.dumps(tested,indent=2)+'\n',encoding='utf-8')
        print(kind,label,tested['errors'],tested['warnings'],flush=True)
        inherited = False
        if kind == 'EN22' and len(tested['errors']) == 1 and len(tested['floating']) == 1:
            source = json.loads((SOURCE.parent/'reports/EN22_final_geometry.json').read_bytes())
            original, current = source['floating'][0], tested['floating'][0]
            inherited = (tested['errors'][0].startswith('floating/detached part in SK_EN22')
                         and tested['objects'][body.name]['islands'] == 2
                         and current['object'] == original['object']
                         and (Vector(current['center'])-Vector(original['center'])).length < .005)
        assert (tested['pass'] or inherited) and not tested['warnings'], (kind,label,tested['errors'],tested['warnings'])
        geometry[label] = {'pass': tested['pass'] or inherited, 'original_separate_sections': inherited}
        review_shots.run(objects=names,out=str(output/f'{kind}-{label}.png'),mode='material',
                         views=['front','right','back'],res=360)
    return peak, geometry


def export(kind, output):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/f'{kind}_skinned.blend'),use_scripts=False)
    rig,body = bpy.data.objects[f'RIG_{kind}'],bpy.data.objects[f'SK_{kind}']
    bpy.context.scene.render.fps = 30
    rig.animation_data_clear()
    rig.data.pose_position = 'POSE'
    props = make_blade(rig) if kind=='EN21' else make_bow(rig)
    for joint in rig.pose.bones:
        joint.matrix_basis.identity()
        joint.rotation_mode = 'QUATERNION'
    _reduce(body,.20)
    assert all(0<len(v.groups)<=4 and abs(sum(g.weight for g in v.groups)-1)<.0001 for v in body.data.vertices)
    actions = bake(rig,kind)
    grip, geometry = verify(rig,body,props,actions,kind,output)
    rig.animation_data.action = None
    for label,action in actions.items():
        track = rig.animation_data.nla_tracks.new()
        track.name = kind+label
        track.strips.new(track.name,1,action)
        track.mute = True
    rig.animation_data.action = actions['Ready-loop']
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/f'{kind}_Board.blend'))
    rig.animation_data.action = None
    for track in rig.animation_data.nla_tracks:
        track.mute = False
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (rig,body,*props):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    target = output/f'{kind}_Board.glb'
    assert bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',use_selection=True,
           export_animation_mode='NLA_TRACKS',export_all_influences=False)=={'FINISHED'}
    return {'body_triangles':len(body.data.polygons),'bones':len(rig.data.bones),
            'props':{obj.name:len(obj.data.polygons) for obj in props},
            'max_grip_offset_m':grip,'geometry':geometry,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    sys.path.insert(0,str(Path('C:/Users/Administrator/.agents/skills/blender-asset-qa/scripts')))
    out = Path(sys.argv[sys.argv.index('--')+1]).resolve()
    out.mkdir(parents=True,exist_ok=True)
    result = {kind:export(kind,out) for kind in ('EN21','EN22')}
    (out/'assets.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

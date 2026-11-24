"""Bake project locomotion and low-amplitude poses onto the 24-bone characters."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_arm_fits import (
    ARM_FITS, ARM_RADII, EQUIPMENT, FLARED_CUFFS, HAND_PROPS, HELD_ARMS, PALM_CONTACTS, ROPE_CONTACT,
)


FPS = 24
CLIPS = {"Walk": 26, "Run": 19, "Idle": 96, "Alert": 72}
SIDES = (("Left", 1), ("Right", -1))
LOCOMOTION = {
    "Walk": "Armature|walking_man|baselayer",
    "Run": "Armature|running|baselayer",
}


def import_armature(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS
    bpy.ops.import_scene.gltf(filepath=str(path), disable_bone_shape=True)
    armature, = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    return armature


def activate(armature, action):
    animation = armature.animation_data_create()
    animation.action = action
    if action.slots:
        animation.action_slot = action.slots[0]


def read_foot_cycles(donor):
    armature = import_armature(donor)
    scene = bpy.context.scene
    rest = armature.data.bones
    leg_span = ((rest["LeftUpLeg"].head_local - rest["LeftFoot"].head_local).length
                * armature.matrix_world.to_scale().x)
    cycles = {}
    for clip, name in LOCOMOTION.items():
        action = bpy.data.actions[name]
        activate(armature, action)
        for track in armature.animation_data.nla_tracks:
            track.mute = True
        start, end = action.frame_range
        samples = []
        for index in range(CLIPS[clip]):
            frame = start + (end - start) * index / CLIPS[clip]
            scene.frame_set(int(frame), subframe=frame % 1)
            world = armature.matrix_world
            positions = {side: world @ armature.pose.bones[f"{side}Foot"].head for side, _ in SIDES}
            samples.append(positions)

        floors = {side: min(p[side].z for p in samples) for side, _ in SIDES}
        fore_aft = [p[side].y for p in samples for side, _ in SIDES]
        center = (min(fore_aft) + max(fore_aft)) / 2
        half_stride = (max(fore_aft) - min(fore_aft)) / 2
        cycles[clip] = [{side: ((p[side].y - center) / leg_span,
                                (p[side].z - floors[side]) / leg_span,
                                (p[side].y - center) / half_stride)
                         for side, _ in SIDES} for p in samples]
    return cycles


def axis_rotation(axis, degrees):
    return Quaternion(axis, math.radians(degrees))


def knee_target(hip, ankle, thigh, shin):
    offset = ankle - hip
    direction = offset.normalized()
    distance = min(offset.length, thigh + shin - 0.00001)
    distance = max(distance, abs(thigh - shin) + 0.00001)
    ankle = hip + direction * distance
    forward = Vector((0, -1, 0))
    pole = (forward - direction * direction.dot(forward)).normalized()
    along = (thigh * thigh - shin * shin + distance * distance) / (2 * distance)
    radius = math.sqrt(max(0.0, thigh * thigh - along * along))
    return hip + direction * along + pole * radius, ankle


def fit_rotation(rest_rotation, direction):
    return (rest_rotation @ Vector((0, 1, 0))).rotation_difference(direction.normalized()) @ rest_rotation


def solve_swing(side, sign, drive, running, carrying, extra_clearance, rest, solved):
    upper, lower, hand = (f"{side}{part}" for part in ("Arm", "ForeArm", "Hand"))
    shoulder = f"{side}Shoulder"
    rest_shoulder, rest_shoulder_rotation = rest[shoulder]
    shoulder_point, shoulder_rotation = solved[shoulder]
    inherited = shoulder_rotation @ rest_shoulder_rotation.inverted()
    upper_point, upper_rotation = rest[upper]
    elbow_point, lower_rotation = rest[lower]
    wrist_point, hand_rotation = rest[hand]
    upper_length = (elbow_point - upper_point).length
    lower_length = (wrist_point - elbow_point).length

    if carrying:
        # Carry the entire bent arm with the stride while keeping its grip.
        pitch = (-10 if running else -7) * drive
        arm_motion = axis_rotation((1, 0, 0), pitch)
        upper_direction = arm_motion @ (elbow_point - upper_point).normalized()
        lower_direction = arm_motion @ (wrist_point - elbow_point).normalized()
        palm_rotation = arm_motion @ hand_rotation
    else:
        # Lay out the elbow and wrist explicitly. A relaxed walking elbow
        # stays below the shoulder, with the hand sweeping past the hip.
        pitch = (-27 if running else -20) * drive - (3 if running else 0)
        bend = (32 + 6 * drive) if running else (6 + 3 * drive)
        clearance = axis_rotation((0, 1, 0), -sign * ((6 if running else 4) + extra_clearance))
        upper_motion = axis_rotation((1, 0, 0), pitch) @ clearance
        lower_motion = axis_rotation((1, 0, 0), pitch - bend) @ clearance
        upper_direction = upper_motion @ (elbow_point - upper_point).normalized()
        lower_direction = lower_motion @ (wrist_point - elbow_point).normalized()
        # Retain the sculpt's palm orientation and carry it through the
        # forearm rotation, with a slight counter-rotation at the wrist.
        lower_delta = (wrist_point - elbow_point).rotation_difference(lower_direction)
        palm_rotation = axis_rotation((1, 0, 0), bend * .18) @ lower_delta @ hand_rotation

    upper_origin = shoulder_point + inherited @ (upper_point - rest_shoulder)
    elbow = upper_origin + (inherited @ upper_direction) * upper_length
    wrist = elbow + (inherited @ lower_direction) * lower_length
    solved[upper] = (upper_origin, inherited @ fit_rotation(upper_rotation, upper_direction))
    solved[lower] = (elbow, inherited @ fit_rotation(lower_rotation, lower_direction))
    solved[hand] = (wrist, inherited @ palm_rotation)


def fit_arms(armature, height, fit):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    bones = armature.data.edit_bones
    for index, (side, sign) in enumerate(SIDES):
        collar, upper, forearm, hand = (bones[f"{side}{part}"] for part in ("Shoulder", "Arm", "ForeArm", "Hand"))
        points = [Vector((sign * x, y, z)) * height for x, y, z in fit[index % len(fit)]]
        collar.tail = points[0]
        for bone, head, tail in zip((upper, forearm, hand), points, points[1:]):
            bone.head, bone.tail = head, tail
            bone.align_roll(Vector((0, 1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")


def smoothstep(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def arm_weights(points, fit, side, radii, held):
    """Use fitted sleeves and palms to anchor the weight smoothing."""
    sign = 1 if side == "Left" else -1
    outward = points[:, 0] * sign
    a, b, c, d = np.asarray(fit) * (sign, 1, 1)
    limits = []
    progress = []
    for start, end, radius in zip((a, b, c), (b, c, d), radii):
        direction = end - start
        fraction = ((points - start) @ direction) / (direction @ direction)
        distance = np.linalg.norm(points - start - np.clip(fraction, 0, 1)[:, None] * direction, axis=1)
        limits.append(distance / radius)
        progress.append(fraction)

    if not held:
        # Finger lengths vary around the centerline. Continue the palm
        # envelope beyond the last pivot without spilling into the hips.
        hand_axis = d - c
        palm_depth = np.linalg.norm(points - c - np.clip(progress[2], 0, 1.72)[:, None] * hand_axis, axis=1)
        limits[2] = palm_depth / radii[2]
    envelope = np.min(limits, axis=0)
    upper = (1 - smoothstep(.74, 1.38, limits[0])) * smoothstep(-.17, .25, progress[0])
    elbow = smoothstep(-.21, .22, progress[1])
    wrist = smoothstep(-.16, .20, progress[2])
    if held:
        # Props extend beyond the wrist radius and keep the hand transform.
        prop = (outward > c[0] * sign - .065) & (points[:, 1] < c[1] + .025)
        if d[2] > c[2]:
            prop &= points[:, 2] > c[2] + .015
        else:
            prop &= (points[:, 2] < c[2] + .039) & (points[:, 2] > d[2] - .070)
        palm_support = np.maximum(1 - smoothstep(.82, 1.53, limits[2]), prop.astype(float))
        # The bent chain points back toward the upper arm. Use the closest
        # segment at the elbow so projection alone cannot skip the forearm.
        elbow *= 1 - smoothstep(.0, .48, np.asarray(limits[1]) - limits[0])
        wrist *= palm_support
        envelope = np.where(prop, np.minimum(envelope, .78), envelope)
    lateral = smoothstep(a[0] * sign - .030, a[0] * sign + .012, outward)
    support = np.maximum(upper, 1 - smoothstep(.82, 1.46, envelope)) * lateral
    support *= np.maximum(smoothstep(-.18, .25, progress[0]), elbow)
    if not held:
        support *= 1 - smoothstep(1.68, 2.04, progress[2])
    # Centerline vertices act as fixed seeds. Leave the shoulder seam soft.
    influence = support[:, None] * np.column_stack(((1 - elbow) * (1 - wrist), elbow * (1 - wrist), wrist))
    return influence


def surface_arm_votes(points, triangles, fit, radii, held):
    """Find arm contours that are separate from clothing in horizontal sections."""
    votes = np.zeros((len(points), 2))
    body_votes = np.zeros(len(points))
    profiles = []
    for index, (side, sign) in enumerate(SIDES):
        if side not in held:
            a, b, c, d = np.asarray(fit[index % len(fit)]) * (sign, 1, 1)
            profiles.append((index, sign, np.stack((d, c, b, a))))
    if not profiles:
        return votes, body_votes

    face_heights = points[triangles, 2]
    lo, hi = face_heights.min(axis=1), face_heights.max(axis=1)
    for level in np.arange(.3155, .732, .007):
        arms = []
        for index, sign, path in profiles:
            tip, wrist, elbow, shoulder = path[:, 2]
            if tip - .060 < level < elbow + (shoulder - elbow) * .45:
                center = [np.interp(level, path[:, 2], path[:, i]) for i in (0, 1)]
                radius = np.interp(level, path[:, 2], (radii[2], max(radii[1:]), radii[1], radii[0]))
                arms.append((index, sign, np.array(center), radius))
        if not arms:
            continue
        links = {}
        for face in triangles[(lo < level) & (hi >= level)]:
            above = points[face, 2] >= level
            pairs = [tuple(sorted((a, b))) for a, b, cross in
                     zip(face, (face[2], face[0], face[1]), above != above[[2, 0, 1]]) if cross]
            left, right = pairs
            links.setdefault(left, []).append(right)
            links.setdefault(right, []).append(left)
        while links:
            stack = [next(iter(links))]
            seen = set()
            while stack:
                edge = stack.pop()
                if edge not in seen:
                    seen.add(edge)
                    stack.extend(links.pop(edge, ()))
            ends = np.array(list(seen))
            a, b = points[ends].transpose(1, 0, 2)
            amount = (level - a[:, 2]) / (b[:, 2] - a[:, 2])
            contour = a[:, :2] + amount[:, None] * (b[:, :2] - a[:, :2])
            nearby = np.unique(ends[np.abs(points[ends, 2] - level) < .023])
            if not len(nearby):
                continue
            if contour[:, 0].min() < -.043 and contour[:, 0].max() > .043:
                body_votes[nearby] += 1
                continue
            for index, sign, center, radius in arms:
                if (sign * contour[:, 0]).min() < .045:
                    continue
                relative = contour - center
                separation = np.linalg.norm(relative, axis=1)
                if np.median(separation) < 1.25 * radius and separation.max() < 2.05 * radius:
                    votes[nearby, index] += 1
    return votes, body_votes


def trace_palms(points, start, end, votes, body_votes, fit, radii, held):
    """Carry distal arm weights along connected fingers without crossing the torso."""
    palms = np.zeros((len(points), 2))
    for index, (side, sign) in enumerate(SIDES):
        if side in held:
            continue
        _, _, wrist, tip = np.asarray(fit[index % len(fit)]) * (sign, 1, 1)
        axis = tip - wrist
        depth = ((points - wrist) @ axis) / (axis @ axis)
        distance = np.linalg.norm(points - wrist - np.clip(depth, 0, 1.75)[:, None] * axis, axis=1)
        side_limit = (points[:, 0] * sign) > max(.09, wrist[0] * sign - radii[2] * .76)
        eligible = ((depth > .18) & (depth < 1.98) & (distance < radii[2] * 1.60) & side_limit
                    & (votes[:, index] >= body_votes))
        seeds = eligible & (depth > .29) & (depth < .94) & (distance < radii[2] * 1.1)
        if not np.any(seeds):
            continue
        connected = seeds.copy()
        edges = eligible[start] & eligible[end]
        a, b = start[edges], end[edges]
        while True:
            reached = b[connected[a] & ~connected[b]]
            if not len(reached):
                break
            connected[reached] = True
        palms[:, index] = connected * smoothstep(.18, .38, depth)
    return palms


def smooth_skin(body, fit, source_name, height, held):
    """Smooth fitted weights over shared geometry, including UV seams."""
    coordinates = np.array([tuple(vertex.co) for vertex in body.data.vertices])
    unique, mapping = np.unique(np.round(coordinates, 6), axis=0, return_inverse=True)
    groups = list(body.vertex_groups)
    weights = np.zeros((len(unique), len(groups)))
    counts = np.bincount(mapping)
    for vertex in body.data.vertices:
        for influence in vertex.groups:
            weights[mapping[vertex.index], influence.group] += influence.weight
    weights /= counts[:, None]

    edges = np.array([tuple(edge.vertices) for edge in body.data.edges])
    pairs = np.unique(np.sort(mapping[edges], axis=1), axis=0)
    pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    start, end = np.vstack((pairs, pairs[:, ::-1])).T
    group_ids = {group.name: group.index for group in groups}
    parts = ("Arm", "ForeArm", "Hand")
    arm_ids = [group_ids[side + part] for side, _ in SIDES for part in parts]
    radii = ARM_RADII.get(source_name.split("_")[0], (.044, .040, .040))
    weights[:, arm_ids] = 0
    body_support = weights.sum(axis=1)
    body_only = body_support < .0001
    # The original nearest-bone bind sometimes put an entire piece on the
    # arm. Give any weight outside the fitted sleeve back to the body.
    levels = unique[body_only, 2] / height
    fallback = np.where(levels > .61, group_ids["Spine"],
                        np.where(levels > .49, group_ids["Spine02"], group_ids["Hips"]))
    weights[body_only, fallback] = 1
    weights /= weights.sum(axis=1, keepdims=True)
    body.data.calc_loop_triangles()
    triangles = mapping[np.array([tuple(face.vertices) for face in body.data.loop_triangles])]
    triangles = triangles[np.logical_and.reduce((triangles[:, 0] != triangles[:, 1],
                                                 triangles[:, 1] != triangles[:, 2],
                                                 triangles[:, 2] != triangles[:, 0]))]
    points = unique / height
    votes, body_votes = surface_arm_votes(points, triangles, fit, radii, held)
    palms = trace_palms(points, start, end, votes, body_votes, fit, radii, held)
    rope = ROPE_CONTACT.get(source_name)
    if rope:
        inner, lower, upper = rope
        x, _, z = points.T
        # The inboard side belongs to the rope and tunic. Keep the
        # original torso distribution here, including the waist bend.
        rope_mask = ((1 - smoothstep(inner - .008, inner + .011, x))
                     * smoothstep(.081, .115, x) * smoothstep(.354, lower, z)
                     * (1 - smoothstep(upper, upper + .032, z)))
        palms[:, 0] *= 1 - rope_mask
        body_votes += 2 * rope_mask
    prop = HAND_PROPS.get(source_name)
    if prop:
        side, (a, b), radius = prop
        axis = np.subtract(b, a)
        offset = points - a
        along = np.clip((offset @ axis) / (axis @ axis), 0, 1)
        distance = np.linalg.norm(offset - along[:, None] * axis, axis=1)
        mask = 1 - smoothstep(radius, radius + .014, distance)
        prop_index = [label for label, _ in SIDES].index(side)
        palms[:, prop_index] = np.maximum(palms[:, prop_index], mask)
    for index, (side, sign) in enumerate(SIDES):
        contact = PALM_CONTACTS.get(source_name, {}).get(side)
        if contact:
            lateral, top, front, back = contact
            x, y, z = points.T
            mask = (smoothstep(lateral - .013, lateral + .009, sign * x)
                    * (1 - smoothstep(top - .033, top, z))
                    * smoothstep(front - .022, front, y)
                    * (1 - smoothstep(back, back + .023, y))
                    * smoothstep(.315, .348, z))
            palms[:, index] = np.maximum(palms[:, index], mask)
    arms = []
    for index, (side, sign) in enumerate(SIDES):
        profile = fit[index % len(fit)]
        arm = arm_weights(points, profile, side, radii, side in held)
        if side not in held:
            confirmed = (votes[:, index] > body_votes) & (votes[:, index] > votes[:, 1 - index])
            if np.any(confirmed):
                a, b, c, d = np.asarray(profile) * (sign, 1, 1)
                forearm = 1 - smoothstep(b[2] - .025, b[2] + .023, points[confirmed, 2])
                palm = 1 - smoothstep(c[2] - .024, c[2] + .015, points[confirmed, 2])
                arm[confirmed] = np.column_stack(((1 - forearm) * (1 - palm), forearm * (1 - palm), palm))
            confirmed_body = (body_votes > votes[:, index]) & (points[:, 2] < profile[2][2] + .030)
            arm[confirmed_body] *= .08
            if source_name in FLARED_CUFFS:
                _, elbow, wrist, _ = np.asarray(profile) * (sign, 1, 1)
                x, y, z = points.T
                cuff_radius = np.hypot(x - wrist[0], y - wrist[1])
                cuff = ((1 - smoothstep(.045, .071, cuff_radius))
                        * smoothstep(wrist[2] - .050, wrist[2] - .024, z)
                        * (1 - smoothstep(elbow[2] - .030, elbow[2], z))
                        * smoothstep(abs(wrist[0]) - .067, abs(wrist[0]) - .031, sign*x)
                        * smoothstep(.025, .046, cuff_radius))
                arm *= 1 - cuff[:, None]
                arm[:, 1] += cuff
            arm *= 1 - palms[:, index, None]
            arm[:, 2] += palms[:, index]
        arms.append(arm)
    fitted = np.column_stack(arms)
    if rope:
        fitted[:, :3] *= 1 - rope_mask[:, None]
    arm_support = fitted.sum(axis=1)
    fitted /= np.maximum(arm_support, 1)[:, None]
    weights *= (1 - fitted.sum(axis=1))[:, None]
    weights[:, arm_ids] = fitted

    lengths = np.linalg.norm(unique[start] - unique[end], axis=1)
    edge_weights = 1 / np.maximum(lengths, .006)
    totals = np.bincount(start, weights=edge_weights, minlength=len(unique))
    anchors = weights.copy()
    keep = np.maximum(.24, .82 * smoothstep(.72, 1, fitted.max(axis=1)))[:, None]
    for _ in range(8):
        neighbors = np.zeros_like(weights)
        np.add.at(neighbors, start, weights[end] * edge_weights[:, None])
        neighbors = np.divide(neighbors, totals[:, None], out=weights.copy(), where=totals[:, None] > 0)
        weights = keep * anchors + (1 - keep) * neighbors
    for index, _ in enumerate(SIDES):
        weights *= 1 - palms[:, index, None]
        weights[:, arm_ids[index * len(parts) + 2]] += palms[:, index]
    for group, bounds in EQUIPMENT.get(source_name, ()):
        sign = -1 if group.startswith("Right") else 1
        mask = np.ones(len(points))
        for coordinate, (lo, hi) in zip((points * (sign, 1, 1)).T, bounds):
            mask *= smoothstep(lo - .012, lo, coordinate) * (1 - smoothstep(hi, hi + .012, coordinate))
        weights *= 1 - mask[:, None]
        weights[:, group_ids[group]] += mask
    top = np.argsort(weights, axis=1)[:, -4:]
    values = np.take_along_axis(weights, top, axis=1)
    values[values < .012] = 0
    values /= values.sum(axis=1, keepdims=True)
    vertex_ids = list(range(len(mapping)))
    for group in groups:
        group.remove(vertex_ids)
    for vertex, index in enumerate(mapping):
        for group, weight in zip(top[index], values[index]):
            if weight:
                groups[group].add([vertex], float(weight), "REPLACE")


def pose_frame(clip, phase, sample, rest, parents, height, held, clearance):
    moving = clip in LOCOMOTION
    running = clip == "Run"
    guard = clip == "Alert"
    wave = math.sin(phase)
    breathing = (1 - math.cos(phase)) / 2
    hip_position, hip_rotation = rest["Hips"]
    lower = (.065 if running else .041) if moving else (.013 if guard else .005)
    bounce = (.019 if running else .009) * (1 - math.cos(2 * phase)) / 2 if moving else .0025 * breathing
    sway = (.008 if running else .010) * wave if moving else (.003 if guard else .002) * wave
    displacement = Vector((height * sway, 0, height * (-lower + bounce)))
    twists = {"Hips": axis_rotation((0, 0, 1), (4.5 if running else 3.5) * wave if moving else .4 * wave)}
    pitch = 11.0 if running else (3.0 if moving else (5.0 if guard else .0))
    twists["Spine02"] = axis_rotation((1, 0, 0), pitch * .6 + .6 * breathing)
    twists["Spine"] = (axis_rotation((1, 0, 0), pitch * .4 + .7 * breathing)
                       @ axis_rotation((0, 0, 1), (-7 if running else -5) * wave if moving else .6 * wave))
    twists["Head"] = (axis_rotation((1, 0, 0), -pitch * .5 + .35 * breathing)
                      @ axis_rotation((0, 0, 1), (2.2 if guard else .8) * wave))

    solved = {}
    for side, sign in SIDES:
        thigh_name, shin_name, foot_name, toe_name = (f"{side}{part}" for part in ("UpLeg", "Leg", "Foot", "ToeBase"))
        thigh, shin, foot, toe = [rest[name] for name in (thigh_name, shin_name, foot_name, toe_name)]
        span = (foot[0] - thigh[0]).length
        hip = hip_position + displacement + twists["Hips"] @ (thigh[0] - hip_position)
        ankle = foot[0].copy()
        if moving:
            stride, lift, _ = sample[side]
            ankle.y += span * stride * (.75 if running else .68)
            ankle.z += span * lift * (.56 if running else .62)
        elif guard:
            ankle.y -= sign * height * .018
            ankle.x += sign * height * .008
        knee, ankle = knee_target(hip, ankle, (shin[0] - thigh[0]).length, (foot[0] - shin[0]).length)
        solved[thigh_name] = (hip, fit_rotation(thigh[1], knee - hip))
        solved[shin_name] = (knee, fit_rotation(shin[1], ankle - knee))
        solved[foot_name] = (ankle, foot[1])
        solved[toe_name] = (ankle + toe[0] - foot[0], toe[1])

        if moving:
            drive = sample[side][2]
            shoulder_yaw = -sign * drive * (5 if running else 3)
            twists[f"{side}Shoulder"] = (axis_rotation((0, 0, 1), shoulder_yaw)
                                          @ axis_rotation((1, 0, 0), (-5 if running else -3) * drive))
        else:
            arm_swing = 1.1 if guard else .55
            elbow_bias = 12 if guard else 1.5
            if side in held:
                arm_swing *= .22
                elbow_bias *= .19
            shoulder_bias = -4 if guard and side not in held else 0
            open_arm = 0 if side in held else (-sign * ((3.0 if guard else 1.5) + clearance.get(side, 0)))
            twists[f"{side}Arm"] = (axis_rotation((1, 0, 0), sign * wave * arm_swing + shoulder_bias)
                                    @ axis_rotation((0, 1, 0), open_arm))
            twists[f"{side}ForeArm"] = axis_rotation((1, 0, 0), -elbow_bias + .7 * breathing)

    for name, (point, rotation) in rest.items():
        if name in solved:
            continue
        parent = parents[name]
        local_delta = twists.get(name, Quaternion())
        if parent is None:
            solved[name] = (point + displacement, local_delta @ hip_rotation)
            continue
        old_point, old_rotation = rest[parent]
        new_point, new_rotation = solved[parent]
        inherited = new_rotation @ old_rotation.inverted()
        solved[name] = (new_point + inherited @ (point - old_point), inherited @ local_delta @ rotation)
        if moving and name.endswith("Shoulder"):
            side = name.removesuffix("Shoulder")
            solve_swing(side, 1 if side == "Left" else -1, sample[side][2], running,
                        side in held, clearance.get(side, 0), rest, solved)
    return solved


def animate(source, output, cycles):
    armature = import_armature(source)
    body, = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.parent == armature]
    height = max(vertex.co.z for vertex in body.data.vertices)
    code = source.stem.split("_")[0]
    fit = ARM_FITS[source.stem]
    held = HELD_ARMS.get(code, set())
    clearance = {side: 3 for side, _ in SIDES} if source.stem in FLARED_CUFFS else {}
    if source.stem in HAND_PROPS:
        clearance[HAND_PROPS[source.stem][0]] = 5
    if code == "M01":
        clearance["Left"] = 4
    fit_arms(armature, height, fit)
    bones = armature.data.bones
    smooth_skin(body, fit, source.stem, height, held)
    rest = {bone.name: (bone.head_local.copy(), bone.matrix_local.to_quaternion()) for bone in bones}
    parents = {bone.name: bone.parent.name if bone.parent else None for bone in bones}
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_coordinates = np.empty(3 * len(body.data.vertices), dtype=np.float32)
    for clip, length in CLIPS.items():
        action = bpy.data.actions.new(f"{clip}-loop")
        action.use_fake_user = True
        activate(armature, action)
        previous = {}
        for frame in range(length + 1):
            scene.frame_set(frame)
            index = frame % length
            sample = cycles[clip][index] if clip in cycles else None
            solved = pose_frame(clip, math.tau * index / length, sample, rest, parents, height, held, clearance)
            for name, (position, rotation) in solved.items():
                bone = armature.pose.bones[name]
                parent = parents[name]
                bind_rotation = rest[name][1]
                if parent is None:
                    basis = bind_rotation.inverted() @ rotation
                    bone.location = bind_rotation.inverted() @ (position - rest[name][0])
                else:
                    bind_local = rest[parent][1].inverted() @ bind_rotation
                    pose_local = solved[parent][1].inverted() @ rotation
                    basis = bind_local.inverted() @ pose_local
                if name in previous:
                    basis.make_compatible(previous[name])
                previous[name] = basis.copy()
                bone.rotation_mode = "QUATERNION"
                bone.rotation_quaternion = basis
                bone.keyframe_insert("rotation_quaternion", frame=frame, group=name)
            bpy.context.view_layer.update()
            mesh = body.evaluated_get(depsgraph).data
            mesh.vertices.foreach_get("co", evaluated_coordinates)
            floor = evaluated_coordinates[2::3].min()
            if floor < -0.0005:
                armature.pose.bones["Hips"].location += rest["Hips"][1].inverted() @ Vector((0, 0, -floor))
            armature.pose.bones["Hips"].keyframe_insert("location", frame=frame, group="Hips")
        for channel_bag in action.layers[0].strips[0].channelbags:
            for curve in channel_bag.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"

    armature.animation_data.action = None
    for bone in armature.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    temp = output.with_suffix(".building.glb")
    try:
        bpy.ops.export_scene.gltf(filepath=str(temp), export_format="GLB", export_skins=True,
                                 export_animations=True, export_animation_mode="ACTIONS", export_image_format="AUTO")
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("donor", type=Path)
    parser.add_argument("--pattern", action="append")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    cycles = read_foot_cycles(args.donor)
    args.output.mkdir(parents=True, exist_ok=True)
    sources = sorted({source for pattern in (args.pattern or ["*.glb"]) for source in args.source.glob(pattern)})
    if not sources:
        parser.error("No source models match the pattern")
    for source in sources:
        target = args.output / source.name
        animate(source, target, cycles)
        print("ANIMATED", target.name, json.dumps(CLIPS), flush=True)


if __name__ == "__main__":
    main()

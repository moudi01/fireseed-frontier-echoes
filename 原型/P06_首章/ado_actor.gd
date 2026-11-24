extends Node3D

const Equipment = preload("res://ado_equipment.gd")
const JOINTS := ["upper_arm.L", "forearm.L", "upper_arm.R", "forearm.R", "chest", "head"]
# Angles use the imported model's rest frame. Each card reuses a stable
# supporting stance while keeping its upper-body silhouette distinct.
const POSES := {
	"ready": [Vector3(6, 4, 51), Vector3(19, 0, 3), Vector3(11, -3, -53), Vector3(18, 0, -9), Vector3(-2, 0, 0), Vector3(1, 0, 0)],
	"MG01-A": [Vector3(7, 5, 53), Vector3(20, 0, 9), Vector3(-11, -18, -28), Vector3(27, 0, -18), Vector3(-7, -14, 3), Vector3(2, 9, -2)],
	"MG01-B": [Vector3(40, 2, 41), Vector3(28, 0, 18), Vector3(18, 3, -52), Vector3(24, 0, -17), Vector3(5, 12, -4), Vector3(-3, -9, 2)],
	"MG01-C": [Vector3(9, 2, 58), Vector3(22, 0, 14), Vector3(44, 6, -35), Vector3(38, 0, -18), Vector3(1, -8, 0), Vector3(-6, 6, 2)],
	"sweep": [Vector3(16, 6, 49), Vector3(22, 0, 9), Vector3(33, 36, -17), Vector3(6, 0, -5), Vector3(6, 23, -2), Vector3(-4, -10, 0)],
	"brace": [Vector3(53, 4, 34), Vector3(38, 0, 13), Vector3(31, 6, -53), Vector3(29, 0, -17), Vector3(10, 11, -4), Vector3(-7, -8, 1)],
	"call": [Vector3(13, 4, 59), Vector3(21, 0, 12), Vector3(63, 9, -32), Vector3(13, 0, -9), Vector3(8, -1, 0), Vector3(-5, 0, 0)],
	"hurt": [Vector3(8, -2, 43), Vector3(17, 0, 8), Vector3(8, 0, -47), Vector3(17, 0, -9), Vector3(-11, 6, 4), Vector3(-6, -3, -2)],
	"fallen": [Vector3(6, 2, 27), Vector3(11, 0, 11), Vector3(4, -2, -26), Vector3(13, 0, -14), Vector3(15, 4, 8), Vector3(17, -5, -7)],
	"remembered": [Vector3(4, 3, 63), Vector3(15, 0, 11), Vector3(15, 5, -60), Vector3(24, 0, -19), Vector3(5, 0, 1), Vector3(9, 0, 1)],
}
const RELEASES := {"MG01-A": "sweep", "MG01-B": "brace", "MG01-C": "call"}
const GUARD_ROLL := {"MG01-B": -72.0, "brace": -96.0}

var model: Node3D
var skeleton: Skeleton3D
var bones: Array[int] = []
var rest: Array[Quaternion] = []
var reference_frames: Array[Quaternion] = []
var destination := Vector3.ZERO
var heading := 0.0
var fallen := false
var reduced := false
var pending := ""
var cast_id := ""
var remembering := false
var released := false
var motion: Tween
var pose: Tween


func assemble(scene: PackedScene) -> bool:
	model = scene.instantiate() as Node3D
	add_child(model)
	for child in model.find_children("*", "Skeleton3D", true, false):
		skeleton = child
		break
	if skeleton == null:
		return false
	model.scale = Vector3.ONE * 1.18
	for name in JOINTS:
		var bone := skeleton.find_bone(name)
		if bone < 0:
			return false
		bones.append(bone)
		rest.append(skeleton.get_bone_pose_rotation(bone))
		reference_frames.append(skeleton.get_bone_global_rest(bone).basis.get_rotation_quaternion())
	if not Equipment.attach(skeleton):
		return false
	_pose("ready")
	return true


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	if pose != null and pose.is_valid():
		pose.kill()
	position = point
	destination = point
	rotation.y = yaw
	heading = yaw
	fallen = down
	reduced = still
	released = false
	model.rotation = Vector3(1.22, 0, 0.24) if fallen else Vector3.ZERO
	model.position = Vector3(0, 0.34, -0.76) if fallen else Vector3.ZERO
	_pose("fallen" if fallen else _held_pose())


func travel(point: Vector3, yaw: float) -> void:
	if fallen:
		return
	if motion != null and motion.is_valid():
		motion.kill()
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.22)
	motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.12)


func show_state(action: Dictionary, yaw: float, memory: bool, restore: bool) -> void:
	var next_id := str(action.get("id", ""))
	if next_id == cast_id and memory == remembering and not restore:
		return
	cast_id = next_id
	pending = str(action.get("move_id", ""))
	remembering = memory
	if fallen:
		return
	released = false
	if not pending.is_empty() and not remembering:
		rotation.y = yaw
	_pose(_held_pose(), 0.0 if restore else 0.16)


func attack(move_id: String, yaw: float) -> void:
	if fallen or remembering:
		return
	released = true
	rotation.y = yaw
	_pose(RELEASES.get(move_id, "sweep"), 0.075, true)


func impact() -> void:
	if not fallen and not released and not remembering and not reduced:
		_pose("hurt", 0.06, true)


func _held_pose() -> String:
	if remembering:
		return "remembered"
	return pending if POSES.has(pending) else "ready"


func _pose(name: String, duration := 0.0, recover := false) -> void:
	if pose != null and pose.is_valid():
		pose.kill()
	var target := _orientations(name)
	if duration <= 0.0 or reduced:
		_set_bones(1.0, target, target)
		released = false
		return
	var start: Array[Quaternion] = []
	for bone in bones:
		start.append(skeleton.get_bone_pose_rotation(bone))
	pose = create_tween()
	pose.tween_method(_set_bones.bind(start, target), 0.0, 1.0, duration).set_trans(Tween.TRANS_SINE)
	if recover:
		pose.tween_interval(0.095)
		pose.tween_method(_set_bones.bind(target, _orientations(_held_pose())), 0.0, 1.0, 0.15)
		pose.tween_callback(func():
			released = false
			if pending.is_empty():
				rotation.y = heading)


func _orientations(name: String) -> Array[Quaternion]:
	var rotations: Array[Quaternion] = []
	for i in range(bones.size()):
		var degrees: Vector3 = POSES[name][i]
		var frame := reference_frames[i]
		var turn := Quaternion.from_euler(degrees * (PI / 180.0))
		var rotation := rest[i] * frame.inverse() * turn * frame
		if JOINTS[i] == "forearm.L" and GUARD_ROLL.has(name):
			# Present the shield face during the guard while the arm stays in its strap.
			rotation *= Quaternion(Vector3.UP, deg_to_rad(GUARD_ROLL[name]))
		rotations.append(rotation.normalized())
	return rotations


func _set_bones(weight: float, start: Array[Quaternion], target: Array[Quaternion]) -> void:
	for i in range(bones.size()):
		skeleton.set_bone_pose_rotation(bones[i], start[i].slerp(target[i], weight))

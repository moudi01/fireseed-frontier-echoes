extends Node3D

const JOINTS := ["canopy", "neck", "sac.L", "sac.R"]
const POSES := {
	"ready": [Vector3.ZERO, Vector3.ZERO, Vector3.ZERO, Vector3.ZERO],
	"windup": [Vector3(-13, 0, 0), Vector3(-11, 0, 0), Vector3(-15, 0, -13), Vector3(-9, 0, 8)],
	"windup_turn": [Vector3(-14, 0, 9), Vector3(-10, 0, 0), Vector3(-9, 0, -8), Vector3(-15, 0, 13)],
	"release": [Vector3(24, 0, 0), Vector3(14, 0, 0), Vector3(20, 0, 5), Vector3(20, 0, -5)],
	"rooted": [Vector3(12, 0, 0), Vector3(11, 0, 0), Vector3(8, 0, -9), Vector3(8, 0, 9)],
	"hurt": [Vector3(-9, 0, 8), Vector3(-6, 0, 0), Vector3(-5, 0, 0), Vector3(-5, 0, 0)],
}

var model: Node3D
var skeleton: Skeleton3D
var bones: Array[int] = []
var rest: Array[Quaternion] = []
var reference_frames: Array[Quaternion] = []
var destination := Vector3.ZERO
var heading := 0.0
var fallen := false
var reduced := false
var cast_id := ""
var held_pose := "ready"
var releasing := false
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
	model.scale = Vector3.ONE * 0.76
	for name in JOINTS:
		var bone := skeleton.find_bone(name)
		if bone < 0:
			return false
		bones.append(bone)
		rest.append(skeleton.get_bone_pose_rotation(bone))
		reference_frames.append(skeleton.get_bone_global_rest(bone).basis.get_rotation_quaternion())
	return true


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	position = point
	destination = point
	rotation.y = yaw
	heading = yaw
	fallen = down
	reduced = still
	releasing = false
	model.scale.y = 0.30 if down else 0.76
	_set_pose("rooted" if down else held_pose)


func travel(point: Vector3, yaw: float) -> void:
	if fallen:
		return
	if motion != null and motion.is_valid():
		motion.kill()
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.22)
	if cast_id.is_empty() and held_pose == "ready":
		motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.12)


func show_state(action: Dictionary, rooted: bool, yaw: float, restore: bool) -> void:
	var next_id := str(action.get("id", ""))
	var next_pose := "rooted" if rooted else "ready"
	if not next_id.is_empty():
		next_pose = "windup_turn" if int(action.get("axis_offset", 0)) != 0 else "windup"
	if fallen or (not restore and next_id == cast_id and next_pose == held_pose):
		return
	cast_id = next_id
	held_pose = next_pose
	releasing = false
	rotation.y = yaw
	_set_pose(held_pose, 0.0 if restore else 0.14)


func release_root(yaw: float) -> void:
	if fallen:
		return
	rotation.y = yaw
	if not reduced:
		releasing = true
		_set_pose("release", 0.065, 0.09)


func impact() -> void:
	if not fallen and not reduced and not releasing and held_pose == "ready":
		_set_pose("hurt", 0.055, 0.035)


func _set_pose(name: String, duration := 0.0, hold := 0.0) -> void:
	if pose != null and pose.is_valid():
		pose.kill()
	var target := _orientations(name)
	if reduced or duration <= 0.0:
		_blend(1.0, target, target)
		return
	var start: Array[Quaternion] = []
	for bone in bones:
		start.append(skeleton.get_bone_pose_rotation(bone))
	pose = create_tween()
	pose.tween_method(_blend.bind(start, target), 0.0, 1.0, duration).set_trans(Tween.TRANS_SINE)
	if hold > 0.0:
		pose.tween_interval(hold)
		pose.tween_method(_blend.bind(target, _orientations(held_pose)), 0.0, 1.0, 0.16)
		pose.tween_callback(func(): releasing = false)


func _orientations(name: String) -> Array[Quaternion]:
	var rotations: Array[Quaternion] = []
	for index in bones.size():
		var degrees: Vector3 = POSES[name][index]
		var frame := reference_frames[index]
		var turn := Quaternion.from_euler(degrees * (PI / 180.0))
		rotations.append((rest[index] * frame.inverse() * turn * frame).normalized())
	return rotations


func _blend(weight: float, start: Array[Quaternion], target: Array[Quaternion]) -> void:
	for index in bones.size():
		skeleton.set_bone_pose_rotation(bones[index], start[index].slerp(target[index], weight))

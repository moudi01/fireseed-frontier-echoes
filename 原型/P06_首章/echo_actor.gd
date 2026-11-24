extends "res://mimic_actor.gd"

const BOARD_SCALE := 0.72

var skeleton: Skeleton3D
var shell := -1
var left_stalk := -1
var right_stalk := -1
var shell_rest := Quaternion.IDENTITY
var left_rest := Quaternion.IDENTITY
var right_rest := Quaternion.IDENTITY
var sounding := false
var _last_tilt := INF


func assemble(scene: PackedScene) -> bool:
	model = scene.instantiate() as Node3D
	add_child(model)
	var rigs := model.find_children("*", "Skeleton3D", true, false)
	if rigs.size() != 1:
		return false
	skeleton = rigs[0] as Skeleton3D
	shell = skeleton.find_bone("shell")
	left_stalk = skeleton.find_bone("stalk_01.L")
	right_stalk = skeleton.find_bone("stalk_01.R")
	if shell < 0 or left_stalk < 0 or right_stalk < 0:
		return false
	shell_rest = skeleton.get_bone_pose_rotation(shell)
	left_rest = skeleton.get_bone_pose_rotation(left_stalk)
	right_rest = skeleton.get_bone_pose_rotation(right_stalk)
	scale = Vector3.ONE * BOARD_SCALE
	return true


func pulse() -> void:
	sounding = false
	super.pulse()


func release_echo() -> void:
	sounding = true
	if not fallen and not reduced:
		pulse_left = 0.42


func _update_pose() -> void:
	if skeleton == null:
		return
	var duration := 0.42 if sounding else 0.28
	var wave := sin(PI * clampf(pulse_left / duration, 0.0, 1.0))
	var tilt := -0.12 if winding and not fallen else 0.0
	if not reduced and not fallen:
		tilt += wave * (0.14 if sounding else 0.07)
		tilt -= minf(impact_left * 0.4, 0.06)
	if tilt == _last_tilt:
		return
	_last_tilt = tilt
	skeleton.set_bone_pose_rotation(shell, shell_rest * Quaternion(Vector3.RIGHT, tilt))
	skeleton.set_bone_pose_rotation(left_stalk, left_rest * Quaternion(Vector3.BACK, -tilt * 0.6))
	skeleton.set_bone_pose_rotation(right_stalk, right_rest * Quaternion(Vector3.BACK, tilt * 0.6))

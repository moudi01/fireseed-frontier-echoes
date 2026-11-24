extends "res://mimic_actor.gd"

const BOARD_SCALE := 0.66
const WINGS := ["wing1.L", "wing1.R", "wing2.L", "wing2.R"]

var skeleton: Skeleton3D
var wings: Array[int] = []
var rest: Array[Quaternion] = []
var axes: Array[Vector3] = []
var abdomen := -1
var stinging := false
var _last_flap := INF


func assemble(scene: PackedScene) -> bool:
	model = scene.instantiate() as Node3D
	add_child(model)
	var rigs := model.find_children("*", "Skeleton3D", true, false)
	if rigs.size() != 1:
		return false
	skeleton = rigs[0] as Skeleton3D
	abdomen = skeleton.find_bone("abdomen_02")
	if abdomen < 0:
		return false
	for name in WINGS:
		var index := skeleton.find_bone(name)
		if index < 0:
			return false
		wings.append(index)
		rest.append(skeleton.get_bone_pose_rotation(index))
		axes.append((skeleton.get_bone_global_rest(index).basis.inverse() * Vector3.FORWARD).normalized())
	scale = Vector3.ONE * BOARD_SCALE
	return true


func pulse() -> void:
	stinging = false
	super.pulse()


func release_sting() -> void:
	stinging = true
	super.pulse()


func sting_origin() -> Vector3:
	var tip := skeleton.get_bone_global_pose(abdomen) * Vector3(0, 0.18, 0)
	return skeleton.to_global(tip)


func _update_pose() -> void:
	if skeleton == null:
		return
	var flap := 0.0
	if not fallen:
		flap = 0.12 if winding else 0.0
		if not reduced:
			var active := winding or (stinging and pulse_left > 0.0)
			flap += sin(age * (28.0 if winding else 18.0)) * (0.12 if active else 0.07)
			flap += sin(PI * clampf(pulse_left / 0.28, 0.0, 1.0)) * 0.09
			flap -= impact_left * 0.15
	flap = clampf(flap, -0.28, 0.35)
	if flap == _last_flap:
		return
	_last_flap = flap
	for slot in wings.size():
		var side := -1.0 if slot % 2 == 0 else 1.0
		skeleton.set_bone_pose_rotation(wings[slot], rest[slot] * Quaternion(axes[slot], flap * side))

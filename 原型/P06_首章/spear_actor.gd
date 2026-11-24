extends Node3D

signal clip_started(clip: String)

const SET := "M01_Tripo_01_SetSpear"
const HOLD := "M01_Tripo_02_LaneHold"
const THRUST := "M01_Tripo_03_LaneThrust"
const CANCEL := "M01_Tripo_04_LaneCancel"
const CONTACT := 0.40

var player: AnimationPlayer
var destination: Vector3
var heading := 0.0
var fallen := false
var cast_id := ""
var lock_cells: Array = []
var motion: Tween
var reduced := false
var enemy := false
var skeleton: Skeleton3D
var set_clip := SET
var hold_clip := HOLD
var thrust_clip := THRUST
var cancel_clip := CANCEL


func assemble(scene: PackedScene, hostile := false) -> bool:
	var model := scene.instantiate() as Node3D
	add_child(model)
	player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var rig := model.find_children("*", "Skeleton3D", true, false)
	if player == null or rig.size() != 1 or rig[0].find_bone("SpearTip") < 0:
		return false
	skeleton = rig[0] as Skeleton3D
	enemy = hostile
	if enemy:
		set_clip = "EN17Set"
		hold_clip = "EN17Hold"
		thrust_clip = "EN17Thrust"
		cancel_clip = "EN17Cancel"
	for clip in [set_clip, hold_clip, thrust_clip, cancel_clip]:
		if not player.has_animation(clip):
			return false
	if enemy:
		if skeleton.find_bone("SpearGrip") < 0:
			return false
		_pose(hold_clip, 0.0)
		skeleton.force_update_all_bone_transforms()
		var axis := spear_axis()
		model.rotation.y = -atan2(axis.x, axis.z)
		model.scale = Vector3.ONE * 0.78
	return true


func spear_axis() -> Vector3:
	var grip := skeleton.get_bone_global_pose(skeleton.find_bone("SpearGrip")).origin
	var tip := skeleton.get_bone_global_pose(skeleton.find_bone("SpearTip")).origin
	return (skeleton.global_basis * (tip - grip)).normalized()


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	_stop_motion()
	position = point
	destination = point
	rotation.y = yaw
	heading = yaw
	fallen = down
	reduced = still
	cast_id = ""
	lock_cells.clear()
	visible = not fallen
	_ready_pose()


func travel(point: Vector3, yaw: float) -> void:
	if fallen or not cast_id.is_empty():
		return
	_stop_motion()
	destination = point
	heading = yaw
	_ready_pose()
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.23)
	motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.10)


func windup(id: String, origin: Vector3, yaw: float, cells: Array, restore := false) -> void:
	if fallen or id.is_empty() or id == cast_id:
		return
	_stop_motion()
	cast_id = id
	lock_cells = cells.duplicate()
	position = origin
	rotation.y = yaw
	if reduced or restore:
		if reduced:
			_pose(hold_clip, 0.0)
		else:
			player.play(hold_clip)
			player.advance(0.0)
		skeleton.force_update_all_bone_transforms()
		return
	var lead := 0.46
	_play(set_clip, player.get_animation(set_clip).length / lead)
	motion = create_tween()
	motion.tween_interval(lead)
	motion.tween_callback(_play.bind(hold_clip))


func resolve(id: String, cancelled: bool) -> float:
	if fallen or id.is_empty() or id != cast_id:
		return -1.0
	_stop_motion()
	cast_id = ""
	lock_cells.clear()
	if reduced:
		snap(destination, heading, false, true)
		return 0.0
	var clip := cancel_clip if cancelled else thrust_clip
	_play(clip)
	motion = create_tween()
	motion.tween_interval(player.get_animation(clip).length)
	motion.tween_callback(func() -> void: snap(destination, heading, false, reduced))
	return 0.0 if cancelled else 0.133 if enemy else CONTACT


func _stop_motion() -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	motion = null


func _ready_pose() -> void:
	_pose(set_clip, 0.0)


func _pose(clip: String, time: float) -> void:
	player.play(clip)
	player.seek(time, true)
	player.pause()


func _play(clip: String, speed := 1.0) -> void:
	player.play(clip, 0.05, speed)
	clip_started.emit(clip)

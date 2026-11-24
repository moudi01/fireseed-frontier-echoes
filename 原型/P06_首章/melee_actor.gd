extends "res://shield_actor.gd"

const SET := "GapSet"
const HOLD := "GapHold"
const STRIKE := "GapStrike"
const ABORT := "GapAbort"
const STRIKE_CONTACT := 13.0 / 30.0
const WINDUP_TIME := 0.28
const STRIKE_TIME := 0.46

var gap_cast := ""
var _mesh: MeshInstance3D
var _gap_correctives_active := false


func assemble_gap(scene: PackedScene, travel_library: AnimationLibrary) -> bool:
	if not super.assemble(scene, travel_library, true):
		return false
	for clip in [SET, HOLD, STRIKE, ABORT]:
		if not player.has_animation(clip):
			return false
	for mesh: MeshInstance3D in find_children("*", "MeshInstance3D", true, false):
		if mesh.get_blend_shape_count() > 0:
			_mesh = mesh
			return true
	return false


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	gap_cast = ""
	super.snap(point, yaw, down, still)


func prepare_gap(id: String, yaw: float, reduced: bool, restore: bool) -> void:
	if fallen or id.is_empty() or id == gap_cast:
		return
	_cancel()
	gap_cast = id
	position = destination
	rotation.y = _closest_yaw(yaw)
	if reduced or restore:
		_pose(HOLD, 0.0)
		return
	_play(SET, 0.0, player.get_animation(SET).length / WINDUP_TIME)
	motion = create_tween()
	motion.tween_interval(WINDUP_TIME)
	motion.tween_callback(_play.bind(HOLD))


func release_gap(id: String, yaw: float, contact: Callable, reduced: bool) -> float:
	if fallen or (not gap_cast.is_empty() and gap_cast != id):
		return 0.0
	gap_cast = ""
	_cancel()
	position = destination
	rotation.y = _closest_yaw(yaw)
	if reduced:
		_return_guard()
		return 0.0
	var speed := player.get_animation(STRIKE).length / STRIKE_TIME
	var lag := STRIKE_CONTACT / speed
	_play(STRIKE, 0.0, speed)
	motion = create_tween()
	motion.tween_interval(lag)
	if contact.is_valid():
		motion.tween_callback(contact)
	motion.tween_interval(STRIKE_TIME - lag)
	motion.tween_callback(_return_guard)
	return lag


func cancel_gap(reduced: bool) -> void:
	if gap_cast.is_empty():
		return
	gap_cast = ""
	_cancel()
	if reduced:
		_return_guard()
		return
	_play(ABORT, 0.0, 2.0)
	motion = create_tween()
	motion.tween_interval(player.get_animation(ABORT).length / 2.0)
	motion.tween_callback(_return_guard)


func react(clip: String, lag: float, reduced_motion: bool) -> void:
	if clip == DOWN:
		gap_cast = ""
	elif not gap_cast.is_empty():
		return
	super.react(clip, lag, reduced_motion)


func _play(clip: String, start := 0.0, speed := 1.0, blend := 0.06) -> void:
	_set_correctives(clip)
	super._play(clip, start, speed, blend)


func _pose(clip: String, time: float) -> void:
	_set_correctives(clip)
	super._pose(clip, time)


func _set_correctives(clip: String) -> void:
	var active := clip.begins_with("Gap")
	if not active and _gap_correctives_active:
		for index in range(_mesh.get_blend_shape_count()):
			_mesh.set_blend_shape_value(index, 0.0)
	_gap_correctives_active = active

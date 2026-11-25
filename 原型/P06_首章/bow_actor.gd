extends "res://shield_actor.gd"

const DRAW := "BowLoad"
const AIM := "BowAim"
const LOOSE := "BowRelease"
const CANCEL_LOADED := "BowCancelLoaded"
const BASIC_START := 0.40
const BASIC_RELEASE := 0.68
const SHOT_SPEED := 2.8
const DRAW_TIME := 0.28

var bow_cast := ""
var arrow_mesh: Mesh
var _arrow_heading := 0.0
var _arrow_origin := Vector3.ZERO
var _held_arrow: MeshInstance3D


func assemble_bow(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	if not super.assemble(scene, travel_library, profile, [DRAW, AIM, LOOSE, CANCEL_LOADED]):
		return false
	var rigs := find_children("*", "Skeleton3D", true, false)
	if rigs.size() != 1:
		return false
	var skeleton := rigs[0] as Skeleton3D
	var arrow := find_child("Combat_flying_arrow", true, false) as MeshInstance3D
	if skeleton == null or arrow == null or skeleton.find_bone("FlightArrow") < 0:
		return false
	arrow_mesh = arrow.mesh
	_held_arrow = find_child("Combat_arrow", true, false) as MeshInstance3D
	for sample_name in ["Combat_flying_arrow", "Bow_FlightArrow2", "Bow_HeldArrow2"]:
		var sample := find_child(sample_name, true, false) as Node3D
		if sample != null:
			sample.hide()
	_pose(LOOSE, 0.0)
	skeleton.force_update_all_bone_transforms()
	var launched := skeleton.get_bone_global_pose(skeleton.find_bone("FlightArrow"))
	_arrow_origin = to_local(skeleton.to_global(launched.origin))
	var axis := global_basis.inverse() * skeleton.global_basis * launched.basis.y
	if axis.length_squared() <= 0.9:
		return false
	_arrow_heading = atan2(axis.x, axis.z)
	return arrow_mesh != null


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	bow_cast = ""
	super.snap(point, yaw, down, still)


func prepare_arrow(id: String, yaw: float, reduced: bool, restore: bool) -> void:
	if fallen or id.is_empty() or bow_cast == id:
		return
	_cancel()
	bow_cast = id
	position = destination
	rotation.y = _closest_yaw(yaw - _arrow_heading)
	if reduced or restore:
		_pose(AIM, 0.0)
		return
	_play(DRAW, 0.0, player.get_animation(DRAW).length / DRAW_TIME)
	motion = create_tween()
	motion.tween_interval(DRAW_TIME)
	motion.tween_callback(_play.bind(AIM))


func fire(yaw: float, piercing: bool, reduced: bool) -> float:
	if fallen:
		return 0.0
	bow_cast = ""
	_cancel()
	position = destination
	rotation.y = _closest_yaw(yaw - _arrow_heading)
	if reduced:
		_pose(guard_clip, 0.0)
		return 0.0
	var clip := LOOSE if piercing else attack_clip
	var start := 0.0 if piercing else BASIC_START
	_play(clip, start, SHOT_SPEED)
	motion = create_tween()
	motion.tween_interval((player.get_animation(clip).length - start) / SHOT_SPEED)
	motion.tween_callback(_return_guard)
	return 0.0 if piercing else (BASIC_RELEASE - BASIC_START) / SHOT_SPEED


func arrow_origin() -> Vector3:
	return to_global(_arrow_origin)


func release_axis() -> Vector2:
	var angle := rotation.y + _arrow_heading
	return Vector2(sin(angle), cos(angle))


func aim_bearing(point: Vector3, _locked := false) -> float:
	var line := point - destination
	var length := Vector2(line.x, line.z).length()
	if length < 0.01:
		return heading
	var lateral := _arrow_origin.x * cos(_arrow_heading) - _arrow_origin.z * sin(_arrow_heading)
	return atan2(line.x, line.z) - asin(clampf(lateral / length, -1.0, 1.0))


func cancel_arrow(reduced: bool) -> void:
	if bow_cast.is_empty():
		return
	bow_cast = ""
	_cancel()
	if reduced:
		_pose(guard_clip, 0.0)
		return
	_play(CANCEL_LOADED, 0.0, 2.0)
	motion = create_tween()
	motion.tween_interval(player.get_animation(CANCEL_LOADED).length / 2.0)
	motion.tween_callback(_return_guard)


func react(clip: String, lag: float, reduced_motion: bool) -> void:
	if clip == DOWN:
		bow_cast = ""
	elif not bow_cast.is_empty():
		return
	super.react(clip, lag, reduced_motion)


func _play(clip: String, start := 0.0, speed := 1.0, blend := 0.06) -> void:
	_show_held_arrow(clip)
	super._play(clip, start, speed, blend)


func _pose(clip: String, time: float) -> void:
	_show_held_arrow(clip)
	super._pose(clip, time)


func _show_held_arrow(clip: String) -> void:
	if _held_arrow != null:
		_held_arrow.visible = clip in [DRAW, AIM, attack_clip, CANCEL_LOADED]

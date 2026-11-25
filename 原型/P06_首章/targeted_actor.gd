extends "res://shield_actor.gd"

const PREP_TIME := 0.24

var effect := ""
var pending_field := ""
var cast_id := ""
var raise_clip := ""
var hold_clip := ""
var abort_clip := ""
var release_clip := ""
var release_time := 0.0
var release_entry := 0.0
var release_speed := 1.0
var _socket_origin := Vector3.ZERO
var _socket_heading := 0.0
var _socket_lateral := 0.0


func assemble_targeted(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	var clips: Dictionary = profile.clips
	var release: Dictionary = profile.release
	effect = profile.effect
	pending_field = profile.pending
	raise_clip = clips.raise
	hold_clip = clips.hold
	abort_clip = clips.abort
	release_clip = clips.release
	release_time = release.contact
	release_entry = release.get("entry", 0.0)
	release_speed = release.speed
	if not super.assemble(scene, travel_library, profile, [raise_clip, hold_clip, abort_clip, release_clip]):
		return false
	return _sample_socket(release.socket)


func _sample_socket(socket: String) -> bool:
	if release_speed <= 0.0 or release_entry < 0.0 or release_time < release_entry \
			or release_time > player.get_animation(release_clip).length:
		return false
	var rigs := find_children("*", "Skeleton3D", true, false)
	if rigs.size() != 1:
		return false
	var skeleton := rigs[0] as Skeleton3D
	var index := skeleton.find_bone(socket)
	if index < 0:
		return false
	_pose(release_clip, release_time)
	skeleton.force_update_all_bone_transforms()
	var marker := skeleton.get_bone_global_pose(index)
	_socket_origin = to_local(skeleton.to_global(marker.origin))
	var axis := global_basis.inverse() * skeleton.global_basis * marker.basis.y
	_socket_heading = atan2(axis.x, axis.z)
	_socket_lateral = _socket_origin.x * cos(_socket_heading) - _socket_origin.z * sin(_socket_heading)
	return Vector2(axis.x, axis.z).length_squared() > 0.01


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	cast_id = ""
	super.snap(point, yaw, down, still)


func _play_stop() -> void:
	last_stop = Time.get_ticks_msec()
	_play(stop_clip, 0.0, player.get_animation(stop_clip).length / stop_time)


func _aim(point: Vector3) -> void:
	var line := point - destination
	var length := Vector2(line.x, line.z).length()
	var bearing := heading if length < 0.05 else atan2(line.x, line.z) \
		- asin(clampf(_socket_lateral / length, -1.0, 1.0)) - _socket_heading
	rotation.y = _closest_yaw(bearing)


func prepare_cast(id: String, point: Vector3, reduced: bool, restore: bool) -> void:
	if fallen or id.is_empty() or cast_id == id:
		return
	_cancel()
	cast_id = id
	position = destination
	_aim(point)
	if reduced or restore:
		_pose(hold_clip, 0.0)
		return
	_play(raise_clip, 0.0, player.get_animation(raise_clip).length / PREP_TIME)
	motion = create_tween()
	motion.tween_interval(PREP_TIME)
	motion.tween_callback(_play.bind(hold_clip))


func release_cast(point: Vector3, reduced: bool) -> float:
	if fallen:
		return 0.0
	cast_id = ""
	_cancel()
	position = destination
	_aim(point)
	if reduced:
		_pose(guard_clip, 0.0)
		return 0.0
	_play(release_clip, release_entry, release_speed, 0.0)
	motion = create_tween()
	motion.tween_interval((player.get_animation(release_clip).length - release_entry) / release_speed)
	motion.tween_callback(_return_guard)
	return (release_time - release_entry) / release_speed


func cast_origin() -> Vector3:
	return to_global(_socket_origin)


func cast_axis() -> Vector2:
	var angle := rotation.y + _socket_heading
	return Vector2(sin(angle), cos(angle))


func cancel_cast(reduced: bool) -> void:
	if cast_id.is_empty():
		return
	cast_id = ""
	_cancel()
	if reduced:
		_pose(guard_clip, 0.0)
		return
	_play(abort_clip, 0.0, 2.0)
	motion = create_tween()
	motion.tween_interval(player.get_animation(abort_clip).length / 2.0)
	motion.tween_callback(_return_guard)


func react(clip: String, lag: float, reduced_motion: bool) -> void:
	if clip == DOWN:
		cast_id = ""
	elif not cast_id.is_empty():
		return
	super.react(clip, lag, reduced_motion)

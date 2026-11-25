extends "res://bow_actor.gd"

const LOCK := "BreachAim"
const KEEP := "BreachHold"
const BREACH := "BreachRelease"
const LOWER := "BreachCancel"
const RELOAD := "BreachReload"
const BASIC_RELEASE_TIME := 0.88
const BREACH_RELEASE_TIME := 11.0 / 30.0
const LOCK_TIME := 0.26
const BOLT_RECOVERY_SPEED := 4.6

var _launches: Dictionary = {}
var _locked := false


func assemble_crossbow(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	if not super.assemble(scene, travel_library, profile, [LOCK, KEEP, BREACH, LOWER, RELOAD]):
		return false
	var rigs := find_children("*", "Skeleton3D", true, false)
	var bolt := find_child("Combat_flying_arrow", true, false) as MeshInstance3D
	if rigs.size() != 1 or bolt == null or bolt.mesh == null:
		return false
	arrow_mesh = bolt.mesh
	bolt.hide()
	var skeleton := rigs[0] as Skeleton3D
	if not _read_mount(skeleton, false, "FlightArrow", attack_clip, BASIC_RELEASE_TIME) \
			or not _read_mount(skeleton, true, "BreachMuzzle", BREACH, BREACH_RELEASE_TIME):
		return false
	return true


func _read_mount(skeleton: Skeleton3D, locked: bool, socket: String, clip: String, release_time: float) -> bool:
	var index := skeleton.find_bone(socket)
	if index < 0:
		return false
	_pose(clip, release_time)
	skeleton.force_update_all_bone_transforms()
	var marker := skeleton.get_bone_global_pose(index)
	var axis := global_basis.inverse() * skeleton.global_basis * marker.basis.y
	var origin := to_local(skeleton.to_global(marker.origin))
	var bearing := atan2(axis.x, axis.z)
	_launches[locked] = {"origin": origin, "bearing": bearing,
		"lateral": origin.x * cos(bearing) - origin.z * sin(bearing)}
	return Vector2(axis.x, axis.z).length_squared() > 0.01


func aim_bearing(point: Vector3, locked := false) -> float:
	var line := point - destination
	var length := Vector2(line.x, line.z).length()
	if length < 0.01:
		return heading
	return atan2(line.x, line.z) - asin(clampf(float(_launches[locked].lateral) / length, -1.0, 1.0))


func arrow_origin() -> Vector3:
	return to_global(_launches[_locked].origin)


func release_axis() -> Vector2:
	var bearing := rotation.y + float(_launches[_locked].bearing)
	return Vector2(sin(bearing), cos(bearing))


func prepare_arrow(id: String, yaw: float, reduced: bool, restore: bool) -> void:
	if fallen or id.is_empty() or bow_cast == id:
		return
	_cancel()
	bow_cast = id
	_locked = true
	position = destination
	rotation.y = _closest_yaw(yaw - float(_launches[true].bearing))
	if reduced or restore:
		_pose(KEEP, 0.0)
		return
	_play(LOCK, 0.0, player.get_animation(LOCK).length / LOCK_TIME)
	motion = create_tween()
	motion.tween_interval(LOCK_TIME)
	motion.tween_callback(_play.bind(KEEP))


func fire(yaw: float, piercing: bool, reduced: bool) -> float:
	if fallen:
		return 0.0
	bow_cast = ""
	_locked = piercing
	_cancel()
	position = destination
	rotation.y = _closest_yaw(yaw - float(_launches[piercing].bearing))
	if reduced:
		_pose(guard_clip, 0.0)
		return 0.0
	var clip := BREACH if piercing else attack_clip
	var entry := 0.0 if piercing else 0.50
	var release_time := BREACH_RELEASE_TIME if piercing else BASIC_RELEASE_TIME
	_play(clip, entry, BOLT_RECOVERY_SPEED, 0.0)
	motion = create_tween()
	motion.tween_interval((player.get_animation(clip).length - entry) / BOLT_RECOVERY_SPEED)
	if piercing:
		motion.tween_callback(_play.bind(RELOAD, 0.0, 7.2, 0.0))
		motion.tween_interval(player.get_animation(RELOAD).length / 7.2)
	motion.tween_callback(_return_guard)
	return (release_time - entry) / BOLT_RECOVERY_SPEED


func cancel_arrow(reduced: bool) -> void:
	if bow_cast.is_empty():
		return
	bow_cast = ""
	_cancel()
	if reduced:
		_pose(guard_clip, 0.0)
		return
	_play(LOWER, 0.0, 3.1)
	motion = create_tween()
	motion.tween_interval(player.get_animation(LOWER).length / 3.1)
	motion.tween_callback(_return_guard)

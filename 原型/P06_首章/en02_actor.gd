extends "res://shield_actor.gd"

const MOVE_ID := "EN02-A"
const WINDUP_TIME := 0.24
const RELEASE_TIME := 0.34

var active_cast := ""
var active_move := ""
var shell_seam := false
var _skill_clips: Dictionary


func assemble_charge(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	_skill_clips = profile.skill_clips
	return assemble(scene, travel_library, profile, _skill_clips.values())


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	shell_seam = false
	super.snap(point, yaw, down, still)


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen:
		return 0.0
	match kind:
		"prepare":
			if move_id != MOVE_ID or cast_id.is_empty() or cast_id == active_cast:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id
			rotation.y = _closest_yaw(yaw)
			if restore or reduced:
				_pose(_skill_clips.hold, 0.0)
			else:
				var clip: String = _skill_clips.raise
				_play(clip, 0.0, player.get_animation(clip).length / WINDUP_TIME)
				motion = create_tween()
				motion.tween_interval(WINDUP_TIME)
				motion.tween_callback(_play.bind(_skill_clips.hold))
		"cancel":
			if cast_id != active_cast or cast_id.is_empty():
				return 0.0
			active_cast = ""
			active_move = ""
			_cancel()
			if reduced:
				_pose(guard_clip, 0.0)
			else:
				var clip: String = _skill_clips.cancel
				_play(clip, 0.0, player.get_animation(clip).length / RELEASE_TIME)
				motion = create_tween()
				motion.tween_interval(RELEASE_TIME)
				motion.tween_callback(_return_guard)
		"hit":
			if active_cast.is_empty() and not shell_seam and player.assigned_animation != _skill_clips.release:
				react(HIT, 0.0, reduced)
	return 0.0


func release_charge(yaw: float, landing: Vector3, reduced: bool) -> float:
	active_cast = ""
	active_move = ""
	_cancel()
	rotation.y = _closest_yaw(yaw)
	if reduced:
		position = landing
		_pose(guard_clip, 0.0)
		return 0.0
	var clip: String = _skill_clips.release
	_play(clip, 0.0, player.get_animation(clip).length / RELEASE_TIME)
	motion = create_tween()
	motion.tween_property(self, "position", landing, RELEASE_TIME).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	motion.tween_callback(_return_guard)
	return RELEASE_TIME * 0.40


func apply_shell_seam(active: bool, reduced: bool, restore: bool) -> void:
	if fallen or (active == shell_seam and not restore):
		return
	shell_seam = active
	var clip: String = _skill_clips.shell_seam
	if active:
		_cancel()
		position = destination
		if reduced or restore:
			_pose(clip, 0.0)
		else:
			_play(clip)
	elif player.assigned_animation == clip:
		if reduced:
			_pose(guard_clip, 0.0)
		else:
			_return_guard()

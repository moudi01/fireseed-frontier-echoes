extends "res://shield_actor.gd"

const RAISE_CLIP := "HeroRaise"
const HOLD_CLIP := "HeroHold"
const RELEASE_CLIP := "HeroRelease"
const CANCEL_CLIP := "HeroCancel"
const SKILL_A_CLIP := "HeroSkillA"
const BLOCK_CLIP := "HeroBlock"
const WINDUP_TIME := 0.28
const MODEL_YAW_OFFSET := {
	"H03": -2.0,
	"H06": -2.0,
}

var hero_kind := ""
var cast_id := ""
var cast_move := ""
var _attack_speed := 1.0


func assemble_hero(scene: PackedScene, travel_library: AnimationLibrary, kind: String) -> bool:
	hero_kind = kind
	guard_clip = "HeroIdle"
	move_clip = "HeroWalk"
	stop_clip = "HeroStop"
	attack_clip = "HeroAttack"
	hit_clip = "HeroHit"
	down_clip = "HeroDown"
	stop_time = 0.16
	attack_entry = 0.08
	attack_contact = 0.28
	var required := [guard_clip, stop_clip, attack_clip, hit_clip, down_clip]
	if not _attach_model(scene, travel_library, required, false):
		return false
	var yaw_offset: float = float(MODEL_YAW_OFFSET.get(kind, 0.0))
	if absf(yaw_offset) > 0.001 and get_child_count() > 0:
		var visual := get_child(get_child_count() - 1) as Node3D
		if visual != null:
			visual.rotation.y += yaw_offset
	var attack_len := player.get_animation(attack_clip).length
	_attack_speed = clampf(attack_len / 0.85, 1.0, 2.8)
	return true


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	cast_id = ""
	cast_move = ""
	super.snap(point, yaw, down, still)


func attack(yaw: float, contact: Callable) -> float:
	if fallen:
		return 0.0
	cast_id = ""
	cast_move = ""
	var still_travelling := player.current_animation == "board/" + move_clip
	var stopping := player.current_animation == stop_clip
	var remaining := maxf(0.0, stop_time - player.current_animation_position) if stopping else 0.0
	var turn := 0.07
	_cancel()
	motion = create_tween()
	motion.tween_property(self, "rotation:y", _closest_yaw(yaw), turn)
	if still_travelling:
		motion.parallel().tween_property(self, "position", destination, turn)
		motion.tween_callback(_play_stop)
		motion.tween_interval(stop_time)
		remaining = stop_time
	elif stopping:
		motion.tween_interval(remaining)
	var total_dur := player.get_animation(attack_clip).length / _attack_speed
	var hit_lag := minf(attack_contact, total_dur * 0.45)
	motion.tween_callback(_play.bind(attack_clip, 0.0, _attack_speed))
	motion.tween_interval(hit_lag)
	if contact.is_valid():
		motion.tween_callback(contact)
	motion.tween_interval(maxf(0.05, total_dur - hit_lag))
	motion.tween_callback(_return_guard)
	return turn + remaining + hit_lag


func prepare_skill(id: String, move: String, yaw: float, reduced: bool, restore: bool) -> void:
	if fallen or id.is_empty() or id == cast_id:
		return
	_cancel()
	cast_id = id
	cast_move = move
	position = destination
	rotation.y = _closest_yaw(yaw)
	var has_hold := player.has_animation(HOLD_CLIP)
	var has_raise := player.has_animation(RAISE_CLIP)
	if reduced or restore:
		if has_hold:
			_pose(HOLD_CLIP, 0.0)
		else:
			_pose(guard_clip, 0.0)
		return
	if has_raise and has_hold:
		var raise_speed := maxf(1.0, player.get_animation(RAISE_CLIP).length / WINDUP_TIME)
		_play(RAISE_CLIP, 0.0, raise_speed)
		motion = create_tween()
		motion.tween_interval(WINDUP_TIME)
		motion.tween_callback(_play.bind(HOLD_CLIP))
	elif has_hold:
		_play(HOLD_CLIP)


func release_skill(id: String, move: String, yaw: float, contact: Callable, reduced: bool) -> float:
	if fallen or (not cast_id.is_empty() and not id.is_empty() and cast_id != id):
		return 0.0
	cast_id = ""
	cast_move = ""
	_cancel()
	position = destination
	rotation.y = _closest_yaw(yaw)
	if reduced:
		_return_guard()
		return 0.0
	var clip := _choose_skill_clip(move)
	var raw_len := player.get_animation(clip).length
	var speed := clampf(raw_len / 0.95, 1.0, 2.6)
	var total_dur := raw_len / speed
	var lag := minf(0.32, total_dur * 0.42)
	_play(clip, 0.0, speed)
	motion = create_tween()
	motion.tween_interval(lag)
	if contact.is_valid():
		motion.tween_callback(contact)
	motion.tween_interval(maxf(0.05, total_dur - lag))
	motion.tween_callback(_return_guard)
	return lag


func cancel_skill(reduced: bool) -> void:
	if cast_id.is_empty():
		return
	cast_id = ""
	cast_move = ""
	_cancel()
	if reduced or not player.has_animation(CANCEL_CLIP):
		_return_guard()
		return
	var speed := maxf(1.0, player.get_animation(CANCEL_CLIP).length / 0.26)
	_play(CANCEL_CLIP, 0.0, speed)
	motion = create_tween()
	motion.tween_interval(player.get_animation(CANCEL_CLIP).length / speed)
	motion.tween_callback(_return_guard)


func react(clip: String, lag: float, reduced_motion: bool) -> void:
	if clip == DOWN:
		cast_id = ""
		cast_move = ""
	elif not cast_id.is_empty():
		return
	if clip == BLOCK:
		if player.has_animation(BLOCK_CLIP):
			_react_custom(BLOCK_CLIP, lag, reduced_motion)
			return
		super.react(HIT, lag, reduced_motion)
		return
	super.react(clip, lag, reduced_motion)


func _react_custom(clip_name: String, lag: float, reduced_motion: bool) -> void:
	if fallen or reduced_motion:
		return
	_cancel()
	motion = create_tween()
	if lag > 0.0:
		motion.tween_interval(lag)
	motion.tween_callback(func() -> void:
		position = destination
		rotation.y = heading
		_play(clip_name)
	)
	motion.tween_interval(player.get_animation(clip_name).length)
	motion.tween_callback(_play.bind(guard_clip))


func _choose_skill_clip(move: String) -> String:
	if move.ends_with("-B") and player.has_animation(RELEASE_CLIP):
		return RELEASE_CLIP
	if move.ends_with("-A") and player.has_animation(SKILL_A_CLIP):
		return SKILL_A_CLIP
	if player.has_animation(RELEASE_CLIP):
		return RELEASE_CLIP
	if player.has_animation(SKILL_A_CLIP):
		return SKILL_A_CLIP
	return attack_clip

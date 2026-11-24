extends Node3D

signal clip_started(clip: String)

const GUARD := "ShieldGuard"
const MOVE := "ShieldAdvance"
const STOP := "ShieldStop"
const ATTACK := "ShieldAttack"
const BLOCK := "ShieldBlock"
const HIT := "ShieldHit"
const DOWN := "ShieldDown"

var player: AnimationPlayer
var destination: Vector3
var heading := 0.0
var fallen := false
var motion: Tween
var last_stop := -1
var melee := false
var guard_clip := GUARD
var move_clip := MOVE
var stop_clip := STOP
var attack_clip := ATTACK
var hit_clip := HIT
var down_clip := DOWN
var stop_time := 0.20
var attack_entry := 0.14
var attack_contact := 0.25


func assemble(scene: PackedScene, travel_library: AnimationLibrary, use_melee := false) -> bool:
	melee = use_melee
	if melee:
		guard_clip = "MeleeGuard"
		move_clip = "MeleeAdvance"
		stop_clip = "MeleeStop"
		attack_clip = "MeleeAttack"
		hit_clip = "MeleeHit"
		down_clip = "MeleeDown"
		stop_time = 0.16
		attack_entry = 0.10
		attack_contact = 0.22
	var required := [guard_clip, stop_clip, attack_clip, hit_clip, down_clip]
	if not melee:
		required.append(BLOCK)
	return _attach_model(scene, travel_library, required)


func _attach_model(scene: PackedScene, travel_library: AnimationLibrary, required: Array, require_root := true) -> bool:
	var model := scene.instantiate() as Node3D
	var animation_player := model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if animation_player == null:
		model.free()
		return false
	for clip in required:
		if not animation_player.has_animation(clip):
			model.free()
			return false
	if travel_library == null:
		travel_library = _in_place_from_player(animation_player, move_clip, require_root)
		if travel_library == null:
			model.free()
			return false
	animation_player.add_animation_library("board", travel_library)
	player = animation_player
	add_child(model)
	return true


static func in_place_travel(scene: PackedScene, clip := MOVE, require_root := true) -> AnimationLibrary:
	var source := scene.instantiate()
	var original := source.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var library := _in_place_from_player(original, clip, require_root)
	source.free()
	return library


static func _in_place_from_player(original: AnimationPlayer, clip: String, require_root: bool) -> AnimationLibrary:
	if original == null or not original.has_animation(clip):
		return null
	var animation := original.get_animation(clip).duplicate() as Animation
	var neutralized := false
	for track in range(animation.get_track_count()):
		var path := animation.track_get_path(track)
		if animation.track_get_type(track) != Animation.TYPE_POSITION_3D or path.get_subname_count() == 0 or path.get_subname(0) != &"Root":
			continue
		var origin: Vector3 = animation.track_get_key_value(track, 0)
		for key in range(animation.track_get_key_count(track)):
			var point: Vector3 = animation.track_get_key_value(track, key)
			animation.track_set_key_value(track, key, Vector3(origin.x, point.y, origin.z))
		neutralized = true
		break
	if require_root and not neutralized:
		return null
	var library := AnimationLibrary.new()
	library.add_animation(clip, animation)
	return library


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	_cancel()
	position = point
	destination = point
	rotation.y = yaw
	heading = yaw
	last_stop = -1
	fallen = down
	if down:
		_pose(down_clip, player.get_animation(down_clip).length)
	else:
		_pose(guard_clip, 0.0)
		if not still:
			player.play(guard_clip)


func _cancel() -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	motion = null


func _pose(clip: String, time: float) -> void:
	player.play(clip)
	player.seek(time, true)
	player.pause()


func _play(clip: String, start := 0.0, speed := 1.0, blend := 0.06) -> void:
	player.play(clip, blend, speed)
	if start > 0.0:
		player.seek(start, true)
	clip_started.emit(clip.get_file())


func travel(point: Vector3, yaw: float) -> void:
	if fallen:
		return
	_cancel()
	destination = point
	heading = yaw
	var duration := 0.26
	_play("board/" + move_clip, 0.0, 2.8)
	motion = create_tween()
	motion.tween_property(self, "rotation:y", _closest_yaw(yaw), 0.08)
	motion.parallel().tween_property(self, "position", point, duration).set_trans(Tween.TRANS_SINE)
	motion.tween_callback(_play_stop)
	motion.tween_interval(stop_time)
	motion.tween_callback(_play.bind(guard_clip))


func _play_stop() -> void:
	last_stop = Time.get_ticks_msec()
	_play(stop_clip)


func _closest_yaw(yaw: float) -> float:
	return rotation.y + angle_difference(rotation.y, yaw)


func attack(yaw: float, contact: Callable) -> float:
	if fallen:
		return 0.0
	var still_travelling := player.current_animation == "board/" + move_clip
	var stopping := player.current_animation == stop_clip
	var remaining := maxf(0.0, stop_time - player.current_animation_position) if stopping else 0.0
	var entering := attack_entry if still_travelling or stopping or (last_stop >= 0 and Time.get_ticks_msec() - last_stop < 280) else 0.0
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
	motion.tween_callback(_play.bind(attack_clip, entering))
	motion.tween_interval(attack_contact - entering)
	if contact.is_valid():
		motion.tween_callback(contact)
	motion.tween_interval(player.get_animation(attack_clip).length - attack_contact)
	motion.tween_callback(_return_guard)
	return turn + remaining + attack_contact - entering


func _return_guard() -> void:
	rotation.y = heading
	_play(guard_clip)


func react(clip: String, lag: float, reduced_motion: bool) -> void:
	if fallen:
		return
	if reduced_motion:
		if clip == DOWN:
			snap(destination, heading, true, true)
			clip_started.emit(down_clip)
		return
	var reaction_clip := down_clip if clip == DOWN else hit_clip if clip == HIT else clip
	_cancel()
	motion = create_tween()
	if lag > 0:
		motion.tween_interval(lag)
	motion.tween_callback(func() -> void:
		position = destination
		rotation.y = heading
		fallen = clip == DOWN
		_play(reaction_clip, 0.14 if clip == BLOCK else 0.0)
	)
	var remaining := player.get_animation(reaction_clip).length - (0.14 if clip == BLOCK else 0.0)
	motion.tween_interval(remaining)
	if clip == DOWN:
		motion.tween_callback(_pose.bind(down_clip, player.get_animation(down_clip).length))
	else:
		motion.tween_callback(_play.bind(guard_clip))

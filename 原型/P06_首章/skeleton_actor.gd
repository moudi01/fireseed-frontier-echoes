extends Node3D

signal clip_started(clip: String)

var model: Node3D
var player: AnimationPlayer
var skeleton: Skeleton3D
var nock := -1
var kind := ""
var archer := false
var destination := Vector3.ZERO
var heading := 0.0
var guarded := false
var cast_id := ""
var fallen := false
var still := false
var motion: Tween


func assemble(scene: PackedScene, unit: String) -> bool:
	kind = unit
	archer = kind == "EN22"
	model = scene.instantiate() as Node3D
	add_child(model)
	model.scale = Vector3.ONE * 0.78
	player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var rigs := model.find_children("*", "Skeleton3D", true, false)
	if player == null or rigs.size() != 1:
		return false
	skeleton = rigs[0] as Skeleton3D
	nock = skeleton.find_bone("BoneBowNock")
	if archer and nock < 0:
		return false
	var clips := ["Ready", "Hold", "Draw", "Release", "Quick"] if archer else ["Ready", "Hold", "Raise", "Cut", "GuardCut"]
	for clip in clips:
		if not player.has_animation(kind + clip):
			return false
	player.animation_finished.connect(_finished)
	return true


func snap(point: Vector3, yaw: float, down: bool, reduced := false) -> void:
	_stop_motion()
	position = point
	destination = point
	heading = yaw
	rotation.y = yaw
	fallen = down
	still = reduced
	cast_id = ""
	model.position = Vector3(0.0, 0.25, -0.64) if down else Vector3.ZERO
	model.rotation.x = 1.42 if down else 0.0
	_idle()


func travel(point: Vector3, yaw: float) -> void:
	if fallen or not cast_id.is_empty():
		return
	_stop_motion()
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.22)
	motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.12)


func observe_guard(active: bool, restore: bool, reduced: bool) -> void:
	var changed := active != guarded or reduced != still
	guarded = active
	still = reduced
	if restore or (changed and player.current_animation in [kind + "Ready", kind + "Hold"]):
		_idle()


func raise_blade() -> void:
	if not fallen and not still:
		_start("Raise")


func swing() -> void:
	if not fallen and not still and player.current_animation != kind + "Raise":
		_start("GuardCut" if guarded else "Cut")


func draw_bow(id: String, point: Vector3, yaw: float, restore: bool, reduced: bool) -> void:
	if fallen or id.is_empty() or (cast_id == id and still == reduced and not restore):
		return
	cast_id = id
	still = reduced
	_stop_motion()
	position = point
	rotation.y = yaw
	if restore or reduced:
		_idle()
	else:
		_start("Draw")


func release_arrow(id: String, yaw: float, locked: bool, reduced: bool) -> float:
	if fallen or (locked and cast_id != id) or (not locked and not cast_id.is_empty()):
		return -1.0
	cast_id = ""
	still = reduced
	rotation.y = yaw
	if still:
		_idle()
		return 0.0
	_start("Release" if locked else "Quick", 1.0 if locked else 1.75)
	return 0.067 if locked else 0.36


func cancel_bow(reduced: bool) -> void:
	cast_id = ""
	still = reduced
	rotation.y = heading
	_idle()


func arrow_origin() -> Vector3:
	skeleton.force_update_all_bone_transforms()
	var local := skeleton.get_bone_global_pose(nock).origin + Vector3(0, 0.035, -0.079)
	return skeleton.to_global(local)


func _start(label: String, speed := 1.0) -> void:
	var clip := kind + label
	player.play(clip, 0.04, speed)
	player.seek(0.0, true)
	clip_started.emit(clip)


func _finished(_clip: StringName) -> void:
	if archer and cast_id.is_empty():
		rotation.y = heading
	_idle()


func _idle() -> void:
	player.play(kind + ("Hold" if not fallen and (guarded or not cast_id.is_empty()) else "Ready"))
	player.advance(0.0)
	if still or fallen:
		player.pause()
	skeleton.force_update_all_bone_transforms()


func _stop_motion() -> void:
	if motion != null and motion.is_valid():
		motion.kill()

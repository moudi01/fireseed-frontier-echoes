extends Node3D

signal clip_started(clip: String)

const READY := "EN04Ready"
const RAISE := "EN04Raise"
const HOLD := "EN04Hold"
const BRACE := "EN04Brace"
const CUT := "EN04Cut"
const GUARDED_CUT := "EN04GuardedCut"
const HURT := "EN04Hurt"

var model: Node3D
var player: AnimationPlayer
var skeleton: Skeleton3D
var plate_bone := -1
var destination := Vector3.ZERO
var heading := 0.0
var guarded := false
var fallen := false
var still := false
var motion: Tween


func assemble(scene: PackedScene) -> bool:
	model = scene.instantiate() as Node3D
	add_child(model)
	model.scale = Vector3.ONE * 0.78
	player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var rigs := model.find_children("*", "Skeleton3D", true, false)
	if player == null or rigs.size() != 1:
		return false
	skeleton = rigs[0] as Skeleton3D
	plate_bone = skeleton.find_bone("RoundShieldGrip")
	if plate_bone < 0:
		return false
	for clip in [READY, RAISE, HOLD, BRACE, CUT, GUARDED_CUT, HURT]:
		if not player.has_animation(clip):
			return false
	player.animation_finished.connect(_finished)
	return true


func snap(point: Vector3, yaw: float, down: bool, reduced := false) -> void:
	if motion != null and motion.is_valid():
		motion.kill()
	position = point
	destination = point
	heading = yaw
	rotation.y = yaw
	fallen = down
	still = reduced
	model.rotation = Vector3(1.38, 0.0, 0.24) if down else Vector3.ZERO
	model.position = Vector3(0.0, 0.31, -0.63) if down else Vector3.ZERO
	_idle()


func travel(point: Vector3, yaw: float) -> void:
	if fallen:
		return
	if motion != null and motion.is_valid():
		motion.kill()
	motion = create_tween()
	motion.tween_property(self, "position", point, 0.22)
	motion.parallel().tween_property(self, "rotation:y", rotation.y + angle_difference(rotation.y, yaw), 0.12)


func observe_protection(active: bool, restore: bool, reduced: bool) -> void:
	var motion_changed := still != reduced
	still = reduced
	var changed := active != guarded
	guarded = active
	if restore or motion_changed or (changed and player.current_animation in [READY, HOLD]):
		_idle()


func raise_shield() -> void:
	if not fallen and not still:
		_start(RAISE)


func brace() -> void:
	if not fallen and not still:
		_start(BRACE)


func strike() -> void:
	if not fallen and not still and player.current_animation != RAISE:
		_start(GUARDED_CUT if guarded else CUT)


func impact() -> void:
	if not fallen and not still and not guarded and player.current_animation == READY:
		_start(HURT)


func _start(clip: String) -> void:
	# Repeated entries are distinct committed events, even if the clip is still playing.
	player.play(clip, 0.06)
	player.seek(0.0, true)
	clip_started.emit(clip)


func _finished(_clip: StringName) -> void:
	_idle()


func _idle() -> void:
	var clip := HOLD if guarded and not fallen else READY
	player.play(clip)
	player.advance(0.0)
	if fallen or still:
		player.pause()
	skeleton.force_update_all_bone_transforms()

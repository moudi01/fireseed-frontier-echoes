extends "res://shield_actor.gd"

## Standalone ADMIN (管理员) boss actor for shared CITADEL_RING (90 cells).
## Matches shield_actor.gd / shield_stage.gd general-cast contract with distinct
## non-color-dependent silhouettes for:
## - ADMIN-A (秩序抹除·扩域, 7-cell magic), ADMIN-B (维护权限, 48 self-shield),
## - ADMIN-C (格式化脉冲·扩域, 15-cell magic), ADMIN-D (法令反噬, enabled by the authority after breaking a law),
## - boss_law_named (点名 84->92 拍) and formatting_started (139 拍格式化) independent state poses.

const ADMIN_MODEL := "res://assets/enemies/ADMIN_Board.glb"
const ADMIN_MOVES := ["ADMIN-A", "ADMIN-B", "ADMIN-C", "ADMIN-D"]

const SKILL_CLIPS := {
	"ADMIN-A": {
		"raise": "AdminEraseRaise",
		"hold": "AdminEraseHold",
		"release": "AdminEraseRelease",
		"cancel": "AdminEraseCancel",
	},
	"ADMIN-B": {
		"raise": "AdminShieldRaise",
		"hold": "AdminShieldHold",
		"release": "AdminShieldRelease",
		"cancel": "AdminShieldCancel",
	},
	"ADMIN-C": {
		"raise": "AdminPulseRaise",
		"hold": "AdminPulseHold",
		"release": "AdminPulseRelease",
		"cancel": "AdminPulseCancel",
	},
	"ADMIN-D": {
		"raise": "AdminBacklashRaise",
		"hold": "AdminBacklashHold",
		"release": "AdminBacklashRelease",
		"cancel": "AdminBacklashCancel",
	},
}

const STATE_CLIPS := {
	"law_named": {"raise": "AdminLawNameRaise", "hold": "AdminLawNameHold"},
	"formatting": {"raise": "AdminFormatRaise", "hold": "AdminFormatHold"},
}

const PROFILE := {
	"model": ADMIN_MODEL,
	"side": "enemy",
	"assembly": "admin",
	"head_height": 2.26,
	"contact_height": 2.40,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"clips": {
		"guard": "AdminIdle",
		"travel": "AdminWalk",
		"stop": "AdminStop",
		"attack": "AdminAttack",
		"hit": "AdminHit",
		"down": "AdminDown",
	},
}

const RAISE_TIME := 0.30
const CAST_SPEED := 1.45

var active_cast := ""
var active_move := ""
var active_state := ""
var _skill_clips: Dictionary


static func is_available() -> bool:
	return ResourceLoader.exists(ADMIN_MODEL, "PackedScene")


static func supports_move(move_id: String) -> bool:
	return move_id in ADMIN_MOVES


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func assemble_admin(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	_skill_clips = SKILL_CLIPS
	var required: Array[String] = _required_skill_clips()
	for clips: Dictionary in STATE_CLIPS.values():
		required.append_array(clips.values())
	return super.assemble(scene, travel_library, profile, required) and find_child("ADMIN_LawRack", true, false) is Node3D


func assemble_guard(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	_skill_clips = {profile.move: profile.skill_clips}
	return super.assemble(scene, travel_library, profile, _required_skill_clips())


func _required_skill_clips() -> Array[String]:
	var names: Array[String] = []
	for clips: Dictionary in _skill_clips.values():
		names.append_array(clips.values())
	return names


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	active_state = ""
	super.snap(point, yaw, down, still)


func apply_state_pose(state_key: String, yaw: float, reduced: bool, restore := false) -> void:
	if active_state == state_key and not restore:
		return
	var former: Dictionary = STATE_CLIPS.get(active_state, {})
	var standing := str(player.assigned_animation) in former.values()
	active_state = state_key
	var clip := str(player.assigned_animation)
	if fallen or not active_cast.is_empty() or clip.ends_with("Release") or clip.ends_with("Cancel"):
		return
	if not STATE_CLIPS.has(state_key):
		if standing:
			_settle_pose(reduced)
		return
	var bank: Dictionary = STATE_CLIPS[state_key]
	_cancel()
	position = destination
	rotation.y = _closest_yaw(yaw)
	if reduced or restore:
		_pose(bank.hold, 0.0)
		return
	var raise_clip: String = bank.raise
	_play(raise_clip, 0.0, player.get_animation(raise_clip).length / RAISE_TIME)
	motion = create_tween()
	motion.tween_interval(RAISE_TIME)
	motion.tween_callback(_play.bind(bank.hold))


func _settle_pose(reduced: bool) -> void:
	rotation.y = heading
	var state: Dictionary = STATE_CLIPS.get(active_state, {})
	var idle: String = state.get("hold", guard_clip)
	if reduced:
		_pose(idle, 0.0)
	else:
		_play(idle)


func _return_guard() -> void:
	_settle_pose(false)


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen and kind != "down":
		return 0.0
	var bank: Dictionary = _skill_clips.get(move_id, {})
	if bank.is_empty() and kind in ["prepare", "release", "cancel"]:
		return 0.0
	match kind:
		"prepare":
			if cast_id.is_empty() or active_cast == cast_id:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id
			position = destination
			rotation.y = _closest_yaw(yaw)
			if reduced or restore:
				_pose(bank.hold, 0.0)
				return 0.0
			var raise_clip: String = bank.raise
			_play(raise_clip, 0.0, player.get_animation(raise_clip).length / RAISE_TIME)
			motion = create_tween()
			motion.tween_interval(RAISE_TIME)
			motion.tween_callback(_play.bind(bank.hold))
			return 0.0
		"release":
			active_cast = ""
			active_move = ""
			_cancel()
			position = destination
			rotation.y = _closest_yaw(yaw)
			if reduced:
				_settle_pose(true)
				return 0.0
			var rel_clip: String = bank.release
			_play(rel_clip, 0.0, CAST_SPEED)
			var dur := player.get_animation(rel_clip).length / CAST_SPEED
			motion = create_tween()
			motion.tween_interval(dur)
			motion.tween_callback(_return_guard)
			return dur * 0.35
		"cancel":
			active_cast = ""
			active_move = ""
			_cancel()
			position = destination
			rotation.y = _closest_yaw(yaw)
			if reduced:
				_settle_pose(true)
				return 0.0
			var can_clip: String = bank.cancel
			_play(can_clip, 0.0, CAST_SPEED)
			var dur := player.get_animation(can_clip).length / CAST_SPEED
			motion = create_tween()
			motion.tween_interval(dur)
			motion.tween_callback(_return_guard)
			return 0.0
		"attack":
			_cancel()
			position = destination
			rotation.y = _closest_yaw(yaw)
			if reduced:
				_pose(guard_clip, 0.0)
				return 0.0
			_play(attack_clip, 0.0, CAST_SPEED)
			var dur := player.get_animation(attack_clip).length / CAST_SPEED
			motion = create_tween()
			motion.tween_interval(dur)
			motion.tween_callback(_return_guard)
			return dur * 0.35
		"hit":
			var current := str(player.assigned_animation)
			var state_raise: String = STATE_CLIPS.get(active_state, {}).get("raise", "")
			if not active_cast.is_empty() or reduced or current.ends_with("Release") or current.ends_with("Cancel") \
					or (not state_raise.is_empty() and current == state_raise):
				return 0.0
			_cancel()
			_play(hit_clip, 0.0, 1.2)
			var dur := player.get_animation(hit_clip).length / 1.2
			motion = create_tween()
			motion.tween_interval(dur)
			motion.tween_callback(_return_guard)
			return 0.0
		"rest":
			active_cast = ""
			active_move = ""
			active_state = ""
			_cancel()
			if reduced:
				_pose(guard_clip, 0.0)
			else:
				_return_guard()
			return 0.0
	return 0.0

extends "res://shield_actor.gd"

## Standalone ADMIN (管理员) boss actor for shared CITADEL_RING (90 cells).
## Matches shield_actor.gd / shield_stage.gd general-cast contract with distinct
## non-color-dependent silhouettes for:
## - ADMIN-A (秩序抹除·扩域, 7-cell magic), ADMIN-B (维护权限, 48 self-shield),
## - ADMIN-C (格式化脉冲·扩域, 15-cell magic), ADMIN-D (法令反噬, directed/定向 only — no A-line sample),
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
var _rack_node: Node3D


static func is_available() -> bool:
	return ResourceLoader.exists(ADMIN_MODEL, "PackedScene")


static func supports_move(move_id: String) -> bool:
	return move_id in ADMIN_MOVES


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func assemble_admin(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	var required: Array[String] = []
	for move_id in ADMIN_MOVES:
		for key in ["raise", "hold", "release", "cancel"]:
			required.append(str(SKILL_CLIPS[move_id][key]))
	for st in STATE_CLIPS.keys():
		for key in ["raise", "hold"]:
			required.append(str(STATE_CLIPS[st][key]))
	if not super.assemble(scene, travel_library, profile, required):
		return false
	_rack_node = find_child("ADMIN_LawRack", true, false) as Node3D
	return _rack_node != null


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	active_state = ""
	super.snap(point, yaw, down, still)


func apply_state_pose(state_key: String, yaw: float, reduced: bool, restore := false) -> void:
	if fallen or not active_cast.is_empty():
		return
	if not STATE_CLIPS.has(state_key):
		active_state = ""
		if reduced:
			_pose(guard_clip, 0.0)
		else:
			_return_guard()
		return
	active_state = state_key
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


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen and kind != "down":
		return 0.0
	if kind in ["law_named", "formatting"]:
		apply_state_pose(kind, yaw, reduced, restore)
		return 0.0
	var bank: Dictionary = SKILL_CLIPS.get(move_id, SKILL_CLIPS["ADMIN-A"])
	match kind:
		"prepare":
			if cast_id.is_empty() or active_cast == cast_id:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id if SKILL_CLIPS.has(move_id) else "ADMIN-A"
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
				_pose(guard_clip, 0.0)
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
				_pose(guard_clip, 0.0)
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
			if not active_cast.is_empty() or reduced:
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

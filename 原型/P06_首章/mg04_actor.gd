extends "res://shield_actor.gd"

# Standalone MG04 (Helan) boss actor for RG05 · FORGE_CROSSING.
# Supports distinct A (物理重铸裁线), B (本人44私盾), and C (双锚魔法 — 非锤击)
# raise/hold/release/cancel clips driven by authoritative battle events, plus reduced_motion and restore.

const MG04_MODEL := "res://assets/enemies/MG04_Board.glb"
const MG04_MOVES := ["MG04-A", "MG04-B", "MG04-C"]

const SKILL_CLIPS := {
	"MG04-A": {
		"raise": "Mg04CleaveRaise",
		"hold": "Mg04CleaveHold",
		"release": "Mg04CleaveRelease",
		"cancel": "Mg04CleaveCancel",
	},
	"MG04-B": {
		"raise": "Mg04ShieldRaise",
		"hold": "Mg04ShieldHold",
		"release": "Mg04ShieldRelease",
		"cancel": "Mg04ShieldCancel",
	},
	"MG04-C": {
		"raise": "Mg04AnchorRaise",
		"hold": "Mg04AnchorHold",
		"release": "Mg04AnchorRelease",
		"cancel": "Mg04AnchorCancel",
	},
}

const PROFILE := {
	"model": MG04_MODEL,
	"side": "enemy",
	"assembly": "mg04",
	"head_height": 2.28,
	"contact_height": 2.42,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"clips": {
		"guard": "Mg04Idle",
		"travel": "Mg04Walk",
		"stop": "Mg04Stop",
		"attack": "Mg04Attack",
		"hit": "Mg04Hit",
		"down": "Mg04Down",
	},
}

const RAISE_TIME := 0.30
const CAST_SPEED := 1.45

var active_cast := ""
var active_move := ""
var _hammer_node: Node3D


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func assemble_mg04(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	var required: Array[String] = []
	for move_id in MG04_MOVES:
		for key in ["raise", "hold", "release", "cancel"]:
			required.append(SKILL_CLIPS[move_id][key])
	if not super.assemble(scene, travel_library, profile, required):
		return false
	_hammer_node = find_child("MG04_Hammer", true, false) as Node3D
	return _hammer_node != null


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	super.snap(point, yaw, down, still)


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen and kind != "down":
		return 0.0
	var bank: Dictionary = SKILL_CLIPS.get(move_id, SKILL_CLIPS["MG04-A"])
	match kind:
		"prepare":
			if cast_id.is_empty() or active_cast == cast_id:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id if SKILL_CLIPS.has(move_id) else "MG04-A"
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
		"attack":
			active_cast = ""
			active_move = ""
			_cancel()
			position = destination
			rotation.y = _closest_yaw(yaw)
			if reduced:
				_pose(guard_clip, 0.0)
				return 0.0
			_play(attack_clip, 0.0, CAST_SPEED)
			var adur := player.get_animation(attack_clip).length / CAST_SPEED
			motion = create_tween()
			motion.tween_interval(adur)
			motion.tween_callback(_return_guard)
			return adur * 0.35
		"cancel":
			if active_cast.is_empty() and cast_id.is_empty():
				return 0.0
			var cancel_bank: Dictionary = SKILL_CLIPS.get(active_move if not active_move.is_empty() else move_id, SKILL_CLIPS["MG04-A"])
			active_cast = ""
			active_move = ""
			_cancel()
			if reduced:
				_pose(guard_clip, 0.0)
				return 0.0
			var c_clip: String = cancel_bank.cancel
			_play(c_clip, 0.0, 1.8)
			motion = create_tween()
			motion.tween_interval(player.get_animation(c_clip).length / 1.8)
			motion.tween_callback(_return_guard)
			return 0.0
		"hit":
			if not active_cast.is_empty():
				return 0.0
			react(hit_clip, 0.0, reduced)
			return 0.0
		"down":
			active_cast = ""
			active_move = ""
			react(down_clip, 0.0, reduced)
			return 0.0
	return 0.0

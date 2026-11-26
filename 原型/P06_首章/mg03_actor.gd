extends "res://shield_actor.gd"

# Standalone MG03 (Yilei) boss actor for RG04 · SALT_CROSSING.
# Supports distinct A (失名诵读), B (空页私盾), and C (抹名针) raise/hold/release/cancel clips
# driven by authoritative battle events, plus reduced_motion and restore handling.

const MG03_MODEL := "res://assets/enemies/MG03_Board.glb"
const MG03_MOVES := ["MG03-A", "MG03-B", "MG03-C"]

const SKILL_CLIPS := {
	"MG03-A": {
		"raise": "Mg03ChantRaise",
		"hold": "Mg03ChantHold",
		"release": "Mg03ChantRelease",
		"cancel": "Mg03ChantCancel",
	},
	"MG03-B": {
		"raise": "Mg03ShieldRaise",
		"hold": "Mg03ShieldHold",
		"release": "Mg03ShieldRelease",
		"cancel": "Mg03ShieldCancel",
	},
	"MG03-C": {
		"raise": "Mg03NeedleRaise",
		"hold": "Mg03NeedleHold",
		"release": "Mg03NeedleRelease",
		"cancel": "Mg03NeedleCancel",
	},
}

const PROFILE := {
	"model": MG03_MODEL,
	"side": "enemy",
	"assembly": "mg03",
	"head_height": 2.02,
	"contact_height": 2.15,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"clips": {
		"guard": "Mg03Idle",
		"travel": "Mg03Walk",
		"stop": "Mg03Stop",
		"attack": "Mg03Attack",
		"hit": "Mg03Hit",
		"down": "Mg03Down",
	},
}

const RAISE_TIME := 0.30
const CAST_SPEED := 1.45

var active_cast := ""
var active_move := ""
var _needle_node: Node3D
var _ledger_node: Node3D


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func assemble_mg03(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	var required: Array[String] = []
	for move_id in MG03_MOVES:
		for key in ["raise", "hold", "release", "cancel"]:
			required.append(SKILL_CLIPS[move_id][key])
	if not super.assemble(scene, travel_library, profile, required):
		return false
	_needle_node = find_child("MG03_Needle", true, false) as Node3D
	_ledger_node = find_child("MG03_Ledger", true, false) as Node3D
	return _needle_node != null and _ledger_node != null


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	super.snap(point, yaw, down, still)


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen and kind != "down":
		return 0.0
	var bank: Dictionary = SKILL_CLIPS.get(move_id, SKILL_CLIPS["MG03-A"])
	match kind:
		"prepare":
			if cast_id.is_empty() or active_cast == cast_id:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id if SKILL_CLIPS.has(move_id) else "MG03-A"
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
			var cancel_bank: Dictionary = SKILL_CLIPS.get(active_move if not active_move.is_empty() else move_id, SKILL_CLIPS["MG03-A"])
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

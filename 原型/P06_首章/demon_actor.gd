extends "res://shield_actor.gd"

## Standalone DEMON (初生魔王) boss actor for shared CITADEL_RING (90 cells).
## Matches shield_actor.gd / shield_stage.gd general-cast contract with distinct
## non-color-dependent silhouettes for DEMON-A (临摹号令), DEMON-B (样本回声, from recorded basic attacks),
## DEMON-C (未解之问 52私盾), DEMON-D (见证崩流 W3可打断), and MIMIC-* (镜像习得/适应技能).

const DEMON_MODEL := "res://assets/enemies/DEMON_Board.glb"
const DEMON_MOVES := ["DEMON-A", "DEMON-B", "DEMON-C", "DEMON-D"]
const MIMIC_PREFIX := "MIMIC-"

const SKILL_CLIPS := {
	"DEMON-A": {
		"raise": "DemonOrderRaise",
		"hold": "DemonOrderHold",
		"release": "DemonOrderRelease",
		"cancel": "DemonOrderCancel",
	},
	"DEMON-B": {
		"raise": "DemonEchoRaise",
		"hold": "DemonEchoHold",
		"release": "DemonEchoRelease",
		"cancel": "DemonEchoCancel",
	},
	"DEMON-C": {
		"raise": "DemonShieldRaise",
		"hold": "DemonShieldHold",
		"release": "DemonShieldRelease",
		"cancel": "DemonShieldCancel",
	},
	"DEMON-D": {
		"raise": "DemonCollapseRaise",
		"hold": "DemonCollapseHold",
		"release": "DemonCollapseRelease",
		"cancel": "DemonCollapseCancel",
	},
	"MIMIC": {
		"raise": "DemonMimicRaise",
		"hold": "DemonMimicHold",
		"release": "DemonMimicRelease",
		"cancel": "DemonMimicCancel",
	},
}

const PROFILE := {
	"model": DEMON_MODEL,
	"side": "enemy",
	"assembly": "demon",
	"head_height": 2.12,
	"contact_height": 2.24,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"clips": {
		"guard": "DemonIdle",
		"travel": "DemonWalk",
		"stop": "DemonStop",
		"attack": "DemonAttack",
		"hit": "DemonHit",
		"down": "DemonDown",
	},
}

const RAISE_TIME := 0.30
const CAST_SPEED := 1.45

var active_cast := ""
var active_move := ""


static func is_available() -> bool:
	return ResourceLoader.exists(DEMON_MODEL, "PackedScene")


static func supports_move(move_id: String) -> bool:
	return move_id in DEMON_MOVES or move_id.begins_with(MIMIC_PREFIX)


static func skill_family(move_id: String) -> String:
	if SKILL_CLIPS.has(move_id):
		return move_id
	if move_id.begins_with(MIMIC_PREFIX):
		return "MIMIC"
	return "DEMON-A"


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func assemble_demon(scene: PackedScene, travel_library: AnimationLibrary, profile: Dictionary) -> bool:
	var required: Array[String] = []
	for fam in SKILL_CLIPS.keys():
		for key in ["raise", "hold", "release", "cancel"]:
			required.append(str(SKILL_CLIPS[fam][key]))
	return super.assemble(scene, travel_library, profile, required)


func snap(point: Vector3, yaw: float, down: bool, still := false) -> void:
	active_cast = ""
	active_move = ""
	super.snap(point, yaw, down, still)


func apply_boss_event(kind: String, move_id: String, cast_id: String, yaw: float,
		reduced: bool, restore := false) -> float:
	if fallen and kind != "down":
		return 0.0
	var fam := skill_family(move_id)
	var bank: Dictionary = SKILL_CLIPS[fam]
	match kind:
		"prepare":
			if cast_id.is_empty() or active_cast == cast_id:
				return 0.0
			_cancel()
			active_cast = cast_id
			active_move = move_id if supports_move(move_id) else "DEMON-A"
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
		"mirror_learn":
			if not active_cast.is_empty():
				return 0.0
			_cancel()
			var m_bank: Dictionary = SKILL_CLIPS["MIMIC"]
			if reduced:
				_pose(m_bank.hold, 0.0)
				return 0.0
			var m_raise: String = m_bank.raise
			_play(m_raise, 0.0, player.get_animation(m_raise).length / RAISE_TIME)
			motion = create_tween()
			motion.tween_interval(RAISE_TIME)
			motion.tween_callback(_return_guard)
			return 0.0
		"rest":
			active_cast = ""
			active_move = ""
			_cancel()
			if reduced:
				_pose(guard_clip, 0.0)
			else:
				_return_guard()
			return 0.0
	return 0.0

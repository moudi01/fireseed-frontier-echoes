extends "res://bow_actor.gd"

const MG02_MODEL := "res://assets/enemies/MG02_Board.glb"
const MG02_MOVES := ["MG02-A", "MG02-B", "MG02-C"]

const PROFILE := {
	"model": MG02_MODEL,
	"side": "enemy",
	"assembly": "bow",
	"head_height": 1.92,
	"contact_height": 2.05,
	"prefetch": true,
	"stagger": true,
	"require_root_track": false,
	"clips": {
		"guard": "BowGuard",
		"travel": "BowWalk",
		"stop": "BowStop",
		"attack": "BowAttack",
		"hit": "BowHitFront",
		"down": "BowDown",
	},
}


static func profile_entry(script_ref: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = script_ref
	return row


func apply_boss_event(kind: String, cast_id: String, yaw: float, reduced: bool, restore := false) -> float:
	match kind:
		"prepare":
			prepare_arrow(cast_id, yaw, reduced, restore)
			return 0.0
		"release":
			return fire(yaw, true, reduced)
		"attack":
			return fire(yaw, false, reduced)
		"cancel":
			cancel_arrow(reduced)
			return 0.0
		"hit":
			react(hit_clip, 0.0, reduced)
			return 0.0
		"down":
			react(down_clip, 0.0, reduced)
			return 0.0
	return 0.0

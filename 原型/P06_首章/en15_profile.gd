class_name En15Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN15 (空腔合唱体).
## Plugs directly into generic shield_actor.gd with optional: true and zero root XY drift.
## EN15-A (同调): raise/hold/release/cancel expressed via chest cavity & pipes; authority drives targets/healing.

const EN15_MODEL := "res://assets/enemies/EN15_Board.glb"

const PROFILE := {
	"model": EN15_MODEL,
	"side": "enemy",
	"head_height": 1.68,
	"contact_height": 1.80,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN15-A",
	"clips": {
		"guard": "EN15Idle",
		"travel": "EN15Walk",
		"stop": "EN15Stop",
		"attack": "EN15Attack",
		"hit": "EN15Hit",
		"down": "EN15Down",
	},
	"skill_clips": {
		"raise": "EN15ChoirRaise",
		"hold": "EN15ChoirHold",
		"release": "EN15ChoirRelease",
		"cancel": "EN15ChoirCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

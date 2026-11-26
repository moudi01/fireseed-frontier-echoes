class_name En07Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary lake enemy EN07 (葬铃鹭).
## Grounded wading heron with bell sac; EN07-A (扫喙, W1) is strictly in-place
## (neck coil / horizontal beak sweep / cancel; target push remains authority-driven).

const EN07_MODEL := "res://assets/enemies/EN07_Board.glb"

const PROFILE := {
	"model": EN07_MODEL,
	"side": "enemy",
	"head_height": 1.56,
	"contact_height": 1.68,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN07-A",
	"clips": {
		"guard": "EN07Idle",
		"travel": "EN07Walk",
		"stop": "EN07Stop",
		"attack": "EN07Attack",
		"hit": "EN07Hit",
		"down": "EN07Down",
	},
	"skill_clips": {
		"raise": "EN07SweepRaise",
		"hold": "EN07SweepHold",
		"release": "EN07SweepRelease",
		"cancel": "EN07SweepCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

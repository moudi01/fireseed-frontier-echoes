class_name En19Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN19 (哥布林劫掠者).
## Low crouched short-blade flanker; EN19-A (侧袭短刀, W1) is strictly in-place
## (side-raised blade / slash / cancel, zero fake forward dash).

const EN19_MODEL := "res://assets/enemies/EN19_Board.glb"

const PROFILE := {
	"model": EN19_MODEL,
	"side": "enemy",
	"head_height": 1.18,
	"contact_height": 1.30,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN19-A",
	"clips": {
		"guard": "EN19Idle",
		"travel": "EN19Walk",
		"stop": "EN19Stop",
		"attack": "EN19Attack",
		"hit": "EN19Hit",
		"down": "EN19Down",
	},
	"skill_clips": {
		"raise": "EN19FlankRaise",
		"hold": "EN19FlankHold",
		"release": "EN19FlankRelease",
		"cancel": "EN19FlankCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

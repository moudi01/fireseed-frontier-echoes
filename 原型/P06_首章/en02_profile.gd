class_name En02Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN02 (磐壳奔兽).
## Plugs directly into generic shield_actor.gd with optional: true and zero root XY drift.
## EN02-A (沉角冲线): raise/hold/release/cancel; EN02ShellSeam: independent +1 beat post-release cue.

const EN02_MODEL := "res://assets/enemies/EN02_Board.glb"

const PROFILE := {
	"model": EN02_MODEL,
	"side": "enemy",
	"head_height": 1.24,
	"contact_height": 1.36,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN02-A",
	"clips": {
		"guard": "EN02Idle",
		"travel": "EN02Walk",
		"stop": "EN02Stop",
		"attack": "EN02Attack",
		"hit": "EN02Hit",
		"down": "EN02Down",
	},
	"skill_clips": {
		"raise": "EN02ChargeRaise",
		"hold": "EN02ChargeHold",
		"release": "EN02ChargeRelease",
		"cancel": "EN02ChargeCancel",
		"shell_seam": "EN02ShellSeam",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

class_name En08Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN08 (雾袋孢母).
## Plugs into generic enemy_cast / shield_actor with optional: true and zero root XY drift.
## EN08-A (结雾, W1): raise/hold/release/cancel expressed purely via crown & shoulder
## mist-sac inflation, clench, puff-release, and relaxation; stealth/reveal remain authority-driven.

const EN08_MODEL := "res://assets/enemies/EN08_Board.glb"

const PROFILE := {
	"model": EN08_MODEL,
	"side": "enemy",
	"head_height": 1.12,
	"contact_height": 1.24,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN08-A",
	"clips": {
		"guard": "EN08Idle",
		"travel": "EN08Walk",
		"stop": "EN08Stop",
		"attack": "EN08Attack",
		"hit": "EN08Hit",
		"down": "EN08Down",
	},
	"skill_clips": {
		"raise": "EN08VeilRaise",
		"hold": "EN08VeilHold",
		"release": "EN08VeilRelease",
		"cancel": "EN08VeilCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

class_name En20Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN20 (哥布林弩手).
## Two-handed crossbowman with explicit CrossbowMuzzle socket; EN20-A (钉脚弩, W2)
## provides raise/hold/release/cancel only (projectile & ray-block remain authority-driven).

const EN20_MODEL := "res://assets/enemies/EN20_Board.glb"

const PROFILE := {
	"model": EN20_MODEL,
	"side": "enemy",
	"head_height": 1.24,
	"contact_height": 1.36,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN20-A",
	"muzzle_socket": "CrossbowMuzzle",
	"clips": {
		"guard": "EN20Idle",
		"travel": "EN20Walk",
		"stop": "EN20Stop",
		"attack": "EN20Attack",
		"hit": "EN20Hit",
		"down": "EN20Down",
	},
	"skill_clips": {
		"raise": "EN20PinRaise",
		"hold": "EN20PinHold",
		"release": "EN20PinRelease",
		"cancel": "EN20PinCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

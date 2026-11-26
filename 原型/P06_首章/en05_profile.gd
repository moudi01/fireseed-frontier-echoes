class_name En05Profile
extends RefCounted

## Standalone generic-Actor profile for #15 ordinary enemy EN05 (盐脉鳗).
## Plugs into generic cast/enemy actor with optional: true and zero root XY drift.
## EN05-A (盐弧, W2): raise/hold/release/cancel expressed via raised coiled head,
## flared salt-crystal crests, and sweeping arc; locked hexes & side/rear weakness
## remain strictly authority-driven.

const EN05_MODEL := "res://assets/enemies/EN05_Board.glb"

const PROFILE := {
	"model": EN05_MODEL,
	"side": "enemy",
	"head_height": 0.72,
	"contact_height": 0.92,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN05-A",
	"clips": {
		"guard": "EN05Idle",
		"travel": "EN05Walk",
		"stop": "EN05Stop",
		"attack": "EN05Attack",
		"hit": "EN05Hit",
		"down": "EN05Down",
	},
	"skill_clips": {
		"raise": "EN05ArcRaise",
		"hold": "EN05ArcHold",
		"release": "EN05ArcRelease",
		"cancel": "EN05ArcCancel",
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

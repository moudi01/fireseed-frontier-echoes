class_name AdminGuardProfiles
extends RefCounted

## Standalone generic-Actor profile definitions for #14 finale ADMIN guards:
## - EN16 校准巡弋体 (EN16-A 划界脉冲: magic range 3, W2)
## - EN18 界标钳 (EN18-A 闭合: edge_block range 2, W1)
## Both mechanical bodies plug directly into generic shield_actor.gd with optional: true.

const EN16_MODEL := "res://assets/enemies/EN16_Board.glb"
const EN18_MODEL := "res://assets/enemies/EN18_Board.glb"

const EN16_PROFILE := {
	"model": EN16_MODEL,
	"side": "enemy",
	"head_height": 1.66,
	"contact_height": 1.78,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN16-A",
	"clips": {
		"guard": "EN16Idle",
		"travel": "EN16Walk",
		"stop": "EN16Stop",
		"attack": "EN16Attack",
		"hit": "EN16Hit",
		"down": "EN16Down",
	},
	"skill_clips": {
		"raise": "EN16PulseRaise",
		"hold": "EN16PulseHold",
		"release": "EN16PulseRelease",
		"cancel": "EN16PulseCancel",
	},
}

const EN18_PROFILE := {
	"model": EN18_MODEL,
	"side": "enemy",
	"head_height": 1.62,
	"contact_height": 1.74,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN18-A",
	"clips": {
		"guard": "EN18Idle",
		"travel": "EN18Walk",
		"stop": "EN18Stop",
		"attack": "EN18Attack",
		"hit": "EN18Hit",
		"down": "EN18Down",
	},
	"skill_clips": {
		"raise": "EN18ClampRaise",
		"hold": "EN18ClampHold",
		"release": "EN18ClampRelease",
		"cancel": "EN18ClampCancel",
	},
}


static func entries(actor_script: Script) -> Dictionary:
	var en16 := EN16_PROFILE.duplicate(true)
	en16["script"] = actor_script
	var en18 := EN18_PROFILE.duplicate(true)
	en18["script"] = actor_script
	return {"EN16": en16, "EN18": en18}

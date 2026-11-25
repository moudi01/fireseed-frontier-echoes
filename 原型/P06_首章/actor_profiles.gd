extends RefCounted

# Presentation only. Move and pending keys come from the existing battle view.
const TARGETED := {
	"M02": {
		"model": "res://assets/M02_Tripo_AidRuntime.glb", "effect": "aid",
		"move": "M02-A", "pending": "aid_pending",
		"clips": {"guard": "AidIdle", "travel": "AidWalk", "stop": "AidStop",
			"attack": "AidFire", "hit": "AidHit", "down": "AidDown", "raise": "AidRaise",
			"hold": "AidHold", "abort": "AidCancel", "release": "AidFire"},
		"release": {"socket": "AidMuzzle", "contact": 23.0 / 30.0, "entry": 0.42, "speed": 4.4},
	},
	"M04": {
		"model": "res://assets/M04_MistRuntime.glb", "effect": "mist",
		"move": "M04-A", "pending": "mist_pending", "attack_contact": 0.46,
		"clips": {"guard": "MistIdle", "travel": "MistWalk", "stop": "MistStop",
			"attack": "MistAttack", "hit": "MistHit", "down": "MistDown", "raise": "MistRaise",
			"hold": "MistHold", "abort": "MistCancel", "release": "MistRelease"},
		"release": {"socket": "MistPalm", "contact": 12.0 / 30.0, "speed": 4.0},
	},
}

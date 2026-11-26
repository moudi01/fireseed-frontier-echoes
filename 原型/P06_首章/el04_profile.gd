class_name El04Profile
extends RefCounted

## Standalone generic-Actor profile for #15 elite lake enemy EL04 (剪潮鹭).
## Grounded elite wading heron with twin crown crest & scissor-forked tail.
## Provides separate in-place clip sets for EN07-A (扫喙) and EL04-B (公开侧步):
## actual 1-hex sidestep & push displacement remain strictly authority-driven.

const EL04_MODEL := "res://assets/enemies/EL04_Board.glb"

const PROFILE := {
	"model": EL04_MODEL,
	"side": "enemy",
	"head_height": 1.76,
	"contact_height": 1.88,
	"prefetch": true,
	"optional": true,
	"require_root_track": false,
	"move": "EN07-A",
	"clips": {
		"guard": "EL04Idle",
		"travel": "EL04Walk",
		"stop": "EL04Stop",
		"attack": "EL04Attack",
		"hit": "EL04Hit",
		"down": "EL04Down",
	},
	"skill_clips": {
		"raise": "EL04SweepRaise",
		"hold": "EL04SweepHold",
		"release": "EL04SweepRelease",
		"cancel": "EL04SweepCancel",
	},
	"step_clips": {
		"raise": "EL04StepRaise",
		"hold": "EL04StepHold",
		"release": "EL04StepRelease",
		"cancel": "EL04StepCancel",
	},
	"move_clips": {
		"EN07-A": {
			"raise": "EL04SweepRaise",
			"hold": "EL04SweepHold",
			"release": "EL04SweepRelease",
			"cancel": "EL04SweepCancel",
		},
		"EL04-B": {
			"raise": "EL04StepRaise",
			"hold": "EL04StepHold",
			"release": "EL04StepRelease",
			"cancel": "EL04StepCancel",
		},
	},
}


static func entry(actor_script: Script) -> Dictionary:
	var row := PROFILE.duplicate(true)
	row["script"] = actor_script
	return row

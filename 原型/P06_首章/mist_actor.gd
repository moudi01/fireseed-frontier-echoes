extends "res://targeted_actor.gd"


func assemble_mist(scene: PackedScene, travel_library: AnimationLibrary) -> bool:
	guard_clip = "MistIdle"
	move_clip = "MistWalk"
	stop_clip = "MistStop"
	attack_clip = "MistAttack"
	hit_clip = "MistHit"
	down_clip = "MistDown"
	raise_clip = "MistRaise"
	hold_clip = "MistHold"
	abort_clip = "MistCancel"
	release_clip = "MistRelease"
	attack_contact = 0.46
	release_time = 12.0 / 30.0
	release_speed = 4.0
	return _attach_caster(scene, travel_library, "MistPalm")

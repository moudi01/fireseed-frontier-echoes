extends "res://targeted_actor.gd"


func assemble_aid(scene: PackedScene, travel_library: AnimationLibrary) -> bool:
	guard_clip = "AidIdle"
	move_clip = "AidWalk"
	stop_clip = "AidStop"
	attack_clip = "AidFire"
	hit_clip = "AidHit"
	down_clip = "AidDown"
	raise_clip = "AidRaise"
	hold_clip = "AidHold"
	abort_clip = "AidCancel"
	release_clip = "AidFire"
	release_time = 23.0 / 30.0
	release_entry = 0.42
	release_speed = 4.4
	return _attach_caster(scene, travel_library, "AidMuzzle")

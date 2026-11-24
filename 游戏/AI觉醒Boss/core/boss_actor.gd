extends Node3D
## Display actor only, never a combat unit or a campaign instance.
const MODEL=preload("res://assets/boss.glb")
const BOUNDS=preload("res://core/asset_bounds.gd")
var model
var player: AnimationPlayer
var stage=""
var paused=false
func _ready():
	model=MODEL.instantiate();add_child(model)
	var box: AABB=BOUNDS.measure(model).bounds;var factor=1.82/box.size.y
	model.scale*=factor;model.position-=Vector3(box.get_center().x,box.position.y,box.get_center().z)*factor
	player=model.find_children("*","AnimationPlayer",true,false)[0]
	player.get_animation("BossIdle").loop_mode=Animation.LOOP_LINEAR
	player.play("BossIdle");player.advance(0)
func set_stage(value: String,settled=false):
	if stage==value:return
	stage=value
	var clip="BossObserve" if value=="observed" else "BossIdle"
	player.play(clip,.15)
	if settled and clip=="BossObserve":player.seek(player.get_animation(clip).length,true);player.pause()
	player.speed_scale=0 if paused else 1
func set_paused(value: bool):
	paused=value;player.speed_scale=0 if value else 1

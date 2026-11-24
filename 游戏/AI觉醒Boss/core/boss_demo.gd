extends Node3D
## Independent art inspection. No store, commands or rule data are created.
const BOARD=preload("res://board.gd")
const BOUNDS=preload("res://core/asset_bounds.gd")
var board
var actor
var paused=false
var elapsed=0.0
var output=""
var samples=[]
var marker=0
func _ready():
	board=BOARD.new();add_child(board);board.set_context("boundary_approach");board.show_boundary([],"approach");board.set_grid_mode("off")
	actor=board.stage_set.get_node("BoundaryBoss")
	board.camera.size=4.9;board.camera.position=actor.position+Vector3(4,2.8,5);board.camera.look_at(actor.position+Vector3(-.35,.95,0))
	var comparison=board.templates.shield.duplicate();comparison.position+=Vector3(-2.1,.31,-3.2);board.stage_set.add_child(comparison)
	var player=comparison.find_children("*","AnimationPlayer",true,false)[0];player.play("Idle");player.seek(.4,true);player.pause()
	var layer=CanvasLayer.new();add_child(layer);var panel=PanelContainer.new();panel.theme=preload("res://core/interface_theme.gd").create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE);panel.offset_left=20;panel.offset_right=-20;panel.offset_top=14;layer.add_child(panel)
	var stack=VBoxContainer.new();panel.add_child(stack);var title=Label.new();title.text="CH-B1 · Boss护甲与动作首版　|　左侧为普通盾兵尺度参照，不读取战役进度";title.add_theme_font_size_override("font_size",20);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	button(row,"待机",func():actor.set_stage("approach"))
	button(row,"观察手势",func():actor.set_stage("approach");actor.set_stage("observed"))
	button(row,"暂停 / 继续",func():paused=not paused;actor.set_paused(paused))
	button(row,"退出",func():get_tree().quit())
	var info=Label.new();info.text="封闭面甲 / 宽肩护甲 / 暗布与旧铁 / 不对称接缝　　F11切换全屏，滚轮缩放";stack.add_child(info)
	var args=OS.get_cmdline_user_args()
	if args.has("--capture-boss"):output=args[args.find("--capture-boss")+1];DirAccess.make_dir_recursive_absolute(output)
func button(row,text,callback):
	var b=Button.new();b.text=text;row.add_child(b);b.pressed.connect(callback)
func capture(name):
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output.path_join(name+".png"))
	var bounds=BOUNDS.measure(actor.model,Transform3D.IDENTITY,true).bounds
	samples.append({"frame":Engine.get_process_frames(),"time":elapsed,"clip":str(actor.player.current_animation),"pose_time":actor.player.current_animation_position,"floor":bounds.position.y,"height":bounds.size.y})
func _process(delta):
	if output.is_empty():return
	elapsed+=delta
	if marker==0 and elapsed>.5:marker=1;capture("boss_idle")
	elif marker==1 and elapsed>.9:marker=2;actor.set_stage("observed")
	elif marker==2 and elapsed>2.8:marker=3;capture("boss_observe")
	elif marker==3 and elapsed>4.7:
		marker=4;await capture("boss_returned")
		var result={"passed":samples.size()==3 and samples.all(func(s):return absf(s.floor)<.04),"samples":samples,"scope":"independent production Boss actor, posed geometry foot height, actual render capture; no campaign state or combat change"}
		var file=FileAccess.open(output.path_join("boss.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify(result));get_tree().quit(0 if result.passed else 1)

func _input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
		board.camera.size=clampf(board.camera.size+(-.35 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .35),2.8,8)
		get_viewport().set_input_as_handled()

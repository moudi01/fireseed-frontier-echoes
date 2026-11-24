extends Node3D
const BOSS=preload("res://core/boss_actor.gd")
const RULES=preload("res://core/anomaly.gd")
const STORE=preload("res://core/campaign_store.gd")
const ANOMALY_ART=preload("res://core/anomaly_art.gd")
const BOARD=preload("res://board.gd")
var context_ui
var engine=RULES.new()
var store=STORE.new(engine)
var board
var decor=Node3D.new()
var boss_actor
var restore_observation=false
var ui=VBoxContainer.new()
var options={}
var actions={}
var checks=[]
var opened=false
var history=false
var token=""
func _ready():
	var args=OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i].begins_with("--"):options[args[i].trim_prefix("--")]=args[i+1]
	opened=store.open(str(options.get("data-dir",OS.get_executable_path().get_base_dir().path_join("save_anomaly"))))
	board=BOARD.new();add_child(board);board.add_child(decor)
	boss_actor=BOSS.new();boss_actor.name="DemoBoss";boss_actor.position=board.position_at(4,7)+Vector3(0,.31,0);board.add_child(boss_actor);boss_actor.hide()
	restore_observation=not store.state.is_empty() and int(store.state.facts.get("demo_stage",-1))==5
	board.set_grid_mode("off");board.surface.material_override=board.ART.mat("626765")
	board.surface.hide()
	board.ground.hide() # The independent white-room/palace fragment has no forest backdrop.
	var layer=CanvasLayer.new();add_child(layer)
	context_ui=preload("res://core/context_interface.gd").new();context_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layer.add_child(context_ui)
	context_ui.headline.text="独立预置片段 · 异常演示";context_ui.dismissed.connect(hide_dialog)
	board.camera.look_at(Vector3(0,.3,0))
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;context_ui.stack.add_child(scroll);ui.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(ui);refresh()
	if options.has("demo-smoke"):call_deferred("smoke")
func text_line(text: String,size=18):
	var label=Label.new();label.text=text;label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;label.add_theme_font_size_override("font_size",size);ui.add_child(label)
func button(text: String,callback: Callable,key=""):
	var b=Button.new();b.text=text;b.pressed.connect(callback);ui.add_child(b)
	if key!="":actions[key]=b
func send(kind: String,payload={}):
	var result=store.dispatch({"id":token+kind,"expected_revision":int(store.state.get("revision",0)),"kind":kind,"payload":payload})
	if result.ok:refresh()
	else:text_line(result.get("error","未提交"))
func hide_dialog():
	context_ui.present("world");context_ui.clear_footer()
	context_ui.action("继续本段对白",func():context_ui.present("story"),"reopen")
func refresh():
	context_ui.present("story");context_ui.clear_footer()
	for child in ui.get_children():ui.remove_child(child);child.queue_free()
	actions={};token="%d:%d:"%[int(store.state.get("revision",0)),Time.get_ticks_usec()]
	text_line("独立预置片段 · 异常演示",23)
	text_line("进度仅在本演示中保存。",15)
	if not opened:
		text_line("此目录不是有效演示进度，原文件已保留。请从独立演示入口启动。")
		button("退出",func():get_tree().quit());return
	if store.state.is_empty():
		button("开始独立演示",func():send("NEW_DEMO"),"new");return
	var stage=int(store.state.facts.demo_stage);var scene=engine.scene(store.state)
	if history:
		for entry in store.state.facts.demo_history:
			text_line(entry.title,19)
			for line in entry.lines:text_line(line,15)
		button("返回演示记录",func():history=false;refresh(),"back")
	else:
		text_line(scene.title,23)
		for line in scene.lines:text_line(line);ui.add_child(HSeparator.new())
		var space=Control.new();space.size_flags_vertical=Control.SIZE_EXPAND_FILL;ui.add_child(space)
		for choice in scene.choices:
			var id=choice.id
			button(choice.text,func():send("DEMO_STEP",{"stage":stage,"choice":id}),id)
		if stage==7:button("回看本次记录",func():history=true;refresh(),"history")
	var toggle=CheckBox.new();toggle.text="降低白光强度";toggle.button_pressed=store.state.facts.reduced_flash;ui.add_child(toggle);toggle.toggled.connect(func(v):send("DEMO_ACCESSIBILITY",{"reduced_flash":v}));actions["reduced"]=toggle
	button("退出并保留演示进度",func():get_tree().quit(),"quit")
	visual(stage,store.state.facts.reduced_flash)
func box(parent: Node3D,pos: Vector3,size: Vector3,color: Color):
	var node=MeshInstance3D.new();var mesh=BoxMesh.new();mesh.size=size;node.mesh=mesh;node.material_override=board.material(color);node.position=pos;parent.add_child(node)
func visual(stage: int,reduced: bool):
	for child in decor.get_children():decor.remove_child(child);child.queue_free()
	var units=[{"instance_id":1,"side":"player","unit_type":"shield","position":[4,2 if stage<4 else 3],"hp":45,"alive":true},{"instance_id":3,"side":"player","unit_type":"archer","position":[4,1 if stage<4 else 2],"hp":24,"alive":true}]
	boss_actor.visible=stage!=2;boss_actor.set_paused(stage==2)
	board.show_units([] if stage==2 else units);board.set_paused(true,1)
	for world in board.get_children():
		if world is WorldEnvironment:world.environment.background_color=(Color("b8c4bd") if not reduced else Color("82938d")) if stage==2 else Color("35443e")
	if stage==2:
		ANOMALY_ART.room(decor,board.position_at(4,4),reduced)
	else:
		boss_actor.set_stage("observed" if stage==5 else "approach",restore_observation and stage==5)
		restore_observation=false
		board.label(decor,"Boss",Color("e8c6a0"),2.35).position+=board.position_at(4,7)
		ANOMALY_ART.boundary(decor,stage==5)
		if stage>=4 and stage<=5:
			var lead=board.figures[1];board.PRESENT.apply_clip(lead.model,"ShieldWall");lead.player.play("ShieldWall");lead.player.seek(.7,true);lead.player.pause()
			# Shadow stops before the body; no visible collision wall or physics controls gameplay.
			box(decor,board.position_at(4,3)+Vector3(.35,.006,-.5),Vector3(.5,.015,.08),Color("363530"))
		if stage==1:
			for x in [-2.6,2.6]:box(decor,board.position_at(4,4)+Vector3(x,.3,0),Vector3(.025,.6,3.8),Color("aebfb5"))
func capture(name: String):
	await get_tree().process_frame;await get_tree().process_frame;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(str(options["evidence-dir"]).path_join(name+".png"))
func smoke():
	var mode=options["demo-smoke"]
	if mode=="reject":checks.append(not opened)
	elif mode=="start":
		actions.new.pressed.emit();checks.append(store.state.facts.demo_stage==0)
		actions.continue.pressed.emit();await capture("demo_voice");actions.continue.pressed.emit();await capture("demo_room")
		checks.append(store.state.facts.demo_stage==2 and store.state.facts.reduced_flash)
	elif mode=="resume":
		checks.append(store.state.facts.demo_stage==2)
		actions.continue.pressed.emit();await capture("demo_approach");actions.forward.pressed.emit();await capture("demo_blocked")
		actions.observe.pressed.emit();await capture("demo_observe");actions.return.pressed.emit();await capture("demo_return");actions.finish.pressed.emit()
		checks.append(store.state.facts.demo_stage==7 and store.state.resources=={"coins":30,"crystals":0,"recruit_token":0})
	elif mode=="check":
		checks.append(store.state.facts.demo_stage==7)
		var before=JSON.stringify(store.state,"",true);actions.history.pressed.emit();await capture("demo_history");actions.back.pressed.emit();checks.append(before==JSON.stringify(store.state,"",true))
	var report={"passed":not false in checks,"checks":checks,"state_sha256":JSON.stringify(store.state,"",true).sha256_text(),"stage":store.state.get("facts",{}).get("demo_stage",-1),"opened":opened}
	var file=FileAccess.open(str(options["evidence-dir"]).path_join("demo_"+mode+".json"),FileAccess.WRITE);file.store_string(JSON.stringify(report));file.close()
	if mode=="start":await get_tree().create_timer(60).timeout
	get_tree().quit(0 if report.passed else 1)

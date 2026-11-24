extends Node3D
## Independent animation workbench. Synthetic poses, no campaign/store/rules.
const BOARD=preload("res://board.gd")
const BOUNDS=preload("res://core/asset_bounds.gd")
var board
var paused=false
var elapsed=0.0
var phase=0
var tick=0
var output=""
var samples=[]
var status: Label
var units=[{"instance_id":1,"unit_type":"lorne","side":"enemy","position":[3,4],"hp":65,"alive":true,"display_name":"洛恩 · 剑盾"},{"instance_id":2,"unit_type":"cavalry","side":"enemy","position":[5,4],"hp":35,"alive":true,"display_name":"突击兵 · 单手剑"},{"instance_id":3,"unit_type":"archer","side":"enemy","position":[7,4],"hp":24,"alive":true,"display_name":"弓兵 · 弓"}]
var names=["待机","起手：举盾 / 蓄力 / 拉弓","保持：盾墙 / 蓄力 / 瞄准","出招：持盾攻击 / 重击 / 放箭","移动：持盾行进 / 弓兵携弓","回收"]
var times=[.8,.55,.65,.5,.65,.8]
var side_view=false
var focus_id=0
func _ready():
	board=BOARD.new();add_child(board);board.set_grid_mode("off");board.sound.set_enabled(false)
	board.camera.size=6.1;board.camera.position=Vector3(3.5,3.5,6.5);board.camera.look_at(Vector3(.5,.65,-.5))
	var layer=CanvasLayer.new();add_child(layer);var panel=PanelContainer.new();panel.theme=preload("res://core/interface_theme.gd").create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE);panel.offset_left=20;panel.offset_right=-20;panel.offset_top=14;layer.add_child(panel)
	var stack=VBoxContainer.new();panel.add_child(stack);var title=Label.new();title.text="AD-02 · 技能动作适配台（独立姿态预置，不读取战役进度）";title.add_theme_font_size_override("font_size",20);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	button(row,"暂停 / 继续",func():paused=not paused;board.set_paused(paused,1))
	button(row,"下一阶段",func():paused=true;next_phase();board.set_paused(true,1))
	button(row,"重新播放",func():paused=false;phase=0;elapsed=0;show_phase())
	button(row,"正面 / 侧面",func():side_view=not side_view;update_camera())
	button(row,"近看：全队 / 角色",func():focus_id=(focus_id+1)%4;set_focus();update_camera(true))
	button(row,"奇幻护壁 开 / 关",func():board.set_shield_visuals(not board.shield_visuals_enabled))
	button(row,"退出",func():get_tree().quit())
	status=Label.new();stack.add_child(status)
	var info=Label.new();info.text="盾前护壁 / 肩甲接缝 / 手掌与装备适配 · F11全屏 / 滚轮缩放";stack.add_child(info)
	var args=OS.get_cmdline_user_args()
	board.set_shield_visuals(not args.has("--shield-rim-off"))
	if args.has("--capture-skills"):output=args[args.find("--capture-skills")+1];DirAccess.make_dir_recursive_absolute(output)
	focus_id=3 if args.has("--focus-archer") else (1 if args.has("--focus-lorne") else (2 if args.has("--focus-assault") else 0));side_view=args.has("--side")
	show_phase()
	update_camera(true)
func button(row,text,callback):
	var b=Button.new();b.text=text;row.add_child(b);b.pressed.connect(callback)
func show_phase():
	if phase==0:board.clear()
	units[0].position=[3,3 if phase>=4 else 4];units[2].position=[7,3 if phase>=4 else 4]
	tick+=1;var events=[];units[0].is_winding=phase==1;units[0].shield_pool=80 if phase in [2,3,4] else 0
	units[1].charge_ticks_left=2 if phase==1 else (1 if phase==2 else 0);units[1].charge_cell=[5,3]
	if phase==3:
		for id in [1,2,3]:events.append({"actor":id,"target":id,"action":"attack","damage":0,"attack_type":"charged_strike" if id==2 else "normal"})
	if phase==4:
		for id in [1,3]:events.append({"actor":id,"action":"move","from":[3 if id==1 else 7,4],"to":[3 if id==1 else 7,3]})
	board.set_paused(false,1);board.show_units(units,events,tick)
	if paused:
		for f in board.figures.values():
			var sample=(.14*f.clip_rate) if phase==3 else (f.skill_hold_at if f.skill_hold_at>=0 else (.75 if f.clip=="ShieldWall" else 0.0))
			f.player.seek(sample,true);f.player.advance(0)
			if f.unit_type=="archer":board.update_bow(f,true)
	board.set_paused(paused,1);status.text=names[phase]
	set_focus();update_camera()
func set_focus():
	for id in board.figures:
		var f=board.figures[id];f.node.visible=focus_id==0 or id==focus_id
		f.nameplate_allowed=focus_id==0;f.label.visible=focus_id==0;f.health_back.visible=focus_id==0;f.health_fill.visible=focus_id==0
	for n in board.effects.get_children()+board.feedback.get_children():n.visible=focus_id==0 or int(n.get_meta("visual_owner",-1))==focus_id
func update_camera(reset_zoom=false):
	var center=board.figures[focus_id].node.position+Vector3(0,1.1,0) if focus_id>0 and board.figures.has(focus_id) else Vector3(.5,.65,-.5)
	var offset=(Vector3(3,.4,.3) if side_view else Vector3(.8,.4,3)) if focus_id>0 else (Vector3(6.5,1.75,1.5) if side_view else Vector3(3,2.85,7))
	board.camera.position=center+offset;board.camera.look_at(center)
	if reset_zoom:board.camera.size=(3.0 if focus_id in [1,2] else 2.6) if focus_id>0 else 6.1
func next_phase():
	phase=(phase+1)%names.size();elapsed=0;show_phase()
func capture():
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	var poses=[]
	for f in board.figures.values():
		var bounds=BOUNDS.measure(f.model,Transform3D.IDENTITY,true).bounds
		var screen={}
		if f.node.visible:
			var world=BOUNDS.measure(f.node,board.global_transform,true).bounds;var top=INF;var bottom=-INF;var left=INF;var right=-INF
			for i in range(8):
				var p=board.camera.unproject_position(world.get_endpoint(i));top=minf(top,p.y);bottom=maxf(bottom,p.y);left=minf(left,p.x);right=maxf(right,p.x)
			screen={"top":top,"bottom":bottom,"left":left,"right":right,"logical_size":[get_viewport().get_visible_rect().size.x,get_viewport().get_visible_rect().size.y]}
		poses.append({"role":f.unit_type,"clip":f.clip,"time":f.player.current_animation_position,"floor":bounds.position.y,"height":bounds.size.y,"screen_bounds":screen,"shield_rim":{"valid":f.shield_fx.valid,"active":f.shield_fx.active_shield,"visible":f.shield_fx.is_visible_in_tree()},"issues":f.model.get_meta("action_issues")})
	get_viewport().get_texture().get_image().save_png(output.path_join("phase_%d.png"%phase));samples.append({"phase":phase,"poses":poses})
func _process(delta):
	if focus_id>0:update_camera()
	if paused:return
	elapsed+=delta
	if not output.is_empty() and elapsed>=(.14 if phase==3 else (.25 if phase==4 else times[phase]-.05)) and not samples.any(func(s):return s.phase==phase):
		set_process(false);await capture();set_process(true)
	if elapsed<times[phase]:return
	if not output.is_empty():
		if phase==names.size()-1:
			var ok=samples.size()==names.size() and samples.all(func(s):return s.poses.all(func(p):return p.issues.is_empty() and absf(p.floor)<.06 and p.height<2.8))
			var result={"passed":ok,"focus_id":focus_id,"side_view":side_view,"samples":samples,"scope":"independent synthetic pose workbench using production board/models; no campaign state or combat authority"}
			var file=FileAccess.open(output.path_join("skills.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify({"passed":ok,"samples":samples.size()}));get_tree().quit(0 if ok else 1);return
	next_phase()
func _input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
		board.camera.size=clampf(board.camera.size+(-.25 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .25),1.3 if focus_id>0 else 3.5,10);get_viewport().set_input_as_handled()

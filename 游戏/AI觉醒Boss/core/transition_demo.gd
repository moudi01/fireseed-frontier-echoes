extends Node3D
## Synthetic snapshots exercise the real board; no campaign/store or battle authority.
const DEMO=preload("res://core/skill_demo.gd")
var board
var units=[]
var phase=0
var tick=0
var clock=0.0
var paused=false
var speed=1.0
var output=""
var samples=[]
var pending=false
var status:Label
var names=["待机","开始行进","停下：盾墙保持 / 收剑 / 携弓","技能起手","技能出招","收势回待机","受击","恢复"]
func _ready():
	board=load("res://board.gd").new();add_child(board);board.sound.set_enabled(false);board.set_grid_mode("off")
	board.camera.size=5.7;board.camera.position=Vector3(3.5,3.5,6.5);board.camera.look_at(Vector3(.5,.65,-.5))
	var layer=CanvasLayer.new();add_child(layer);var panel=PanelContainer.new();panel.theme=preload("res://core/interface_theme.gd").create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE);panel.offset_left=20;panel.offset_right=-20;panel.offset_top=14;layer.add_child(panel);var stack=VBoxContainer.new();panel.add_child(stack)
	var title=Label.new();title.text="AD-02 · 动作衔接检查（独立预置，不读取战役）";title.add_theme_font_size_override("font_size",20);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	button(row,"暂停 / 继续",func():paused=not paused;board.set_paused(paused,speed))
	button(row,"下一阶段",func():paused=true;next_phase();board.set_paused(true,speed))
	button(row,"1倍 / 3倍",func():speed=3.0 if speed==1 else 1.0;board.set_paused(paused,speed))
	button(row,"衔接 开 / 关",func():board.set_pose_smoothing(not board.pose_smoothing_enabled))
	button(row,"重新播放",func():restart())
	button(row,"退出",func():get_tree().quit())
	status=Label.new();stack.add_child(status);var info=Label.new();info.text="停下 / 攻击收势：0.10秒姿态过渡 · 技能起手与判定不延迟 · F11全屏 / 滚轮缩放";stack.add_child(info)
	var args=OS.get_cmdline_user_args()
	if args.has("--capture-transitions"):output=args[args.find("--capture-transitions")+1];DirAccess.make_dir_recursive_absolute(output)
	if args.has("--transition-speed"):speed=3.0 if args[args.find("--transition-speed")+1]=="3" else 1.0
	board.set_pose_smoothing(not args.has("--transition-baseline"));restart()
func button(row,text,callback):
	var b=Button.new();b.text=text;row.add_child(b);b.pressed.connect(callback)
func restart():
	board.clear();var preset=DEMO.new();units=preset.units.duplicate(true);preset.free();phase=0;tick=0;clock=0;paused=false;samples=[];board.set_paused(false,speed);show_phase()
func next_phase():
	phase=(phase+1)%names.size();clock=0;show_phase()
func show_phase():
	tick+=1;var events=[]
	for unit in units:
		unit.is_winding=phase==3 and unit.unit_type=="lorne";unit.shield_pool=80 if unit.unit_type=="lorne" and phase in [1,2,4,5] else 0
		unit.charge_ticks_left=1 if phase==3 and unit.unit_type=="cavalry" else 0;unit.charge_cell=[5,3]
		if phase==1:
			var before=unit.position.duplicate();unit.position=[unit.position[0],3 if unit.position[1]==4 else 4];events.append({"actor":unit.instance_id,"action":"move","from":before,"to":unit.position.duplicate()})
		if phase==4:events.append({"actor":unit.instance_id,"target":unit.instance_id,"action":"attack","damage":0,"attack_type":"charged_strike" if unit.unit_type=="cavalry" else "normal"})
		if phase==6:events.append({"actor":99,"target":unit.instance_id,"action":"attack","damage":1})
	board.set_paused(paused,speed);board.show_units(units,events,tick)
func capture():
	pending=true;await get_tree().process_frame;await RenderingServer.frame_post_draw
	var poses=[]
	for f in board.figures.values():poses.append({"role":f.unit_type,"clip":f.clip,"weight":f.pose.latest.weight,"blending":f.pose.latest.applied,"callbacks":f.plant.callbacks,"issues":f.model.get_meta("action_issues")})
	get_viewport().get_texture().get_image().save_png(output.path_join("phase_%d.png"%phase));samples.append({"phase":phase,"poses":poses});pending=false
func _process(delta):
	status.text="%s · %d倍 · 衔接%s（关闭恢复原生混合，弓跟随修复仍生效）"%[names[phase],int(speed),"开" if board.pose_smoothing_enabled else "关"]
	if paused or pending:return
	clock+=delta*speed
	if not output.is_empty() and clock>=.045 and not samples.any(func(s):return s.phase==phase):await capture();return
	if clock<.65:return
	if phase==names.size()-1 and not output.is_empty():
		var ok=samples.size()==names.size() and samples.all(func(s):return s.poses.all(func(p):return p.issues.is_empty() and p.callbacks>0))
		var result={"passed":ok,"enabled":board.pose_smoothing_enabled,"speed":speed,"samples":samples,"scope":"synthetic production board snapshots; incoming neutral poses only, not full start/stop clips or gameplay"};var file=FileAccess.open(output.path_join("transitions.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify({"passed":ok,"samples":samples.size()}));get_tree().quit(0 if ok else 1);return
	next_phase()
func _input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:board.camera.size=clampf(board.camera.size+(-.25 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .25),4,9);get_viewport().set_input_as_handled()

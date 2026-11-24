extends Node3D
## Independent visual trajectory fixture, not a battle or campaign simulation.
var board
var units=[]
var tick=0
var route=[[0,0],[1,0],[0,0],[0,-1]]
var index=0
var clock=0.0
var elapsed=0.0
var paused=false
var speed=1.0
var output=""
var captures=[]
var samples=[]
var status: Label
var plant_metrics={"samples":0,"before_sum":0.0,"after_sum":0.0,"max_shift":0.0}
var unit_count=3
var bases=[]
var benchmark_seconds=0.0
var frame_times=[]
var previous_wall=0
func _ready():
	board=preload("res://board.gd").new();add_child(board);board.set_grid_mode("off");board.sound.set_enabled(false);board.camera.size=6.6;board.camera.position=Vector3(3.5,3.5,6.5);board.camera.look_at(Vector3(.5,.6,-.5));Engine.max_fps=30
	var layer=CanvasLayer.new();add_child(layer);var panel=PanelContainer.new();panel.theme=preload("res://core/interface_theme.gd").create();panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE);panel.offset_left=20;panel.offset_right=-20;panel.offset_top=14;layer.add_child(panel);var stack=VBoxContainer.new();panel.add_child(stack)
	var title=Label.new();title.text="AD-02 · 转向与步态检查（独立显示预置，不读取战役）";title.add_theme_font_size_override("font_size",20);stack.add_child(title)
	var row=HBoxContainer.new();stack.add_child(row)
	button(row,"暂停 / 继续",func():paused=not paused;board.set_paused(paused,speed))
	button(row,"单步",func():paused=true;step())
	button(row,"1倍 / 3倍",func():speed=3.0 if speed==1 else 1.0;board.set_paused(paused,speed))
	button(row,"帧率上限30 / 120",func():Engine.max_fps=120 if Engine.max_fps==30 else 30)
	button(row,"支撑脚修整 开/关",func():board.set_foot_planting(not board.foot_planting_enabled))
	button(row,"重新播放",func():restart())
	button(row,"退出",func():get_tree().quit())
	status=Label.new();stack.add_child(status);var info=Label.new();info.text="90° / 180°往返 · 持盾行进 / 携弓 / 单手剑步态 · F11全屏，滚轮缩放";stack.add_child(info)
	var args=OS.get_cmdline_user_args()
	if args.has("--capture-motion"):output=args[args.find("--capture-motion")+1];DirAccess.make_dir_recursive_absolute(output)
	if args.has("--motion-speed"):speed=clampf(float(args[args.find("--motion-speed")+1]),1,3)
	if args.has("--motion-fps"):Engine.max_fps=120 if args[args.find("--motion-fps")+1]=="120" else 30
	board.set_foot_planting(not args.has("--foot-baseline"))
	if args.has("--motion-count"):unit_count=clampi(int(args[args.find("--motion-count")+1]),3,48)
	if args.has("--benchmark-seconds"):
		benchmark_seconds=maxf(1,float(args[args.find("--benchmark-seconds")+1]));Engine.max_fps=0;DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	if unit_count>3:board.camera.size=11.6;board.camera.position=Vector3(9,12,12);board.camera.look_at(Vector3(0,.2,0))
	restart()
func button(row,text,callback):
	var b=Button.new();b.text=text;row.add_child(b);b.pressed.connect(callback)
func restart():
	board.clear();index=0;tick=0;clock=0;elapsed=0;paused=false;plant_metrics={"samples":0,"before_sum":0.0,"after_sum":0.0,"max_shift":0.0}
	units=[{"instance_id":1,"unit_type":"lorne","side":"enemy","position":[3,4],"hp":65,"alive":true,"shield_pool":80,"display_name":"洛恩 · 持盾行进"},{"instance_id":2,"unit_type":"cavalry","side":"enemy","position":[5,4],"hp":35,"alive":true,"display_name":"突击兵 · 单手剑"},{"instance_id":3,"unit_type":"archer","side":"enemy","position":[7,4],"hp":24,"alive":true,"display_name":"弓兵 · 携弓"}];board.set_paused(false,speed);board.show_units(units,[],0)
	if unit_count>3:
		units=[]
		for i in range(unit_count):units.append({"instance_id":i+1,"unit_type":"lorne" if i==0 else ["shield","cavalry","archer"][i%3],"side":"enemy","position":[1+i%8,1+int(i/8)],"hp":45,"alive":true,"shield_pool":80 if i==0 else 0})
		board.clear();board.show_units(units,[],0)
	bases=[]
	for unit in units:bases.append(unit.position.duplicate())
	frame_times=[];previous_wall=Time.get_ticks_usec()
func step():
	index=(index+1)%route.size();tick+=1;var events=[]
	for i in range(units.size()):
		var before=units[i].position.duplicate();units[i].position=[int(bases[i][0])+int(route[index][0]),int(bases[i][1])+int(route[index][1])];events.append({"actor":units[i].instance_id,"action":"move","from":before,"to":units[i].position.duplicate()})
	board.set_paused(paused,speed);board.show_units(units,events,tick)
func capture(name):
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	var poses=[]
	for f in board.figures.values():poses.append({"role":f.unit_type,"clip":f.clip,"angle":f.node.rotation.y,"target":f.facing,"turning":f.turn_active,"turn_age":f.turn_age,"turn_duration":f.turn_duration,"issues":f.model.get_meta("action_issues"),"plant_callbacks":f.plant.callbacks,"plant_profile":not f.plant.profile.is_empty()})
	get_viewport().get_texture().get_image().save_png(output.path_join(name+".png"));samples.append({"name":name,"time":elapsed,"tick":tick,"poses":poses})
func _process(delta):
	status.text="显示步%d · %d倍 · 帧率上限%d · 支撑脚修整%s（有限校正，非完整足部IK）"%[tick,int(speed),Engine.max_fps,"开" if board.foot_planting_enabled else "关"]
	if paused:return
	for f in board.figures.values():
		for v in f.plant.latest:
			plant_metrics.samples+=1;plant_metrics.before_sum+=Vector2(v.before.x-v.anchor.x,v.before.z-v.anchor.z).length();plant_metrics.after_sum+=Vector2(v.after.x-v.anchor.x,v.after.z-v.anchor.z).length();plant_metrics.max_shift=maxf(plant_metrics.max_shift,v.correction)
	elapsed+=delta*speed;clock+=delta*speed
	var wall=Time.get_ticks_usec();var wall_ms=(wall-previous_wall)/1000.0;previous_wall=wall
	if benchmark_seconds>0 and elapsed>=3.0:frame_times.append(wall_ms)
	if clock>=.5:clock=fmod(clock,.5);step()
	if output.is_empty():return
	if benchmark_seconds>0:
		if elapsed>=3.0+benchmark_seconds:set_process(false);finish_benchmark()
		return
	for row in [["quarter_turn",.60],["quarter_settled",.88],["half_turn",1.14],["half_settled",1.40]]:
		if elapsed>=row[1] and row[0] not in captures:captures.append(row[0]);capture(row[0])
	if elapsed>2.7:
		set_process(false);await capture("cycle_repeat")
		var ok=samples.size()==5 and samples.all(func(s):return s.poses.all(func(p):return p.issues.is_empty()))
		var result={"passed":ok,"speed":speed,"frame_cap":Engine.max_fps,"samples":samples,"plant_enabled":board.foot_planting_enabled,"plant_metrics":plant_metrics,"scope":"production models, motion and bounded stance correction in a synthetic route; visual time; same-contact samples before/after correction exclude swing/released feet; no battle/campaign state, turn-in-place clip or terrain foot IK"};var file=FileAccess.open(output.path_join("motion.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify({"passed":ok,"samples":samples.size(),"plant_metrics":plant_metrics}));get_tree().quit(0 if ok else 1)
func finish_benchmark():
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output.path_join("benchmark.png"));var ordered=frame_times.duplicate();frame_times.sort()
	var sum=0.0
	for value in frame_times:sum+=value
	var ok=frame_times.size()>10 and board.figures.size()==unit_count and board.figures.values().all(func(f):return not f.plant.profile.is_empty() and f.model.get_meta("action_issues").is_empty())
	var p95=frame_times[int((frame_times.size()-1)*.95)] if not frame_times.is_empty() else -1
	var result={"passed":ok,"unit_count":unit_count,"resolution":[get_viewport().get_visible_rect().size.x,get_viewport().get_visible_rect().size.y],"warmup_s":3,"sample_target_s":benchmark_seconds,"actual_visual_s":elapsed,"frames":frame_times.size(),"mean_wall_ms":sum/maxi(1,frame_times.size()),"p95_wall_ms":p95,"max_wall_ms":frame_times[-1] if not frame_times.is_empty() else -1,"performance_target_met":p95>0 and p95<=16.7,"frame_cap":Engine.max_fps,"vsync_mode":DisplayServer.window_get_vsync_mode(),"cpu":OS.get_processor_name(),"gpu":RenderingServer.get_video_adapter_name(),"engine":Engine.get_version_info(),"renderer":ProjectSettings.get_setting("rendering/renderer/rendering_method"),"plant_metrics":plant_metrics,"plant_metrics_window":"includes warmup","frame_wall_ms":ordered,"scope":"actual standalone synthetic moving-model load; frame wall-clock includes rendering, scheduling and script work, not pure GPU time; no battle AI or minimum hardware guarantee"}
	var file=FileAccess.open(output.path_join("motion.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close();print(JSON.stringify({"passed":ok,"units":unit_count,"frames":frame_times.size(),"p95_wall_ms":result.p95_wall_ms}));get_tree().quit(0 if ok else 1)
func _input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
		board.camera.size=clampf(board.camera.size+(-.3 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .3),3.5,10);get_viewport().set_input_as_handled()

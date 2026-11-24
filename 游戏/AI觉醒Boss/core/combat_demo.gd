extends Node3D
## Explicit independent fixture using the real deterministic rules. Never opens campaign saves.
const BOARD=preload("res://board.gd")
const CORE=preload("res://core/battle_core.gd")
const THEME=preload("res://core/interface_theme.gd")
const PANEL=preload("res://core/contact_panel.gd")
var controls
var close_view=false
var trace_seen=0
var board
var battle
var units_data
var rules
var paused=false
var speed=1.0
var clock=0.0
var elapsed=0.0
var finish_hold=0.0
var status: Label
var output=""
var captures=[]
var checks=[]
var round_id=0
var shield_visual_samples=[]

func _ready():
	units_data=JSON.parse_string(FileAccess.get_file_as_string("res://data/units.json"));rules=JSON.parse_string(FileAccess.get_file_as_string("res://data/design_rules.json"))
	var args=OS.get_cmdline_user_args()
	board=BOARD.new();board.contact_alignment_enabled=not args.has("--alignment-baseline");board.melee_enabled=not args.has("--melee-baseline");board.contact_enabled=not args.has("--contact-baseline");board.assault_enabled=not args.has("--assault-baseline") and board.melee_enabled;board.label_layout_enabled=not args.has("--label-baseline");add_child(board);board.camera.look_at(Vector3(0,.3,0));board.set_grid_mode("battle")
	var layer=CanvasLayer.new();add_child(layer)
	controls=PANEL.new();layer.add_child(controls);status=controls.status
	controls.pause_requested.connect(func():paused=not paused;board.set_paused(paused,speed))
	controls.step_requested.connect(func():paused=true;step())
	controls.speed_requested.connect(func():speed=3.0 if speed==1 else 1.0;board.set_paused(paused,speed))
	controls.sound_requested.connect(func():board.sound.set_enabled(not board.sound.enabled))
	controls.replay_requested.connect(restart)
	controls.focus_requested.connect(func():close_view=not close_view;update_contact_camera(true))
	controls.comparison_requested.connect(func():board.set_contact_presentation(not board.contact_enabled);restart())
	controls.quit_requested.connect(func():get_tree().quit())
	close_view=args.has("--contact-close");board.set_contact_presentation(not args.has("--contact-baseline"))
	if args.has("--capture-combat"):output=args[args.find("--capture-combat")+1];DirAccess.make_dir_recursive_absolute(output)
	restart()

func button(parent: Node,text: String,callback: Callable):
	var b=Button.new();b.text=text;b.pressed.connect(callback);parent.add_child(b)

func restart():
	round_id+=1;board.begin_location("combat_demo_"+str(round_id));battle=CORE.new();paused=false;clock=0;elapsed=0;finish_hold=0
	shield_visual_samples=[];trace_seen=0;captures=[]
	var source={"seed":42,"budget":24,"player":[{"instance_id":1,"side":"player","unit_type":"shield","x":4,"y":2,"stance":"defend"},{"instance_id":2,"side":"player","unit_type":"archer","x":4,"y":0,"stance":"attack"},{"instance_id":3,"side":"player","unit_type":"lorne","x":5,"y":2,"stance":"attack"}],"enemy":[{"instance_id":10001,"side":"enemy","unit_type":"shield","x":4,"y":5,"stance":"attack"},{"instance_id":10002,"side":"enemy","unit_type":"cavalry","x":5,"y":5,"stance":"attack"},{"instance_id":10003,"side":"enemy","unit_type":"archer","x":4,"y":6,"stance":"defend"}],"skill_config":[{"caster_id":3,"skill_id":"shield_wall","enabled":true,"trigger":"opening"}],"charge_config":[{"caster_id":10002,"skill_id":"telegraphed_strike"}]}
	if not battle.configure(source,units_data,rules):status.text=battle.error;set_process(false);return
	show_snapshot([]);update_contact_camera(true)

func update_contact_camera(reset=false):
	if close_view and board.figures.has(3) and board.figures.has(10002):
		var center=(board.figures[3].node.position+board.figures[10002].node.position)*.5+Vector3(0,.75,0)
		board.camera.position=center+Vector3(3.5,2.4,5);board.camera.look_at(center)
		if reset:board.camera.size=5.6
	elif reset:
		board.camera.position=Vector3(11,14,17);board.camera.look_at(Vector3(0,.3,0));board.camera.size=11.6

func show_snapshot(events: Array):
	var display=[]
	for unit in battle.states:
		var record=unit.duplicate(true);record.position=[unit.x,unit.y];record.max_hp=battle.stats(unit).hp;record.display_name={1:"林",2:"岑",3:"洛恩"}.get(int(unit.instance_id),units_data[unit.unit_type].name)
		record.shield_pool=int(battle.shared_shields[unit.side]);record.is_winding=int(battle.skill_states.get(str(int(unit.instance_id)),{}).get("windup_until",0))>battle.tick
		var charge=battle.charges.states.get(str(int(unit.instance_id)),{})
		record.charge_ticks_left=maxi(0,int(charge.get("release_tick",0))-battle.tick);record.charge_cell=charge.get("target_cell",[]);display.append(record)
	board.set_paused(paused,speed);board.show_units(display,events,battle.tick)
	var fx=board.figures[3].shield_fx;shield_visual_samples.append({"tick":battle.tick,"active":fx.active_shield,"pulse":fx.pulse,"triggers":fx.triggers,"pool":battle.shared_shields.player,"paused":paused})
	var hits=events.filter(func(e):return e.action=="attack")
	var absorbed=0
	for hit in hits:absorbed+=int(hit.get("absorbed",0))
	controls.set_status("第%d步 · 我方共享盾%d · 本步吸收%d · %s　|　放箭 / 受击 / 倒地与声音仅消费真实事件"%[battle.tick,battle.shared_shields.player,absorbed,battle.result if battle.finished else ("暂停" if paused else "播放")])

func step():
	if battle.finished:return
	var frame=battle.step();show_snapshot(frame.events)
	if not output.is_empty():
		var key="tick_%02d"%battle.tick
		if battle.tick in [2,5,12] or (frame.events.any(func(e):return e.action=="downed") and not "first_down" in captures):
			if frame.events.any(func(e):return e.action=="downed"):key="first_down"
			capture_frame(key)

func _process(delta):
	controls.update_controls(paused,speed,board.sound.enabled,board.contact_enabled,"全场" if close_view else "近看对战")
	if board.contact_enabled and board.melee_enabled:controls.comparison_button.text=("接触表现044" if board.contact_alignment_enabled else "接触表现043（转向基线）") if board.assault_enabled else "接触表现042（动作基线）"
	board.set_label_reserved([controls.get_global_rect()])
	if not board.melee_enabled and board.contact_enabled:controls.comparison_button.text="接触表现041（动作基线）"
	if close_view:update_contact_camera()
	if not output.is_empty() and board.contact_trace.size()>trace_seen:
		for index in range(trace_seen,board.contact_trace.size()):
			var key="contact_"+str(board.contact_trace[index].kind)
			if key not in captures:capture_frame(key)
		trace_seen=board.contact_trace.size()
	if paused:return
	elapsed+=delta
	if battle.finished:
		finish_hold+=delta*speed
		if not output.is_empty() and finish_hold>1.0:finish_capture()
		return
	clock+=delta*speed
	if clock>=.5:clock=fmod(clock,.5);step()
	if not output.is_empty() and elapsed>=32.0:finish_capture()

func capture_frame(key: String):
	if key in captures:return
	captures.append(key)
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output.path_join(key+".png"))

func finish_capture():
	var result={"passed":battle.error.is_empty(),"tick":battle.tick,"finished":battle.finished,"result":battle.result,"events":battle.events,"sounds_played":board.sound.played,"captures":captures,"shield_visual_samples":shield_visual_samples,"contact_enabled":board.contact_enabled,"melee_enabled":board.melee_enabled,"assault_enabled":board.assault_enabled,"assault_fit_active":board.figures[10002].model.get_meta("assault_attack_fit",false),"label_layout_enabled":board.label_layout_enabled,"visible_nameplates":board.unit_label_nodes.values().filter(func(node):return node.is_visible_in_tree()).size(),"shield_fit_active":board.figures[3].model.get_meta("shield_attack_fit",false),"shield_fit":board.figures[3].model.get_meta("shield_attack_fit_042",{}),"close_view":close_view,"contact_trace":board.contact_trace,"panel_height":controls.size.y,"scope":"actual standalone deterministic battle fixture; DeepSeek control panel; independent of campaign saves; cosmetic contact timeline only"}
	result["contact_alignment_enabled"]=board.contact_alignment_enabled
	var f=FileAccess.open(output.path_join("combat.json"),FileAccess.WRITE);f.store_string(JSON.stringify(result,"  "));f.close();print(JSON.stringify({"passed":result.passed,"tick":battle.tick,"sounds_played":board.sound.played}));get_tree().quit(0 if result.passed else 1)

func _input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
		board.camera.size=clampf(board.camera.size+(-.5 if event.button_index==MOUSE_BUTTON_WHEEL_UP else .5),3.5,19);get_viewport().set_input_as_handled()

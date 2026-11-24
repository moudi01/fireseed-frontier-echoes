extends Node3D
const SESSION=preload("res://core/session_log.gd")
const RULES=preload("res://core/campaign_rules.gd")
const STORE=preload("res://core/campaign_store.gd")
const STORY=preload("res://core/story.gd")
const BOARD=preload("res://board.gd")
const TOWN_SCENE=preload("res://core/town_scene.gd")
const TOWN_UI=preload("res://core/town_ui.gd")
const DEPLOYMENT_UI=preload("res://core/deployment_ui.gd")
const RETURN_VIEW=preload("res://core/return_presentation.gd")
var deployment_view
var return_report={}
var reading_return=false
var return_notice_shown=true
var transport_summary:Label
const INTERFACE_THEME=preload("res://core/interface_theme.gd")
const CONTEXT=preload("res://core/context_interface.gd")
const UI_USABILITY=preload("res://core/ui_usability.gd")
var pause_reason=""
var context_ui
var details_paused=true
const ROUTE_MAP=preload("res://core/route_map.gd")
var route_map
var route_ack=""
var route_resume_paused=true
var route_content
var route_actions
var route_summary
var route_entry
var town_scene
var town_page
var town_tab="overview"
var town_draft={}
var engine
var session_log=SESSION.new()
var last_view=""
var charge_notice_seen=false
var pause_on_charge=true
var store
var board
var ui: VBoxContainer
var actions: VBoxContainer
var headline: Label
var notice: Label
var inspection: Label
var battle_label: Label
var rows={}
var loot_rows={}
var bring_rows={}
var lorne_stay: CheckBox
var leave_confirm: CheckBox
var abandonment_signature=""
var route_eta: Label
var route: OptionButton
var focus_target: OptionButton
var shield_trigger: OptionButton
var shield_wall: CheckBox
var reading_history=false
var focus: CheckBox
var expiry: CheckBox
var rescuing: CheckBox
var paused=true
var speed=1.0
var clock=0.0
var battle_outro_left=0.0
var options={}
var seed_value=42
var formation=[]
var page_token=""
var ready_to_play=false
var commands_ui={}
var smoke_checks=[]
func _ready():
	var args=OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i].begins_with("--"):options[args[i].trim_prefix("--")]=args[i+1]
	if options.has("candidate-probe"):
		var probe_root=str(options.get("data-dir","")).get_base_dir()
		var candidate=str(ProjectSettings.get_setting("application/config/candidate_label",""))
		if candidate not in ["052","053"] or DisplayServer.get_name()!="headless" or options.get("candidate-probe") not in ["fresh","legacy"] or not options.has("data-dir") or str(options.get("probe-output","")).get_base_dir()!=probe_root or FileAccess.get_file_as_string(probe_root.path_join(candidate+"-owned-probe.txt")).strip_edges()!=candidate+" isolated release verification":
			push_error("Candidate probe requires headless mode and an explicitly owned isolated test directory")
			get_tree().quit(2);return
	if options.get("demo")=="transitions":
		get_tree().call_deferred("change_scene_to_file","res://transition_demo.tscn");return
	if options.get("demo")=="contact-load":
		var load_scene=load("res://core/contact_load.gd").new();add_child(load_scene);return
	if options.get("demo")=="surfaces":
		get_tree().call_deferred("change_scene_to_file","res://character_surface_demo.tscn");return
	if options.get("demo")=="motion":
		get_tree().call_deferred("change_scene_to_file","res://motion_demo.tscn");return
	if options.get("demo")=="skills":
		get_tree().call_deferred("change_scene_to_file","res://skill_demo.tscn");return
	if options.get("demo")=="boss":
		get_tree().call_deferred("change_scene_to_file","res://boss_demo.tscn");return
	if options.get("demo")=="anomaly":
		get_tree().call_deferred("change_scene_to_file","res://anomaly.tscn");return
	if options.get("demo")=="art":
		get_tree().call_deferred("change_scene_to_file","res://art_benchmark.tscn");return
	if options.get("demo")=="combat":
		get_tree().call_deferred("change_scene_to_file","res://combat_demo.tscn");return
	get_tree().auto_accept_quit=false
	engine=RULES.new(read("res://data/units.json"),read("res://data/design_rules.json"),read("res://data/campaign_params.json"))
	store=STORE.new(engine)
	var default_path=OS.get_executable_path().get_base_dir().path_join("save") if not OS.has_feature("editor") else ProjectSettings.globalize_path("res://local/save")
	var opened=store.open(str(options.get("data-dir",default_path)))
	board=BOARD.new();board.contact_alignment_enabled=not args.has("--alignment-baseline");add_child(board);board.inspected.connect(inspect_units)
	get_viewport().size_changed.connect(frame_deployment)
	town_scene=TOWN_SCENE.new();add_child(town_scene);town_scene.selected.connect(open_town)
	var layer=CanvasLayer.new();add_child(layer)
	route_map=ROUTE_MAP.new();route_map.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);route_map.offset_top=62;route_map.offset_bottom=-76;layer.add_child(route_map);route_map.hide();route_map.entered.connect(enter_route_node)
	context_ui=CONTEXT.new();context_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layer.add_child(context_ui);context_ui.dismissed.connect(dismiss_context)
	context_ui.quit_requested.connect(request_exit);context_ui.exit_confirmed.connect(complete_exit)
	context_ui.exit_cancelled.connect(func():board.set_paused(paused,speed))
	context_ui.set_exit_hint(UI_USABILITY.exit_hint(false))
	var stack=context_ui.stack;headline=context_ui.headline;notice=context_ui.notice;inspection=context_ui.inspection
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;stack.add_child(scroll);ui=VBoxContainer.new();ui.size_flags_horizontal=Control.SIZE_EXPAND_FILL;scroll.add_child(ui)
	actions=VBoxContainer.new();stack.add_child(actions)
	board.camera.look_at(Vector3(0,.3,0));town_scene.camera.look_at(Vector3(0,0,0))
	if not opened:
		label(ui,store.error,18);notice.text="进度文件保留在："+store.root;button(actions,"退出游戏",request_exit,"quit");context_ui.present("error",false);return
	if options.has("session-log") and not session_log.open(str(options["session-log"])):notice.text=session_log.error
	ready_to_play=true;notice.text=store.warning if session_log.error.is_empty() else session_log.error;refresh()
	if options.has("candidate-probe"):
		var probe=preload("res://core/candidate_probe.gd").new();add_child(probe)
		probe.start(self,str(options["candidate-probe"]),str(options["probe-output"]))
	if options.has("smoke"):call_deferred("smoke")
	if options.has("display-smoke"):
		var probe=preload("res://core/display_probe.gd").new();add_child(probe);probe.call_deferred("run",self)
func read(path):return JSON.parse_string(FileAccess.get_file_as_string(path))
func request_exit():
	if return_report.is_empty():complete_exit();return
	context_ui.show_exit_warning(UI_USABILITY.exit_hint(true))
	board.set_paused(true,speed)
func complete_exit():get_tree().quit()
func _notification(what):
	if what==NOTIFICATION_WM_CLOSE_REQUEST and is_instance_valid(context_ui):request_exit()
func label(parent: Node,text: String,size=17) -> Label:
	var node=Label.new();node.text=text;node.add_theme_font_size_override("font_size",size);parent.add_child(node)
	if size>=22:node.add_theme_font_override("font",INTERFACE_THEME.title_font())
	return node
func button(parent: Node,text: String,callback: Callable,key="") -> Button:
	var node=Button.new();node.text=text;node.pressed.connect(callback);parent.add_child(node)
	if key in ["new","depart","continue_journey","settle","map_enter","story_continue","story_recruit","rescue_fight"]:node.theme_type_variation="PrimaryAction"
	if key in ["quit","pause","step","speed","suggest_discard","settle"]:
		INTERFACE_THEME.action_style(node,"danger" if key=="quit" else ("primary" if key=="settle" else "secondary"))
	if key!="":commands_ui[key]=node
	return node
func checkbox(parent: Node,text: String,pressed=false) -> CheckBox:
	var node=CheckBox.new();node.text=text;node.button_pressed=pressed;parent.add_child(node);return node
func line(parent: Node) -> HBoxContainer:
	var node=HBoxContainer.new();parent.add_child(node);return node
func spin(parent: Node,minimum: int,maximum: int,value: int) -> SpinBox:
	var node=SpinBox.new();node.min_value=minimum;node.max_value=maximum;node.value=value;node.custom_minimum_size.x=68;parent.add_child(node);return node
func send(kind: String,payload: Dictionary={},suffix="") -> bool:
	var before=store.state.duplicate(true) if kind=="SETTLE" else {}
	var command={"id":page_token+":"+kind+suffix,"expected_revision":int(store.state.get("revision",0)),"kind":kind,"payload":payload}
	var result=store.dispatch(command)
	if kind!="ADVANCE_BATTLE":session_log.record("command",{"command":kind,"ok":result.ok,"choice":payload.get("choice",""),"revision":store.state.get("revision",0)})
	if not result.ok:
		context_ui.notify(result.get("error","行动失败"));paused=true;pause_reason="error"
		if store.state.get("phase")=="battle":show_battle()
		return false
	if kind=="SETTLE":return_report=RETURN_VIEW.settled(before,store.state,payload,engine);return_notice_shown=false;reading_return=false
	elif kind=="NEW_GAME":return_report={};return_notice_shown=true;reading_return=false
	if kind in ["NEW_GAME","SETTLE"]:town_tab="overview"
	if kind in ["NEW_GAME","SETTLE","DEPART"]:town_draft.clear()
	notice.text=result.get("warning","")
	return true
func refresh():
	route_map.hide()
	if not store.state.is_empty() and store.state.get("phase")=="town" and not rows.is_empty():remember_town_draft()
	for parent in [ui,actions]:
		for child in parent.get_children():parent.remove_child(child);child.queue_free()
	rows={};loot_rows={};bring_rows={};commands_ui={};battle_label=null;shield_wall=null;lorne_stay=null;leave_confirm=null;abandonment_signature=""
	deployment_view=null;transport_summary=null
	context_ui.set_exit_hint(UI_USABILITY.exit_hint(not return_report.is_empty()))
	actions.add_theme_constant_override("separation",INTERFACE_THEME.ACTION_GAP)
	page_token="%d-%d"%[int(store.state.get("revision",0)),Time.get_ticks_usec()]
	if store.state.is_empty():
		show_town_surface(true)
		label(ui,"新游戏 · 伤兵返程v2",24);label(ui,"教程只派2人，其余留城轮换。")
		var candidate=str(ProjectSettings.get_setting("application/config/candidate_label",""))
		if not candidate.is_empty():label(ui,"内部候选 "+candidate+" · 独立测试进度",16)
		button(ui,"开始新游戏",func():
			if send("NEW_GAME",{"seed":seed_value}):refresh(),"new")
		board.clear();context_ui.present("new",false);context_ui.clear_footer();return
	var state=store.state
	board.instance_health={};board.display_names={}
	for member in state.roster.values():
		board.instance_health[int(member.id)]=engine.member_stats(member).hp;board.display_names[int(member.id)]=member.name
	headline.text="第%d日 · 第%d次远征
铜币%d  结晶%d  信物%d"%[state.day,state.expedition,state.resources.coins,state.resources.crystals,state.resources.recruit_token]
	headline.text=headline.text.replace("\n","  ·  ")
	headline.text+=" · 伤兵返程v%d"%engine.settlement_version(state)
	var candidate_label=str(ProjectSettings.get_setting("application/config/candidate_label",""))
	if not candidate_label.is_empty():headline.text="候选"+candidate_label+" · "+headline.text
	var scene=STORY.pending(state)
	board.begin_location("%d:%s:%s:%s:%s"%[int(state.expedition),str(state.pending.get("route","")),str(scene.get("id",state.phase)),str(state.pending.get("journey",{}).get("node",state.pending.get("rescue_path",{}).get("node",""))),str(state.pending.get("boundary",{}).get("stage",""))])
	show_town_surface(state.phase=="town" and scene.get("id","") not in ["lorne_joined","act1_memory"] and (town_tab!="deploy" or reading_history or not scene.is_empty()))
	board.set_context(str(state.pending.get("journey",{}).get("node","")) if state.phase=="journey" else "")
	if state.phase=="boundary":board.set_context("boundary_"+str(state.pending.boundary.stage))
	elif scene.get("id")=="act1_memory":board.set_context("memory")
	board.set_grid_mode("deployment" if (state.phase=="town" and town_tab=="deploy") or (state.phase=="journey" and state.pending.journey.node=="formation") else ("battle" if state.phase=="battle" else "off"))
	var view=("history" if reading_history else ("story:"+str(scene.id) if not scene.is_empty() else state.phase+":"+str(state.pending.get("route",""))+":"+str(state.pending.get("journey",{}).get("node",state.pending.get("rescue_path",{}).get("node",state.pending.get("boundary",{}).get("stage",""))))))
	if view!=last_view:session_log.record("view",{"view":view,"revision":state.revision,"expedition":state.expedition,"day":state.day});last_view=view
	if reading_history:
		history_panel()
	elif not scene.is_empty():
		story_panel(scene)
	elif reading_return:
		return_panel()
	else:
		if state.phase in ["battle","journey","rescue_journey","boundary","settlement"]:
			render_route_phase(state.phase)
		else:render_phase(state.phase)
	var exit_action=button(actions,"退出游戏",request_exit,"quit")
	if reading_return or state.phase=="settlement":exit_action.hide()
	if state.phase=="town" and town_tab=="deploy" and scene.is_empty() and not reading_history and not reading_return:
		exit_action.hide();button(actions,"返回据点",func():open_town("overview"),"preparation_home")
	if exit_action.visible:
		var exit_note=label(actions,UI_USABILITY.exit_hint(false),14)
		exit_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	# Existing regression drivers acknowledge transitions through the real UI button.
	# Dedicated map_* drivers exercise the visible gate and restart explicitly.
	if options.has("smoke") and not str(options.smoke).begins_with("map_") and route_map.visible:commands_ui.map_enter.pressed.emit()
	present_interface()
	frame_deployment()
	if not return_notice_shown and not return_report.is_empty() and state.phase=="town" and scene.is_empty() and town_tab=="overview" and not reading_return and not reading_history:
		return_notice_shown=true;context_ui.notify("归城物资与经验已入账 · 待命%d人\n可在下方查看归城战报，培养或轮换队员。"%int(return_report.ready_count))
func render_route_phase(phase: String):
	var parent_ui=ui;var parent_actions=actions
	route_content=VBoxContainer.new();ui.add_child(route_content);ui=route_content
	route_actions=VBoxContainer.new();actions.add_child(route_actions);actions=route_actions
	render_phase(phase)
	button(actions,"查看行军图 · 暂停",func():route_resume_paused=paused;show_route_map(true),"map_open")
	ui=parent_ui;actions=parent_actions
	route_summary=VBoxContainer.new();ui.add_child(route_summary)
	route_entry=VBoxContainer.new();actions.add_child(route_entry)
	route_map.configure(store.state)
	label(route_summary,route_map.model.title,23)
	var current=route_map.model.nodes.filter(func(n):return n.status=="current")[0]
	paragraph_in(route_summary,"当前位置："+current.title)
	paragraph_in(route_summary,"队伍已停在地图标记处。点击当前位置或下方按钮进入，不会自动跳过下一站。")
	for text in route_map.model.notes:paragraph_in(route_summary,text)
	if route_map.model.failed:paragraph_in(route_summary,"目标未完成，正在返回；本次人员与物资按实际结果结算。")
	paragraph_in(route_summary,"返回途中可在运输页确认带回谁、保留哪些物资。" if phase=="settlement" else "已确认的路线与日历已经保存；停留、看图与进入地点不再计日。")
	button(route_entry,"查看运输并返回据点" if phase=="settlement" else "进入当前位置 →",enter_route_node,"map_enter")
	route_resume_paused=paused
	show_route_map(route_ack!=route_map.model.key)
func paragraph_in(parent: Node,text: String):
	var item=label(parent,text,17);item.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
func show_route_map(value: bool):
	route_map.visible=value;route_content.visible=not value;route_actions.visible=not value;route_summary.visible=value;route_entry.visible=value
	board.visible=not value;town_scene.activate(false)
	if value:
		paused=true;board.set_paused(true,speed);inspection.text="点击地图上的当前位置进入；后续节点需沿路线逐步到达。"
	else:
		paused=route_resume_paused;board.camera.make_current();inspection.text="点击棋盘格查看该格的存活与倒地者。"
		if store.state.phase=="battle":show_battle()
	present_interface()
func enter_route_node():
	if not route_map.visible:return
	route_ack=route_map.model.key;clock=0;show_route_map(false)
func render_phase(phase: String):
	match phase:
		"town":town()
		"battle":battle_panel()
		"settlement":settlement()
		"journey":journey_panel()
		"rescue_journey":rescue_panel()
		"boundary":boundary_panel()
func present_interface():
	if not is_instance_valid(context_ui) or store.state.is_empty():return
	context_ui.clear_footer()
	var phase=str(store.state.phase)
	if reading_history:context_ui.present("history");return
	if not STORY.pending(store.state).is_empty():context_ui.present("story",false);return
	if reading_return:context_ui.present("report");return
	if route_map.visible:
		context_ui.present("map");context_ui.status.text=route_map.model.title
		context_ui.action("查看运输并归城" if phase=="settlement" else "进入当前位置 →",enter_route_node,"map_enter");return
	if phase=="town":
		context_ui.present("town" if town_tab=="overview" else ("formation" if town_tab=="deploy" else "management"))
		for pair in [["据点","overview"],["兵营","barracks"],["培养","training"],["休整","rest"],["仓库","warehouse"],["出征","deploy"]]:
			var place=pair[1];context_ui.action(pair[0],func():
				open_town(place)
				if place=="overview":context_ui.present("management"),"town_"+place)
		context_ui.action("记事",func():reading_history=true;refresh(),"history")
		if not return_report.is_empty():context_ui.action("归城战报",open_return_report,"return_report")
		return
	if phase=="battle":
		for key in ["pause","step","speed","map_open"]:commands_ui[key].disabled=false
		context_ui.present("battle")
		for pair in [["暂停战斗","pause"],["单步","step"],["1倍 / 3倍","speed"],["行军图","map_open"]]:
			var key=pair[1];context_ui.action(pair[0],func():commands_ui[key].pressed.emit(),key)
		context_ui.action("战况详情",open_battle_details,"details")
		context_ui.action("声音："+("开" if board.sound.enabled else "关"),func():board.sound.set_enabled(not board.sound.enabled);present_interface(),"sound");sync_battle_controls();return
	context_ui.present("transport" if phase=="settlement" else "event")
func open_battle_details():
	if store.state.phase!="battle" or route_map.visible:return
	details_paused=paused;paused=true;show_battle();context_ui.present("details")
	for key in ["pause","step","speed","map_open"]:commands_ui[key].disabled=true
func dismiss_context():
	if reading_return:reading_return=false;refresh();return
	if reading_history:reading_history=false;refresh();return
	if store.state.phase=="battle" and context_ui.mode=="details":
		paused=details_paused;present_interface();show_battle();return
	if not STORY.pending(store.state).is_empty():return
	context_ui.present("world");context_ui.clear_footer()
	if store.state.phase=="town":
		context_ui.action("继续整备" if town_tab=="deploy" else "打开据点管理",present_interface,"reopen")
		context_ui.action("返回据点",func():open_town("overview"),"home")
	else:
		context_ui.action("继续运输选择" if store.state.phase=="settlement" else "处理当前事件",present_interface,"reopen")
		context_ui.action("查看行军图",func():route_resume_paused=paused;show_route_map(true),"map_open")
func story_panel(scene: Dictionary):
	paused=true;board.set_paused(true,1)
	if scene.id=="act1_memory":board.clear()
	if scene.id=="lorne_joined":
		var hero=store.state.roster.values().filter(func(member):return member.unit_type=="lorne")
		if not hero.is_empty():board.show_units([{"instance_id":hero[0].id,"unit_type":"lorne","side":"player","position":[4,2],"hp":150,"alive":true}]);board.set_paused(true,1)
	label(ui,scene.title,23)
	for text in scene.lines:
		var node=label(ui,text,18);node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		ui.add_child(HSeparator.new())
	for item in scene.choices:
		var choice=item.id
		button(actions,item.text,func():
			var success=send("RECRUIT_LORNE") if choice=="recruit" else send("ACK_SCENE",{"scene_id":scene.id,"choice":choice})
			if success:refresh(),"story_"+choice)
func history_panel():
	paused=true;label(ui,"已见对白",23)
	for entry in store.state.facts.get("scene_history",[]):
		label(ui,entry.title,19)
		for text in entry.lines:
			var node=label(ui,text,16);node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		label(ui,"当时选择："+str(entry.get("choice_text",{"continue":"继续","later":"稍后再说","bring":"演示：带回伤兵","leave":"演示：保留收益","recruit":"邀请洛恩"}.get(entry.choice,entry.choice))),14);ui.add_child(HSeparator.new())
	button(actions,"返回当前进度",func():reading_history=false;refresh())
func dismiss_story():
	for guard in range(8):
		var handled=false
		for key in ["story_continue","story_bring","story_later"]:
			if commands_ui.has(key):commands_ui[key].pressed.emit();handled=true;break
		if not handled:break
func status(member: Dictionary) -> String:
	return {"READY":"就绪","RESTING":"轮休%d次"%member.rest_remaining,"RECOVERING":"恢复%d次"%member.rest_remaining,"CAPTURED":"失联 · 截止第%s日"%str(member.deadline_day),"ABSORBED":"已吞并","DISMISSED":"已离队","ACTIVE":"出征中"}.get(member.status,member.status)
func open_town(place):
	if store.state.is_empty() or store.state.get("phase")!="town" or not STORY.pending(store.state).is_empty():return
	if place not in ["overview","barracks","training","rest","warehouse","deploy"]:return
	town_tab=place;reading_history=false;reading_return=false;refresh()
func show_town_surface(value: bool):
	board.visible=not value;town_scene.activate(value)
	inspection.text="点击建筑进入管理，也可用底部入口切换。" if value else "点击棋盘格查看该格的存活与倒地者。"
	if not value:board.camera.make_current()
func town():
	var content=ui;var navigation=VBoxContainer.new();content.add_child(navigation)
	var legacy=VBoxContainer.new();content.add_child(legacy);ui=legacy
	town_deployment();restore_town_draft();ui=content;legacy.visible=town_tab=="deploy"
	for child in actions.get_children():child.visible=town_tab=="deploy"
	town_page=TOWN_UI.new()
	if town_tab!="deploy":town_page.build(navigation,store.state,engine,self,town_tab)
	else:
		# Keep legacy navigation handles for external regression drivers; real
		# preparation navigation uses the visible Return-to-town action.
		town_page.build(navigation,store.state,engine,self,"deploy");navigation.hide()
func remember_town_draft():
	var selected={}
	for id in rows:
		var r=rows[id]
		if is_instance_valid(r.enable):selected[id]={"enable":r.enable.button_pressed,"x":r.x.value,"y":r.y.value,"stance":r.stance.selected,"reserve":r.reserve.button_pressed}
	town_draft={"rows":selected,"route":route.get_item_metadata(route.selected) if route!=null else "","focus":focus.button_pressed if focus!=null else false,"target":focus_target.get_item_metadata(focus_target.selected) if focus_target!=null and focus_target.selected>=0 else -1}
	if shield_wall!=null:town_draft["shield"]={"enabled":shield_wall.button_pressed,"trigger":shield_trigger.selected}
func restore_town_draft():
	if town_draft.is_empty():return
	for id in rows:
		if not town_draft.rows.has(id):continue
		var r=rows[id];var d=town_draft.rows[id]
		r.enable.set_pressed_no_signal(d.enable and not r.enable.disabled);r.reserve.set_pressed_no_signal(d.reserve);r.x.set_value_no_signal(d.x);r.y.set_value_no_signal(d.y);r.stance.select(d.stance)
	for i in range(route.item_count):
		if route.get_item_metadata(i)==town_draft.route:route.select(i)
	focus.set_pressed_no_signal(town_draft.focus)
	if shield_wall!=null and town_draft.has("shield"):
		shield_wall.set_pressed_no_signal(town_draft.shield.enabled);shield_trigger.select(town_draft.shield.trigger)
	preview_formation()
	for i in range(focus_target.item_count):
		if focus_target.get_item_metadata(i)==town_draft.target:focus_target.select(i)
func town_deployment():
	deployment_view=DEPLOYMENT_UI.new();deployment_view.build(self,ui,actions)
	preview_formation()
func validate_formation_summary(payload:Dictionary)->String:
	if payload.deployment.is_empty():return "请至少选择1名上场队员；预备队不会进入战场。"
	if store.state.expedition==0 and payload.deployment.size()!=2:return "教程需要2名队员上场，请保留其余人手轮换。"
	var cells={};var cost=0
	for spec in payload.deployment:
		var key="%d:%d"%[spec.x,spec.y]
		if cells.has(key):return "两名队员站在同一格，请调整格位。"
		cells[key]=true;cost+=int(engine.units[store.state.roster[str(spec.instance_id)].unit_type].cost)
	for id in payload.reserve_ids:cost+=int(engine.units[store.state.roster[str(id)].unit_type].cost)
	if payload.reserve_ids.size()>int(engine.rules.formation.max_reserve):return "预备人数超过上限，请减少预备队。"
	if cost>(14 if store.state.facts.get("lorne_recruited",false) else 10):return "已超出编制；洛恩与预备队也占编制。"
	return ""
func frame_deployment():
	if not is_instance_valid(board) or not is_instance_valid(context_ui):return
	if route_map.visible:route_map.offset_bottom=-maxf(76,context_ui.footer_panel.size.y+24)
	var active=board.visible and context_ui.mode=="formation" and context_ui.panel.visible
	if active and deployment_view!=null:deployment_view.fit_to_scroll()
	board.camera.h_offset=(context_ui.panel.size.x+20)*board.camera.size/(2*maxf(1,get_viewport().get_visible_rect().size.y)) if active else 0.0
func open_return_report():
	if store.state.is_empty() or store.state.phase!="town" or return_report.is_empty() or not STORY.pending(store.state).is_empty():return
	context_ui.notify("");reading_return=true;reading_history=false;refresh()
func return_panel():
	if return_report.is_empty():reading_return=false;town();return
	label(ui,return_report.headline,24)
	label(ui,"第%d次远征 · 第%d日 · 数据已确认，不需要再次领取。"%[return_report.expedition,return_report.day],15)
	var cards=GridContainer.new();cards.columns=3;cards.add_theme_constant_override("h_separation",10);ui.add_child(cards)
	for resource in return_report.resource_rows:
		var card=PanelContainer.new();card.size_flags_horizontal=Control.SIZE_EXPAND_FILL;card.add_theme_stylebox_override("panel",INTERFACE_THEME.box("263d3b","727663",12));cards.add_child(card)
		var content=VBoxContainer.new();card.add_child(content);label(content,resource.name,16);label(content,"%+d"%int(resource.delta),25);label(content,"%d → %d"%[resource.before,resource.after],14)
	paragraph("铜币入库已含援助%d；以上是仓库实际变化。"%int(return_report.aid_coins))
	label(ui,"归城时待命%d · 轮休%d · 养伤%d · 失联%d"%[return_report.ready_count,return_report.resting_count,return_report.recovering_count,return_report.captured_count],16)
	label(ui,"队员回报与轮换",20)
	if return_report.xp_rows.is_empty():paragraph("本次没有永久队员获得经验。")
	for member in return_report.xp_rows:paragraph("%s · 经验%d → %d（+%d）"%[member.name,member.before,member.after,member.delta])
	for member in return_report.member_rows:
		var description=RETURN_VIEW.STATUS_NAMES.get(member.status,member.status)
		if member.status in ["RESTING","RECOVERING"]:description+=" · 还需%d次后续远征结算"%int(member.rest_remaining)
		paragraph("%s · %s"%[member.name,description])
	label(ui,"归城时可安排的下一步",20)
	for line_text in return_report.next_steps:paragraph(line_text)
	label(ui,"详细战报仅保留在本次运行中；已入账的进度照常保存。",14)
	button(actions,"前往训练场",func():open_town("training"),"report_training")
	button(actions,"返回据点，安排下一队",func():open_town("overview"),"report_home")

func boundary_panel():
	paused=true;var b=store.state.pending.boundary
	board.show_boundary(store.state.battle_result.units,b.stage)
	label(ui,"深核边界 · 道路阻断",23)
	var lines=[]
	if b.stage=="approach":lines=["通向王座的台阶就在前面，没有新的伏击阵型。","守卫战已结束；伤势和倒地者保留。可以继续靠近，也可以提前折返。"]
	elif b.stage=="wall":lines=["Boss：怎么不走了？","最前面的人抬起手。手掌贴住了空气。","这不是战斗失败。可以查看前方，也可以原路返回。"]
	else:lines=["那一段台阶没有断，但鞋底的灰越不过去。","Boss：我没关门。","观察没有额外奖惩；返回仍按实际伤势和物资结算。"]
	for text in lines:
		var node=label(ui,text,18);node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if b.stage=="approach":boundary_button("向前一步","forward")
	if b.stage=="wall":boundary_button("查看前方","observe")
	boundary_button("原路返回" if b.stage!="approach" else "提前返回 · 暂不触及边界","return")
func boundary_button(text: String,choice: String):
	button(actions,text,func():
		if send("BOUNDARY_CHOICE",{"stage":store.state.pending.boundary.stage,"choice":choice}):refresh(),"boundary_"+choice)

func recommend_first():
	if rows.has(1) and rows.has(3):
		for id in rows:rows[id].enable.set_pressed_no_signal(id in [1,3]);rows[id].reserve.set_pressed_no_signal(false)
		rows[1].x.value=4;rows[1].y.value=2;rows[1].stance.select(1)
		rows[3].x.value=4;rows[3].y.value=0;rows[3].stance.select(1)
		focus.button_pressed=true;preview_formation();focus_target.select(1 if focus_target.item_count>1 else 0)
	preview_formation()
func journey_panel():
	paused=true;var state=store.state;var j=state.pending.journey
	label(ui,"林道侦查 · 途中",23)
	label(ui,"普通战 → 商队残骸 → 休整 → 精英 → 返回",15)
	label(ui,"本趟食物%d · 指挥点%d/10"%[int(j.food),10-int(state.pending.cp_spent)],17)
	label(ui,"离线、停留与阅读不推进日期。",14)
	show_travel_party()
	if j.node=="caravan":
		paragraph("一辆货车翻在路边。货箱裂了，车夫不在。车辙一直延伸到林子里。")
		paragraph("收取物资只增加本趟食物；留下路标多花1行动日。剩余食物回城后清空。")
		journey_choice("取走可用物资 · 本趟食物+1","collect")
		journey_choice("收拢货物，留下路标 · +1日","mark")
		journey_choice("沿路继续 · 不消耗","pass")
	elif j.node=="camp":
		paragraph("林间有一处可以歇脚。休整恢复仍能行动的队员；倒地者不能靠吃饭重新参战。")
		for id in j.hp:label(ui,"%s · HP %d/%d"%[state.roster[id].name,int(j.hp[id]),int(engine.units[state.roster[id].unit_type].hp)],17)
		paragraph("休整消耗1份本趟食物，仍能行动的队员最多恢复45HP，不增加行动日。")
		journey_choice("消耗1食物休整","rest")
		journey_choice("不休整，继续前进","skip")
	elif j.node=="formation":
		paragraph("精英重击会标记相邻一格，蓄力2步后落下；不追踪离开该格的人，提前倒地会取消。战时不能改命令，请在此调整。" if int(j.get("encounter_version",1))>=2 else "守路精英：突击兵在前，弓兵在后。可重新安排仍能行动的队员；不能从城镇换人。")
		paragraph("先看敌人，再调整前后排。战后会用当前生命、同一敌人、种子与本场集火，比较沿用前阵的参考结果；不计为第二场真实战斗。")
		for spec in j.first_input.player:
			var id=int(spec.instance_id)
			if not j.hp.has(str(id)):continue
			label(ui,"%s · HP%d"%[state.roster[str(id)].name,int(j.hp[str(id)])],18)
			var controls=line(ui);var x=spin(controls,0,9,int(spec.x));var y=spin(controls,0,2,int(spec.y))
			var stance=OptionButton.new();stance.add_item("进攻");stance.add_item("防御");stance.select(0 if spec.stance=="attack" else 1);controls.add_child(stance)
			rows[id]={"x":x,"y":y,"stance":stance}
			x.value_changed.connect(func(_v):preview_journey());y.value_changed.connect(func(_v):preview_journey());stance.item_selected.connect(func(_v):preview_journey())
		focus=checkbox(ui,"本场集火 · 消耗5指挥点",int(state.pending.cp_spent)<=5)
		focus_target=OptionButton.new();ui.add_child(focus_target)
		for enemy in engine.TRAIL.enemies(engine.rules.tutorial_trail.elite_enemy,10003):
			focus_target.add_item("目标 %s"%engine.units[enemy.unit_type].name);focus_target.set_item_metadata(focus_target.item_count-1,enemy.instance_id)
		focus_target.select(1)
		if rows.keys().map(func(id):return state.roster[str(id)].unit_type).has("shield") and rows.keys().map(func(id):return state.roster[str(id)].unit_type).has("archer"):
			button(ui,"推荐调整：盾守侧前，弓跟进",recommend_elite,"recommend_elite")
		button(actions,"确认布阵，进入精英战",func():
			if send("CONTINUE_JOURNEY",journey_payload()):paused=false;clock=0;refresh(),"continue_journey")
		preview_journey()
	journey_choice("提前返回 · 无精英战利品","return")
	button(ui,"回看已见对白",func():reading_history=true;refresh(),"history")
func rescue_panel():
	paused=true;var state=store.state;var r=state.pending.rescue_path
	label(ui,"林道营救 · 三节点",23)
	label(ui,"入口 → 营地 → 守卫战",17)
	paragraph("基础2日已计入当前日历。绕行与等待各多1日；停留、暂停和阅读不计日。")
	label(ui,"注意 %d / 3 · 到3增加1名盾卫"%int(r.attention),16)
	for target in r.targets:
		var member=state.roster[str(int(target.id))]
		paragraph("%s · %s · 最晚第%d日完成"%[target.name,status(member),int(target.deadline_day)])
	expiry=checkbox(ui,"确认额外耗日可能导致所列人员超期")
	if r.node=="approach":
		paragraph("旧路标还在。直走能赶上，绕到林后会更隐蔽。")
		rescue_button("沿路搜寻 · 不加日 / 注意+1","direct",0)
		rescue_button("绕到林后 · +1日 / 注意降低1","detour",1)
	elif r.node=="camp":
		paragraph("营地里有人巡逻。立即突入节省时间；等待换岗会多花一天。")
		rescue_button("立即突入 · 不加日 / 注意+2","breach",0)
		rescue_button("等待换岗 · +1日 / 注意降低1","wait",1)
	elif r.node=="gate":
		paragraph("守卫尚在，必须真正赢下战斗才能带回原目标。注意条本身不会杀死目标；日历超期仍会吞并。")
		label(ui,"本场守卫%d人"%engine.RESCUE.enemies(engine,int(r.attention)).size(),19)
		rescue_button("确认进入守卫战","fight",0)
	rescue_button("撤离 · 不发援助、经验或战利品","withdraw",0)
	var preview=[]
	for unit in state.pending.battle_input.player:
		var item=unit.duplicate();item.hp=engine.units[unit.unit_type].hp;item.alive=true;preview.append(item)
	for unit in engine.RESCUE.enemies(engine,int(r.attention)):
		var item=unit.duplicate();item.hp=engine.units[unit.unit_type].hp;item.alive=true;preview.append(item)
	board.show_units(preview);board.set_paused(true,1)
func rescue_button(text: String,choice: String,days: int):
	if days>0:
		var next_day=int(store.state.day)+days
		paragraph("此选择完成：第%d日%s"%[next_day,"；将超期："+"、".join(engine.RESCUE.overdue_names(store.state,next_day)) if not engine.RESCUE.overdue_names(store.state,next_day).is_empty() else ""])
	button(actions,text,func():
		if send("RESCUE_CHOICE",{"node":store.state.pending.rescue_path.node,"choice":choice,"acknowledge_expiry":expiry.button_pressed}):paused=store.state.phase!="battle";clock=0;refresh(),"rescue_"+choice)

func paragraph(text: String):
	var item=label(ui,text,17);item.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
func journey_choice(text: String,choice: String):
	button(actions,text,func():
		if send("JOURNEY_CHOICE",{"node":store.state.pending.journey.node,"choice":choice}):refresh(),"journey_"+choice)
func journey_payload() -> Dictionary:
	var deployment=[]
	for id in rows:
		var row=rows[id];deployment.append({"instance_id":id,"x":int(row.x.value),"y":int(row.y.value),"stance":"attack" if row.stance.selected==0 else "defend"})
	return {"deployment":deployment,"focus":focus.button_pressed,"focus_target":focus_target.get_selected_metadata()}
func recommend_elite():
	for id in rows:
		var row=rows[id];var type=store.state.roster[str(id)].unit_type
		row.x.value=3;row.y.value=2 if type=="shield" else 0;row.stance.select(1 if type=="shield" else 0)
	focus.button_pressed=true;focus_target.select(1);preview_journey()
func preview_journey():
	var preview=[];var j=store.state.pending.journey
	for spec in journey_payload().deployment:
		preview.append({"instance_id":spec.instance_id,"side":"player","unit_type":store.state.roster[str(spec.instance_id)].unit_type,"position":[spec.x,spec.y],"hp":int(j.hp[str(spec.instance_id)]),"alive":true})
	for enemy in engine.TRAIL.enemies(engine.rules.tutorial_trail.elite_enemy,10003):
		var unit=enemy.duplicate();unit["hp"]=engine.units[unit.unit_type].hp;unit["alive"]=true;preview.append(unit)
	board.show_units(preview);board.set_paused(true,1)

func formation_payload() -> Dictionary:
	var deployment=[];var reserves=[]
	for id in rows:
		var row=rows[id]
		if not row.enable.button_pressed:continue
		if row.reserve.button_pressed:reserves.append(id)
		else:deployment.append({"instance_id":id,"x":int(row.x.value),"y":int(row.y.value),"stance":"attack" if row.stance.selected==0 else "defend"})
	var rescue_ids=[]
	if rescuing!=null and is_instance_valid(rescuing) and rescuing.button_pressed:
		for id in engine.captured(store.state):
			if int(store.state.roster[str(id)].deadline_day)>=int(store.state.day)+2:rescue_ids.append(id)
	return {"deployment":deployment,"reserve_ids":reserves,"route":route.get_selected_metadata(),"tutorial_version":2,"shield_wall_enabled":shield_wall.button_pressed if is_instance_valid(shield_wall) else true,"shield_wall_trigger":shield_trigger.get_selected_metadata() if is_instance_valid(shield_wall) else "low_hp","focus":focus.button_pressed,"focus_target":focus_target.get_selected_metadata(),"acknowledge_expiry":expiry.button_pressed,"rescue_ids":rescue_ids}
func preview_formation():
	var preview=[]
	for id in rows:
		var row=rows[id]
		if row.enable.button_pressed and not row.reserve.button_pressed:
			var member=store.state.roster[str(id)]
			preview.append({"instance_id":id,"unit_type":member.unit_type,"side":"player","position":[int(row.x.value),int(row.y.value)],"hp":engine.member_stats(member).hp,"alive":true})
	route_eta.text="预计第%d日完成（确认出征后记账）"%[int(store.state.day)+int(engine.params.route_days[route.get_selected_metadata()])]
	if route.get_selected_metadata()=="outpost":route_eta.text+="\n两盾分守，弓兵后置；敌方守阵不追。请检查谁能主动接近、谁能支援。"
	if route.get_selected_metadata()=="boundary":route_eta.text+="\n先通过守卫，再到台阶；到墙后返回才记录边界。提前折返仍保留伤势。"
	var old_target=focus_target.get_selected_metadata() if focus_target.item_count>0 else -1
	focus_target.clear()
	for enemy in engine.enemy_deployment(store.state,route.get_selected_metadata()).units:
		var unit=enemy.duplicate();unit["hp"]=engine.units[unit.unit_type].hp;unit["alive"]=true;preview.append(unit)
		focus_target.add_item("目标 #%d · %s"%[unit.instance_id,engine.units[unit.unit_type].name]);focus_target.set_item_metadata(focus_target.item_count-1,unit.instance_id)
		if int(unit.instance_id)==old_target:focus_target.select(focus_target.item_count-1)
	if old_target==-1 and store.state.expedition==0 and focus_target.item_count>1:focus_target.select(1)
	board.show_units(preview);board.set_paused(true,1)
	if deployment_view!=null:deployment_view.refresh_summary(self)
func depart():
	if send("DEPART",formation_payload()):paused=false;clock=0;refresh()
func battle_panel():
	label(ui,"战斗 · 固定半秒一步",23)
	label(ui,"林道：普通战" if store.state.pending.get("journey",{}).get("node")=="first" else ("林道：守路精英" if store.state.pending.get("journey",{}).get("node")=="elite" else "行动已锁定；离线、暂停不推进游戏日。"),15)
	if not store.state.pending.battle_input.get("growth_config",[]).is_empty():label(ui,"培养已生效：Lv2生命+6 / 攻击+2",15)
	label(ui,"CP %d / 10 · 集火%s"%[10-int(store.state.pending.cp_spent),"已生效" if store.state.pending.cp_spent else "未配置"],17)
	battle_label=label(ui,"",17)
	var controls=line(ui)
	button(controls,"暂停战斗",toggle_battle_pause,"pause")
	button(controls,"单步",step_battle,"step")
	button(controls,"1倍 / 3倍",func():speed=3.0 if speed==1 else 1.0,"speed")
	if not store.state.pending.battle_input.get("charge_config",[]).is_empty():
		var warning_pause=checkbox(ui,"首次重击预警时暂停",pause_on_charge);warning_pause.toggled.connect(func(v):pause_on_charge=v)
	show_battle()
func toggle_battle_pause():
	if route_map.visible or context_ui.mode=="details" or context_ui.exit_overlay.visible:return
	if store.state.phase!="battle" and battle_outro_left<=0:return
	paused=not paused;pause_reason="manual" if paused else "";show_battle()
func step_battle():
	if store.state.phase!="battle" or battle_outro_left>0 or route_map.visible or context_ui.mode=="details" or context_ui.exit_overlay.visible:return
	paused=true;pause_reason="step";advance()
func sync_battle_controls():
	var snapshot=store.state.battle_snapshot
	var finished=store.state.phase!="battle" or bool(snapshot.get("finished",false))
	var view=UI_USABILITY.battle(int(snapshot.tick),paused,pause_reason,finished,battle_outro_left>0)
	if context_ui.mode=="battle":context_ui.status.text=view.status;context_ui.call_deferred("layout")
	for group in [commands_ui,context_ui.footer_buttons]:
		if group.has("pause"):
			group.pause.text=view.pause_text;group.pause.disabled=not view.can_pause
			INTERFACE_THEME.action_style(group.pause,"primary" if paused and view.can_pause else "secondary")
		if group.has("step"):group.step.text=view.step_text;group.step.disabled=not view.can_step
func show_battle():
	var snapshot=store.state.battle_snapshot
	if not paused:pause_reason=""
	sync_battle_controls()
	var events=snapshot.events.filter(func(event):return int(event.tick)==int(snapshot.tick))
	var summary=[]
	for unit in snapshot.states:
		var record=unit.duplicate();record["position"]=[int(unit.x),int(unit.y)]
		record["display_name"]=store.state.roster.get(str(int(unit.instance_id)),{}).get("name",engine.units[unit.unit_type].name)
		record["max_hp"]=engine.member_stats(store.state.roster[str(int(unit.instance_id))]).hp if store.state.roster.has(str(int(unit.instance_id))) else engine.units[unit.unit_type].hp
		record["shield_pool"]=int(snapshot.get("shared_shields",{}).get(unit.side,0))
		var charge=snapshot.get("charge_states",{}).get(str(int(unit.instance_id)),{})
		record["charge_ticks_left"]=maxi(0,int(charge.get("release_tick",0))-int(snapshot.tick));record["charge_cell"]=charge.get("target_cell",[])
		record["is_winding"]=int(snapshot.get("skill_states",{}).get(str(int(unit.instance_id)),{}).get("windup_until",0))>int(snapshot.tick)
		summary.append(record)
	var focused=int(store.state.pending.battle_input.get("focus_targets",{}).get("player",-1))
	board.set_paused(paused,speed);board.show_units(summary,events,int(snapshot.tick),focused)
	if is_instance_valid(battle_label):
		battle_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		battle_label.text="第%d步 · %.1f秒 · %s"%[snapshot.tick,float(snapshot.tick)*.5,"暂停" if paused else "播放"]
		if snapshot.has("shared_shields"):
			battle_label.text+="\n我方共享盾 %d"%int(snapshot.shared_shields.player)
			if summary.any(func(u):return u.side=="player" and u.is_winding):battle_label.text+="\n洛恩前摇中：自身受伤×2"
		for unit in summary:
			if unit.charge_ticks_left>0:battle_label.text+="\n重击格(%d,%d) · %d步后落下"%[int(unit.charge_cell[0]),int(unit.charge_cell[1]),int(unit.charge_ticks_left)]
		for event in events:
			if event.get("attack_type")=="charged_strike":battle_label.text+="\n"+("重击落空" if event.action=="cancelled" else "重击命中%d点"%int(event.damage))
			if event.get("absorbed",0)>0:battle_label.text+="\n盾替#%d吸收%d，剩%d"%[int(event.target),int(event.absorbed),int(event.shared_shield_remaining)]
func show_travel_party():
	var state=store.state;var party=[]
	var j=state.pending.get("journey",{})
	for unit in state.battle_snapshot.states:
		if unit.side!="player" or not unit.alive:continue
		var shown=unit.duplicate(true)
		if not j.is_empty() and j.node not in ["first","elite"]:shown.hp=int(j.hp.get(str(int(unit.instance_id)),unit.hp))
		shown.position=[3+party.size()%4,2+int(party.size()/4)];party.append(shown)
	board.set_paused(true,1);board.show_units(party)
func advance():
	if battle_outro_left>0:return
	if route_map.visible or context_ui.mode=="details":return
	var animate_transition=not paused
	if send("ADVANCE_BATTLE",{},":%d"%int(store.state.battle_snapshot.tick)):
		var warnings=store.state.battle_snapshot.events.filter(func(e):return int(e.tick)==int(store.state.battle_snapshot.tick) and e.action=="charge_windup")
		if not warnings.is_empty():
			session_log.record("charge_warning",{"tick":store.state.battle_snapshot.tick,"release_tick":warnings[0].ready_tick})
			if pause_on_charge and not charge_notice_seen:paused=true;charge_notice_seen=true;pause_reason="charge"
		if store.state.phase!="battle":
			if animate_transition and board.visible:
				show_battle();battle_outro_left=.50
				if board.contact_enabled:
					for contact_time in board.contact.death_times.values():battle_outro_left=maxf(battle_outro_left,float(contact_time)+.46+.03)
				context_ui.status.text="战斗结束 · 正在收束"
				for key in context_ui.footer_buttons:
					if key not in ["pause","speed"]:context_ui.footer_buttons[key].disabled=true
				sync_battle_controls()
			else:paused=true;refresh()
		else:show_battle();page_token="%d-%d"%[store.state.revision,Time.get_ticks_usec()]
func _exit_tree():session_log.finish()
func _process(delta):
	frame_deployment()
	if is_instance_valid(board) and is_instance_valid(context_ui):
		var reserved=[]
		for panel in [context_ui.header_panel,context_ui.footer_panel,context_ui.panel,context_ui.toast]:
			if is_instance_valid(panel) and panel.is_visible_in_tree():reserved.append(panel.get_global_rect())
		board.set_label_reserved(reserved)
	session_log.advance(delta,DisplayServer.window_is_focused())
	if is_instance_valid(context_ui) and context_ui.exit_overlay.visible:return
	if battle_outro_left>0:
		board.set_paused(paused,speed)
		if not paused:battle_outro_left=maxf(0,battle_outro_left-delta*speed)
		if battle_outro_left<=0:paused=true;refresh()
		return
	if ready_to_play and not store.state.is_empty() and store.state.phase=="battle" and not paused and not route_map.visible and context_ui.mode!="details":
		clock+=delta*speed
		if clock>=.5:clock=fmod(clock,.5);advance()
func settlement():
	paused=true
	var title="返回结算 · "+str(store.state.battle_result.result_label)
	if store.state.pending.get("route")=="boundary" and store.state.battle_result.result=="player_win":title="道路阻断 · 返回结算" if store.state.pending.boundary.completed else "提前折返 · 返回结算"
	label(ui,title,21);show_travel_party()
	if store.state.pending.battle_input.has("charge_config"):
		var reports=store.state.battle_result.events
		paragraph("精英重击：预警%d次，命中%d次，落空%d次。"%[reports.filter(func(e):return e.action=="charge_windup").size(),reports.filter(func(e):return e.action=="attack" and e.get("attack_type")=="charged_strike").size(),reports.filter(func(e):return e.action=="cancelled" and e.get("attack_type")=="charged_strike").size()])
	var shield_total=0
	for event in store.state.battle_result.events:shield_total+=int(event.get("absorbed",0))
	if shield_total>0:label(ui,"本场共享盾实际吸收%d点伤害"%shield_total,17)
	if engine.settlement_version(store.state)==2:
		var plan=RETURN_VIEW.preview(store.state,{},engine)
		paragraph("\n".join(plan.lines))
		label(ui,"无伤者轮休1次，归队伤员养伤2次；安全撤回不增加胜利收益。",15)
		transport_summary=label(actions,"可救伤员接回%d人 · 城镇援助%d铜币\n确认后按实际战果一次入账。"%[int(plan.people.wounded_returning),int(plan.aid_coins)],15)
		transport_summary.clip_text=true;transport_summary.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
		transport_summary.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;transport_summary.max_lines_visible=2
		transport_summary.tooltip_text="\n".join(plan.lines)
		button(actions,"确认实际战果并归城",settle,"settle")
		return
	var wiped=store.state.battle_result.result in ["enemy_win","draw"]
	if wiped:label(ui,"队伍覆灭：普通出战者正式吞并；英雄失联。",15)
	else:
		for id in engine.wounded(store.state):
			var check=checkbox(ui,"带回 #%d %s · 否则失联6日"%[id,store.state.roster[str(id)].name],true)
			bring_rows[id]=check;check.toggled.connect(func(_v):update_ledger())
	lorne_stay=checkbox(ui,"确认：洛恩将随留下的伤兵失联")
	lorne_stay.visible=false
	leave_confirm=checkbox(ui,"确认留下所列伤兵并开始6日期限");leave_confirm.visible=false
	label(ui,"本次新增收益（不扣既有仓库）",18)
	label(ui,"另有城镇援助%d铜币 · 不属于运输战利品"%engine.return_aid(store.state),14)
	for item in engine.loot(store.state):
		var row=line(ui);label(row,"%s ×%d · 值%d"%[item.name,item.quantity,item.unit_value],15);label(row,"弃",15)
		loot_rows[item.id]=spin(row,0,int(item.quantity),0);loot_rows[item.id].value_changed.connect(func(_v):update_ledger())
	battle_label=label(ui,"",17);battle_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	label(ui,"活着返回轮休1次；伤兵恢复2次。
本次返回不抵消自身轮休。",15)
	button(actions,"建议最小弃置（可修改）",suggest_discard,"suggest_discard")
	transport_summary=label(actions,"",15);transport_summary.clip_text=true;transport_summary.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	transport_summary.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;transport_summary.max_lines_visible=2
	button(actions,"确认弃置、人员去向并入账",settle,"settle");suggest_discard()
	lorne_stay.toggled.connect(func(_v):update_ledger());leave_confirm.toggled.connect(func(_v):update_ledger());update_ledger()
func settlement_payload() -> Dictionary:
	if engine.settlement_version(store.state)==2:return {}
	var bring=[];var discard={}
	for id in bring_rows:
		if bring_rows[id].button_pressed:bring.append(id)
	for key in loot_rows:
		if int(loot_rows[key].value)>0:discard[key]=int(loot_rows[key].value)
	return {"bring_ids":bring,"discard":discard,"acknowledge_lorne_stays":lorne_stay.button_pressed if is_instance_valid(lorne_stay) else false,"acknowledge_abandonment":leave_confirm.button_pressed if is_instance_valid(leave_confirm) else false}
func suggest_discard():
	var payload=settlement_payload();var required=int(engine.transport(store.state,payload.bring_ids).required_discard)
	var combinations={0:{}}
	for item in engine.loot(store.state):
		var next={}
		for total in combinations:
			for quantity in range(int(item.quantity)+1):
				var value=int(total)+quantity*int(item.unit_value)
				if not next.has(value):
					var chosen=combinations[total].duplicate();chosen[item.id]=quantity;next[value]=chosen
		combinations=next
	var best=-1
	for value in combinations:
		if value>=required and (best<0 or value<best):best=value
	if best>=0:
		for key in loot_rows:loot_rows[key].value=combinations[best].get(key,0)
	update_ledger()
func update_ledger():
	var payload=settlement_payload()
	var abandonment=engine.abandonment_plan(store.state,payload.bring_ids)
	if is_instance_valid(lorne_stay):
		var signature=JSON.stringify(abandonment,"",true)
		if signature!=abandonment_signature:
			lorne_stay.set_pressed_no_signal(false)
			if is_instance_valid(leave_confirm):leave_confirm.set_pressed_no_signal(false)
			abandonment_signature=signature
		lorne_stay.visible=not abandonment.follows_ids.is_empty()
	if is_instance_valid(leave_confirm):leave_confirm.visible=store.state.pending.get("route") in ["tutorial_trail","outpost","boundary"] and not abandonment.left_ids.is_empty() and store.state.battle_result.result not in ["enemy_win","draw"]
	var account=engine.transport(store.state,payload.bring_ids);var value=0
	for item in engine.loot(store.state):value+=int(payload.discard.get(item.id,0))*int(item.unit_value)
	if is_instance_valid(battle_label):battle_label.text="新增清算值 %d · 损失比例 %d%%
至少弃置 %d · 已选弃置 %d"%[account.total,account.loss_percent,account.required_discard,value]
	if not abandonment.left_ids.is_empty() and store.state.battle_result.result not in ["enemy_win","draw"]:
		battle_label.text+="\n将留下：%s；当前第%d日，最晚第%d日营救。"%["、".join(abandonment.left_ids.map(func(id):return store.state.roster[str(id)].name)),int(store.state.day),int(abandonment.deadline_day)]
	if not abandonment.follows_ids.is_empty():battle_label.text+="\n洛恩将随伤兵留下；最晚第%d日营救。"%abandonment.deadline_day
	if is_instance_valid(transport_summary):
		var plan=RETURN_VIEW.preview(store.state,payload,engine)
		var carried="、".join(plan.items.map(func(item):return "%s%d"%[item.name,int(item.brought)]))
		transport_summary.text="最终带回：%s · 另计援助%d铜币\n%s"%[carried if not carried.is_empty() else "无战利品",int(plan.aid_coins),"运输要求已满足；确认后一次入账。" if plan.can_confirm else "\n".join(plan.warnings.slice(0,2))]
		transport_summary.tooltip_text=transport_summary.text
func settle():
	if send("SETTLE",settlement_payload()):refresh()
func inspect_units(ids: Array):
	board.selected_ids=ids
	for id in board.figures:board.figures[id].label.visible=board.figures.size()<=16 or id in ids or not board.stats[id].get("alive",true)
	var lines=[]
	for id in ids:
		var unit=board.stats[id];lines.append("#%d %s · HP %d · %s"%[id,engine.units[unit.unit_type].name,int(unit.get("hp",0)),"存活占格" if unit.get("alive",true) else "倒地可通行"])
	inspection.text="
".join(lines) if not lines.is_empty() else "空格；点击其他格查看。"
	context_ui.notify(inspection.text)
func smoke():
	# Exercise actual UI handlers in the exported application, then write evidence.
	paused=true
	if store.state.is_empty():commands_ui.new.pressed.emit();smoke_checks.append(store.state.phase=="town")
	dismiss_story()
	if store.state.expedition==0 and not str(options.smoke).begins_with("map_") and not str(options.smoke).begins_with("trail_") and not str(options.smoke).begins_with("rescue_") and not str(options.smoke).begins_with("charge_") and not str(options.smoke).begins_with("growth_") and not str(options.smoke).begins_with("boundary_") and not str(options.smoke).begins_with("town_"):
		route.set_item_metadata(0,"tutorial");route.set_item_text(0,"旧版单战教程回归 · 2日");preview_formation()
	if str(options.smoke).begins_with("map_"):
		await map_smoke()
	elif str(options.smoke).begins_with("town_"):
		await town_smoke()
	elif str(options.smoke).begins_with("boundary_"):
		await boundary_smoke()
	elif str(options.smoke).begins_with("growth_"):
		await growth_smoke()
	elif str(options.smoke).begins_with("charge_"):
		await charge_smoke()
	elif str(options.smoke).begins_with("rescue_"):
		await rescue_smoke()
	elif str(options.smoke).begins_with("trail_"):
		await trail_smoke()
	elif str(options.smoke).begins_with("hero_"):
		await hero_smoke()
	elif options.smoke in ["first","crash"]:
		commands_ui.depart.pressed.emit();paused=true;smoke_checks.append(store.state.phase=="battle")
		var before=JSON.stringify(store.state,"",true)
		commands_ui.pause.pressed.emit();commands_ui.pause.pressed.emit()
		commands_ui.speed.pressed.emit();commands_ui.speed.pressed.emit()
		smoke_checks.append(JSON.stringify(store.state,"",true)==before)
		commands_ui.pause.pressed.emit() # First single-step starts from active playback.
		for index in range(5):
			commands_ui.step.pressed.emit()
			smoke_checks.append(store.state.battle_snapshot.states.filter(func(u):return u.alive).all(func(u):return board.figures[int(u.instance_id)].node.position==board.position_at(u.x,u.y)))
		await capture("battle")
	elif options.smoke=="resume":
		smoke_checks.append(store.state.phase=="battle" and store.state.battle_snapshot.tick==5)
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		await capture("settlement")
		if store.state.phase=="settlement":
			for key in loot_rows:loot_rows[key].value=loot_rows[key].max_value
			commands_ui.settle.pressed.emit()
		smoke_checks.append(store.state.phase=="town")
		dismiss_story()
		await capture("town")
		if store.state.phase=="town":commands_ui.depart.pressed.emit();paused=true
		smoke_checks.append(store.state.phase=="battle" and store.state.expedition==2)
		await capture("second")
	elif options.smoke=="check":smoke_checks.append(store.state.phase=="battle" and store.state.expedition==2)
	var data={"checks":smoke_checks,"passed":not false in smoke_checks,"phase":store.state.phase,"expedition":store.state.expedition,"revision":store.state.revision,"locked_input":store.state.pending.get("battle_input",{}),"state_sha256":JSON.stringify(store.state,"",true).sha256_text()}
	var path=str(options.get("evidence-dir",store.root));DirAccess.make_dir_recursive_absolute(path)
	if str(options.smoke).begins_with("trail_") or str(options.smoke).begins_with("rescue_") or str(options.smoke).begins_with("charge_"):data["facts"]=store.state.facts.duplicate(true);data["roster"]=store.state.roster.duplicate(true);data["resources"]=store.state.resources.duplicate()
	var file=FileAccess.open(path.path_join("smoke_"+str(options.smoke)+".json"),FileAccess.WRITE);file.store_string(JSON.stringify(data,"  "));file.close()
	if options.smoke in ["map_start","crash","hero_start","trail_start","rescue_start","charge_start","growth_start","growth_resume","boundary_start"]:await get_tree().create_timer(60).timeout
	get_tree().quit(0 if data.passed else 1)
func town_smoke():
	var before=JSON.stringify(store.state,"",true)
	# Exercise native viewport picking through the actual building Area3D.
	var mouse=InputEventMouseButton.new();mouse.button_index=MOUSE_BUTTON_LEFT;mouse.pressed=true;mouse.position=town_scene.camera.unproject_position(Vector3(-4.3,1,-3))
	get_viewport().push_input(mouse,true);await get_tree().physics_frame;await get_tree().process_frame;await get_tree().process_frame
	smoke_checks.append(town_tab=="barracks" and JSON.stringify(store.state,"",true)==before)
	mouse=InputEventMouseButton.new();mouse.button_index=MOUSE_BUTTON_LEFT;mouse.pressed=false;mouse.position=town_scene.camera.unproject_position(Vector3(-4.3,1,-3));get_viewport().push_input(mouse,true)
	for place in ["overview","barracks","training","rest","warehouse","deploy"]:
		town_page.buttons["nav_"+place].pressed.emit()
		smoke_checks.append(JSON.stringify(store.state,"",true)==before and town_tab==place)
		smoke_checks.append(board.visible==(place=="deploy") and town_scene.visible==(place!="deploy"))
		await capture("town_"+place)
	# The former barracks volume must not steal a board click while hidden.
	mouse=InputEventMouseButton.new();mouse.button_index=MOUSE_BUTTON_LEFT;mouse.pressed=true;mouse.position=board.camera.unproject_position(Vector3(-4.3,1,-3));get_viewport().push_input(mouse,true)
	await get_tree().physics_frame;await get_tree().process_frame;await get_tree().process_frame
	smoke_checks.append(town_tab=="deploy" and JSON.stringify(store.state,"",true)==before)
	mouse=InputEventMouseButton.new();mouse.button_index=MOUSE_BUTTON_LEFT;mouse.pressed=false;mouse.position=board.camera.unproject_position(Vector3(-4.3,1,-3));get_viewport().push_input(mouse,true)
	town_page.buttons.nav_barracks.pressed.emit()
	town_page.buttons.nav_deploy.pressed.emit();rows[1].x.value=3
	town_page.buttons.nav_warehouse.pressed.emit();town_page.buttons.nav_deploy.pressed.emit()
	smoke_checks.append(rows[1].x.value==3 and JSON.stringify(store.state,"",true)==before)
	town_page.buttons.nav_barracks.pressed.emit()
	if options.smoke=="town_manage":
		var coins=int(store.state.resources.coins);var count=store.state.roster.size()
		town_page.buttons.recruit_shield.pressed.emit()
		smoke_checks.append(store.state.resources.coins==coins-int(engine.params.recruit_cost) and store.state.roster.size()==count+1)
		await capture("town_recruited")
	town_page.buttons.nav_overview.pressed.emit()
	smoke_checks.append(town_tab=="overview" and town_scene.camera.current)
	await capture("town_final")
func charge_smoke():
	var branch=str(options.get("trail-branch","safe"))
	if options.smoke=="charge_start":
		commands_ui.recommend_first.pressed.emit();commands_ui.depart.pressed.emit();finish_smoke_battle()
		smoke_checks.append(store.state.phase=="journey" and store.state.pending.journey.encounter_version==2 and board.stage_set.current=="caravan")
		await capture("charge_caravan");commands_ui.journey_pass.pressed.emit();await capture("charge_camp");commands_ui.journey_rest.pressed.emit()
		if branch=="safe":commands_ui.recommend_elite.pressed.emit()
		await capture("charge_formation");commands_ui.continue_journey.pressed.emit();paused=true
		for guard in range(121):
			if store.state.phase!="battle" or store.state.battle_snapshot.get("charge_states",{}).get("10003",{}).get("release_tick",0)>int(store.state.battle_snapshot.tick):break
			advance()
		var state=store.state;var pending=state.battle_snapshot.charge_states["10003"]
		smoke_checks.append(pending.release_tick==int(state.battle_snapshot.tick)+2 and paused and charge_notice_seen)
		smoke_checks.append(state.pending.battle_input.charge_config[0].caster_id==10003)
		var uninterrupted=engine.CORE.new();uninterrupted.configure(state.pending.battle_input,engine.units,engine.rules);uninterrupted.restore(state.battle_snapshot)
		var file=FileAccess.open(str(options["evidence-dir"]).path_join("charge_expected.json"),FileAccess.WRITE);file.store_string(JSON.stringify(uninterrupted.run()));file.close()
		await capture("charge_warning")
	elif options.smoke=="charge_resume":
		var snap=store.state.battle_snapshot;var at=int(snap.tick);var mark=snap.charge_states["10003"].target_cell.duplicate()
		smoke_checks.append(snap.charge_states["10003"].release_tick==at+2)
		advance();smoke_checks.append(store.state.battle_snapshot.charge_states["10003"].release_tick==int(store.state.battle_snapshot.tick)+1 and store.state.battle_snapshot.charge_states["10003"].target_cell==mark)
		await capture("charge_one_tick");advance();await capture("charge_release")
		smoke_checks.append(store.state.battle_snapshot.events.any(func(e):return e.tick==at+2 and e.get("attack_type")=="charged_strike"))
		finish_smoke_battle()
		var expected=engine.CORE.normalize_numbers(JSON.parse_string(FileAccess.get_file_as_string(str(options["evidence-dir"]).path_join("charge_expected.json"))))
		smoke_checks.append(store.state.battle_result==expected and store.state.battle_result.result=="player_win")
		smoke_checks.append(engine.wounded(store.state)==([] if branch=="safe" else [1]))
		if branch=="leave":
			bring_rows[1].button_pressed=false
			for key in loot_rows:loot_rows[key].value=0
			leave_confirm.button_pressed=true
		await capture("charge_transport");commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.phase=="town" and store.state.facts.formation_payoff.improved==(branch=="safe"))
		smoke_checks.append(store.state.resources.recruit_token==(0 if branch=="bring" else 1) and store.state.resources.crystals==40)
		await capture("charge_returned")
	elif options.smoke=="charge_check":
		smoke_checks.append(store.state.phase=="town" and store.state.facts.tutorial_trail_return.node=="elite")
		var before=JSON.stringify(store.state,"",true);commands_ui.history.pressed.emit();await capture("charge_history");reading_history=false;refresh();smoke_checks.append(before==JSON.stringify(store.state,"",true))

func finish_smoke_battle():
	paused=true
	for guard in range(121):
		if store.state.phase!="battle":break
		advance()
func select_rescue():
	route.select(2);rescuing.button_pressed=true;preview_formation()
func rescue_smoke():
	var mode=str(options.get("rescue-mode","normal"))
	if options.smoke=="rescue_start":
		commands_ui.recommend_first.pressed.emit();commands_ui.depart.pressed.emit();finish_smoke_battle()
		commands_ui.journey_pass.pressed.emit();commands_ui.journey_rest.pressed.emit();commands_ui.continue_journey.pressed.emit();finish_smoke_battle()
		smoke_checks.append(engine.wounded(store.state)==[1])
		bring_rows[1].button_pressed=false
		for key in loot_rows:loot_rows[key].value=0
		leave_confirm.button_pressed=true;commands_ui.settle.pressed.emit();dismiss_story()
		commands_ui.recruit_lorne.pressed.emit();dismiss_story()
		if mode in ["deadline","late"]:
			for day in range(4):commands_ui.day.pressed.emit()
		select_rescue()
		if mode=="failure":
			for id in rows:rows[id].enable.set_pressed_no_signal(id==2)
			preview_formation()
		commands_ui.depart.pressed.emit()
		smoke_checks.append(store.state.phase=="rescue_journey" and store.state.pending.rescue_path.node=="approach")
		await capture("rescue_entry");commands_ui.rescue_direct.pressed.emit();await capture("rescue_camp")
		smoke_checks.append(store.state.pending.rescue_path.node=="camp" and store.state.pending.rescue_path.attention==1 and store.state.roster["1"].status=="CAPTURED")
	elif options.smoke=="rescue_resume":
		smoke_checks.append(store.state.phase=="rescue_journey" and store.state.pending.rescue_path.node=="camp")
		if mode=="late":
			var before=JSON.stringify(store.state,"",true);commands_ui.rescue_wait.pressed.emit()
			smoke_checks.append(before==JSON.stringify(store.state,"",true))
			expiry.button_pressed=true;commands_ui.rescue_wait.pressed.emit()
			smoke_checks.append(store.state.day==10 and store.state.roster["1"].status=="ABSORBED")
			await capture("rescue_overdue");commands_ui.rescue_withdraw.pressed.emit();var money=store.state.resources.duplicate();commands_ui.settle.pressed.emit()
			smoke_checks.append(store.state.phase=="town" and store.state.resources==money and engine.valid_expeditions(store.state)==1)
		else:
			commands_ui.rescue_breach.pressed.emit()
			smoke_checks.append(store.state.pending.rescue_path.attention==3 and store.state.roster["1"].status=="CAPTURED")
			await capture("rescue_guards");commands_ui.rescue_fight.pressed.emit();finish_smoke_battle();await capture("rescue_result")
			smoke_checks.append(store.state.phase=="settlement" and store.state.battle_result.result==("enemy_win" if mode=="failure" else "player_win"))
			commands_ui.settle.pressed.emit()
			if mode=="failure":
				smoke_checks.append(store.state.roster["1"].status=="CAPTURED" and store.state.roster["1"].deadline_day==9 and store.state.roster["2"].status=="ABSORBED")
				dismiss_story();select_rescue();commands_ui.depart.pressed.emit();commands_ui.rescue_direct.pressed.emit();commands_ui.rescue_breach.pressed.emit();commands_ui.rescue_fight.pressed.emit();finish_smoke_battle();commands_ui.settle.pressed.emit()
			smoke_checks.append(store.state.roster["1"].status=="RECOVERING" and store.state.day==(9 if mode=="deadline" else (7 if mode=="failure" else 5)))
		for guard in range(16):
			var scene=STORY.pending(store.state)
			if scene.is_empty():break
			if str(scene.id).begins_with("rescue_return_"):await capture("rescue_return_story")
			dismiss_story()
		await capture("rescue_town")
	elif options.smoke=="rescue_check":
		smoke_checks.append(store.state.phase=="town" and store.state.roster["1"].status==("ABSORBED" if mode=="late" else "RECOVERING"))
		var before=JSON.stringify(store.state,"",true);commands_ui.history.pressed.emit();await capture("rescue_history");reading_history=false;refresh();smoke_checks.append(before==JSON.stringify(store.state,"",true))

func trail_smoke():
	var branch=str(options.get("trail-branch","safe"))
	if options.smoke=="trail_start":
		commands_ui.recommend_first.pressed.emit()
		smoke_checks.append(formation_payload().route=="tutorial_trail" and formation_payload().deployment.size()==2)
		commands_ui.depart.pressed.emit();paused=true
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		smoke_checks.append(store.state.phase=="journey" and store.state.pending.journey.node=="caravan")
		smoke_checks.append(board.stats.values().all(func(u):return u.alive and u.side=="player"))
		await capture("caravan")
		commands_ui.journey_mark.pressed.emit()
		smoke_checks.append(store.state.pending.journey.node=="camp" and store.state.day==4 and store.state.expedition==1)
		smoke_checks.append(board.stats.values().all(func(u):return u.alive and u.side=="player"))
		await capture("camp_checkpoint")
	elif options.smoke=="trail_resume":
		smoke_checks.append(store.state.phase=="journey" and store.state.pending.journey.node=="camp" and store.state.day==4)
		commands_ui.journey_rest.pressed.emit()
		smoke_checks.append(store.state.pending.journey.hp=={"1":45,"3":24} and store.state.pending.journey.food==1)
		if branch=="safe":commands_ui.recommend_elite.pressed.emit()
		await capture("formation")
		commands_ui.continue_journey.pressed.emit();paused=true
		smoke_checks.append(store.state.phase=="battle" and store.state.pending.cp_spent==10 and store.state.expedition==1)
		var expected=engine.CORE.new();expected.configure(store.state.pending.battle_input,engine.units,engine.rules);expected.restore(store.state.battle_snapshot)
		var reference=expected.run()
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		smoke_checks.append(store.state.phase=="settlement" and store.state.battle_result==reference and store.state.battle_result.result=="player_win")
		smoke_checks.append(engine.wounded(store.state)==([] if branch=="safe" else [1]))
		smoke_checks.append(board.stats.values().all(func(u):return u.alive and u.side=="player"))
		if branch=="leave":
			bring_rows[1].button_pressed=false
			for key in loot_rows:loot_rows[key].value=0
			smoke_checks.append(leave_confirm.visible and not leave_confirm.button_pressed and battle_label.text.contains("最晚第10日"))
			leave_confirm.button_pressed=true
		await capture("transport")
		commands_ui.settle.pressed.emit()
		smoke_checks.append(store.state.phase=="town" and store.state.resources.crystals==40 and store.state.resources.recruit_token==(0 if branch=="bring" else 1))
		smoke_checks.append(store.state.facts.formation_payoff.improved==(branch=="safe"))
		# Read and capture actual branch text; scene history persists exact text.
		for guard in range(16):
			var card=STORY.pending(store.state)
			if card.is_empty():break
			if card.id=="trail_return":await capture("return_story")
			if card.id=="formation_payoff":await capture("payoff")
			var key="story_later" if card.id=="lorne_offer" else ("story_bring" if commands_ui.has("story_bring") else "story_continue")
			commands_ui[key].pressed.emit()
		smoke_checks.append(STORY.seen(store.state,"trail_return") and STORY.seen(store.state,"formation_payoff"))
		if branch=="leave":
			smoke_checks.append(store.state.roster["1"].status=="CAPTURED" and store.state.roster["1"].deadline_day==10)
			route.select(2);rescuing.button_pressed=true;preview_formation()
		commands_ui.depart.pressed.emit();paused=true
		if store.state.phase=="rescue_journey":
			commands_ui.rescue_direct.pressed.emit();commands_ui.rescue_wait.pressed.emit();commands_ui.rescue_fight.pressed.emit();paused=true
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		smoke_checks.append(store.state.phase=="settlement" and store.state.battle_result.result=="player_win")
		commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.phase=="town" and store.state.expedition==2)
		if branch=="leave":smoke_checks.append(store.state.roster["1"].status=="RECOVERING" and store.state.day==7)
		if branch=="bring":
			smoke_checks.append(store.state.resources.recruit_token>=1)
			commands_ui.recruit_lorne.pressed.emit();dismiss_story()
			smoke_checks.append(store.state.facts.get("lorne_recruited",false))
		await capture("continued")
	elif options.smoke=="trail_check":
		smoke_checks.append(store.state.phase=="town" and store.state.expedition==2 and STORY.seen(store.state,"trail_return"))
		var before=JSON.stringify(store.state,"",true)
		commands_ui.history.pressed.emit();await capture("history");reading_history=false;refresh()
		smoke_checks.append(before==JSON.stringify(store.state,"",true))

func pick_route(value: String):
	for i in range(route.item_count):
		if route.get_item_metadata(i)==value:route.select(i);preview_formation();return
	smoke_checks.append(false)
func boundary_party(ids: Array,route_name: String):
	var specs=[]
	for i in range(ids.size()):specs.append([ids[i],2+i*2])
	growth_deployment(specs);pick_route(route_name)
	if is_instance_valid(shield_trigger):shield_trigger.select(1)
func boundary_smoke():
	var branch=str(options.get("boundary-branch","observe"))
	if options.smoke=="boundary_start":
		commands_ui.recommend_first.pressed.emit();commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle()
		commands_ui.journey_pass.pressed.emit();commands_ui.journey_rest.pressed.emit();commands_ui.recommend_elite.pressed.emit();commands_ui.continue_journey.pressed.emit();finish_smoke_battle();commands_ui.settle.pressed.emit();dismiss_story()
		commands_ui.recruit_lorne.pressed.emit();dismiss_story()
		boundary_party([7,2,4],"commission");commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle();commands_ui.settle.pressed.emit();dismiss_story()
		boundary_party([1,3,5,6],"commission");commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle();commands_ui.settle.pressed.emit()
		for guard in range(10):
			var scene=STORY.pending(store.state)
			if scene.is_empty():break
			if scene.id=="act1_memory":await capture("normal_memory")
			dismiss_story_once()
		smoke_checks.append(engine.valid_expeditions(store.state)==3 and STORY.seen(store.state,"act1_new_enemy") and STORY.seen(store.state,"act1_memory"))
		boundary_party([7,2,4],"outpost");await capture("outpost_preview");commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle()
		smoke_checks.append(store.state.battle_result.result=="player_win" and engine.wounded(store.state).is_empty())
		await capture("outpost_result");commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(engine.valid_expeditions(store.state)==4 and not store.state.facts.get("boundary_seen",false))
		if branch.begins_with("wounded"):
			boundary_party([1,3,5,6],"commission");commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle();commands_ui.settle.pressed.emit();dismiss_story()
			boundary_party([7,2],"boundary");shield_wall.button_pressed=false;focus.button_pressed=true;focus_target.select(1)
		else:
			boundary_party([1,3,5,6],"outpost");pick_route("boundary")
			smoke_checks.append(board.figures[30002].unit_type=="archer")
		commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle()
		smoke_checks.append(store.state.phase=="boundary" and engine.wounded(store.state)==([2] if branch.begins_with("wounded") else []))
		await capture("boundary_approach");commands_ui.boundary_forward.pressed.emit()
		smoke_checks.append(store.state.pending.boundary.stage=="wall" and not store.state.facts.get("boundary_seen",false))
		await capture("boundary_wall")
	elif options.smoke=="boundary_resume":
		smoke_checks.append(store.state.phase=="boundary" and store.state.pending.boundary.stage=="wall" and not store.state.facts.get("boundary_seen",false))
		var day=store.state.day;var outcome=store.state.battle_result.duplicate(true)
		await capture("boundary_restored")
		if branch!="return":commands_ui.boundary_observe.pressed.emit()
		commands_ui.boundary_return.pressed.emit()
		smoke_checks.append(store.state.phase=="settlement" and store.state.battle_result==outcome and store.state.day==day)
		if branch=="wounded_leave":
			bring_rows[2].button_pressed=false
			for key in loot_rows:loot_rows[key].value=0
			lorne_stay.button_pressed=true;leave_confirm.button_pressed=true
		elif branch=="wounded_bring":smoke_checks.append(engine.transport(store.state,[2]).required_discard==20)
		await capture("boundary_transport");commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.phase=="town" and store.state.facts.boundary_seen and store.state.facts.awk==15 and store.state.facts.boundary_return.observed==(branch!="return"))
		if branch=="wounded_leave":smoke_checks.append(store.state.roster["2"].status=="CAPTURED" and store.state.roster["7"].status=="CAPTURED")
		elif branch=="wounded_bring":smoke_checks.append(store.state.roster["2"].status=="RECOVERING" and store.state.roster["2"].rest_remaining==2)
		await capture("boundary_returned");var money=store.state.resources.duplicate();var people=store.state.roster.duplicate(true);commands_ui.act2.pressed.emit()
		smoke_checks.append(store.state.facts.current_act==2 and store.state.resources==money and store.state.roster==people and store.state.day==day)
		await capture("act2_entry");dismiss_story()
	elif options.smoke=="boundary_check":
		smoke_checks.append(store.state.phase=="town" and store.state.facts.current_act==2 and STORY.seen(store.state,"act2_entry"))
		var before=JSON.stringify(store.state,"",true);commands_ui.history.pressed.emit();await capture("boundary_history");reading_history=false;refresh();smoke_checks.append(before==JSON.stringify(store.state,"",true))
func dismiss_story_once():
	for key in ["story_continue","story_bring","story_later"]:
		if commands_ui.has(key):commands_ui[key].pressed.emit();return

func growth_deployment(specs: Array):
	for id in rows:
		rows[id].enable.set_pressed_no_signal(false);rows[id].reserve.set_pressed_no_signal(false)
	for spec in specs:
		var row=rows[spec[0]];row.enable.set_pressed_no_signal(true);row.x.value=spec[1];row.y.value=2;row.stance.select(0)
	focus.set_pressed_no_signal(false);preview_formation()
func growth_smoke():
	if options.smoke=="growth_start":
		commands_ui.recommend_first.pressed.emit();commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle()
		commands_ui.journey_pass.pressed.emit();commands_ui.journey_rest.pressed.emit();commands_ui.recommend_elite.pressed.emit();commands_ui.continue_journey.pressed.emit();finish_smoke_battle()
		smoke_checks.append(store.state.phase=="settlement" and engine.wounded(store.state).is_empty())
		commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.roster["3"].xp==1 and commands_ui.has("level_3"))
		town_page.buttons.nav_training.pressed.emit();smoke_checks.append(town_page.buttons.has("level_3"))
		await capture("growth_available")
		var day=store.state.day;var money=store.state.resources.duplicate();town_page.buttons.level_3.pressed.emit()
		smoke_checks.append(store.state.roster["3"].level==2 and store.state.roster["3"].xp==0 and not commands_ui.has("level_3"))
		smoke_checks.append(store.state.day==day and store.state.resources==money and store.state.roster["3"].rest_remaining==1)
		await capture("growth_upgraded")
	elif options.smoke=="growth_resume":
		smoke_checks.append(store.state.roster["3"].level==2 and store.state.roster["3"].xp==0 and not commands_ui.has("level_3"))
		smoke_checks.append(store.state.roster["3"].status=="RESTING" and engine.member_stats(store.state.roster["3"]).attack==10)
		await capture("growth_town_resume")
		growth_deployment([[2,3],[4,5],[5,7]]);commands_ui.depart.pressed.emit();paused=true;finish_smoke_battle();commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.roster["3"].status=="READY" and store.state.expedition==2)
		growth_deployment([[1,4],[3,3],[6,5]]);await capture("growth_formation");commands_ui.depart.pressed.emit();paused=true
		smoke_checks.append(store.state.pending.battle_input.growth_config==[{"instance_id":3,"level":2}])
		smoke_checks.append(store.state.battle_snapshot.states.filter(func(u):return u.instance_id==3)[0].hp==30 and store.state.battle_snapshot.states.filter(func(u):return u.instance_id==6)[0].hp==24)
		for i in range(5):advance()
		var b=engine.CORE.new();b.configure(store.state.pending.battle_input,engine.units,engine.rules);b.restore(store.state.battle_snapshot)
		var file=FileAccess.open(str(options["evidence-dir"]).path_join("growth_expected.json"),FileAccess.WRITE);file.store_string(JSON.stringify(b.run()));file.close()
		await capture("growth_battle_checkpoint")
	elif options.smoke=="growth_finish":
		smoke_checks.append(store.state.phase=="battle" and store.state.battle_snapshot.tick==5 and store.state.pending.battle_input.growth_config==[{"instance_id":3,"level":2}])
		await capture("growth_battle_resume");finish_smoke_battle()
		var expected=engine.CORE.normalize_numbers(read(str(options["evidence-dir"]).path_join("growth_expected.json")))
		smoke_checks.append(store.state.battle_result==expected and store.state.battle_result.result=="player_win")
		await capture("growth_result");commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.phase=="town" and store.state.roster["3"].level==2 and store.state.roster["3"].xp==1 and not commands_ui.has("level_3"))
		await capture("growth_returned")
	elif options.smoke=="growth_check":
		smoke_checks.append(store.state.phase=="town" and store.state.expedition==3 and store.state.roster["3"].level==2 and store.state.roster["3"].xp==1)
		var before=JSON.stringify(store.state,"",true);commands_ui.history.pressed.emit();await capture("growth_history");reading_history=false;refresh();smoke_checks.append(before==JSON.stringify(store.state,"",true))

func hero_smoke():
	if options.smoke=="hero_start":
		commands_ui.depart.pressed.emit();paused=true
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		smoke_checks.append(store.state.battle_result.result=="player_win")
		commands_ui.settle.pressed.emit()
		# Show the independent zero-loss lesson, then explicitly invite Lorne.
		for guard in range(6):
			if commands_ui.has("story_recruit"):commands_ui.story_recruit.pressed.emit();break
			dismiss_story_until_offer()
		dismiss_story()
		var heroes=store.state.roster.values().filter(func(m):return m.unit_type=="lorne")
		smoke_checks.append(heroes.size()==1 and heroes[0].hero and store.state.facts.get("transport_lesson_choice")=="bring")
		await capture("lorne_recruited")
		commands_ui.depart.pressed.emit();paused=true
		smoke_checks.append(store.state.pending.battle_input.skill_config[0].trigger=="opening" and store.state.pending.battle_input.budget==14)
		var comparison=engine.CORE.new();comparison.configure(store.state.pending.battle_input,engine.units,engine.rules)
		var expected=comparison.run();var evidence=str(options.get("evidence-dir",store.root));DirAccess.make_dir_recursive_absolute(evidence)
		var reference=FileAccess.open(evidence.path_join("hero_expected.json"),FileAccess.WRITE);reference.store_string(JSON.stringify(expected));reference.close()
		commands_ui.step.pressed.emit()
		smoke_checks.append(store.state.battle_snapshot.tick==1 and store.state.battle_snapshot.events.any(func(e):return e.action=="shield_windup"))
		await capture("lorne_windup")
	elif options.smoke=="hero_resume":
		smoke_checks.append(store.state.phase=="battle" and store.state.battle_snapshot.tick==1)
		commands_ui.step.pressed.emit()
		smoke_checks.append(store.state.battle_snapshot.events.any(func(e):return e.action=="shield_formed") and store.state.battle_snapshot.shared_shields.player>0)
		await capture("lorne_formed")
		for guard in range(121):
			if store.state.phase!="battle":break
			advance()
		var expected=engine.CORE.normalize_numbers(read(str(options.get("evidence-dir",store.root)).path_join("hero_expected.json")))
		smoke_checks.append(store.state.battle_result==expected)
		var protected=store.state.battle_result.events.filter(func(e):return e.get("target_side")=="player" and e.get("absorbed",0)>0)
		smoke_checks.append(not protected.is_empty())
		await capture("lorne_after")
		commands_ui.settle.pressed.emit()
		smoke_checks.append(STORY.pending(store.state).get("id")=="lorne_protection")
		await capture("lorne_report")
		dismiss_story()
	elif options.smoke=="hero_check":
		smoke_checks.append(store.state.phase=="town" and store.state.facts.get("lorne_recruited",false) and STORY.seen(store.state,"lorne_protection"))
		var before=JSON.stringify(store.state,"",true)
		commands_ui.history.pressed.emit();await capture("lorne_history");reading_history=false;refresh()
		smoke_checks.append(before==JSON.stringify(store.state,"",true))
func dismiss_story_until_offer():
	for guard in range(6):
		if commands_ui.has("story_recruit"):return
		var handled=false
		for key in ["story_continue","story_bring"]:
			if commands_ui.has(key):commands_ui[key].pressed.emit();handled=true;break
		if not handled:return
func capture(name: String):
	await get_tree().process_frame;await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path=str(options.get("evidence-dir",store.root));DirAccess.make_dir_recursive_absolute(path)
	get_viewport().get_texture().get_image().save_png(path.path_join(name+".png"))

func map_checkpoint(node: String,picture: String):
	smoke_checks.append(route_map.visible and route_map.model.current==node and not board.visible and not route_content.visible and route_entry.visible)
	var before=JSON.stringify(store.state,"",true)
	await get_tree().create_timer(.65).timeout
	if store.state.phase=="battle":advance()
	smoke_checks.append(before==JSON.stringify(store.state,"",true))
	await capture(picture)
func map_smoke():
	if options.smoke=="map_start":
		commands_ui.recommend_first.pressed.emit();commands_ui.depart.pressed.emit()
		await map_checkpoint("first","map_departure")
		# Future markers cannot teleport the party or unpause the simulation.
		route_map.markers[-1].pressed.emit();smoke_checks.append(route_map.visible)
		await get_tree().process_frame
		var marker=route_map.markers[1];var click=marker.get_global_rect().get_center()
		for down in [true,false]:
			var event=InputEventMouseButton.new();event.button_index=MOUSE_BUTTON_LEFT;event.pressed=down;event.position=click;get_viewport().push_input(event,true)
		await get_tree().process_frame
		smoke_checks.append(not route_map.visible and board.visible and store.state.battle_snapshot.tick==0)
		paused=true
		for i in range(5):advance()
		var before=JSON.stringify(store.state,"",true);commands_ui.map_open.pressed.emit()
		await map_checkpoint("first","map_during_battle");commands_ui.map_enter.pressed.emit()
		smoke_checks.append(before==JSON.stringify(store.state,"",true) and paused)
		finish_smoke_battle();await map_checkpoint("caravan","map_caravan")
		commands_ui.map_enter.pressed.emit();commands_ui.journey_mark.pressed.emit()
		await map_checkpoint("camp","map_camp_checkpoint")
		smoke_checks.append(store.state.day==4 and store.state.expedition==1)
	elif options.smoke=="map_resume":
		await map_checkpoint("camp","map_reopened_camp")
		smoke_checks.append(store.state.day==4 and store.state.pending.journey.caravan_choice=="mark")
		commands_ui.map_enter.pressed.emit()
		if options.get("map-branch")=="early":
			commands_ui.journey_return.pressed.emit();await map_checkpoint("return","map_early_return")
			smoke_checks.append(route_map.model.nodes.filter(func(n):return n.id in ["formation","elite"]).all(func(n):return n.status=="future") and route_map.model.nodes.filter(func(n):return n.id=="camp")[0].status=="visited")
		else:
			commands_ui.journey_rest.pressed.emit();await map_checkpoint("formation","map_formation")
			commands_ui.map_enter.pressed.emit();commands_ui.recommend_elite.pressed.emit();commands_ui.continue_journey.pressed.emit()
			await map_checkpoint("elite","map_elite");commands_ui.map_enter.pressed.emit();paused=true
			finish_smoke_battle();await map_checkpoint("return","map_return")
		commands_ui.map_enter.pressed.emit();commands_ui.settle.pressed.emit();dismiss_story()
		smoke_checks.append(store.state.phase=="town" and not route_map.visible and store.state.expedition==1 and store.state.day==4)
		await capture("map_back_at_base")
	elif options.smoke=="map_check":
		smoke_checks.append(store.state.phase=="town" and store.state.expedition==1 and store.state.day==4 and not route_map.visible)

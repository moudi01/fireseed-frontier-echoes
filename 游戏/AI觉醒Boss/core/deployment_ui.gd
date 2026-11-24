extends RefCounted
## Presentation only: existing host controls remain the sole source of formation input.
const THEME=preload("res://core/interface_theme.gd")
var tabs: TabContainer
var summary: Label
var selection_hint: Label
var roster_cards: Dictionary={}
var roster_controls: Dictionary={}
var root: VBoxContainer

func build(host,parent: VBoxContainer,actions: VBoxContainer) -> void:
	host.paused=true
	host.shield_wall=null;host.shield_trigger=null
	roster_cards.clear();roster_controls.clear()
	root=VBoxContainer.new();root.name="DeploymentContent";root.size_flags_horizontal=Control.SIZE_EXPAND_FILL;root.add_theme_constant_override("separation",7);parent.add_child(root)
	_build_route(host)
	var summary_panel=_panel(root,"DeploymentSummaryPanel")
	summary=host.label(summary_panel,"",16);summary.name="DeploymentSummary";summary.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	selection_hint=host.label(summary_panel,"",14);selection_hint.name="DeploymentSelectionHint";selection_hint.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	tabs=TabContainer.new();tabs.name="DeploymentTabs";tabs.custom_minimum_size.y=250;tabs.size_flags_horizontal=Control.SIZE_EXPAND_FILL;root.add_child(tabs)
	tabs.add_theme_font_size_override("font_size",16)
	for key in ["tab_selected","tab_unselected","tab_hovered","panel"]:
		tabs.add_theme_stylebox_override(key,THEME.box("3a514a" if key=="tab_selected" else "202f31","727663",8))
	var members=_tab("队员","RosterCards")
	var tactics=_tab("战术与营救","DeploymentTactics")
	var ids=host.engine.eligible(host.store.state)
	var selected=ids.slice(0,2 if host.store.state.expedition==0 else mini(3,ids.size()))
	if host.store.state.expedition==0 and 1 in ids and 3 in ids:selected=[1,3]
	var heroes=ids.filter(func(id):return host.store.state.roster[str(id)].unit_type=="lorne")
	if not heroes.is_empty():selected=[heroes[0]]+ids.filter(func(id):return id!=heroes[0]).slice(0,2)
	var member_hint=host.label(members,"勾选出征者；预备队不站上棋盘，也占编制。",14);member_hint.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var index=0
	for member in host.store.state.roster.values():
		_build_member(host,members,member,selected,index)
		if member.status=="READY":index+=1
	_build_tactics(host,tactics,heroes)
	_build_actions(host,tactics,actions,ids)
	# Signals attach only after all host fields required by formation_payload exist.
	for row in host.rows.values():
		row.enable.toggled.connect(func(_v):host.preview_formation())
		row.reserve.toggled.connect(func(_v):host.preview_formation())
		row.x.value_changed.connect(func(_v):host.preview_formation())
		row.y.value_changed.connect(func(_v):host.preview_formation())
		row.stance.item_selected.connect(func(_v):host.preview_formation())
	host.route.item_selected.connect(func(_v):host.preview_formation())
	host.focus.toggled.connect(func(_v):host.preview_formation())
	host.focus_target.item_selected.connect(func(_v):host.preview_formation())
	host.expiry.toggled.connect(func(_v):host.preview_formation())
	host.rescuing.toggled.connect(func(_v):host.preview_formation())
	if is_instance_valid(host.shield_wall):
		host.shield_wall.toggled.connect(func(_v):host.preview_formation())
		host.shield_trigger.item_selected.connect(func(_v):host.preview_formation())
	refresh_summary(host)

func _build_route(host) -> void:
	var route_row=HBoxContainer.new();route_row.add_theme_constant_override("separation",8);root.add_child(route_row)
	host.label(route_row,"远征路线",15)
	host.route=OptionButton.new();host.route.name="DeploymentRoute";host.route.size_flags_horizontal=Control.SIZE_EXPAND_FILL;host.route.add_theme_font_size_override("font_size",15);route_row.add_child(host.route)
	if host.store.state.expedition==0:
		host.route.add_item("林道侦查 · 两战 / 基础2日");host.route.set_item_metadata(0,"tutorial_trail")
	else:
		for pair in [["短程委托 · 2日","commission"],["边境出征 · 3日","outskirts"],["营救专线 · 基础2日","rescue_path"]]:
			host.route.add_item(pair[0]);host.route.set_item_metadata(host.route.item_count-1,pair[1])
		if host.engine.valid_expeditions(host.store.state)>=3:
			host.route.add_item("重甲前哨 · 3日");host.route.set_item_metadata(host.route.item_count-1,"outpost")
		if host.engine.can_reach_boundary(host.store.state) and not host.store.state.facts.get("boundary_seen",false):
			host.route.add_item("深核边界 · 3日");host.route.set_item_metadata(host.route.item_count-1,"boundary")
	host.route_eta=host.label(root,"",14);host.route_eta.name="DeploymentETA";host.route_eta.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART

func _tab(title: String,list_name: String) -> VBoxContainer:
	var page=ScrollContainer.new();page.name=title;page.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;tabs.add_child(page)
	var list=VBoxContainer.new();list.name=list_name;list.size_flags_horizontal=Control.SIZE_EXPAND_FILL;list.add_theme_constant_override("separation",7);page.add_child(list)
	return list

func _panel(parent: Node,node_name: String) -> VBoxContainer:
	var panel=PanelContainer.new();panel.name=node_name;panel.size_flags_horizontal=Control.SIZE_EXPAND_FILL;panel.add_theme_stylebox_override("panel",THEME.box("263d3b","727663",8));parent.add_child(panel)
	var content=VBoxContainer.new();content.add_theme_constant_override("separation",3);panel.add_child(content);return content

func _build_member(host,parent: VBoxContainer,member: Dictionary,selected: Array,index: int) -> void:
	var id=int(member.id)
	var content=_panel(parent,"RosterCard_%d"%id)
	roster_cards[id]=content.get_parent()
	var heading=HBoxContainer.new();heading.add_theme_constant_override("separation",4);content.add_child(heading)
	var enabled=host.checkbox(heading,"#%d %s"%[id,member.name],id in selected);enabled.name="MemberEnabled_%d"%id;enabled.disabled=member.status!="READY";enabled.size_flags_horizontal=Control.SIZE_EXPAND_FILL;enabled.add_theme_font_size_override("font_size",16)
	var state_label=host.label(heading,host.status(member),14)
	state_label.add_theme_color_override("font_color",Color("b9d49c") if member.status=="READY" else Color("dac19a"))
	var stats=host.engine.member_stats(member)
	var type_name=host.engine.units[member.unit_type].name
	var values=host.label(content,"%s · Lv%d · 生命%d · 攻击%d · 经验%d"%[type_name,int(member.level),int(stats.hp),int(stats.attack),int(member.xp)],14);values.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	roster_controls[id]={"enable":enabled,"status":state_label,"stats":values}
	if member.status=="READY":
		var reserve=host.checkbox(heading,"预备");reserve.name="MemberReserve_%d"%id;reserve.add_theme_font_size_override("font_size",14);reserve.tooltip_text="勾选队员并设为预备，不上场但占用编制"
		var controls=HBoxContainer.new();controls.add_theme_constant_override("separation",5);content.add_child(controls)
		host.label(controls,"格位",14)
		var default_first=host.store.state.expedition==0 and id in [1,3]
		var x=host.spin(controls,0,9,4 if default_first else 3+(index%3)*2);x.name="MemberX_%d"%id;x.custom_minimum_size.x=59;x.add_theme_font_size_override("font_size",14);x.tooltip_text="横向格位 x（0—9）"
		var y=host.spin(controls,0,2,(2 if id==1 else 0) if default_first else 2-int(index/3));y.name="MemberY_%d"%id;y.custom_minimum_size.x=59;y.add_theme_font_size_override("font_size",14);y.tooltip_text="纵向格位 y（0—2）；越靠近敌阵数值越大"
		var stance=OptionButton.new();stance.name="MemberStance_%d"%id;stance.add_item("进攻");stance.add_item("防御");stance.add_theme_font_size_override("font_size",14);controls.add_child(stance)
		if default_first:stance.select(1)
		stance.tooltip_text="进攻：主动接近敌人；防御：守住布阵位置"
		host.rows[id]={"enable":enabled,"x":x,"y":y,"stance":stance,"reserve":reserve,"controls":controls}
	else:
		var reasons={"RESTING":"轮休由后续远征结算推进；在城镇等待不会减少。","RECOVERING":"养伤由后续远征结算推进；请换用就绪队员。","CAPTURED":"失联者无法出征；请在战术与营救页核对期限。","ABSORBED":"该队员已被吞并，无法再次编入队伍。","DISMISSED":"该队员已离队。","ACTIVE":"该队员正在出征中。"}
		var reason=host.label(content,reasons.get(member.status,"当前状态无法编入队伍。"),13);reason.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if host.engine.GROWTH.can_level(member,host.engine.rules.cultivation):
		var level_button=host.button(content,"培养至Lv2 · 1经验 / 生命+6 攻击+2",func():
			if host.send("LEVEL_UP",{"unit_id":id},"_%d"%id):host.refresh(),"level_%d"%id)
		level_button.add_theme_font_size_override("font_size",14)

func _build_tactics(host,parent: VBoxContainer,heroes: Array) -> void:
	var focus_section=_panel(parent,"DeploymentFocusPanel")
	host.label(focus_section,"战前集火",17)
	host.focus=host.checkbox(focus_section,"启用集火偏好 · 消耗5指挥点",host.store.state.expedition==0);host.focus.name="DeploymentFocus";host.focus.add_theme_font_size_override("font_size",15)
	host.focus_target=OptionButton.new();host.focus_target.name="DeploymentFocusTarget";host.focus_target.add_theme_font_size_override("font_size",15);focus_section.add_child(host.focus_target)
	var focus_note=host.label(focus_section,"确认出征后自动生效；可用指挥点见上方摘要。",14);focus_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if not heroes.is_empty():
		var shield_section=_panel(parent,"DeploymentShieldPanel")
		host.shield_wall=host.checkbox(shield_section,"启用洛恩自动盾墙",true);host.shield_wall.name="DeploymentShieldWall";host.shield_wall.add_theme_font_size_override("font_size",15)
		host.shield_trigger=OptionButton.new();host.shield_trigger.name="DeploymentShieldTrigger";host.shield_trigger.add_item("友方低于40%时施放");host.shield_trigger.set_item_metadata(0,"low_hp");host.shield_trigger.add_item("开局施放一次 · 首战建议");host.shield_trigger.set_item_metadata(1,"opening");host.shield_trigger.select(1 if not host.store.state.facts.has("lorne_protection") else 0);host.shield_trigger.add_theme_font_size_override("font_size",15);shield_section.add_child(host.shield_trigger)
	var rescue_section=_panel(parent,"DeploymentRescuePanel")
	host.label(rescue_section,"期限与营救",17)
	var captured=host.engine.captured(host.store.state)
	if captured.is_empty():host.label(rescue_section,"当前没有失联队员。",14)
	for id in captured:
		var member=host.store.state.roster[str(id)]
		var deadline=host.label(rescue_section,"#%d %s · 截止第%d日"%[id,member.name,int(member.deadline_day)],14);deadline.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		if member.hero:
			host.button(rescue_section,"祭坛提取 #%d · %d结晶"%[id,mini(50,10+2*int(member.level))+10],func():
				if host.send("ALTAR",{"unit_id":id}):host.refresh())
	host.rescuing=host.checkbox(rescue_section,"营救2日内来得及的失联者",not captured.is_empty());host.rescuing.name="DeploymentRescuing";host.rescuing.add_theme_font_size_override("font_size",14)
	host.expiry=host.checkbox(rescue_section,"允许越过期限（逾期将被吞并）");host.expiry.name="DeploymentExpiry";host.expiry.add_theme_font_size_override("font_size",14)
	var rescue_note=host.label(rescue_section,"固定营救用时2日；截止日当天救回仍有效。停留与阅读不推进日期。",14);rescue_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART

func _build_actions(host,parent: VBoxContainer,actions: VBoxContainer,ids: Array) -> void:
	var depart=host.button(actions,"确认编队并出征",host.depart,"depart");depart.custom_minimum_size.y=44
	if host.store.state.expedition==0:
		var recommend=host.button(parent,"推荐：盾在前，弓在后",host.recommend_first,"recommend_first");recommend.add_theme_font_size_override("font_size",15)
	if host.engine.can_enter_act2(host.store.state) and host.store.state.facts.get("current_act",1)==1:
		host.button(parent,"开启异常调查 · 第二幕",func():
			if host.send("ENTER_ACT2"):host.refresh(),"act2")
	if ids.is_empty():
		host.button(parent,"领取免费应急巡逻队",func():
			if host.send("EMERGENCY_PATROL"):host.refresh(),"emergency")
	if not host.store.state.facts.get("lorne_recruited",false) and host.store.state.facts.get("tutorial_done",false):
		host.button(parent,"邀请洛恩 · 1信物 / 编制提升至14",func():
			if host.send("RECRUIT_LORNE"):host.refresh(),"recruit_lorne")
	var utility=_panel(parent,"DeploymentUtilities")
	host.label(utility,"据点事务",17)
	host.button(utility,"回看已见对白（不改进度）",func():host.reading_history=true;host.refresh(),"history")
	host.button(utility,"在城镇行动1日（不减少轮休）",func():
		if host.send("ADVANCE_DAY",{"acknowledge_expiry":host.expiry.button_pressed}):host.refresh(),"day")
	var note=host.label(utility,"补充队员请前往兵营；培养和休整可从据点入口查看。",14);note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART

func refresh_summary(host) -> void:
	if not is_instance_valid(summary):return
	var payload=host.formation_payload()
	var deployed=payload.deployment.size();var reserves=payload.reserve_ids.size();var cost=0
	for spec in payload.deployment:cost+=int(host.engine.units[host.store.state.roster[str(spec.instance_id)].unit_type].cost)
	for id in payload.reserve_ids:cost+=int(host.engine.units[host.store.state.roster[str(id)].unit_type].cost)
	var limit=14 if host.store.state.facts.get("lorne_recruited",false) else 10
	summary.text="上场 %d  ·  预备 %d  ·  编制 %d/%d\n指挥点 %d/10  ·  %s"%[deployed,reserves,cost,limit,5 if host.focus.button_pressed else 10,"集火已启用" if host.focus.button_pressed else "集火未启用"]
	var warning=""
	if host.has_method("validate_formation_summary"):warning=str(host.validate_formation_summary(payload))
	selection_hint.text=warning if not warning.is_empty() else "在棋盘查看站位；调整后确认出征。"
	selection_hint.visible=not warning.is_empty()
	selection_hint.add_theme_color_override("font_color",Color("f2be89") if not warning.is_empty() else Color("b6c4b5"))
	for id in host.rows:
		var row=host.rows[id];var active=row.enable.button_pressed
		row.controls.visible=active and not row.reserve.button_pressed
		row.x.editable=active and not row.reserve.button_pressed;row.y.editable=active and not row.reserve.button_pressed;row.stance.disabled=not active or row.reserve.button_pressed
		var panel=roster_cards[id]
		panel.add_theme_stylebox_override("panel",THEME.box("3a514a" if active else "202f31","727663",8))
	if is_instance_valid(host.focus_target):host.focus_target.disabled=not host.focus.button_pressed
	if is_instance_valid(host.shield_trigger):host.shield_trigger.disabled=not host.shield_wall.button_pressed

func fit_to_scroll() -> void:
	# The tabs own scrolling; keep route and summary outside that scroll area.
	var scroll=root.get_parent()
	while is_instance_valid(scroll) and not scroll is ScrollContainer:scroll=scroll.get_parent()
	if not is_instance_valid(scroll) or scroll.size.y<100:return
	var fixed=root.get_combined_minimum_size().y-tabs.get_combined_minimum_size().y
	var desired=maxf(130,floorf(scroll.size.y-fixed)-2)
	if absf(tabs.custom_minimum_size.y-desired)>1:tabs.custom_minimum_size.y=desired

extends RefCounted
## Uses only existing campaign commands. Buildings have no fabricated production.
var buttons={}
var host
var parent: VBoxContainer
var state: Dictionary
var rules
func build(p: VBoxContainer,s: Dictionary,r,controller,tab: String):
	parent=p;state=s;rules=r;host=controller
	# Compact navigation remains available when a building is occluded.
	var grid=GridContainer.new();grid.columns=3;parent.add_child(grid)
	for pair in [["据点","overview"],["兵营","barracks"],["训练场","training"],["营舍","rest"],["仓库","warehouse"],["出征","deploy"]]:
		var id=pair[1];var b=Button.new();b.text=pair[0];b.size_flags_horizontal=Control.SIZE_EXPAND_FILL;b.custom_minimum_size.y=38;grid.add_child(b);b.pressed.connect(func():host.open_town(id));buttons["nav_"+id]=b
	parent.add_child(HSeparator.new())
	match tab:
		"overview":overview()
		"barracks":barracks()
		"training":training()
		"rest":rest()
		"warehouse":warehouse()
func text(value: String,size=17):
	var l=Label.new();l.text=value;l.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;l.add_theme_font_size_override("font_size",size);parent.add_child(l);return l
func action(value: String,kind: String,payload: Dictionary={},key=""):
	var b=Button.new();b.text=value;b.custom_minimum_size.y=46;parent.add_child(b)
	b.pressed.connect(func():
		if b.disabled:return
		b.disabled=true
		if host.send(kind,payload):host.refresh()
		else:b.disabled=false)
	if key!="":buttons[key]=b
	return b
func overview():
	text("前线据点",27);text("下一趟远征，从这里开始。",17)
	var ready=rules.eligible(state).size();var resting=0;var recovering=0;var trainable=0
	for m in state.roster.values():
		if m.status=="RESTING":resting+=1
		elif m.status=="RECOVERING":recovering+=1
		if rules.GROWTH.can_level(m,rules.rules.cultivation):trainable+=1
	text("待命 %d   轮休 %d   养伤 %d"%[ready,resting,recovering],20)
	text("兵营补充人手，训练场培养队员。休整情况可在营舍查看；物资保存在仓库。",16)
	if trainable>0:
		var training=Button.new();training.text="%d名队员可以培养  →"%trainable;parent.add_child(training);training.pressed.connect(func():host.open_town("training"))
	var b=Button.new();b.text="前往出征营帐  →";b.custom_minimum_size.y=54;parent.add_child(b);b.pressed.connect(func():host.open_town("deploy"));buttons.departure=b
	if ready==0:action("领取应急巡逻队","EMERGENCY_PATROL",{},"emergency")
	if rules.can_enter_act2(state) and state.facts.get("current_act",1)==1:action("开启异常调查","ENTER_ACT2",{},"act2")
	var history=Button.new();history.text="查看同行记事";parent.add_child(history);history.pressed.connect(func():host.reading_history=true;host.refresh())
func barracks():
	text("兵营 · 补充队伍",24);text("每名士兵 %d 铜币，招募后立即加入名册。"%int(rules.params.recruit_cost))
	for pair in [["盾兵","shield","守住正面，掩护后排。"],["突击兵","cavalry","近身作战，主动接近目标。"],["弓兵","archer","保持距离，提供远程支援。"]]:
		text(pair[2],15);action("招募%s  ·  %d铜币"%[pair[0],int(rules.params.recruit_cost)],"RECRUIT",{"unit_type":pair[1]},"recruit_"+pair[1])
	if state.facts.get("tutorial_done",false) and not state.facts.get("lorne_recruited",false):action("邀请洛恩  ·  1招募信物","RECRUIT_LORNE",{},"lorne")
func training():
	text("训练场 · 队员培养",24);text("消耗队员的出战经验，提升下一趟的实际能力。",16)
	for m in state.roster.values():
		if m.status in ["ABSORBED","DISMISSED"]:continue
		var stats=rules.member_stats(m)
		text("%s   Lv%d  ·  经验%d"%[m.name,int(m.level),int(m.xp)],19)
		text("生命%d  /  攻击%d   ·   %s"%[int(stats.hp),int(stats.attack),host.status(m)],15)
		if rules.GROWTH.can_level(m,rules.rules.cultivation):action("培养至Lv2  ·  1经验  /  生命+6 攻击+2","LEVEL_UP",{"unit_id":int(m.id)},"level_"+str(int(m.id)))
	text("培养不推进日期，也不抵消轮休或养伤。当前可培养至Lv2。",15)
func rest():
	text("营舍 · 轮换与休整",24);text("让待命队员接替出征。轮休与养伤随后续远征结算推进。",16)
	for m in state.roster.values():
		if m.status in ["ABSORBED","DISMISSED"]:continue
		text("%s   ·   %s"%[m.name,host.status(m)],18)
		if m.status=="CAPTURED" and m.hero:action("祭坛提取  ·  %d结晶"%[mini(50,10+2*int(m.level))+10],"ALTAR",{"unit_id":int(m.id)},"altar_"+str(int(m.id)))
	text("在城镇等待不会减少轮休；有失联者时，出征前核对截止日。",15)
func warehouse():
	text("仓库 · 远征所得",24)
	for pair in [["铜币","coins","用于兵营招募队员。"],["结晶","crystals","失联英雄可按实际费用从祭坛提取。"],["招募信物","recruit_token","用于邀请洛恩。"]]:
		text("%s    %d"%[pair[0],int(state.resources[pair[1]])],24);text(pair[2],15);parent.add_child(HSeparator.new())
	text("出征战利品先经过返回运输结算，确认后的物资才进入仓库。",16)

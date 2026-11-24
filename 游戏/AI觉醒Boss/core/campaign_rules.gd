extends RefCounted
## Pure Command -> State + Events. All numbers in campaign_params are prototype anchors.
const PROGRESS=preload("res://core/progression.gd")
const BOUNDARY=preload("res://core/boundary.gd")
const GROWTH=preload("res://core/cultivation.gd")
const STORY=preload("res://core/story.gd")
const RESCUE=preload("res://core/rescue.gd")
const TRAIL=preload("res://core/tutorial.gd")
const CORE=preload("res://core/battle_core.gd")
var units: Dictionary={}
var rules: Dictionary={}
var params: Dictionary={}

func _init(unit_data: Dictionary={},rule_data: Dictionary={},parameters: Dictionary={}) -> void:
	units=unit_data;rules=rule_data;params=parameters

func initial(seed: int) -> Dictionary:
	var roster={}
	var types=["shield","cavalry","archer","shield","cavalry","archer"]
	for index in range(types.size()):
		var id=index+1
		roster[str(id)]={"id":id,"name":({1:"林",3:"岑"}.get(id,units[types[index]].name+"%02d"%id)),"unit_type":types[index],"hero":false,"level":1,"xp":0,"status":"READY","rest_remaining":0,"rest_set_on":0,"captured_day":null,"deadline_day":null,"temporary":false}
	return {"schema_version":1,"settlement_rules_version":2,"revision":0,"run_seed":seed,"rng_state":seed,"phase":"town","day":1,"expedition":0,"next_unit_id":7,"resources":{"coins":int(params.get("starting_coins",30)),"crystals":0,"recruit_token":0},"roster":roster,"pending":{},"battle_snapshot":{},"battle_result":{},"events":[],"applied_commands":{},"absorbed_count":0,"facts":{}}

static func settlement_version(state: Dictionary) -> int:
	# Missing only denotes the existing schema-v1 campaign, never a new-game option.
	return int(state.get("settlement_rules_version",1))

static func supported_schema(state: Dictionary) -> bool:
	var value=state.get("schema_version")
	return CORE.integer(value) and int(value)==1

static func supported_settlement(state: Dictionary) -> bool:
	var value=state.get("settlement_rules_version",1)
	return CORE.integer(value) and value in [1,2]

func bad(message: String) -> Dictionary:
	return {"ok":false,"error":message}

func emit(state: Dictionary,command: Dictionary,kind: String,fields: Dictionary={}) -> void:
	var event={"id":str(command.id)+":"+str(state.events.size()),"kind":kind,"day":state.day}
	event.merge(fields);state.events.append(event)

func valid_state(state: Dictionary) -> bool:
	if not supported_settlement(state):return false
	if not supported_schema(state) or state.get("phase") not in ["town","battle","settlement","journey","rescue_journey","boundary"]:return false
	for key in ["roster","resources","applied_commands","facts","pending","battle_snapshot","battle_result"]:
		if not state.get(key) is Dictionary:return false
	for key in ["day","revision","expedition","next_unit_id","rng_state","run_seed","absorbed_count"]:
		if not CORE.integer(state.get(key)) or state[key]<0:return false
	if state.day<1 or state.next_unit_id<1 or not state.get("events") is Array:return false
	for key in ["coins","crystals","recruit_token"]:
		if not CORE.integer(state.resources.get(key)) or state.resources[key]<0:return false
	for key in ["boundary_seen"]:
		if state.facts.has(key) and not state.facts[key] is bool:return false
	if state.facts.has("current_act") and (not CORE.integer(state.facts.current_act) or state.facts.current_act not in [1,2]):return false
	if state.facts.has("awk") and (not CORE.integer(state.facts.awk) or state.facts.awk<0 or state.facts.awk>100):return false
	if state.facts.has("anomaly_demo"):return false # A demo save is never a normal campaign.
	var largest=0;var absorbed=0
	for key in state.roster:
		var member=state.roster[key]
		if not member is Dictionary or not CORE.integer(member.get("id")) or str(int(member.id))!=key:return false
		largest=maxi(largest,int(member.id))
		if member.get("unit_type") not in units or not member.get("name") is String:return false
		if not member.get("hero") is bool or not member.get("temporary") is bool:return false
		if member.get("status") not in ["READY","ACTIVE","RESTING","RECOVERING","CAPTURED","ABSORBED","DISMISSED"]:return false
		for field in ["level","xp","rest_remaining","rest_set_on"]:
			if not CORE.integer(member.get(field)) or member[field]<0:return false
		if not GROWTH.valid_member(member):return false
		if member.status=="ABSORBED":absorbed+=1
		if member.status=="CAPTURED" and (not CORE.integer(member.get("deadline_day")) or not CORE.integer(member.get("captured_day")) or member.deadline_day<member.captured_day):return false
	if state.next_unit_id<=largest or absorbed!=state.absorbed_count:return false
	var event_ids={}
	for event in state.events:
		if not event is Dictionary or not event.get("id") is String or event_ids.has(event.id):return false
		if event.get("kind")=="expedition_settled" and event.has("valid_for_act") and not event.valid_for_act is bool:return false
		event_ids[event.id]=true
	for value in state.applied_commands.values():
		if not value is String or value.length()!=64:return false
	if state.phase=="town":return state.pending.is_empty() and state.battle_snapshot.is_empty() and state.battle_result.is_empty()
	var pending=state.pending
	for key in ["deployed_ids","reserve_ids","rescue_ids"]:
		if not pending.get(key) is Array:return false
	if not pending.get("battle_input") is Dictionary or not pending.get("action_id") is String:return false
	if not TRAIL.validate(state,units,rules) or not RESCUE.validate(state,self) or not BOUNDARY.validate(state):return false
	var battle=CORE.new()
	if not battle.configure(pending.battle_input,units,rules) or not battle.restore(state.battle_snapshot):return false
	if battle.input.get("growth_config",[])!=growth_config(state,battle.input.player):return false
	var assigned={}
	for value in pending.deployed_ids+pending.reserve_ids:
		if not CORE.integer(value) or not state.roster.has(str(int(value))) or assigned.has(int(value)):return false
		if state.roster[str(int(value))].status!="ACTIVE":return false
		assigned[int(value)]=true
	var expected=pending.deployed_ids.map(func(value):return int(value))
	if pending.get("journey",{}).get("node")=="elite":expected=expected.filter(func(id):return pending.journey.hp.has(str(id)))
	if battle.input.player.map(func(unit):return int(unit.instance_id))!=expected:return false
	if state.phase=="boundary":return battle.finished and battle.result=="player_win" and JSON.stringify(state.battle_result,"",true)==JSON.stringify(battle.summary(),"",true)
	if state.phase=="journey":return battle.finished and JSON.stringify(state.battle_result,"",true)==JSON.stringify(battle.summary(),"",true)
	if state.phase=="rescue_journey":return not battle.finished and state.battle_result.is_empty()
	if state.phase=="battle":return not battle.finished and state.battle_result.is_empty()
	return battle.finished and JSON.stringify(state.battle_result,"",true)==JSON.stringify(battle.summary(),"",true)

func member_stats(member: Dictionary) -> Dictionary:
	return GROWTH.stats(units[member.unit_type],rules.cultivation,member.has("growth_version"))

func growth_config(state: Dictionary,player: Array) -> Array:
	var result=[]
	for spec in player:
		var member=state.roster.get(str(int(spec.instance_id)),{})
		if member.has("growth_version"):result.append({"instance_id":int(spec.instance_id),"level":2})
	result.sort_custom(func(a,b):return a.instance_id<b.instance_id)
	return result

func eligible(state: Dictionary) -> Array:
	var ids=[]
	for member in state.roster.values():
		if member.status=="READY":ids.append(int(member.id))
	ids.sort();return ids

func captured(state: Dictionary) -> Array:
	var ids=[]
	for member in state.roster.values():
		if member.status=="CAPTURED":ids.append(int(member.id))
	ids.sort();return ids

func absorb(state: Dictionary,member: Dictionary,command: Dictionary,event_day: int=-1) -> void:
	if member.status=="ABSORBED":return
	member.status="ABSORBED";state.absorbed_count+=1
	emit(state,command,"unit_absorbed",{"unit_id":member.id,"day":int(state.day) if event_day<0 else event_day})

func expire_before(state: Dictionary,day: int,command: Dictionary) -> void:
	var pending=state.roster.values().filter(func(member):return member.status=="CAPTURED" and int(member.deadline_day)<day)
	pending.sort_custom(func(a,b):return CORE.less([int(a.deadline_day),int(a.id)],[int(b.deadline_day),int(b.id)]))
	for member in pending:absorb(state,member,command,int(member.deadline_day))

func capture(state: Dictionary,member: Dictionary,command: Dictionary) -> void:
	member.status="CAPTURED";member.captured_day=state.day;member.deadline_day=int(state.day)+int(rules.rescue.normal_window_days)
	emit(state,command,"unit_captured",{"unit_id":member.id,"deadline_day":member.deadline_day})

func apply(previous: Dictionary,command: Dictionary) -> Dictionary:
	var state=previous.duplicate(true)
	if not command.get("kind") is String or not command.get("payload",{}) is Dictionary:return bad("命令格式错误")
	var payload=command.get("payload",{})
	if command.kind=="NEW_GAME":
		if not state.is_empty():return bad("已有滚动进度，请继续游戏")
		if not CORE.integer(payload.get("seed",42)) or payload.get("seed",42)<0 or payload.get("seed",42)>4294967295:return bad("周目种子须为0到4294967295的整数")
		state=initial(int(payload.get("seed",42)))
		emit(state,command,"new_game")
		return {"ok":true,"state":state}
	if not valid_state(state):return bad("无有效游戏进度")
	match command.kind:
		"DEPART":
			if state.phase!="town":return bad("当前不能出征")
			var result=depart(state,command,payload)
			if not result.ok:return result
		"ADVANCE_BATTLE":
			if state.phase!="battle":return bad("没有正在进行的战斗")
			var battle=CORE.new()
			if not battle.configure(state.pending.battle_input,units,rules) or not battle.restore(state.battle_snapshot):return bad("战斗恢复失败："+battle.error)
			battle.step();state.battle_snapshot=battle.snapshot()
			if battle.finished:
				state.battle_result=battle.summary();state.phase="settlement"
				emit(state,command,"battle_finished",{"result":battle.result,"expedition":state.expedition})
				if state.pending.get("journey",{}).get("node")=="first" and battle.result=="player_win":TRAIL.first_finished(state)
				if state.pending.route=="boundary" and battle.result=="player_win":state.pending.boundary.stage="approach";state.phase="boundary"
		"BOUNDARY_CHOICE":
			var result=BOUNDARY.choose(self,state,command,payload)
			if not result.ok:return result
		"ENTER_ACT2":
			if state.phase!="town" or not can_enter_act2(state) or state.facts.get("current_act",1)!=1:return bad("需教程、四次有效目标及正式边界返回；第二幕入口仅开启一次")
			state.facts["current_act"]=2;state.facts["act2_started_day"]=state.day
			emit(state,command,"act_entered",{"act":2})
		"RESCUE_CHOICE":
			var result=RESCUE.choice(self,state,command,payload)
			if not result.ok:return result
		"JOURNEY_CHOICE":
			var result=TRAIL.choice(self,state,command,payload)
			if not result.ok:return result
		"CONTINUE_JOURNEY":
			var result=TRAIL.continue_battle(self,state,command,payload)
			if not result.ok:return result
		"SETTLE":
			if state.phase!="settlement":return bad("本次结算已结束或尚无战果")
			var result=settle(state,command,payload)
			if not result.ok:return result
		"ACK_SCENE":
			var scene=STORY.pending(state)
			if scene.is_empty() or scene.id!=payload.get("scene_id"):return bad("当前没有该待播场景")
			var choice=payload.get("choice","continue")
			if choice not in scene.choices.map(func(item):return item.id) or choice=="recruit":return bad("无效对话选择")
			STORY.acknowledge(state,scene,choice);emit(state,command,"scene_acknowledged",{"scene_id":scene.id,"choice":choice})
		"RECRUIT_LORNE":
			if state.phase!="town" or not state.facts.get("tutorial_done",false):return bad("完成教程并回城后才能招募洛恩")
			if state.facts.get("lorne_recruited",false):return bad("洛恩已招募；不会创建第二个实例")
			if int(state.resources.recruit_token)<1:return bad("缺少1件招募信物，可完成短程委托")
			if state.roster.values().filter(func(m):return m.status not in ["ABSORBED","DISMISSED"]).size()>=int(rules.formation.max_roster):return bad("名册已满，未消耗信物")
			var scene=STORY.pending(state)
			if scene.get("id")=="lorne_offer":STORY.acknowledge(state,scene,"recruit")
			state.resources.recruit_token=int(state.resources.recruit_token)-1
			add_member(state,"lorne",false);var member=state.roster[str(int(state.next_unit_id)-1)];member.name="洛恩";member.hero=true
			state.facts["lorne_recruited"]=true
			emit(state,command,"hero_recruited",{"unit_id":member.id,"hero_id":"lorne","token_spent":1,"formation_budget":14})
		"LEVEL_UP":
			if state.phase!="town":return bad("只能在城镇确认升级，已锁定的出征不会改变")
			if not CORE.integer(payload.get("unit_id")):return bad("人物ID必须为整数")
			var member=state.roster.get(str(int(payload.unit_id)),{})
			if not GROWTH.can_level(member,rules.cultivation):return bad("需永久队员在城镇、Lv1且至少1经验；轮休/恢复不会因升级取消")
			var before=member_stats(member)
			member.xp-=int(rules.cultivation.xp_cost);member.level=2;member["growth_version"]=1
			var after=member_stats(member)
			emit(state,command,"unit_leveled",{"unit_id":member.id,"from_level":1,"to_level":2,"xp_spent":int(rules.cultivation.xp_cost),"hp_before":before.hp,"hp_after":after.hp,"attack_before":before.attack,"attack_after":after.attack})
		"RECRUIT":
			if state.phase!="town":return bad("只能在城镇征兵")
			var type=payload.get("unit_type","")
			var cost=int(params.get("recruit_cost",10))
			if type not in ["shield","cavalry","archer"]:return bad("当前只开放三兵种")
			if state.resources.coins<cost:return bad("铜币不足")
			if state.roster.values().filter(func(m):return m.status not in ["ABSORBED","DISMISSED"]).size()>=int(rules.formation.max_roster):return bad("名册已满")
			state.resources.coins-=cost
			add_member(state,type,false)
			emit(state,command,"recruited",{"unit_id":state.next_unit_id-1,"cost":cost})
		"EMERGENCY_PATROL":
			if state.phase!="town" or not eligible(state).is_empty():return bad("仍有可出征人员，无需应急队")
			add_member(state,"shield",true);add_member(state,"cavalry",true)
			emit(state,command,"emergency_patrol_issued")
		"ALTAR":
			if state.phase!="town":return bad("只能在城镇祭坛提取")
			if not CORE.integer(payload.get("unit_id")):return bad("人物ID必须为整数")
			var member=state.roster.get(str(int(payload.unit_id)),{})
			if member.get("status")!="CAPTURED" or not member.get("hero",false) or int(member.deadline_day)<int(state.day):return bad("该人物不能祭坛提取")
			var cost=mini(50,10+2*int(member.level))+10
			if state.resources.crystals<cost:return bad("结晶不足，可查看固定2日救援线")
			state.resources.crystals-=cost;member.status="RECOVERING";member.rest_remaining=2;member.rest_set_on=state.expedition
			emit(state,command,"hero_extracted",{"unit_id":member.id,"cost":cost});homecoming(state,member,"祭坛提取",command)
		"ADVANCE_DAY":
			if state.phase!="town":return bad("行动尚未结束")
			var next_day=int(state.day)+1
			if not acknowledge_expiry(state,next_day,payload):return bad("此行动将越过营救期限，需要明确确认")
			expire_before(state,next_day,command);state.day=next_day
			emit(state,command,"day_advanced")
		_:
			return bad("未知命令")
	return {"ok":true,"state":state}

func add_member(state: Dictionary,type: String,temporary: bool) -> void:
	var id=int(state.next_unit_id);state.next_unit_id=id+1
	state.roster[str(id)]={"id":id,"name":("应急" if temporary else "")+units[type].name+"%02d"%id,"unit_type":type,"hero":false,"level":1,"xp":0,"status":"READY","rest_remaining":0,"rest_set_on":0,"captured_day":null,"deadline_day":null,"temporary":temporary}

func acknowledge_expiry(state: Dictionary,end_day: int,payload: Dictionary) -> bool:
	for member in state.roster.values():
		if member.status=="CAPTURED" and int(member.deadline_day)<end_day and not payload.get("acknowledge_expiry",false):return false
	return true

func depart(state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	for key in ["focus","acknowledge_expiry"]:
		if payload.has(key) and not payload[key] is bool:return bad("确认与集火字段必须为布尔值")
	var route=payload.get("route","commission")
	if route not in ["tutorial","tutorial_trail","commission","outskirts","rescue","rescue_path","outpost","boundary"]:return bad("未知路线")
	if int(state.expedition)==0 and route not in ["tutorial","tutorial_trail"]:return bad("先完成教程委托")
	if route in ["tutorial","tutorial_trail"] and int(state.expedition)>0:return bad("教程已经结束")
	if route=="outpost" and valid_expeditions(state)<int(rules.act1_path.outpost_valid_expeditions):return bad("完成三次有效目标后开放重甲前哨")
	if route=="boundary" and (not can_reach_boundary(state) or state.facts.get("boundary_seen",false)):return bad("需四次有效目标且尚未完成正式边界事件")
	var duration=int(params.route_days[route])
	var end_day=int(state.day)+duration
	if not acknowledge_expiry(state,end_day,payload):return bad("本次预计完成日期将越过被俘期限，请确认后再出发")
	var specs=payload.get("deployment",[])
	var reserves=payload.get("reserve_ids",[])
	if not specs is Array or not reserves is Array:return bad("编队格式错误")
	if route in ["tutorial","tutorial_trail"] and specs.size()!=2:return bad("教程只派2人，保留轮换人员")
	var used={};var player=[];var cost=0
	for spec in specs:
		if not spec is Dictionary or not CORE.integer(spec.get("instance_id")):return bad("部署实例错误")
		var id=int(spec.instance_id);var member=state.roster.get(str(id),{})
		if used.has(id) or member.get("status")!="READY":return bad("只能部署就绪且不重复的人员")
		used[id]=true;cost+=int(units[member.unit_type].cost)
		player.append({"instance_id":id,"side":"player","unit_type":member.unit_type,"x":spec.get("x"),"y":spec.get("y"),"stance":spec.get("stance","attack")})
	if reserves.size()>int(rules.formation.max_reserve) or used.size()+reserves.size()>int(rules.formation.max_roster):return bad("编队超出人数上限")
	for value in reserves:
		if not CORE.integer(value):return bad("预备实例错误")
		var id=int(value);var member=state.roster.get(str(id),{})
		if used.has(id) or member.get("status")!="READY":return bad("非法预备人员")
		used[id]=true;cost+=int(units[member.unit_type].cost)
	var limit=14 if state.facts.get("lorne_recruited",false) else 10
	if cost>limit:return bad("整队cost超过编制")
	var rescue_ids=payload.get("rescue_ids",[])
	if route in ["rescue","rescue_path"]:
		if not rescue_ids is Array or rescue_ids.is_empty():return bad("请选择实际失联目标")
		var seen_rescues={}
		for id in rescue_ids:
			if not CORE.integer(id) or seen_rescues.has(int(id)):return bad("营救目标ID错误或重复")
			seen_rescues[int(id)]=true
			var member=state.roster.get(str(int(id)),{})
			if member.get("status")!="CAPTURED" or int(member.deadline_day)<end_day:return bad("2日救援无法赶上该人物期限")
	var preview=enemy_deployment(state,route)
	var next_rng=preview.seed;var enemy=preview.units
	var battle_input={"seed":next_rng,"budget":limit,"player":player,"enemy":enemy}
	if payload.get("focus",false):
		var target=payload.get("focus_target",enemy[0].instance_id)
		if not CORE.integer(target):return bad("集火目标ID错误")
		battle_input["focus_targets"]={"player":int(target)}
	var skills=[]
	if payload.has("shield_wall_enabled") and not payload.shield_wall_enabled is bool:return bad("盾墙开关必须为布尔值")
	for spec in player:
		if spec.unit_type=="lorne":skills.append({"caster_id":spec.instance_id,"skill_id":"shield_wall","enabled":payload.get("shield_wall_enabled",true),"trigger":payload.get("shield_wall_trigger","low_hp")})
	if not skills.is_empty():battle_input["skill_config"]=skills
	var growth=growth_config(state,player)
	if not growth.is_empty():battle_input["growth_config"]=growth
	var battle=CORE.new()
	if not battle.configure(battle_input,units,rules):return bad(battle.error)
	state.rng_state=next_rng;state.expedition=int(state.expedition)+1
	expire_before(state,end_day,command);state.day=end_day
	state.pending={"action_id":str(command.id),"expedition":state.expedition,"route":route,"duration_days":duration,"deployed_ids":battle.input.player.map(func(spec):return spec.instance_id),"reserve_ids":reserves.duplicate(),"rescue_ids":rescue_ids.duplicate(),"battle_input":battle.input.duplicate(true),"cp_max":10,"cp_spent":5 if payload.get("focus",false) else 0}
	if route=="tutorial_trail":
		if not CORE.integer(payload.get("tutorial_version",1)) or payload.get("tutorial_version",1) not in [1,2]:return bad("未知教程遭遇版本")
		TRAIL.begin(state,rules.tutorial_trail,int(payload.get("tutorial_version",1)))
	for id in used:state.roster[str(id)].status="ACTIVE"
	state.battle_snapshot=battle.snapshot();state.battle_result={};state.phase="battle"
	if route=="boundary":state.pending["boundary"]={"stage":"guards","observed":false,"completed":false}
	if route=="rescue_path":RESCUE.begin(state,self)
	emit(state,command,"expedition_locked",{"expedition":state.expedition,"seed":next_rng})
	return {"ok":true}

func enemy_deployment(state: Dictionary,route: String) -> Dictionary:
	var next_rng=(int(state.rng_state)*1664525+1013904223)&0xffffffff
	if route in ["outpost","boundary"]:return {"seed":next_rng,"units":BOUNDARY.enemies(rules.act1_path,route)}
	if route=="rescue_path":return {"seed":next_rng,"units":RESCUE.enemies(self,0)}
	if route=="tutorial_trail":return {"seed":next_rng,"units":TRAIL.enemies(rules.tutorial_trail.first_enemy,10001)}
	var enemy=[]
	var count=1 if route=="tutorial" else (3 if route=="outskirts" else 2)
	for index in range(count):
		var type=["shield","cavalry","archer"][(index+next_rng)%3]
		enemy.append({"instance_id":10001+int(state.expedition)*100+index,"side":"enemy","unit_type":type,"x":3+index*2,"y":5+index%2,"stance":"attack"})
	return {"seed":next_rng,"units":enemy}

func loot(state: Dictionary) -> Array:
	if state.battle_result.get("result")!="player_win":return []
	if state.pending.get("route")=="boundary" and not state.pending.boundary.completed:return []
	if state.pending.get("journey",{}).get("node") in ["first","return"]:return []
	var temporary=false
	for id in state.pending.deployed_ids:
		if state.roster[str(int(id))].temporary:temporary=true
	return params.patrol_loot.duplicate(true) if temporary else params.route_loot[state.pending.route].duplicate(true)

func campaign_units(state: Dictionary) -> Array:
	var result=state.battle_result.get("units",[]).duplicate(true)
	if state.pending.get("journey",{}).get("node")=="elite":result.append_array(state.pending.journey.down)
	return result

func wounded(state: Dictionary) -> Array:
	var ids=[]
	for unit in campaign_units(state):
		if unit.side=="player" and not unit.alive:ids.append(int(unit.instance_id))
	return ids

func transport(state: Dictionary,bring: Array) -> Dictionary:
	var total=0
	for item in loot(state):total+=int(item.quantity)*int(item.unit_value)
	var percent=0 if settlement_version(state)==2 or bring.is_empty() else mini(100,50+10*(bring.size()-1))
	return {"total":total,"loss_percent":percent,"required_discard":ceili(float(total*percent)/100.0)}

func abandonment_plan(state: Dictionary,bring: Array) -> Dictionary:
	if settlement_version(state)==2:return {"left_ids":[],"follows_ids":[],"deadline_day":int(state.day)+int(rules.rescue.normal_window_days)}
	var left=wounded(state).filter(func(id):return id not in bring)
	var follows=[]
	if not left.is_empty() and state.battle_result.result not in ["enemy_win","draw"]:
		for value in state.pending.deployed_ids+state.pending.reserve_ids:
			var member=state.roster[str(int(value))]
			if member.unit_type!="lorne" or int(value) in left:continue
			var battle_unit=state.battle_result.units.filter(func(u):return int(u.instance_id)==int(value) and u.side=="player")
			if battle_unit.is_empty() or battle_unit[0].alive:follows.append(int(value))
	return {"left_ids":left,"follows_ids":follows,"deadline_day":int(state.day)+int(rules.rescue.normal_window_days)}

func escorted_ids(state: Dictionary) -> Array:
	return state.pending.get("journey",{}).get("escorted_ids",[]) if settlement_version(state)==2 else []

func automatic_return_ids(state: Dictionary) -> Array:
	return escorted_ids(state).duplicate() if state.battle_result.get("result") in ["enemy_win","draw"] else wounded(state)

func settlement_selection(state: Dictionary,payload: Dictionary) -> Dictionary:
	if settlement_version(state)==2:
		if not payload.get("discard",{}) is Dictionary or not payload.get("discard",{}).is_empty():return bad("新返程规则不接受弃置；伤员由实际战果确定，不能主动遗弃")
		return {"ok":true,"bring_ids":automatic_return_ids(state),"discard":{}}
	return {"ok":true,"bring_ids":payload.get("bring_ids",[]),"discard":payload.get("discard",{})}

func failed_member_status(state: Dictionary,unit: Dictionary) -> String:
	if settlement_version(state)==2:
		if int(unit.instance_id) in escorted_ids(state):return "RECOVERING"
		var previous=state.pending.get("journey",{}).get("down",[])
		if previous.any(func(u):return int(u.instance_id)==int(unit.instance_id)):return "CAPTURED"
	return "CAPTURED" if state.roster[str(int(unit.instance_id))].hero else "ABSORBED"

func settle(state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	var wiped=state.battle_result.result in ["enemy_win","draw"]
	var selection=settlement_selection(state,payload)
	if not selection.ok:return selection
	var down=wounded(state);var bring=selection.bring_ids;var discard=selection.discard
	if not bring is Array or not discard is Dictionary:return bad("运输选择格式错误")
	var selected={}
	for value in bring:
		if not CORE.integer(value) or int(value) not in down or selected.has(int(value)) or (wiped and int(value) not in escorted_ids(state)):return bad("非法带回伤兵")
		selected[int(value)]=true
	var abandonment=abandonment_plan(state,bring)
	if not abandonment.follows_ids.is_empty() and not (payload.get("acknowledge_lorne_stays") is bool and payload.acknowledge_lorne_stays):return bad("洛恩会随留下的伤兵失联；请先确认人员去向")
	if state.pending.route in ["tutorial_trail","outpost","boundary"] and not wiped and not abandonment.left_ids.is_empty() and not (payload.get("acknowledge_abandonment") is bool and payload.acknowledge_abandonment):return bad("请确认留下所列伤兵并开始6日营救期限；也可返回调整带回名单")
	var items=loot(state);var values={};var discarded_value=0
	for item in items:values[item.id]=item
	for key in discard:
		if not values.has(key) or not CORE.integer(discard[key]) or int(discard[key])<0 or int(discard[key])>int(values[key].quantity):return bad("弃置物数量无效，不扣仓库")
		discarded_value+=int(discard[key])*int(values[key].unit_value)
	var account=transport(state,bring)
	if discarded_value<int(account.required_discard):return bad("弃置清算值不足：需要%d，当前%d"%[account.required_discard,discarded_value])
	# Existing rest decrements before this expedition's newly returned members enter rest.
	for member in state.roster.values():
		if member.status in ["RESTING","RECOVERING"] and int(member.rest_set_on)<int(state.expedition):
			member.rest_remaining=maxi(0,int(member.rest_remaining)-1)
			if int(member.rest_remaining)==0:member.status="READY"
	for unit in campaign_units(state):
		if unit.side!="player":continue
		var member=state.roster[str(int(unit.instance_id))]
		if wiped:
			match failed_member_status(state,unit):
				"RECOVERING":
					member.status="RECOVERING";member.rest_remaining=2;member.rest_set_on=state.expedition
					if not member.temporary:member.xp=int(member.xp)+int(params.returned_xp)
				"CAPTURED":capture(state,member,command)
				"ABSORBED":absorb(state,member,command)
		elif int(unit.instance_id) in abandonment.follows_ids or (not unit.alive and not selected.has(int(unit.instance_id))):
			capture(state,member,command)
		else:
			member.status="RECOVERING" if not unit.alive else "RESTING"
			member.rest_remaining=2 if not unit.alive else 1;member.rest_set_on=state.expedition
			if not member.temporary and not state.pending.get("rescue_path",{}).get("withdrawn",false):member.xp=int(member.xp)+int(params.returned_xp)
		if member.temporary and member.status in ["RESTING","RECOVERING","CAPTURED"]:member.status="DISMISSED"
	for value in state.pending.reserve_ids:
		var member=state.roster[str(int(value))]
		if int(value) in abandonment.follows_ids:capture(state,member,command)
		else:member.status="RESTING";member.rest_remaining=1;member.rest_set_on=state.expedition
	var rescued=[]
	if state.pending.route in ["rescue","rescue_path"] and state.battle_result.result=="player_win":
		for value in state.pending.rescue_ids:
			var member=state.roster[str(int(value))]
			if member.status=="CAPTURED" and int(member.deadline_day)>=int(state.day):
				member.status="RECOVERING";member.rest_remaining=2;member.rest_set_on=state.expedition
				rescued.append(int(member.id));emit(state,command,"unit_rescued",{"unit_id":member.id})
				if member.hero:homecoming(state,member,"营救",command)
	if state.pending.route in ["rescue","rescue_path"]:
		# Rescue finishes this action day. Success is resolved first, then overdue unsaved targets.
		for m in state.roster.values():
			if m.status=="CAPTURED" and int(m.deadline_day)<=int(state.day):absorb(state,m,command,int(m.deadline_day))
		var reports=state.facts.get("rescue_reports",[])
		reports.append({"expedition":state.expedition,"day":state.day,"result":state.battle_result.result,"withdrawn":state.pending.get("rescue_path",{}).get("withdrawn",false),"rescued_names":rescued.map(func(id):return state.roster[str(id)].name),"targets":state.pending.rescue_ids.map(func(id):return {"id":id,"name":state.roster[str(int(id))].name,"status":state.roster[str(int(id))].status,"deadline":state.roster[str(int(id))].deadline_day})})
		state.facts["rescue_reports"]=reports
	for item in items:
		var quantity=int(item.quantity)-int(discard.get(item.id,0))
		state.resources[item.id]=int(state.resources.get(item.id,0))+quantity
	state.resources.coins=int(state.resources.coins)+return_aid(state)
	emit(state,command,"expedition_settled",{"expedition":state.expedition,"discarded_value":discarded_value,"loot_total":account.total,"wounded_returned":bring.duplicate(),"valid_for_act":objective_completed(state)})
	if int(state.expedition)==1 and not state.facts.has("first_return"):
		state.facts["first_return"]={"result":state.battle_result.result,"zero_loss":down.is_empty() and not wiped,"wounded_ids":down.duplicate(),"returned_ids":bring.duplicate()}
	var absorbed_for_others=0
	var casters=state.pending.battle_input.get("skill_config",[]).filter(func(config):return config.enabled).map(func(config):return int(config.caster_id))
	for event in state.battle_result.events:
		if event.action=="attack" and event.get("target_side")=="player" and event.get("absorbed",0)>0 and int(event.target) not in casters:absorbed_for_others+=int(event.absorbed)
	if absorbed_for_others>0 and not state.facts.has("lorne_protection"):state.facts["lorne_protection"]={"absorbed":absorbed_for_others,"expedition":state.expedition}
	if state.pending.has("journey"):
		var j=state.pending.journey
		var actual=TRAIL.metrics(state.battle_result)
		state.facts["tutorial_trail_return"]={"expedition":state.expedition,"caravan_choice":j.caravan_choice,"camp_choice":j.camp_choice,"node":j.node,"result":state.battle_result.result,"brought":bring.duplicate(),"left":abandonment.left_ids.duplicate(),"discarded_value":discarded_value,"day":state.day,"baseline":j.baseline.duplicate(true),"actual":actual,"wounded_names":down.map(func(id):return state.roster[str(id)].name)}
		if j.node=="elite" and not j.baseline.is_empty():
			var ref=j.baseline.metrics
			state.facts["formation_payoff"]={"improved":actual.alive>ref.alive or (actual.alive==ref.alive and actual.hp>ref.hp),"actual":actual,"reference":ref,"expedition":state.expedition}
	if state.pending.get("route")=="boundary" and state.pending.boundary.completed:
		state.facts["boundary_seen"]=true;state.facts["awk"]=maxi(int(state.facts.get("awk",0)),int(rules.act1_path.boundary_awk_min))
		state.facts["boundary_return"]={"day":state.day,"expedition":state.expedition,"observed":state.pending.boundary.observed,"wounded_ids":down.duplicate(),"returned_ids":bring.duplicate()}
	state.facts["tutorial_done"]=true;state.pending={};state.battle_snapshot={};state.battle_result={};state.phase="town"
	return {"ok":true}

func homecoming(state: Dictionary,member: Dictionary,method: String,command: Dictionary):
	var entries=state.facts.get("homecomings",[]);entries.append({"id":str(command.id)+":"+str(member.id),"name":member.name,"method":method,"day":state.day});state.facts["homecomings"]=entries

func objective_completed(state: Dictionary) -> bool:
	return state.battle_result.get("result")=="player_win" and not state.pending.get("rescue_path",{}).get("withdrawn",false) and state.pending.get("journey",{}).get("node","") not in ["first","return"] and (state.pending.get("route")!="boundary" or state.pending.boundary.completed)

func valid_expeditions(state: Dictionary) -> int:
	return PROGRESS.count(state)
func can_reach_boundary(state: Dictionary) -> bool:
	return state.facts.get("tutorial_done",false) and valid_expeditions(state)>=int(rules.act1.min_valid_expeditions)
func can_enter_act2(state: Dictionary) -> bool:
	return can_reach_boundary(state) and state.facts.get("boundary_seen",false)

func return_aid(state: Dictionary) -> int:
	if state.pending.get("rescue_path",{}).get("withdrawn",false):return 0
	var permanent=false
	for value in state.pending.deployed_ids:
		if not state.roster[str(int(value))].temporary:permanent=true
	return int(params.return_aid_coins) if state.battle_result.result not in ["enemy_win","draw"] or permanent else 0

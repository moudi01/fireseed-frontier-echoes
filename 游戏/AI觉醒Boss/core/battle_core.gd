extends RefCounted
## Deterministic port of 原型/战斗模拟/battle_sim.py. No clock, physics or I/O.

const GROWTH=preload("res://core/cultivation.gd")
const CHARGE=preload("res://core/charged_strike.gd")
const SIDES = ["player", "enemy"]
const DIRECTIONS = [Vector2i(0,-1),Vector2i(1,0),Vector2i(0,1),Vector2i(-1,0)]
const LABELS = {"player_win":"我方胜","enemy_win":"敌方胜","draw":"同归于尽（draw）","retreat_stalemate":"僵持撤离（retreat_stalemate）","retreat_timeout":"超时撤离（retreat_timeout）"}
const INTENT_DETAILS = {"cooldown":"攻击冷却中，等待下一次普攻","defend_no_target":"防御姿态，射程内无目标","no_reachable_target":"无可达目标","no_step":"无可执行的移动步骤"}
const MOVE_DETAILS = {"non_orthogonal":"目标不是正交相邻格","out_of_bounds":"目标格越界","occupied_cell":"目标格被占用","contested_cell":"争格失败（较小 instance_id 优先）"}
const ATTACK_DETAILS = {"target_down":"目标已倒地","out_of_range":"移动后复核时目标不在射程","cooldown":"攻击尚未冷却","marked_cell_empty":"蓄力落空：标记格已无敌人"}
var error = ""
var states: Array = []
var by_id: Dictionary = {}
var templates: Dictionary = {}
var focus: Dictionary = {}
var input: Dictionary = {}
var width = 10
var height = 8
var deployment_rows = 3
var budget = 24
var seed = 0
var tick = 0
var no_damage_ticks = 0
var events: Array = []
var finished = false
var result = null
var result_tick = null
var skill_config: Array=[]
var skill_states: Dictionary={}
var shared_shields: Dictionary={"player":0,"enemy":0}
var shield_rule: Dictionary={}
var charges=CHARGE.new()
var growth_levels: Dictionary={}
var growth_rule: Dictionary={}

func stats(unit: Dictionary) -> Dictionary:
	return GROWTH.stats(templates[unit.unit_type],growth_rule,growth_levels.has(str(int(unit.instance_id))))

static func integer(value) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value)==floor(float(value)) and abs(float(value))<=9007199254740991.0

static func damage(attack: int, armor: int, defending: bool = false) -> int:
	var value = maxi(1,floori(float(attack*50)/float(50+maxi(0,armor))))
	return maxi(1,floori(float(value*4)/5.0)) if defending else value

static func less(a: Array, b: Array) -> bool:
	for index in range(mini(a.size(),b.size())):
		if a[index]!=b[index]: return a[index]<b[index]
	return a.size()<b.size()

func configure(source: Dictionary, unit_data: Dictionary, rule_data: Dictionary) -> bool:
	error=""; states=[]; by_id={}; events=[]; tick=0; no_damage_ticks=0; finished=false; result=null; result_tick=null
	templates=unit_data.duplicate(true);growth_levels={};growth_rule=rule_data.get("cultivation",{})
	skill_config=[];skill_states={};shared_shields={"player":0,"enemy":0};shield_rule=rule_data.get("heroes",{}).get("lorne",{}).get("shield_wall",{})
	var formation=rule_data.get("formation",{})
	width=int(formation.get("columns",10));height=int(formation.get("rows",8));deployment_rows=int(formation.get("deployment_rows",3))
	if not integer(source.get("budget",24)) or not integer(source.get("seed",0)):
		return fail("预算与种子必须为整数")
	budget=int(source.get("budget",24));seed=int(source.get("seed",0))
	if budget<0: return fail("预算不能为负数")
	var counts={"player":0,"enemy":0};var costs={"player":0,"enemy":0};var occupied={}
	for side in SIDES:
		if not source.get(side) is Array: return fail("缺少完整部署数组")
		for spec in source[side]:
			if not spec is Dictionary: return fail("部署项不是对象")
			if spec.get("side")!=side or not templates.has(spec.get("unit_type")): return fail("非法阵营或兵种")
			if spec.get("stance") not in ["attack","defend"]: return fail("非法姿态")
			if not integer(spec.get("instance_id")) or not integer(spec.get("x")) or not integer(spec.get("y")): return fail("实例ID与坐标必须为整数")
			var id=int(spec.instance_id);var x=int(spec.x);var y=int(spec.y)
			if by_id.has(id) or occupied.has(Vector2i(x,y)): return fail("重复实例或占格")
			if x<0 or x>=width or y<0 or y>=height: return fail("坐标越界")
			if (side=="player" and y>=deployment_rows) or (side=="enemy" and y<height-deployment_rows): return fail("不在己方部署区")
			var template=templates[spec.unit_type]
			var unit={"instance_id":id,"side":side,"unit_type":spec.unit_type,"stance":spec.stance,"x":x,"y":y,"hp":int(template.hp),"alive":true,"next_attack_tick":0,"downed_tick":null}
			states.append(unit);by_id[id]=unit;occupied[Vector2i(x,y)]=true
			counts[side]+=1;costs[side]+=int(template.cost)
		if counts[side]<1 or counts[side]>int(formation.get("max_deployed",24)) or costs[side]>budget: return fail("人数或cost不合法")
	states.sort_custom(func(a,b):return a.instance_id<b.instance_id)
	focus={}
	if not source.get("focus_targets",{}) is Dictionary: return fail("集火配置不是对象")
	for side in source.get("focus_targets",{}):
		var id=source.focus_targets[side]
		if side not in SIDES or not integer(id) or not by_id.has(int(id)) or by_id[int(id)].side==side: return fail("非法集火目标")
		focus[side]=int(id)
	input={"seed":seed,"budget":budget,"player":[],"enemy":[]}
	for unit in states:
		input[unit.side].append({"instance_id":unit.instance_id,"side":unit.side,"unit_type":unit.unit_type,"x":unit.x,"y":unit.y,"stance":unit.stance})
	if not focus.is_empty():input["focus_targets"]=focus.duplicate()
	var seen_sides={}
	if not source.get("skill_config",[]) is Array:return fail("技能配置必须为数组")
	for config in source.get("skill_config",[]):
		if not config is Dictionary or not integer(config.get("caster_id")) or not by_id.has(int(config.caster_id)):return fail("技能施放者错误")
		var caster=by_id[int(config.caster_id)]
		if caster.unit_type!="lorne" or config.get("skill_id")!="shield_wall" or not config.get("enabled") is bool or shield_rule.is_empty():return fail("非法技能配置")
		if seen_sides.has(caster.side):return fail("每方仅允许一个洛恩盾墙配置")
		seen_sides[caster.side]=true
		var trigger=config.get("trigger","low_hp")
		if trigger not in ["low_hp","opening"]:return fail("非法盾墙触发预设")
		skill_config.append({"caster_id":caster.instance_id,"skill_id":"shield_wall","enabled":config.enabled,"trigger":trigger})
		skill_states[str(caster.instance_id)]={"windup_until":0,"next_cast_tick":1}
	skill_config.sort_custom(func(a,b):return a.caster_id<b.caster_id)
	if not skill_config.is_empty():input["skill_config"]=skill_config.duplicate(true)
	var growth=GROWTH.configure(source.get("growth_config",[]),states,growth_rule)
	if not growth.ok:return fail(growth.error)
	growth_levels=growth.levels
	if not growth.config.is_empty():
		input["growth_config"]=growth.config
		for unit in states:unit.hp=int(stats(unit).hp)
	if not charges.configure(self,source,rule_data):return false
	if not charges.configs.is_empty():input["charge_config"]=charges.configs.duplicate(true)
	return true

func fail(message: String) -> bool:
	error=message
	return false

func alive_states() -> Array:
	return states.filter(func(unit):return unit.alive)

func cell(unit: Dictionary) -> Vector2i:
	return Vector2i(unit.x,unit.y)

func distance(a: Vector2i,b: Vector2i) -> int:
	return absi(a.x-b.x)+absi(a.y-b.y)

func array_cell(value: Vector2i) -> Array:
	return [value.x,value.y]

func attack_cells(position: Vector2i, reach: int) -> Array:
	var cells=[]
	for dx in range(-reach,reach+1):
		for dy in range(-reach,reach+1):
			var next=position+Vector2i(dx,dy)
			if absi(dx)+absi(dy)<=reach and next.x>=0 and next.x<width and next.y>=0 and next.y<height:cells.append(next)
	return cells

func bfs(start: Vector2i,occupied: Dictionary) -> Dictionary:
	var distances={start:0};var parents={start:null};var queue=[start];var head=0
	while head<queue.size():
		var current=queue[head];head+=1
		for direction in DIRECTIONS:
			var next=current+direction
			if next.x<0 or next.x>=width or next.y<0 or next.y>=height or occupied.has(next) or distances.has(next):continue
			distances[next]=distances[current]+1;parents[next]=current;queue.append(next)
	return {"distance":distances,"parent":parents}

func is_focus(side: String,id: int) -> bool:
	return focus.get(side,null)==id

func choose(unit: Dictionary,occupied: Dictionary,enemies: Array) -> Dictionary:
	var reach=int(templates[unit.unit_type].range)
	var in_range=enemies.filter(func(enemy):return distance(cell(unit),cell(enemy))<=reach)
	if not in_range.is_empty():
		in_range.sort_custom(func(a,b):return less([0 if is_focus(unit.side,a.instance_id) else 1,a.instance_id],[0 if is_focus(unit.side,b.instance_id) else 1,b.instance_id]))
		var target=in_range[0].instance_id
		return {"kind":"attack","target":target} if tick>=unit.next_attack_tick else {"kind":"wait","target":target,"reason":"cooldown"}
	if unit.stance!="attack":return {"kind":"idle","reason":"defend_no_target"}
	var paths=bfs(cell(unit),occupied);var best_key=null;var best_cell=null;var best_target=null
	for enemy in enemies:
		var candidate=null
		for point in attack_cells(cell(enemy),reach):
			if point!=cell(unit) and occupied.has(point):continue
			if not paths.distance.has(point):continue
			var key=[paths.distance[point],point.x,point.y]
			if candidate==null or less(key,candidate):candidate=key
		if candidate==null:continue
		var key=[candidate[0],0 if is_focus(unit.side,enemy.instance_id) else 1,enemy.instance_id]
		if best_key==null or less(key,best_key):
			best_key=key;best_cell=Vector2i(candidate[1],candidate[2]);best_target=enemy.instance_id
	if best_cell==null:return {"kind":"idle","reason":"no_reachable_target"}
	var path=[best_cell]
	while path[-1]!=cell(unit):
		var previous=paths.parent[path[-1]]
		if previous==null:return {"kind":"idle","reason":"no_step"}
		path.append(previous)
	path.reverse()
	if path.size()<2:return {"kind":"idle","reason":"no_step"}
	return {"kind":"move","target":best_target,"next":path[1],"goal":best_cell}

func engagement() -> bool:
	var alive=alive_states();var occupied={}
	for unit in alive:occupied[cell(unit)]=true
	for unit in alive:
		var enemies=alive.filter(func(enemy):return enemy.side!=unit.side)
		var reach=int(templates[unit.unit_type].range)
		for enemy in enemies:
			if distance(cell(unit),cell(enemy))<=reach:return true
		if unit.stance!="attack":continue
		var paths=bfs(cell(unit),occupied)
		for enemy in enemies:
			for point in attack_cells(cell(enemy),reach):
				if (point==cell(unit) or not occupied.has(point)) and paths.distance.has(point):return true
	return false

func event(phase: String,action: String,fields: Dictionary) -> Dictionary:
	var record={"tick":tick,"phase":phase,"action":action}
	record.merge(fields)
	return record

func step() -> Dictionary:
	if finished:return {"error":"战斗已经结束"}
	tick+=1
	var emitted=[];var alive=alive_states();var occupied={};var intents={}
	var casting=skill_step(emitted)
	var charge_plan=charges.plan(self,emitted);casting.merge(charge_plan.blocked)
	for unit in alive:occupied[cell(unit)]=true
	for unit in alive:
		intents[unit.instance_id]={"kind":"charged","cell":charge_plan.releases[unit.instance_id]} if charge_plan.releases.has(unit.instance_id) else ({"kind":"skill"} if casting.has(unit.instance_id) else choose(unit,occupied,alive.filter(func(enemy):return enemy.side!=unit.side)))
	for unit in alive:
		var intent=intents[unit.instance_id]
		if intent.kind not in ["wait","idle"]:continue
		var fields={"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"actor_pos":array_cell(cell(unit)),"reason":intent.reason,"detail":INTENT_DETAILS[intent.reason]}
		if intent.has("target"):
			fields["target"]=intent.target
			if is_focus(unit.side,intent.target):fields["target_preference"]="focus"
		emitted.append(event("intent",intent.kind,fields))
	var reserved=occupied.duplicate();var claimed={}
	for unit in alive:
		var intent=intents[unit.instance_id]
		if intent.kind!="move":continue
		var origin=cell(unit);var target=intent.next;var reason=""
		if distance(origin,target)!=1:reason="non_orthogonal"
		elif target.x<0 or target.x>=width or target.y<0 or target.y>=height:reason="out_of_bounds"
		elif claimed.has(target):reason="contested_cell"
		elif reserved.has(target):reason="occupied_cell"
		var fields={"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"from":array_cell(origin),"to":array_cell(target)}
		if reason.is_empty():
			claimed[target]=unit.instance_id;reserved[target]=true;unit.x=target.x;unit.y=target.y
			fields["stance"]=unit.stance
			if is_focus(unit.side,intent.target):fields["target"]=intent.target;fields["target_preference"]="focus"
			emitted.append(event("move","move",fields))
		else:
			fields["reason"]=reason;fields["detail"]=MOVE_DETAILS[reason];emitted.append(event("move","cancelled",fields))
	var hp_before={};var attacks=[];var totals={}
	for unit in alive:hp_before[unit.instance_id]=unit.hp
	for unit in alive:
		var intent=intents[unit.instance_id]
		if intent.kind not in ["attack","charged"]:continue
		var charged=intent.kind=="charged";var target=null;var reason=""
		if charged:
			var marked=Vector2i(int(intent.cell[0]),int(intent.cell[1]))
			var occupants=alive.filter(func(u):return u.side!=unit.side and cell(u)==marked)
			unit.next_attack_tick=tick+int(templates[unit.unit_type].attack_interval_ticks)
			if occupants.is_empty():attacks.append([unit,null,"marked_cell_empty",{"attack_type":"charged_strike","target_cell":intent.cell.duplicate()}]);continue
			target=occupants[0]
		else:
			target=by_id[intent.target]
			if not target.alive:reason="target_down"
			elif distance(cell(unit),cell(target))>int(templates[unit.unit_type].range):reason="out_of_range"
			elif tick<unit.next_attack_tick:reason="cooldown"
		if not reason.is_empty():attacks.append([unit,target,reason]);continue
		var hit=damage(int(stats(unit).attack)*(int(charges.rule.attack_multiplier) if charged else 1),int(templates[target.unit_type].armor),target.stance=="defend")
		unit.next_attack_tick=tick+int(templates[unit.unit_type].attack_interval_ticks)
		var raw=hit;var absorbed=0;var winding=false
		if skill_states.has(str(target.instance_id)) and skill_states[str(target.instance_id)].windup_until>tick:
			winding=true;hit*=int(shield_rule.windup_incoming_multiplier);raw=hit
		if int(shared_shields[target.side])>0:
			absorbed=mini(hit,int(shared_shields[target.side]));shared_shields[target.side]=int(shared_shields[target.side])-absorbed;hit-=absorbed
		totals[target.instance_id]=totals.get(target.instance_id,0)+hit
		var extra={"raw_damage":raw,"absorbed":absorbed,"shared_shield_remaining":int(shared_shields[target.side]),"windup_vulnerable":winding} if absorbed>0 or winding else {}
		if charged:extra.merge({"attack_type":"charged_strike","target_cell":intent.cell.duplicate()})
		attacks.append([unit,target,hit,extra])
	for id in totals:by_id[id].hp=maxi(0,by_id[id].hp-totals[id])
	for record in attacks:
		var unit=record[0];var target=record[1];var value=record[2]
		if target==null:
			var miss={"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"actor_pos":array_cell(cell(unit)),"reason":value,"detail":ATTACK_DETAILS[value]};miss.merge(record[3]);emitted.append(event("attack","cancelled",miss));continue
		var fields={"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"actor_pos":array_cell(cell(unit)),"target":target.instance_id,"target_side":target.side,"target_unit":templates[target.unit_type].name,"target_pos":array_cell(cell(target))}
		if value is int:
			if record.size()>3:fields.merge(record[3])
			fields.merge({"damage":value,"target_hp_before":hp_before[target.instance_id],"target_hp_after":target.hp,"target_defending":target.stance=="defend"})
			if is_focus(unit.side,target.instance_id):fields["target_preference"]="focus"
			emitted.append(event("attack","attack",fields))
		else:
			fields.merge({"reason":value,"detail":ATTACK_DETAILS[value]});emitted.append(event("attack","cancelled",fields))
	for unit in alive:
		if unit.hp==0 and unit.alive:
			unit.alive=false;unit.downed_tick=tick;charges.clear_pending(unit.instance_id)
			if skill_states.has(str(unit.instance_id)):skill_states[str(unit.instance_id)].windup_until=0
			emitted.append(event("down","downed",{"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"position":array_cell(cell(unit)),"detail":"HP归零，倒地"}))
	var total=0
	for value in totals.values():total+=value
	no_damage_ticks=0 if total>0 else no_damage_ticks+1
	var players=states.filter(func(unit):return unit.alive and unit.side=="player").size()
	var enemies=states.filter(func(unit):return unit.alive and unit.side=="enemy").size()
	if players==0 and enemies==0:result="draw"
	elif players==0:result="enemy_win"
	elif enemies==0:result="player_win"
	elif no_damage_ticks>=8 and not engagement():result="retreat_stalemate"
	elif tick>=120:result="retreat_timeout"
	if result!=null:
		finished=true;result_tick=tick
		for id in charges.states:charges.clear_pending(id)
	events.append_array(emitted)
	return {"tick":tick,"events":emitted,"finished":finished,"result":result}

func skill_step(emitted: Array) -> Dictionary:
	var blocked={}
	for config in skill_config:
		var unit=by_id[int(config.caster_id)];var status=skill_states[str(config.caster_id)]
		if not unit.alive or not config.enabled:continue
		var fields={"actor":unit.instance_id,"side":unit.side,"unit":templates[unit.unit_type].name,"actor_pos":array_cell(cell(unit)),"skill_id":"shield_wall"}
		if int(status.windup_until)>0:
			blocked[unit.instance_id]=true
			if tick>=int(status.windup_until):
				status.windup_until=0;shared_shields[unit.side]=int(shield_rule.shared_pool)
				fields["shared_pool"]=int(shield_rule.shared_pool);emitted.append(event("skill","shield_formed",fields))
			continue
		if tick<int(status.next_cast_tick) or int(shared_shields[unit.side])>0:continue
		var endangered=alive_states().filter(func(ally):return ally.side==unit.side and int(ally.hp)*100<int(stats(ally).hp)*int(shield_rule.trigger_hp_percent))
		if (config.trigger=="opening" and tick!=1) or (config.trigger=="low_hp" and endangered.is_empty()):continue
		status.windup_until=tick+int(shield_rule.windup_ticks);status.next_cast_tick=tick+int(shield_rule.cooldown_ticks)
		blocked[unit.instance_id]=true;fields["trigger_target"]=endangered[0].instance_id if not endangered.is_empty() else unit.instance_id;fields["trigger_preset"]=config.trigger;fields["ready_tick"]=status.windup_until
		emitted.append(event("skill","shield_windup",fields))
	return blocked

func run() -> Dictionary:
	for guard in range(121):
		if finished:break
		step()
	return summary()

func summary() -> Dictionary:
	var units=[]
	for unit in states:
		units.append({"instance_id":unit.instance_id,"side":unit.side,"unit_type":unit.unit_type,"name":templates[unit.unit_type].name,"hp":unit.hp,"max_hp":int(stats(unit).hp),"alive":unit.alive,"downed_tick":unit.downed_tick,"position":array_cell(cell(unit)),"stance":unit.stance,"next_attack_tick":unit.next_attack_tick})
	var output={"seed":seed,"tick_seconds":0.5,"tick_count":tick,"result":result,"result_label":LABELS.get(result,result),"finished":finished,"board":{"columns":width,"rows":height,"deployment_rows":deployment_rows},"budget":budget,"units":units,"events":events.duplicate(true)}
	if not growth_levels.is_empty():output["growth_config"]=input.growth_config.duplicate(true)
	if not focus.is_empty():output["focus_targets"]=focus.duplicate()
	if not skill_config.is_empty():output.merge({"skill_config":skill_config.duplicate(true),"skill_states":skill_states.duplicate(true),"shared_shields":shared_shields.duplicate(true)})
	if not charges.configs.is_empty():output.merge({"charge_config":charges.configs.duplicate(true),"charge_states":charges.states.duplicate(true)})
	return output

func snapshot() -> Dictionary:
	var data={"tick":tick,"states":states.duplicate(true),"events":events.duplicate(true),"no_damage_ticks":no_damage_ticks,"finished":finished,"result":result,"result_tick":result_tick}
	if not skill_config.is_empty():data.merge({"skill_states":skill_states.duplicate(true),"shared_shields":shared_shields.duplicate(true)})
	if not charges.configs.is_empty():data["charge_states"]=charges.states.duplicate(true)
	return data

static func normalize_numbers(value):
	if value is float and integer(value):return int(value)
	if value is Array:return value.map(func(item):return normalize_numbers(item))
	if value is Dictionary:
		var result={}
		for key in value:result[key]=normalize_numbers(value[key])
		return result
	return value

func restore(data: Dictionary) -> bool:
	for key in ["tick","states","events","no_damage_ticks","finished","result","result_tick"]:
		if not data.has(key):return fail("战斗快照缺少字段")
	if not integer(data.get("tick")) or not data.get("states") is Array or data.states.size()!=states.size():return fail("无效战斗快照")
	if int(data.tick)<0 or int(data.tick)>120 or not data.get("events") is Array or not data.get("finished") is bool or not integer(data.get("no_damage_ticks")):return fail("战斗快照计时错误")
	if data.no_damage_ticks<0 or data.no_damage_ticks>data.tick:return fail("无伤计时越界")
	var previous_tick=0;var previous_phase=-1
	for record in data.events:
		if not record is Dictionary or not integer(record.get("tick")) or record.tick<1 or record.tick>data.tick or not integer(record.get("actor")) or not by_id.has(int(record.actor)):return fail("战斗事件格式错误")
		var phase=["skill","intent","move","attack","down"].find(record.get("phase"))
		if phase<0 or record.get("action") not in {"skill":["shield_windup","shield_formed","charge_windup"],"intent":["wait","idle"],"move":["move","cancelled"],"attack":["attack","cancelled"],"down":["downed"]}[record.phase]:return fail("战斗事件阶段错误")
		if record.tick<previous_tick or (record.tick==previous_tick and phase<previous_phase):return fail("战斗事件顺序错误")
		previous_phase=phase;previous_tick=int(record.tick)
		if record.action=="charge_windup":
			if not charges.states.has(str(int(record.actor))) or not integer(record.get("ready_tick")) or int(record.ready_tick)!=int(record.tick)+int(charges.rule.windup_ticks):return fail("精英预警事件时点错误")
			var marked=record.get("target_cell")
			if not marked is Array or marked.size()!=2 or not integer(marked[0]) or not integer(marked[1]) or marked[0]<0 or marked[0]>=width or marked[1]<0 or marked[1]>=height:return fail("精英预警事件标记错误")
		if record.get("side")!=by_id[int(record.actor)].side:return fail("战斗事件阵营错误")
		if record.has("target") and (not integer(record.target) or not by_id.has(int(record.target))):return fail("战斗事件目标错误")
	var occupied={};var seen={};var replacements=[]
	for saved in data.states:
		if not saved is Dictionary or not integer(saved.get("instance_id")) or not by_id.has(int(saved.instance_id)) or seen.has(int(saved.instance_id)):return fail("战斗快照实例错误")
		for key in ["side","unit_type","stance","hp","alive","x","y","next_attack_tick","downed_tick"]:
			if not saved.has(key):return fail("单位快照缺少字段")
		var unit=by_id[int(saved.instance_id)]
		for key in ["side","unit_type","stance"]:
			if saved.get(key)!=unit[key]:return fail("战斗快照固定输入变化")
		for key in ["hp","x","y","next_attack_tick"]:
			if not integer(saved.get(key)):return fail("战斗快照数值错误")
		if saved.hp<0 or saved.hp>stats(unit).hp or saved.x<0 or saved.x>=width or saved.y<0 or saved.y>=height or saved.next_attack_tick<0:return fail("战斗快照数值越界")
		if not saved.get("alive") is bool or saved.alive!=(saved.hp>0):return fail("战斗快照生死状态错误")
		if (saved.alive and saved.get("downed_tick")!=null) or (not saved.alive and (not integer(saved.get("downed_tick")) or saved.downed_tick<1 or saved.downed_tick>data.tick)):return fail("倒地时点错误")
		var normalized=saved.duplicate(true)
		for key in ["instance_id","hp","x","y","next_attack_tick"]:normalized[key]=int(normalized[key])
		if normalized.downed_tick!=null:normalized.downed_tick=int(normalized.downed_tick)
		seen[normalized.instance_id]=true
		if normalized.alive:
			if occupied.has(cell(normalized)):return fail("存活单位重叠")
			occupied[cell(normalized)]=true
		replacements.append(normalized)
	if data.result!=null and data.result not in LABELS:return fail("战斗结果错误")
	if data.finished!=(data.result!=null) or (data.finished and data.result_tick!=data.tick):return fail("战斗完成标记错误")
	if not data.finished and data.result_tick!=null:return fail("未完成战斗不能有结束时点")
	var players=replacements.filter(func(u):return u.side=="player" and u.alive).size()
	var enemies=replacements.filter(func(u):return u.side=="enemy" and u.alive).size()
	if (data.result=="player_win" and (players==0 or enemies>0)) or (data.result=="enemy_win" and (enemies==0 or players>0)) or (data.result=="draw" and (players>0 or enemies>0)):return fail("战果与人员不符")
	if (not data.finished or data.result in ["retreat_timeout","retreat_stalemate"]) and (players==0 or enemies==0):return fail("撤离与人员不符")
	if not skill_config.is_empty():
		if not data.get("skill_states") is Dictionary or not data.get("shared_shields") is Dictionary or data.skill_states.size()!=skill_states.size():return fail("缺少技能快照")
		for side in SIDES:
			if not integer(data.shared_shields.get(side)) or data.shared_shields[side]<0 or data.shared_shields[side]>int(shield_rule.shared_pool):return fail("共享盾快照错误")
		for id in skill_states:
			var saved=data.skill_states.get(id,{})
			if not saved is Dictionary or not integer(saved.get("windup_until")) or not integer(saved.get("next_cast_tick")):return fail("技能时序错误")
			if saved.windup_until<0 or saved.windup_until>int(data.tick)+int(shield_rule.windup_ticks) or (saved.windup_until>0 and saved.windup_until<=data.tick) or saved.next_cast_tick<1 or saved.next_cast_tick>int(data.tick)+int(shield_rule.cooldown_ticks):return fail("技能时序越界")
		for id in skill_states:skill_states[id]={"windup_until":int(data.skill_states[id].windup_until),"next_cast_tick":int(data.skill_states[id].next_cast_tick)}
		for side in SIDES:shared_shields[side]=int(data.shared_shields[side])
	elif data.has("skill_states") or data.has("shared_shields"):return fail("未配置技能却出现技能状态")
	if not charges.configs.is_empty():
		if not charges.restore(self,data.get("charge_states"),replacements,int(data.tick),data.finished):return false
	elif data.has("charge_states"):return fail("未配置重击却出现精英状态")
	for unit in replacements:by_id[unit.instance_id].merge(unit,true)
	tick=int(data.tick);events=normalize_numbers(data.events);no_damage_ticks=int(data.no_damage_ticks);finished=data.finished;result=data.result;result_tick=int(data.result_tick) if data.result_tick!=null else null
	return true

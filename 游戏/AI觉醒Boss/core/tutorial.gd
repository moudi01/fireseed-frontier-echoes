extends RefCounted
## Tutorial route only. No presentation, I/O, or post-battle scripted damage.
const CORE=preload("res://core/battle_core.gd")

static func enemies(types: Array,start_id: int) -> Array:
	var output=[]
	for i in range(types.size()):output.append({"instance_id":start_id+i,"side":"enemy","unit_type":types[i],"x":4+i,"y":5,"stance":"attack"})
	return output

static func begin(state: Dictionary,rule: Dictionary,version: int=1):
	state.pending["journey"]={"encounter_version":version,"node":"first","food":int(rule.food_start),"caravan_choice":"","camp_choice":"","first_result":{},"first_input":{},"first_snapshot":{},"hp":{},"down":[],"baseline":{}}

static func first_finished(state: Dictionary):
	var j=state.pending.journey
	j.first_result=state.battle_result.duplicate(true);j.first_input=state.pending.battle_input.duplicate(true);j.first_snapshot=state.battle_snapshot.duplicate(true)
	for unit in state.battle_result.units:
		if unit.side!="player":continue
		if unit.alive:j.hp[str(int(unit.instance_id))]=int(unit.hp)
		else:j.down.append(unit.duplicate(true))
	j.node="caravan";state.phase="journey"

static func validate(state: Dictionary,units: Dictionary,rules: Dictionary) -> bool:
	if state.pending.get("route")!="tutorial_trail":return state.phase!="journey"
	var j=state.pending.get("journey",{})
	if not j is Dictionary or not CORE.integer(j.get("encounter_version",1)) or j.get("encounter_version",1) not in [1,2]:return false
	if j.get("node") not in ["first","caravan","camp","formation","elite","return"]:return false
	if not CORE.integer(j.get("food")) or j.food<0 or j.food>int(rules.tutorial_trail.food_start)+int(rules.tutorial_trail.collect_food):return false
	if j.get("caravan_choice") not in ["","collect","mark","pass"] or j.get("camp_choice") not in ["","rest","skip"]:return false
	for key in ["first_result","first_input","first_snapshot","hp","baseline"]:
		if not j.get(key) is Dictionary:return false
	if not j.get("down") is Array:return false
	if j.node=="first":return state.phase in ["battle","settlement"] and j.first_result.is_empty()
	var first=CORE.new()
	if not first.configure(j.first_input,units,rules) or not first.restore(j.first_snapshot) or not first.finished or first.result!="player_win":return false
	if JSON.stringify(first.summary(),"",true)!=JSON.stringify(j.first_result,"",true):return false
	if state.phase=="journey" and j.node not in ["caravan","camp","formation"]:return false
	if state.phase=="battle" and j.node!="elite":return false
	if state.phase=="settlement" and j.node not in ["elite","return"]:return false
	var expected_down=j.first_result.units.filter(func(u):return u.side=="player" and not u.alive)
	if JSON.stringify(j.down,"",true)!=JSON.stringify(expected_down,"",true):return false
	if state.get("settlement_rules_version",1)==2:
		var escorted=j.get("escorted_ids",[])
		var expected=expected_down.map(func(u):return int(u.instance_id)) if j.node=="elite" and not state.pending.reserve_ids.is_empty() else []
		if not escorted is Array or escorted!=expected:return false
	var alive=j.first_result.units.filter(func(u):return u.side=="player" and u.alive)
	if j.hp.size()!=alive.size():return false
	for unit in alive:
		var hp=j.hp.get(str(int(unit.instance_id)))
		if not CORE.integer(hp) or hp<int(unit.hp) or hp>int(first.stats(unit).hp):return false
	return true

static func metrics(result: Dictionary) -> Dictionary:
	var alive=0;var hp=0
	for unit in result.units:
		if unit.side=="player":alive+=1 if unit.alive else 0;hp+=int(unit.hp)
	return {"result":result.result,"alive":alive,"hp":hp,"ticks":int(result.tick_count)}

static func configure_elite(engine,state: Dictionary,deployment: Array,focus: bool,target) -> Dictionary:
	var j=state.pending.journey;var original=j.first_input.player
	if deployment.size()!=j.hp.size():return engine.bad("只为仍能行动的同行队员重新布阵，不能换人或加入预备")
	var ids={};var player=[]
	for spec in deployment:
		if not spec is Dictionary or not CORE.integer(spec.get("instance_id")):return engine.bad("部署实例错误")
		var id=str(int(spec.instance_id))
		if not j.hp.has(id) or ids.has(id):return engine.bad("不可加入新队员、倒地者或重复实例")
		ids[id]=true
		var member=state.roster[id]
		player.append({"instance_id":int(id),"side":"player","unit_type":member.unit_type,"x":spec.get("x"),"y":spec.get("y"),"stance":spec.get("stance","attack")})
	var enemy=enemies(engine.rules.tutorial_trail.elite_enemy,10003)
	var input={"seed":state.pending.battle_input.seed,"budget":10,"player":player,"enemy":enemy}
	var growth=j.first_input.get("growth_config",[]).filter(func(g):return ids.has(str(int(g.instance_id))))
	if not growth.is_empty():input["growth_config"]=growth.duplicate(true)
	if int(j.get("encounter_version",1))>=2:input["charge_config"]=[{"caster_id":10003,"skill_id":"telegraphed_strike"}]
	if focus:
		if int(state.pending.cp_spent)+5>10:return engine.bad("本趟指挥点不足")
		input["focus_targets"]={"player":target}
	var battle=CORE.new()
	if not battle.configure(input,engine.units,engine.rules):return engine.bad(battle.error)
	for unit in battle.states:
		if unit.side=="player":unit.hp=int(j.hp[str(int(unit.instance_id))])
	return {"ok":true,"battle":battle}

static func choice(engine,state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	if state.phase!="journey":return engine.bad("当前不在途中节点")
	var j=state.pending.journey;var selected=payload.get("choice","")
	if payload.get("node")!=j.node:return engine.bad("该途中节点已经处理或尚未到达")
	if selected=="return":
		j.node="return";state.phase="settlement";engine.emit(state,command,"journey_returned_early");return {"ok":true}
	if j.node=="caravan":
		if selected not in ["collect","mark","pass"]:return engine.bad("未知商队选项")
		if selected=="mark":
			var day=int(state.day)+int(engine.rules.tutorial_trail.mark_days)
			if not engine.acknowledge_expiry(state,day,payload):return engine.bad("留下路标会越过期限，需要确认")
			engine.expire_before(state,day,command);state.day=day
		if selected=="collect":j.food+=int(engine.rules.tutorial_trail.collect_food)
		j.caravan_choice=selected;j.node="camp"
	elif j.node=="camp":
		if selected not in ["rest","skip"]:return engine.bad("未知休整选项")
		if selected=="rest":
			var cost=int(engine.rules.tutorial_trail.rest_food)
			if j.food<cost:return engine.bad("本趟食物不足，可跳过休整或返回")
			j.food-=cost
			for id in j.hp:j.hp[id]=mini(int(engine.member_stats(state.roster[id]).hp),int(j.hp[id])+int(engine.rules.tutorial_trail.rest_heal))
		j.camp_choice=selected;j.node="formation"
	else:return engine.bad("请先确认精英战布阵")
	engine.emit(state,command,"journey_choice",{"node":payload.node,"choice":selected,"food_remaining":j.food})
	return {"ok":true}

static func continue_battle(engine,state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	if state.phase!="journey" or state.pending.journey.node!="formation":return engine.bad("当前不能进入精英战")
	if not payload.get("deployment") is Array or not payload.get("focus",false) is bool:return engine.bad("精英布阵格式错误")
	var result=configure_elite(engine,state,payload.deployment,payload.get("focus",false),payload.get("focus_target",10004))
	if not result.ok:return result
	var j=state.pending.journey
	# Reference uses first formation, same current HP/enemy/seed and same second-battle CP choice.
	var baseline=j.first_input.player.filter(func(s):return j.hp.has(str(int(s.instance_id))))
	var reference=configure_elite(engine,state,baseline,payload.get("focus",false),payload.get("focus_target",10004))
	if not reference.ok:return reference
	j.baseline={"input":reference.battle.input.duplicate(true),"hp":j.hp.duplicate(),"metrics":metrics(reference.battle.run())}
	j.node="elite";state.pending.cp_spent+=5 if payload.get("focus",false) else 0
	if engine.settlement_version(state)==2:
		j["escorted_ids"]=j.down.map(func(u):return int(u.instance_id)) if not state.pending.reserve_ids.is_empty() else []
		if not j.escorted_ids.is_empty():engine.emit(state,command,"wounded_escorted",{"unit_ids":j.escorted_ids.duplicate(),"reserve_ids":state.pending.reserve_ids.duplicate()})
	state.pending.battle_input=result.battle.input.duplicate(true);state.battle_snapshot=result.battle.snapshot();state.battle_result={};state.phase="battle"
	engine.emit(state,command,"journey_elite_locked",{"input":state.pending.battle_input.duplicate(true)})
	return {"ok":true}

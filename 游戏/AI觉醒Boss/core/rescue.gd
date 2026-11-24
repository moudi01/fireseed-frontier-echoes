extends RefCounted
const CORE=preload("res://core/battle_core.gd")
static func enemies(engine,attention: int) -> Array:
	var types=engine.rules.rescue_path.base_enemies.duplicate()
	if attention>=int(engine.rules.rescue_path.extra_guard_at):types.append(engine.rules.rescue_path.extra_guard)
	var result=[]
	for i in range(types.size()):result.append({"instance_id":20001+i,"side":"enemy","unit_type":types[i],"x":3+i*2,"y":5+i%2,"stance":"attack"})
	return result
static func begin(state: Dictionary,engine):
	var targets=[]
	for id in state.pending.rescue_ids:
		var m=state.roster[str(int(id))];targets.append({"id":m.id,"name":m.name,"deadline_day":m.deadline_day,"captured_day":m.captured_day})
	state.pending["rescue_path"]={"node":"approach","attention":int(engine.rules.rescue_path.attention_start),"targets":targets,"choices":[],"withdrawn":false}
	state.phase="rescue_journey"
static func validate(state: Dictionary,engine) -> bool:
	if state.pending.get("route")!="rescue_path":return state.phase!="rescue_journey"
	var r=state.pending.get("rescue_path",{})
	if not r is Dictionary or r.get("node") not in ["approach","camp","gate","battle","withdrawn"]:return false
	if not CORE.integer(r.get("attention")) or r.attention<0 or r.attention>int(engine.rules.rescue_path.attention_cap):return false
	if not r.get("withdrawn") is bool or not r.get("targets") is Array or r.targets.is_empty() or not r.get("choices") is Array:return false
	for target in r.targets:
		if not target is Dictionary or not CORE.integer(target.get("id")) or not state.roster.has(str(int(target.id))) or not target.get("name") is String or not CORE.integer(target.get("deadline_day")):return false
	if r.targets.map(func(t):return int(t.id))!=state.pending.rescue_ids.map(func(id):return int(id)):return false
	if state.phase=="rescue_journey":return r.node in ["approach","camp","gate"] and not r.withdrawn and state.battle_snapshot.tick==0
	if state.phase=="battle":return r.node=="battle" and not r.withdrawn
	return state.phase=="settlement" and r.node in ["battle","withdrawn"] and r.withdrawn==(r.node=="withdrawn")
static func overdue_names(state: Dictionary,day: int) -> Array:
	return state.roster.values().filter(func(m):return m.status=="CAPTURED" and int(m.deadline_day)<day).map(func(m):return m.name)
static func choice(engine,state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	if state.phase!="rescue_journey":return engine.bad("当前不在救援途中")
	var r=state.pending.rescue_path;var selected=payload.get("choice","")
	if payload.get("node")!=r.node:return engine.bad("救援节点已变化，未重复执行")
	if payload.has("acknowledge_expiry") and not payload.acknowledge_expiry is bool:return engine.bad("越期确认必须为布尔值")
	if selected=="withdraw":
		var b=CORE.new();b.configure(state.pending.battle_input,engine.units,engine.rules);b.finished=true;b.result="retreat_stalemate";b.result_tick=0
		state.battle_snapshot=b.snapshot();state.battle_result=b.summary();state.phase="settlement";r.node="withdrawn";r.withdrawn=true
		engine.emit(state,command,"rescue_withdrawn");return {"ok":true}
	var extra=0;var attention=int(r.attention)
	if r.node=="approach":
		if selected not in ["direct","detour"]:return engine.bad("未知入口选择")
		if selected=="direct":attention+=int(engine.rules.rescue_path.fast_attention)
		else:extra=int(engine.rules.rescue_path.detour_days);attention=maxi(0,attention-1)
	elif r.node=="camp":
		if selected not in ["breach","wait"]:return engine.bad("未知营地选择")
		if selected=="breach":attention+=int(engine.rules.rescue_path.breach_attention)
		else:extra=int(engine.rules.rescue_path.wait_days);attention=maxi(0,attention-1)
	elif r.node=="gate":
		if selected!="fight":return engine.bad("请进入守卫战或撤离")
		if not state.pending.rescue_ids.any(func(id):return state.roster[str(int(id))].status=="CAPTURED" and int(state.roster[str(int(id))].deadline_day)>=int(state.day)):return engine.bad("原目标已不在期限内，请撤离并查看名册")
		var input=state.pending.battle_input.duplicate(true);input.enemy=enemies(engine,int(r.attention))
		# Keep a previously selected target only if it still exists; IDs20001/20002 are stable.
		var b=CORE.new()
		if not b.configure(input,engine.units,engine.rules):return engine.bad(b.error)
		state.pending.battle_input=b.input.duplicate(true);state.battle_snapshot=b.snapshot();state.battle_result={};state.phase="battle";r.node="battle"
		engine.emit(state,command,"rescue_guard_locked",{"attention":r.attention,"guard_count":input.enemy.size()});return {"ok":true}
	var day=int(state.day)+extra
	if not engine.acknowledge_expiry(state,day,payload):return engine.bad("此选择将错过营救期限；请明确确认，或改走不额外耗日的路线")
	engine.expire_before(state,day,command);state.day=day;r.attention=mini(int(engine.rules.rescue_path.attention_cap),attention)
	r.choices.append({"node":r.node,"choice":selected,"extra_days":extra});r.node="camp" if r.node=="approach" else "gate"
	engine.emit(state,command,"rescue_path_choice",{"choice":selected,"extra_days":extra,"attention":r.attention})
	return {"ok":true}

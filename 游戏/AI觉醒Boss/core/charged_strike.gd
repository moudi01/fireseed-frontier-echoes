extends RefCounted
## Optional elite only. Fixed cell, deterministic ticks, no I/O/physics/clock.
var configs=[]
var states={}
var rule={}
func configure(core,source: Dictionary,rules: Dictionary) -> bool:
	configs=[];states={};rule=rules.get("elite_charge",{})
	var values=source.get("charge_config",[])
	if not values is Array or values.size()>1:return core.fail("精英招式配置必须为至多一项数组")
	for c in values:
		if not c is Dictionary or not core.integer(c.get("caster_id")) or not core.by_id.has(int(c.caster_id)) or c.get("skill_id")!="telegraphed_strike":return core.fail("精英招式配置错误")
		var actor=core.by_id[int(c.caster_id)]
		if actor.side!="enemy" or actor.unit_type!="cavalry" or rule.is_empty():return core.fail("重击仅用于显式敌方突击兵精英")
		configs.append({"caster_id":actor.instance_id,"skill_id":"telegraphed_strike"});states[str(actor.instance_id)]={"release_tick":0,"next_cast_tick":1,"target_cell":[]}
	return true
func plan(core,emitted: Array) -> Dictionary:
	var blocked={};var releases={}
	for c in configs:
		var actor=core.by_id[int(c.caster_id)];var s=states[str(actor.instance_id)]
		if not actor.alive:continue
		if int(s.release_tick)>0:
			blocked[actor.instance_id]=true
			if core.tick>=int(s.release_tick):
				releases[actor.instance_id]=s.target_cell.duplicate();s.release_tick=0;s.target_cell=[]
			continue
		if core.tick<int(s.next_cast_tick) or core.tick<int(actor.next_attack_tick):continue
		var adjacent=core.alive_states().filter(func(u):return u.side!=actor.side and core.distance(core.cell(actor),core.cell(u))<=1)
		if adjacent.is_empty():continue
		adjacent.sort_custom(func(a,b):return core.less([0 if core.is_focus(actor.side,a.instance_id) else 1,a.instance_id],[0 if core.is_focus(actor.side,b.instance_id) else 1,b.instance_id]))
		s.target_cell=core.array_cell(core.cell(adjacent[0]));s.release_tick=core.tick+int(rule.windup_ticks);s.next_cast_tick=core.tick+int(rule.cooldown_ticks);blocked[actor.instance_id]=true
		emitted.append(core.event("skill","charge_windup",{"actor":actor.instance_id,"side":actor.side,"unit":core.templates[actor.unit_type].name,"actor_pos":core.array_cell(core.cell(actor)),"target_cell":s.target_cell.duplicate(),"ready_tick":s.release_tick,"skill_id":"telegraphed_strike"}))
	return {"blocked":blocked,"releases":releases}
func clear_pending(id):
	if states.has(str(int(id))):states[str(int(id))].release_tick=0;states[str(int(id))].target_cell=[]
func restore(core,data,replacements: Array,at_tick: int,finished: bool) -> bool:
	if not data is Dictionary or data.size()!=states.size():return core.fail("精英快照缺失或多余")
	var checked={}
	for id in states:
		var s=data.get(id,{})
		if not s is Dictionary or not core.integer(s.get("release_tick")) or not core.integer(s.get("next_cast_tick")) or not s.get("target_cell") is Array:return core.fail("精英快照格式错误")
		if s.next_cast_tick<1 or s.next_cast_tick>at_tick+int(rule.cooldown_ticks):return core.fail("精英冷却越界")
		if s.release_tick==0:
			if not s.target_cell.is_empty():return core.fail("没有蓄力却保留标记格")
		else:
			if s.release_tick<=at_tick or s.release_tick>at_tick+int(rule.windup_ticks) or finished:return core.fail("精英释放时点越界")
			if not replacements.any(func(u):return int(u.instance_id)==int(id) and u.alive):return core.fail("倒地精英不能保留蓄力")
			if int(s.next_cast_tick)!=int(s.release_tick)-int(rule.windup_ticks)+int(rule.cooldown_ticks):return core.fail("精英冷却与起手不一致")
			if s.target_cell.size()!=2 or not core.integer(s.target_cell[0]) or not core.integer(s.target_cell[1]) or s.target_cell[0]<0 or s.target_cell[0]>=core.width or s.target_cell[1]<0 or s.target_cell[1]>=core.height:return core.fail("标记格越界")
			var actor=replacements.filter(func(u):return int(u.instance_id)==int(id))[0]
			if core.distance(core.cell(actor),Vector2i(int(s.target_cell[0]),int(s.target_cell[1])))!=1:return core.fail("蓄力标记不在施法者邻格")
		checked[id]={"release_tick":int(s.release_tick),"next_cast_tick":int(s.next_cast_tick),"target_cell":s.target_cell.map(func(v):return int(v))}
	states=checked;return true

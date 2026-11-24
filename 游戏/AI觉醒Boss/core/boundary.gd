extends RefCounted
## Formal route only; no demo namespace, rewards, losses or time from scene buttons.
static func enemies(rule: Dictionary,route: String) -> Array:
	var result=[];var types=rule.outpost_enemy if route=="outpost" else rule.boundary_enemy
	var positions=rule.outpost_positions if route=="outpost" else rule.boundary_positions
	for i in range(types.size()):result.append({"instance_id":30001+i,"side":"enemy","unit_type":types[i],"x":positions[i][0],"y":positions[i][1],"stance":rule.outpost_stances[i] if route=="outpost" else "attack"})
	return result
static func validate(state: Dictionary) -> bool:
	if state.pending.get("route")!="boundary":return state.phase!="boundary"
	var value=state.pending.get("boundary",{})
	if not value is Dictionary or value.get("stage") not in ["guards","approach","wall","observed","returned"] or not value.get("observed") is bool or not value.get("completed") is bool:return false
	if state.phase=="battle":return value.stage=="guards" and not value.observed and not value.completed
	if state.phase=="boundary":return value.stage in ["approach","wall","observed"] and not value.completed and value.observed==(value.stage=="observed")
	if state.phase!="settlement":return false
	if value.stage=="guards":return not value.observed and not value.completed and state.battle_result.get("result")!="player_win"
	return value.stage=="returned" and state.battle_result.get("result")=="player_win" and (not value.observed or value.completed)
static func choose(engine,state: Dictionary,command: Dictionary,payload: Dictionary) -> Dictionary:
	if state.phase!="boundary":return engine.bad("当前不在正式边界节点")
	var b=state.pending.boundary
	if payload.get("stage")!=b.stage:return engine.bad("边界节点已改变，未重复确认")
	var choice=payload.get("choice","")
	if choice=="return":
		b.completed=b.stage in ["wall","observed"];b.stage="returned";state.phase="settlement"
	elif choice=="forward" and b.stage=="approach":b.stage="wall"
	elif choice=="observe" and b.stage=="wall":b.stage="observed";b.observed=true
	else:return engine.bad("该节点没有这个选项")
	engine.emit(state,command,"boundary_choice",{"choice":choice,"stage":b.stage});return {"ok":true}

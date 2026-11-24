extends RefCounted
## Display-only projections. The host captures settled() only after a successful
## committed SETTLE. Nothing here awards resources, advances time or writes saves.
const RESOURCE_NAMES={"coins":"铜币","crystals":"结晶","recruit_token":"招募信物"}
const STATUS_NAMES={"READY":"待命","ACTIVE":"出征中","RESTING":"轮休","RECOVERING":"养伤","CAPTURED":"失联","ABSORBED":"正式吞并","DISMISSED":"已离队"}

static func member_name(state: Dictionary,id: int) -> String:
	return str(state.get("roster",{}).get(str(id),{}).get("name","#%d"%id))

static func names(state: Dictionary,ids: Array) -> String:
	return "、".join(ids.map(func(id):return member_name(state,int(id))))

static func preview(state: Dictionary,payload: Dictionary,engine) -> Dictionary:
	if state.get("phase")!="settlement":return {}
	var errors=[];var bring=[];var discard={}
	var selection=engine.settlement_selection(state,payload)
	if not selection.ok:return {"can_confirm":false,"warnings":[selection.error],"lines":[selection.error]}
	var modern=engine.settlement_version(state)==2
	var raw_bring=selection.bring_ids;var raw_discard=selection.discard
	var wiped=state.battle_result.get("result") in ["enemy_win","draw"]
	var down=engine.wounded(state)
	if not raw_bring is Array:errors.append("带回伤兵名单格式错误。")
	else:
		for value in raw_bring:
			if not engine.CORE.integer(value) or int(value) not in down or int(value) in bring or (wiped and int(value) not in engine.escorted_ids(state)):errors.append("带回名单含无效或重复人员。")
			else:bring.append(int(value))
	if not raw_discard is Dictionary:errors.append("弃置数量格式错误。")
	else:discard=raw_discard
	var account=engine.transport(state,bring)
	var abandonment=engine.abandonment_plan(state,bring)
	var items=[];var item_ids=[];var discarded_value=0
	for item in engine.loot(state):
		var amount=discard.get(item.id,0)
		var valid=engine.CORE.integer(amount) and int(amount)>=0 and int(amount)<=int(item.quantity)
		if not valid:errors.append("%s的弃置数量无效。"%item.name)
		var dropped=int(amount) if valid else 0
		items.append({"id":str(item.id),"name":str(item.name),"quantity":int(item.quantity),"unit_value":int(item.unit_value),"discarded":dropped,"brought":int(item.quantity)-dropped})
		item_ids.append(item.id);discarded_value+=dropped*int(item.unit_value)
	for key in discard:
		if key not in item_ids:errors.append("弃置清单含本次没有获得的物资。")
	var shortfall=maxi(0,int(account.required_discard)-discarded_value)
	if shortfall>0:errors.append("还需弃置清算值%d。"%shortfall)
	var follows=abandonment.follows_ids
	var left=abandonment.left_ids
	if not follows.is_empty() and payload.get("acknowledge_lorne_stays")!=true:errors.append("请确认洛恩将随伤兵留下。")
	if state.pending.get("route") in ["tutorial_trail","outpost","boundary"] and not wiped and not left.is_empty() and payload.get("acknowledge_abandonment")!=true:errors.append("请确认留下的伤兵及营救期限。")
	var people={"living_returning":0,"wounded_returning":bring.size(),"down":down.size(),"left_wounded":0 if wiped else left.size(),"following":follows.size(),"absorbed":0,"captured":0,"temporary_leaving":0,"reserves_returning":0}
	for unit in engine.campaign_units(state):
		if unit.get("side")!="player":continue
		var id=int(unit.instance_id);var member=state.roster[str(id)]
		if wiped:
			var status=engine.failed_member_status(state,unit)
			if status=="CAPTURED":people.captured+=1
			elif status=="ABSORBED":people.absorbed+=1
		elif id in follows or (not unit.alive and id not in bring):
			if member.temporary:people.temporary_leaving+=1
			else:people.captured+=1
		elif member.temporary:people.temporary_leaving+=1
		elif unit.alive:people.living_returning+=1
	for id in state.pending.reserve_ids:
		if int(id) in follows:people.captured+=1
		else:people.reserves_returning+=1
	var lines=[]
	if items.is_empty():lines.append("本次战利品：无；不会从既有仓库扣除物资。")
	for item in items:
		lines.append("%s  获得%d → 带回%d"%[item.name,item.quantity,item.brought] if modern else "%s  获得%d → 带回%d / 弃置%d"%[item.name,item.quantity,item.brought,item.discarded])
	if modern:lines.append("伤员由实际战果确定，胜利或安全返回时自动接回；途中不会回血或复活。")
	else:lines.append("运输清算值%d · 需弃置%d（%d%%） · 已选%d%s"%[int(account.total),int(account.required_discard),int(account.loss_percent),discarded_value," · 已满足" if shortfall==0 else " · 尚缺%d"%shortfall])
	var aid=int(engine.return_aid(state))
	lines.append("另计城镇援助：%d铜币。"%aid)
	if wiped:lines.append("本次结算：普通出战者正式吞并%d；实际失联%d（含仍随队的先前伤员）。"%[people.absorbed,people.captured] if modern else "队伍覆灭：普通出战者正式吞并%d；英雄失联%d。"%[people.absorbed,people.captured])
	elif modern:lines.append("存活返回%d · 伤员接回%d"%[people.living_returning,people.wounded_returning])
	else:lines.append("存活返回%d · 伤兵带回%d · 伤兵留下%d · 随行留下%d"%[people.living_returning,people.wounded_returning,people.left_wounded,people.following])
	if modern and wiped and people.wounded_returning>0:lines.append("此前已由预备队护送离场的伤员%d人，仍按实际结果归队养伤。"%people.wounded_returning)
	if people.reserves_returning>0:lines.append("另有预备队员%d人返回轮休。"%people.reserves_returning)
	if people.temporary_leaving>0:lines.append("临时队员%d人将在结算后离队。"%people.temporary_leaving)
	if not wiped and not left.is_empty():lines.append("留下：%s；最晚第%d日营救。"%[names(state,left),int(abandonment.deadline_day)])
	if not follows.is_empty():lines.append("随伤兵留下：%s。"%names(state,follows))
	return {"items":items,"total_value":int(account.total),"loss_percent":int(account.loss_percent),"required_discard":int(account.required_discard),"discarded_value":discarded_value,"shortfall":shortfall,"aid_coins":aid,"people":people,"can_confirm":errors.is_empty(),"warnings":errors,"lines":lines,"bring_ids":bring.duplicate(),"left_ids":left.duplicate(),"follows_ids":follows.duplicate()}

static func settled(before: Dictionary,after: Dictionary,payload: Dictionary,engine) -> Dictionary:
	# Never infer exact rewards from old event history: it does not retain item
	# quantities or every transport choice. This report is deliberately ephemeral.
	if before.get("phase")!="settlement" or after.get("phase")!="town":return {}
	if before.get("expedition")!=after.get("expedition") or before.get("day")!=after.get("day"):return {}
	var prior_ids={}
	for event in before.get("events",[]):prior_ids[str(event.get("id",""))]=true
	var settled_event={}
	for event in after.get("events",[]):
		if event.get("kind")=="expedition_settled" and not prior_ids.has(str(event.get("id",""))) and event.get("expedition")==before.get("expedition"):
			if not settled_event.is_empty():return {}
			settled_event=event
	if settled_event.is_empty():return {}
	var plan=preview(before,payload,engine)
	if plan.is_empty() or not plan.can_confirm:return {}
	if int(settled_event.get("loot_total",-1))!=int(plan.total_value):return {}
	if int(settled_event.get("discarded_value",-1))!=int(plan.discarded_value):return {}
	var actual_bring=settled_event.get("wounded_returned",[]).duplicate();actual_bring.sort()
	var planned_bring=plan.bring_ids.duplicate();planned_bring.sort()
	if actual_bring!=planned_bring:return {}
	var resource_rows=[];var lines=[]
	for key in ["coins","crystals","recruit_token"]:
		var old=int(before.resources.get(key,0));var current=int(after.resources.get(key,0))
		resource_rows.append({"id":key,"name":RESOURCE_NAMES[key],"before":old,"after":current,"delta":current-old})
		lines.append("%s  %d → %d（本次入库%s%d）"%[RESOURCE_NAMES[key],old,current,"+" if current-old>=0 else "",current-old])
	var exact=true
	for row in resource_rows:
		var expected=int(plan.aid_coins) if row.id=="coins" else 0
		for item in plan.items:
			if item.id==row.id:expected+=int(item.brought)
		if int(row.delta)!=expected:exact=false
	if exact:
		for item in plan.items:lines.append("%s：带回%d。"%[item.name,item.brought] if engine.settlement_version(before)==2 else "%s：带回%d / 弃置%d。"%[item.name,item.brought,item.discarded])
		lines.append("本次铜币入库已含城镇援助%d；援助另计，不重复领取。"%int(plan.aid_coins))
	else:lines.append("物资以实际仓库变化为准；不额外推算本次物资来源。")
	var xp_rows=[];var member_rows=[];var counts={"READY":0,"RESTING":0,"RECOVERING":0,"CAPTURED":0,"ABSORBED":0,"DISMISSED":0}
	var ids=after.roster.keys();ids.sort_custom(func(a,b):return int(a)<int(b))
	for key in ids:
		var member=after.roster[key];var previous=before.roster.get(key,{})
		if counts.has(member.status):counts[member.status]+=1
		if previous.is_empty():continue
		var delta=int(member.xp)-int(previous.xp)
		if delta>0 and not member.temporary:xp_rows.append({"id":int(member.id),"name":str(member.name),"before":int(previous.xp),"after":int(member.xp),"delta":delta})
		if previous.status!=member.status or int(previous.rest_remaining)!=int(member.rest_remaining) or delta!=0:
			member_rows.append({"id":int(member.id),"name":str(member.name),"before_status":str(previous.status),"status":str(member.status),"before_rest":int(previous.rest_remaining),"rest_remaining":int(member.rest_remaining),"xp_delta":delta,"temporary":bool(member.temporary)})
	for row in xp_rows:lines.append("%s  经验%d → %d（+%d）"%[row.name,row.before,row.after,row.delta])
	if xp_rows.is_empty():lines.append("本次没有永久队员获得经验。")
	for row in member_rows:
		var rest=" · 还需%d次远征结算"%row.rest_remaining if row.status in ["RESTING","RECOVERING"] else ""
		lines.append("%s  %s → %s%s"%[row.name,STATUS_NAMES.get(row.before_status,row.before_status),STATUS_NAMES.get(row.status,row.status),rest])
	lines.append("据点现有：待命%d · 轮休%d · 养伤%d · 失联%d"%[counts.READY,counts.RESTING,counts.RECOVERING,counts.CAPTURED])
	var next=[]
	if not xp_rows.is_empty():next.append("训练场：查看本次归队者的培养条件。")
	if counts.RESTING+counts.RECOVERING>0:next.append("营舍：查看轮休与养伤；等待不减少次数。")
	if counts.CAPTURED>0:next.append("出征营帐：核对失联者的营救截止日。")
	if counts.READY==0:next.append("据点：领取应急巡逻队，继续恢复队伍。")
	else:next.append("出征营帐：从%d名待命队员中重新编队。"%counts.READY)
	var recruit_cost=int(engine.params.get("recruit_cost",10))
	var living_roster=after.roster.values().filter(func(member):return member.status not in ["ABSORBED","DISMISSED"]).size()
	if int(after.resources.coins)>=recruit_cost and living_roster<int(engine.rules.formation.max_roster):next.append("兵营：当前铜币足够招募1名士兵。")
	var completed=bool(settled_event.get("valid_for_act",false))
	var result=str(before.battle_result.get("result",""))
	var headline="远征归城 · 已入账" if completed else ("队伍覆灭 · 已结算" if result in ["enemy_win","draw"] else "提前返回 · 已入账")
	return {"headline":headline,"day":int(after.day),"expedition":int(after.expedition),"event_id":str(settled_event.id),"objective_completed":completed,"battle_result":result,"resource_rows":resource_rows,"resources":resource_rows,"xp_rows":xp_rows,"xp":xp_rows,"member_rows":member_rows,"people":counts,"ready_count":int(counts.READY),"resting_count":int(counts.RESTING),"recovering_count":int(counts.RECOVERING),"captured_count":int(counts.CAPTURED),"loot_breakdown_exact":exact,"aid_coins":int(plan.aid_coins) if exact else 0,"lines":lines,"summary_lines":lines,"next_steps":next}

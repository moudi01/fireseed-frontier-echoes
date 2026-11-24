extends RefCounted
const PROGRESS=preload("res://core/progression.gd")
## Read-only scene selection. Gameplay changes only happen through campaign commands.
static func seen(state: Dictionary,id: String) -> bool:
	return id in state.facts.get("seen_scenes",[])
static func card(id: String,title: String,lines: Array,choices: Array) -> Dictionary:
	return {"id":id,"title":title,"lines":lines,"choices":choices}
static func pending(state: Dictionary) -> Dictionary:
	if state.get("phase")!="town":return {}
	var next={}
	var confirm=[{"id":"continue","text":"继续"}]
	if int(state.expedition)==0 and not seen(state,"gate_intro"):
		next=card("gate_intro","城门 · 先去看路",["岑：两个人够吗？","林：看路，不是攻城。走近了再说。","选择两名队员，其他人留城轮换。推荐林（盾兵）与岑（弓兵）。","部署区为y=0–2。进攻会接近敌人，防御会留在原地；集火在开战前选择，消耗5/10指挥点。"],confirm)
	var first=state.facts.get("first_return",{})
	if next.is_empty() and not first.is_empty() and not seen(state,"first_return"):
		if first.result in ["enemy_win","draw"]:
			next=card("first_return","城门 · 接住失败",["此次出战人员的损失已按实际结果列入名册。","留城队员仍可出征；铜币可用于征兵。全队无人就绪时，可领取免费应急巡逻队。","不需要再输一次。完成短程委托，仍能取得招募信物。"],confirm)
		elif state.get("settlement_rules_version",1)==2:
			next=card("first_return","返程 · 核对实际战果",["本次可救回的伤员已随队归城；没有倒地者时不额外制造伤员。","带回伤员不需要放弃战利品，也不能主动将其留下。无伤者轮休1次，归队伤员养伤2次；途中不回血、不复活。","战败的真实失联与限期营救仍保留，实际人员、物资和期限请看名册与归城记录。"],confirm)
		elif first.zero_loss:
			next=card("first_return","无人倒地 · 运输演示",["首次教程远征没人倒下。名册与仓库保持实际战果，下面只演示另一种处境。","假设本次得到信物1件（清算值60）和40结晶，总值100；另有1名伤兵。带回需要弃置至少50。","只弃40结晶还不够；信物不可拆分。弃信物60可以带人回城，并保留40结晶。","以下选择仅记录已看教学，不扣物资、不制造伤兵、不推进日期。"],[{"id":"bring","text":"模拟：弃信物60，带回伤兵"},{"id":"leave","text":"模拟：保留收益，留下伤兵"}])
		else:
			next=card("first_return","返程 · 记下实际选择",["运输与人员去向已按你刚才确认的选择入账。","带回者恢复两次远征；留在原地者进入6日失联窗口。实际状态与期限请看名册。","没有信物也能继续：短程委托会提供新的信物，其他待命队员可接替出征。"],confirm)
	var trail=state.facts.get("tutorial_trail_return",{})
	if next.is_empty() and not trail.is_empty() and not seen(state,"trail_return"):
		var lines=[]
		if trail.result in ["enemy_win","draw"]:
			lines=["这趟侦查在%s失利。请按名册查看实际人员损失。"%("普通战" if trail.node=="first" else "精英战"),"下一趟先看敌人的接近路线，再调整盾兵与弓兵。待命队员、征兵与免费应急队保证仍有下一步。"]
		elif trail.node!="elite":lines=["队伍选择提前折返，没有取得精英战利品。真实伤势与人员去向已按结算处理。" if trail.node=="return" else "普通战结束后队伍未能继续推进，已返回。没有取得精英战利品。","留城队员可以接短程委托，信物和营救路线仍可继续。"]
		elif state.get("settlement_rules_version",1)==2:lines=["林道侦查完成，可救回的本次伤员已接回养伤，战利品与实际人员只入账一次。","无需以战利品换人，不提供主动遗弃；请在名册安排轮换与培养。"]
		elif trail.wounded_names.is_empty():lines=["林道侦查完成，没有人倒下。战利品与实际人员已入账。","不需要制造一次损失；运输规则仍可通过独立演示查看。"]
		else:
			lines=["这趟倒地者："+"、".join(trail.wounded_names)+"。"]
			if not trail.brought.is_empty():lines.append("你弃置了%d清算值的本次战利品，将%d名伤兵带回。带回者恢复2次远征。"%[int(trail.discarded_value),trail.brought.size()])
			if not trail.left.is_empty():lines.append("你留下了%d名伤兵；失联从第%d日开始，最晚第%d日完成营救。"%[trail.left.size(),int(trail.day),int(trail.day)+6])
			lines.append("没有信物可接明确奖励信物的短委托；有人失联时，2日营救入口与委托并列。")
		next=card("trail_return","林道 · 你的返回选择",lines,confirm)
	var payoff=state.facts.get("formation_payoff",{})
	if next.is_empty() and not payoff.is_empty() and not seen(state,"formation_payoff"):
		var a=payoff.actual;var r=payoff.reference
		next=card("formation_payoff","布阵 · 这次调整带来了什么",["当前生命、相同敌人与种子、本场相同集火配置的参考演算：","沿用普通战站位：存活%d人，剩余%dHP；实际精英战：存活%d人，剩余%dHP。"%[int(r.alive),int(r.hp),int(a.alive),int(a.hp)],"你的调整让更多队员站着，或保留了更多生命。" if payoff.improved else "本次调整未提高存活人数或剩余生命。可以在下一趟尝试不同站位与姿态。","参考演算不推进日期，不发战利品，也不改变已经确认的真实战果。"],confirm)
	if next.is_empty() and not trail.is_empty() and trail.caravan_choice=="mark" and int(state.expedition)>int(trail.expedition) and not seen(state,"caravan_echo"):
		next=card("caravan_echo","城门 · 路标的回响",["车主捎来口信：沿着那段布找到了车。","你上趟多花的1日已经记在日历里；这封口信没有额外奖励。"],confirm)
	if next.is_empty() and not state.facts.get("lorne_recruited",false) and state.resources.recruit_token>0 and not seen(state,"lorne_offer"):
		next=card("lorne_offer","城门 · 守墙的人",["洛恩把盾靠在桌边，先看了一眼队伍。","洛恩：少的是人手，还是能站在前面的人？","交付1件信物即可招募洛恩，正式编制免费提升至14。你也可以先整理队伍，稍后再招募。"],[{"id":"recruit","text":"交1件信物，请洛恩同行"},{"id":"later","text":"先整理队伍，稍后再说"}])
	if next.is_empty() and state.facts.get("lorne_recruited",false) and not seen(state,"lorne_joined"):
		var returned=state.roster.values().any(func(m):return m.unit_type=="lorne" and m.status in ["READY","RESTING","RECOVERING"])
		next=card("lorne_joined","洛恩 · 抬盾的那一下",["洛恩：抬盾那一下，我顾不过来。先替我挡住。" if returned else "洛恩目前未归队，请在名册查看其去向与期限。","洛恩的cost为8，当前编制为14；士兵各占1，可与他一同出征。","可选低于40%生命时起手，或首战建议的开局施放一次。前摇1步，期间洛恩自身受伤翻倍；下一步形成全队共用的80点盾。","抬盾与展开时不移动、不普攻。盾未耗尽时不重放，起手后12步可再次施放。"],confirm)
	var protection=state.facts.get("lorne_protection",{})
	if next.is_empty() and not protection.is_empty() and not seen(state,"lorne_protection"):
		var returned=state.roster.values().any(func(m):return m.unit_type=="lorne" and m.status in ["READY","RESTING","RECOVERING"])
		next=card("lorne_protection","战后 · 盾替谁挡住了",["第%d次远征记录：洛恩的共享盾为其他队员吸收了%d点伤害。"%[int(protection.expedition),int(protection.absorbed)],"洛恩：还站着就好。下回换你看着我。" if returned else "洛恩未随队返回。战报里保留了那次抬盾的记录。","回到名册，确认队员的轮休与失联期限，再安排下一趟。"],confirm)
	if next.is_empty():
		for report in state.facts.get("rescue_reports",[]):
			var id="rescue_return_"+str(int(report.expedition))
			if seen(state,id):continue
			var lines=["第%d日，救援队%s。"%[int(report.day),"撤离返回" if report.withdrawn else ("赢下了守卫战" if report.result=="player_win" else "未能完成营救")]]
			if not report.rescued_names.is_empty():lines.append("实际救回："+"、".join(report.rescued_names)+"。伤后恢复2次远征。")
			for target in report.targets:
				if target.status=="CAPTURED":lines.append("当次返回时，%s尚未救回，原期限仍为第%d日。"%[target.name,int(target.deadline)])
				elif target.status=="ABSORBED":lines.append("%s的期限已过，已正式吞并，不能再营救或祭坛提取。"%target.name)
			lines.append("救援队本身的轮休、伤势或全灭损失另列名册；未救目标不会因失败重新获得6日。")
			next=card(id,"林道 · 救援结果",lines,confirm);break
	if next.is_empty():
		for entry in state.facts.get("homecomings",[]):
			var id="homecoming_"+entry.id
			if seen(state,id):continue
			next=card(id,"归城夜 · 盾旁的一点灯",["第%d日，%s通过%s归城。"%[int(entry.day),entry.name,entry.method],"那一夜，有人把灯放在空床边。盾靠着墙，扣带还没解开。","这页记录的是那次归城。当前能否同行，请看名册中的实际恢复与人员去向。"],confirm);break
	var valid=PROGRESS.count(state)
	if next.is_empty() and valid>=3 and not seen(state,"act1_new_enemy"):
		var lines=["斥候带回一块剥落的甲片，比上一批更厚。","新敌情：重甲前哨。两名盾兵守住不同方向，弓兵留在后排。下一趟先看接近路线、站位与集火。"]
		if state.roster.values().any(func(m):return m.unit_type=="lorne" and m.status in ["READY","RESTING","RECOVERING"]):lines.append("洛恩：盾不是拿来比谁厚的。看它先护哪边。")
		next=card("act1_new_enemy","斥候报告 · 重甲前哨",lines,confirm)
	if next.is_empty() and valid>=3 and not seen(state,"act1_memory"):
		next=card("act1_memory","门还在",["Boss：门还在。规矩也在。","Boss：这一次，别只让他们记得怎么进来。","棋盘的阴影忽然很浅。白色轮廓里，只有一把空椅子。"],confirm)
	if next.is_empty() and state.facts.has("boundary_return") and not seen(state,"boundary_return"):
		var report=state.facts.boundary_return
		next=card("boundary_return","归城 · 道路阻断",["第%d日，队伍从深核边界返回。前路被看不见的东西阻断；这不是战斗失败。"%int(report.day),"你查看过台阶：鞋底的灰越不过去。" if report.observed else "队伍选择原路返回，没有继续观察台阶。","人员、伤势与物资已按实际选择结算。可以在城镇开启异常调查，也可先处理名册与失联期限。"],confirm)
	if next.is_empty() and state.facts.get("current_act",1)==2 and not seen(state,"act2_entry"):
		next=card("act2_entry","第二幕 · 异常调查",["军务记录：道路阻断。敌我都没有给出关闭那条路的命令。","下一步是追查阻断与旧记录之间的关系。","已抵达当前内容终点。你可以继续整备、培养和远征；后续调查内容尚未开放。"],confirm)
	return next
static func acknowledge(state: Dictionary,scene: Dictionary,choice: String):
	var seen_ids=state.facts.get("seen_scenes",[]).duplicate();seen_ids.append(scene.id);state.facts["seen_scenes"]=seen_ids
	var history=state.facts.get("scene_history",[]).duplicate(true)
	history.append({"scene_id":scene.id,"title":scene.title,"lines":scene.lines.duplicate(),"choice":choice,"choice_text":scene.choices.filter(func(item):return item.id==choice)[0].text})
	state.facts["scene_history"]=history
	if scene.id=="first_return" and choice in ["bring","leave"]:state.facts["transport_lesson_choice"]=choice

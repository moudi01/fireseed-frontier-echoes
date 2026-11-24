extends RefCounted
## Uses the existing durable store, but refuses normal campaign files and commands.
const CORE=preload("res://core/battle_core.gd")
const CAMPAIGN=preload("res://core/campaign_rules.gd")
var campaign
func _init():
	campaign=CAMPAIGN.new(JSON.parse_string(FileAccess.get_file_as_string("res://data/units.json")),JSON.parse_string(FileAccess.get_file_as_string("res://data/design_rules.json")),JSON.parse_string(FileAccess.get_file_as_string("res://data/campaign_params.json")))
func valid_state(state: Dictionary) -> bool:
	if not state.get("facts") is Dictionary or state.facts.get("anomaly_demo")!=true:return false
	# Reuse structural checks on a copy; the namespace tag stays in every persisted demo record.
	var structural=state.duplicate(true);structural.facts.erase("anomaly_demo")
	return campaign.valid_state(structural) and CORE.integer(state.facts.get("demo_stage")) and state.facts.demo_stage>=0 and state.facts.demo_stage<=7 and state.facts.get("reduced_flash") is bool and state.facts.get("demo_history") is Array
func apply(previous: Dictionary,command: Dictionary) -> Dictionary:
	var state=previous.duplicate(true);var payload=command.get("payload",{})
	if not payload is Dictionary:return campaign.bad("演示选择格式错误")
	if command.get("kind")=="NEW_DEMO":
		if not state.is_empty():return campaign.bad("已有演示进度，请继续")
		state=campaign.initial(42);state.facts={"anomaly_demo":true,"demo_stage":0,"reduced_flash":true,"demo_history":[]};campaign.emit(state,command,"demo_created");return {"ok":true,"state":state}
	if not valid_state(state):return campaign.bad("这不是独立演示存档，未覆盖文件")
	if command.get("kind")=="DEMO_ACCESSIBILITY":
		if not payload.get("reduced_flash") is bool:return campaign.bad("显示设置必须为布尔值")
		state.facts.reduced_flash=payload.reduced_flash
	elif command.get("kind")=="DEMO_STEP":
		var card=scene(state);var choice=payload.get("choice","")
		if payload.get("stage")!=state.facts.demo_stage or choice not in card.choices.map(func(c):return c.id):return campaign.bad("演示节点已经改变，未重复执行")
		state.facts.demo_history.append({"title":card.title,"lines":card.lines.duplicate(),"choice":choice})
		state.facts.demo_stage=6 if int(state.facts.demo_stage)==4 and choice=="return" else int(state.facts.demo_stage)+1
		campaign.emit(state,command,"demo_step",{"stage":state.facts.demo_stage,"choice":choice})
	else:return campaign.bad("独立演示不接受正式游戏命令")
	return {"ok":true,"state":state}
func scene(state: Dictionary) -> Dictionary:
	var next=[{"id":"continue","text":"继续"}]
	var cards=[
		{"title":"独立异常演示","lines":["这是预置的第4次远征片段，使用独立存档。演示完成不会解锁正式周目的剧情。","正式周目仍需按正常进度抵达这里。这个片段不要求你先失去队员。"],"choices":next},
		{"title":"门还在","lines":["Boss：门还在。规矩也在。","Boss：这一次，别只让他们记得怎么进来。","棋盘的阴影忽然很浅。白色轮廓里，有一把空椅子。"],"choices":next},
		{"title":"白房间","lines":["房间里没有人。椅子面对着一个没有窗的方向。","这不是队员死亡触发的记忆。你可以停下来查看，也可以继续走。"],"choices":next},
		{"title":"深核边界","lines":["前方是通向王座的台阶，没有伏击阵型。","最前面的队员向前。影子停在空处，人还没来得及停。"],"choices":[{"id":"forward","text":"向前一步"}]},
		{"title":"不存在的墙","lines":["Boss：怎么不走了？","最前面的人抬起手。手掌贴住了空气。","界面仍在工作。这里没有判你战败。"],"choices":[{"id":"observe","text":"查看前方"},{"id":"return","text":"原路返回"}]},
		{"title":"台阶没有断","lines":["那一段台阶没有断，但鞋底的灰越不过去。","Boss：我没关门。","继续观察没有隐藏善恶分，也不需要牺牲队员。"],"choices":[{"id":"return","text":"原路返回"}]},
		{"title":"道路阻断 · 返回记录","lines":["这次片段中无人倒地。正式游戏里，无伤兵全额带回；若已有伤兵，仍按正常运输处理。","本次记录只保存在演示中，不改原队伍、物资或剧情进度。"],"choices":[{"id":"finish","text":"完成演示"}]},
		{"title":"演示已完成","lines":["可以回看本次记录，或关闭窗口继续原来的周目。","演示记录会保留，关闭窗口不会重新播放已确认的片段。"],"choices":[]}
	]
	return cards[int(state.facts.demo_stage)]

extends RefCounted
## Presentation only: never infer a pause cause from a tick number or change rules.
static func exit_hint(has_report: bool) -> String:
	var text="下次启动同一存档，将从最后已确认的行动继续；未确认的选择需重新设置。"
	if has_report:text+="\n详细归城战报仅在本次运行保留，退出后无法重开；已入账的物资与经验不受影响。"
	return text
static func battle(tick: int,paused: bool,reason: String,finished: bool,ending: bool) -> Dictionary:
	var description=""
	if finished:description="战斗结束 · 正在收束" if ending else "战斗结束 · 等待返回"
	elif paused:
		description={"charge":"蓄力重击预警暂停","manual":"已手动暂停","step":"单步后暂停","error":"行动未完成，战斗已暂停"}.get(reason,"战斗已暂停")
		description+=" · 可继续战斗，或单步观察。"
	else:description="战斗进行中"
	return {"status":"第%d步 · %s"%[tick,description],"pause_text":("继续收束" if paused else "暂停收束") if finished else ("继续战斗" if paused else "暂停战斗"),"step_text":"单步" if paused else "单步并暂停","can_pause":not finished or ending,"can_step":not finished}

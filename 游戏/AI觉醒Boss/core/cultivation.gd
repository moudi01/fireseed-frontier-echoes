extends RefCounted
## Optional first level-up. No clock, I/O, template mutation or purchased training.
static func whole(value) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value)==floor(float(value)) and abs(float(value))<=9007199254740991.0
static func valid_member(member: Dictionary) -> bool:
	if not member.has("growth_version"):return true # Legacy levels never imply new bonuses.
	return whole(member.growth_version) and member.growth_version==1 and member.level==2 and not member.temporary
static func can_level(member: Dictionary,rule: Dictionary) -> bool:
	return member.get("status") in ["READY","RESTING","RECOVERING"] and not member.get("temporary",true) and member.get("level") == 1 and not member.has("growth_version") and int(member.get("xp",0))>=int(rule.xp_cost)
static func stats(template: Dictionary,rule: Dictionary,grown: bool) -> Dictionary:
	var result=template.duplicate()
	if grown:
		result.hp=int(result.hp)+int(rule.hp_bonus);result.attack=int(result.attack)+int(rule.attack_bonus)
	return result
static func configure(config,states: Array,rule: Dictionary) -> Dictionary:
	if not config is Array or config.size()>states.size():return {"ok":false,"error":"等级配置须为有界数组"}
	var levels={};var normalized=[]
	for item in config:
		if not item is Dictionary or not whole(item.get("instance_id")) or not whole(item.get("level")) or item.level!=2 or rule.is_empty():return {"ok":false,"error":"等级配置只开放Lv2原型"}
		var id=int(item.instance_id);var key=str(id)
		if levels.has(key) or not states.any(func(u):return int(u.instance_id)==id and u.side=="player"):return {"ok":false,"error":"等级配置实例重复或不属我方部署"}
		levels[key]=2;normalized.append({"instance_id":id,"level":2})
	normalized.sort_custom(func(a,b):return a.instance_id<b.instance_id)
	return {"ok":true,"levels":levels,"config":normalized}

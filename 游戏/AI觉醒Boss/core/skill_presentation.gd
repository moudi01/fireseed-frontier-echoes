extends RefCounted
## Model/rig/equipment contracts for visual actions. No campaign state or cast authority.
static var cache={}
static func profiles() -> Dictionary:
	if cache.is_empty():cache=JSON.parse_string(FileAccess.get_file_as_string("res://data/animation_profiles.json")).models
	return cache
static func player(model: Node) -> AnimationPlayer:
	var found=model.find_children("*","AnimationPlayer",true,false);return found[0] if not found.is_empty() else null
static func prepare(model: Node,id: String) -> Array:
	var issues=[];var profile=profiles().get(id,{})
	if profile.is_empty():issues.append("未登记模型 "+id)
	else:
		if model.scene_file_path!=profile.scene_path:issues.append("资产路径与配置不符")
		var found=model.find_children("*","Skeleton3D",true,false)
		if found.size()!=1:issues.append("需要唯一骨架")
		else:
			var skeleton=found[0]
			if skeleton.get_bone_count()!=profile.rig.size():issues.append("骨骼数量不符")
			else:
				for i in range(profile.rig.size()):
					var expected=profile.rig[i];var t=skeleton.get_bone_rest(i);var values=[]
					for v in [t.basis.x,t.basis.y,t.basis.z,t.origin]:values.append_array([v.x,v.y,v.z])
					if str(skeleton.get_bone_name(i))!=expected.name or skeleton.get_bone_parent(i)!=int(expected.parent):issues.append("骨骼层级不符："+str(i));break
					for j in range(12):
						if absf(float(values[j])-float(expected.rest[j]))>.001:issues.append("绑定姿态不符："+expected.name);break
		var p=player(model)
		if found.size()==1:
			for spec in profile.skills.values():
				for bone in spec.bones:
					if found[0].find_bone(bone)<0:issues.append("缺少技能骨骼："+bone)
		if p==null:issues.append("没有动画播放器")
		else:
			for spec in profile.skills.values():
				for clip in spec.phases.values():
					if not p.has_animation(clip):issues.append("缺少片段："+clip)
				for phase in spec.get("loops",[]):
					var clip=spec.phases.get(phase,"")
					if p.has_animation(clip):p.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
	model.set_meta("action_profile",id);model.set_meta("action_issues",issues)
	return issues
static func supported(model: Node,skill: String,role: String) -> bool:
	if not model.has_meta("action_profile") or not model.get_meta("action_issues",["未检查"]).is_empty():return false
	var spec=profiles()[model.get_meta("action_profile")].skills.get(skill,{})
	if spec.is_empty() or role not in spec.roles:return false
	for pattern in spec.gear:
		if not model.find_children(pattern,"Node3D",true,false).any(func(n):return n.visible):return false
	return true
static func action(model: Node,skill: String,phase: String,role: String) -> Dictionary:
	if not supported(model,skill,role):return {}
	var spec=profiles()[model.get_meta("action_profile")].skills[skill]
	return {"clip":spec.phases.get(phase,""),"hold_at":float(spec.hold_at),"skill":skill,"phase":phase}
static func resolve(model: Node,unit: Dictionary,events: Array,base: String) -> Dictionary:
	var role=str(unit.unit_type);var chosen={"clip":base,"hold_at":-1.0,"rate":1.0,"hold":false,"one_shot":base in ["BowRelease","Right_Hand_Sword_Slash","Hit_Reaction","dying_backwards"]}
	if unit.get("alive",true):
		if role=="archer" and base in ["BowReady","BowRelease"]:
			var cast=action(model,"bow_shot","release" if base=="BowRelease" else "ready",role)
			if cast.is_empty():chosen.clip="Idle"
		if int(unit.get("charge_ticks_left",0))>0:
			var cast=action(model,"telegraphed_strike","windup",role)
			chosen.merge(cast,true);chosen.hold=true;chosen.rate=1;chosen.one_shot=false
			if cast.is_empty():chosen.clip="Idle"
		elif events.any(func(e):return e.get("actor")==unit.instance_id and e.get("attack_type")=="charged_strike" and e.action in ["attack","cancelled"]):
			var cast=action(model,"telegraphed_strike","release",role);chosen.merge(cast,true);chosen.one_shot=true
			if cast.is_empty():chosen.clip="Idle"
		elif role=="lorne" and (unit.get("is_winding",false) or (int(unit.get("shield_pool",0))>0 and base in ["Idle","Right_Hand_Sword_Slash","Armature|walking_man|baselayer"])):
			var phase="windup" if unit.get("is_winding",false) else ("guard_attack" if base=="Right_Hand_Sword_Slash" else ("guard_move" if base=="Armature|walking_man|baselayer" else "guard"))
			var cast=action(model,"shield_wall",phase,role);chosen.merge(cast,true)
			chosen.hold=phase=="guard";chosen.rate=float(cast.get("hold_at",.5))/.5 if phase=="windup" else 1.0;chosen.one_shot=phase=="guard_attack"
			if cast.is_empty():chosen.clip="Idle"
	var p=player(model)
	if p==null or not p.has_animation(chosen.clip):chosen.clip="Idle" if p!=null and p.has_animation("Idle") else ""
	return chosen

extends RefCounted
## Offline-measured visual cues, guarded by this model's existing action contract.
## The cylinder proxy is an authoring aid, never a hurtbox or damage authority.
static var data={}
const FIT=preload("res://core/shield_attack_fit.gd")
const ASSAULT=preload("res://core/assault_attack_fit.gd")
static func apply_assault(model:Node,enabled:bool)->Dictionary:
	if model.get_meta("action_profile","")!="infantry":return {}
	var player=FIT.SKILL.player(model)
	if player==null:return {}
	if enabled and not model.has_meta("assault_original_clips"):
		var originals={}
		for clip in ASSAULT.CLIPS:
			if not player.has_animation(clip):return {}
			originals[clip]=player.get_animation(clip)
		var initial=playback(player);var result=ASSAULT.fit(model)
		if not result.get("valid",false):return result
		var fitted={}
		for clip in ASSAULT.CLIPS:fitted[clip]=player.get_animation(clip)
		model.set_meta("assault_original_clips",originals);model.set_meta("assault_fitted_clips",fitted)
		if not initial.clip.is_empty():
			player.play(initial.clip);player.seek(initial.time,true)
			if not initial.playing:player.pause()
	if not model.has_meta("assault_original_clips"):return {}
	var desired=model.get_meta("assault_fitted_clips") if enabled else model.get_meta("assault_original_clips")
	if ASSAULT.CLIPS.any(func(clip):return player.get_animation(clip)!=desired[clip]):
		var saved=playback(player);var library=player.get_animation_library("").duplicate()
		for clip in ASSAULT.CLIPS:library.remove_animation(clip);library.add_animation(clip,desired[clip])
		player.stop();player.remove_animation_library("");player.add_animation_library("",library)
		if not saved.clip.is_empty():
			player.play(saved.clip);player.seek(saved.time,true)
			if not saved.playing:player.pause()
	model.set_meta("assault_attack_fit",enabled)
	return model.get_meta("assault_attack_fit_043",{})
static func playback(player:AnimationPlayer)->Dictionary:
	# current_animation is empty while paused. Reassigning the same clip resumes
	# its retained time; a stopped player starts safely at zero before querying.
	var clip=player.assigned_animation;var playing=player.is_playing();var time=0.0
	if not clip.is_empty():
		player.play(clip);time=player.current_animation_position
		if not playing:player.pause()
	return {"clip":clip,"time":time,"playing":playing}
static func apply_pose(model:Node,enabled:bool)->Dictionary:
	var players=model.find_children("*","AnimationPlayer",true,false)
	if players.is_empty():return {}
	var player=players[0]
	if enabled and not model.has_meta("melee_original_attack"):
		if not player.has_animation("ShieldAttack"):return {}
		var original=player.get_animation("ShieldAttack")
		var initial=playback(player)
		var result=FIT.fit(model)
		if not result.get("valid",false):return result
		model.set_meta("melee_original_attack",original);model.set_meta("melee_fitted_attack",player.get_animation("ShieldAttack"))
		if not initial.clip.is_empty():
			player.play(initial.clip);player.seek(initial.time,true)
			if not initial.playing:player.pause()
	if not model.has_meta("melee_original_attack"):return {}
	var desired=model.get_meta("melee_fitted_attack") if enabled else model.get_meta("melee_original_attack")
	if player.get_animation("ShieldAttack")!=desired:
		var saved=playback(player)
		var library=player.get_animation_library("").duplicate();library.remove_animation("ShieldAttack");library.add_animation("ShieldAttack",desired)
		player.stop();player.remove_animation_library("");player.add_animation_library("",library)
		if not saved.clip.is_empty():
			player.play(saved.clip);player.seek(saved.time,true)
			if not saved.playing:player.pause()
	model.set_meta("shield_attack_fit",enabled)
	return model.get_meta("shield_attack_fit_042",{})
static func profiles()->Dictionary:
	if data.is_empty():data=JSON.parse_string(FileAccess.get_file_as_string("res://data/melee_contacts.json")).models
	return data
static func cue(model:Node,clip:String,rate:float,probe)->Dictionary:
	var id=str(model.get_meta("action_profile",""))
	var result={"valid":false,"source":"fallback_041","clip":clip,"at":.18,"local_time":.18*rate,"model":id}
	if not model.get_meta("action_issues",["unchecked"]).is_empty() or probe==null:return result
	if not probe.sample().get("valid",false):return result
	var record=profiles().get(id,{}).get("clips",{}).get(clip,{})
	if record.is_empty() or not is_finite(rate) or rate<=0:return result
	if record.get("requires_fitted_right_arm",false) and not model.get_meta("shield_attack_fit",false):return result
	var player=model.find_children("*","AnimationPlayer",true,false)
	if player.is_empty() or not player[0].has_animation(clip):return result
	var length=player[0].get_animation(clip).length
	if absf(length-float(record.length))>.0001:return result
	var phase=float(record.phase)
	if record.get("requires_assault_fit",false) and not model.get_meta("assault_attack_fit",false):phase=float(record.get("baseline_phase_042",.18/.46))
	var local_time=phase*length;var at=local_time/rate
	if not is_finite(at) or at<.03 or at>.42:return result
	return {"valid":true,"source":"measured_blade_proxy","clip":clip,"at":at,"local_time":local_time,"model":id}

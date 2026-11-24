extends Node
## Headless maintenance probe, compiled into the actual release PCK.
## No project/source path, screenshots, native input or frame_post_draw.
var app
var checks=[]
var failures=[]
var serial=0
var version_guard_cases=0
var candidate=""
func start(host,mode,output):
	app=host
	call_deferred("run",mode,output)
func check(value,label):
	checks.append(label)
	if not value:failures.append(label);push_error(label)
func act(kind,payload={}):
	serial+=1
	check(app.send(kind,payload,"-package-probe-%d"%serial),"release main command "+kind)
func result_fixture(version):
	var engine=app.engine;var state=engine.initial(42)
	if version==1:state.erase("settlement_rules_version")
	var outcome=engine.apply(state,{"id":"fixture-depart","kind":"DEPART","payload":{"route":"tutorial","deployment":[{"instance_id":1,"x":3,"y":2,"stance":"attack"},{"instance_id":3,"x":5,"y":2,"stance":"attack"}]}})
	check(outcome.ok,"release rules configure explicit transport fixture")
	state=outcome.state
	var b=engine.CORE.new();b.configure(state.pending.battle_input,engine.units,engine.rules)
	b.finished=true;b.tick=10;b.result_tick=10;b.result="player_win"
	for u in b.states:
		u.alive=u.side=="player" and u.instance_id==3
		u.hp=int(engine.units[u.unit_type].hp) if u.alive else 0;u.downed_tick=null if u.alive else 10
	state.phase="settlement";state.battle_snapshot=b.snapshot();state.battle_result=b.summary()
	check(engine.valid_state(state),"explicit transport fixture validates with packaged code")
	return state
func file_hashes(path):
	var result={};var directory=DirAccess.open(path)
	if directory==null:return result
	for name in directory.get_files():result[name]=FileAccess.get_sha256(path.path_join(name))
	for name in directory.get_directories():
		for relative in file_hashes(path.path_join(name)):result[name+"/"+relative]=FileAccess.get_sha256(path.path_join(name).path_join(relative))
	return result
func save_envelope(state):
	var payload=JSON.stringify(state,"",true)
	return {"magic":"AI_BOSS_SAVE","version":1,"revision":state.revision,"payload_json":payload,"sha256":payload.sha256_text()}
func guard_case(root,placement,scope,value,missing=false,newer=false):
	version_guard_cases+=1
	var path=root.path_join("guard_%03d"%version_guard_cases)
	var store=app.store.get_script().new(app.engine)
	check(store.open(path),"release guard isolated store opens")
	for kind in ["NEW_GAME","ACK_SCENE"]:
		var payload={"scene_id":"gate_intro","choice":"continue"} if kind=="ACK_SCENE" else {}
		check(store.dispatch({"id":kind,"kind":kind,"payload":payload,"expected_revision":int(store.state.get("revision",0))}).ok,"release guard commits valid "+kind)
	var state=store.state.duplicate(true);state.revision=3 if newer else 1
	var envelope=save_envelope(state)
	if scope=="envelope":
		if missing:envelope.erase("version")
		else:envelope.version=value
	else:
		var field="schema_version" if scope=="schema" else "settlement_rules_version"
		if missing:state.erase(field)
		else:state[field]=value
		envelope=save_envelope(state)
	var targets=[path.path_join("latest.save"),path.path_join("recovery.save")] if newer else [path.path_join("journal/entry_00000001.save/record.save") if placement=="journal" else path.path_join(placement+".save")]
	for target in targets:
		var file=FileAccess.open(target,FileAccess.WRITE);file.store_string(JSON.stringify(envelope));file.close()
	var before=file_hashes(path);var reopened=app.store.get_script().new(app.engine)
	check(not reopened.open(path),"release malformed/unknown version refuses all fallback")
	check(reopened.load_blocked and reopened.state.is_empty() and reopened.error.contains("不支持"),"release rejection leaves no usable state")
	for kind in ["NEW_GAME","DEPART"]:
		var payload={"route":"tutorial","deployment":[{"instance_id":1,"x":4,"y":2,"stance":"defend"},{"instance_id":3,"x":4,"y":0,"stance":"defend"}]} if kind=="DEPART" else {}
		check(not reopened.dispatch({"id":"blocked-"+kind,"kind":kind,"payload":payload,"expected_revision":int(reopened.state.get("revision",0))}).ok,"release rejection blocks "+kind)
	check(file_hashes(path)==before,"release rejection preserves every journal/mirror byte")
func version_guards(root):
	for placement in ["journal","latest","recovery"]:
		for scope in ["envelope","schema","settlement"]:
			for value in [3,null,[],{},true,"2"]:guard_case(root,placement,scope,value)
			if scope!="settlement":guard_case(root,placement,scope,null,true)
	for scope in ["envelope","schema"]:guard_case(root,"latest",scope,"2",false,true)
func run(mode,output):
	candidate=str(ProjectSettings.get_setting("application/config/candidate_label",""))
	check(DisplayServer.get_name()=="headless" and not OS.has_feature("editor"),"actual release binary runs headless, not editor/source tests")
	check(str(ProjectSettings.get_setting("application/config/candidate_label",""))in ["052","053"],"packaged project identifies known candidate")
	await get_tree().process_frame
	check(app.ready_to_play,"packaged main scene opens isolated store")
	var initial_hash="";var save=app.store.root.path_join("latest.save")
	if mode=="fresh":
		check(app.store.state.is_empty(),"fresh package launch starts without a save")
		app.commands_ui.new.pressed.emit()
		await get_tree().process_frame;await get_tree().process_frame
		app.dismiss_story()
		await get_tree().process_frame;await get_tree().process_frame
		check(app.store.state.get("settlement_rules_version")==2,"normal packaged new-game control persists settlementv2")
		check(app.headline.text.contains("候选"+candidate) and app.headline.text.contains("伤兵返程v2"),"actual packaged HUD labels candidate and new rules")
		act("DEPART",{"route":"tutorial_trail","tutorial_version":2,"deployment":[{"instance_id":1,"x":3,"y":1,"stance":"attack"},{"instance_id":3,"x":3,"y":0,"stance":"defend"}],"focus":true,"focus_target":10002})
		for i in range(121):
			if app.store.state.phase!="battle":break
			act("ADVANCE_BATTLE")
		check(app.engine.wounded(app.store.state)==[1],"release natural battle creates one actual casualty")
		act("JOURNEY_CHOICE",{"node":"caravan","choice":"return"})
		app.refresh()
		await get_tree().process_frame;await get_tree().process_frame
		if app.route_map.visible:app.enter_route_node()
		check(not app.commands_ui.has("suggest_discard") and app.settlement_payload().is_empty(),"releasev2 return UI has no client discard/abandonment selection")
		app.commands_ui.settle.pressed.emit()
		await get_tree().process_frame;await get_tree().process_frame
		check(app.store.state.phase=="town" and app.store.state.roster["1"].status=="RECOVERING","releasev2 actual UI commit returns casualty")
		check(app.store.state.resources.recruit_token==0 and app.store.state.resources.crystals==0,"release early return gives no uncompleted objective loot")
		var checkpoint=app.store.state.duplicate(true);var hash=FileAccess.get_sha256(save)
		var reopened=app.store.get_script().new(app.engine)
		check(reopened.open(app.store.root) and reopened.state==checkpoint and FileAccess.get_sha256(save)==hash,"release savedv2 reload is exact and does not re-award")
	else:
		initial_hash=FileAccess.get_sha256(save)
		check(not app.store.state.is_empty() and not app.store.state.has("settlement_rules_version") and app.engine.settlement_version(app.store.state)==1,"packaged main loads genuine controlled unversioned fixture asv1")
		check(app.headline.text.contains("候选"+candidate) and app.headline.text.contains("伤兵返程v1"),"loaded old fixture HUD clearly labelsv1")
	# Identical controlled results must differ only by settlement version, using release resources.
	for version in [1,2]:
		var state=result_fixture(version);var engine=app.engine
		var no_fee=engine.apply(state,{"id":"probe-no-fee","kind":"SETTLE","payload":{"bring_ids":[]}})
		check(no_fee.ok,"packaged SETTLE accepts valid selected/default result")
		check(no_fee.state.roster["1"].status==("CAPTURED" if version==1 else "RECOVERING"),"release rule split preservesv1 choice and derivesv2 casualty")
		var keep=engine.apply(state,{"id":"probe-keep","kind":"SETTLE","payload":{"bring_ids":[1]}})
		check(keep.ok==(version==2),"releasev1 requires old cost, v2 returns without it")
		var discard=engine.apply(state,{"id":"probe-discard","kind":"SETTLE","payload":{"bring_ids":[1],"discard":{"recruit_token":1}}})
		check(discard.ok==(version==1),"releasev1 accepts original indivisible cost, v2 rejects obsolete discard")
		if version==2:check(keep.state.resources.recruit_token==1 and keep.state.resources.crystals==40,"releasev2 victory retains unchanged full loot")
		else:check(discard.state.resources.recruit_token==0 and discard.state.resources.crystals==40,"releasev1 outcome retains old inventory semantics")
	if mode!="fresh":check(FileAccess.get_sha256(save)==initial_hash,"controlled old checkpoint bytes untouched by package loading/pure probes")
	if candidate=="053":version_guards(output.get_base_dir())
	var result={"version_guard_cases":version_guard_cases,"passed":failures.is_empty(),"case":mode,"checks":checks.size(),"labels":checks,"failures":failures,"executable":OS.get_executable_path(),"candidate_label":str(ProjectSettings.get_setting("application/config/candidate_label","")),"loaded_settlement_version":app.engine.settlement_version(app.store.state),"data_dir":app.store.root,"scope":"actual exported release EXE/PCK; no source-project path; headless controls/store and controlled pure rule probes; visual/audio/native input unverified"}
	var f=FileAccess.open(output,FileAccess.WRITE);f.store_string(JSON.stringify(result,"  "));f.close();print(JSON.stringify(result))
	# Let Control/SystemFont resources leave the tree before the release text server shuts down.
	# Immediate quit with live/deferred Controls can otherwise report null font data on shutdown.
	var tree=get_tree();app.remove_child(self);tree.root.add_child(self)
	app.queue_free();app=null
	await tree.process_frame;await tree.process_frame
	tree.quit(0 if failures.is_empty() else 1)

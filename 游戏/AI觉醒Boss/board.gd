extends Node3D
const SKILL=preload("res://core/skill_presentation.gd")
const BOW=preload("res://core/bow_attachment.gd")
const FACING=preload("res://core/facing_presentation.gd")
const ALIGNMENT=preload("res://core/contact_alignment.gd")
const POSE=preload("res://core/pose_transition.gd")
const SHIELD_VISUAL=preload("res://core/shield_visual.gd")
const CONTACT=preload("res://core/contact_timeline.gd")
const CONTACT_EFFECT=preload("res://core/contact_effect.gd")
const MELEE=preload("res://core/melee_contact.gd")
const MELEE_CUES=preload("res://core/melee_presentation.gd")
const UNIT_LABELS=preload("res://core/unit_labels.gd")
var label_manager
var unit_label_nodes={}
var label_layout_report=[]
var label_layout_enabled=true
var label_focus_id=-1
var melee_enabled=true
var assault_enabled=true
var contact=CONTACT.new()
var contact_enabled=true
var contact_alignment_enabled=true
var contact_trace=[]
var contact_context={}
var contact_audio={}
var contact_totals={}
var contact_labels={}
var shield_visuals_enabled=true
var pose_smoothing_enabled=true
const FOOT=preload("res://core/foot_plant.gd")
var foot_planting_enabled=true
const BOSS=preload("res://core/boss_actor.gd")
const STAGE=preload("res://core/stage_set.gd")
const BOUNDS=preload("res://core/asset_bounds.gd")
const PRESENT=preload("res://core/character_presentation.gd")
const GROUND=preload("res://core/battle_ground.gd")
const ART=preload("res://core/forest_art.gd")
const FEEDBACK=preload("res://core/combat_feedback.gd")
signal inspected(ids)
var figures={}
var camera: Camera3D
var font=SystemFont.new()
var templates={}
var stats={}
var last_tick=-1
var selected_ids=[]
var effects=Node3D.new()
var feedback=Node3D.new()
var sound=FEEDBACK.new()
var stage_set=STAGE.new()
var ground=GROUND.new()
var visual_speed=1.0
var visual_paused=true
var location_key=""
var boundary_stage=""
var grid_lines=Node3D.new()
var surface=MeshInstance3D.new()
var health_limits={}
var instance_health={}
var display_names={}
func _ready():
	font.font_names=PackedStringArray(["Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC"])
	label_manager=UNIT_LABELS.new();add_child(label_manager);label_manager.configure(self);label_manager.enabled=label_layout_enabled;unit_label_nodes=label_manager.nodes
	add_child(effects);add_child(stage_set);add_child(feedback);add_child(sound)
	add_child(ground)
	var world=WorldEnvironment.new();world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color("606e69")
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color=Color("c5d2d6");world.environment.ambient_light_energy=0.55
	# Reflection lighting gives bare iron a broad environment response rather than black chrome.
	var sky_material=ProceduralSkyMaterial.new();sky_material.sky_top_color=Color("8e9eaa");sky_material.sky_horizon_color=Color("c4c8b7");sky_material.ground_bottom_color=Color("77735e");sky_material.ground_horizon_color=Color("a7aa94")
	var sky=Sky.new();sky.sky_material=sky_material;world.environment.sky=sky;world.environment.reflected_light_source=Environment.REFLECTION_SOURCE_SKY
	add_child(world)
	var light=DirectionalLight3D.new();light.rotation_degrees=Vector3(-48,-35,0);light.light_color=Color("fff5e7");light.light_energy=.9;light.shadow_enabled=true;add_child(light)
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=11.6
	camera.position=Vector3(11,14,17);add_child(camera);camera.look_at(Vector3(2.8,0.3,-1.8));camera.current=true
	health_limits=JSON.parse_string(FileAccess.get_file_as_string("res://data/units.json"))
	var floor_mesh=PlaneMesh.new();floor_mesh.size=Vector2(10.6,8.6);surface.mesh=floor_mesh;surface.position.y=-.04;surface.material_override=ART.earth("b9b1a1",1.2);add_child(surface)
	add_child(grid_lines)
	for x in range(11):grid_line(Vector3(float(x)-5,.002,0),Vector3(.013,.008,8))
	for y in range(9):grid_line(Vector3(0,.002,float(y)-4),Vector3(10,.008,.013))
	for type in ["infantry","shield","archer"]:
		var model=load(str(SKILL.profiles()[type].asset)).instantiate()
		SKILL.prepare(model,type)
		if type=="shield" and melee_enabled and contact_enabled:
			add_child(model);MELEE_CUES.apply_pose(model,true);remove_child(model)
		if type=="infantry" and assault_enabled and melee_enabled and contact_enabled:
			add_child(model);MELEE_CUES.apply_assault(model,true);remove_child(model)
		if type=="archer":BOW.prepare(model)
		ART.prepare_character(model)
		var bounds=BOUNDS.measure(model);var box: AABB=bounds.bounds;var factor=1.3/box.size.y
		model.scale*=factor;model.position=Vector3(-box.get_center().x,-box.position.y,-box.get_center().z)*factor
		templates[type]=model
func set_context(value: String):
	if not value.begins_with("boundary_"):boundary_stage=""
	ground.visible=value!="memory" and not value.begins_with("boundary_")
	surface.visible=ground.visible
	surface.material_override=ART.earth("b9b1a1",1.2) if ground.visible else ART.mat("626765")
	stage_set.show_scene(value)
func grid_line(p: Vector3,size_value: Vector3):
	var line=MeshInstance3D.new();var mesh=BoxMesh.new();mesh.size=size_value;line.mesh=mesh;line.position=p;line.material_override=material(Color(.57,.64,.59,.22));line.material_override.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;grid_lines.add_child(line)
func set_grid_mode(value: String):
	grid_lines.visible=value!="off"
	for line in grid_lines.get_children():line.material_override.albedo_color=Color(.67,.75,.7,.38 if value=="deployment" else .15)
func begin_location(value: String):
	if location_key==value:return
	location_key=value;clear()
func show_boundary(units: Array,stage: String):
	var display=[];var at=0
	for unit in units:
		if unit.side!="player" or not unit.get("alive",true):continue
		var shown=unit.duplicate(true);shown.position=[1+at%7,(3 if stage in ["wall","observed"] and unit.alive else 2)-int(at/7)];display.append(shown);at+=1
	show_units(display);set_paused(true,1)
	for unit in display:
		if unit.alive:
			var figure=figures[int(unit.instance_id)];figure.player.play("Idle");figure.player.seek(.4,true);figure.player.pause()
	if not stage_set.has_node("BoundaryBoss"):
		var boss=BOSS.new();boss.name="BoundaryBoss";boss.position=position_at(4,7)+Vector3(0,.31,0);stage_set.add_child(boss)
		label(stage_set,"Boss",Color("e8c6a0"),2.35).position+=position_at(4,7)
	stage_set.get_node("BoundaryBoss").set_stage(stage,stage=="observed" and boundary_stage!="wall")
	boundary_stage=stage
	if stage in ["wall","observed"]:
		for unit in display:
			if not unit.alive:continue
			var figure=figures[int(unit.instance_id)];PRESENT.apply_clip(figure.model,"ShieldWall");figure.player.play("ShieldWall");figure.player.seek(.7,true);figure.player.pause();break
func material(color: Color) -> StandardMaterial3D:
	var mat=StandardMaterial3D.new();mat.albedo_color=color;mat.roughness=.85;return mat
func position_at(x,y) -> Vector3:return Vector3(float(x)-4.5,0,3.5-float(y))
func clear():
	label_focus_id=-1
	if is_instance_valid(label_manager):label_manager.clear_nodes()
	contact.clear();contact_trace.clear();contact_context.clear();contact_audio.clear();contact_totals.clear();contact_labels.clear()
	for figure in figures.values():remove_child(figure.node);figure.node.queue_free()
	for effect in effects.get_children():effects.remove_child(effect);effect.queue_free()
	for effect in feedback.get_children():feedback.remove_child(effect);effect.queue_free()
	sound.stop()
	figures={};stats={};selected_ids=[];last_tick=-1
func label(parent: Node3D,text: String,color: Color,y: float) -> Label3D:
	var node=Label3D.new();node.text=text;node.font=font;node.font_size=36;node.pixel_size=.0045;node.outline_size=10;node.modulate=color;node.billboard=BaseMaterial3D.BILLBOARD_ENABLED;node.position.y=y;parent.add_child(node);return node
func rod(parent: Node3D,start: Vector3,end: Vector3,color: Color,radius=.012):
	var node=MeshInstance3D.new();var mesh=CylinderMesh.new();mesh.height=start.distance_to(end);mesh.top_radius=radius;mesh.bottom_radius=radius;mesh.radial_segments=6
	node.mesh=mesh;node.material_override=material(color);parent.add_child(node);node.position=(start+end)*.5;node.basis=Basis(Quaternion(Vector3.UP,(end-start).normalized()))
	return node
func make(unit: Dictionary):
	var node=Node3D.new();add_child(node)
	var model=templates["shield" if unit.unit_type in ["shield","lorne"] else ("archer" if unit.unit_type=="archer" else "infantry")].duplicate();node.add_child(model)
	if unit.unit_type=="lorne":node.scale=Vector3.ONE*1.12
	node.rotation.y=PI if unit.side=="player" else 0.0
	for equipment in model.find_children("Equipment_*","MeshInstance3D",true,false):
		if unit.unit_type=="archer" or (unit.unit_type=="cavalry" and str(equipment.name).contains("Shield")):equipment.visible=false
	if unit.unit_type=="archer":
		var bow=Node3D.new();bow.name="Equipment_Bow";node.add_child(bow)
		rod(bow,Vector3(0,-.42,0),Vector3(0,0,.14),Color("79542e"),.018);rod(bow,Vector3(0,0,.14),Vector3(0,.42,0),Color("79542e"),.018)
		var string_root=Node3D.new();string_root.name="BowString";bow.add_child(string_root)
		rod(string_root,Vector3(0,-.42,0),Vector3(0,0,-.2),Color("decda6"),.004)
		rod(string_root,Vector3(0,0,-.2),Vector3(0,.42,0),Color("decda6"),.004)
		var arrow=rod(bow,Vector3(0,0,-.20),Vector3(0,0,.33),Color("b5a17a"),.006);arrow.name="HeldArrow"
	var ring=MeshInstance3D.new();var mesh=TorusMesh.new();mesh.inner_radius=.28;mesh.outer_radius=.32;mesh.rings=24;mesh.ring_segments=6;ring.mesh=mesh;ring.position.y=.03;node.add_child(ring)
	var info=label(node,"",Color.WHITE,1.65)
	info.font_size=40;info.pixel_size=.0045;info.outline_size=7;info.no_depth_test=true
	var back=health_bar(node,Color("293735"));var fill=health_bar(node,Color("73aa9e"));fill.position.z=.002
	figures[int(unit.instance_id)]={"unit_type":unit.unit_type,"node":node,"model":model,"label":info,"ring":ring,"health_back":back,"health_fill":fill,"player":model.find_children("*","AnimationPlayer",true,false)[0],"clip":"","clip_rate":1.0,"death_elapsed":1.0,"base_scale":model.scale,"motion":1.0,"motion_from":Vector3.ZERO,"motion_to":Vector3.ZERO,"facing":node.rotation.y,"skill_hold_at":-1.0,"bow_grip":Basis.IDENTITY}
	var probe=MELEE.new();probe.prepare(model);figures[int(unit.instance_id)]["melee_probe"]=probe
	figures[int(unit.instance_id)]["melee_cue"]={}
	figures[int(unit.instance_id)]["motion_duration"]=.5
	figures[int(unit.instance_id)]["contact_alignment"]={}
	FACING.target(figures[int(unit.instance_id)],node.rotation.y,true)
	if unit.unit_type=="archer" and SKILL.supported(model,"bow_shot","archer"):
		var p=figures[int(unit.instance_id)].player;p.play("BowReady");p.seek(0,true);p.advance(0)
		var skeleton=model.find_children("*","Skeleton3D",true,false)[0];var hand=skeleton.find_bone("LeftHand")
		var hand_basis=(skeleton.global_transform*skeleton.get_bone_global_pose(hand)).basis.orthonormalized()
		figures[int(unit.instance_id)].bow_grip=hand_basis.inverse()*node.global_basis.orthonormalized()
	var skel=model.find_children("*","Skeleton3D",true,false)[0];var smoothing=POSE.new();skel.add_child(smoothing);smoothing.configure(figures[int(unit.instance_id)]);smoothing.enabled=pose_smoothing_enabled;figures[int(unit.instance_id)]["pose"]=smoothing
	var plant=FOOT.new();skel.add_child(plant);plant.configure(figures[int(unit.instance_id)]);plant.enabled=foot_planting_enabled;figures[int(unit.instance_id)]["plant"]=plant;plant.modification_processed.connect(_after_pose.bind(int(unit.instance_id)))
	var shield_fx=SHIELD_VISUAL.new();shield_fx.name="ShieldOutline";node.add_child(shield_fx);shield_fx.configure(figures[int(unit.instance_id)]);shield_fx.enabled=shield_visuals_enabled;figures[int(unit.instance_id)]["shield_fx"]=shield_fx
func set_label_layout(value:bool):
	label_layout_enabled=value
	if is_instance_valid(label_manager):label_manager.enabled=value;label_manager.refresh()
func set_label_reserved(rects:Array):
	if is_instance_valid(label_manager):label_manager.reserved=rects.duplicate()
func refresh_labels():
	if is_instance_valid(label_manager):label_manager.refresh()
func health_bar(parent: Node3D,color: Color) -> MeshInstance3D:
	var n=MeshInstance3D.new();var q=QuadMesh.new();q.size=Vector2(.62,.055);n.mesh=q;n.position.y=1.48;var m=material(color);m.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED;m.billboard_keep_scale=true;m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;m.no_depth_test=true;m.render_priority=1 if color!=Color("293735") else 0;n.material_override=m;n.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;parent.add_child(n);return n
func show_units(units: Array,events: Array=[],tick=0,focus_id=-1):
	label_focus_id=focus_id
	var fresh_tick=tick!=last_tick and last_tick>=0
	if tick!=last_tick:
		for child in feedback.get_children():feedback.remove_child(child);child.queue_free()
	for child in effects.get_children():effects.remove_child(child);child.queue_free()
	var current={}
	for unit in units:
		var id=int(unit.instance_id);current[id]=unit
		if figures.has(id) and figures[id].unit_type!=unit.unit_type:
			var old=figures[id].node;remove_child(old);old.queue_free();figures.erase(id)
		if not figures.has(id):make(unit)
	for id in figures.keys():
		if not current.has(id):
			var old=figures[id].node;remove_child(old);old.queue_free();figures.erase(id)
	# Plan from immutable rule snapshots. Visual clocks never feed back into CORE.
	var snap_contact=(visual_paused and tick!=last_tick) or last_tick<0 or (tick!=last_tick and tick!=last_tick+1)
	var rates={}
	for id in current:
		var actor=current[id];var f=figures[id]
		var attack_clip="BowRelease" if actor.unit_type=="archer" else "Right_Hand_Sword_Slash"
		var acting=actor.duplicate(true);acting.alive=true
		if contact_enabled:
			if tick!=last_tick:
				if not snap_contact:
					for event in events:
						if event.get("action")=="attack" and current.get(int(event.get("target",-1)),{}).get("side","")==actor.get("side","?"):acting.shield_pool=int(acting.get("shield_pool",0))+int(event.get("absorbed",0))
			else:acting.shield_pool=maxi(int(f.get("contact_pool_visual",acting.get("shield_pool",0))),1 if float(f.get("contact_pool_until",-1))>contact.age else 0)
		var action=SKILL.resolve(f.model,acting,events,attack_clip);attack_clip=action.clip
		var rate=f.player.get_animation(attack_clip).length/.46 if f.player.has_animation(attack_clip) else 1.0
		rates[id]={"clip_rate":rate}
		if melee_enabled and contact_enabled and actor.unit_type!="archer":
			var cue=MELEE_CUES.cue(f.model,attack_clip,rate,f.melee_probe)
			if tick!=last_tick:f.melee_cue=cue
			rates[id]["melee_contact_at"]=cue.at
	contact.enabled=contact_enabled
	contact.queue_tick(tick,events,current,stats,rates,snap_contact)
	var display_events=[] if contact_enabled and snap_contact else events
	if tick!=last_tick:contact_context=current.duplicate(true);contact_audio.clear();contact_totals.clear();contact_labels.clear()
	for id in current:
		var unit=current[id];var figure=figures[id];var pos=unit.get("position",[unit.get("x",0),unit.get("y",0)])
		var destination=position_at(pos[0],pos[1]);var authoritative_alive=unit.get("alive",true)
		var deferred=contact_enabled and float(contact.death_times.get(id,0.0))>contact.age+.000001
		var alive=authoritative_alive or deferred
		figure["contact_death_pending"]=deferred
		if contact_enabled and snap_contact and not authoritative_alive:figure.death_elapsed=1.0
		var shown_unit=unit.duplicate(true);shown_unit.alive=alive
		if tick!=last_tick:
			figure["contact_hp_start"]=int(stats.get(id,unit).get("hp",0)) if not snap_contact else int(unit.get("hp",0))
			figure["contact_stage_hp"]=contact_enabled and not snap_contact and events.any(func(e):return e.get("action")=="attack" and int(e.get("target",-1))==id and int(e.get("damage",0))>0)
			var waiting_absorption=0
			if contact_enabled and not snap_contact:
				for e in events:
					if e.get("action")=="attack" and current.get(int(e.get("target",-1)),{}).get("side","")==unit.get("side","?"):waiting_absorption+=int(e.get("absorbed",0))
			figure["contact_pool_visual"]=int(unit.get("shield_pool",0))+waiting_absorption;figure["contact_pool_until"]=-1.0
		if contact_enabled:shown_unit.shield_pool=maxi(int(figure.get("contact_pool_visual",unit.get("shield_pool",0))),1 if float(figure.get("contact_pool_until",-1))>contact.age else 0)
		if not visual_paused and tick!=last_tick and last_tick>=0 and stats.has(id) and alive and stats[id].get("alive",true) and figure.motion_to!=destination and (not contact_enabled or not snap_contact):
			figure.motion_from=figure.node.position;figure.motion_to=destination;figure.motion=0.0;figure.motion_duration=.5
		elif figure.motion_to!=destination or not alive or (visual_paused and tick!=last_tick) or (contact_enabled and snap_contact):
			figure.node.position=destination;figure.motion_to=destination;figure.motion=1.0;figure.motion_duration=.5
		if tick!=last_tick:
			var aligned=contact_alignment_enabled and contact_enabled and not snap_contact
			var window=ALIGNMENT.window(id,str(unit.unit_type),contact.pending,contact.age) if aligned else {"outgoing_at":-1.0,"incoming_at":-1.0,"turn_deadline":-1.0,"motion_deadline":-1.0}
			var retimed=ALIGNMENT.shorten_motion(figure,float(window.motion_deadline)) if aligned else false
			figure.contact_alignment=window;figure.contact_alignment["tick"]=tick;figure.contact_alignment["enabled"]=aligned;figure.contact_alignment["retimed"]=retimed;figure.contact_alignment["motion_duration"]=figure.motion_duration
			figure.contact_alignment["preaim_target"]=-1
		var color=Color("87b6ad") if unit.side=="player" else Color("c38e79")
		if not alive:color=Color("b5aba0")
		figure.ring.material_override=material(Color("ffd257") if id==focus_id and alive else (Color("6affdf") if unit.get("shield_pool",0)>0 and alive else color))
		var name={"shield":"盾","cavalry":"突","archer":"弓","lorne":"洛恩"}.get(unit.unit_type,"?")
		figure.label.text=str(unit.get("display_name",display_names.get(id,name))) if alive else "倒地"
		var visual_hp=int(unit.get("hp",0))
		if figure.get("contact_stage_hp",false):visual_hp=maxi(visual_hp,int(figure.contact_hp_start)-int(contact_totals.get(id,{}).get("damage",0)))
		if id in selected_ids:figure.label.text+=" · %d"%visual_hp
		var max_hp=float(unit.get("max_hp",instance_health.get(id,health_limits.get(unit.unit_type,{"hp":45}).hp)));var ratio=clampf(float(visual_hp)/maxf(1,max_hp),0,1)
		figure.health_back.visible=alive;figure.health_fill.visible=alive;figure.health_fill.scale.x=maxf(.01,ratio)
		figure.health_fill.material_override.albedo_color=Color("73aa9e") if unit.side=="player" else Color("ba7c66")
		if ratio<.35:figure.health_fill.material_override.albedo_color=Color("d4a15a")
		if alive and unit.side=="enemy" and unit.get("stance")=="defend":figure.label.text+=" · 守"
		figure.label.visible=units.size()<=16 or id==focus_id or id in selected_ids or not alive
		figure.label.modulate=Color("f2ead9") if alive else Color("b5b7a9");figure.label.position.y=1.65 if alive else .12
		# Bodies remain inspectable; shrink presentation footprint to keep occupied cells readable.
		var newly_down=not alive and fresh_tick and stats.has(id) and stats[id].get("alive",true) and (not contact_enabled or not snap_contact)
		if newly_down and not visual_paused:figure.death_elapsed=0.0
		if newly_down and contact_enabled and not visual_paused:contact_sound("down")
		figure.model.scale=figure.base_scale*(1.0 if alive else lerpf(1.0,.68,smoothstep(.28,.46,float(figure.death_elapsed))))
		if not alive:
			for other in current.values():
				if other.instance_id!=id and other.get("alive",true) and other.get("position",[])==pos:figure.node.position+=Vector3(.28,.01,.28);break
		if alive and unit.get("charge_ticks_left",0)>0:
			figure.ring.material_override=material(Color("ffb94c"));figure.label.text="精英 · 蓄力%d步"%int(unit.charge_ticks_left)
			var target=unit.charge_cell
			var origin=position_at(target[0],target[1]);var warning=Color("ed7148")
			for dx in [-.46,.46]:hazard_box(origin+Vector3(dx,.06,0),Vector3(.045,.035,.94),warning).set_meta("visual_owner",id)
			for dz in [-.46,.46]:hazard_box(origin+Vector3(0,.06,dz),Vector3(.94,.035,.045),warning).set_meta("visual_owner",id)
			var warning_label=label(effects,"重击 %d"%int(unit.charge_ticks_left),warning,.15);warning_label.position=origin+Vector3(0,.16,0);warning_label.set_meta("visual_owner",id)
		var clip=("BowReady" if unit.unit_type=="archer" else "Idle") if alive else "dying_backwards"
		if alive:
			for event in display_events:
				if event.get("actor")==id and event.action=="move":clip="Armature|walking_man|baselayer"
				elif event.get("actor")==id and event.action=="attack":clip="BowRelease" if unit.unit_type=="archer" else "Right_Hand_Sword_Slash"
				elif not contact_enabled and event.get("target")==id and event.action=="attack" and int(event.get("damage",0))>0 and clip in ["Idle","BowReady"]:clip="Hit_Reaction"
		if alive:
			for event in display_events:
				if event.get("actor")!=id:continue
				var origin=event.get("from",event.get("actor_pos",[]));var target=event.get("to",event.get("target_pos",[]))
				# A known cooldown target can be watched before the next release. This
				# consumes only confirmed positions, without choosing a new rule target.
				if contact_alignment_enabled and contact_enabled and event.get("action")=="wait" and target.is_empty():
					var watched=int(event.get("target",-1));var watched_unit=current.get(watched,{})
					if not watched_unit.is_empty() and watched_unit.get("alive",true):
						target=watched_unit.get("position",[watched_unit.get("x",0),watched_unit.get("y",0)])
						if origin.is_empty():origin=pos
						figure.contact_alignment["preaim_target"]=watched
				if target.is_empty() and event.get("attack_type","")=="charged_strike":target=event.get("target_cell",[])
				if origin.is_empty() and event.get("action") in ["attack","cancelled"]:origin=pos
				if origin.size()==2 and target.size()==2:
					var direction=position_at(target[0],target[1])-position_at(origin[0],origin[1])
					if direction.length_squared()>0:figure.facing=atan2(direction.x,direction.z)
		var action=SKILL.resolve(figure.model,shown_unit,display_events,clip);clip=action.clip
		PRESENT.apply_clip(figure.model,clip)
		var shield_events=events.filter(func(e):return e.get("action")!="attack") if contact_enabled else events
		figure.shield_fx.sync(shown_unit,shield_events,current,fresh_tick,snap_contact if contact_enabled else ((visual_paused and tick!=last_tick) or not stats.has(id)))
		if clip.is_empty():continue
		figure.clip_rate=float(action.rate)
		if clip in ["Armature|walking_man|baselayer","ShieldWalk"]:figure.clip_rate=figure.player.get_animation(clip).length/.5
		if action.one_shot:figure.clip_rate=figure.player.get_animation(clip).length/.46
		var previous_clip=figure.clip
		var neutral=POSE.is_neutral(clip,action,shown_unit)
		if clip!=figure.clip or not neutral or (visual_paused and tick!=last_tick):figure.pose.begin(neutral and alive and stats.has(id) and not (visual_paused and tick!=last_tick) and (not contact_enabled or not snap_contact))
		if clip!=figure.clip:
			figure.player.play(clip,0.0 if pose_smoothing_enabled and neutral else .07);figure.clip=clip
		elif tick!=last_tick and action.one_shot and clip!="dying_backwards":
			figure.player.seek(0,true);figure.player.play(clip,.08)
		figure.skill_hold_at=-1.0
		var charge_active=unit.get("charge_ticks_left",0)>0
		var shield_windup=unit.unit_type=="lorne" and unit.get("is_winding",false) and clip=="ShieldWall"
		if alive and (charge_active or shield_windup):
			figure.skill_hold_at=float(action.hold_at)
			var fresh_windup=fresh_tick and stats.has(id) and (int(stats[id].get("charge_ticks_left",0))==0 if charge_active else not stats[id].get("is_winding",false))
			if fresh_windup and previous_clip==clip:figure.player.play(clip);figure.player.seek(0,true)
			if figure.skill_hold_at>=0 and ((visual_paused and tick!=last_tick) or (contact_enabled and snap_contact) or (not fresh_windup and previous_clip!=clip)):
				figure.player.seek(figure.skill_hold_at,true);figure.player.pause()
			if charge_active:
				var direction=position_at(unit.charge_cell[0],unit.charge_cell[1])-destination
				if direction.length_squared()>0:figure.facing=atan2(direction.x,direction.z)
		elif bool(action.hold) and float(action.hold_at)>=0:
			figure.player.seek(float(action.hold_at),true);figure.player.pause()
		if not alive:
			if newly_down and not visual_paused:figure.player.seek(0,true)
			elif figure.death_elapsed>=.46:figure.player.seek(figure.player.get_animation(clip).length,true);figure.player.pause()
		var turn_deadline=float(figure.contact_alignment.get("turn_deadline",-1.0)) if tick!=last_tick else -1.0
		FACING.target(figure,figure.facing,snap_contact if contact_enabled else ((visual_paused and tick!=last_tick) or not stats.has(id)),not alive,bool(action.one_shot),turn_deadline)
		figure.player.speed_scale=0 if visual_paused else visual_speed*figure.clip_rate
		figure.player.advance(0)
		if unit.unit_type=="archer":update_bow(figure,alive)
	if fresh_tick and (not contact_enabled or not snap_contact):
		create_tick_feedback(events.filter(func(e):return e.get("action") not in ["attack","downed"]) if contact_enabled else events,current)
	stats=current.duplicate(true);last_tick=tick
func hazard_box(pos: Vector3,size: Vector3,color: Color):
	var n=MeshInstance3D.new();var mesh=BoxMesh.new();mesh.size=size;n.mesh=mesh;n.position=pos;n.material_override=material(color);effects.add_child(n)
	return n
func set_paused(paused: bool,speed: float):
	visual_paused=paused;visual_speed=speed
	for figure in figures.values():figure.player.speed_scale=0 if paused else speed*figure.clip_rate
	for voice in sound.voices:voice.stream_paused=paused
func set_contact_presentation(value:bool):
	contact_enabled=value;contact.set_enabled(value)
	for model in templates.values():
		if model.get_meta("action_profile","")=="shield":
			add_child(model);MELEE_CUES.apply_pose(model,value and melee_enabled);remove_child(model)
		if model.get_meta("action_profile","")=="infantry":
			add_child(model);MELEE_CUES.apply_assault(model,value and melee_enabled and assault_enabled);remove_child(model)
	for figure in figures.values():MELEE_CUES.apply_pose(figure.model,value and melee_enabled)
	for figure in figures.values():MELEE_CUES.apply_assault(figure.model,value and melee_enabled and assault_enabled)
	for effect in feedback.get_children():feedback.remove_child(effect);effect.queue_free()
	for id in figures:
		if figures[id].get("contact_death_pending",false):finish_contact_death(id,true)
func set_contact_alignment(value:bool):
	# Used by the isolated 043 comparison. Existing interpolation is not restarted.
	contact_alignment_enabled=value
func set_pose_smoothing(value:bool):
	pose_smoothing_enabled=value
	for figure in figures.values():figure.pose.enabled=value;figure.pose.reset()
func _after_pose(id:int):
	if not figures.has(id):return
	var figure=figures[id];figure.pose.remember()
	if figure.unit_type=="archer":update_bow(figure,figure.clip!="dying_backwards")
func set_shield_visuals(value:bool):
	shield_visuals_enabled=value
	for id in figures:
		var fx=figures[id].shield_fx;fx.enabled=value
		if stats.has(id):fx.sync(stats[id],[],stats,false,true)
func set_foot_planting(value:bool):
	foot_planting_enabled=value
	for figure in figures.values():figure.plant.enabled=value;figure.plant.anchors.clear()
func _process(delta: float):
	if visual_paused or not visible:return
	var seconds=delta*visual_speed
	# Advance existing effects first. New launches are aged only by time since due.
	for effect in feedback.get_children():
		if effect is CONTACT_EFFECT:
			effect.advance(seconds)
			if effect.finished:feedback.remove_child(effect);effect.queue_free()
	for figure in figures.values():
		figure.pose.advance(delta*visual_speed)
		figure.shield_fx.advance(delta*visual_speed)
		if figure.skill_hold_at>=0 and figure.player.current_animation_position>=figure.skill_hold_at:
			figure.player.seek(figure.skill_hold_at,true);figure.player.pause()
		if figure.clip=="dying_backwards" and figure.death_elapsed<.46:
			figure.death_elapsed=minf(.46,figure.death_elapsed+delta*visual_speed)
			figure.model.scale=figure.base_scale*lerpf(1.0,.68,smoothstep(.28,.46,float(figure.death_elapsed)))
			if figure.death_elapsed>=.46:figure.player.seek(figure.player.get_animation(figure.clip).length,true);figure.player.pause()
		if figure.motion<1.0:
			figure.motion=minf(1.0,figure.motion+delta*visual_speed/maxf(.001,float(figure.get("motion_duration",.5))))
			figure.node.position=figure.motion_from.lerp(figure.motion_to,figure.motion)
		FACING.advance(figure,delta*visual_speed)
		if figure.unit_type=="archer":update_bow(figure,figure.clip!="dying_backwards")
	if contact_enabled:
		for item in contact.advance(seconds):dispatch_contact(item)
		for id in figures:
			if figures[id].get("contact_death_pending",false) and contact.age+.000001>=float(contact.death_times.get(id,0.0)):finish_contact_death(id)
			var f=figures[id]
			if float(f.get("contact_pool_until",-1.0))>=0 and contact.age>=float(f.contact_pool_until):
				f.contact_pool_until=-1.0;f.shield_fx.sync(stats.get(id,{}),[],stats,false,true)
	for effect in feedback.get_children():
		if effect is CONTACT_EFFECT:continue
		var age=float(effect.get_meta("age",0))+delta*visual_speed;var duration=float(effect.get_meta("duration",.32));effect.set_meta("age",age)
		if effect is Label3D:effect.modulate.a=1.0-smoothstep(duration*.5,duration,age);effect.position.y+=delta*visual_speed*.35
		elif effect is MeshInstance3D:effect.visible=age<duration
		if age>=duration:feedback.remove_child(effect);effect.queue_free()

func update_bow(figure: Dictionary,alive: bool):
	var bow=figure.node.get_node_or_null("Equipment_Bow")
	if bow==null:return
	bow.visible=alive and SKILL.supported(figure.model,"bow_shot","archer")
	if not bow.visible:return
	var skeleton=figure.model.find_children("*","Skeleton3D",true,false)[0]
	var hand=skeleton.find_bone("LeftHand")
	var hand_world=skeleton.global_transform*skeleton.get_bone_global_pose(hand)
	bow.global_transform=Transform3D(hand_world.basis.orthonormalized()*figure.bow_grip,BOW.palm(figure.model,"Left"))
	var hand_nock=bow.to_local(BOW.palm(figure.model,"Right"));var nock=Vector3.ZERO;var t=figure.player.current_animation_position
	if figure.clip=="BowReady":nock=hand_nock;figure["ready_nock"]=hand_nock
	elif figure.clip=="BowRelease":
		if t<.05:nock=figure.get("ready_nock",hand_nock)*(1.0-smoothstep(0,.05,t))
		elif t>.22:nock=hand_nock*smoothstep(.22,.42,t)
	figure["bow_nock"]=nock
	var parts=bow.get_node("BowString").get_children()
	var segments=[[Vector3(0,-.42,0),nock],[nock,Vector3(0,.42,0)]]
	for i in range(2):
		var a=segments[i][0];var b=segments[i][1];parts[i].mesh.height=a.distance_to(b);parts[i].position=(a+b)*.5;parts[i].basis=Basis(Quaternion(Vector3.UP,(b-a).normalized()))
	var arrow=bow.get_node("HeldArrow");arrow.visible=figure.clip=="BowReady" or (figure.clip=="BowRelease" and (t<.03 or t>.28))
	var aim=(-figure.get("ready_nock",Vector3(0,0,-.25))).normalized();var a=nock;var b=nock+aim*.65
	arrow.mesh.height=.65;arrow.position=(a+b)*.5;arrow.basis=Basis(Quaternion(Vector3.UP,aim))

func pop_text(text: String,p: Vector3,color: Color):
	var n=label(feedback,text,color,0);n.position=p;n.font_size=38;n.pixel_size=.004;n.outline_size=4;n.no_depth_test=true;n.set_meta("duration",.38);n.set_meta("age",0.0)
	return n

func contact_sound(kind:String):
	if visual_paused or not visible or int(contact_audio.get(kind,0))>=2:return
	sound.play_kind(kind);contact_audio[kind]=int(contact_audio.get(kind,0))+1

func contact_point(event:Dictionary) -> Vector3:
	var cell=event.get("target_pos",event.get("target_cell",[]))
	if cell.size()!=2:cell=contact_context.get(int(event.get("target",-1)),{}).get("position",[])
	return position_at(cell[0],cell[1]) if cell.size()==2 else Vector3.ZERO

func add_contact_effect(spec:Dictionary,elapsed=0.0):
	if feedback.get_child_count()>=48:return null
	var effect=CONTACT_EFFECT.new();feedback.add_child(effect);effect.configure(spec);effect.advance(maxf(0,elapsed))
	return effect

func dispatch_contact(item:Dictionary):
	var event:Dictionary=item.event;var actor=int(event.get("actor",-1));var target=int(event.get("target",-1));var lag=maxf(0,contact.age-float(item.at))
	contact_trace.append({"tick":last_tick,"key":item.key,"kind":item.kind,"at":item.at,"age":contact.age,"actor":actor,"target":target})
	if figures.has(actor):
		var f=figures[actor];var p=f.node.position
		contact_trace[-1]["actor_turn_error"]=absf(wrapf(float(f.facing)-float(f.node.rotation.y),-PI,PI));contact_trace[-1]["actor_position"]=[p.x,p.y,p.z]
	if figures.has(target):
		var p=figures[target].node.position
		contact_trace[-1]["target_position"]=[p.x,p.y,p.z];contact_trace[-1]["target_cell_error"]=p.distance_to(contact_point(event))
	if melee_enabled and figures.has(actor) and figures[actor].unit_type!="archer":contact_trace[-1]["melee_cue"]=figures[actor].get("melee_cue",{}).duplicate(true)
	if item.kind=="release":
		if not figures.has(actor):return
		var figure=figures[actor];var bow=figure.node.get_node_or_null("Equipment_Bow")
		if bow==null or not bow.is_visible_in_tree():return
		var nock=figure.get("bow_nock",Vector3.ZERO);var aim=(-figure.get("ready_nock",Vector3(0,0,-.25))).normalized()
		var start=to_local(bow.to_global(nock+aim*.65));var finish=contact_point(event)+Vector3(0,.8,0)
		var impact_at=float(item.at)+.16
		for future in contact.pending:
			if future.kind=="impact" and future.key.trim_suffix(":impact")==str(item.key).trim_suffix(":release"):impact_at=float(future.at);break
		# A long frame may dispatch release and impact together, so infer the same
		# fixed flight from the event when its impact is no longer in pending.
		var origin=event.get("actor_pos",contact_context.get(actor,{}).get("position",[]));var destination=event.get("target_pos",contact_context.get(target,{}).get("position",[]))
		if origin.size()==2 and destination.size()==2:impact_at=float(item.at)+clampf(.12+Vector2(origin[0],origin[1]).distance_to(Vector2(destination[0],destination[1]))*.02,.12,.20)
		add_contact_effect({"kind":"arrow","from":start,"to":finish,"owner":actor,"duration":impact_at-float(item.at)},lag)
		contact_sound("bow");contact_trace[-1]["from"]=[start.x,start.y,start.z];contact_trace[-1]["to"]=[finish.x,finish.y,finish.z]
	elif item.kind=="ground":
		add_contact_effect({"kind":"ground","to":contact_point(event),"owner":actor,"duration":.18},lag)
		contact_sound("hit")
		if feedback.get_child_count()<48:pop_text("落空",contact_point(event)+Vector3(0,.35,0),Color("d1b797")).set_meta("visual_owner",actor)
	else:
		if not figures.has(target):return
		var absorbed=int(event.get("absorbed",0));var damage=int(event.get("damage",0));var point=contact_point(event)+Vector3(0,.8,0)
		add_contact_effect({"kind":"hit","to":point,"owner":target,"duration":.12,"tint":Color("b8d7d7") if absorbed>0 else Color("f3d9a0")},lag)
		contact_sound("shield" if absorbed>0 else "hit")
		if not contact_totals.has(target):contact_totals[target]={"damage":0,"shield":0}
		contact_totals[target].damage+=damage;contact_totals[target].shield+=absorbed
		var total=contact_totals[target];var text="−%d"%int(total.damage) if total.damage>0 else ""
		var unit=contact_context.get(target,{});var display_hp=maxi(int(unit.get("hp",0)),int(figures[target].get("contact_hp_start",unit.get("hp",0)))-int(total.damage))
		var max_hp=float(unit.get("max_hp",instance_health.get(target,health_limits.get(unit.get("unit_type","shield"),{"hp":45}).hp)))
		var ratio=clampf(float(display_hp)/maxf(1,max_hp),0,1);figures[target].health_fill.scale.x=maxf(.01,ratio)
		figures[target].health_fill.material_override.albedo_color=Color("d4a15a") if ratio<.35 else (Color("73aa9e") if unit.get("side")=="player" else Color("ba7c66"))
		if target in selected_ids:
			var short_name={"shield":"盾","cavalry":"突","archer":"弓","lorne":"洛恩"}.get(unit.get("unit_type","shield"),"?")
			figures[target].label.text=str(unit.get("display_name",display_names.get(target,short_name)))+" · %d"%display_hp
			if unit.get("side")=="enemy" and unit.get("stance")=="defend":figures[target].label.text+=" · 守"
		if total.shield>0:text+=("  " if not text.is_empty() else "")+"盾%d"%int(total.shield)
		if not text.is_empty() and (feedback.get_child_count()<48 or (contact_labels.has(target) and is_instance_valid(contact_labels[target]) and contact_labels[target].is_inside_tree())):
			if not contact_labels.has(target) or not is_instance_valid(contact_labels[target]) or not contact_labels[target].is_inside_tree():
				contact_labels[target]=pop_text(text,point+Vector3(0,.35,0),Color("edc6a3") if total.damage>0 else Color("b8d7d7"));contact_labels[target].set_meta("visual_owner",target)
			else:contact_labels[target].text=text
		if absorbed>0:
			for id in figures:
				if contact_context.get(id,{}).get("side","")!=contact_context.get(target,{}).get("side","?"):continue
				var shown=contact_context[id].duplicate(true)
				if figures[id].get("contact_death_pending",false):shown.alive=true
				figures[id].contact_pool_visual=maxi(int(shown.get("shield_pool",0)),int(figures[id].get("contact_pool_visual",0))-absorbed)
				shown.shield_pool=figures[id].contact_pool_visual
				if int(shown.shield_pool)==0 and figures[id].shield_fx.valid:
					shown.shield_pool=1;figures[id].contact_pool_until=contact.age+.10
				figures[id].shield_fx.sync(shown,[event],contact_context,true,false)
		var victim=figures[target]
		if damage>0 and contact_context.get(target,{}).get("alive",true) and victim.clip in ["Idle","BowReady"]:
			victim.pose.begin(false);victim.clip="Hit_Reaction";PRESENT.apply_clip(victim.model,victim.clip);victim.player.play(victim.clip,.025);victim.clip_rate=victim.player.get_animation(victim.clip).length/.30;victim.player.speed_scale=visual_speed*victim.clip_rate

func finish_contact_death(id:int,snap=false):
	if not figures.has(id):return
	var figure=figures[id];figure["contact_death_pending"]=false;figure.pose.reset();figure.clip="dying_backwards";figure.skill_hold_at=-1.0
	figure.clip_rate=figure.player.get_animation(figure.clip).length/.46;figure.death_elapsed=1.0 if snap else 0.0
	PRESENT.apply_clip(figure.model,figure.clip);figure.player.play(figure.clip,0);figure.player.seek(figure.player.get_animation(figure.clip).length if snap else 0.0,true)
	figure.health_back.hide();figure.health_fill.hide();figure.label.text="倒地";figure.label.position.y=.12;figure.label.modulate=Color("b5b7a9")
	figure.ring.material_override=material(Color("b5aba0"))
	figure.player.speed_scale=0 if visual_paused or snap else visual_speed*figure.clip_rate
	if snap:figure.player.pause();figure.model.scale=figure.base_scale*.68
	figure.shield_fx.visible=false;figure.shield_fx.active_shield=false
	FACING.target(figure,figure.node.rotation.y,true,true)
	if figure.unit_type=="archer":update_bow(figure,false)
	if not snap:contact_sound("down")

func create_tick_feedback(events: Array,current: Dictionary):
	var totals={};var counts={};var visuals=0
	for event in events:
		var action=str(event.get("action",""));var kind=""
		if action=="attack":
			var target=int(event.target)
			if not totals.has(target):totals[target]={"damage":0,"shield":0}
			totals[target].damage+=int(event.damage);totals[target].shield+=int(event.get("absorbed",0))
			kind="bow" if current.get(int(event.actor),{}).get("unit_type","")=="archer" else ("shield" if int(event.get("absorbed",0))>0 else "hit")
			if kind=="bow" and not visual_paused and visible:
				var impact="shield" if int(event.get("absorbed",0))>0 else "hit"
				if int(counts.get(impact,0))<2:sound.play_kind(impact);counts[impact]=int(counts.get(impact,0))+1
			if kind=="bow" and visuals<6 and figures.has(target):
				var a=figures[int(event.actor)].node.position+Vector3(0,1,0);var b=figures[target].node.position+Vector3(0,.8,0)
				var trail=rod(feedback,a.lerp(b,.60),b,Color("d6c293"),.009);trail.set_meta("duration",.10);trail.set_meta("visual_owner",int(event.actor));visuals+=1
		elif action=="shield_formed":
			kind="formed";pop_text("盾墙 · %d"%int(event.shared_pool),figures[int(event.actor)].node.position+Vector3(0,1.25,0),Color("b8d7d7")).set_meta("visual_owner",int(event.actor))
		elif action in ["shield_windup","charge_windup"]:kind="windup"
		elif action=="downed":kind="down"
		if not kind.is_empty() and not visual_paused and visible and int(counts.get(kind,0))<2:
			sound.play_kind(kind);counts[kind]=int(counts.get(kind,0))+1
	for id in totals:
		if not figures.has(id) or visuals>=10:continue
		var total=totals[id];var text=("−%d"%int(total.damage)) if total.damage>0 else ""
		if total.shield>0:text+=("  " if not text.is_empty() else "")+"盾%d"%int(total.shield)
		if not text.is_empty():pop_text(text,figures[id].node.position+Vector3(0,1.15,0),Color("b8d7d7") if total.damage==0 else Color("edc6a3")).set_meta("visual_owner",id);visuals+=1
func _unhandled_input(event):
	if not visible:return
	if event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:camera.size=maxf(8,camera.size-.7)
		elif event.button_index==MOUSE_BUTTON_WHEEL_DOWN:camera.size=minf(19,camera.size+.7)
		elif event.button_index==MOUSE_BUTTON_LEFT:
			var plane=Plane(Vector3.UP,0);var origin=camera.project_ray_origin(event.position);var hit=plane.intersects_ray(origin,camera.project_ray_normal(event.position))
			if hit!=null:
				var x=roundi(hit.x+4.5);var y=roundi(3.5-hit.z);var ids=[]
				for id in stats:
					var p=stats[id].get("position",[stats[id].get("x"),stats[id].get("y")])
					if int(p[0])==x and int(p[1])==y:ids.append(id)
				inspected.emit(ids)
func _exit_tree():
	for template in templates.values():template.free()

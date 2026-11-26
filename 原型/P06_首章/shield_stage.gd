extends Control

signal geometry_ready

const Profiles = preload("res://actor_profiles.gd")
const Actor = Profiles.Actor
const Melee = Profiles.Melee
const Bow = Profiles.Bow
const Crossbow = Profiles.Crossbow
const Targeted = Profiles.Targeted
const Spear = Profiles.Spear
const Hero = Profiles.Hero
const Mimic = Profiles.Mimic
const DualSac = Profiles.DualSac
const Echo = Profiles.Echo
const Wasp = Profiles.Wasp
const RingGuard = Profiles.RingGuard
const SkeletonEnemy = Profiles.SkeletonEnemy
const Ado = Profiles.Ado
const Mg02 = Profiles.Mg02
const Mg03 = Profiles.Mg03
const Mg04 = Profiles.Mg04
const Demon = Profiles.Demon
const Admin = Profiles.Admin
const En02 = Profiles.En02
const GENERAL_CAST_MOVES := {
	"MG03": Mg03.MG03_MOVES, "MG04": Mg04.MG04_MOVES, "ADMIN": Admin.ADMIN_MOVES,
	"EN02": [En02.MOVE_ID], "EN15": [Profiles.En15Profile.PROFILE.move], "EN16": ["EN16-A"], "EN18": ["EN18-A"],
}
const MirrorCourtKit = preload("res://mirror_court_kit.gd")
const SaltCrossingKit = preload("res://salt_crossing_kit.gd")
const ForgeCrossingKit = preload("res://forge_crossing_kit.gd")
const CitadelRingKit = preload("res://citadel_ring_kit.gd")
const FortressKit = preload("res://fortress_kit.gd")
const MODEL_PATH := Profiles.SHIELD_MODEL
const ADO_PATH := Profiles.ADO_MODEL
const FORTRESS := Profiles.FORTRESS
const ADO_ASSET := Profiles.ADO_ASSET
const GRAY_OAK := "res://assets/gray_oak/"
const BONE_ARROW_NOSE := 0.22
const STING_NOSE := 0.16
const CONCURRENT_MODEL_LOADS := 4
const SIDE_PITCH := PI * 44.0 / 180.0
const SIDE_TURN := -PI / 3.0
const SIDE_UNIT_SCALE := 1.20
const MAP_UNIT_SCALE := 1.52
const FACINGS := [Vector2(1, 0), Vector2(0.5, 0.8660254), Vector2(-0.5, 0.8660254),
	Vector2(-1, 0), Vector2(-0.5, -0.8660254), Vector2(0.5, -0.8660254)]

var enabled := true
var show_spear := true
var reduced := false
var battle_id := ""
var actors: Dictionary = {}
var seen: Dictionary = {}
var audit := {"clips": {}, "contacts": 0, "absorptions": 0, "events": 0, "peak_models": 0,
	"melee_peak": 0, "melee_skill_releases": 0, "melee_skill_misses": 0,
	"bow_peak": 0, "bow_shots": {}, "bow_flights": 0, "bow_flight_meshes_created": 0,
	"aid_peak": 0, "aid_actions": {}, "aid_contacts": 0, "aid_flights": 0,
	"crossbow_peak": 0, "crossbow_shots": {}, "crossbow_flights": 0,
	"mist_peak": 0, "mist_casts": {}, "mist_delays": {}, "mist_flights": 0,
	"spear_peak": 0, "spear_windups": 0, "spear_releases": 0, "spear_hits": 0,
	"spear_misses": 0, "spear_cancels": 0, "spear_blocks": 0,
	"enemy_spear_peak": 0, "enemy_spear_windups": 0, "enemy_spear_releases": {},
	"enemy_spear_hits": 0, "enemy_spear_misses": 0, "enemy_spear_downs": 0,
	"mimic_peak": 0, "mimic_windups": 0, "mimic_releases": 0, "mimic_downs": 0,
	"mimic_prepared_before_battle": false,
	"echo_peak": 0, "echo_windups": 0, "echo_releases": {}, "echo_downs": 0,
	"wasp_peak": 0, "sting_windups": 0, "sting_releases": {}, "sting_flights": 0, "wasp_downs": 0,
	"ado_seen": false, "ado_phases": [], "ado_releases": 0, "ado_downs": 0,
	"ado_windups": {}, "ado_moves": {}, "ado_shields": 0, "ado_cues": [], "field_props": {},
	"sev_shots": {},
	"ado_prepared_before_battle": false, "viewport_resizes_in_battle": 0, "scenery_updates": 0,
	"bone_arrows": {}, "bone_arrow_flights": 0,
	"hero_peak": 0, "hero_kinds": {}, "hero_skills": {}}
var marks: Dictionary = {}
var ado_traces: Dictionary = {}
var cells: Dictionary = {}
var viewport_3d: SubViewport
var camera: Camera3D
var _ground_origin := Vector3.ZERO
var _ground_x := Vector3.ZERO
var _ground_y := Vector3.ZERO
var _ground_facings: Array[float] = []
var model: PackedScene
var actor_travels: Dictionary = {}
var aid_capsules: Dictionary = {}
var mist_visual: SphereMesh
var sting_visual: CylinderMesh
var bone_arrow_visual: CylinderMesh
var flying_projectiles: Array[MeshInstance3D] = []
var spare_projectiles: Array[MeshInstance3D] = []
var projectile_tweens: Dictionary = {}
var spear_model: PackedScene
var _optional_model_available: Dictionary = {}
var spear_warmed := false
var skeletons_warmed := false
var gray_oak_warmed := false
var mimic_warmed := false
var echo_warmed := false
var wasp_warmed := false
var scenery: Dictionary = {}
var _scenery_placements: Dictionary = {}
var _scenery_projection_dirty := true
var scene_assets: Dictionary = {}
var _scene_load_queue: Array[String] = []
var _scene_loads: Dictionary = {}
var _scenes_ready_to_present: Array[String] = []
var _actor_attachment_frames: Dictionary = {}
var _actor_attachment_pending := false
var profile_assets := false
var asset_load_timings: Array[Dictionary] = []
var model_dispatch_timings: Array[Dictionary] = []
var actor_attachment_timings: Array[Dictionary] = []
var contact_timings: Array[Dictionary] = []
var travel_library: AnimationLibrary
var is_ready := false
var focused_pause := false
var window_hidden := false
var timers: Array[Tween] = []
var warmup_pawn: Node3D
var ado_prepared: Node3D
var ado_preview: SubViewport
var ado_preview_drawn := false
var side_view := false
var deployment_handoffs := 0
var contact_occluders: Array[String] = []


static func project_ground(point: Vector2, sideways: bool) -> Vector2:
	if not sideways:
		return point
	var turned := point.rotated(SIDE_TURN)
	return Vector2(turned.x, turned.y * sin(SIDE_PITCH))


static func unit_scale(sideways: bool) -> float:
	return SIDE_UNIT_SCALE if sideways else MAP_UNIT_SCALE


func _ready() -> void:
	mouse_filter = MOUSE_FILTER_IGNORE
	if not enabled:
		return
	viewport_3d = SubViewport.new()
	viewport_3d.own_world_3d = true
	viewport_3d.transparent_bg = true
	viewport_3d.render_target_update_mode = SubViewport.UPDATE_DISABLED
	viewport_3d.gui_disable_input = true
	add_child(viewport_3d)
	var display := TextureRect.new()
	display.mouse_filter = MOUSE_FILTER_IGNORE
	display.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	display.texture = viewport_3d.get_texture()
	display.show_behind_parent = true
	add_child(display)
	display.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	var fill := WorldEnvironment.new()
	fill.environment = Environment.new()
	fill.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	fill.environment.ambient_light_color = Color("aabec3")
	fill.environment.ambient_light_energy = 0.65
	viewport_3d.add_child(fill)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-54, -37, 0)
	light.light_color = Color("ffe6bb")
	light.light_energy = 0.95
	viewport_3d.add_child(light)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	viewport_3d.add_child(camera)
	camera.position = Vector3(0, 13, 10)
	camera.look_at(Vector3.ZERO)
	_update_ground_projection()
	is_ready = true
	visible = false
	if DisplayServer.get_name() == "headless":
		_prepare_shield(_load_scene(MODEL_PATH))
	else:
		_load_scene(MODEL_PATH, true)


func _prepare_shield(source: PackedScene) -> void:
	if source == null:
		return
	travel_library = Actor.in_place_travel(source, Profiles.STANDARD.S01.clips.travel)
	if travel_library == null:
		push_error("P06 shield has no advance Root position track")
		return
	model = source


func _warmup() -> void:
	# Compile the compatibility skin/material variant while the sidecar opens.
	# Rendering a tiny hidden viewport avoids a cold first draw in combat.
	var pawn := Actor.new()
	viewport_3d.add_child(pawn)
	if not pawn.assemble(model, travel_library, Profiles.STANDARD.S01):
		pawn.queue_free()
		return
	pawn.snap(Vector3(0, -0.65, 0), -0.6, false, true)
	_draw_warmup(pawn, 2.6)


func _draw_warmup(pawn: Node3D, extent: float) -> void:
	warmup_pawn = pawn
	hide()
	camera.size = extent
	viewport_3d.size = Vector2i(96, 96)
	_schedule_board_draw()


func _finish_warmup() -> void:
	warmup_pawn.hide()
	warmup_pawn.queue_free()
	warmup_pawn = null
	audit.mimic_prepared_before_battle = mimic_warmed
	geometry_ready.emit()


func _add_mimic_warmup(parent: Node3D, point: Vector3) -> void:
	if mimic_warmed:
		return
	var scene := _load_scene(Profiles.entries["EN01"].model)
	if scene == null:
		return
	var enemy := Mimic.new()
	parent.add_child(enemy)
	if not enemy.assemble(scene):
		enemy.queue_free()
		return
	enemy.snap(point, 0.0, false, true)
	mimic_warmed = true


func prepare_mimic() -> void:
	if not is_ready or mimic_warmed or not battle_id.is_empty() or DisplayServer.get_name() == "headless":
		return
	var holder := Node3D.new()
	var preview := _actor_preview(96, 2.8)
	preview.add_child(holder)
	_add_mimic_warmup(holder, Vector3(0, -0.3, 0))
	if not mimic_warmed:
		preview.queue_free()
		return
	preview.render_target_update_mode = SubViewport.UPDATE_ONCE
	RenderingServer.frame_post_draw.connect(func() -> void:
		audit.mimic_prepared_before_battle = true
		preview.queue_free()
	, CONNECT_ONE_SHOT)


func prepare_creature(kind: String) -> void:
	if not is_ready or not battle_id.is_empty() or DisplayServer.get_name() == "headless":
		return
	var wasp := kind == "EN03"
	if (wasp and wasp_warmed) or (not wasp and echo_warmed):
		return
	var source := _load_scene(Profiles.entries["EN03" if wasp else "EN06"].model)
	if source == null:
		return
	var preview := _actor_preview(96, 2.6)
	var pawn: Node3D = Wasp.new() if wasp else Echo.new()
	preview.add_child(pawn)
	if not pawn.assemble(source):
		preview.queue_free()
		return
	if wasp:
		wasp_warmed = true
		var dart := MeshInstance3D.new()
		dart.mesh = _sting_mesh()
		dart.position = Vector3(0.52, 0.23, 0.0)
		preview.add_child(dart)
	else:
		echo_warmed = true
	pawn.snap(Vector3(0, -0.45, 0), 0.0, false, true)
	preview.render_target_update_mode = SubViewport.UPDATE_ONCE
	RenderingServer.frame_post_draw.connect(preview.queue_free, CONNECT_ONE_SHOT)


func prepare_gray_oak() -> void:
	if not is_ready or gray_oak_warmed or warmup_pawn != null or not battle_id.is_empty():
		return
	gray_oak_warmed = true
	if DisplayServer.get_name() == "headless":
		return
	var wall := _scene("SM_Wall_Short.glb")
	if wall == null:
		return
	var warmup := Node3D.new()
	viewport_3d.add_child(warmup)
	_add_mimic_warmup(warmup, Vector3.ZERO)
	var sample := wall.instantiate() as Node3D
	warmup.add_child(sample)
	sample.position = Vector3(0.55, 0, -0.35)
	_draw_warmup(warmup, 2.8)


func prepare_skeletons() -> void:
	if not is_ready or skeletons_warmed or not battle_id.is_empty() or DisplayServer.get_name() == "headless":
		return
	var preview := _actor_preview(96, 3.3)
	for kind: String in Profiles.SKELETON_KINDS:
		var source := _load_scene(Profiles.entries[kind].model)
		var pawn := SkeletonEnemy.new()
		preview.add_child(pawn)
		if source == null or not pawn.assemble(source, kind):
			preview.queue_free()
			return
		pawn.snap(Vector3(-0.55 if kind == "EN21" else 0.55, -0.42, 0.0), 0.0, false, true)
	skeletons_warmed = true
	preview.render_target_update_mode = SubViewport.UPDATE_ONCE
	RenderingServer.frame_post_draw.connect(preview.queue_free, CONNECT_ONE_SHOT)


func _scene(asset: String) -> PackedScene:
	return _load_scene(GRAY_OAK + asset)


func _load_scene(path: String, background := false) -> PackedScene:
	if scene_assets.has(path):
		if background and path in _scenes_ready_to_present:
			return null
		return scene_assets[path]
	if background and DisplayServer.get_name() != "headless":
		if not _scene_loads.has(path) and path not in _scene_load_queue:
			_scene_load_queue.append(path)
			_wake_model_dispatch()
		return null
	var started := Time.get_ticks_usec() if profile_assets else 0
	var source := load(path) as PackedScene
	scene_assets[path] = source
	if profile_assets:
		asset_load_timings.append({"path": path, "started_usec": started,
			"load_usec": Time.get_ticks_usec() - started, "background": false})
	return source


func _poll_scene_loads() -> void:
	if _scene_loads.is_empty():
		return
	for path: String in _scene_loads.keys():
		var status := ResourceLoader.load_threaded_get_status(path)
		if status == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			continue
		var source: PackedScene
		if status == ResourceLoader.THREAD_LOAD_LOADED:
			source = ResourceLoader.load_threaded_get(path) as PackedScene
		if source == null:
			push_warning("P06 model could not be loaded: " + path)
		scene_assets[path] = source
		if profile_assets:
			var started: int = _scene_loads[path]
			asset_load_timings.append({"path": path, "started_usec": started,
				"load_usec": Time.get_ticks_usec() - started, "background": true, "loaded": source != null})
		_scene_loads.erase(path)
		if source != null:
			_scenes_ready_to_present.append(path)


func _start_queued_loads() -> void:
	while _scene_loads.size() < CONCURRENT_MODEL_LOADS and not _scene_load_queue.is_empty():
		var path: String = _scene_load_queue.pop_front()
		if ResourceLoader.load_threaded_request(path, "PackedScene") == OK:
			_scene_loads[path] = Time.get_ticks_usec() if profile_assets else 0
		else:
			scene_assets[path] = null
			push_warning("P06 could not queue model: " + path)


func set_scenery(placements: Dictionary) -> void:
	if not is_ready or warmup_pawn != null:
		return
	var changed := false
	for id in scenery.keys():
		if not placements.has(id) or placements[id].asset != _scenery_placements[id].asset:
			scenery[id].hide()
			scenery[id].queue_free()
			scenery.erase(id)
			_scenery_placements.erase(id)
			changed = true
	for id in placements:
		var row: Dictionary = placements[id]
		if not _scenery_projection_dirty and row == _scenery_placements.get(id):
			continue
		if not scenery.has(id):
			var part: Node3D
			if row.asset.begins_with("fortress-") or row.asset.begins_with("town-"):
				part = FortressKit.piece(row.asset)
			elif MirrorCourtKit.supports(row.asset):
				part = MirrorCourtKit.piece(row.asset)
			elif SaltCrossingKit.supports(row.asset):
				part = SaltCrossingKit.piece(row.asset)
			elif ForgeCrossingKit.supports(row.asset):
				part = ForgeCrossingKit.piece(row.asset)
			elif CitadelRingKit.supports(row.asset):
				part = CitadelRingKit.piece(row.asset)
			else:
				var resource := _scene(row.asset)
				if resource != null:
					part = resource.instantiate()
			if part == null:
				continue
			scenery[id] = part
			viewport_3d.add_child(part)
		var prop: Node3D = scenery[id]
		prop.position = _world(row.pixel)
		prop.scale = Vector3.ONE * float(row.scale)
		prop.rotation.y = float(row.yaw)
		if prop is MultiMeshInstance3D:
			prop.material_override = FortressKit.backdrop_material() if row.get("backdrop", false) else null
		_scenery_placements[id] = row.duplicate()
		audit.field_props[id] = row.asset
		changed = true
	_scenery_projection_dirty = false
	if changed:
		audit.scenery_updates += 1
	_update_scene_visibility(changed)


func _update_scene_visibility(redraw: bool) -> void:
	var show_stage := not battle_id.is_empty() or not actors.is_empty() or not scenery.is_empty()
	if visible != show_stage:
		visible = show_stage
		redraw = true
	if redraw:
		_schedule_board_draw()


func prepare_spear() -> void:
	if not show_spear or not is_ready or spear_warmed or warmup_pawn != null or not battle_id.is_empty():
		return
	if not _load_spear():
		return
	spear_warmed = true
	if DisplayServer.get_name() == "headless":
		return
	var pawn := Spear.new()
	viewport_3d.add_child(pawn)
	if not pawn.assemble(spear_model):
		pawn.queue_free()
		return
	pawn.snap(Vector3(0, -0.65, 0), -0.6, false, true)
	_draw_warmup(pawn, 2.6)


func _load_spear() -> bool:
	if spear_model == null:
		spear_model = _load_scene(Profiles.SPEAR_MODEL, true)
	return spear_model != null


func prefetch_ado() -> void:
	if is_ready and DisplayServer.get_name() != "headless":
		_load_scene(ADO_PATH, true)


func prefetch_contact_models(kinds: Array) -> void:
	if not is_ready or DisplayServer.get_name() == "headless":
		return
	for kind in kinds:
		if not (kind is String):
			continue
		var profile: Dictionary = Profiles.entries.get(kind, {})
		if profile.get("prefetch", false) and _profile_available(kind, profile):
			_load_scene(profile.model, true)


func _profile_available(kind: String, profile: Dictionary) -> bool:
	if profile.get("spear_setting", false) and not show_spear:
		return false
	if not profile.get("optional", false):
		return true
	if not _optional_model_available.has(kind):
		_optional_model_available[kind] = ResourceLoader.exists(profile.model)
	return _optional_model_available[kind]


func is_model_pending(kind: String, enemy := false) -> bool:
	if not enabled or not is_ready:
		return false
	return _supports_enemy(kind) if enemy else _supports_deployment(kind)


func _ado_visual_pending() -> bool:
	return ADO_PATH in _scene_load_queue or _scene_loads.has(ADO_PATH) or ADO_PATH in _scenes_ready_to_present \
		or (ado_prepared != null and (not ado_preview_drawn or focused_pause or window_hidden))


func _has_model_work() -> bool:
	return not _scene_load_queue.is_empty() or not _scene_loads.is_empty() \
		or (not focused_pause and not window_hidden \
			and (_actor_attachment_pending or not _scenes_ready_to_present.is_empty()))


func _wake_model_dispatch() -> void:
	if _has_model_work() and not get_tree().process_frame.is_connected(_dispatch_models):
		get_tree().process_frame.connect(_dispatch_models)


func _dispatch_models() -> void:
	# Background reads do not need the animation process to be running.
	var started := Time.get_ticks_usec() if profile_assets else 0
	_poll_scene_loads()
	_start_queued_loads()
	var polled := Time.get_ticks_usec() if profile_assets else 0
	var path := ""
	var prepared := polled
	var refresh := false
	if not focused_pause and not window_hidden and _actor_attachment_pending:
		_actor_attachment_pending = false
		refresh = true
	elif not focused_pause and not window_hidden and not _scenes_ready_to_present.is_empty():
		path = _scenes_ready_to_present.pop_front()
		if path == MODEL_PATH:
			_prepare_shield(scene_assets[path])
			if model != null and cells.is_empty() and warmup_pawn == null:
				_warmup()
		elif path == ADO_PATH:
			_prepare_ado_view(scene_assets[path])
		if profile_assets:
			prepared = Time.get_ticks_usec()
		refresh = path != ADO_PATH or ado_prepared == null
	if refresh and not cells.is_empty():
		geometry_ready.emit()
	if profile_assets:
		model_dispatch_timings.append({"path": path, "started_usec": started, "dispatch_usec": polled - started,
			"prepare_usec": prepared - polled, "geometry_usec": Time.get_ticks_usec() - prepared})
	if not _has_model_work():
		get_tree().process_frame.disconnect(_dispatch_models)


func stop_background_loading() -> Vector2i:
	var outstanding := Vector2i(_scene_loads.size(), _scene_load_queue.size())
	if get_tree().process_frame.is_connected(_dispatch_models):
		get_tree().process_frame.disconnect(_dispatch_models)
	_scene_load_queue.clear()
	_scenes_ready_to_present.clear()
	_actor_attachment_pending = false
	return outstanding


func _actor_preview(edge: int, extent: float) -> SubViewport:
	var preview := SubViewport.new()
	preview.own_world_3d = true
	preview.size = Vector2i(edge, edge)
	preview.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(preview)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-54, -37, 0)
	preview.add_child(light)
	var lens := Camera3D.new()
	lens.projection = Camera3D.PROJECTION_ORTHOGONAL
	lens.size = extent
	preview.add_child(lens)
	lens.position = Vector3(0, 13, 10)
	lens.look_at(Vector3.ZERO)
	return preview


func _prepare_ado_view(resource: PackedScene) -> void:
	ado_preview = _actor_preview(80, 3.3)
	var pawn := Ado.new()
	ado_preview.add_child(pawn)
	if not pawn.assemble(resource):
		ado_preview.queue_free()
		ado_preview = null
		return
	ado_prepared = pawn
	pawn.snap(Vector3(0, -0.72, 0), -0.6, false, true)
	ado_preview.add_child(FortressKit.piece("fortress-rubble"))
	_schedule_ado_preview_draw()


func _schedule_ado_preview_draw() -> void:
	if ado_preview == null or ado_preview_drawn:
		return
	ado_preview.render_target_update_mode = SubViewport.UPDATE_DISABLED if window_hidden else SubViewport.UPDATE_ONCE
	var connected := RenderingServer.frame_post_draw.is_connected(_ado_preview_finished)
	if window_hidden and connected:
		RenderingServer.frame_post_draw.disconnect(_ado_preview_finished)
	elif not window_hidden and not connected:
		RenderingServer.frame_post_draw.connect(_ado_preview_finished, CONNECT_ONE_SHOT)


func _ado_preview_finished() -> void:
	ado_preview_drawn = ado_prepared != null
	if ado_preview_drawn and not focused_pause and not window_hidden:
		geometry_ready.emit()


func _take_ado() -> Node3D:
	var pawn := ado_prepared
	if pawn != null:
		audit.ado_prepared_before_battle = ado_preview_drawn
		pawn.reparent(viewport_3d, false)
		ado_prepared = null
		ado_preview.queue_free()
		ado_preview = null
	return pawn


func set_geometry(points: Dictionary, radius: float, sideways := false) -> void:
	cells = points
	if not is_ready or warmup_pawn != null or size.x < 2 or size.y < 2:
		return
	var requested := Vector2i(size.round())
	var extent := size.y / maxf(radius * unit_scale(sideways), 1.0)
	if viewport_3d.size == requested and is_equal_approx(camera.size, extent) and side_view == sideways:
		return
	if not battle_id.is_empty():
		audit.viewport_resizes_in_battle += 1
	viewport_3d.size = requested
	camera.size = extent
	side_view = sideways
	# The exploration map can cover many more cells than a battle. Keep
	# ground-plane samples inside the near plane at the wider ortho extent.
	var eye := Vector3(0, sin(SIDE_PITCH), cos(SIDE_PITCH)) * 16.5 if side_view else Vector3(0, 13, 10)
	camera.position = eye * maxf(1.0, extent / 18.0)
	camera.look_at(Vector3.ZERO)
	_update_ground_projection()
	_scenery_projection_dirty = true
	for token in actors.values():
		var point := _world(_at(token.row.pos))
		var facing := _facing(int(token.row.facing))
		var down := float(token.row.hp) <= 0
		if down and not battle_id.is_empty() and token.node is Actor:
			# The results panel can resize the viewport while a defeat clip is playing.
			token.node.position = point
			token.node.destination = point
			token.node.heading = facing
		else:
			token.node.snap(point, facing, down, reduced or battle_id.is_empty())
		_sync_pose(token.node, token.row, true)
	_schedule_board_draw()


func _schedule_board_draw() -> void:
	if not is_ready:
		return
	if warmup_pawn != null:
		viewport_3d.render_target_update_mode = SubViewport.UPDATE_DISABLED if window_hidden else SubViewport.UPDATE_ONCE
		var connected := RenderingServer.frame_post_draw.is_connected(_finish_warmup)
		if window_hidden and connected:
			RenderingServer.frame_post_draw.disconnect(_finish_warmup)
		elif not window_hidden and not connected:
			RenderingServer.frame_post_draw.connect(_finish_warmup, CONNECT_ONE_SHOT)
	elif not visible or window_hidden:
		viewport_3d.render_target_update_mode = SubViewport.UPDATE_DISABLED
	elif not battle_id.is_empty() and not focused_pause:
		viewport_3d.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	else:
		viewport_3d.render_target_update_mode = SubViewport.UPDATE_ONCE
		if focused_pause and not RenderingServer.frame_post_draw.is_connected(_freeze_paused_board):
			RenderingServer.frame_post_draw.connect(_freeze_paused_board, CONNECT_ONE_SHOT)


func _freeze_paused_board() -> void:
	if focused_pause and warmup_pawn == null:
		viewport_3d.render_target_update_mode = SubViewport.UPDATE_DISABLED


func set_window_hidden(value: bool) -> void:
	if value != window_hidden:
		window_hidden = value
		_schedule_board_draw()
		_schedule_ado_preview_draw()
		if not window_hidden:
			_wake_model_dispatch()
			geometry_ready.emit()


func set_paused(value: bool) -> void:
	if value == focused_pause:
		return
	focused_pause = value
	process_mode = Node.PROCESS_MODE_DISABLED if value else Node.PROCESS_MODE_INHERIT
	for timer in timers:
		if timer.is_valid():
			if value:
				timer.pause()
			else:
				timer.play()
	if not focused_pause:
		_wake_model_dispatch()
	_schedule_board_draw()


func _project_floor(pixel: Vector2) -> Vector3:
	var origin := camera.project_ray_origin(pixel)
	var ray := camera.project_ray_normal(pixel)
	return origin - ray * (origin.y / ray.y)


func _update_ground_projection() -> void:
	# An orthographic ray intersects the flat board affinely in screen coordinates.
	var extent := Vector2(viewport_3d.size)
	_ground_origin = _project_floor(Vector2.ZERO)
	_ground_x = (_project_floor(Vector2(extent.x, 0)) - _ground_origin) / extent.x
	_ground_y = (_project_floor(Vector2(0, extent.y)) - _ground_origin) / extent.y
	_ground_facings.clear()
	for direction in FACINGS:
		var offset := project_ground(direction, side_view)
		_ground_facings.append(_yaw(_ground_x * offset.x + _ground_y * offset.y))


func _world(pixel: Vector2) -> Vector3:
	return _ground_origin + _ground_x * pixel.x + _ground_y * pixel.y


func _at(pos: Array) -> Vector2:
	return cells.get(Vector2i(int(pos[0]), int(pos[1])), size / 2.0)


func _facing(direction: int) -> float:
	return _ground_facings[posmod(direction, 6)]


func _yaw(direction: Vector3) -> float:
	return atan2(direction.x, direction.z)


func clear_battle() -> void:
	if battle_id.is_empty():
		return
	for timer in timers:
		if timer.is_valid():
			timer.kill()
	timers.clear()
	for token in actors.values():
		token.node.hide()
		token.node.queue_free()
	actors.clear()
	seen.clear()
	marks.clear()
	ado_traces.clear()
	for flight: Tween in projectile_tweens.values():
		if flight.is_valid():
			flight.kill()
	projectile_tweens.clear()
	for projectile in flying_projectiles:
		projectile.hide()
		spare_projectiles.append(projectile)
	flying_projectiles.clear()
	battle_id = ""
	viewport_3d.render_target_update_mode = SubViewport.UPDATE_ONCE
	visible = false
	queue_redraw()


func apply(snapshot: Dictionary, restore: bool, deployment: Array = [], enemies: Array = []) -> void:
	if not is_ready or warmup_pawn != null:
		return
	if snapshot.is_empty():
		clear_battle()
		_apply_deployment(deployment, enemies)
		return
	if cells.is_empty():
		return
	if battle_id != snapshot.id:
		if battle_id.is_empty():
			_keep_actors(snapshot.actors.map(func(row): return row.id))
			deployment_handoffs += actors.values().filter(func(token): return token.row.side == "player").size()
		else:
			clear_battle()
		battle_id = snapshot.id
		restore = true
		visible = true
		_schedule_board_draw()
	var by_id := {}
	var relocated := {}
	var spears := 0
	var enemy_spears := 0
	var mimics := 0
	var melee_count := 0
	var bow_count := 0
	var targeted_counts := {}
	var crossbow_count := 0
	var hero_count := 0
	var echoes := 0
	var wasps := 0
	for row in snapshot.actors:
		by_id[row.id] = row
		if _supports_deployment(row.kind) and row.side == "player" and row.pos is Array:
			_update_actor(row, restore, false, relocated)
			if row.kind == "M01" and actors.has(row.id):
				spears += 1
			elif row.kind == "S02" and actors.has(row.id):
				melee_count += 1
			elif row.kind == "S03" and actors.has(row.id):
				bow_count += 1
			elif Profiles.TARGETED.has(row.kind) and actors.has(row.id):
				var key: String = Profiles.TARGETED[row.kind].effect + "_peak"
				targeted_counts[key] = int(targeted_counts.get(key, 0)) + 1
			elif row.kind == "M03" and actors.has(row.id):
				crossbow_count += 1
			elif row.kind in Profiles.HERO_KINDS and actors.has(row.id):
				hero_count += 1
				audit.hero_kinds[row.kind] = int(audit.hero_kinds.get(row.kind, 0)) + 1
		elif _supports_enemy(row.kind) and row.side == "enemy" and row.pos is Array:
			_update_actor(row, restore, false, relocated)
			if row.kind == "EN01" and actors.has(row.id):
				mimics += 1
			elif row.kind == "EN06" and actors.has(row.id):
				echoes += 1
			elif row.kind == "EN03" and actors.has(row.id):
				wasps += 1
			elif row.kind == "EN17" and actors.has(row.id):
				enemy_spears += 1
			elif row.kind == "MG01" and actors.has(row.id):
				audit.ado_seen = true
				var phase := int(row.boss_phase)
				if phase not in audit.ado_phases:
					audit.ado_phases.append(phase)
	audit.peak_models = maxi(int(audit.peak_models), actors.size())
	audit.melee_peak = maxi(int(audit.melee_peak), melee_count)
	audit.bow_peak = maxi(int(audit.bow_peak), bow_count)
	for key in targeted_counts:
		audit[key] = maxi(int(audit.get(key, 0)), int(targeted_counts[key]))
	audit.crossbow_peak = maxi(int(audit.crossbow_peak), crossbow_count)
	audit.hero_peak = maxi(int(audit.hero_peak), hero_count)
	audit.spear_peak = maxi(int(audit.spear_peak), spears)
	audit.enemy_spear_peak = maxi(int(audit.enemy_spear_peak), enemy_spears)
	audit.mimic_peak = maxi(int(audit.mimic_peak), mimics)
	audit.echo_peak = maxi(int(audit.echo_peak), echoes)
	audit.wasp_peak = maxi(int(audit.wasp_peak), wasps)
	var events: Array[Dictionary] = []
	for row in snapshot.events:
		if not row.get("event_id", "") in seen:
			seen[row.event_id] = true
			if not restore:
				events.append(row)
	audit.events += events.size()
	if not events.is_empty():
		_animate(events, by_id, snapshot.get("finished", false), relocated)
	elif not restore and not relocated.is_empty():
		_apply_relocations(relocated, {}, {})
	for row in snapshot.actors:
		var pawn: Variant = actors.get(row.id, {}).get("node")
		if pawn is Melee and not pawn.gap_cast.is_empty() and float(row.hp) > 0 \
				and pawn.gap_cast != row.get("melee_pending", {}).get("id", ""):
			pawn.cancel_gap(reduced)
		if _uses_general_casts(pawn) and not pawn.active_cast.is_empty() and float(row.hp) > 0 \
				and pawn.active_cast != row.get("boss_pending", {}).get("id", ""):
			pawn.apply_boss_event("cancel", pawn.active_move, pawn.active_cast, pawn.heading, reduced)
		if pawn is Admin and row.kind == "ADMIN" and float(row.hp) > 0:
			pawn.apply_state_pose(str(row.get("admin_pose", "")), pawn.heading, reduced, restore)
		if pawn is En02 and float(row.hp) > 0:
			pawn.apply_shell_seam(row.has("shell_seam"), reduced, restore)
		if pawn is Bow and not pawn.bow_cast.is_empty() and float(row.hp) > 0 \
				and pawn.bow_cast != row.get("bow_pending", {}).get("id", ""):
			_cancel_bow(pawn)
		if pawn is Spear and pawn.enemy and not pawn.cast_id.is_empty() and float(row.hp) > 0 \
				and pawn.cast_id != row.get("spear_pending", {}).get("id", ""):
			pawn.resolve(pawn.cast_id, true)
		if pawn is SkeletonEnemy and pawn.archer and not pawn.cast_id.is_empty() and float(row.hp) > 0 \
				and pawn.cast_id != row.get("bone_pending", {}).get("id", ""):
			pawn.cancel_bow(reduced)
		if pawn is Targeted and not pawn.cast_id.is_empty() and float(row.hp) > 0:
			var pending: Dictionary = row.get(pawn.pending_field, {})
			if pawn.cast_id != pending.get("id", ""):
				pawn.cancel_cast(reduced)
		if pawn is Hero and not pawn.cast_id.is_empty() and float(row.hp) > 0 \
				and pawn.cast_id != row.get("hero_pending", {}).get("id", ""):
			pawn.cancel_skill(reduced)
	if focused_pause and (restore or not events.is_empty() or not relocated.is_empty()):
		_schedule_board_draw()


func _supports_deployment(kind: String) -> bool:
	var profile: Dictionary = Profiles.entries.get(kind, {})
	return profile.get("side") == "player" and _profile_available(kind, profile)


func _supports_enemy(kind: String) -> bool:
	var profile: Dictionary = Profiles.entries.get(kind, {})
	return profile.get("side") == "enemy" and _profile_available(kind, profile)


func _apply_deployment(rows: Array, enemies: Array) -> void:
	var visible_ids: Array = []
	var changed := false
	for member in rows:
		if not member.deployed or not member.deployable or int(member.injury_days) > 0:
			continue
		if not _supports_deployment(member.unit_id):
			continue
		var pos := Vector2i(int(member.position[0]), int(member.position[1]))
		if not cells.has(pos):
			continue
		var id: String = member.instance_id
		visible_ids.append(id)
		var row := {"id": id, "kind": member.unit_id, "side": "player", "pos": member.position,
			"facing": member.facing, "hp": member.hp}
		if not actors.has(id) or actors[id].row != row:
			_update_actor(row, true, true)
			changed = actors.has(id) or changed
	for enemy in enemies:
		var pos := Vector2i(int(enemy.position[0]), int(enemy.position[1]))
		if not _supports_enemy(enemy.kind) or not cells.has(pos):
			continue
		if enemy.kind == "MG01" and _ado_visual_pending():
			continue
		var id: String = enemy.id
		visible_ids.append(id)
		var row := {"id": id, "kind": enemy.kind, "side": "enemy", "pos": enemy.position,
			"facing": enemy.facing, "hp": enemy.hp}
		if not actors.has(id) or actors[id].row != row:
			_update_actor(row, true, true)
			changed = actors.has(id) or changed
	var removed := _keep_actors(visible_ids)
	_update_scene_visibility(changed or removed)


func _keep_actors(ids: Array) -> bool:
	var removed := false
	for id in actors.keys():
		if id not in ids:
			actors[id].node.hide()
			actors[id].node.queue_free()
			actors.erase(id)
			removed = true
	return removed


func inspect_contact_enemy(id: String) -> void:
	var was_hidden := not contact_occluders.is_empty()
	for hidden_id in contact_occluders:
		if actors.has(hidden_id):
			actors[hidden_id].node.show()
	contact_occluders.clear()
	if battle_id.is_empty() and actors.has(id):
		var behind := _contact_model_bounds(id)
		var selected_y := foot_pixel(id).y
		for other: String in actors:
			if actors[other].row.side != "enemy" or foot_pixel(other).y <= selected_y:
				continue
			if behind.intersects(_contact_model_bounds(other)):
				actors[other].node.hide()
				contact_occluders.append(other)
	if was_hidden or not contact_occluders.is_empty():
		_schedule_board_draw()


func _contact_model_bounds(id: String) -> Rect2:
	var token: Dictionary = actors[id]
	var actor: Node3D = token.node
	var height_in_world: float = Profiles.entries[token.row.kind].get("contact_height", 1.8)
	var foot := camera.unproject_position(actor.global_position)
	var head := camera.unproject_position(actor.global_position + Vector3.UP * height_in_world)
	var height := foot.y - head.y
	var half_width := clampf(height * 0.30, 11.0, 38.0)
	return Rect2(head - Vector2(half_width, 0), Vector2(half_width * 2.0, height))


func pick_actor(point: Vector2, allies_only := false) -> String:
	if not is_ready:
		return ""
	var picked := ""
	var foremost := -INF
	for id in actors:
		if float(actors[id].row.hp) <= 0 or not actors[id].node.visible \
				or (allies_only and actors[id].row.side == "enemy"):
			continue
		var root: Vector3 = actors[id].node.global_position
		var foot := camera.unproject_position(root)
		var head := camera.unproject_position(root + Vector3.UP * 1.60)
		var height := foot.y - head.y
		var half_width := clampf(height * 0.23, 9.0, 25.0)
		var bounds := Rect2(head - Vector2(half_width, 0), Vector2(half_width * 2.0, height + 4.0))
		if bounds.has_point(point) and foot.y > foremost:
			picked = id
			foremost = foot.y
	return picked


func foot_pixel(id: String) -> Vector2:
	return camera.unproject_position(actors[id].node.global_position)


func head_pixel(id: String) -> Vector2:
	if not is_ready or not actors.has(id):
		return Vector2.INF
	var token: Dictionary = actors[id]
	var pawn: Node3D = token.node
	var height: float = 0.52 if float(token.row.get("hp", 0)) <= 0 else \
		Profiles.entries[token.row.kind].get("head_height", 1.70)
	return camera.unproject_position(pawn.global_position + Vector3.UP * height)


func _update_actor(row: Dictionary, restore: bool, preview := false, relocated := {}) -> void:
	var attachment_timing: Dictionary = {}
	if not actors.has(row.id):
		if row.kind == "MG01" and _ado_visual_pending():
			return
		var prepared: Node3D = _take_ado() if row.kind == "MG01" else null
		if prepared != null:
			actors[row.id] = {"node": prepared, "row": row}
			restore = true
	if not actors.has(row.id):
		var profile: Dictionary = Profiles.entries.get(row.kind, {})
		if profile.is_empty():
			return
		var profile_attachment: bool = profile_assets and profile.get("stagger", false)
		var started := Time.get_ticks_usec() if profile_attachment else 0
		var assembly: String = profile.get("assembly", "standard")
		var scene: PackedScene = model if assembly == "shield" else \
			_load_scene(profile.model, profile.get("background", profile.get("prefetch", false)))
		if scene == null:
			return
		# A loaded infantry scene can supply several deployed actors in the same refresh.
		var stagger: bool = profile.get("stagger", false) and DisplayServer.get_name() != "headless"
		var frame := Engine.get_process_frames() if stagger else -1
		if stagger and (focused_pause or window_hidden or frame == _actor_attachment_frames.get(row.kind, -1)):
			_actor_attachment_pending = true
			_wake_model_dispatch()
			return
		if profile.get("prefetch_travel", false) and not actor_travels.has(row.kind):
			var travel := Actor.in_place_travel(scene, profile.clips.travel, profile.get("require_root_track", true))
			if travel == null:
				push_error("P06 in-place travel is missing for " + str(row.kind))
				return
			actor_travels[row.kind] = travel
		var assembling := Time.get_ticks_usec() if profile_attachment else 0
		var constructor: Script = profile.script
		var pawn: Node3D = constructor.new()
		viewport_3d.add_child(pawn)
		var assembled := _assemble_actor(pawn, scene, row.kind, profile)
		if not assembled:
			pawn.queue_free()
			push_error("P06 animation import is incomplete: " + str(row.kind))
			return
		if assembly in ["melee", "bow", "hero"] and not actor_travels.has(row.kind):
			actor_travels[row.kind] = pawn.player.get_animation_library("board")
		if stagger:
			_actor_attachment_frames[row.kind] = frame
		if profile_attachment:
			var attached := Time.get_ticks_usec()
			attachment_timing = {"id": row.id, "kind": row.kind, "frame": frame, "attached_usec": attached,
				"prepare_usec": assembling - started, "assemble_usec": attached - assembling}
		if pawn is Actor or pawn is Spear or pawn is RingGuard or pawn is SkeletonEnemy:
			pawn.clip_started.connect(_count_clip)
		actors[row.id] = {"node": pawn, "row": row}
		restore = true
	var token: Dictionary = actors[row.id]
	var prev_pos: Variant = token.row.get("pos")
	token.row = row
	if restore:
		token.node.snap(_world(_at(row.pos)), _facing(int(row.facing)), float(row.hp) <= 0, reduced or preview)
	else:
		token.node.destination = _world(_at(row.pos))
		token.node.heading = _facing(int(row.facing))
		if prev_pos != row.pos:
			relocated[row.id] = true
	_sync_pose(token.node, row, restore)
	if not attachment_timing.is_empty():
		attachment_timing["pose_usec"] = Time.get_ticks_usec() - int(attachment_timing.attached_usec)
		actor_attachment_timings.append(attachment_timing)


func _assemble_actor(pawn: Node3D, scene: PackedScene, kind: String, profile: Dictionary) -> bool:
	var travel: AnimationLibrary = actor_travels.get(kind)
	match profile.get("assembly", "standard"):
		"shield":
			return pawn.assemble(scene, travel_library, profile)
		"melee":
			return pawn.assemble_gap(scene, travel, profile)
		"bow":
			return pawn.assemble_bow(scene, travel, profile)
		"crossbow":
			return pawn.assemble_crossbow(scene, travel, profile)
		"targeted":
			return pawn.assemble_targeted(scene, travel, profile)
		"hero":
			return pawn.assemble_hero(scene, travel, kind, profile)
		"mg03":
			return pawn.assemble_mg03(scene, travel, profile)
		"mg04":
			return pawn.assemble_mg04(scene, travel, profile)
		"demon":
			return pawn.assemble_demon(scene, travel, profile)
		"admin":
			return pawn.assemble_admin(scene, travel, profile)
		"admin_guard", "enemy_cast":
			return pawn.assemble_guard(scene, travel, profile)
		"charge":
			return pawn.assemble_charge(scene, travel, profile)
		"enemy_spear":
			return pawn.assemble(scene, true)
		"skeleton":
			return pawn.assemble(scene, kind)
	return pawn.assemble(scene)


func _sync_pose(pawn: Node3D, row: Dictionary, restore: bool) -> void:
	if restore and pawn is Melee and row.get("melee_pending") is Dictionary:
		_prepare_gap(pawn, row, true)
	if restore and pawn is Bow and row.get("bow_pending") is Dictionary:
		_prepare_bow(pawn, row, true)
	if restore and pawn is Targeted and row.get(pawn.pending_field) is Dictionary:
		_prepare_targeted(pawn, row[pawn.pending_field], true)
	if restore and pawn is Hero and row.get("hero_pending") is Dictionary:
		_prepare_hero_skill(pawn, row, true)
	if restore and pawn is Spear and row.get("spear_pending") is Dictionary:
		var pending: Dictionary = row.spear_pending
		_lock_spear(pawn, row, str(pending.id), pending.get("cells", []), pending.get("origin"), true)
	if pawn is Echo:
		var winding := row.has("echo_pending") and float(row.hp) > 0
		if winding and not pawn.winding and not restore:
			audit.echo_windups += 1
		pawn.set_winding(winding)
	elif pawn is Wasp:
		var winding := row.has("sting_pending") and float(row.hp) > 0
		if winding and not pawn.winding and not restore:
			audit.sting_windups += 1
		pawn.set_winding(winding)
	elif pawn is RingGuard:
		pawn.observe_protection(row.get("guard_active", false), restore, reduced)
	elif pawn is SkeletonEnemy:
		if pawn.archer:
			var draw: Dictionary = row.get("bone_pending", {})
			if not draw.is_empty() and (restore or pawn.cast_id == draw.id):
				_draw_bone_bow(pawn, row, draw, restore)
		else:
			pawn.observe_guard(row.get("guard_active", false), restore, reduced)
	elif pawn is Mimic:
		var winding := row.has("mimic_pending") and float(row.hp) > 0
		if winding and not pawn.winding and not restore:
			audit.mimic_windups += 1
		pawn.set_winding(winding)
	elif pawn is DualSac:
		var locked: Dictionary = row.get("dual_sac_pending", {})
		pawn.show_state(locked, row.get("dual_sac_rooted", false), _intent_facing(locked.get("facing"), int(row.facing)), restore)
	elif pawn is Ado:
		var action: Dictionary = row.get("boss_pending", {})
		var yaw := _intent_facing(action.get("facing"), int(row.facing))
		pawn.show_state(action, yaw, row.get("memory_pose", false), restore)
	elif _uses_general_casts(pawn) and restore and row.get("boss_pending") is Dictionary:
		_prepare_general_cast(pawn, row, true)


func _prepare_gap(pawn: Node3D, row: Dictionary, restore: bool) -> void:
	var pending: Dictionary = row.melee_pending
	var cells_locked: Array = pending.get("cells", [])
	var vector: Vector3 = Vector3.ZERO if cells_locked.is_empty() else _world(_at(cells_locked[0])) - pawn.destination
	var yaw := _intent_facing(pending.get("facing"), int(row.facing)) if vector.length_squared() < 0.0001 else _yaw(vector)
	pawn.prepare_gap(str(pending.id), yaw, reduced, restore)


func _prepare_bow(pawn: Node3D, row: Dictionary, restore: bool) -> void:
	var pending: Dictionary = row.bow_pending
	var locked: Array = pending.get("cells", [])
	var yaw: float = _intent_facing(pending.get("facing"), int(row.facing)) \
		if locked.is_empty() else pawn.aim_bearing(_world(_at(locked[-1])), true)
	if pawn is Mg02:
		pawn.apply_boss_event("prepare", str(pending.id), yaw, reduced, restore)
	else:
		pawn.prepare_arrow(str(pending.id), yaw, reduced, restore)


func _uses_general_casts(pawn: Variant) -> bool:
	return pawn is Mg03 or pawn is Mg04 or pawn is Demon or pawn is Admin or pawn is En02


func _prepare_general_cast(pawn: Node3D, row: Dictionary, restore: bool) -> void:
	var pending: Dictionary = row.boss_pending
	var yaw := _intent_facing(pending.get("facing"), int(row.facing))
	pawn.apply_boss_event("prepare", str(pending.move_id), str(pending.id), yaw, reduced, restore)


func _cancel_bow(pawn: Bow) -> void:
	if pawn is Mg02:
		pawn.apply_boss_event("cancel", pawn.bow_cast, pawn.heading, reduced)
	else:
		pawn.cancel_arrow(reduced)


func _prepare_targeted(pawn: Node3D, pending: Dictionary, restore: bool) -> void:
	var locked: Array = pending.get("cells", [])
	var point: Vector3 = pawn.destination if locked.is_empty() else _world(_at(locked[0]))
	pawn.prepare_cast(str(pending.id), point, reduced, restore)


func _prepare_hero_skill(pawn: Node3D, row: Dictionary, restore: bool) -> void:
	var pending: Dictionary = row.hero_pending
	var locked: Array = pending.get("cells", [])
	var vector: Vector3 = Vector3.ZERO if locked.is_empty() else _world(_at(locked[0])) - pawn.destination
	var yaw := _intent_facing(pending.get("facing"), int(row.facing)) if vector.length_squared() < 0.0001 else _yaw(vector)
	pawn.prepare_skill(str(pending.get("id", "")), str(pending.get("move_id", "")), yaw, reduced, restore)


func _intent_facing(value: Variant, fallback: int) -> float:
	return _facing(fallback if value == null else int(value))


func _lock_spear(pawn: Node3D, row: Dictionary, id: String, locked: Array, base: Variant, restore: bool) -> void:
	var origin := _world(_at(base if base is Array else row.pos))
	var direction := Vector3.ZERO if locked.is_empty() else _world(_at(locked[0])) - origin
	var yaw := _facing(int(row.facing)) if direction.length_squared() < 0.0001 else _yaw(direction)
	pawn.windup(id, origin, yaw, locked, restore)


func _draw_bone_bow(pawn: Node3D, row: Dictionary, draw: Dictionary, restore: bool) -> void:
	var base: Array = draw.origin if draw.origin is Array else row.pos
	var yaw := _intent_facing(draw.get("facing"), int(row.facing))
	pawn.draw_bow(draw.id, _world(_at(base)), yaw, restore, reduced)


func _apply_relocations(relocated: Dictionary, moved: Dictionary, downs: Dictionary) -> void:
	for id: String in relocated:
		if moved.has(id) or downs.has(id) or not actors.has(id):
			continue
		var token: Dictionary = actors[id]
		if float(token.row.get("hp", 0)) <= 0:
			continue
		var mover: Node3D = token.node
		if reduced:
			mover.snap(mover.destination, mover.heading, false, true)
		else:
			mover.travel(mover.destination, mover.heading)


func _animate(events: Array[Dictionary], by_id: Dictionary, finished: bool, relocated := {}) -> void:
	var downs := {}
	var contacts := {}
	var reactions := {}
	var melee_impacts := {}
	var bow_impacts := {}
	var aid_impacts := {}
	var mist_impacts := {}
	var mist_contacts := {}
	var sting_misses := {}
	var bone_hits := {}
	var bone_misses := {}
	var charges := {}
	for event in events:
		var kind: String = by_id.get(event.get("actor", ""), {}).get("kind", "")
		var profile: Dictionary = Profiles.TARGETED.get(kind, {})
		var effect: String = profile.get("effect", "")
		if event.type == "down":
			downs[event.actor] = event
		elif event.type == "charge_move" and kind == "EN02":
			charges[event.action_id] = event
		elif event.type == "hit" and by_id.get(event.actor, {}).get("kind") == "S02":
			melee_impacts[_attack_key(event)] = event.target
		elif event.type == "hit" and kind in ["S03", "M03", "MG02"]:
			var key := _attack_key(event)
			if not bow_impacts.has(key):
				bow_impacts[key] = []
			bow_impacts[key].append(event.target)
		elif effect == "aid" and (event.type == "hit" \
				or (event.type in ["heal", "skill_miss"] and event.get("move") == profile.move)):
			aid_impacts[_attack_key(event)] = event
		elif effect == "mist" and event.type == "hit" and event.get("action") == profile.move:
			mist_impacts[_attack_key(event)] = event.target
		elif event.type == "skill_miss" and event.get("move") == "EN03-A":
			sting_misses[event.action_id] = true
		elif event.type == "skill_miss" and event.get("move") == "EN22-A":
			bone_misses[event.action_id] = true
		elif event.type == "hit" and by_id.get(event.actor, {}).get("kind") == "EN22":
			var key := _attack_key(event)
			if not bone_hits.has(key):
				bone_hits[key] = []
			bone_hits[key].append(event.target)
	var moved := {}
	for charge in charges.values():
		moved[charge.actor] = true
	for event in events:
		if event.type == "move" and actors.has(event.actor) and not downs.has(event.actor):
			moved[event.actor] = true
			var mover = actors[event.actor].node
			if reduced:
				mover.snap(mover.destination, mover.heading, false, true)
			else:
				mover.travel(_world(_at(event.position)), mover.heading)
	if not relocated.is_empty():
		_apply_relocations(relocated, moved, downs)
	for event in events:
		if event.type in ["basic_start", "release"] and actors.has(event.actor):
			var source = actors[event.actor].node
			if source is Echo and not downs.has(event.actor):
				if event.type == "release" and event.get("move") == "EN06-A":
					source.release_echo()
					audit.echo_releases[event.action_id] = {"actor": event.actor, "cells": event.get("cells", [])}
				elif event.type == "basic_start":
					source.pulse()
			elif source is Wasp and not downs.has(event.actor):
				if event.type == "release" and event.get("move") == "EN03-A":
					contacts[_attack_key(event)] = _sting_shot(source, event, sting_misses.has(event.action_id))
				elif event.type == "basic_start":
					source.pulse()
			elif source is Mimic and not downs.has(event.actor):
				source.pulse()
				if event.type == "release":
					audit.mimic_releases += 1
			elif source is DualSac and event.type == "release" and event.get("move") == "EL02-A" and not downs.has(event.actor):
				source.release_root(_intent_facing(event.get("facing"), int(by_id[event.actor].facing)))
			elif source is RingGuard and event.type == "basic_start" and not downs.has(event.actor):
				source.strike()
			elif source is SkeletonEnemy and not downs.has(event.actor):
				if source.archer and (event.type == "basic_start" or event.get("move") == "EN22-A"):
					var key := _attack_key(event)
					contacts[key] = _bone_arrow_shot(source, event, by_id, bone_hits.get(key, []), bone_misses.has(event.action_id))
				elif not source.archer and event.type == "basic_start":
					source.swing()
			elif source is Ado and not downs.has(event.actor):
				var row: Dictionary = by_id[event.actor]
				source.attack(str(event.get("move", "")), _intent_facing(event.get("facing"), int(row.facing)))
	for event in events:
		var id: String = event.get("actor", "")
		if by_id.get(id, {}).get("kind") == "MG01":
			_ado_effect(event, by_id[id])
		elif not downs.has(id):
			var skeleton_enemy = actors.get(id, {}).get("node")
			if skeleton_enemy is SkeletonEnemy and event.type == "private_shield":
				skeleton_enemy.raise_blade()
			elif skeleton_enemy is SkeletonEnemy and event.type == "windup" and event.get("move") == "EN22-A":
				var row: Dictionary = by_id[id]
				var draw: Dictionary = row.get("bone_pending", {})
				if draw.get("id") == event.action_id:
					_draw_bone_bow(skeleton_enemy, row, draw, false)
	for event in events:
		var skill: bool = event.get("move") == "S02-A"
		var piercing: bool = event.get("move") in ["S03-A", "M03-A"]
		var source_row: Dictionary = by_id.get(event.get("actor", ""), {})
		var profile: Dictionary = Profiles.TARGETED.get(source_row.get("kind", ""), {})
		var targeted_skill: bool = not profile.is_empty() and event.get("move") == profile.move
		var actor_node: Variant = actors.get(event.get("actor", ""), {}).get("node")
		var event_move := str(event.get("move", ""))
		var sev_skill: bool = actor_node is Mg02 and event_move in Mg02.MG02_MOVES
		var source_kind: String = source_row.get("kind", "")
		var general_skill: bool = event_move in GENERAL_CAST_MOVES.get(source_kind, []) \
			or (source_kind == "DEMON" and Demon.supports_move(event_move))
		if event.type in ["hero_interrupt", "hero_stun_cancel"]:
			var cancelled_id: String = event.target if event.type == "hero_interrupt" else event.actor
			var cancelled = actors.get(cancelled_id, {}).get("node")
			if cancelled is Mg02 and cancelled.bow_cast == event.get("cast_id", ""):
				_cancel_bow(cancelled)
			elif _uses_general_casts(cancelled) and not cancelled.active_cast.is_empty() \
					and cancelled.active_cast == event.get("cast_id", ""):
				cancelled.apply_boss_event("cancel", cancelled.active_move, cancelled.active_cast, cancelled.heading, reduced)
		if (sev_skill or general_skill) and event.type == "boss_private_shield" and not downs.has(event.actor):
			_mark(event.actor, source_row.pos, "护盾 +%d" % int(event.amount), true)
		# mimic_start describes the same cast as windup. Only windup starts its pose.
		if general_skill and event.type == "windup" and _uses_general_casts(actor_node) \
				and source_row.get("boss_pending", {}).get("id") == event.action_id:
			_prepare_general_cast(actor_node, source_row, false)
		if general_skill and event.type == "skill_miss":
			_mark(event.actor, source_row.pos, "放空", false)
		var hero_skill: bool = actor_node is Hero and (event_move.begins_with("H") or event_move.begins_with("CMD-"))
		if hero_skill:
			if event.type == "windup" and by_id[event.actor].get("hero_pending", {}).get("id") == event.action_id:
				_prepare_hero_skill(actor_node, by_id[event.actor], false)
			elif event.type == "skill_miss":
				_mark(event.actor, by_id[event.actor].pos, "放空", false)
		if skill and actors.has(event.actor):
			if event.type == "windup" and by_id[event.actor].get("melee_pending", {}).get("id") == event.action_id:
				_prepare_gap(actors[event.actor].node, by_id[event.actor], false)
			elif event.type == "release":
				audit.melee_skill_releases += 1
			elif event.type == "skill_miss":
				audit.melee_skill_misses += 1
				_mark(event.actor, by_id[event.actor].pos, "放空", false)
		if (piercing or sev_skill) and event.type == "windup" and actors.has(event.actor) \
				and by_id[event.actor].get("bow_pending", {}).get("id") == event.action_id:
			_prepare_bow(actors[event.actor].node, by_id[event.actor], false)
		if event.type == "skill_miss" and event.get("move") == "M03-A" and actors.has(event.actor):
			_mark(event.actor, by_id[event.actor].pos, "放空", false)
		if targeted_skill and actor_node is Targeted:
			var pending: Dictionary = source_row.get(actor_node.pending_field, {})
			if event.type == "windup" and pending.get("id") == event.action_id:
				_prepare_targeted(actor_node, pending, false)
			elif actor_node.effect == "mist" and event.type == "skill_miss":
				_mark(event.actor, source_row.pos, "放空", false)
		var skill_release: bool = event.type == "release" and (skill or piercing or targeted_skill or hero_skill or sev_skill or general_skill)
		var attack: bool = event.type == "basic_start" or skill_release
		if attack and actors.has(event.actor) and actors[event.actor].node is Actor:
			var attacker = actors[event.actor].node
			var key := _attack_key(event)
			if attacker is Bow:
				if sev_skill and event_move != "MG02-A":
					var locked: Array = event.get("cells", [])
					var bearing: float = _intent_facing(event.get("facing"), int(source_row.facing)) if locked.is_empty() \
						else attacker.aim_bearing(_world(_at(locked[-1])), true)
					contacts[key] = attacker.apply_boss_event("release", event.action_id, bearing, reduced)
				else:
					contacts[key] = _bow_shot(attacker, event, by_id, bow_impacts.get(key, []), piercing or sev_skill)
				continue
			if attacker is Targeted and attacker.effect == "aid":
				contacts[key] = _aid_shot(attacker, event, by_id, aid_impacts.get(key, {}), targeted_skill)
				continue
			if attacker is Targeted and attacker.effect == "mist" and targeted_skill:
				var hit: String = mist_impacts.get(key, "")
				contacts[key] = _mist_shot(attacker, event, by_id, hit)
				mist_contacts[str(event.actor) + "/" + hit] = contacts[key]
				continue
			if downs.has(event.actor):
				continue
			if attacker is Hero and hero_skill and event.type == "release":
				var hmove := str(event.get("move", ""))
				var htarget: Dictionary = by_id.get(event.get("target"), {})
				var hcells: Array = event.get("cells", [])
				var hvec := Vector3.ZERO
				if not htarget.is_empty():
					hvec = _world(_at(htarget.pos)) - attacker.destination
				elif not hcells.is_empty():
					hvec = _world(_at(hcells[0])) - attacker.destination
				var hyaw: float = _intent_facing(event.get("facing"), int(by_id[event.actor].facing)) if hvec.length_squared() < 0.0001 else _yaw(hvec)
				contacts[key] = attacker.release_skill(str(event.get("action_id", "")), hmove, hyaw, _emit_attack_contact, reduced)
				audit.hero_skills[str(event.get("action_id", key))] = {"actor": event.actor, "kind": attacker.hero_kind, "move": hmove}
				continue
			var target: Dictionary = by_id.get(melee_impacts.get(key, event.get("target")), {})
			var direction: Vector3 = Vector3.ZERO if target.is_empty() else _world(_at(target.pos)) - attacker.destination
			var yaw: float = attacker.heading if direction.length_squared() < 0.0001 else _yaw(direction)
			var contact := _emit_attack_contact if not attacker is Melee or melee_impacts.has(key) else Callable()
			if attacker is En02:
				if general_skill:
					var movement: Dictionary = charges.get(event.action_id, {})
					var landing: Vector3 = attacker.position if movement.is_empty() else _world(_at(movement.position))
					var charge_yaw := _intent_facing(event.get("facing"), int(source_row.facing))
					contacts[key] = attacker.release_charge(charge_yaw, landing, reduced)
				elif not reduced and attacker.active_cast.is_empty() and not attacker.shell_seam:
					contacts[key] = attacker.attack(yaw, contact)
			elif _uses_general_casts(attacker):
				if general_skill:
					yaw = _intent_facing(event.get("facing"), int(source_row.facing))
				contacts[key] = attacker.apply_boss_event("release" if general_skill else "attack",
					event_move, str(event.get("action_id", "")), yaw, reduced)
			elif skill:
				contacts[key] = attacker.release_gap(event.action_id, yaw, contact, reduced)
			elif not reduced:
				contacts[key] = attacker.attack(yaw, contact)
	var spear_marks := _spear_events(events, by_id, downs, contacts, finished)
	var guards := {}
	for event in events:
		if event.type not in ["shared_shield", "guard_redirect"] or downs.has(event.actor):
			continue
		var guard = actors.get(event.actor, {}).get("node")
		if not guard is RingGuard:
			continue
		if event.type == "shared_shield":
			guard.raise_shield()
		else:
			guards[event.actor] = true
			var lag := float(contacts.get(str(event.attacker) + "/" + str(event.action_id), 0.0))
			if lag > 0.0:
				_defer(lag, guard.brace)
			else:
				guard.brace()
	for event in events:
		if event.type != "hit" or not by_id.has(event.target):
			continue
		var lag := float(contacts.get(_attack_key(event), 0.0))
		var damaged := int(event.get("actual_hp_damage", 0))
		var absorbed := int(event.get("absorbed", 0))
		if (damaged > 0 or absorbed > 0) and (actors.has(event.actor) or actors.has(event.target)):
			var label := "护盾吸收" if damaged == 0 else "−%d" % damaged
			if event.get("action") == "M01-A" and spear_marks.has(str(event.actor) + "/" + str(event.target)):
				label += " · 受阻"
			if lag > 0:
				_defer(lag, _mark.bind(event.target, by_id[event.target].pos, label, damaged == 0))
			else:
				_mark(event.target, by_id[event.target].pos, label, damaged == 0)
		if downs.has(event.target):
			downs[event.target]["lag"] = maxf(float(downs[event.target].get("lag", 0.0)), lag)
		elif actors.has(event.target) and actors[event.target].node is Actor and damaged > 0:
			var clip := Actor.BLOCK if event.get("front_guard", false) else Actor.HIT
			if not reactions.has(event.target) or clip == Actor.BLOCK:
				reactions[event.target] = {"clip": clip, "lag": lag}
		elif damaged > 0 and not guards.has(event.target) and actors.has(event.target) \
				and (actors[event.target].node is Mimic or actors[event.target].node is DualSac \
					or actors[event.target].node is Ado or actors[event.target].node is RingGuard):
			var reaction: Callable = actors[event.target].node.impact
			if lag > 0.0:
				_defer(lag, reaction)
			else:
				reaction.call()
	for event in events:
		if event.type == "cast_delayed" and by_id.has(event.target):
			audit.mist_delays[event.cast_id] = {"actor": event.actor, "target": event.target,
				"release_tick": event.release_tick}
			var delay := float(mist_contacts.get(str(event.actor) + "/" + str(event.target), 0.0))
			var show_delay := _mark.bind(event.target, by_id[event.target].pos, "延咒", false)
			if delay > 0.0:
				_defer(delay, show_delay)
			else:
				show_delay.call()
	for id in reactions:
		var pawn: Node3D = actors[id].node
		var lag: float = reactions[id].lag
		if _uses_general_casts(pawn):
			var hit: Callable = pawn.apply_boss_event.bind("hit", "", "", pawn.heading, reduced)
			if lag > 0.0:
				_defer(lag, hit)
			else:
				hit.call()
		else:
			pawn.react(reactions[id].clip, lag, reduced)
	for id in downs:
		if actors.has(id):
			var pawn = actors[id].node
			var delay := float(downs[id].get("lag", 0.0))
			if _uses_general_casts(pawn):
				pawn.active_cast = ""
				pawn.active_move = ""
			if pawn is Actor:
				pawn.react(Actor.DOWN, delay, reduced)
			else:
				if pawn is Echo:
					audit.echo_downs += 1
				elif pawn is Wasp:
					audit.wasp_downs += 1
				elif pawn is Mimic:
					audit.mimic_downs += 1
				elif pawn is Ado:
					audit.ado_downs += 1
				elif pawn is Spear and pawn.enemy:
					audit.enemy_spear_downs += 1
				var down: Callable = pawn.snap.bind(pawn.destination, pawn.heading, true, reduced)
				if delay > 0.0:
					_defer(delay, down)
				else:
					down.call()


func _bow_shot(pawn: Node3D, event: Dictionary, by_id: Dictionary, hit_targets: Array, piercing: bool) -> float:
	var locked: Array = event.get("cells", [])
	var crossbow := pawn is Crossbow
	var target: Variant = hit_targets[0] if not hit_targets.is_empty() else event.get("target")
	var use_locked_end := piercing and not locked.is_empty() and (not crossbow or hit_targets.is_empty())
	var grid: Variant = locked[-1] if use_locked_end else by_id.get(target, {}).get("pos")
	var has_endpoint: bool = grid is Array and cells.has(Vector2i(int(grid[0]), int(grid[1])))
	var landing: Vector3 = _world(_at(grid)) + Vector3.UP * 1.0 if has_endpoint else pawn.destination
	var bearing: float = pawn.aim_bearing(landing, piercing)
	var sev := pawn is Mg02
	var release_lag: float = pawn.apply_boss_event("release" if piercing else "attack",
		event.action_id, bearing, reduced) if sev else pawn.fire(bearing, piercing, reduced)
	var shots: Dictionary = audit.sev_shots if sev else (audit.crossbow_shots if crossbow else audit.bow_shots)
	shots[event.action_id] = {"actor": event.actor, "target": target, "hits": hit_targets, "cells": locked}
	if not has_endpoint:
		return release_lag
	var start: Vector3 = pawn.arrow_origin()
	var delta := landing - start
	var direction := Vector2(delta.x, delta.z).normalized()
	shots[event.action_id]["aim_dot"] = direction.dot(pawn.release_axis())
	if reduced or (crossbow and piercing and hit_targets.is_empty()):
		return release_lag
	var duration := clampf(start.distance_to(landing) / 21.0, 0.06, 0.20)
	var launch := _launch_bolt.bind(pawn.arrow_mesh, start, landing, duration, piercing) if crossbow \
		else _launch_arrow.bind(pawn.arrow_mesh, start, landing, duration)
	if release_lag > 0:
		_defer(release_lag, launch)
	else:
		launch.call()
	return release_lag + duration


func _launch_bolt(mesh: Mesh, start: Vector3, landing: Vector3, duration: float, start_at_tip: bool) -> void:
	var nose := mesh.get_aabb().end.z
	var direction := (landing - start).normalized()
	if direction.length_squared() < 0.9 or nose <= 0.0:
		return
	audit.crossbow_flights += 1
	_launch_projectile(mesh, start - direction * (nose if start_at_tip else 0.0), landing, duration, nose, false)


func _launch_arrow(mesh: Mesh, start: Vector3, landing: Vector3, duration: float) -> void:
	var axis := (landing - start).normalized()
	if axis.length_squared() < 0.9 or absf(axis.y) > 0.98:
		return
	if spare_projectiles.is_empty():
		audit.bow_flight_meshes_created += 1
	audit.bow_flights += 1
	_launch_projectile(mesh, start, landing, duration, 0.49, false)


func _bone_arrow_shot(pawn: Node3D, event: Dictionary, by_id: Dictionary, hits: Array, missed: bool) -> float:
	var locked: bool = event.get("move") == "EN22-A"
	var path: Array = event.get("cells", [])
	var target: Dictionary = by_id.get(event.get("target", ""), {})
	var grid: Array = target.get("pos", [])
	var blocker: String = event.get("blocked_by", "")
	var aim: float = pawn.rotation.y
	if locked:
		grid = event.get("flight_stop", [])
		if not hits.is_empty() and blocker.is_empty():
			grid = by_id[hits.back()].pos
	elif not grid.is_empty():
		var direction: Vector3 = _world(_at(grid)) - pawn.destination
		if direction.length_squared() > 0.0001:
			aim = _yaw(direction)
	var delay: float = pawn.release_arrow(event.action_id, aim, locked, reduced)
	if delay < 0.0 or grid.is_empty():
		return maxf(delay, 0.0)
	var landing := _world(_at(grid)) + Vector3.UP * (0.12 if missed and blocker.is_empty() else 0.95)
	if not blocker.is_empty():
		var line: Vector3 = landing - pawn.destination
		landing -= Vector3(line.x, 0.0, line.z).normalized() * 0.23
	var duration := 0.0 if reduced else clampf(pawn.position.distance_to(landing) / 23.0, 0.08, 0.20)
	if locked:
		audit.bone_arrows[event.action_id] = {"cells": path, "landing": grid, "hits": hits, "miss": missed, "blocked_by": blocker}
	if not reduced:
		var locked_origin: Vector3 = pawn.arrow_origin() if locked else Vector3.INF
		_defer(delay, _launch_bone_arrow.bind(pawn, locked_origin, landing, duration))
	if missed:
		var marker := _mark.bind(str(event.action_id), grid, "放空" if blocker.is_empty() else "受阻", false)
		if reduced:
			marker.call()
		else:
			_defer(delay + duration, marker)
	return delay + duration


func _launch_bone_arrow(pawn: Node3D, locked_origin: Vector3, landing: Vector3, duration: float) -> void:
	if not is_instance_valid(pawn):
		return
	if bone_arrow_visual == null:
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("e8d6a1")
		bone_arrow_visual = CylinderMesh.new()
		bone_arrow_visual.top_radius = 0.0
		bone_arrow_visual.bottom_radius = 0.034
		bone_arrow_visual.height = BONE_ARROW_NOSE * 2.0
		bone_arrow_visual.radial_segments = 8
		bone_arrow_visual.rings = 1
		bone_arrow_visual.material = material
	var start: Vector3 = pawn.arrow_origin() if locked_origin == Vector3.INF else locked_origin
	audit.bone_arrow_flights += 1
	_launch_projectile(bone_arrow_visual, start, landing, duration, BONE_ARROW_NOSE, true)


func _launch_projectile(mesh: Mesh, start: Vector3, landing: Vector3, duration: float, nose: float, local_y: bool) -> void:
	var axis := (landing - start).normalized()
	if axis.length_squared() < 0.9:
		return
	var shaft: MeshInstance3D
	if spare_projectiles.is_empty():
		shaft = MeshInstance3D.new()
		shaft.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		viewport_3d.add_child(shaft)
	else:
		shaft = spare_projectiles.pop_back()
	if shaft.mesh != mesh:
		shaft.mesh = mesh
	var up := Vector3.FORWARD if absf(axis.y) > 0.98 else Vector3.UP
	shaft.look_at_from_position(start - axis * (nose if local_y else 0.0), landing, up, true)
	if local_y:
		shaft.rotate_object_local(Vector3.RIGHT, PI / 2.0)
	shaft.show()
	flying_projectiles.append(shaft)
	var flight := shaft.create_tween()
	projectile_tweens[shaft] = flight
	flight.tween_property(shaft, "position", landing - axis * nose, duration)
	flight.tween_callback(func() -> void:
		projectile_tweens.erase(shaft)
		flying_projectiles.erase(shaft)
		shaft.hide()
		spare_projectiles.append(shaft)
	)


func _sting_mesh() -> CylinderMesh:
	if sting_visual == null:
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("ffcb77")
		sting_visual = CylinderMesh.new()
		sting_visual.top_radius = 0.0
		sting_visual.bottom_radius = 0.055
		sting_visual.height = STING_NOSE * 2.0
		sting_visual.radial_segments = 6
		sting_visual.rings = 1
		sting_visual.cap_top = false
		sting_visual.material = material
	return sting_visual


func _sting_shot(pawn: Node3D, event: Dictionary, missed: bool) -> float:
	pawn.release_sting()
	var lock: Array = event.get("cells", [])
	var delivery := {"actor": event.actor, "cells": lock, "missed": missed}
	audit.sting_releases[event.action_id] = delivery
	if lock.size() != 1:
		return 0.0
	var grid: Array = lock[0]
	if not cells.has(Vector2i(int(grid[0]), int(grid[1]))):
		return 0.0
	var landing := _world(_at(grid)) + Vector3.UP * (0.10 if missed else 0.86)
	var start: Vector3 = pawn.sting_origin()
	var duration := 0.0
	if not reduced and start.distance_squared_to(landing) > 0.0001:
		duration = clampf(start.distance_to(landing) / 18.0, 0.12, 0.22)
		audit.sting_flights += 1
		_launch_projectile(_sting_mesh(), start, landing, duration, STING_NOSE, true)
	delivery["travel_seconds"] = duration
	if missed:
		var show_miss := _mark.bind(str(event.action_id), grid, "放空", false)
		if duration > 0.0:
			_defer(duration, show_miss)
		else:
			show_miss.call()
	return duration


func _aid_shot(pawn: Node3D, event: Dictionary, by_id: Dictionary, impact: Dictionary, medical: bool) -> float:
	var target: Variant = impact.get("target", event.get("target"))
	var grid: Variant = by_id.get(target, {}).get("pos")
	var valid := grid is Array and cells.has(Vector2i(int(grid[0]), int(grid[1])))
	var landing: Vector3 = _world(_at(grid)) + Vector3.UP * 0.92 if valid else pawn.destination
	var delay: float = pawn.release_cast(landing, reduced)
	var outcome: String = impact.get("type", "")
	var healed := int(impact.get("effective", 0))
	var report := {"actor": event.actor, "target": target, "medical": medical,
		"outcome": outcome, "effective": healed}
	audit.aid_actions[event.action_id] = report
	if outcome == "skill_miss":
		_mark(event.actor, by_id[event.actor].pos, "放空", false)
		return delay
	if not valid or (medical and outcome != "heal"):
		return delay
	var start: Vector3 = pawn.cast_origin()
	var direction := Vector2(landing.x - start.x, landing.z - start.z).normalized()
	if target != event.actor:
		report["aim_dot"] = direction.dot(pawn.cast_axis())
	if not reduced:
		var duration := clampf(start.distance_to(landing) / 18.0, 0.07, 0.22)
		var capsule := _aid_capsule(medical)
		_defer(delay, func() -> void:
			audit.aid_flights += 1
			_launch_projectile(capsule, start, landing, duration, 0.065, true)
		)
		delay += duration
	if healed > 0:
		var show_contact := func() -> void:
			audit.aid_contacts += 1
			_mark(target, grid, "", false, true)
		if delay > 0.0:
			_defer(delay, show_contact)
		else:
			show_contact.call()
	return delay


func _aid_capsule(medical: bool) -> Mesh:
	if not aid_capsules.has(medical):
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("7ef0c1") if medical else Color("ffc18b")
		var capsule := SphereMesh.new()
		capsule.material = material
		capsule.radius = 0.022
		capsule.height = 0.13
		capsule.radial_segments = 10
		capsule.rings = 6
		aid_capsules[medical] = capsule
	return aid_capsules[medical]


func _mist_shot(pawn: Node3D, event: Dictionary, by_id: Dictionary, hit: String) -> float:
	var target: Variant = event.get("target") if hit.is_empty() else hit
	var grid: Variant = by_id.get(target, {}).get("pos")
	var valid := grid is Array and cells.has(Vector2i(int(grid[0]), int(grid[1])))
	var landing: Vector3 = _world(_at(grid)) + Vector3.UP * 1.0 if valid else pawn.destination
	var delay: float = pawn.release_cast(landing, reduced)
	var report := {"actor": event.actor, "target": target, "hit": hit}
	audit.mist_casts[event.action_id] = report
	if not valid or hit.is_empty():
		return delay
	var start: Vector3 = pawn.cast_origin()
	var direction := Vector2(landing.x - start.x, landing.z - start.z).normalized()
	report["aim_dot"] = direction.dot(pawn.cast_axis())
	if reduced:
		return delay
	if mist_visual == null:
		var material := StandardMaterial3D.new()
		material.albedo_color = Color("c3a7e6")
		mist_visual = SphereMesh.new()
		mist_visual.material = material
		mist_visual.radius = 0.068
		mist_visual.height = 0.136
		mist_visual.radial_segments = 10
		mist_visual.rings = 6
	var duration := clampf(start.distance_to(landing) / 15.0, 0.08, 0.24)
	_defer(delay, func() -> void:
		audit.mist_flights += 1
		_launch_projectile(mist_visual, start, landing, duration, 0.0, false)
	)
	return delay + duration


func _ado_effect(event: Dictionary, actor: Dictionary) -> void:
	var move_id: String = event.get("move", "")
	match event.type:
		"windup":
			audit.ado_windups[move_id] = int(audit.ado_windups.get(move_id, 0)) + 1
		"boss_private_shield":
			audit.ado_shields += 1
		"release":
			audit.ado_releases += 1
			audit.ado_moves[move_id] = int(audit.ado_moves.get(move_id, 0)) + 1
			var key: String = event.event_id
			var cells_to_mark: Array = event.get("cells", [])
			audit.ado_cues.append({"move": move_id, "cells": cells_to_mark, "tick": event.tick})
			if cells_to_mark.is_empty():
				return
			ado_traces[key] = {"move": move_id, "origin": actor.pos, "cells": cells_to_mark}
			queue_redraw()
			_defer(0.31, func():
				ado_traces.erase(key)
				queue_redraw())


func _spear_events(events: Array[Dictionary], by_id: Dictionary, downs: Dictionary, contacts: Dictionary, finished: bool) -> Dictionary:
	var blocks := {}
	var release_point := {}
	for event in events:
		var id: String = event.target if event.type == "hero_interrupt" else event.get("actor", "")
		var pawn = actors.get(id, {}).get("node")
		if not pawn is Spear:
			continue
		match event.type:
			"windup":
				if not finished and not downs.has(id):
					var row: Dictionary = by_id[id]
					_lock_spear(pawn, row, event.action_id, event.cells, row.get("spear_pending", {}).get("origin"), false)
					if pawn.enemy:
						audit.enemy_spear_windups += 1
					else:
						audit.spear_windups += 1
			"release":
				var cells: Array = pawn.lock_cells.duplicate()
				var contact: float = pawn.resolve(event.action_id, false)
				if contact >= 0.0:
					contacts[_attack_key(event)] = contact
					release_point[_attack_key(event)] = cells.back() if not cells.is_empty() else by_id[id].pos
					if pawn.enemy:
						audit.enemy_spear_releases[event.action_id] = {"actor": id, "cells": cells}
					else:
						audit.spear_releases += 1
			"hero_stun_cancel", "hero_interrupt":
				if pawn.resolve(str(event.get("cast_id", "")), true) >= 0.0:
					audit.spear_cancels += 1
			"skill_miss":
				var key := _attack_key(event)
				if release_point.has(key):
					if pawn.enemy:
						audit.enemy_spear_misses += 1
					else:
						audit.spear_misses += 1
					var feedback := _mark.bind(id, release_point[key], "放空", false)
					if contacts[key] > 0.0:
						_defer(contacts[key], feedback)
					else:
						feedback.call()
			"hit":
				if event.get("action") == "M01-A":
					audit.spear_hits += 1
				elif event.get("action") == "EN17-A":
					audit.enemy_spear_hits += 1
			"movement_block":
				blocks[id + "/" + str(event.target)] = event.until
	for event in events:
		if event.type == "hit" and event.get("action") == "M01-A" and blocks.has(str(event.actor) + "/" + str(event.target)):
			audit.spear_blocks += 1
	return blocks


func _attack_key(event: Dictionary) -> String:
	return str(event.actor) + "/" + str(event.get("action_id", ""))


func _emit_attack_contact() -> void:
	audit.contacts += 1


func _count_clip(clip: String) -> void:
	audit.clips[clip] = int(audit.clips.get(clip, 0)) + 1


func _defer(seconds: float, callback: Callable) -> void:
	timers = timers.filter(func(timer: Tween) -> bool: return timer.is_valid())
	var timer := create_tween()
	timer.tween_interval(seconds)
	timer.tween_callback(callback)
	if focused_pause:
		timer.pause()
	timers.append(timer)


func _mark(id: String, pos: Array, label: String, absorbed: bool, healed := false) -> void:
	if absorbed:
		audit.absorptions += 1
	var stamp := Time.get_ticks_usec()
	var color := Color("7ef0c1") if healed else Color("a9d8e1") if absorbed else Color("ffc092")
	if label == "延咒":
		color = Color("ddbeff")
	marks[id] = {"pos": pos, "label": label, "color": color, "stamp": stamp}
	queue_redraw()
	_defer(0.42, func() -> void:
		if marks.get(id, {}).get("stamp") == stamp:
			marks.erase(id)
			queue_redraw()
	)


func _draw() -> void:
	for trace in ado_traces.values():
		_draw_ado_trace(trace)
	var mark_font := get_theme_default_font()
	for id: String in marks:
		var mark: Dictionary = marks[id]
		var color: Color = mark.color
		draw_circle(_at(mark.pos), 19, color, false, 2, true)
		var label: String = mark.label
		if mark_font != null and (label == "放空" or label.ends_with("受阻")):
			var text := "受阻" if label.ends_with("受阻") else label
			var anchor := head_pixel(id)
			if anchor == Vector2.INF:
				anchor = _at(mark.pos) + Vector2(0.0, -38.0)
			var text_size := mark_font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16)
			var pill := Rect2(anchor - Vector2(text_size.x * 0.5 + 6.0, text_size.y + 8.0),
				Vector2(text_size.x + 12.0, text_size.y + 4.0))
			pill.position = pill.position.clamp(Vector2(10.0, 10.0), (size - pill.size - Vector2(10.0, 10.0)).max(Vector2(10.0, 10.0)))
			draw_rect(pill, Color(0.08, 0.12, 0.11, 0.88))
			draw_rect(pill, Color(color, 0.75), false, 1.0)
			var baseline := pill.position.y + (pill.size.y + mark_font.get_ascent(16) - mark_font.get_descent(16)) * 0.5
			draw_string(mark_font, Vector2(pill.position.x + 6.0, baseline), text,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 16, color)


func _draw_ado_trace(trace: Dictionary) -> void:
	var color := Color("e6a467") if trace.move == "MG01-A" else Color("cab3d3")
	var origin := _at(trace.origin)
	for grid in trace.cells:
		var point := _at(grid)
		draw_arc(point, 13, 0, TAU, 20, color, 2.0, true)
		if reduced:
			continue
		if trace.move == "MG01-C":
			var axis := (point - origin).normalized()
			draw_line(point - axis * 11, point + axis * 11, color, 2.2, true)
		else:
			draw_arc(point, 16, PI * 0.1, PI * 0.85, 15, color, 2.5, true)

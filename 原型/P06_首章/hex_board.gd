extends Control

signal cell_selected(cell: Vector2i)
signal deployment_dropped(id: String, cell: Vector2i)
signal deployment_selected(id: String)
signal deployment_withdrawn(id: String)
signal battle_actor_selected(id: String)
signal route_site_selected(id: String)
signal overlook_requested()

const OVERLOOK_INSPECTION := "overlook-inspection"
signal town_shortcut_selected(key: String)

const ShieldStage = preload("res://shield_stage.gd")
const TownGround = preload("res://town_ground.gd")
const OverlookGround = preload("res://overlook_ground.gd")
const FORTRESS_COURT_ART := {
	"B1": "res://assets/fortress/watch_ink_court.png",
	"B2": "res://assets/fortress/flank_ink_court.png",
	"G": "res://assets/fortress/keep_ink_court.png",
	"L": "res://assets/fortress/trench_ink_court.png",
}
const GRAY_OAK_FIELD_ART := {
	"A": "res://assets/gray_oak/approach_ink_field.png",
	"G": "res://assets/gray_oak/rootmouth_ink_field.png",
}
const GRAY_OAK_ROUTE_FIELDS := {
	"B1": "res://assets/gray_oak/shallow_bay_ink.png",
	"B2": "res://assets/gray_oak/north_gap_ink.png",
	"G": "res://assets/gray_oak/watchtower_gate_ink.png",
}
const TOWN_YARD_ART := "res://assets/town/muster_yard_ink.png"
const TRANSFER_YARD_ART := "res://assets/town/transfer_yard_ink.png"
const WETLAND_FIELD_ART := {
	"B1": "res://assets/wetland/dry_island_ink.png",
	"B2": "res://assets/wetland/tidal_yard_ink.png",
	"G": "res://assets/wetland/north_levee_ink.png",
}
const REGION_ROUTE_ART := {
	"RG01": "res://assets/gray_oak/route_ink_map.png",
	"RG02": "res://assets/fortress/route_ink_map.png",
	"RG07": "res://assets/wetland/route_ink_map.png",
}
var map_data: Dictionary = {}
var slice: Dictionary = {}
var danger: Dictionary = {}
var font: Font
var coordinate_map: Dictionary = {}
var selected_id := ""
var battle_focus_id := ""
var contact_enemy_id := ""
var impacts: Dictionary = {}
var impact_font_size := 15
var show_models := true
var show_spear := true
var stage: Control
var _scale := 24.0
var _center := Vector2.ZERO
var _presentation: Dictionary = {}
var _layout_cells: Array = []
var _layout_size := Vector2(-1, -1)
var _layout_sideways := false
var _layout_town_yard := false
var _layout_deployment := false
var _overlook_width := 0.0
var _overlook_art: Texture2D
var _terrain: Control
var _units: Control
var _unit_labels: Node2D
var _overlay: Control
var _contact_badges: Dictionary = {}
var _danger_cells: Dictionary = {}
var _danger_areas: Array[Dictionary] = []
var _drawn_warning_keys: Array[Dictionary] = []
var _pressed_battle_actor := ""
var _field_art: Texture2D
var _route_art: Texture2D
var _prepared_field_art := ""
var field_art_timings: Array[Dictionary] = []
var _unit_markers: Dictionary = {}
var unit_marker_draws := 0
var unit_label_draws := 0
var _badge_widths := {14: {}, 15: {}, 19: {}}
var _show_deployment := false
var deployment_open := false:
	set(value):
		deployment_open = value
		if not value:
			cancel_deployment_drag()
var deployment_target: Callable
var reserve_zone: PanelContainer
var _reserve_label: Label
var _reserve_style: StyleBoxFlat
var _drop_cell := Vector2i(999, 999)
var _drop_allowed := false
var _battle_hover_cell := Vector2i(999, 999)
var _deploy_hover_cell := Vector2i(999, 999)
var _drag_label: Label
var _deployment_drag: Variant = null
var _discard_drag_release := false
var _pointer := Vector2.ZERO
var _terrain_state: Array = []
var _battle_mode := false
var _gray_oak_field := false
var _sideways := false
var _town := true
var _town_yard := false
var _town_landmarks: Dictionary = {}
var _town_shortcuts: Dictionary = {}
var _town_buttons: Dictionary = {}
var _last_battle_map: Dictionary = {}
var _last_live_battle := ""
var _terminal_version := -1
var _version := -1
var _hold: Tween
var _motion_reduced := false
var _restore_pose := false
var _geometry_refresh_pending := false
var _paused := false
var _route_input := false
var _route_hover := ""
var _route_press := ""

const TEXT := Color("e9dbc0")
const MUTED := Color("98ada5")
const ACCENT := Color("e7bd75")
const DANGER := Color("f6a073")
const WATER_TERRAIN_STYLES := {
	"SHALLOW_WATER": {"surface": Color("82947e"), "ripple": Color("d2c5a0"), "label": "浅水"},
	"DEEP_WATER": {"surface": Color("405e6b"), "ripple": Color("8aa3a5"), "label": "深水"},
	"FIXED_BRIDGE": {"surface": Color("a3815f"), "label": "木桥"},
}
const HEX_VERTICES := [Vector2i(0, 2), Vector2i(-1, 1), Vector2i(-1, -1),
	Vector2i(0, -2), Vector2i(1, -1), Vector2i(1, 1)]
const HEX_NEIGHBORS := [Vector2i(-1, 1), Vector2i(-1, 0), Vector2i(0, -1),
	Vector2i(1, -1), Vector2i(1, 0), Vector2i(0, 1)]
const TOWN_SHORTCUT_HEIGHTS := {"muster": 2.0, "store": 1.72, "departure-gate": 1.92}
const GRAY_OAK_LANDMARKS := {
	"B_SUPPORT": "SM_RG01_SupportLedger.glb",
	"C": "SM_RG01_RestBench.glb",
	"D": "SM_RG01_PatrolStone.glb"
}
const GRAY_OAK_FOOTPRINTS := {
	"battle-wall": Vector2(1.08, 0.20), "battle-fence": Vector2(1.02, 0.16), "battle-root": Vector2(0.80, 0.18)
}
const GRAY_OAK_PROP_POINTS := {
	"A": {"wall": Vector2(0.19, 0.32), "fence": Vector2(0.62, 0.32), "root": Vector2(0.91, 0.35)},
	"G": {"wall": Vector2(0.19, 0.39), "fence": Vector2(0.61, 0.39), "root": Vector2(0.90, 0.41)},
}
const SITE_LABELS := {"I": "入口", "A": "林道", "B_SUPPORT": "护运", "B_MATERIAL": "材料",
	"C": "歇脚", "D": "远眺", "G": "根口", "X": "归路"}
const FORTRESS_LANDMARKS := {
	"I": "fortress-camp", "B1": "fortress-watch", "S": "fortress-aid",
	"B2": "fortress-palisade", "G": "fortress-gate", "X": "fortress-exit",
	"A": "fortress-ledger-post", "B": "fortress-padding-shed", "C": "fortress-recovery-wall",
	"D": "fortress-shift-door", "L": "fortress-ditch-rampart"
}
const FORTRESS_LABEL_OFFSETS := {"B": Vector2(10, 19), "D": Vector2(-76, -17)}
const FORTRESS_BROKEN_RAMPART: Array[Vector2] = [
	Vector2(0.017, 0.204), Vector2(0.093, 0.196), Vector2(0.111, 0.144), Vector2(0.139, 0.144),
	Vector2(0.150, 0.120), Vector2(0.178, 0.126), Vector2(0.188, 0.160), Vector2(0.211, 0.163),
	Vector2(0.227, 0.202), Vector2(0.298, 0.204), Vector2(0.321, 0.223), Vector2(0.411, 0.237),
	Vector2(0.541, 0.232), Vector2(0.573, 0.211), Vector2(0.612, 0.202), Vector2(0.651, 0.174),
	Vector2(0.691, 0.180), Vector2(0.709, 0.139), Vector2(0.730, 0.171), Vector2(0.763, 0.170),
	Vector2(0.777, 0.200), Vector2(0.811, 0.192), Vector2(0.884, 0.233), Vector2(0.983, 0.223),
	Vector2(0.983, 0.343), Vector2(0.017, 0.343),
]
const GRAY_OAK_CANOPIES := [
	[Vector2(0, 0.33), Vector2(0.09, 0.26), Vector2(0.16, 0.32), Vector2(0.23, 0.38),
		Vector2(0.31, 0.33), Vector2(0.38, 0.41), Vector2(0.47, 0.50), Vector2(0.57, 0.46),
		Vector2(0.66, 0.40), Vector2(0.73, 0.42), Vector2(0.84, 0.27), Vector2(0.91, 0.30), Vector2(1, 0.40)],
	[Vector2(0, 0.58), Vector2(0.059, 0.43), Vector2(0.12, 0.48), Vector2(0.18, 0.40),
		Vector2(0.23, 0.53), Vector2(0.31, 0.58), Vector2(0.39, 0.70), Vector2(0.50, 0.77),
		Vector2(0.62, 0.71), Vector2(0.69, 0.59), Vector2(0.77, 0.52), Vector2(0.86, 0.54),
		Vector2(0.93, 0.45), Vector2(1, 0.52)],
]
const GRAY_OAK_SILHOUETTE := [
	Vector2(-0.13, 0), Vector2(-0.16, -0.32), Vector2(-0.31, -0.47), Vector2(-0.57, -0.51),
	Vector2(-0.73, -0.66), Vector2(-0.62, -0.82), Vector2(-0.45, -0.83), Vector2(-0.34, -0.95),
	Vector2(-0.13, -0.92), Vector2(0.08, -1.0), Vector2(0.28, -0.89), Vector2(0.49, -0.87),
	Vector2(0.69, -0.72), Vector2(0.65, -0.56), Vector2(0.41, -0.49), Vector2(0.22, -0.50),
	Vector2(0.07, -0.33), Vector2(0.12, 0),
]


func update_board(presentation: Dictionary, member_id: String, version: int, reduced: bool, paused: bool,
	show_deployment: bool) -> void:
	if version != _version:
		cancel_deployment_drag()
		_pressed_battle_actor = ""
	_presentation = presentation
	selected_id = member_id
	_version = version
	_show_deployment = show_deployment
	_restore_pose = _restore_pose or _motion_reduced != reduced
	_motion_reduced = reduced
	var pause_changed := _paused != paused
	_paused = paused
	stage.reduced = reduced
	stage.set_paused(paused)
	if pause_changed and _hold != null and _hold.is_valid():
		if paused:
			_hold.pause()
		else:
			_hold.play()
	_refresh()


func _ready() -> void:
	_terrain = Control.new()
	_terrain.name = "Terrain"
	_terrain.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_terrain.show_behind_parent = true
	add_child(_terrain)
	_terrain.draw.connect(_draw_terrain)
	_units = Control.new()
	_units.name = "UnitMarkers"
	_units.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_units)
	stage = ShieldStage.new()
	stage.enabled = show_models
	stage.show_spear = show_spear
	add_child(stage)
	stage.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	stage.geometry_ready.connect(_queue_geometry_refresh)
	_unit_labels = Node2D.new()
	_unit_labels.name = "UnitLabels"
	add_child(_unit_labels)
	_overlay = Control.new()
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_overlay)
	_overlay.draw.connect(_draw_overlay)
	_build_reserve_zone()
	for id: String in TOWN_SHORTCUT_HEIGHTS:
		var button := Button.new()
		button.focus_mode = Control.FOCUS_NONE
		button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		button.pressed.connect(_select_town_shortcut.bind(id))
		button.hide()
		_town_buttons[id] = button
		add_child(button)
	mouse_exited.connect(_clear_drop_hint)
	mouse_exited.connect(_clear_route_hover)
	mouse_exited.connect(_clear_battle_pointer)
	resized.connect(_refresh)
	RenderingServer.frame_pre_draw.connect(_align_unit_markers)


func _queue_geometry_refresh() -> void:
	if not _geometry_refresh_pending:
		_geometry_refresh_pending = true
		_refresh_geometry.call_deferred()


func _refresh_geometry() -> void:
	if _geometry_refresh_pending:
		_refresh()


func _refresh() -> void:
	_geometry_refresh_pending = false
	if stage.window_hidden:
		_restore_pose = true
		return
	slice = _presentation.get("slice", {})
	var frame: Variant = slice.get("battle_view")
	var snapshot: Dictionary = frame if frame is Dictionary else {}
	var phase: String = slice.get("phase", "")
	var profile_contact: bool = stage.profile_assets and phase == "EXPLORE" and _show_deployment
	var started := Time.get_ticks_usec() if profile_contact else 0
	var projected: Dictionary = _presentation.get("map") if _presentation.get("map") is Dictionary else {}
	if phase == "BATTLE" and projected.is_empty() and not slice.get("rescue_board", []).is_empty():
		projected = {"battle_cells": slice.rescue_board}
	if phase == "BATTLE" and not snapshot.is_empty():
		_last_live_battle = snapshot.id
		_last_battle_map = projected
		_terminal_version = -1
	elif not snapshot.is_empty() and snapshot.get("finished", false) and _last_live_battle == snapshot.id:
		_last_live_battle = ""
		if stage.is_ready:
			_terminal_version = _version
			if _hold != null and _hold.is_valid():
				_hold.kill()
			_hold = create_tween()
			_hold.tween_interval(0.45 if _motion_reduced else 1.95)
			_hold.tween_callback(_end_terminal)
			if _paused:
				_hold.pause()
	var terminal := _terminal_version >= 0 and _terminal_version == _version
	map_data = _last_battle_map if terminal else projected
	if slice.get("region") == "RG02" and (phase == "EXPLORE" or \
			(phase == "BATTLE" and snapshot.get("encounter") == "BATTLE-MG01")):
		stage.prefetch_ado()
	if stage.battle_id.is_empty():
		var upcoming: Array = snapshot.get("actors", []) if phase == "BATTLE" else map_data.get("enemy_preview", [])
		if phase == "EXPLORE" and slice.get("tutorial_area", false):
			stage.prepare_gray_oak()
		elif not stage.mimic_warmed and upcoming.any(func(actor): return actor.get("kind") == "EN01"):
			stage.prepare_mimic()
		if not stage.echo_warmed and upcoming.any(func(actor): return actor.get("kind") == "EN06"):
			stage.prepare_creature("EN06")
		if not stage.wasp_warmed and upcoming.any(func(actor): return actor.get("kind") == "EN03"):
			stage.prepare_creature("EN03")
		if not stage.skeletons_warmed and upcoming.any(func(actor): return actor.get("kind") in ["EN21", "EN22"]):
			stage.prepare_skeletons()
	if phase == "TOWN":
		for member in slice.get("party", []):
			if member.unit_id == "M01":
				stage.prepare_spear()
				break
	var layout_started := Time.get_ticks_usec() if profile_contact else 0
	danger = _presentation.get("danger") if _presentation.get("danger") is Dictionary else {}
	if terminal:
		slice = slice.duplicate()
		slice["actors"] = snapshot.actors
	_town = map_data.is_empty()
	_town_yard = _town and phase in ["TOWN", "RETURNED", "FAILED", "FIN_C"]
	_battle_mode = terminal or phase == "BATTLE" or slice.get("route", {}).get("contact_pending", false)
	_gray_oak_field = _battle_mode and not _town and slice.get("tutorial_return", false)
	var route_path: String = REGION_ROUTE_ART.get(slice.get("region"), "")
	if _route_art != null and (_town or _route_art.resource_path != route_path):
		_route_art = null
	var art_path := _field_art_path(str(slice.get("site", ""))) if _battle_mode and not _town else ""
	if _town_yard:
		art_path = TOWN_YARD_ART
	elif not _town and not _battle_mode and phase == "EXPLORE":
		art_path = route_path
	if art_path != (_field_art.resource_path if _field_art != null else ""):
		_field_art = _load_site_art(art_path)
		if not route_path.is_empty() and art_path == route_path:
			# Keep the current region's chart across its contact and battle views.
			_route_art = _field_art
	_sideways = _battle_mode or _town_yard
	_layout()
	var overlook_path := OverlookGround.art_path(_root_cleared()) if _overlook_width > 53.0 else ""
	if overlook_path != (_overlook_art.resource_path if _overlook_art != null else ""):
		_overlook_art = _load_site_art(overlook_path)
	_layout_danger_cells()
	if _route_input:
		_set_route_hover(_route_at(get_local_mouse_position()))
	elif slice.get("phase") != "BATTLE" or not slice.get("battle_memory", {}).is_empty():
		_clear_battle_pointer()
	if not _show_deployment:
		_deploy_hover_cell = Vector2i(999, 999)
	var terrain_state := [size, _town, _battle_mode, _sideways, art_path, slice.get("region"), slice.get("site"),
		phase == "MISSING_SEARCH", _show_deployment, _gray_oak_field, _layout_cells, _deployment_cells(),
		_overlook_width, overlook_path, impact_font_size]
	var terrain_changed := terrain_state != _terrain_state
	var same_ado_field: bool = not terrain_changed and phase == "BATTLE" \
		and snapshot.get("encounter") == "BATTLE-MG01" and snapshot.id == stage.battle_id
	stage.set_geometry(coordinate_map, _scale, _sideways)
	var deployment: Array = slice.get("party", []) if _show_deployment else []
	var enemies: Array = map_data.get("enemy_preview", []) if _show_deployment else []
	_layout_contact_badges(enemies)
	if contact_enemy_id.is_empty() and not stage.contact_occluders.is_empty():
		stage.inspect_contact_enemy("")
	var actors_started := Time.get_ticks_usec() if profile_contact else 0
	stage.apply(snapshot if phase == "BATTLE" or terminal else {}, _restore_pose, deployment, enemies)
	if not contact_enemy_id.is_empty():
		stage.inspect_contact_enemy(contact_enemy_id)
	reserve_zone.visible = _show_deployment
	if _show_deployment:
		var spent := 0
		var reserves := 0
		for member in deployment:
			if member.deployed:
				spent += int(member.cost)
			else:
				reserves += 1
		_reserve_label.text = "部署 %d/%d  ·  预备 %d 人\n拖到这里撤下" % [spent, int(slice.budget.battle), reserves]
	var scenery_started := Time.get_ticks_usec() if profile_contact else 0
	if not same_ado_field:
		if _town_yard:
			_town_landmarks = _town_scenery()
			stage.set_scenery(_town_landmarks)
		elif slice.get("region", "") == "RG02":
			stage.set_scenery(_fortress_scenery())
		else:
			stage.set_scenery(_gray_oak_scenery())
	var markers_started := Time.get_ticks_usec() if profile_contact else 0
	if _town_yard or not _town_shortcuts.is_empty():
		_position_town_shortcuts()
	_restore_pose = false
	if terrain_changed:
		_terrain_state = terrain_state
		_terrain.queue_redraw()
	queue_redraw()
	_sync_unit_markers()
	_overlay.queue_redraw()
	if profile_contact:
		stage.contact_timings.append({"version": _version, "started_usec": started,
			"prepare_usec": layout_started - started, "layout_usec": actors_started - layout_started,
			"actors_usec": scenery_started - actors_started, "scenery_usec": markers_started - scenery_started,
			"markers_usec": Time.get_ticks_usec() - markers_started,
			"models": stage.actors.size(), "markers": _unit_markers.size(),
			"scenery_updates": stage.audit.scenery_updates})


func _align_unit_markers() -> void:
	if stage.battle_id.is_empty() or stage.window_hidden:
		return
	for id in _unit_markers:
		var marker: Dictionary = _unit_markers[id]
		if marker.root == null or not stage.actors.has(id):
			continue
		var position_3d: Vector3 = stage.actors[id].node.global_position
		if marker.root != position_3d:
			marker.root = position_3d
			marker.node.position = stage.foot_pixel(id)
			marker.label.position = marker.node.position


func _end_terminal() -> void:
	_hold = null
	_terminal_version = -1
	_refresh()


func reset_battle_presentation() -> void:
	if _hold != null and _hold.is_valid():
		_hold.kill()
	_hold = null
	_last_live_battle = ""
	_last_battle_map = {}
	_terminal_version = -1
	stage.clear_battle()


func _layout() -> void:
	var rows: Array = []
	if slice.get("phase") != "MISSING_SEARCH":
		rows = slice.get("town_board_cells", []) if _town else map_data.get("battle_cells" if _battle_mode else "cells", [])
	var at_overlook: bool = not _town and not _battle_mode and slice.get("phase") == "EXPLORE" \
		and slice.get("tutorial_area", false) and slice.get("site") == "D"
	var overlook_width := size.x * 0.42 if at_overlook else 0.0
	if size == _layout_size and rows == _layout_cells and _layout_sideways == _sideways \
			and _layout_town_yard == _town_yard and _layout_deployment == _show_deployment \
			and _overlook_width == overlook_width:
		return
	coordinate_map.clear()
	_layout_size = size
	_layout_sideways = _sideways
	_layout_town_yard = _town_yard
	_layout_deployment = _show_deployment
	_layout_cells = rows
	_overlook_width = overlook_width
	if _layout_cells.is_empty():
		return
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for row in _layout_cells:
		var point := _grid(float(row["q"]), float(row["r"]))
		low = low.min(point)
		high = high.max(point)
	var span := high - low
	var middle := Vector2.ZERO
	if _sideways:
		var available_width := size.x - 36.0
		var top_y := size.y * (0.36 if _town_yard else 0.24)
		var bot_pad := 76.0 if _show_deployment else 38.0
		var bot_y := maxf(top_y + 40.0, size.y - bot_pad)
		var sin_pitch := sin(ShieldStage.SIDE_PITCH)
		_scale = maxf(1.0, minf(56.0, minf(available_width / (span.x + 2.0), (bot_y - top_y) / (span.y + 2.0 * sin_pitch))))
		middle = Vector2(size.x * 0.5, (top_y + bot_y) * 0.5)
	else:
		var available_width := size.x - _overlook_width - (108.0 if at_overlook else 130.0)
		_scale = maxf(1.0, minf(37.0, minf(available_width / (span.x + 3), (size.y - 126) / (span.y + 3))))
		middle = Vector2((size.x + _overlook_width) * 0.5, (size.y - 38) * 0.5)
	_center = middle - (low + high) * 0.5 * _scale
	for row in _layout_cells:
		var cell := Vector2i(int(row["q"]), int(row["r"]))
		coordinate_map[cell] = _point([cell.x, cell.y])


func _overlook_bounds() -> Rect2:
	var width := maxf(0.0, minf(_overlook_width - 53.0, (size.y - 98.0) * OverlookGround.FRAME.aspect()))
	var extent := Vector2(width, width / OverlookGround.FRAME.aspect())
	return Rect2(Vector2((_overlook_width - width) * 0.5, (size.y - 43.0 - extent.y) * 0.5), extent)


func _root_cleared() -> bool:
	return "G" in slice.get("route", {}).get("cleared", [])


func _town_scenery() -> Dictionary:
	if coordinate_map.is_empty():
		return {}
	var prop_scale := minf(0.87, minf(size.x / 930.0, size.y / 670.0)) * (ShieldStage.MAP_UNIT_SCALE / ShieldStage.SIDE_UNIT_SCALE)
	if _field_art != null:
		var frame := _field_art_rect()
		return {
			"muster": _field_prop("town-muster", frame.position + Vector2(0.26, 0.44) * frame.size, 0.19, prop_scale),
			"store": _field_prop("town-store", frame.position + Vector2(0.51, 0.39) * frame.size, 0.08, prop_scale),
			"departure-gate": _field_prop("town-gate", frame.position + Vector2(0.77, 0.40) * frame.size, -0.13, prop_scale),
		}
	var rear := _backdrop_y() + 16.0
	return {
		"muster": _field_prop("town-muster", Vector2(size.x * 0.26, rear + 14), 0.19, prop_scale),
		"store": _field_prop("town-store", Vector2(size.x * 0.51, rear - 36), 0.08, prop_scale),
		"departure-gate": _field_prop("town-gate", Vector2(size.x * 0.77, rear), -0.13, prop_scale),
		"town-house": _field_prop("town-house", Vector2(size.x * 0.35, rear - 48), 0.24, prop_scale * 0.74, true),
		"town-fence-left": _field_prop("town-fence", Vector2(size.x * 0.14, rear - 7), 0.24, prop_scale * 0.78, true),
		"town-fence-right": _field_prop("town-fence", Vector2(size.x * 0.86, rear - 11), -0.21, prop_scale * 0.76, true),
	}


func set_town_shortcuts(shortcuts: Dictionary) -> void:
	if shortcuts == _town_shortcuts:
		return
	_town_shortcuts = shortcuts
	_position_town_shortcuts()


func _position_town_shortcuts() -> void:
	for id in _town_buttons:
		var button: Button = _town_buttons[id]
		var entry: Dictionary = _town_shortcuts.get(id, {})
		var landmark: Dictionary = _town_landmarks.get(id, {})
		button.visible = _town_yard and not entry.is_empty() and not landmark.is_empty()
		if not button.visible:
			continue
		button.text = entry.label
		button.tooltip_text = entry.description
		button.disabled = entry.disabled
		button.size = button.get_combined_minimum_size().max(Vector2(108, 34))
		var anchor: Vector2 = landmark.pixel
		var height: float = TOWN_SHORTCUT_HEIGHTS[id] * landmark.scale
		anchor.y -= height * _scale * ShieldStage.unit_scale(_sideways) * cos(ShieldStage.SIDE_PITCH)
		button.position = Vector2(clampf(anchor.x - button.size.x / 2.0, 16.0, size.x - button.size.x - 16.0),
			maxf(18.0, anchor.y - button.size.y - 5.0))


func _select_town_shortcut(id: String) -> void:
	if _town_yard and _town_shortcuts.has(id):
		town_shortcut_selected.emit(_town_shortcuts[id].key)


func _gray_oak_scenery() -> Dictionary:
	if _gray_oak_field:
		return _gray_oak_battle_props()
	if _town or coordinate_map.is_empty() or not slice.get("tutorial_area", false):
		return {}
	var props := {}
	for entry in map_data.get("objects", []):
		if not GRAY_OAK_LANDMARKS.has(entry.id) or not entry.get("visible", false):
			continue
		var pin := _point(entry.position)
		var pixel := Vector2(clampf(pin.x - 27, 28, size.x - 28), clampf(pin.y + 1, 25, size.y - 60))
		props[entry.id] = _field_prop(GRAY_OAK_LANDMARKS[entry.id], pixel, 0.18, maxf(1.0, 26.0 / (_scale * 1.52)))
	return props


func _gray_oak_battle_props() -> Dictionary:
	if coordinate_map.is_empty():
		return {}
	var back := _backdrop_y()
	var wall := Vector2(size.x * 0.21, back)
	var fence := Vector2(size.x * 0.70, back + 8)
	var root := Vector2(size.x * 0.86, back + 28)
	var points: Dictionary = GRAY_OAK_PROP_POINTS.get(slice.get("site"), {})
	if _field_art != null and not points.is_empty():
		var frame := _field_art_rect()
		wall = frame.position + Vector2(points.wall) * frame.size
		fence = frame.position + Vector2(points.fence) * frame.size
		root = frame.position + Vector2(points.root) * frame.size
	return {
		"battle-wall": _field_prop("SM_Wall_Short.glb", wall, 0.17, 1.20),
		"battle-fence": _field_prop("SM_Fence_TiltedEnd.glb", fence, -0.27, 1.20),
		"battle-root": _field_prop("SM_Root_Forked.glb", root, 0.17, 1.20),
	}


func _fortress_scenery() -> Dictionary:
	if _town or coordinate_map.is_empty():
		return {}
	var pieces := {}
	if not _battle_mode:
		for entry in map_data.get("objects", []):
			if not FORTRESS_LANDMARKS.has(entry.id):
				continue
			var offset := Vector2(-33, 6)
			if entry.id in ["A", "B"]:
				offset = Vector2(25, 29) if entry.id == "A" else Vector2(24, -9)
			var pixel := (_point(entry.position) + offset).clamp(Vector2(30, 43), size - Vector2(30, 52))
			var pixels_per_unit := 16.0 if entry.id == "G" else 18.0
			pieces[entry.id] = _field_prop(FORTRESS_LANDMARKS[entry.id], pixel, 0.24, pixels_per_unit / (_scale * 1.52))
		return pieces
	for row in _layout_cells:
		if row.get("terrain_id") == "HIGH_OBSTACLE":
			var grid := Vector2i(int(row.q), int(row.r))
			pieces["masonry-%d-%d" % [grid.x, grid.y]] = _field_prop("fortress-rubble", coordinate_map[grid], 0.2 * grid.y, 0.98)
	return pieces


func _backdrop_y() -> float:
	var top := INF
	for point: Vector2 in coordinate_map.values():
		top = minf(top, point.y)
	return maxf(size.y * 0.22, top - _scale * 0.95)


func _field_prop(asset: String, pixel: Vector2, yaw: float, visual_scale := 1.0, backdrop := false) -> Dictionary:
	return {"asset": asset, "pixel": pixel, "yaw": yaw, "scale": visual_scale, "backdrop": backdrop}


func _grid(q: float, r: float) -> Vector2:
	return ShieldStage.project_ground(Vector2(1.73205 * (q + r / 2.0), 1.5 * r), _sideways)


func _point(value: Array) -> Vector2:
	return _grid(float(value[0]), float(value[1])) * _scale + _center


static func cell_index(point: Array) -> Vector2i:
	return Vector2i(int(point[0]), int(point[1]))


func _label(at: Vector2, message: String, color: Color, size_px := 15) -> void:
	if font != null:
		draw_string(font, at, message, HORIZONTAL_ALIGNMENT_LEFT, -1, size_px, color)


func _hex(pos: Vector2, radius: float) -> PackedVector2Array:
	var shape := PackedVector2Array()
	for i in range(6):
		var angle := TAU * (float(i) / 6.0 + 0.25)
		shape.append(pos + ShieldStage.project_ground(Vector2(cos(angle), sin(angle)), _sideways) * radius)
	return shape


func _deployment_cells() -> Array:
	if _town:
		return slice.get("town_deploy_cells", [])
	return map_data.get("deploy_cells", []) if slice.get("route", {}).get("contact_pending", false) \
		and slice.get("phase") == "EXPLORE" else []


func _draw_terrain() -> void:
	var rect := Rect2(Vector2.ZERO, size)
	var fortress: bool = not _town and slice.get("region") == "RG02"
	_terrain.draw_rect(rect, Color("252522") if fortress else Color("101d20"))
	if slice.get("phase") == "MISSING_SEARCH":
		return
	if _field_art != null:
		_terrain.draw_texture_rect(_field_art, _field_art_rect(), false)
		if _town_yard:
			TownGround.paint_landmark_lighting(_terrain, _town_landmarks, _scale, show_models)
	elif fortress and _battle_mode:
		_draw_fortress_court()
	elif _gray_oak_field and not coordinate_map.is_empty():
		_draw_gray_oak_field()
	elif _town_yard:
		TownGround.paint(_terrain, size, _town_landmarks, _scale, show_models)
	if _gray_oak_field and show_models:
		_draw_gray_oak_prop_shadows()
	if _field_art == null and not _gray_oak_field and not _town_yard and not (fortress and _battle_mode):
		for y in range(32, int(size.y), 36):
			for x in range(24, int(size.x), 40):
				_terrain.draw_circle(Vector2(x, y), 1.0, Color("3b382f") if fortress else Color("233335"))
	if _overlook_width > 53.0:
		OverlookGround.paint(_terrain, _overlook_bounds(), _root_cleared(), font, _overlook_art, impact_font_size > 15)
	var painted_field := _field_art != null and not _has_route_art()
	_terrain.draw_rect(rect.grow(-4 if painted_field else -14), Color("554a38") if fortress else Color("314343"), false, 1)
	if _battle_mode:
		if _field_art != null and (slice.get("region") == "RG07" or _field_art.resource_path == GRAY_OAK_ROUTE_FIELDS.B1):
			_draw_water_and_bridges()
		_draw_ground_obstacles(fortress)
	if _show_deployment:
		_draw_deployment_grid(fortress)
		_draw_board_legend("┅ 部署格     拖动队员调整阵位")
	elif not _town and not _battle_mode and slice.get("phase") == "EXPLORE":
		_draw_board_legend("◆ 当前位置     ◉ 可点击的站点", impact_font_size)


func _field_art_path(site: String) -> String:
	if site == "RESCUE":
		return TRANSFER_YARD_ART
	if slice.get("region") == "RG02":
		return FORTRESS_COURT_ART.get(site, "")
	if slice.get("region") == "RG07":
		return WETLAND_FIELD_ART.get(site, "")
	if slice.get("region") == "RG01" and site == "B1":
		return GRAY_OAK_ROUTE_FIELDS.B1
	if slice.get("tutorial_return", false):
		return GRAY_OAK_FIELD_ART.get(site, "")
	return GRAY_OAK_ROUTE_FIELDS.get(site, "") if slice.get("region") == "RG01" else ""


func prepare_field_art(site: String) -> void:
	if site in slice.get("route", {}).get("cleared", []):
		return
	var path := _field_art_path(site)
	if site == "D" and slice.get("tutorial_area", false):
		path = OverlookGround.art_path(_root_cleared())
	if not path.is_empty() and _prepared_field_art.is_empty() \
			and ResourceLoader.load_threaded_request(path, "Texture2D") == OK:
		_prepared_field_art = path


func finish_field_art_prefetch() -> void:
	if not _prepared_field_art.is_empty():
		var started := Time.get_ticks_usec() if stage.profile_assets else 0
		ResourceLoader.load_threaded_get(_prepared_field_art)
		_record_field_art_load(_prepared_field_art, "unused-prefetch", started)
		_prepared_field_art = ""


func _load_site_art(path: String) -> Texture2D:
	if path.is_empty():
		return null
	var started := Time.get_ticks_usec() if stage.profile_assets else 0
	var texture: Texture2D
	if path == _prepared_field_art:
		_prepared_field_art = ""
		texture = ResourceLoader.load_threaded_get(path) as Texture2D
		_record_field_art_load(path, "prefetched", started)
	else:
		var cached := started > 0 and ResourceLoader.has_cached(path)
		texture = load(path) as Texture2D
		_record_field_art_load(path, "cached" if cached else "synchronous", started)
	return texture


func _record_field_art_load(path: String, source: String, started: int) -> void:
	if started > 0:
		field_art_timings.append({"path": path, "source": source, "site": slice.get("site"),
			"region": slice.get("region"), "phase": slice.get("phase"), "version": _version,
			"usec": Time.get_ticks_usec() - started})


func _has_route_art() -> bool:
	return _field_art != null and _field_art.resource_path == REGION_ROUTE_ART.get(slice.get("region"), "")


func _field_art_rect() -> Rect2:
	if _has_route_art():
		return Rect2(Vector2(14, 14), size - Vector2(28, 28))
	return Rect2(Vector2(4, 4), size - Vector2(8, 48 if _show_deployment else 8))


func _draw_board_legend(text: String, font_px := 15) -> void:
	if font != null:
		_terrain.draw_line(Vector2(28, size.y - 43), Vector2(size.x - 28, size.y - 43), Color("554a38"), 1)
		_terrain.draw_string(font, Vector2(30, size.y - 22), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_px, TEXT)


func _draw_ground_obstacles(fortress: bool) -> void:
	for row in _layout_cells:
		var terrain: String = row.get("terrain_id", "")
		var high := terrain == "HIGH_OBSTACLE"
		if not high and terrain != "LOW_OBSTACLE":
			continue
		if high and fortress and show_models:
			continue
		var at: Vector2 = coordinate_map[Vector2i(int(row.q), int(row.r))]
		var extent := Vector2(0.82, 0.34) * _scale if high else Vector2(0.65, 0.20) * _scale
		TownGround.flagstone(_terrain, at + Vector2(0, 3), extent * 1.3, Color("231e19", 0.80))
		if high and _field_art != null and _field_art.resource_path == GRAY_OAK_ROUTE_FIELDS.G:
			_draw_watchtower_rubble(at, extent)
			continue
		TownGround.flagstone(_terrain, at, extent, Color("867564") if high else Color("726658"))


func _draw_watchtower_rubble(at: Vector2, extent: Vector2) -> void:
	TownGround.flagstone(_terrain, at, extent * Vector2(1.12, 1.22), Color("574c3d"))
	TownGround.flagstone(_terrain, at + extent * Vector2(-0.23, -0.14), extent * 0.59, Color("988970"))
	TownGround.flagstone(_terrain, at + extent * Vector2(0.13, -0.42), extent * 0.66, Color("ad9b7d"))
	TownGround.flagstone(_terrain, at + extent * Vector2(0.34, 0.13), extent * 0.38, Color("82745d"))
	TownGround.flagstone(_terrain, at + extent * Vector2(-0.02, 0.25), extent * 0.42, Color("8c7b62"))


func _water_and_bridge_cells() -> Dictionary:
	var terrain_cells := {}
	for row: Dictionary in _layout_cells:
		var terrain: String = row.get("terrain_id", "")
		if WATER_TERRAIN_STYLES.has(terrain):
			if not terrain_cells.has(terrain):
				terrain_cells[terrain] = {}
			terrain_cells[terrain][Vector2i(int(row.q), int(row.r))] = true
	return terrain_cells


func _draw_water_and_bridges() -> void:
	var terrain_cells := _water_and_bridge_cells()
	for depth: String in ["SHALLOW_WATER", "DEEP_WATER"]:
		var water: Dictionary = terrain_cells.get(depth, {})
		var style: Dictionary = WATER_TERRAIN_STYLES[depth]
		for cell: Vector2i in water:
			var point: Vector2 = coordinate_map[cell]
			_terrain.draw_colored_polygon(_hex(point, _scale), Color(style.surface, 0.88))
			var shift := float(posmod(cell.x - cell.y, 3) - 1) * 0.12
			for spacing: float in [-0.12, 0.11]:
				var crest := point + Vector2(shift, spacing) * _scale
				_terrain.draw_line(crest - Vector2(_scale * 0.23, 0), crest + Vector2(_scale * 0.22, -0.9),
					Color(style.ripple, 0.47), 1.35, true)
		for path: PackedVector2Array in _warning_boundary(water):
			path.append(path[0])
			_terrain.draw_polyline(path, Color(style.ripple, 0.48), 1.25, true)
	var bridges: Dictionary = terrain_cells.get("FIXED_BRIDGE", {})
	for cell: Vector2i in bridges:
		_draw_fixed_bridge(cell, bridges)
	if not terrain_cells.is_empty() and font != null:
		_draw_water_and_bridge_key(terrain_cells)


func _draw_fixed_bridge(cell: Vector2i, bridges: Dictionary) -> void:
	var point: Vector2 = coordinate_map[cell]
	# The deck runs along the q axis and joins only its actual axial bridge neighbors.
	var reach := _grid(0.5, 0) * _scale
	var across := ShieldStage.project_ground(Vector2(0, 0.40), _sideways) * _scale
	var start := point - reach * (1.0 if bridges.has(cell - Vector2i.RIGHT) else 0.91)
	var end := point + reach * (1.0 if bridges.has(cell + Vector2i.RIGHT) else 0.91)
	var drop := Vector2(0, _scale * 0.15)
	_terrain.draw_colored_polygon(PackedVector2Array([start - across + drop, end - across + drop,
		end + across + drop * 1.6, start + across + drop * 1.6]), Color("423a31", 0.30))
	_terrain.draw_colored_polygon(PackedVector2Array([start + across, end + across, end + across + drop, start + across + drop]),
		Color("5e4634"))
	_terrain.draw_colored_polygon(PackedVector2Array([start - across, end - across, end + across, start + across]),
		WATER_TERRAIN_STYLES.FIXED_BRIDGE.surface)
	for fraction: float in [0.16, 0.33, 0.49, 0.67, 0.83]:
		var seam := start.lerp(end, fraction)
		_terrain.draw_line(seam - across, seam + across, Color("594637"), 1.3, true)
		_terrain.draw_line(seam - across + reach * 0.07, seam + across + reach * 0.07, Color("c5a481", 0.56), 1.0, true)
	for edge: Vector2 in [-across, across]:
		_terrain.draw_line(start + edge, end + edge, Color("4e4134"), 2.0, true)
	for brace: Vector2 in [start.lerp(end, 0.09), start.lerp(end, 0.91)]:
		_terrain.draw_line(brace - across, brace - across - drop * 0.42, Color("493a30"), 2.8, true)
		_terrain.draw_line(brace + across + drop * 1.35, brace + across - drop * 0.32, Color("493a30"), 3.4, true)
		_terrain.draw_circle(brace + across - drop * 0.33, 1.7, Color("c3a483"), true, -1, true)


func _draw_water_and_bridge_key(terrain_cells: Dictionary) -> void:
	var origin := Vector2(24.0, size.y - (86.0 if _show_deployment else 46.0))
	var height := float(impact_font_size + 17)
	var span := float(impact_font_size * 2 + 38)
	_terrain.draw_rect(Rect2(origin, Vector2(span * terrain_cells.size() + 9.0, height)), Color(0.12, 0.15, 0.135, 0.90))
	var left := origin.x + 9.0
	for terrain: String in WATER_TERRAIN_STYLES:
		if not terrain_cells.has(terrain):
			continue
		var style: Dictionary = WATER_TERRAIN_STYLES[terrain]
		_terrain.draw_rect(Rect2(Vector2(left, origin.y + 9.0), Vector2(17.0, height - 18.0)), style.surface)
		_terrain.draw_string(font, Vector2(left + 24.0, origin.y + height - 9.0), style.label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size, TEXT)
		left += span


func _draw_deployment_grid(fortress: bool) -> void:
	var deployment := _deployment_cells().map(cell_index)
	for row in _layout_cells:
		var cell := Vector2i(int(row["q"]), int(row["r"]))
		var xy: Vector2 = coordinate_map[cell]
		var shape := _hex(xy, _scale * 0.94)
		var can_deploy := cell in deployment
		if can_deploy:
			_terrain.draw_colored_polygon(shape, Color("32675e", 0.52))
		shape.append(shape[0])
		if can_deploy:
			_terrain.draw_polyline(shape, Color(0.05, 0.08, 0.07, 0.55), 2.8, true)
			_terrain.draw_polyline(shape, Color("c2ecd7"), 1.6, true)
		else:
			var edge := Color("8b745c", 0.72) if _field_art != null else Color("b29c78", 0.48) if fortress else Color("b6b197", 0.48)
			_terrain.draw_polyline(shape, edge, 1.1, true)


func _actor_cell(id: String) -> Vector2i:
	if id.is_empty():
		return Vector2i(999, 999)
	var actors: Array = slice.get("actors", [])
	if actors.is_empty():
		actors = slice.get("party", [])
	for actor: Dictionary in actors:
		var actor_id: String = actor.get("instance_id", actor.get("id", ""))
		if actor_id == id:
			if not actor.get("deployed", true):
				return Vector2i(999, 999)
			var grid: Variant = actor.get("pos", actor.get("position"))
			if grid is Array and grid.size() == 2:
				return cell_index(grid)
			return Vector2i(999, 999)
	return Vector2i(999, 999)


func _is_enemy_actor(id: String) -> bool:
	for actor: Dictionary in slice.get("actors", []):
		if actor.get("id", "") == id:
			return actor.get("side") == "enemy"
	return false


func _draw_hex_highlight(canvas: CanvasItem, cell: Vector2i, fill: Color, rim: Color, rim_width := 2.4, halo_alpha := 0.82) -> void:
	if not coordinate_map.has(cell):
		return
	var shape := _hex(coordinate_map[cell], _scale * 0.94)
	if fill.a > 0.0:
		canvas.draw_colored_polygon(shape, fill)
	shape.append(shape[0])
	canvas.draw_polyline(shape, Color(0.05, 0.07, 0.06, halo_alpha), rim_width + 2.8, true)
	canvas.draw_polyline(shape, rim, rim_width, true)


func _draw() -> void:
	if slice.get("phase") == "MISSING_SEARCH":
		return
	if _layout_cells.is_empty():
		_draw_waiting()
		return
	if not _town and not _battle_mode:
		_draw_route()
	if _battle_mode and not _show_deployment and slice.get("battle_memory", {}).is_empty():
		var focused_cell := _actor_cell(battle_focus_id)
		if coordinate_map.has(_battle_hover_cell) and _battle_hover_cell != focused_cell:
			var hover_rim := Color("ffd4a8") if _danger_cells.has(_battle_hover_cell) else Color("d6efe0")
			_draw_hex_highlight(self, _battle_hover_cell, Color(hover_rim, 0.11), Color(hover_rim, 0.85), 2.0, 0.65)
		if coordinate_map.has(focused_cell):
			var focus_rim := Color("ffc48c") if _is_enemy_actor(battle_focus_id) else Color("ffe49e")
			_draw_hex_highlight(self, focused_cell, Color(focus_rim, 0.18), focus_rim, 2.7, 0.88)
	elif _show_deployment:
		var selected_cell := _actor_cell(selected_id)
		if coordinate_map.has(_deploy_hover_cell) and _deploy_hover_cell != selected_cell and _deployment_drag == null:
			_draw_hex_highlight(self, _deploy_hover_cell, Color("b9ebd1", 0.14), Color("daf7e7"), 2.1, 0.72)
		if coordinate_map.has(selected_cell):
			_draw_hex_highlight(self, selected_cell, Color("ffe49e", 0.18), Color("ffe49e"), 2.6, 0.85)
	_draw_danger_ranges(self, false)
	var memory: Dictionary = slice.get("battle_memory", {})
	if memory.is_empty():
		memory = slice.get("hunt", {}).get("memory", {})
	if memory.get("id") == "MG01-W1":
		_draw_whistle()


func _draw_overlay() -> void:
	_draw_danger_ranges(_overlay, true)
	_draw_warning_keys()
	if _battle_mode and not impacts.is_empty() and slice.get("battle_memory", {}).is_empty():
		_draw_combat_impacts()
	if slice.get("phase") == "BATTLE" and slice.get("battle_memory", {}).is_empty() and get_viewport().gui_get_hovered_control() == self:
		_update_battle_cursor(get_local_mouse_position())
	if not _contact_badges.is_empty():
		_draw_contact_badges()
	if _show_deployment and coordinate_map.has(_drop_cell):
		var edge := Color("c6f8df") if _drop_allowed else Color("ff9e78")
		_draw_hex_highlight(_overlay, _drop_cell, Color(edge, 0.30), edge, 2.8, 0.88)


func select_contact_enemy(id: String) -> void:
	contact_enemy_id = id if id != contact_enemy_id and _contact_badges.has(id) else ""
	stage.inspect_contact_enemy(contact_enemy_id)
	_overlay.queue_redraw()


func _layout_contact_badges(enemies: Array) -> void:
	_contact_badges.clear()
	if not enemies.is_empty():
		var plaque := Vector2(40, 22)
		var frame := Rect2(Vector2(18, 20), size - Vector2(36, 65))
		var occupied: Array[Rect2] = []
		for enemy in enemies:
			var cell := cell_index(enemy.position)
			if not coordinate_map.has(cell):
				continue
			var tile: Vector2 = coordinate_map[cell]
			var x := tile.x + 21.0
			if x + plaque.x > frame.end.x:
				x = tile.x - 21.0 - plaque.x
			var position := Vector2(x, tile.y - plaque.y * 0.5)
			position = position.clamp(frame.position, (frame.end - plaque).max(frame.position))
			var rect := Rect2(position, plaque)
			for offset in [0.0, 26.0, -26.0, 52.0, -52.0]:
				var option := Rect2(position + Vector2(0.0, offset), plaque)
				if frame.encloses(option) and not occupied.any(func(previous: Rect2) -> bool: return previous.intersects(option.grow(2))):
					rect = option
					break
			occupied.append(rect)
			_contact_badges[enemy.id] = {"tile": tile, "box": rect, "label": enemy.badge}
	if not _contact_badges.has(contact_enemy_id):
		contact_enemy_id = ""


func _draw_contact_badges() -> void:
	if _contact_badges.has(contact_enemy_id):
		var enemy_cell := _cell_at(_contact_badges[contact_enemy_id].tile)
		_draw_hex_highlight(_overlay, enemy_cell, Color(1.0, 0.70, 0.40, 0.22), Color("ffe1ab"), 2.7, 0.85)
	for id in _contact_badges:
		var row: Dictionary = _contact_badges[id]
		var rect: Rect2 = row.box
		var tile: Vector2 = row.tile
		var active: bool = id == contact_enemy_id
		var ink := Color("ffe1ab") if active else DANGER
		var end_x := rect.position.x if tile.x <= rect.get_center().x else rect.end.x
		_overlay.draw_line(tile, Vector2(end_x, rect.get_center().y), ink, 1.5, true)
		_overlay.draw_circle(tile, 2.3, ink)
		_overlay.draw_rect(rect, Color("594333") if active else Color("241f1d"))
		_overlay.draw_rect(rect, ink, false, 1.3)
		if font != null:
			_overlay.draw_string(font, rect.position + Vector2(8, 16), row.label,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, ink)


func _draw_fortress_court() -> void:
	_draw_fortress_backdrop()
	var outline := PackedVector2Array()
	for anchor in [Vector2(0.095, 0.33), Vector2(0.19, 0.235), Vector2(0.80, 0.235),
		Vector2(0.92, 0.37), Vector2(0.974, 0.68), Vector2(0.87, 0.86),
		Vector2(0.13, 0.86), Vector2(0.031, 0.71)]:
		outline.append(anchor * size)
	var shadow := PackedVector2Array()
	for point in outline:
		shadow.append(point + Vector2(0, 8))
	_terrain.draw_colored_polygon(shadow, Color("1b1c19"))
	_terrain.draw_colored_polygon(outline, Color("393329"))
	outline.append(outline[0])
	_terrain.draw_polyline(outline, Color("655741"), 2.0, true)


func _draw_fortress_backdrop() -> void:
	var sky := Color("303532")
	var horizon := Color("414537")
	var left := 14.0
	var right := size.x - left
	var upper := maxf(left, size.y * 0.176)
	var lower := maxf(upper, size.y * 0.40)
	var clear := Color(horizon, 0.0)
	_terrain.draw_polygon(PackedVector2Array([Vector2(left, left), Vector2(right, left),
		Vector2(right, upper), Vector2(left, upper)]), PackedColorArray([sky, sky, horizon, horizon]))
	_terrain.draw_polygon(PackedVector2Array([Vector2(left, upper), Vector2(right, upper),
		Vector2(right, lower), Vector2(left, lower)]), PackedColorArray([horizon, horizon, clear, clear]))
	TownGround.land(_terrain, size, Color("303930"), FORTRESS_BROKEN_RAMPART)
	TownGround.land(_terrain, size, Color("353d33"), [
		Vector2(0.017, 0.262), Vector2(0.22, 0.254), Vector2(0.44, 0.287), Vector2(0.62, 0.276),
		Vector2(0.79, 0.255), Vector2(0.983, 0.271), Vector2(0.983, 0.339), Vector2(0.017, 0.339)])
	var fade_start := size.y * 0.260
	var fade_end := size.y * 0.337
	var base := Color("252522")
	_terrain.draw_polygon(PackedVector2Array([Vector2(left, fade_start), Vector2(right, fade_start),
		Vector2(right, fade_end), Vector2(left, fade_end)]), PackedColorArray([Color(base, 0.0), Color(base, 0.0), base, base]))
	_terrain.draw_rect(Rect2(left, fade_end, right - left, lower - fade_end), base)


func _draw_gray_oak_field() -> void:
	var upper := _backdrop_y() - _scale * 0.50
	var front := -INF
	for point: Vector2 in coordinate_map.values():
		front = maxf(front, point.y)
	var lower := minf(size.y - 53.0, front + _scale * 0.90)
	var span := Vector2(size.x, lower - upper)
	var origin := Vector2(0, upper)
	_draw_gray_oak_backdrop(upper)
	var edge := PackedVector2Array()
	for point: Vector2 in [Vector2(0.035, 0.66), Vector2(0.064, 0.36), Vector2(0.15, 0.08),
		Vector2(0.29, 0.01), Vector2(0.46, 0.08), Vector2(0.64, 0.0), Vector2(0.84, 0.06),
		Vector2(0.93, 0.23), Vector2(0.967, 0.48), Vector2(0.945, 0.80),
		Vector2(0.80, 0.94), Vector2(0.62, 0.99), Vector2(0.40, 0.94), Vector2(0.21, 1.0), Vector2(0.072, 0.87)]:
		edge.append(origin + point * span)
	_terrain.draw_colored_polygon(edge, Color("374033"))
	edge.append(edge[0])
	_terrain.draw_polyline(edge, Color("4c5340"), 1.5, true)

	var trail := PackedVector2Array()
	for point: Vector2 in [Vector2(0.079, 0.57), Vector2(0.26, 0.47), Vector2(0.45, 0.51),
		Vector2(0.67, 0.41), Vector2(0.88, 0.22), Vector2(0.92, 0.32), Vector2(0.76, 0.53),
		Vector2(0.53, 0.74), Vector2(0.30, 0.66), Vector2(0.067, 0.80)]:
		trail.append(origin + point * span)
	_terrain.draw_colored_polygon(trail, Color("554b36"))


func _draw_gray_oak_prop_shadows() -> void:
	var props := _gray_oak_battle_props()
	for id in props:
		var center: Vector2 = props[id].pixel
		var footprint: Vector2 = GRAY_OAK_FOOTPRINTS[id] * _scale
		var contact := PackedVector2Array()
		for i in range(16):
			var angle := TAU * float(i) / 16.0
			contact.append(center + Vector2(cos(angle), sin(angle)) * footprint)
		_terrain.draw_colored_polygon(contact, Color(0.06, 0.10, 0.08, 0.44))


func _draw_gray_oak_backdrop(upper: float) -> void:
	var inset := Vector2(14, 14)
	var band := Vector2(size.x - 2.0 * inset.x, upper - inset.y)
	if band.x < 2.0 or band.y < 2.0:
		return
	var sky := Color("233130")
	var horizon := Color("424e43")
	var bottom := Color(horizon, 0.0)
	for strip in [0, 1]:
		var start := 0.0 if strip == 0 else 0.74
		var end := 0.74 if strip == 0 else 1.30
		var top_color := sky if strip == 0 else horizon
		var end_color := horizon if strip == 0 else bottom
		_terrain.draw_polygon(PackedVector2Array([inset + Vector2(0, band.y * start),
			inset + Vector2(band.x, band.y * start), inset + Vector2(band.x, band.y * end),
			inset + Vector2(0, band.y * end)]), PackedColorArray([top_color, top_color, end_color, end_color]))
	var shades := [Color("3c4839"), Color("303d30")]
	for i in GRAY_OAK_CANOPIES.size():
		var points := PackedVector2Array()
		var colors := PackedColorArray()
		var shade: Color = shades[i]
		for crest: Vector2 in GRAY_OAK_CANOPIES[i]:
			points.append(inset + band * crest)
			colors.append(shade)
		for edge in [1.0, 0.0]:
			points.append(inset + band * Vector2(edge, 1.21))
			colors.append(Color(shade, 0.0))
		_terrain.draw_polygon(points, colors)
	for side in [-1.0, 1.0]:
		var base := inset + band * Vector2(0.5 + side * 0.386, 1.10)
		var measure := band * Vector2(0.088 * side, 0.76 if side < 0.0 else 0.61)
		var canopy := PackedVector2Array()
		var colors := PackedColorArray()
		for point: Vector2 in GRAY_OAK_SILHOUETTE:
			canopy.append(base + point * measure)
			colors.append(Color(shades[1], clampf(-point.y * 3.5, 0.0, 1.0)))
		_terrain.draw_polygon(canopy, colors)


func _draw_waiting() -> void:
	var origin := size / 2.0 - Vector2(0, 20)
	for radius in [100.0, 73.0, 49.0]:
		draw_arc(origin, radius, 0, TAU, 72, Color("465540"), 1)
	draw_circle(origin, 12, ACCENT)
	draw_line(origin - Vector2(0, 112), origin + Vector2(0, 112), Color("746449"), 1)
	draw_line(origin - Vector2(112, 0), origin + Vector2(112, 0), Color("746449"), 1)
	_label(origin + Vector2(-47, 132), "暮汀 · 入夜", MUTED)


func _draw_whistle() -> void:
	var origin := Vector2(30, 35)
	draw_style_box(_whistle_plate(), Rect2(origin, Vector2(130, 94)))
	var grip := origin + Vector2(32, 54)
	var tip := origin + Vector2(97, 33)
	var span := (tip - grip).normalized()
	var edge := span.orthogonal()
	draw_arc(grip - span * 6, 8, 0, TAU, 20, Color("bc995c"), 2.7, true)
	draw_colored_polygon(PackedVector2Array([grip + edge * 9, tip + edge * 8, tip + span * 3 - edge * 6,
		tip - span * 12 - edge * 8, grip - edge * 9]), Color("b79358"))
	draw_line(grip - edge * 5, tip - span * 13 - edge * 5, Color("e0bc79"), 3.0, true)
	draw_line(grip + span * 22, grip + span * 33, Color("42362a"), 6.0, true)
	draw_polyline(PackedVector2Array([tip - edge * 7, tip - span * 9 - edge * 1, tip - span * 3 + edge * 5]),
		Color("46392b"), 2.5, true)
	_label(origin + Vector2(27, 78), "裂口铜哨", TEXT, 15)


func _whistle_plate() -> StyleBoxFlat:
	var plate := StyleBoxFlat.new()
	plate.bg_color = Color("222722")
	plate.border_color = Color("826d4a")
	plate.set_border_width_all(1)
	plate.set_corner_radius_all(6)
	return plate


func _draw_route() -> void:
	var route: Dictionary = slice.get("route", {})
	var commands: Dictionary = route.get("map_actions", {}) if _route_input else {}
	var here: Variant = slice.get("site")
	var anchors := {}
	for entry in map_data.get("objects", []):
		anchors[entry["id"]] = entry["position"]
		if entry.get("lamp") is Dictionary and entry.get("visible", false):
			var at := _point(entry.position)
			TownGround.flagstone(self, at, Vector2(3.6, 2.7) * _scale, Color("ae804a", 0.15))
			TownGround.flagstone(self, at, Vector2(2.3, 1.65) * _scale, Color("b98a4e", 0.20))
	for link in route.get("links", []):
		if anchors.has(link[0]) and anchors.has(link[1]):
			var a := _point(anchors[link[0]])
			var b := _point(anchors[link[1]])
			var next: String = link[1] if link[0] == here else link[0] if link[1] == here else ""
			if commands.has(next):
				draw_line(a, b, Color("89ad95"), 3.0, true)
			else:
				draw_dashed_line(a, b, Color("988359"), 2.0, 6.0)
	for entry in map_data.get("objects", []):
		var position := _point(entry["position"])
		var reachable := commands.has(entry.id)
		var hover: bool = entry.id == _route_hover
		var edge := Color("b3e6cf") if reachable else Color("92cbb5") if entry.get("cleared", false) else ACCENT
		if reachable:
			draw_circle(position, 14, Color(edge, 0.32 if hover else 0.18), true, -1, true)
		draw_circle(position, 8, Color("111d1e"))
		draw_circle(position, 8, edge, false, 2, true)
		if font != null:
			var label := _route_label(entry)
			var box := _route_label_box(entry.id, position, label)
			if _has_route_art():
				var backing := Color(0.09, 0.08, 0.067, 0.82) if slice.get("region") == "RG02" \
					else Color(0.06, 0.085, 0.07, 0.82)
				draw_rect(box.grow(2.0), backing)
			_label(box.position + Vector2(0, font.get_ascent(impact_font_size)), label,
				edge if hover else TEXT, impact_font_size)
	var player := _point(map_data["position"])
	draw_circle(player, 14, Color("645738"))
	draw_colored_polygon(PackedVector2Array([player+Vector2(0,-9),player+Vector2(7,0),player+Vector2(0,9),player+Vector2(-7,0)]), ACCENT)


func _route_label(entry: Dictionary) -> String:
	if not slice.get("tutorial_area", false):
		return str(entry.get("name", entry.id))
	if entry.id == "D" and slice.get("observation") is Dictionary:
		return "远眺 · 已记录"
	return SITE_LABELS.get(entry.id, entry.id)


func _route_label_box(id: String, anchor: Vector2, label: String) -> Rect2:
	var offset := Vector2(10, -9)
	if slice.get("region") == "RG02":
		offset = FORTRESS_LABEL_OFFSETS.get(id, offset)
	var extent := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size)
	var at := anchor + offset - Vector2(0, font.get_ascent(impact_font_size))
	if at.x + extent.x > size.x - 18:
		at.x = anchor.x - extent.x - 14
	at = at.clamp(Vector2(_overlook_width + 16.0, 16), Vector2(size.x - extent.x - 16, size.y - extent.y - 44))
	return Rect2(at, extent)


func _sync_unit_markers() -> void:
	var actors: Array = slice.get("actors", [])
	if actors.is_empty():
		actors = slice.get("party", [])
	if _show_deployment:
		actors = actors + map_data.get("enemy_preview", [])
	if _layout_cells.is_empty() or (not _town and not _battle_mode) or (_town_yard and not _show_deployment):
		actors = []
	var living_cells := {}
	for actor: Dictionary in actors:
		if float(actor.get("hp", 0)) <= 0 or not actor.get("deployed", true):
			continue
		var grid: Variant = actor.get("pos", actor.get("position"))
		if grid is Array and grid.size() == 2:
			living_cells[cell_index(grid)] = true
	var entries: Array[Dictionary] = []
	for index in range(actors.size()):
		var actor: Dictionary = actors[index]
		var id: String = actor.get("instance_id", actor.get("id", ""))
		var modelled: bool = stage.actors.has(id)
		var down := float(actor.get("hp", 0)) <= 0
		if (down and not modelled) or not actor.get("deployed", true):
			continue
		var grid: Variant = actor.get("pos", actor.get("position"))
		if not grid is Array or grid.size() != 2:
			continue
		var cell := cell_index(grid)
		if not coordinate_map.has(cell):
			continue
		var pos_px: Vector2 = stage.foot_pixel(id) if modelled else _point(grid)
		entries.append({"index": index, "actor": actor, "id": id, "modelled": modelled,
			"down": down, "cell": cell, "pos_px": pos_px})
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a.down != b.down:
			return a.down
		if not is_equal_approx(a.pos_px.y, b.pos_px.y):
			return a.pos_px.y < b.pos_px.y
		return int(a.index) < int(b.index)
	)
	var retained := {}
	var focus := battle_focus_id if slice.get("phase") == "BATTLE" else selected_id
	var radius := clampf(_scale * 0.37, 12.0, 16.0) if _sideways else minf(17.0, _scale * 0.53)
	for entry: Dictionary in entries:
		var actor: Dictionary = entry.actor
		var id: String = entry.id
		var modelled: bool = entry.modelled
		var down: bool = entry.down
		var cell: Vector2i = entry.cell
		var marker: Dictionary = _unit_markers.get(id, {})
		if marker.is_empty():
			var item := Node2D.new()
			var label := Node2D.new()
			marker = {"node": item, "label": label, "appearance": {}, "label_style": {}, "label_box": Rect2(), "label_extent": Rect2()}
			_unit_markers[id] = marker
			label.set_meta("actor_id", id)
			_units.add_child(item)
			_unit_labels.add_child(label)
			item.draw.connect(_draw_unit_marker.bind(id))
			label.draw.connect(_draw_unit_label.bind(id))
		var item: Node2D = marker.node
		if item.get_index() != retained.size():
			_units.move_child(item, retained.size())
			_unit_labels.move_child(marker.label, retained.size())
		retained[id] = true
		var health := clampf(float(actor.hp) / maxf(1.0, float(actor.max_hp)), 0.0, 1.0) if not down and actor.has("max_hp") else -1.0
		var enemy: bool = actor.get("side") == "enemy"
		var appearance := {"modelled": modelled, "down": down, "enemy": enemy, "sideways": _sideways,
			"focused": id == focus, "barrier": not down and int(actor.get("private_shield", actor.get("boss_barrier", 0))) > 0,
			"shared_shield": not down and actor.has("shared_protection"), "radius": radius}
		var label_style := {"enemy": enemy, "modelled": modelled, "down": down, "sideways": _sideways,
			"co_located": down and living_cells.has(cell), "radius": radius,
			"badge": "" if _show_deployment and enemy else actor.get("badge", str(int(entry.index) + 1)),
			"health": health, "badge_font_size": impact_font_size if modelled else 14}
		if marker.appearance != appearance:
			marker.appearance = appearance
			item.queue_redraw()
		if marker.label_style != label_style:
			marker.label_style = label_style
			marker.label.queue_redraw()
		marker.root = stage.actors[id].node.global_position if modelled else null
		item.position = entry.pos_px
		marker.label.position = item.position
	for id in _unit_markers.keys():
		if not retained.has(id):
			var item: Node2D = _unit_markers[id].node
			_units.remove_child(item)
			item.queue_free()
			var label: Node2D = _unit_markers[id].label
			_unit_labels.remove_child(label)
			label.queue_free()
			_unit_markers.erase(id)


static func _enemy_base(point: Vector2, radius: float) -> PackedVector2Array:
	return _enemy_diamond(point, radius, radius)


static func _enemy_diamond(point: Vector2, rx: float, ry: float) -> PackedVector2Array:
	return PackedVector2Array([point + Vector2(0, -ry), point + Vector2(rx, 0),
		point + Vector2(0, ry), point + Vector2(-rx, 0)])


static func _ellipse_points(center: Vector2, rx: float, ry: float, steps := 24) -> PackedVector2Array:
	var points := PackedVector2Array()
	for i in range(steps):
		var angle := TAU * float(i) / float(steps)
		points.append(center + Vector2(cos(angle) * rx, sin(angle) * ry))
	return points


func _draw_unit_marker(id: String) -> void:
	unit_marker_draws += 1
	var marker: Dictionary = _unit_markers[id]
	var item: Node2D = marker.node
	var style: Dictionary = marker.appearance
	var radius: float = style.radius
	var sideways: bool = style.get("sideways", false)
	var ry := radius * 0.64 if sideways else radius
	var rx := radius * 1.05 if sideways else radius
	var ink := DANGER if style.enemy else Color("95dbca")
	var rim := Color(0.54, 0.56, 0.55, 0.42) if style.down else ink
	if style.modelled:
		if sideways:
			var shadow_center := Vector2(0.5, 2.0)
			item.draw_colored_polygon(_ellipse_points(shadow_center, rx * 1.48, ry * 1.45, 20),
				Color(0.05, 0.04, 0.03, 0.10 if style.down else 0.18))
			item.draw_colored_polygon(_ellipse_points(shadow_center, rx * 1.15, ry * 1.15, 20),
				Color(0.04, 0.03, 0.02, 0.15 if style.down else 0.30))
		var base := Color(0.14, 0.15, 0.15, 0.28) if style.down else Color(0.08, 0.12, 0.12, 0.68)
		var poly := _enemy_diamond(Vector2.ZERO, rx, ry) if style.enemy else _ellipse_points(Vector2.ZERO, rx, ry, 24)
		item.draw_colored_polygon(poly, base)
		poly.append(poly[0])
		if not style.down:
			item.draw_polyline(poly, Color(0.06, 0.06, 0.05, 0.72), 3.2, true)
		item.draw_polyline(poly, rim, 1.1 if style.down else 1.7, true)
	elif style.enemy:
		item.draw_colored_polygon(_enemy_diamond(Vector2.ZERO, rx, ry), ink)
	else:
		item.draw_colored_polygon(_ellipse_points(Vector2.ZERO, rx, ry, 24), ink)
	if style.focused:
		for direction in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			var corner := Vector2(direction.x * (rx + 4.0), direction.y * (ry + 4.0))
			var arm := PackedVector2Array([corner - Vector2(direction.x * 7.5, 0), corner,
				corner - Vector2(0, direction.y * 6.5)])
			item.draw_polyline(arm, Color(0.05, 0.06, 0.05, 0.85), 3.8, true)
			item.draw_polyline(arm, Color("ffe29c"), 2.1, true)
	if style.barrier:
		var arc := PackedVector2Array()
		for i in range(17):
			var angle := lerpf(-PI * 0.92, PI * 0.92, float(i) / 16.0)
			arc.append(Vector2(cos(angle) * (rx + 5.0), sin(angle) * (ry + 4.0)))
		item.draw_polyline(arc, Color("d2c7ad"), 2.8, true)
	if style.shared_shield:
		for start in [-PI * 0.17, PI * 0.83]:
			var arc := PackedVector2Array()
			for i in range(7):
				var angle := lerpf(start, start + PI * 0.34, float(i) / 6.0)
				arc.append(Vector2(cos(angle) * (rx + 7.0), sin(angle) * (ry + 5.5)))
			item.draw_polyline(arc, Color("edbe84"), 2.4, true)


func _draw_unit_label(id: String) -> void:
	unit_label_draws += 1
	var marker: Dictionary = _unit_markers[id]
	var item: Node2D = marker.label
	var style: Dictionary = marker.label_style
	var radius: float = style.radius
	var sideways: bool = style.get("sideways", false)
	var down: bool = style.get("down", false)
	marker.label_box = Rect2()
	marker.label_extent = Rect2()
	if style.get("co_located", false):
		return
	var foot_gap := (radius * 0.64 + 1.5) if sideways else (radius + 1.0)
	var gauge_y := foot_gap + (14.0 if style.modelled else 4.0)
	var extent := Rect2()
	if font != null and not style.badge.is_empty():
		var token: String = style.badge
		var px: int = style.badge_font_size
		var widths: Dictionary = _badge_widths[px]
		if not widths.has(token):
			widths[token] = font.get_string_size(token, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x
		var width: float = widths[token]
		var baseline := Vector2(-width * 0.5, 5)
		var color := Color("132221")
		if style.modelled:
			var plate := Rect2(baseline.x - 3.0, foot_gap, width + 6.0, px + 3.0)
			marker.label_box = plate
			extent = plate
			if down:
				item.draw_rect(plate, Color(0.15, 0.15, 0.15, 0.42))
				item.draw_rect(plate, Color(0.56, 0.58, 0.57, 0.30), false, 1.0)
				color = Color(0.70, 0.65, 0.63, 0.56) if style.enemy else Color(0.63, 0.70, 0.68, 0.56)
			else:
				item.draw_rect(plate, Color(0.14, 0.11, 0.09, 0.90))
				var rim := Color("f6a073", 0.48) if style.enemy else Color("95dbca", 0.42)
				item.draw_rect(plate, rim, false, 1.0)
				color = Color("ffd6bd") if style.enemy else Color("cff5e8")
			baseline.y = plate.get_center().y + (font.get_ascent(px) - font.get_descent(px)) * 0.5
			gauge_y = plate.end.y + 2.0
		else:
			extent = Rect2(-radius, -radius, radius * 2.0, radius * 2.0)
		item.draw_string(font, baseline, token, HORIZONTAL_ALIGNMENT_LEFT, -1, px, color)
	if down and style.modelled:
		var width := clampf(radius * 2.35, 26.0, 38.0)
		var gauge := Rect2(-width * 0.5, gauge_y, width, 3.5)
		item.draw_rect(gauge.grow(1.0), Color(0.08, 0.10, 0.10, 0.32))
		item.draw_rect(gauge, Color(0.34, 0.36, 0.36, 0.38))
		extent = extent.merge(gauge.grow(1.0)) if extent.has_area() else gauge.grow(1.0)
	elif style.health >= 0.0:
		var width := clampf(radius * 2.55, 28.0, 42.0)
		var gauge := Rect2(-width * 0.5, gauge_y, width, 5.0)
		item.draw_rect(gauge.grow(1.0), Color("0e1617"))
		item.draw_rect(gauge, Color("455050"))
		item.draw_rect(Rect2(gauge.position, Vector2(width * style.health, gauge.size.y)), DANGER if style.enemy else Color("95dbca"))
		extent = extent.merge(gauge.grow(1.0)) if extent.has_area() else gauge.grow(1.0)
	marker.label_extent = extent


static func impact_text(row: Dictionary) -> String:
	var parts: PackedStringArray = []
	if row.has("ward"):
		parts.append("代受")
	if int(row.get("damage", 0)) > 0:
		parts.append("−%d" % int(row.damage))
	if int(row.get("healed", 0)) > 0:
		parts.append("回复 %d" % int(row.healed))
	if int(row.get("absorbed", 0)) > 0:
		parts.append("抵消 %d" % int(row.absorbed))
	if int(row.get("shared_shield", 0)) > 0:
		parts.append("共享盾 +%d" % int(row.shared_shield))
	if int(row.get("bone_guard", 0)) > 0:
		parts.append("架刀 +%d" % int(row.bone_guard))
	if row.has("delay_until"):
		parts.append("延至第 %d 拍" % int(row.delay_until))
	if row.get("down", false):
		parts.append("倒地")
	return "  ".join(parts)


func _draw_combat_impacts() -> void:
	if font == null:
		return
	var cards: Array[Dictionary] = []
	for actor in slice.get("actors", []):
		var impact: Dictionary = impacts.get(actor.id, {})
		if impact.is_empty() or not coordinate_map.has(cell_index(actor.pos)):
			continue
		var priority := 4 if actor.id == battle_focus_id else 3 if impact.get("down", false) else 1
		var protection := impact.has("ward") or impact.has("shared_shield") or impact.has("bone_guard")
		var support: bool = protection or int(impact.get("healed", 0)) > 0 or int(impact.get("absorbed", 0)) > 0
		var delayed := impact.has("delay_until")
		if priority == 1:
			priority = 3 if delayed or protection else 2 if support else 1
		var ink := DANGER if impact.get("down", false) or not support else Color("b3e6cf")
		if delayed and not impact.get("down", false):
			ink = Color("ddbeff")
		var anchor: Vector2 = stage.head_pixel(actor.id)
		if anchor == Vector2.INF:
			anchor = _point(actor.pos) - Vector2(0.0, _scale * 0.6)
		anchor = anchor.clamp(Vector2(20.0, 24.0), (size - Vector2(20.0, 50.0)).max(Vector2(20.0, 24.0)))
		cards.append({"priority": priority, "anchor": anchor, "ink": ink,
			"text": "%s  %s" % [actor.badge, impact_text(impact)]})
	cards.sort_custom(func(a, b): return a.priority > b.priority)
	var avoid: Array[Rect2] = []
	for key: Dictionary in _drawn_warning_keys:
		avoid.append(key.box.grow(4.0))
	for marker: Dictionary in _unit_markers.values():
		var extent: Rect2 = marker.get("label_extent", marker.label_box)
		if extent.has_area():
			avoid.append(Rect2(marker.label.position + extent.position, extent.size).grow(3.0))
	var occupied: Array[Rect2] = []
	for card in cards:
		if occupied.size() == 3:
			break
		var text: String = card.text
		var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size).x + 14.0
		var height := float(impact_font_size + 10)
		var anchor: Vector2 = card.anchor
		var offsets := [
			Vector2(-width * 0.5, -height - 10.0),
			Vector2(12.0, -height - 8.0),
			Vector2(-width - 12.0, -height - 8.0),
			Vector2(-width * 0.5, -height * 2.0 - 16.0),
			Vector2(14.0, -height * 2.0 - 14.0),
			Vector2(-width - 14.0, -height * 2.0 - 14.0),
			Vector2(20.0, -height * 0.5),
			Vector2(-width - 20.0, -height * 0.5),
		]
		var chosen := Rect2()
		var min_overlap := INF
		for offset: Vector2 in offsets:
			var point := (anchor + offset).clamp(Vector2(18, 14), (size - Vector2(width + 18, height + 44)).max(Vector2(18, 14)))
			var box := Rect2(point, Vector2(width, height))
			if occupied.any(func(prior: Rect2): return prior.grow(3).intersects(box)):
				continue
			var overlap := 0.0
			for obstacle: Rect2 in avoid:
				if box.intersects(obstacle):
					var clip := box.intersection(obstacle)
					overlap += clip.size.x * clip.size.y
			if overlap == 0.0:
				chosen = box
				break
			if overlap < min_overlap:
				min_overlap = overlap
				chosen = box
		if not chosen.has_area():
			continue
		var edge: Color = card.ink
		var pin := anchor.clamp(chosen.position, chosen.end)
		_overlay.draw_line(anchor, pin, Color(edge, 0.72), 1.3, true)
		_overlay.draw_rect(chosen, Color(0.07, 0.12, 0.12, 0.94))
		_overlay.draw_rect(chosen, Color(edge, 0.80), false, 1.3)
		_overlay.draw_string(font, chosen.position + Vector2(7, height - 7), text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size, edge)
		occupied.append(chosen)


static func warning_numbers(current: Dictionary) -> Dictionary:
	var numbers := {}
	for action in current.get("actions", []):
		if action.get("side") == "enemy" and not action.get("locked_cells", []).is_empty():
			numbers[action.action_id] = numbers.size() + 1
	return numbers if numbers.size() > 1 else {}


func _layout_danger_cells() -> void:
	_drawn_warning_keys.clear()
	_danger_cells.clear()
	_danger_areas.clear()
	var numbers := warning_numbers(danger)
	for action in danger.get("actions", []):
		if action["side"] != "enemy":
			continue
		var cells := {}
		var roll_call: bool = action.get("move_id") == "MG01-C"
		for pair in action.get("locked_cells", []):
			var cell := cell_index(pair)
			if not coordinate_map.has(cell):
				continue
			cells[cell] = true
			if not _danger_cells.has(cell):
				_danger_cells[cell] = {"sources": {}, "roll_call": false}
			var mark: Dictionary = _danger_cells[cell]
			mark.sources[action.actor_id] = true
			mark.roll_call = mark.roll_call or roll_call
		if not cells.is_empty():
			_danger_areas.append({"id": action.action_id, "source": action.actor_id, "cells": cells,
				"roll_call": roll_call, "due": int(action.get("due", danger.tick)), "paths": _warning_boundary(cells),
				"number": numbers.get(action.action_id, 0)})


func _warning_boundary(cells: Dictionary) -> Array[PackedVector2Array]:
	# Integer lattice coordinates let adjacent hexes share identical vertices.
	var edges := {}
	for cell: Vector2i in cells:
		var center := Vector2i(2 * cell.x + cell.y, 3 * cell.y)
		for i in range(6):
			if not cells.has(cell + HEX_NEIGHBORS[i]):
				edges[center + HEX_VERTICES[i]] = center + HEX_VERTICES[(i + 1) % 6]
	var paths: Array[PackedVector2Array] = []
	while not edges.is_empty():
		var first: Vector2i = edges.keys().front()
		var at := first
		var path := PackedVector2Array()
		while true:
			var world := Vector2(float(at.x) * sqrt(3.0) * 0.5, float(at.y) * 0.5)
			path.append(_center + ShieldStage.project_ground(world, _sideways) * _scale)
			var next: Vector2i = edges[at]
			edges.erase(at)
			at = next
			if at == first:
				break
		paths.append(path)
	return paths


func _draw_danger_ranges(canvas: CanvasItem, foreground: bool) -> void:
	for area in _danger_areas:
		var focused: bool = area.source == battle_focus_id
		var urgent: bool = area.due - int(danger.tick) <= 1
		var shadow := Color("432930") if area.roll_call else Color("54291f")
		var ink := Color("e0b8dc") if area.roll_call else Color("ef9e6e")
		if focused or urgent:
			ink = ink.lerp(Color("fff0c9"), 0.52)
		var width := 3.0 if focused or urgent else 2.2
		for path: PackedVector2Array in area.paths:
			if foreground:
				# Only short strokes on the near rim go over occupied spaces.
				for i in path.size():
					var start := path[i]
					var end := path[(i + 1) % path.size()]
					var edge := (end - start).normalized()
					var near := -edge.x > 0.45
					if not near and not focused:
						continue
					var a := start.lerp(end, 0.23)
					var b := start.lerp(end, 0.77)
					canvas.draw_line(a, b, shadow if near else Color(shadow, 0.80), width + 3.0 if near else 3.6, true)
					canvas.draw_line(a, b, ink if near else Color(ink, 0.90), width if near else 1.65, true)
				continue
			var outline := PackedVector2Array()
			var bevel := minf(4.5, _scale * 0.12)
			for i in path.size():
				var at := path[i]
				outline.append(at.move_toward(path[posmod(i - 1, path.size())], bevel))
				outline.append(at.move_toward(path[(i + 1) % path.size()], bevel))
			outline.append(outline[0])
			canvas.draw_polyline(outline, shadow, width + 3.0, true)
			canvas.draw_polyline(outline, ink, width, true)


func _warning_key_layout() -> Array[Dictionary]:
	var keys: Array[Dictionary] = []
	if font == null or _danger_areas.size() < 2:
		return keys
	var bounds := Rect2(Vector2(9, 9), size - Vector2(18, 18))
	var height := float(impact_font_size + 7)
	var label_rects: Array[Rect2] = []
	var body_rects: Array[Rect2] = []
	for marker: Dictionary in _unit_markers.values():
		var foot: Vector2 = marker.node.position
		var unit_extent: Rect2 = marker.get("label_extent", marker.label_box)
		if unit_extent.has_area():
			label_rects.append(Rect2(marker.label.position + unit_extent.position, unit_extent.size).grow(3.0))
		if marker.appearance.modelled and not marker.appearance.down:
			var half_w := maxf(14.0, _scale * 0.44)
			var top := _scale * 1.45
			body_rects.append(Rect2(foot - Vector2(half_w, top), Vector2(half_w * 2.0, top)))
	for area: Dictionary in _danger_areas:
		var label := str(area.number)
		var label_size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size)
		var extent := Vector2(maxf(height, label_size.x + 10.0), height)
		var best := -INF
		var placement := {}
		for path: PackedVector2Array in area.paths:
			var count := path.size()
			var signed_area := 0.0
			for i in count:
				var p0 := path[i]
				var p1 := path[(i + 1) % count]
				signed_area += p0.x * p1.y - p1.x * p0.y
			var winding := 1.0 if signed_area >= 0.0 else -1.0
			for i in count:
				var start := path[i]
				var end := path[(i + 1) % count]
				var outward := (end - start).normalized().orthogonal() * winding
				var prev := path[posmod(i - 1, count)]
				var prev_out := (start - prev).normalized().orthogonal() * winding
				var bisector := outward + prev_out
				bisector = bisector.normalized() if bisector.length_squared() > 0.01 else outward
				var anchors := [
					{"pos": (start + end) * 0.5, "dir": outward, "bonus": 2.0},
					{"pos": start, "dir": bisector, "bonus": 0.0},
				]
				for item: Dictionary in anchors:
					var anchor: Vector2 = item.pos
					var dir: Vector2 = item.dir
					for distance: float in [height * 0.78, height * 1.32, height * 1.95, height * 2.60]:
						var box := Rect2(anchor + dir * distance - extent * 0.5, extent)
						if not bounds.encloses(box) or keys.any(func(key: Dictionary) -> bool: return box.grow(4).intersects(key.box)):
							continue
						var score := -22.0 * dir.y - distance * 0.75 + float(item.bonus)
						if label_rects.any(func(rect: Rect2) -> bool: return box.intersects(rect)):
							score -= 500.0
						if body_rects.any(func(rect: Rect2) -> bool: return box.intersects(rect)):
							score -= 180.0
						var box_center := box.get_center()
						for other_area: Dictionary in _danger_areas:
							if other_area.id == area.id:
								continue
							for other_path: PackedVector2Array in other_area.paths:
								if Geometry2D.is_point_in_polygon(box_center, other_path):
									score -= 45.0
									break
						if score > best:
							best = score
							placement = {"id": area.id, "source": area.source, "number": area.number,
								"box": box, "anchor": anchor, "label": label, "text_width": label_size.x}
		if not placement.is_empty():
			keys.append(placement)
	return keys


func _draw_warning_keys() -> void:
	_drawn_warning_keys = _warning_key_layout()
	for key: Dictionary in _drawn_warning_keys:
		var box: Rect2 = key.box
		var focused: bool = key.source == battle_focus_id
		var edge := Color("ffe2a6") if focused else Color("e6bd91")
		var dark := Color("33251e")
		_overlay.draw_line(key.anchor, box.get_center(), dark, 3.2, true)
		_overlay.draw_line(key.anchor, box.get_center(), edge, 1.2, true)
		_overlay.draw_rect(box, edge if focused else dark)
		_overlay.draw_rect(box, dark if focused else edge, false, 1.2)
		var baseline := (box.size.y + font.get_ascent(impact_font_size) - font.get_descent(impact_font_size)) * 0.5
		_overlay.draw_string(font, box.position + Vector2((box.size.x - key.text_width) * 0.5, baseline),
			key.label, HORIZONTAL_ALIGNMENT_LEFT, -1, impact_font_size, dark if focused else TEXT)


func _gui_input(event: InputEvent) -> void:
	if _route_input and not _town and not _battle_mode:
		if event is InputEventMouseMotion:
			_set_route_hover(_route_at(event.position))
		elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
			var site := _route_at(event.position)
			if event.pressed:
				_route_press = site
			else:
				var requested := _route_press
				_route_press = ""
				if not requested.is_empty() and requested == site and not get_viewport().gui_is_dragging():
					if site == OVERLOOK_INSPECTION:
						overlook_requested.emit()
					else:
						route_site_selected.emit(site)
			accept_event()
		return
	if slice.get("phase") == "BATTLE" and slice.get("battle_memory", {}).is_empty():
		if event is InputEventMouseMotion:
			_update_battle_cursor(event.position)
			var next_cell := _cell_at(event.position)
			if next_cell != _battle_hover_cell:
				_battle_hover_cell = next_cell
				queue_redraw()
		elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
			var target := _battle_actor_at(event.position)
			if event.pressed:
				_pressed_battle_actor = target
			else:
				var selected := _pressed_battle_actor
				_pressed_battle_actor = ""
				if not selected.is_empty() and selected == target and not get_viewport().gui_is_dragging():
					battle_actor_selected.emit(selected)
			accept_event()
		return
	if _show_deployment and event is InputEventMouseMotion and _deployment_drag == null:
		var candidate := _cell_at(event.position)
		var next_deploy := candidate if candidate in _deployment_cells().map(cell_index) else Vector2i(999, 999)
		if next_deploy != _deploy_hover_cell:
			_deploy_hover_cell = next_deploy
			queue_redraw()
	if event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if not get_viewport().gui_is_dragging():
			if deployment_open:
				var member := _deployment_member(event.position)
				if not member.is_empty():
					deployment_selected.emit(member)
					accept_event()
					return
			var cell := _cell_at(event.position)
			if coordinate_map.has(cell):
				cell_selected.emit(cell)
				accept_event()


func set_route_input(enabled: bool) -> void:
	if _route_input == enabled:
		return
	_route_input = enabled
	if not enabled:
		_clear_route_hover()
		queue_redraw()


func _route_at(point: Vector2) -> String:
	if _overlook_width > 53.0 and _overlook_bounds().has_point(point):
		return OVERLOOK_INSPECTION
	if _town or _battle_mode:
		return ""
	var commands: Dictionary = slice.get("route", {}).get("map_actions", {})
	var pin_distance := 20.0 * 20.0
	var label_distance := INF
	var pin := ""
	var label := ""
	for entry in map_data.get("objects", []):
		if not commands.has(entry.id):
			continue
		var anchor := _point(entry.position)
		var distance := point.distance_squared_to(anchor)
		if distance < pin_distance:
			pin = entry.id
			pin_distance = distance
		elif font != null and distance < label_distance \
				and _route_label_box(entry.id, anchor, _route_label(entry)).grow(3.0).has_point(point):
			label = entry.id
			label_distance = distance
	return label if pin.is_empty() else pin


func _clear_route_hover() -> void:
	_route_press = ""
	_set_route_hover("")


func _clear_battle_pointer() -> void:
	_pressed_battle_actor = ""
	if _battle_hover_cell != Vector2i(999, 999):
		_battle_hover_cell = Vector2i(999, 999)
		queue_redraw()
	if _route_hover.is_empty():
		mouse_default_cursor_shape = CURSOR_ARROW


func _update_battle_cursor(point: Vector2) -> void:
	mouse_default_cursor_shape = CURSOR_ARROW if _battle_annotation_at(point).is_empty() else CURSOR_POINTING_HAND


func _set_route_hover(id: String) -> void:
	if _route_hover != id:
		_route_hover = id
		mouse_default_cursor_shape = CURSOR_ARROW if id.is_empty() else CURSOR_POINTING_HAND
		queue_redraw()


func _input(event: InputEvent) -> void:
	if _deployment_drag != null and event.is_action_pressed("ui_cancel") and cancel_deployment_drag():
		get_viewport().set_input_as_handled()
		return
	if _discard_drag_release and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_discard_drag_release = false
		if not event.pressed:
			get_viewport().set_input_as_handled()
			return
	if deployment_open and event is InputEventMouse:
		# Resolve the drop from the same input event as the dragged preview.
		_pointer = make_input_local(event).position


func _cell_at(point: Vector2) -> Vector2i:
	for cell: Vector2i in coordinate_map:
		var center: Vector2 = coordinate_map[cell]
		if point.distance_squared_to(center) < _scale * _scale \
			and Geometry2D.is_point_in_polygon(point, _hex(center, _scale * 0.96)):
			return cell
	return Vector2i(999, 999)


func _get_drag_data(point: Vector2) -> Variant:
	if not deployment_open:
		return null
	var id := _deployment_member(point)
	return null if id.is_empty() else begin_deployment_drag(point, id)


func _deployment_member(point: Vector2) -> String:
	var id: String = stage.pick_actor(point, true)
	if not id.is_empty():
		return id
	var cell := _cell_at(point)
	for member in slice.get("party", []):
		if member.deployed and cell_index(member.position) == cell:
			return member.instance_id
	return ""


func _battle_annotation_at(point: Vector2) -> String:
	for key: Dictionary in _drawn_warning_keys:
		if key.box.has_point(point):
			return key.source
	for down_pass in [false, true]:
		for index in range(_unit_labels.get_child_count() - 1, -1, -1):
			var label := _unit_labels.get_child(index) as Node2D
			var id: String = label.get_meta("actor_id")
			var marker: Dictionary = _unit_markers[id]
			if bool(marker.label_style.get("down", false)) != down_pass:
				continue
			if marker.label_box.has_point(point - label.position):
				return id
	return ""


func _battle_actor_at(point: Vector2) -> String:
	var id := _battle_annotation_at(point)
	if not id.is_empty():
		return id
	id = stage.pick_actor(point)
	if not id.is_empty():
		return id
	var cell := _cell_at(point)
	for actor in slice.get("actors", []):
		if actor.pos is Array and cell_index(actor.pos) == cell and float(actor.hp) > 0:
			return actor.id
	return ""


func focus_battle_actor(id: String) -> void:
	if battle_focus_id == id:
		return
	battle_focus_id = id
	_sync_unit_markers()
	if _battle_mode or not _danger_areas.is_empty():
		queue_redraw()
	if not impacts.is_empty() or not _danger_cells.is_empty():
		_overlay.queue_redraw()


func begin_deployment_drag(_local: Vector2, id: String) -> Variant:
	if not deployment_open:
		return null
	for member in slice.get("party", []):
		if member.instance_id != id or not member.deployable or int(member.injury_days) > 0:
			continue
		var preview := PanelContainer.new()
		preview.position = Vector2(14, 17)
		preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var style := _whistle_plate()
		for edge in [SIDE_LEFT, SIDE_RIGHT]:
			style.set_content_margin(edge, 10)
		for edge in [SIDE_TOP, SIDE_BOTTOM]:
			style.set_content_margin(edge, 6)
		preview.add_theme_stylebox_override("panel", style)
		_drag_label = Label.new()
		_drag_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_drag_label.add_theme_font_override("font", font)
		_drag_label.add_theme_font_size_override("font_size", 16)
		_drag_label.text = member.get("display_name", "队员")
		preview.add_child(_drag_label)
		set_drag_preview(preview)
		_deployment_drag = {"deploy_member": id, "caption": _drag_label.text}
		return _deployment_drag
	return null


func _is_deployment_drag(data: Variant) -> bool:
	return deployment_open and data is Dictionary and is_same(data, _deployment_drag)


func cancel_deployment_drag() -> bool:
	if _deployment_drag == null:
		return false
	var viewport := get_viewport()
	var active := viewport.gui_is_dragging() and is_same(viewport.gui_get_drag_data(), _deployment_drag)
	if active:
		_discard_drag_release = true
		viewport.gui_cancel_drag()
	else:
		_finish_deployment_drag()
	return active


func _can_drop_data(_position: Vector2, data: Variant) -> bool:
	if not _is_deployment_drag(data):
		return false
	_drop_cell = _cell_at(_pointer)
	var destination: Dictionary = deployment_target.call(data.deploy_member, _drop_cell)
	_drop_allowed = not destination.has("error")
	if is_instance_valid(_drag_label):
		_drag_label.text = data.caption + " · " + (destination.get("hint", "可部署") if _drop_allowed else destination.error)
	_overlay.queue_redraw()
	return _drop_allowed


func _drop_data(_position: Vector2, data: Variant) -> void:
	if _is_deployment_drag(data):
		# Submitting the drop closes deployment until its own receipt arrives.
		_deployment_drag = null
		deployment_dropped.emit(data.deploy_member, _cell_at(_pointer))


func _clear_drop_hint() -> void:
	_drop_cell = Vector2i(999, 999)
	_drop_allowed = false
	if _deploy_hover_cell != Vector2i(999, 999):
		_deploy_hover_cell = Vector2i(999, 999)
		queue_redraw()
	if _overlay != null:
		_overlay.queue_redraw()


func _build_reserve_zone() -> void:
	reserve_zone = PanelContainer.new()
	reserve_zone.name = "ReserveDrop"
	reserve_zone.position = Vector2(30, 24)
	reserve_zone.hide()
	_reserve_style = _whistle_plate()
	_reserve_style.bg_color = Color("2d261fee")
	_reserve_style.set_corner_radius_all(2)
	for edge in [SIDE_LEFT, SIDE_RIGHT]:
		_reserve_style.set_content_margin(edge, 13)
	for edge in [SIDE_TOP, SIDE_BOTTOM]:
		_reserve_style.set_content_margin(edge, 8)
	reserve_zone.add_theme_stylebox_override("panel", _reserve_style)
	_reserve_label = Label.new()
	_reserve_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_reserve_label.add_theme_font_size_override("font_size", 17)
	_reserve_label.add_theme_color_override("font_color", TEXT)
	reserve_zone.add_child(_reserve_label)
	reserve_zone.set_drag_forwarding(Callable(), _can_put_in_reserve, _put_in_reserve)
	reserve_zone.mouse_exited.connect(_clear_reserve_hint)
	add_child(reserve_zone)


func _can_put_in_reserve(_position: Vector2, data: Variant) -> bool:
	if not _is_deployment_drag(data):
		return false
	for member in slice.get("party", []):
		if member.instance_id == data.deploy_member and member.deployed:
			_clear_drop_hint()
			_reserve_style.border_color = Color("a4e0c4")
			if is_instance_valid(_drag_label):
				_drag_label.text = data.caption + " · 撤下部署"
			return true
	return false


func _put_in_reserve(_position: Vector2, data: Variant) -> void:
	if _is_deployment_drag(data):
		_deployment_drag = null
		deployment_withdrawn.emit(data.deploy_member)


func _clear_reserve_hint() -> void:
	if _reserve_style != null:
		_reserve_style.border_color = Color("826d4a")


func _notification(what: int) -> void:
	if what == NOTIFICATION_DRAG_END:
		_finish_deployment_drag()


func _finish_deployment_drag() -> void:
	_deployment_drag = null
	_clear_drop_hint()
	_clear_reserve_hint()
	_drag_label = null

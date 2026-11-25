extends Node

const Measurement = preload("res://measure.gd")
const FORTRESS_ART_LABELS := {"B1": "watch", "B2": "flank", "G": "keep", "L": "trench"}
var app: Control
var steps: Array = []
var failure := ""
var mode := ""
var began := 0
var mouse := false
var capture := false
var pacing := false
var measure: Node
var spear_count := 0
var ado_frames: Dictionary = {}
var fortress_frames: Dictionary = {}
var grip_checks: Dictionary = {}
var side_checks: Dictionary = {}
var map_steps: Array[String] = []
var map_route_check := false
var feedback_check := false
var feedback_frames: Dictionary = {}
var feedback_marks: Dictionary = {}
var melee_check := false
var melee_marks: Dictionary = {}
var bow_check := false
var bow_marks: Dictionary = {}
var aid_check := false
var aid_marks: Dictionary = {}
var crossbow_marks: Dictionary = {}
var mist_marks: Dictionary = {}
var mercenary_checks: Dictionary = {}
var echo_checks: Dictionary = {}
var sting_checks: Dictionary = {}
var guard_checks: Dictionary = {}
var paused_viewport_checks: Dictionary = {}
var enemy_spear_checks: Dictionary = {}
var skeleton_checks: Dictionary = {}


func _quiet_ado() -> bool:
	return "--quiet-ado" in OS.get_cmdline_user_args()


func start(root: Control, scenario: String) -> void:
	app = root
	mode = scenario
	mouse = mode == "full-mouse" or "--mouse" in OS.get_cmdline_user_args()
	map_route_check = mouse and "--map-route-check" in OS.get_cmdline_user_args()
	feedback_check = "--combat-feedback-check" in OS.get_cmdline_user_args()
	melee_check = "--melee-model-check" in OS.get_cmdline_user_args()
	bow_check = "--bow-model-check" in OS.get_cmdline_user_args()
	aid_check = "--aid-model-check" in OS.get_cmdline_user_args()
	spear_count = 1 if mode == "spear" else 2 if mode == "spear-dual" else 0
	capture = "--capture" in OS.get_cmdline_user_args()
	if mode == "late-ado-model":
		app.board.stage.profile_assets = true
		if "--delay-shield-start" in OS.get_cmdline_user_args():
			app.board.stage._scene_load_queue.erase(app.board.stage.MODEL_PATH)
	elif mode == "minimized-contact":
		app.board.stage._scene_load_queue.erase(app.board.stage.MODEL_PATH)
	if "--measure" in OS.get_cmdline_user_args():
		measure = Measurement.new()
		add_child(measure)
		if "--profile-render" in OS.get_cmdline_user_args():
			measure.profile_render(app.board.stage.viewport_3d, app)
			app.client.profile_receipts = true
			app.profile_panels = true
			app.board.stage.profile_assets = true
			if mode == "ado-auto-sample":
				measure.begin("CONTACT-MG01")
	pacing = capture or "--pace" in OS.get_cmdline_user_args() or (measure != null and (spear_count > 0 or mode in ["full", "full-mouse"]))
	began = Time.get_ticks_msec()
	_run.call_deferred()


func _wait_ready() -> bool:
	var deadline := Time.get_ticks_msec() + 15000
	while app.client.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if app.client.busy or app.client.blocked:
		failure = "Runtime unavailable: " + app.notice.text
		return false
	return true


func _press(key: String, accept_confirmation := true) -> bool:
	if not failure.is_empty():
		return false
	await get_tree().process_frame
	var button: Variant = app.command_buttons.get(key)
	if not button is Button or button.disabled:
		failure = "Unavailable control: %s at %s keys %s" % [key, app.view.get("site"), app.command_buttons.keys()]
		return false
	if mouse:
		var scroll: ScrollContainer = app._action_scroll
		if app.actions.is_ancestor_of(button):
			var offset := scroll.scroll_vertical
			scroll.ensure_control_visible(button)
			if scroll.scroll_vertical != offset:
				await RenderingServer.frame_post_draw
		await get_tree().process_frame
		var point := _button_point(button)
		_mouse(point, true)
		_mouse(point, false)
	else:
		for i in range(app.command_buttons.size() + 2):
			if app.get_viewport().gui_get_focus_owner() == button:
				break
			_key(KEY_TAB, true)
			_key(KEY_TAB, false)
			await get_tree().process_frame
		if app.get_viewport().gui_get_focus_owner() != button:
			failure = "Keyboard cannot reach: " + key
			return false
		_key(KEY_ENTER, true)
		_key(KEY_ENTER, false)
	await get_tree().process_frame
	if accept_confirmation and not app.confirmation.is_empty() and key != "cancel":
		if app.get_viewport().gui_get_focus_owner() != app.command_buttons.get("cancel"):
			await get_tree().process_frame
			if app.get_viewport().gui_get_focus_owner() != app.command_buttons.get("cancel"):
				failure = "The confirmation does not focus Cancel"
				return false
		if not await _press("confirm"):
			return false
	return await _wait_ready()


func _button_point(control: Control) -> Vector2:
	return control.get_viewport().get_final_transform() * control.get_global_rect().get_center()


func _key(key: int, pressed: bool, echo := false) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.pressed = pressed
	event.echo = echo
	Input.parse_input_event(event)


func _mouse(point: Vector2, pressed: bool, double_click := false) -> void:
	var event := InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.double_click = double_click
	Input.parse_input_event(event)


func _mouse_motion(point: Vector2, relative: Vector2, held: bool) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = relative
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if held else 0
	Input.parse_input_event(event)


func _capture(mark: String) -> void:
	if not capture:
		return
	await RenderingServer.frame_post_draw
	var image := app.get_viewport().get_texture().get_image()
	if image == null or image.save_png(app.data_dir.path_join(app.case_name + "." + mark + ".png")) != OK:
		failure = "Cannot capture viewport: " + mark


func _command(key: String, route_point := Vector2.INF) -> bool:
	var before := int(app.client.frame.get("state_version", -1))
	var started := Time.get_ticks_usec()
	var site := key.get_slice(" ", 1)
	var via_map := map_route_check and key.begins_with("move ")
	var anchor := _route_anchor(site) if route_point == Vector2.INF and via_map else route_point
	var clue_click := key.begins_with("rescue investigate inspect ") and "--search-map-click" in OS.get_cmdline_user_args()
	if clue_click and anchor == Vector2.INF:
		var chart = app._search_chart
		anchor = chart._label_box(chart.KEYS.find(key.get_slice(" ", 3))).get_center()
	if clue_click or (anchor != Vector2.INF and app.board._route_input and app.board._route_at(anchor) == site):
		await get_tree().process_frame
		_click_board(anchor)
		await get_tree().process_frame
		if not await _wait_ready():
			return false
		if clue_click:
			if not side_checks.has("chart_clicks"):
				side_checks["chart_clicks"] = []
			side_checks.chart_clicks.append(key.get_slice(" ", 3))
		else:
			map_steps.append(site)
	elif not await _press(key):
		return false
	var frame: Dictionary = app.client.frame
	if int(frame["state_version"]) != before + 1:
		failure = "Command was not committed: " + key + " / " + app.notice.text
		return false
	steps.append({"command": key, "version": frame["state_version"], "digest": frame["state_digest"],
		"phase": app.view.get("phase"), "site": app.view.get("site")})
	if measure != null:
		steps[-1]["elapsed_usec"] = Time.get_ticks_usec() - started
	if capture and mode == "chapter" and key in ["move B_SUPPORT", "move C", "move D"]:
		await _capture("landmark-" + site)
		if app.board.show_models and not _visible_landmark(site):
			failure = "Landmark was outside the 3D camera: " + site
			return false
	return true


func _route_anchor(site: String) -> Vector2:
	for entry in app.board.map_data.get("objects", []):
		if entry.id == site:
			return app.board._point(entry.position)
	return Vector2.INF


func _click_board(anchor: Vector2) -> void:
	var point := _board_pixel(anchor)
	_mouse_motion(point, Vector2.ZERO, false)
	_mouse(point, true)
	_mouse(point, false)


func _panel_has(text: String) -> bool:
	return app.actions.get_children().any(func(control): return control is Label and text in control.text)


func _check_map_blockers() -> bool:
	var anchor := _route_anchor("B_MATERIAL")
	if anchor == Vector2.INF or app.board._route_at(anchor) != "B_MATERIAL":
		failure = "The discovered materials stop is not a clickable neighboring map site"
		return false
	if _route_anchor("D") != Vector2.INF or not app.command_buttons.has("move D"):
		failure = "The undiscovered overlook was exposed or cannot be approached from the route list"
		return false
	await _capture("route-adjacent")
	var version: int = app.client.frame.state_version
	var unreachable := _route_anchor("A")
	if unreachable == Vector2.INF or not app.board._route_at(unreachable).is_empty():
		failure = "The former contact at A is no longer a blocked map test site"
		return false
	_click_board(unreachable)
	await get_tree().process_frame
	if app.client.frame.state_version != version or app.client.busy:
		failure = "Clicking a non-neighboring map site submitted an action"
		return false
	if not await _press("settings"):
		return false
	_click_board(anchor)
	await get_tree().process_frame
	if app.client.frame.state_version != version or app.client.busy or not app.settings_open:
		failure = "Clicking the map behind Settings submitted an action"
		return false
	return await _press("settings-back")


func _visible_landmark(site: String) -> bool:
	var stage = app.board.stage
	var node: Node3D = stage.scenery.get(site)
	if node == null:
		return false
	var layer: Image = stage.viewport_3d.get_texture().get_image()
	var pin := Vector2i(stage.camera.unproject_position(node.position))
	var window := Rect2i(pin - Vector2i(37, 36), Vector2i(75, 57))
	window = window.intersection(Rect2i(Vector2i.ZERO, layer.get_size()))
	var count := 0
	for y in range(window.position.y, window.end.y):
		for x in range(window.position.x, window.end.x):
			if layer.get_pixel(x, y).a > 0.25:
				count += 1
	return count > 16


func _commands(keys: Array) -> bool:
	for key in keys:
		if not await _command(key):
			return false
	return true


func _fight(expected: String) -> bool:
	if not await _command("fight"):
		return false
	if app.board.show_models and app.board.stage.actors.is_empty():
		failure = "No shield model on the actual board: " + expected
		return false
	if measure != null:
		measure.begin(expected)
		await get_tree().create_timer(1.65).timeout
	var saw_warning := false
	var saw_spear := false
	var saw_spear_hit := false
	for i in range(160):
		if app.view.get("phase") != "BATTLE":
			if measure != null:
				measure.finish()
			var reports: Array = app.view.get("battle_results", [])
			if not reports.is_empty() and reports[-1]["encounter_id"] == expected and reports[-1]["result"] == "VICTORY" and saw_warning:
				if pacing:
					await get_tree().create_timer(1.45).timeout
				return true
			failure = "Unexpected result or missing warning for " + expected
			return false
		var prior_hit: int = app.board.stage.audit.spear_hits
		if not await _command("step"):
			return false
		if app.warning.visible and not saw_warning:
			await _capture(expected + "-warning")
		saw_warning = saw_warning or app.warning.visible
		if capture and spear_count > 0:
			if not saw_spear and app.view.get("battle_view", {}) is Dictionary:
				for row in app.view.battle_view.get("actors", []):
					if row.has("spear_pending"):
						await get_tree().create_timer(0.45).timeout
						await _capture(expected + "-spear-lock")
						saw_spear = true
						break
			if not saw_spear_hit and app.board.stage.audit.spear_hits > prior_hit:
				await get_tree().create_timer(0.43).timeout
				await _capture(expected + "-spear-hit")
				saw_spear_hit = true
		if pacing:
			await get_tree().create_timer(0.62).timeout
	failure = "Battle did not resolve: " + expected
	return false


func _opening() -> bool:
	var opening_version := int(app.client.frame["state_version"])
	var initial: String = app.data_dir.path_join("runs").path_join(app.case_name).path_join("save.json")
	if DirAccess.copy_absolute(initial, app.data_dir.path_join(app.case_name + ".initial.json")) != OK:
		failure = "Initial comparison state could not be copied"
		return false
	await _capture("opening")
	var first: String = app.subtitles.text
	if not await _press("subtitle-next"):
		return false
	if app.subtitles.text == first:
		failure = "Opening did not advance to the next canonical subtitle"
		return false
	for control in ["opening", "opening-replay", "opening"]:
		if not await _press(control):
			return false
	if int(app.client.frame["state_version"]) != opening_version:
		failure = "Opening navigation changed the authority state"
		return false
	if not await _commands(["quest commission CONFIRM", "tutorial recommend CONFIRM"]):
		return false
	if spear_count > 0:
		if measure != null:
			measure.begin("spear_setup")
		if not await _spear_roster():
			return false
		if measure != null:
			measure.finish()
	if measure != null:
		await _sample_scene("town")
	if mode == "access":
		if not await _confirmation_focus() or not await _keyboard_deploy():
			return false
	return await _command("tutorial start")


func _spear_roster() -> bool:
	for index in range(spear_count):
		if not await _command("recruit M01"):
			return false
	var home: Array = app.view.town_roster.home.filter(func(member: Dictionary) -> bool: return member.unit_id == "M01")
	if home.size() != spear_count or int(app.view.town_roster.copper) != 60 - 16 * spear_count:
		failure = "Recruitment did not use the domain roster or payment"
		return false
	var reserves := ["INIT-S01-C", "INIT-S02-C", "INIT-S02-A", "INIT-S02-B"]
	for index in range(2 * spear_count):
		var id: String = reserves[index]
		if not await _press("member-" + id) or not await _command("squad " + id + " off"):
			return false
	for member in home:
		if not await _command("squad " + member.instance_id + " on"):
			return false
	var bench := ["INIT-S02-A", "INIT-S02-B", "INIT-S01-A"] if spear_count == 1 else ["INIT-S01-A", "INIT-S03-B"]
	for id in bench:
		if not await _press("member-" + id) or not await _command("deploy " + id + " off"):
			return false
	for index in range(spear_count):
		var id: String = home[index].instance_id
		var column := index + 1
		if not await _press("member-" + id) or not await _press_cell("cell-%d-1" % column):
			return false
		if app.selected_facing != 1 and not await _press("facing"):
			return false
		if not await _command("place %s %d 1 1" % [id, column]) or not await _command("deploy " + id + " on"):
			return false
	return true


func _confirmation_focus() -> bool:
	var version := int(app.client.frame["state_version"])
	var files: Dictionary = app.client.frame["files"].duplicate()
	if not await _press("tutorial start", false) or not await _wait_focus("cancel"):
		failure = "The departure confirmation did not focus Cancel"
		return false
	if not await _press("settings", false) or not await _wait_focus("volume") or not app.settings_open:
		failure = "Settings over the departure confirmation did not focus Volume"
		return false
	_key(KEY_ESCAPE, true)
	await get_tree().process_frame
	_key(KEY_ESCAPE, true, true)
	_key(KEY_ESCAPE, false)
	if not await _wait_focus("settings") or app.settings_open or app.confirmation.is_empty():
		failure = "Closing settings did not restore its entry in the confirmation"
		return false
	_key(KEY_ESCAPE, true)
	_key(KEY_ESCAPE, false)
	if not await _wait_focus("tutorial start") or not app.confirmation.is_empty():
		failure = "Cancel did not restore the departure button"
		return false
	if int(app.client.frame["state_version"]) != version or app.client.frame["files"] != files:
		failure = "Closing the confirmation changed the authority"
		return false
	return true


func _has_focus(key: String) -> bool:
	return app.command_buttons.has(key) and app.get_viewport().gui_get_focus_owner() == app.command_buttons[key]


func _wait_focus(key: String) -> bool:
	for frame in range(5):
		if _has_focus(key):
			return true
		await get_tree().process_frame
	return _has_focus(key)


func _keyboard_deploy() -> bool:
	for member in app.view["party"]:
		if not member["deployed"] or not member["position"] in app.view["town_deploy_cells"]:
			continue
		var member_id: String = member["instance_id"]
		var point: Array = member["position"]
		var face := (int(member["facing"]) + 1) % 6
		return await _press("member-" + member_id) and await _press_cell("cell-%d-%d" % point) and await _press("facing") and await _command("place %s %d %d %d" % [member_id, point[0], point[1], face])
	failure = "No deployed member on a legal town cell"
	return false


func _press_cell(key: String, next_focus := "facing") -> bool:
	if not app.command_buttons.has(key) and not await _press("deployment-cells"):
		return false
	if not await _press(key):
		return false
	if app.command_buttons.has(key) or not await _wait_focus(next_focus):
		failure = "Selecting a slot did not collapse the grid and focus its next control"
		return false
	return true


func _full() -> void:
	if measure != null:
		await _sample_scene("explore")
	if not await _commands(["move A"]) or not await _fight("INTRO-EN01"):
		return
	var extended_run := mode in ["ado-early", "ado-late", "fortress-branches", "rescue"]
	var material := "tutorial materials PASS" if mouse and not extended_run else "tutorial materials"
	if not await _commands(["tutorial plan PL01", "move B_SUPPORT", "tutorial support PASS", "move A", "move B_MATERIAL",
		material, "move A", "move B_MATERIAL"]):
		return
	if app.command_buttons.has("tutorial materials") or app.command_buttons.has("tutorial materials PASS"):
		failure = "Revisiting the materials branch re-opened a settled choice"
		return
	if not await _command("move C"):
		return
	if map_route_check and not await _check_map_blockers():
		return
	if not await _command("move D"):
		return
	if app.view.get("observation") != null:
		failure = "Reaching D created a false observation"
		return
	if mode != "unobserved" and not await _command("tutorial observe"):
		return
	if map_route_check:
		if not _panel_has("远眺已记录"):
			failure = "Recording the overlook did not update the visible scouting progress"
			return
		await _capture("route-observed")
	if not await _command("move G") or not await _fight("TUT01-ROOT"):
		return
	if app.model.get("active", {}).get("id", "") != "trip-1-root_win":
		failure = "The authority did not show G's distant voice"
		return
	var offers: Array = app.view.get("gear_offers", [])
	if offers.is_empty():
		failure = "The reward was not presented"
		return
	var loot := str(offers[0])
	if (mode == "chapter" or extended_run) and not app.view.get("gear_compatible", []).is_empty():
		loot = app.view.gear_compatible[0]
	if mode not in ["unclaimed", "unobserved"] and not await _command("tutorial cache " + loot):
		return
	if not await _commands(["move X", "return CONFIRM"]):
		return
	if map_route_check:
		var gear: Array = app.view.get("settlement", {}).get("returned_gear_names", [])
		if "B_MATERIAL" not in map_steps or map_steps.size() < 3 or gear.is_empty() or not _panel_has(gear[0]):
			failure = "Map navigation or the named returned equipment was missing"
			return
	if app.warning.visible or app.sound_count < 2:
		failure = "Missing final danger clear or warning audio dispatch"
		return
	_check_settlement("SAFE_RETURN", mode != "unobserved")
	await _capture("settlement")


func _chapter_flow(collect_whistle := true) -> void:
	if not await _command("town"):
		return
	if app.command_buttons.has("quest archive CONFIRM"):
		failure = "Archive was offered without the review"
		return
	if not await _commands(["quest review CONFIRM", "quest archive CONFIRM"]):
		return
	var chapter: Dictionary = app.view.chapter
	if not chapter.reviewed or not chapter.archived or int(chapter.seals) != 1 or chapter.books.is_empty():
		failure = "The native chapter facts or first delivery were not reflected"
		return
	await _capture("chapter-archive")
	var book: Dictionary = chapter.books[0]
	if not await _press("chapter-books") or not await _command("book choice ST-104 " + book.id + " CONFIRM"):
		return
	if app.view.chapter.book_selected.id != book.id or not app.view.chapter.books.is_empty():
		failure = "The first chapter book was not claimed once"
		return
	var call_id: String = app.view.chapter.summon_id
	if not await _command("summon " + call_id + " CONFIRM"):
		return
	if int(app.view.chapter.seals) != 0 or not app.view.town_roster.home.any(func(member: Dictionary) -> bool: return member.unit_id.begins_with("H")):
		failure = "The hero or the seal receipt was missing"
		return
	var copper := int(app.view.town_roster.copper)
	var price := int(app.view.whistle.price)
	if collect_whistle:
		if not await _commands(["quest MG01 record", "quest MG01 witness", "quest MG01 collect CONFIRM"]):
			return
		if app.view.whistle.stage != "done" or int(app.view.town_roster.copper) != copper - price:
			failure = "The whistle was not paid for and recorded exactly once"
			return
	if not await _press("town-roster"):
		return
	for item in app.view.equipment.inventory:
		for member in app.view.party:
			if member.unit_id in item.allowed and not item.locked:
				if not await _press("member-" + member.instance_id) or not await _command("equip " + member.instance_id + " " + item.id):
					return
				if collect_whistle:
					_check_chapter()
				await _capture("chapter-equipment")
				return
	failure = "The actual tutorial loot could not be equipped"


func _check_chapter() -> void:
	var chapter: Dictionary = app.view.get("chapter", {})
	var party: Array = app.view.get("party", [])
	var equipped := party.any(func(member: Dictionary) -> bool: return not member.equipment.is_empty())
	var recruited: bool = app.view.get("town_roster", {}).get("home", []).any(
		func(member: Dictionary) -> bool: return member.unit_id.begins_with("H"))
	if app.view.get("phase") != "TOWN" or not chapter.get("archived", false) or chapter.get("book_selected", {}).is_empty() or app.view.whistle.stage != "done" or int(chapter.get("seals", -1)) != 0 or not recruited or not equipped:
		failure = "Chapter archive, claimed rewards, whistle or equipped loot failed to persist"


func _measure_opening_cuts() -> bool:
	var cuts := []
	var original: Dictionary = app.client.frame
	var current := 0
	for target: int in [1, 2, 3, 2, 3, 2, 3, 2, 3, 2, 1, 0]:
		await get_tree().process_frame
		var key := "subtitle-next" if target > current else "subtitle-prev"
		var button: Button = app.command_buttons[key]
		var point := _button_point(button)
		var from: String = app._opening_art._cue
		var started := Time.get_ticks_usec()
		_mouse(point, true)
		_mouse(point, false)
		Input.flush_buffered_events()
		var dispatched := Time.get_ticks_usec()
		await RenderingServer.frame_post_draw
		var displayed := Time.get_ticks_usec()
		var cue: String = app.view.opening_lines[target].id
		if app._opening_art._cue != cue or not app.subtitles.text.contains(app.view.opening_lines[target].text) \
				or app.client.frame != original:
			failure = "The measured opening cut did not present its saved line"
			return false
		cuts.append({"from": from, "to": cue, "dispatch_us": dispatched - started, "drawn_us": displayed - started,
			"texture_id": str(app._opening_art._plate.get_instance_id())})
		current = target
	side_checks["opening_cuts"] = cuts
	return true


func _check_commission_receipt() -> void:
	var original: Dictionary = app.client.frame
	if app.view.commissioned:
		failure = "The commission check did not start in a new campaign"
		return
	if "--measure-opening-cuts" in OS.get_cmdline_user_args() and not await _measure_opening_cuts():
		return
	if "--opening-beats" in OS.get_cmdline_user_args():
		var cues := ["TD001", "TD002", "TD003", "TD032"]
		for index in cues.size():
			if not app._opening_art.visible or app._opening_art._cue != cues[index] \
					or not app.subtitles.text.contains(app.view.opening_lines[index].text):
				failure = "A north-gate shot did not match its saved line"
				return
			var plate: Texture2D = app._opening_art._plate
			var expected_plate: String = app._opening_art.REGISTRY if cues[index] == "TD032" else app._opening_art.NORTH_GATE
			if plate == null or plate.resource_path != expected_plate or plate.get_size() != app._opening_art.PLATE_SIZE:
				failure = "The north-gate shot did not load its painted plate"
				return
			if index == 1:
				if not await _press("subtitle-prev") or app._opening_art._cue != "TD001" or app._opening_art._plate != plate:
					failure = "Returning to the wide shot lost its place or reloaded the same plate"
					return
				if not await _press("subtitle-next") or app._opening_art._cue != "TD002":
					failure = "Returning to the arrival shot did not restore its line"
					return
			await _capture("north-gate-" + cues[index])
			if index < cues.size() - 1 and not await _press("subtitle-next"):
				return
		if not ["opening-reopen-record", "opening-ask", "opening"].all(
				func(control: String) -> bool: return app.command_buttons.has(control)):
			failure = "The authored replies were missing at the end of the opening"
			return
		if not await _press("opening-ask"):
			return
		side_checks["opening_cues"] = cues
		side_checks["opening_reply"] = "谁回来过"
	else:
		await _capture("north-gate-skip")
		if not await _press("opening"):
			return
	if app._opening_art.visible or app.client.frame != original or app.board.reserve_zone.visible \
			or app.board.deployment_open or app.dialogue_next.visible or not app.subtitles.text.is_empty() \
			or not await _wait_focus("quest commission CONFIRM"):
		failure = "Entering town changed the campaign or left obsolete opening or deployment controls"
		return
	if "--verify-opening-plates" in OS.get_cmdline_user_args():
		var art = app._opening_art
		if not await _wait_until(func(): return not art._loading_registry and not art.is_processing() \
				and art._plate == null and art._gate == null and art._registry == null \
				and not ResourceLoader.has_cached(art.NORTH_GATE) and not ResourceLoader.has_cached(art.REGISTRY), 2000):
			failure = "Leaving the opening retained a loaded plate or a pending background request"
			return
		side_checks["opening_plates_released"] = true
	var asked: bool = side_checks.get("opening_reply", "") == "谁回来过"
	if _panel_has("旧队档案缺了几页") != asked \
			or not _panel_has("城墙可以晚修一截，回来的路不能再少一条") \
			or not _panel_has("报名的人有名字，回来的时候照着名字点"):
		failure = "The commission lost its chapter dialogue or answered a question the player did not ask"
		return
	side_checks["commission_old_log_answer"] = asked
	await _capture("town-commission")
	if "--opening-skip-only" in OS.get_cmdline_user_args():
		side_checks["opening_skip_read_only"] = true
		return
	var key := "quest commission CONFIRM"
	if not await _press(key, false) or not _panel_has("3 名盾兵、3 名近战兵和 2 名弓兵") \
			or not _panel_has("60 铜、12 结晶和 6 补给") or not await _press("cancel"):
		failure = "The commission preview did not list its grant or support cancellation"
		return
	if app.client.frame != original or app.view.commissioned or not app.view.party.is_empty():
		failure = "Cancelling the commission changed the campaign"
		return
	var initial: String = app.data_dir.path_join("runs").path_join(app.case_name).path_join("save.json")
	if DirAccess.copy_absolute(initial, app.data_dir.path_join(app.case_name + ".initial.json")) != OK:
		failure = "Could not copy the uncommissioned save for reference replay"
		return
	if not await _command(key):
		return
	var receipt: Dictionary = app.view.commission_receipt
	if int(receipt.members) != 8 or int(receipt.resources.copper) != 60 or int(receipt.resources.crystal) != 12 \
			or int(receipt.resources.supply) != 6 or "初次登记 8 名队员" not in app.notice.text \
			or "CONFIRM" in app.notice.text or not await _wait_focus("tutorial recommend CONFIRM"):
		failure = "The accepted commission did not show its saved grant and next action"
		return
	var accepted: Dictionary = app.client.frame
	if not await _press("opening-replay") or not app._opening_art.visible or app._opening_art._cue != "TD001":
		failure = "The opening replay did not restart from its first shot"
		return
	if not await _press("opening"):
		return
	if app.client.frame != accepted or app._opening_art.visible or app.command_buttons.has(key):
		failure = "Returning from the opening replay changed or reoffered the commission"
		return
	side_checks["commission_receipt"] = receipt
	side_checks["cancel_and_replay_transactions"] = 0


func _check_early_whistle(reopening: bool) -> void:
	if app.view.get("phase") != "TOWN" or app.view.get("complete") or app.view.commissioned != reopening:
		failure = "The early whistle test must start before the first field trip"
		return
	if not reopening:
		var initial: String = app.data_dir.path_join("runs").path_join(app.case_name).path_join("save.json")
		if DirAccess.copy_absolute(initial, app.data_dir.path_join(app.case_name + ".initial.json")) != OK:
			failure = "Initial comparison state could not be copied"
			return
		if not await _press("opening"):
			return
		if app.command_buttons.has("whistle-section") or not app.view.whistle.is_empty():
			failure = "Whistle work was offered before the commission"
			return
		if not await _command("quest commission CONFIRM"):
			return
	var before: int = app.client.frame.state_version
	if not await _press("whistle-section"):
		return
	if not reopening:
		var balance: int = app.view.town_roster.copper
		if not await _commands(["quest MG01 record", "quest MG01 witness"]):
			return
		if not _panel_has(app.view.whistle.record) or not _panel_has(app.view.whistle.witness):
			failure = "The panel did not display the recorded registration and testimony"
			return
		var collect := "quest MG01 collect CONFIRM"
		if not await _press(collect, false) or not _panel_has("%d 铜" % int(app.view.whistle.price)):
			failure = "The collection confirmation did not show the actual copper charge"
			return
		await _capture("whistle-confirmation")
		if not await _press("cancel") or int(app.client.frame.state_version) != before + 2 \
				or int(app.view.town_roster.copper) != balance:
			failure = "Cancel charged copper or wrote a collection receipt"
			return
		if not await _command(collect):
			return
		if int(app.view.town_roster.copper) != balance - int(app.view.whistle.price):
			failure = "The early collection did not charge the frozen price once"
			return
	if app.view.whistle.stage != "done" or not _panel_has("裂口铜哨已入任务物品") \
			or app.command_buttons.has("quest MG01 collect CONFIRM") or not app.view.hunt.is_empty() \
			or app.command_buttons.has("challenge MG01") or not app.command_buttons.has("tutorial start"):
		failure = "The completed whistle did not persist, or it unlocked the hunt before the archive"
		return
	await _capture("whistle-on-record")
	if not await _press("whistle-section"):
		return
	if app.whistle_open or int(app.client.frame.state_version) != (before if reopening else before + 3):
		failure = "Closing the optional commission changed the save"
		return
	side_checks["early_whistle"] = {"stage": app.view.whistle.stage, "copper": app.view.town_roster.copper,
		"version": app.client.frame.state_version, "reopened": reopening, "hunt_unlocked": false}


func _check_copy_size() -> bool:
	var preview: Label = app._confirmation_text
	var original_text := preview.text
	var version: int = app.client.frame.state_version
	var samples := []
	for cycle in 3:
		if cycle > 0:
			if not await _press("settings", false) or not await _press("大字", false) or not await _press("settings-back", false):
				return false
		var large: bool = app.settings["大字"]
		var heading: Label = app._confirmation_actions.get_child(0)
		if not await _wait_focus("cancel") or preview.text != original_text or app.client.frame.state_version != version \
				or preview.get_theme_font_size("font_size") != (26 if large else 19) \
				or heading.get_theme_font_size("font_size") != (30 if large else 23) \
				or preview.get_line_count() != preview.get_visible_line_count() \
				or preview.size.x > app._action_scroll.size.x:
			failure = "Changing text size lost the pending preview, focus, wrapping, or font sizes"
			return false
		samples.append({"large": large, "body_px": preview.get_theme_font_size("font_size"),
			"heading_px": heading.get_theme_font_size("font_size"), "lines": preview.get_line_count(), "width": preview.size.x})
		if cycle < 2:
			await _capture("large-copy" if large else "standard-copy")
	side_checks["copy_size_cycle"] = samples
	return true


func _check_chapter_delivery() -> void:
	var archive: bool = not app.view.chapter.archived
	var key := "quest archive CONFIRM" if archive else "quest report MG01 CONFIRM"
	var version: int = app.client.frame.state_version
	var seals := int(app.view.chapter.seals)
	var books := 0 if archive else int(app.view.hunt.report_book.count)
	var offer := "出征预算 8 → 12 Cost\n战斗预算 6 → 8 Cost" if archive else "「守誓回斩」×1 · 应召印 ×1"
	if not await _press(key, false):
		return
	if not _panel_has(offer) or (archive and (not _panel_has("应召印 ×1\n自选基础技能书 ×1") \
				or not _panel_has("任务物品「封存档案片」"))) \
			or int(app.client.frame.state_version) != version:
		failure = "The delivery confirmation did not show the frozen reward before submitting"
		return
	if "--cycle-copy-size" in OS.get_cmdline_user_args() and not await _check_copy_size():
		return
	await _capture("delivery-confirmation")
	if not await _press("confirm"):
		return
	if int(app.client.frame.state_version) != version + 1 or int(app.view.chapter.seals) != seals + 1 \
			or app.command_buttons.has(key):
		failure = "The first delivery did not settle exactly once"
		return
	if archive:
		if not app.view.chapter.archived or int(app.view.budget.expedition) != 12 or int(app.view.budget.battle) != 8 \
				or not _panel_has("出征预算 12 Cost · 战斗预算 8 Cost") or not app.command_buttons.has("chapter-books"):
			failure = "The archived chapter panel did not show the saved budget and choice"
			return
		side_checks["archive_budget"] = app.view.budget
	else:
		var book: Dictionary = app.view.hunt.report_book
		if not app.view.hunt.reported or book.id != "SB-X01" or int(book.count) != books + 1 \
				or not _panel_has(offer) or not _panel_has("「守誓回斩」现存 %d 本" % int(book.count)) \
				or not _panel_has("第 %d 日交存" % int(app.view.day)):
			failure = "The reported hunt did not distinguish the first reward from its current stock"
			return
		side_checks["report_book"] = book
	side_checks["seals_added"] = int(app.view.chapter.seals) - seals
	steps.append({"command": key, "version": version + 1, "digest": app.client.frame.state_digest})
	await _capture("delivery-receipt")


func _check_chapter_book_browser(offers: Array) -> bool:
	var before: Dictionary = app.client.frame
	var page = app._archive_page
	for i in offers.size():
		var book: Dictionary = offers[i]
		var key := "book choice ST-104 %s CONFIRM" % book.id
		var entry: Button = app.command_buttons[key]
		if mouse:
			app._action_scroll.ensure_control_visible(entry)
			await RenderingServer.frame_post_draw
			_mouse_motion(_button_point(entry), Vector2(2, 0), false)
		elif i > 0:
			_key(KEY_TAB, true)
			_key(KEY_TAB, false)
		if not await _wait_focus(key) or not page.visible or page.current_key != book.id or page.heading.text != book.name \
				or not page.body.text.contains(book.timing) or not page.body.text.contains(book.summary) \
				or not app.confirmation.is_empty() or not app._action_scroll.get_global_rect().has_point(entry.get_global_rect().get_center()):
			failure = "Unreadable offer %s (page=%s, focused=%s, scroll=%d, control=%s)" % [
				key, page.current_key, _has_focus(key), app._action_scroll.scroll_vertical, entry.get_global_rect()]
			return false
		if not await _check_preview_readers(book):
			return false
		if book.timing == "被动":
			await _capture("passive-preview")
	var last_key := "book choice ST-104 %s CONFIRM" % offers.back().id
	if not await _press(last_key, false) or not _panel_has(offers.back().name) or not await _wait_focus("cancel") \
			or page.current_key != offers.back().id or not await _press("cancel") or not await _wait_focus(last_key):
		failure = "Cancelling the skill-book claim did not restore the same manual"
		return false
	_key(KEY_ESCAPE, true)
	_key(KEY_ESCAPE, false)
	if not await _wait_until(func(): return not app.books_open and _has_focus("chapter-books"), 2000) \
			or page.visible or app.client.frame != before or not await _press("chapter-books"):
		failure = "Browsing, cancelling or closing the book list changed the earned choice"
		return false
	side_checks["books_previewed_without_claim"] = offers.size()
	return true


func _check_preview_readers(book: Dictionary) -> bool:
	var page = app._archive_page
	var lines := PackedStringArray()
	if book.learners.is_empty():
		lines.append("当前无人可学习，可先存入书库。")
	for reader: Dictionary in book.learners:
		lines.append("%s　%s" % [reader.location, reader.name])
	for reader: Dictionary in book.known:
		lines.append("已学会 · %s　%s" % [reader.location, reader.name])
	if not page.reader_section.visible or page.reader_names.get_parsed_text() != "\n".join(lines):
		failure = "The visible manual did not match the current learner list for " + str(book.id)
		return false
	var args := OS.get_cmdline_user_args()
	if "--ordinary-book-roster" in args and (not book.known.is_empty() or not book.learners.is_empty()):
		failure = "The initial ordinary soldiers were listed as book learners"
		return false
	if "--mixed-book-readers" in args:
		var eligible := {"SB-B01": ["N-0001", "HERO-H08"], "SB-C01": ["HERO-H08"], "SB-D05": ["N-0001"], "SB-D09": []}
		var known_ids := []
		if "--studied-book-reader" in args and book.id == "SB-B01":
			eligible["SB-B01"] = ["HERO-H08"]
			known_ids.append("N-0001")
		if eligible.has(book.id) and (book.learners.map(func(r): return r.id) != eligible[book.id] \
				or book.known.map(func(r): return r.id) != known_ids):
			failure = "The list disagreed with the saved archer capability, melee capability or learned book: " + str(book.id)
			return false
		if book.id in ["SB-B01", "SB-D05", "SB-D09"]:
			await _capture("readers-" + str(book.id))
	return true


func _check_archive_progress() -> void:
	if app.view.get("scouting", {}).get("delivered_here", false):
		if not _panel_has("可在暮汀旧档案请许苇核对远眺记录") or not await _command("town"):
			failure = "The scouting settlement did not link to its archive task"
			return
	if app.view.get("phase") == "EXPLORE" and app.view.get("hunt", {}).get("report_pending_return", false):
		var through_entrance := "--entrance-report" in OS.get_cmdline_user_args()
		var return_path := ["move T", "move W", "move B2", "move V", "move B1", "move U", "move I"] \
			if through_entrance else ["move X"]
		if through_entrance and not _panel_has("沿原路返回入口"):
			failure = "The fortress did not explain the valid entrance return"
			return
		if not await _commands(return_path) or not await _press("return CONFIRM", false):
			return
		side_checks["report_return_site"] = app.view.site
		var version := int(app.client.frame.state_version)
		if not _panel_has("安全归城后，可在暮汀旧档案交存阿铎讨伐报告"):
			failure = "The return preview did not explain how to unlock delivery"
			return
		await _capture("report-return")
		if not await _press("confirm") or int(app.client.frame.state_version) != version + 1 \
				or not _panel_has("阿铎讨伐报告可在暮汀旧档案交存") or app.view.hunt.reported:
			failure = "The safe return did not unlock the pending report"
			return
		steps.append({"command": "return CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
		if not await _command("town"):
			return
		await get_tree().process_frame
		var hunt: Dictionary = app.view.hunt
		if app.town_tab != "chapter" or app.get_viewport().gui_get_focus_owner() != app.command_buttons.get("quest report MG01 CONFIRM") \
				or not _panel_has("第 %d 日胜利 · 第 %d 日安全归城" % [int(hunt.victory_day), int(hunt.report_return_day)]):
			failure = "The return opened the wrong panel or lost the saved return date"
			return
		await _capture("report-ready")
		await _check_chapter_delivery()
		return
	var saved_hunt: Dictionary = app.view.get("hunt", {})
	if app.view.get("phase") == "TOWN" and saved_hunt.get("report_ready", false) and not saved_hunt.reported:
		if app.town_tab != "chapter" or not await _wait_focus("quest report MG01 CONFIRM"):
			failure = "Reopening a pending report did not focus its delivery"
			return
		side_checks["initial_archive_focus"] = "quest report MG01 CONFIRM"
		await _check_chapter_delivery()
		return
	var chapter: Dictionary = app.view.get("chapter", {})
	if chapter.is_empty():
		failure = "This check requires an earned chapter save"
		return
	var review_line := "记得一个动作，和记得是谁教的，是两件事。"
	var whistle_clue := "秦姨拿出铜哨的旧照片和寄存登记单。"
	if not chapter.archived:
		var pending_key := "quest archive CONFIRM" if chapter.reviewed else "quest review CONFIRM"
		if app.town_tab != "chapter" or not await _wait_focus(pending_key):
			failure = "The pending chapter action was not focused"
			return
		side_checks["initial_archive_focus"] = pending_key
	if not chapter.reviewed:
		var observation: String = chapter.observation
		if not await _press("chapter-history") or not app._archive_page.visible or app._archive_page.body.text != observation \
				or app._archive_page.current_key != "ST-102" or not app.command_buttons.has_all(["archive-ST-000", "archive-ST-101"]) \
				or app.command_buttons.has("archive-ST-103") or app.command_buttons.has("archive-ST-104") \
				or app._archive_page.body.text.contains(review_line) or app._archive_page.body.text.contains(whistle_clue):
			failure = "The unreviewed archive lost a saved record or showed a future milestone"
			return
		await _capture("scouting-record")
		if not await _press("chapter-history"):
			return
		var version := int(app.client.frame.state_version)
		if not await _press("quest review CONFIRM", false) or not _panel_has(observation) \
				or _panel_has(review_line) or _panel_has(whistle_clue) or int(app.client.frame.state_version) != version:
			failure = "The review confirmation did not show the saved observation"
			return
		if not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
			failure = "The observation review was not committed"
			return
		steps.append({"command": "quest review CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
		await get_tree().process_frame
		if app.get_viewport().gui_get_focus_owner() != app.command_buttons.get("quest archive CONFIRM") \
				or not _panel_has(review_line) or _panel_has(whistle_clue):
			failure = "The review did not reveal Xu Wei's reply or focus the next chapter action"
			return
	if not app.view.chapter.archived:
		await _check_chapter_delivery()
		if not failure.is_empty():
			return
		if app.view.whistle.stage == "record" and not _panel_has(whistle_clue):
			failure = "The first archive delivery did not reveal the whistle lead"
			return
	if "--check-chapter-choice" in OS.get_cmdline_user_args():
		var offers: Array = app.view.chapter.books
		if offers.size() != 12:
			failure = "The archive did not offer exactly twelve basic books"
			return
		var selection: String = offers[9].id if "--choose-passive" in OS.get_cmdline_user_args() else offers[0].id
		if "--choose-fire-arrow" in OS.get_cmdline_user_args():
			selection = "SB-D09"
		if not await _press("chapter-books"):
			return
		await _capture("chapter-book-offers")
		if "--browse-book-offers" in OS.get_cmdline_user_args() and not await _check_chapter_book_browser(offers):
			return
		if not await _command("book choice ST-104 " + selection + " CONFIRM"):
			return
		if app.view.chapter.book_selected.id != selection or not app.view.chapter.books.is_empty():
			failure = "The basic book was not selected and recorded once"
			return
	if "--teach-previewed-book" in OS.get_cmdline_user_args():
		var student := "HERO-H08"
		var chosen: Dictionary = app.view.chapter.book_selected
		if int(chosen.count) != 1:
			failure = "The new book was missing from the library"
			return
		if not await _press("town-skills"):
			return
		if app.selected_id != student and not await _press("book-member-" + student):
			return
		if not await _command("book learn %s %s" % [student, chosen.id]) or not await _press("town-chapter"):
			return
		if int(app.view.chapter.book_selected.count) != 0 or chosen.id not in app.view.skill_books.members[student].learned:
			failure = "The learner listed in the manual could not consume the claimed book at the library"
			return
		side_checks["learned_after_preview"] = {"member": student, "book": chosen.id}
	if "--use-chapter-rewards" in OS.get_cmdline_user_args():
		var learner := "N-0002"
		var starting_seals := int(app.view.chapter.seals)
		if not saved_hunt.get("reported", false) or int(saved_hunt.report_book.count) != 1 \
				or int(app.view.chapter.book_selected.count) != 1 or starting_seals != 1 \
				or not await _press("town-skills") or not await _press("book-member-" + learner):
			failure = "The receipt check needs one of each earned book and one seal"
			return
		if not await _commands(["book learn " + learner + " " + app.view.chapter.book_selected.id,
				"book learn " + learner + " " + saved_hunt.report_book.id]) \
				or not await _press("town-chapter") \
				or not await _command("summon " + app.view.chapter.summon_id + " CONFIRM"):
			return
		saved_hunt = app.view.hunt
		if int(saved_hunt.report_book.count) != 0 or int(app.view.chapter.book_selected.count) != 0 \
				or not _panel_has("应召印库存 0 枚"):
			failure = "The current inventory did not reflect learning and summoning"
			return
		side_checks["used_rewards"] = true
	var before := int(app.client.frame.state_version)
	if not await _press("chapter-history"):
		return
	var page = app._archive_page
	if not page.visible or page.current_key != "ST-104" or page.scroll.scroll_vertical != 0 \
			or not page.body.text.contains("封存档案片") or not page.body.text.contains(whistle_clue) \
			or not page.body.text.contains("交档后出征预算 12 Cost · 战斗预算 8 Cost") \
			or not page.body.text.contains("首交发放应召印 ×1\n登记基础技能书自选权益 ×1") \
			or app.command_buttons.has("town-roster") or app.command_buttons.has("chapter-books"):
		failure = "The chapter folio did not open on the saved archive receipt"
		return
	await _capture("archived-records")
	var selected: Dictionary = app.view.chapter.book_selected
	if not selected.is_empty():
		if selected.claimed_day == null or not page.body.text.contains("已领技能书 · %s · 第 %d 日" % [
				selected.name, int(selected.claimed_day)]) or not page.body.text.contains("书库现存 %d 本" % int(selected.count)):
			failure = "The archive page lost the claimed book or its current stock"
			return
		side_checks["archived_book"] = selected.id
	var bar: VScrollBar = page.scroll.get_v_scroll_bar()
	if bar.max_value > bar.page + 1:
		_key(KEY_PAGEDOWN, true)
		_key(KEY_PAGEDOWN, false)
		if page.scroll.scroll_vertical <= 0:
			failure = "The archive page did not scroll from its directory using Page Down"
			return
		side_checks["archive_page_scrolled"] = page.scroll.scroll_vertical
	for record: Dictionary in app.view.chapter.history:
		if not await _press("archive-" + str(record.id)) or page.heading.text != record.title \
				or page.date_line.text != "第 %d 日" % int(record.day) or page.scroll.scroll_vertical != 0:
			failure = "The selected archive document, day or scroll position did not match its directory entry"
			return
		var line: String = app._commission_grant_text(app.view.commission_receipt) if record.get("commission", false) else record.text
		if not page.body.text.contains(line):
			failure = "The archive omitted a saved passage"
			return
		if record.id == "ST-103":
			await _capture("review-exchange")
	if saved_hunt.get("reported", false):
		if not await _press("archive-report") or not page.body.text.contains("第 %d 日交存" % int(saved_hunt.report_delivery_day)) \
				or not page.body.text.contains("「守誓回斩」现存 %d 本" % int(saved_hunt.report_book.count)) \
				or not page.body.text.contains("「守誓回斩」×1 · 应召印 ×1") or app.command_buttons.has("quest report MG01 CONFIRM"):
			failure = "The stored report date or reward stock was lost on reopen"
			return
		side_checks["report_delivery_day"] = saved_hunt.report_delivery_day
		await _capture("report")
	elif app.command_buttons.has("archive-report"):
		failure = "An unearned hunt report was shown in the archive"
		return
	var collection: Dictionary = app.view.whistle.get("collection", {})
	if not collection.is_empty():
		if not await _press("archive-whistle") or not page.body.text.contains("裂口铜哨 · 第 %d 日修缮取回 · 支付 %d 铜" % [
				int(collection.day), int(collection.copper)]):
			failure = "The history lost the copper whistle payment receipt"
			return
		await _capture("whistle")
	elif app.command_buttons.has("archive-whistle"):
		failure = "An unearned whistle receipt was shown in the archive"
		return
	_key(KEY_ESCAPE, true)
	_key(KEY_ESCAPE, false)
	if not await _wait_until(func(): return not app.chapter_history_open and _has_focus("chapter-history"), 1500) \
			or page.visible or not _panel_has("暮汀 · 旧档案") or int(app.client.frame.state_version) != before:
		failure = "Returning from the report reader did not restore the archive and its focus"


func _check_ado_remembrance(reopening: bool) -> void:
	var hunt: Dictionary = app.view.get("hunt", {})
	if app.view.get("phase") != "TOWN" or not hunt.get("reported", false) or hunt.awakened:
		failure = "The town remembrance test needs a first report with no awakening"
		return
	var day := int(app.view.day)
	var seals := int(app.view.chapter.seals)
	var book := int(hunt.report_book.count)
	if reopening:
		var retain := "remember retain MG01-W2"
		await get_tree().process_frame
		if hunt.memory.get("id") != "MG01-W2" or not hunt.memory.enabled \
				or not _panel_has("第 2 / 2 段") \
				or not app.subtitles.text.is_empty() or _panel_has("我记得那半声了") \
				or app.get_viewport().gui_get_focus_owner() != app.command_buttons.get(retain):
			failure = "The saved town remembrance did not restore its second window and action focus"
			return
		await _capture("remembrance-resumed")
		if not await _command(retain):
			return
		var version := int(app.client.frame.state_version)
		if not app.view.hunt.awakened or app.command_buttons.has("remember MG01") \
				or not ("我记得那半声了" in app.subtitles.text) \
				or not await _press("remembrance-history") \
				or not _panel_has("铜哨缺口把回撤的第二声截断了") \
				or not _panel_has("我记得那半声了") \
				or app._action_scroll.scroll_vertical != 0 or app.command_buttons.has("town-roster") \
				or not app.subtitles.text.is_empty() \
				or int(app.client.frame.state_version) != version:
			failure = "The archive did not make both committed choices available without writing a new record"
			return
		await _capture("remembrance-transcript")
		if not await _press("remembrance-history") or not _panel_has("暮汀 · 旧档案") \
				or not app.subtitles.text.is_empty() \
				or int(app.client.frame.state_version) != version:
			failure = "Returning from the saved transcript changed the archive or the save"
			return
	else:
		if not _panel_has("追忆尚缺裂口铜哨、秦姨核实的证词") or app.command_buttons.has("remember MG01") \
				or not await _commands(["quest MG01 record", "quest MG01 witness"]):
			failure = "The archive did not show the actual starting prerequisites"
			return
		if not _panel_has("追忆尚缺裂口铜哨。") or app.command_buttons.has("remember MG01"):
			failure = "Testimony mistakenly unlocked remembrance without the whistle"
			return
		if not await _command("quest MG01 collect CONFIRM"):
			return
		await get_tree().process_frame
		if app.get_viewport().gui_get_focus_owner() != app.command_buttons.get("remember MG01") \
				or not await _commands(["remember MG01", "remember skip MG01-W1"]):
			failure = "Collecting both clues did not lead to the remembrance entry"
			return
		if not _panel_has("请先暂离追忆，再进入并补做第 1 段") or app.command_buttons.has("remember retain MG01-W2") \
				or not app.subtitles.text.is_empty() or _panel_has("我记得那半声了"):
			failure = "Skipping the first choice did not explain the blocked second step"
			return
		await _capture("remembrance-blocked")
		if not await _command("remember close"):
			return
		var resume: Button = app.command_buttons.get("remember MG01")
		if resume == null or "补做第 1 段" not in resume.text or app.command_buttons.has("remembrance-history"):
			failure = "The skipped window was not offered for repair, or uncommitted text leaked into the archive"
			return
		if not await _commands(["remember MG01", "remember evidence MG01-W1"]):
			return
		if app.view.hunt.memory.get("id") != "MG01-W2" or not app.view.hunt.memory.enabled \
				or not ("铜哨缺口把回撤的第二声截断了" in app.subtitles.text) \
				or _panel_has("我记得那半声了"):
			failure = "Repairing the first window did not show its reply and unlock the second choice"
			return
	if int(app.view.day) != day or int(app.view.chapter.seals) != seals or int(app.view.hunt.report_book.count) != book:
		failure = "Remembrance unexpectedly advanced time or changed the first report reward"


func _check_field_spoils() -> void:
	var rewards: Dictionary = app.view.get("field_book_rewards", {})
	if app.view.get("phase") == "BATTLE":
		var carried: Dictionary = rewards.get("carried", {})
		if carried.is_empty() or not await _press("flee CONFIRM", false) \
				or not _panel_has("成功撤出可带回行囊物资，战败时会丢失"):
			failure = "The retreat preview did not distinguish carrying from loss"
			return
		for title in carried:
			if not _panel_has(title):
				failure = "The retreat preview omitted a carried book"
				return
		if not await _press("cancel") or not await _command("step"):
			return
		var settlement: Dictionary = app.view.settlement
		if settlement.result != "DEFEAT" or settlement.lost_book_names != carried \
				or settlement.lost_cargo.pending.copper <= 0 or not _panel_has("损失物资") \
				or not _panel_has("损失技能书") or _panel_has("入库技能书"):
			failure = "The loss screen did not reflect actual lost cargo and books"
			return
		side_checks["books_lost"] = settlement.lost_book_names
		await _capture("spoils-lost")
		return
	var offer: Dictionary = rewards.get("offer", {})
	if offer.is_empty() or not offer.can_claim or int(offer.remaining_cap) != 1 \
			or not _panel_has(offer.book.name):
		failure = "The real battle drop did not appear at the source site"
		return
	var title: String = offer.book.name
	var version := int(app.client.frame.state_version)
	if "--decline-spoils" in OS.get_cmdline_user_args():
		if not await _command("book drop") or app.command_buttons.has("book claim") \
				or not app.view.field_book_rewards.carried.is_empty():
			failure = "Declining the battle drop added a book or left a pending offer"
		return
	if not await _press("book claim", false) or not _panel_has(title) or not _panel_has(offer.book.timing) \
			or int(app.client.frame.state_version) != version:
		failure = "The claim preview did not show the actual book and cost before committing"
		return
	await _capture("spoils-claim")
	if not await _press("cancel") or int(app.client.frame.state_version) != version \
			or not await _command("book claim"):
		return
	if app.view.field_book_rewards.carried.get(title) != 1 or app.command_buttons.has("book claim") \
			or not _panel_has("行囊技能书 · 待归城入库"):
		failure = "The picked book was not carried exactly once"
		return
	if not await _command("move X") or not await _press("return CONFIRM", false) \
			or not _panel_has("随队技能书将入库") or not _panel_has(title) or not await _press("cancel"):
		failure = "The safe return preview omitted the carried book"
		return
	if not await _command("return CONFIRM") or not _panel_has("入库技能书  " + title) \
			or app.view.settlement.banked_book_names.get(title) != 1:
		failure = "The settlement omitted the actual banked book"
		return
	side_checks["books_banked"] = app.view.settlement.banked_book_names
	await _capture("spoils-banked")
	if not await _command("town") or not await _press("town-skills") or not _panel_has(title):
		failure = "The same book did not appear in the town library"


func _check_handbook_event() -> void:
	var event: Dictionary = app.view.get("handbook_event", {})
	if event.is_empty() or event.get("choices", []).size() != 2 or not _panel_has(event.name) \
			or not _panel_has("本站只能选一项"):
		failure = "The material and handbook choices were not visible together at the source"
		return
	var book: Dictionary = event.book
	var material: Dictionary = event.choices[0]
	var gear: Dictionary = event.choices[1]
	var key := "choose " + str(material.id)
	var gear_key := "choose " + str(gear.id)
	var capped := "--handbook-cap-used" in OS.get_cmdline_user_args()
	var take_gear := "--handbook-gear" in OS.get_cmdline_user_args()
	var book_button: Button = app.command_buttons.get("choose BOOK")
	if book_button == null or book_button.disabled != capped or not material.allowed \
			or material.kind != "materials" or gear.kind != "gear" or not app.command_buttons.has(gear_key):
		failure = "The event did not apply the battle and event book quota independently of materials"
		return
	await _capture("handbook-options")
	var chosen: String
	if take_gear:
		var version := int(app.client.frame.state_version)
		if not await _press(gear_key, false) or not _panel_has("随队人员侵蚀 +5") \
				or not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
			failure = "The unopened box did not present the actual corrosion cost"
			return
		steps.append({"command": gear_key, "version": app.client.frame.state_version, "digest": app.client.frame.state_digest})
		chosen = gear.label
	elif capped:
		var version := int(app.client.frame.state_version)
		if int(event.remaining_books) != 0 or not await _press(key, false) or not _panel_has("当地材料 ×2"):
			failure = "Using the book quota wrongly blocked taking the original local materials"
			return
		if not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
			failure = "The material choice did not commit exactly once"
			return
		steps.append({"command": key, "version": app.client.frame.state_version, "digest": app.client.frame.state_digest})
		chosen = material.label
	else:
		if not await _commands(["move T", "move C"]) or app.view.handbook_event.book != book:
			failure = "Leaving before a choice did not preserve the same handbook offer"
			return
		var version := int(app.client.frame.state_version)
		if not await _press("choose BOOK", false) or not _panel_has(book.name) \
				or not _panel_has("结束本站其他选项") or not await _press("cancel") \
				or int(app.client.frame.state_version) != version:
			failure = "Preview and cancel did not preserve the event and shared quota"
			return
		if not await _command("choose BOOK"):
			return
		if app.view.field_book_rewards.carried.get(book.name) != 1:
			failure = "Taking the handbook did not add it to the expedition cargo"
			return
		chosen = book.name
	if app.view.handbook_event.get("resolved") != chosen or not _panel_has("本站已处理 · " + chosen) \
			or app.command_buttons.has("choose BOOK") or app.command_buttons.has(key) or app.command_buttons.has(gear_key):
		failure = "The completed event left a second reward selectable"
		return
	side_checks["handbook_choice"] = {"result": chosen, "book": book.id, "quota_used_by_battle": capped}
	await _capture("handbook-resolved")


func _route_hunt(general_id: String) -> Dictionary:
	for hunt: Dictionary in app.view.get("hunts", []):
		if hunt.id == general_id:
			return hunt
	return {}


func _route_member_action(parts: PackedStringArray) -> bool:
	var place := parts[0] == "place"
	if app.selected_id != parts[1] or place:
		if not await _press("member-" + parts[1]):
			return false
	if place:
		if not await _press_cell("cell-%s-%s" % [parts[2], parts[3]]):
			return false
		while app.selected_facing != int(parts[4]):
			if not await _press("facing"):
				return false
	return true


func _play_hunt_route(route_name: String, general_id: String) -> Array[String]:
	var path: String = app.data_dir.path_join(app.case_name + "." + route_name + "-route.json")
	var route: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not route is Dictionary or not route.get("commands") is Array:
		failure = "Missing native tactical route: " + path
		return []
	var victories: Array[String] = []
	var report_button := "quest report %s CONFIRM" % general_id
	var on_hunt := false
	for value in route.commands:
		var key := str(value)
		var parts := key.split(" ")
		var command := parts[0]
		if command in ["challenge", "depart", "pack_medical", "buy_supply", "rest"] and not await _ado_tab("expedition"):
			return []
		if command == "recruit" or command == "squad" or (app.view.phase == "TOWN" and command in ["place", "stance", "deploy", "level_up"]):
			if not await _ado_tab("roster"):
				return []
		if command in ["quest", "remember"] and app.view.get("town_memory", {}).is_empty() and not await _ado_tab("chapter"):
			return []
		if command == "supply" and not await _ado_tab("items"):
			return []
		if command == "quest" and parts[1] == "MG02" and not app.scarf_open and not await _press("scarf-section"):
			return []
		if command == "depart":
			on_hunt = _route_hunt(general_id).get("selected", false)
		var member_control := command in ["place", "stance", "deploy", "level_up"]
		if (member_control or (command == "squad" and parts[2] == "off")) and not await _route_member_action(parts):
			return []
		if key == "run 600":
			if not await _ado_steps(victories):
				return []
			continue
		if general_id != "MG01" and command == "return" and on_hunt:
			var hunt := _route_hunt(general_id)
			if not hunt.report_pending_return or hunt.report_ready or hunt.reported:
				failure = "%s victory did not wait for a safe return before enabling its report" % general_id
				return []
			if mode == "sev-awakening" and not hunt.awakened:
				failure = "Sev's live awakening was missing from the victory before the safe return"
				return []
		if key == report_button and _route_hunt(general_id).reported:
			if app.command_buttons.has(key):
				failure = "The first-delivery control appeared again"
				return []
			continue
		if command == "fight" and measure != null and app.view.region == "RG02" and app.view.site == "G":
			measure.begin("BATTLE-MG01")
		if command in ["memory", "remember"] and parts.size() == 3:
			if command == "memory" and (app.command_buttons.has("step") or app.command_buttons.has("flee CONFIRM")):
				failure = "Battle commands displayed during a memory window"
				return []
			if parts[2].begins_with("MG02-") and not _check_sev_window(command, parts[2]):
				return []
			await _capture(command + "-" + parts[2])
		if not await _command(key):
			return []
		if key == "quest MG02 witness" and int(app.view.scarf.short) > 0:
			var collect: Button = app.command_buttons.get("quest MG02 collect CONFIRM")
			if collect == null or not collect.disabled or not app.command_buttons.has("scarf-materials"):
				failure = "The scarf offered an unfunded collection or hid the material commission"
				return []
		if key == "remember skip MG02-W1":
			var second: Dictionary = app.view.town_memory
			if second.get("id") != "MG02-W2" or second.enabled or app.command_buttons.has("remember retain MG02-W2"):
				failure = "Skipping the scarf choice did not lock the second remembrance choice"
				return []
		if command == "memory" and app.view.phase != "BATTLE":
			var result: Dictionary = app.view.battle_results[-1]
			if result.result != "VICTORY" or result.encounter_id != "BATTLE-" + general_id:
				failure = "The memory window closed without an authentic battle victory"
				return []
			victories.append(result.encounter_id)
			if general_id == "MG01" and measure != null:
				measure.finish()
		if general_id != "MG01" and on_hunt and command in ["depart", "next"]:
			side_checks.get_or_add(route_name + "_regions", []).append(app.view.region)
		if command == "depart":
			await _capture("hunt-departure")
		elif command == "next":
			await _capture("fortress-entry")
		if app.view.region == "RG02" and command in ["next", "move", "fight"]:
			if not await _fortress_frame():
				return []
	return victories


func _ado_route() -> void:
	var victories := await _play_hunt_route("ado", "MG01")
	if not failure.is_empty():
		return
	if mode == "fortress-branches":
		if victories.size() != 5 or app.view.phase != "BATTLE" or app.view.site != "L":
			failure = "Fortress branches did not reach the live side-ditch battle"
			return
		for mark in ["map-A", "map-B", "map-C", "map-D", "contact-L", "battle-L"]:
			if not fortress_frames.has("fortress-" + mark):
				failure = "Missing a fortress branch view: " + mark
				return
		await _capture("fortress-branch-L-live")
		return
	if victories.size() != 6 or victories[-1] != "BATTLE-MG01":
		failure = "Expected five route battles and Ado's victory"
		return
	if app.view.hunt.awakened and app.view.hunt.reported and int(app.view.hunt.report_book.count) == 1 and int(app.view.chapter.seals) == 1:
		var audit: Dictionary = app.board.stage.audit
		if app.board.show_models and (not audit.ado_seen or audit.ado_phases != [1, 2, 3] or audit.ado_releases < 1 or audit.ado_downs != 1):
			failure = "Ado model or battle-phase feedback missing"
			return
		if app.board.show_models and fortress_frames.size() != 9:
			failure = "Expected the fortress entry, aid, exit and three encounter locations in preview and battle"
			return
		var moves: Dictionary = audit.ado_moves
		if app.board.show_models and (moves.size() != 3 or audit.ado_windups.size() != 3 or audit.ado_shields != moves.get("MG01-B", 0)):
			failure = "Ado's three skills were not fully displayed"
			return
		if _quiet_ado() and not app.ado_sound_counts.is_empty():
			failure = "Ado played a cue while muted"
			return
		if not _quiet_ado() and app.board.show_models:
			var audible := moves.duplicate()
			audible["whistle"] = 1
			if app.ado_sound_counts != audible:
				failure = "Ado's event-to-audio counts differed"
				return
		await _capture("hunt-complete")
	else:
		failure = "Ado's first report, book, seal or awakening missing"


func _sev_route() -> void:
	if app.view.get("phase") != "TOWN" or not app.view.get("chapter", {}).get("archived", false) \
			or app.view.sev_hunt.defeated:
		failure = "The Sev route needs a town save with ST-104 and no Sev victory"
		return
	var old_seals := int(app.view.chapter.seals)
	var old_books := int(app.view.sev_hunt.report_book.count)
	var old_budget: Dictionary = app.view.budget.duplicate()
	var completes_chapter: bool = app.view.hunt.reported
	var victories := await _play_hunt_route("sev", "MG02")
	if not failure.is_empty():
		return
	if side_checks.get("sev_regions") != ["RG06", "RG03"] or victories.size() != 6 or victories[-1] != "BATTLE-MG02":
		failure = "The Sev hunt missed its two-region path or authentic battle victory"
		return
	if app.view.get("phase") != "TOWN" or not app.view.sev_hunt.reported \
			or int(app.view.chapter.seals) != old_seals + 1 or int(app.view.sev_hunt.report_book.count) != old_books + 1:
		failure = "Sev's first report did not award exactly one seal and book"
		return
	var budget: Dictionary = app.view.budget
	if completes_chapter and (budget.milestone != "CH2_COMPLETE" or int(budget.expedition) != 16 or int(budget.battle) != 12):
		failure = "The two first reports did not grant the Chapter 3 budget"
		return
	if not completes_chapter and budget != old_budget:
		failure = "Sev's report alone changed the chapter budget"
		return
	side_checks["sev_victories"] = victories
	if mode == "sev-awakening":
		if side_checks.get("sev_windows") != ["MG02-W1", "MG02-W2"]:
			failure = "Both live Sev memory windows were not reached"
			return
		if not await _check_sev_awakened():
			return
	await _check_hunt_report_archive("MG02", "SB-X02", "sev")


func _check_sev_window(command: String, id: String) -> bool:
	var memory: Dictionary = app.view.town_memory if command == "remember" else app.view.battle_memory
	var heading: String = app.view.sev_hunt.name + " · " + ("追忆" if command == "remember" else "战斗暂停")
	if memory.get("id") != id or memory.get("general_id") != "MG02" or not _panel_has(heading):
		failure = "The projected memory did not belong to Sev"
		return false
	if command == "remember" and not app.view.hunt.memory.is_empty():
		failure = "Sev's active remembrance also appeared in Ado's record"
		return false
	side_checks.get_or_add("sev_windows", []).append(id)
	return true


func _check_sev_awakened() -> bool:
	var hunt: Dictionary = app.view.sev_hunt
	var records: Array = hunt.memory_records
	var version := int(app.client.frame.state_version)
	if not hunt.awakened or not hunt.reported or records.size() != 2 or not await _ado_tab("chapter"):
		failure = "Sev's awakening, separate first report or two records were missing"
		return false
	if app.command_buttons.has("remember MG02") or not _panel_has(hunt.name + "已保留记忆") \
			or not await _press("remembrance-history-MG02"):
		failure = "Sev offered another choice or lost her committed transcript"
		return false
	if not _panel_has(hunt.name + " · 已提交的追忆对白") or app.command_buttons.has("town-roster"):
		failure = "The transcript did not open in Sev's archive"
		return false
	for record: Dictionary in records:
		if not record.committed or record.lines.size() != 2:
			failure = "An uncommitted or incomplete memory appeared in the transcript"
			return false
		for line: Dictionary in record.lines:
			if not _panel_has(line.text):
				failure = "A committed line was missing from Sev's transcript"
				return false
	await _capture("sev-remembrance-transcript")
	if not await _press("remembrance-history-MG02") or int(app.client.frame.state_version) != version:
		failure = "Reading Sev's transcript changed the save"
		return false
	side_checks["sev_memory_records"] = records
	return true


func _sev_remembrance() -> void:
	var hunt: Dictionary = app.view.sev_hunt
	if app.view.phase != "TOWN" or not hunt.reported or hunt.awakened or hunt.evidence or not await _ado_tab("chapter"):
		failure = "The remembrance needs a reported but unawakened Sev save without the evidence"
		return
	if not _panel_has("追忆尚缺缝补红围巾、镇民核实的证词") or app.command_buttons.has("remember MG02"):
		failure = "The archive offered Sev's remembrance without the prerequisites"
		return
	var old_seals := int(app.view.chapter.seals)
	var old_books := int(hunt.report_book.count)
	var old_day := int(app.view.day)
	var report_day := int(hunt.report_delivery_day)
	await _play_hunt_route("sev-recall", "MG02")
	if not failure.is_empty():
		return
	if not _check_sev_window("remember", "MG02-W2") or not app.view.town_memory.enabled \
			or app.view.sev_hunt.awakened or int(app.view.day) != old_day + 1 \
			or int(app.view.chapter.seals) != old_seals or int(app.view.sev_hunt.report_book.count) != old_books \
			or int(app.view.sev_hunt.report_delivery_day) != report_day:
		failure = "Preparing the second remembrance changed a report or advanced time beyond the material trip"
		return
	side_checks["sev_remembrance_pending"] = app.view.town_memory


func _sev_remembrance_resume() -> void:
	if not _check_sev_window("remember", "MG02-W2") or not app.view.town_memory.enabled:
		return
	var day := int(app.view.day)
	var seals := int(app.view.chapter.seals)
	var book := int(app.view.sev_hunt.report_book.count)
	var report_day := int(app.view.sev_hunt.report_delivery_day)
	if not await _command("remember retain MG02-W2"):
		return
	var hunt: Dictionary = app.view.sev_hunt
	var reply: String = hunt.memory_records[1].lines[1].text if hunt.awakened else ""
	if reply.is_empty() or not app.subtitles.text.contains(reply) or not app.view.town_memory.is_empty() \
			or int(app.view.day) != day or int(app.view.chapter.seals) != seals \
			or int(hunt.report_book.count) != book or int(hunt.report_delivery_day) != report_day:
		failure = "Sev's retained reply was missing or the remembrance changed the original report"
		return
	if await _check_sev_awakened():
		await _check_hunt_report_archive("MG02", "SB-X02", "sev")


func _chapter_three_hunt(general_id: String, goal_region: String, book_id: String, seals: int) -> void:
	var hunt := _route_hunt(general_id)
	if app.view.get("phase") != "TOWN" or app.view.budget.milestone != "CH2_COMPLETE" \
			or hunt.is_empty() or hunt.defeated:
		failure = "The %s route needs a town save with both Chapter 2 reports and no victory over that general" % general_id
		return
	var old_seals := int(app.view.chapter.seals)
	var old_books := int(hunt.report_book.count)
	var old_budget: Dictionary = app.view.budget.duplicate()
	var evidence_key := general_id.to_lower()
	var victories := await _play_hunt_route(evidence_key, general_id)
	if not failure.is_empty():
		return
	if side_checks.get(evidence_key + "_regions") != ["RG07", goal_region] or victories.size() != 6 \
			or victories[-1] != "BATTLE-" + general_id:
		failure = "The %s hunt missed its two-region path or authentic battle victory" % general_id
		return
	hunt = _route_hunt(general_id)
	if app.view.get("phase") != "TOWN" or not hunt.reported or int(app.view.chapter.seals) != old_seals + seals \
			or int(hunt.report_book.count) != old_books + 1 or app.view.budget != old_budget:
		failure = "The %s report awarded the wrong seals, book or budget" % general_id
		return
	side_checks[evidence_key + "_victories"] = victories
	await _check_hunt_report_archive(general_id, book_id, evidence_key)


func _check_hunt_report_archive(general_id: String, book_id: String, evidence_key: String) -> void:
	var hunt := _route_hunt(general_id)
	if app.view.get("phase") != "TOWN" or not hunt.get("reported", false) or hunt.report_book.id != book_id:
		failure = "The saved %s report or its book did not restore" % general_id
		return
	var version := int(app.client.frame.state_version)
	if not await _ado_tab("chapter"):
		return
	if app.command_buttons.has("quest report %s CONFIRM" % general_id):
		failure = "The first %s report was offered again" % general_id
		return
	if not await _press("chapter-history") or not await _press("archive-report-" + general_id):
		return
	if not app._archive_page.heading.text.contains(hunt.name) \
			or not app._archive_page.body.text.contains(hunt.report_book.name) \
			or int(app.client.frame.state_version) != version:
		failure = "Reopening the %s report lost its receipt or changed the save" % general_id
		return
	side_checks[evidence_key + "_report"] = hunt
	side_checks[evidence_key + "_budget"] = app.view.budget


func _campaign_research_route() -> void:
	var path: String = app.data_dir.path_join(app.case_name + ".research-commands.json")
	var route: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not route is Dictionary or not route.get("commands") is Array:
		failure = "Missing native research route: " + path
		return
	var victories: Array[String] = []
	for value in route.commands:
		var key := str(value)
		var args := key.split(" ")
		match args[0]:
			"facility":
				if not await _ado_tab("construction"):
					return
				if app.construction_project != "lamp_store" and not await _press("construction-project-lamp_store"):
					return
				var quote: Dictionary = _construction_project("lamp_store").quote
				if int(quote.target) != int(args[3]) or not quote.blocker.is_empty():
					failure = "The observatory did not expose an available next-level quote"
					return
			"depart", "buy_supply":
				if not await _ado_tab("expedition"):
					return
			"rest":
				if not app.command_buttons.has(key) and not await _ado_tab("expedition"):
					return
			"research":
				if not await _ado_tab("research"):
					return
				if args[1] == "correlate" and not await _press("research-member-" + args[2]):
					return
			"place", "stance", "deploy":
				if not await _route_member_action(args):
					return
			"run":
				if not await _ado_steps(victories):
					return
				continue
		if not await _command(key):
			return
	side_checks["funding_victories"] = victories
	if not victories.is_empty() and app.view.get("phase") != "TOWN":
		failure = "Funding trip did not return to town"
		return
	if mode == "research-early":
		var research: Dictionary = app.view.research
		if research.fragments.size() != 2 or int(research.level) != 2 or research.action != "correlate" \
				or research.blocker.is_empty() or app.command_buttons.has("research test CONFIRM"):
			failure = "Early terminal analysis or the next-stage gate was incorrect"
		return
	await _check_campaign_research()


func _check_campaign_research() -> void:
	var research: Dictionary = app.view.get("research", {})
	var budget: Dictionary = app.view.get("budget", {})
	if app.view.get("phase") != "TOWN" or not research.get("delivered", false) or research.fragments.size() != 3 \
			or budget.get("milestone") != "CH3_COMPLETE" or int(budget.expedition) != 20 or int(budget.battle) != 16:
		failure = "The saved research delivery, fragments or Chapter 3 budget were missing"
		return
	var version := int(app.client.frame.state_version)
	if not await _ado_tab("research"):
		return
	if not _panel_has("ST-303 已交付") or app.command_buttons.has("research deliver CONFIRM") \
			or (research.reward.choices.is_empty() and research.reward.selected.is_empty()):
		failure = "Research was offered twice or its first-delivery entitlement was missing"
		return
	if not await _ado_tab("chapter") or not await _press("chapter-history") or not await _press("archive-ST-303"):
		return
	if not app._archive_page.heading.text.contains("研究交付") or not app._archive_page.body.text.contains(research.fragments[2]) \
			or int(app.client.frame.state_version) != version:
		failure = "Reopening the research receipt lost its last fragment or changed the save"
		return
	side_checks["research"] = research
	side_checks["research_budget"] = budget


func _finale_steps() -> bool:
	var snapshot: Dictionary = app.view.battle_view
	var encounter: String = snapshot.encounter
	if app.board.coordinate_map.is_empty() or app.command_buttons["flee CONFIRM"].visible:
		failure = "The finale battle did not open its board or still offered retreat"
		return false
	if encounter == "BATTLE-ADMIN" and int(snapshot.tick) != int(app.view.finale.reports[0].tick):
		failure = "The second battle reset the first battle's clock"
		return false
	for i in range(320):
		if app.view.phase != "BATTLE":
			var report: Dictionary = app.view.finale.reports[-1]
			if report.encounter_id != encounter:
				failure = "The finale was missing its completed battle report"
				return false
			return true
		if not await _command("step"):
			return false
	failure = "Finale fight exceeded the smoke step limit: " + encounter
	return false


func _campaign_finale_route() -> void:
	var path: String = app.data_dir.path_join(app.case_name + ".finale-commands.json")
	var route: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not route is Dictionary or not route.get("commands") is Array:
		failure = "Missing native finale route: " + path
		return
	var victories: Array[String] = []
	for value in route.commands:
		var key := str(value)
		var args := key.split(" ")
		match args[0]:
			"maintain", "rest", "depart", "buy_supply", "pack_medical":
				if not await _ado_tab("expedition"):
					return
			"summon":
				if not await _ado_tab("chapter"):
					return
			"recruit", "squad", "level_up":
				if not await _ado_tab("roster"):
					return
				if args[0] == "level_up" and not await _route_member_action(args):
					return
				if args[0] == "squad" and args[2] == "off" and app.selected_id != args[1] \
						and not await _press("member-" + args[1]):
					return
			"book":
				if args[1] == "choice":
					if not await _ado_tab("research"):
						return
				else:
					if not await _ado_tab("skills"):
						return
					if app.selected_id != args[2] and not await _press("book-member-" + args[2]):
						return
			"place", "stance", "deploy":
				if app.view.phase == "TOWN" and not await _ado_tab("roster"):
					return
				if not await _route_member_action(args):
					return
			"finale":
				if args[1] in ["prepare", "enter"] and not await _ado_tab("finale"):
					return
				if args[1] == "prepare" and not app.finale_preview_open:
					if not await _press("finale-preview") or not _panel_has("管理员生命降至 25%") \
							or not _panel_has("初生魔王") or not await _press("finale-preview"):
						failure = "The finale preview omitted actual opponents or the formatting warning"
						return
				if args[1] in ["deploy", "place"] and not await _press("member-" + args[2]):
					return
				if args[1] == "place" and not await _press_cell("cell-%s-%s" % [args[3], args[4]], key):
					return
			"run":
				if app.view.get("finale", {}).get("stage") in ["DEMON", "ADMIN"]:
					if not await _finale_steps():
						return
				elif not await _ado_steps(victories):
					return
				continue
		if not await _command(key):
			return
		if key == "finale prepare CONFIRM":
			var budget: Dictionary = app.view.budget
			if budget.milestone != "FINALE_READY" or int(budget.expedition) != 24 or int(budget.battle) != 20:
				failure = "Finale preparation did not grant the authoritative budget"
				return
		if key == "finale enter CONFIRM" and (app.view.phase != "FINAL_CHOICE" or app.command_buttons.has("step") \
				or not app.command_buttons.has("finale choice KEEP_SELF")):
			failure = "Entry bypassed the player's identity choice"
			return
	side_checks["training_victories"] = victories
	if mode == "finale-training":
		if app.view.get("phase") != "TOWN" or not app.view.finale.get("prepared", false):
			failure = "Finale training did not leave a prepared town save"
		return
	await _check_campaign_ending("FIN-C" if mode == "finale-defeat" else "FIN-A")


func _check_campaign_ending(id: String) -> void:
	var ending: Dictionary = app.view.get("finale", {}).get("ending", {})
	if ending.get("id") != id or not _panel_has(ending.get("title", "")) \
			or app.command_buttons.has("step") or app.command_buttons.has("finale enter CONFIRM"):
		failure = "The sealed finale ending did not reopen as a result"
		return
	var reports: Array = app.view.finale.reports
	if id == "FIN-A" and (reports.size() != 2 or reports[0].encounter_id != "BATTLE-DEMON" \
			or reports[1].encounter_id != "BATTLE-ADMIN" or not reports.all(func(row: Dictionary): return row.result == "VICTORY")):
		failure = "The A ending lacks both actual victories"
		return
	if id == "FIN-C" and (reports.is_empty() or reports[-1].result != "DEFEAT"):
		failure = "The C result lacks its actual defeat"
		return
	side_checks["finale_ending"] = ending
	side_checks["finale_reports"] = reports
	await _capture("ending")


func _fortress_frame() -> bool:
	var site: String = app.view.site
	var landmark: String = app.board.FORTRESS_LANDMARKS.get(site, "")
	if not app.board.show_models or landmark.is_empty():
		return true
	var phase := "map"
	if app.view.phase == "BATTLE":
		phase = "battle"
	elif app.view.route.get("contact_pending", false):
		phase = "contact"
	var mark := "fortress-%s-%s" % [phase, site]
	if fortress_frames.has(mark):
		return true
	var stage = app.board.stage
	var ink_court := FORTRESS_ART_LABELS.has(site) and phase != "map"
	if ink_court:
		var art: String = FORTRESS_ART_LABELS[site]
		if app.board._field_art == null or app.board._field_art.resource_path != "res://assets/fortress/%s_ink_court.png" % art \
				or stage.scenery.has(site) or stage.scenery.has("fortress-left"):
			failure = "The painted court and 3D scenery did not match: " + mark
			return false
		landmark = "fortress-%s-ink" % art
	elif not stage.scenery.has(site) or stage.audit.field_props.get(site) != landmark:
		failure = "Fortress landmark is missing: " + mark
		return false
	if phase == "map":
		if app.board._field_art == null or app.board._field_art.resource_path != "res://assets/fortress/route_ink_map.png":
			failure = "The fortress route did not use its own map backing: " + mark
			return false
		var known: Array = app.board.map_data.get("objects", []).map(func(entry): return entry.id)
		for part in stage.scenery:
			if part not in known:
				failure = "Fortress landmark revealed an undiscovered site: " + part
				return false
	else:
		var rendered_obstacles := 0
		for row in app.board.map_data.get("battle_cells", []):
			var obstacle := "masonry-%d-%d" % [int(row.q), int(row.r)]
			if stage.scenery.has(obstacle) != (row.terrain_id == "HIGH_OBSTACLE"):
				failure = "Fortress obstacle differs from the rules board: " + obstacle
				return false
			if stage.scenery.has(obstacle):
				rendered_obstacles += 1
		var actual: Array = stage.scenery.keys().filter(func(part): return part.begins_with("masonry-"))
		if actual.size() != rendered_obstacles:
			failure = "Fortress rubble outside the rules board: " + mark
			return false
	await _capture(mark)
	if capture and not ink_court and not _visible_landmark(site):
		failure = "Fortress landmark was outside the 3D camera: " + mark
		return false
	fortress_frames[mark] = landmark
	return true


func _ado_tab(tab: String) -> bool:
	return app.town_tab == tab or await _press("town-" + tab)


func _ado_steps(victories: Array[String]) -> bool:
	var encounter: String = app.view.battle_view.encounter
	for i in range(160):
		if app.view.phase != "BATTLE":
			var result: Dictionary = app.view.battle_results[-1]
			if result.result != "VICTORY" or result.encounter_id != encounter:
				failure = "Natural battle was lost: " + encounter
				return false
			victories.append(encounter)
			if encounter == "BATTLE-MG01" and measure != null:
				measure.finish()
			return true
		if not app.view.battle_memory.is_empty():
			return true
		if not await _command("step"):
			return false
		if feedback_check and encounter == "BATTLE-MG01" and not await _check_combat_feedback():
			return false
		if aid_check and encounter == "BATTLE-MG01" and not await _observe_aid():
			return false
		if bow_check and encounter == "BATTLE-MG01":
			var snapshot: Dictionary = app.view.battle_view
			if not bow_marks.has("draw") and snapshot.actors.any(func(actor): return actor.has("bow_pending")):
				bow_marks["draw"] = int(snapshot.tick)
				await _capture("bow-draw")
			if not bow_marks.has("flight") and app.board.stage.flying_projectiles.any(
					func(projectile): return projectile.mesh != null and not projectile.mesh is SphereMesh):
				bow_marks["flight"] = int(snapshot.tick)
				await _capture("bow-flight")
		if melee_check and encounter == "BATTLE-MG01" and not melee_marks.has("windup"):
			for actor in app.view.battle_view.actors:
				if not actor.has("melee_pending"):
					continue
				var pawn: Node3D = app.board.stage.actors[actor.id].node
				await get_tree().create_timer(0.32).timeout
				if pawn.player.current_animation != "GapHold" or pawn.gap_cast != actor.melee_pending.id:
					failure = "The authored melee hold was not reached from the windup receipt"
					return false
				melee_marks["windup"] = int(app.view.battle_view.tick)
				await _capture("melee-windup")
				break
		if melee_check and encounter == "BATTLE-MG01" and not melee_marks.has("skill") \
				and int(app.board.stage.audit.melee_skill_releases) > 0:
			await get_tree().create_timer(0.23).timeout
			await _capture("melee-release")
			melee_marks["skill"] = int(app.view.battle_view.tick)
		if encounter == "BATTLE-MG01" and measure != null:
			await get_tree().create_timer(0.065).timeout
		if encounter == "BATTLE-MG01" and i == 4:
			await _capture("ado-battle")
		if encounter == "BATTLE-MG01" and app.view.get("battle_view") is Dictionary:
			for event in app.view.battle_view.events:
				var skill: String = event.get("move", "")
				if skill not in ["MG01-A", "MG01-B", "MG01-C"] or event.type not in ["windup", "release"]:
					continue
				var mark := "%s-%s" % [skill, event.type]
				if not ado_frames.has(mark):
					ado_frames[mark] = true
					if capture:
						await get_tree().create_timer(0.17 if event.type == "windup" else 0.095).timeout
					await _capture(mark)
	failure = "Battle did not resolve: " + encounter
	return false


func _check_settlement(reason: String, complete: bool) -> void:
	var summary: Variant = app.view.get("settlement")
	var title := "侦路调查已交付" if complete else "远征结算"
	if not summary is Dictionary or summary.get("result") != reason or app.view.get("complete") != complete:
		failure = "Unexpected settlement: " + reason
		return
	for control in app.actions.get_children():
		if control is Label and control.text == title:
			return
	failure = "Settlement is missing from the action panel: " + reason


func _rescue_route() -> void:
	var path: String = app.data_dir.path_join(app.case_name + ".rescue-route.json")
	var route: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not route is Dictionary or not route.get("commands") is Array:
		failure = "Missing native rescue route: " + path
		return
	var victim := "INIT-S03-A"
	var batch_id := "CAP-0002"
	var battles := 0
	for command in route.commands:
		var parts: PackedStringArray = command.split(" ")
		if parts[0] in ["squad", "recruit", "deploy", "care"] and not await _ado_tab("roster"):
			return
		if command == "depart CONFIRM" and not await _ado_tab("expedition"):
			return
		if app.view.phase == "TOWN" and parts[0] in ["rescue", "buy_supply", "rest"] and not await _ado_tab("rescue"):
			return
		var needs_member := parts[0] in ["deploy", "care"] or (parts[0] == "squad" and parts[2] == "off")
		if needs_member and app.selected_id != parts[1]:
			if not await _press("member-" + parts[1]):
				return
		if command == "run 600":
			var expected := "DEFEAT" if battles == 0 else "RESCUE_SUCCESS"
			if not await _rescue_battle(expected):
				return
			battles += 1
			continue
		if command == "rescue investigate start " + batch_id + " CONFIRM":
			if app.command_buttons.has("rescue " + batch_id + " CONFIRM"):
				failure = "An unknown destination offered direct rescue"
				return
		if not await _command(command):
			return
		if command == "rescue investigate inspect tracks":
			if app.command_buttons.has("rescue investigate inspect tracks"):
				failure = "Recorded tracks offered a duplicate inspection"
				return
			await _capture("tracks")
		if command == "rescue investigate inspect marker":
			await _capture("marker")
		if command == "rescue " + batch_id + " CONFIRM":
			await _capture("rescue-battle")
			if app.board.map_data.get("battle_cells", []).is_empty() or (app.board.show_models and app.board.stage.actors.is_empty()):
				failure = "The rescue battlefield was not drawn from the native board"
				return
		if command == "care " + victim:
			await _capture("care")
	if battles != 2 or int(app.view.day) != 6:
		failure = "The rescue flow did not take the expected action days"
		return
	var rescued: Dictionary = {}
	for member in app.view.party:
		if member.instance_id == victim:
			rescued = member
	var batch: Dictionary = app.view.rescue.batches[0]
	if rescued.is_empty() or int(rescued.hp) != int(rescued.max_hp) or int(rescued.injury_days) != 0 or rescued.equipment != ["EQ-000001"] or int(batch.deadline) != 5 or not batch.members.is_empty() or batch.recovered.size() != 1:
		failure = "The original rescued person or equipped item did not return to the party"
		return
	await _capture("rejoined")


func _rescue_battle(expected: String, members: Array = ["INIT-S03-A"], names: Array = ["弓兵 A"], return_day := 5) -> bool:
	for i in range(160):
		if app.view.phase != "BATTLE":
			var settlement: Dictionary = app.view.settlement
			var ok: bool = settlement.result == expected
			if expected == "DEFEAT":
				ok = ok and settlement.get("missing_ids", []) == members
			else:
				ok = ok and settlement.get("rescued_ids", []) == members and int(settlement.day) == return_day and int(settlement.rescued_injury_days) == 2
			if not ok:
				failure = "Unexpected rescue-path settlement: " + str(settlement.result)
				return false
			var member_label := ("失联  " if expected == "DEFEAT" else "已救回  ") + "、".join(names)
			if not _panel_has(member_label):
				failure = "The settlement did not name the original missing members"
				return false
			await _capture("defeated" if expected == "DEFEAT" else "rescued")
			if expected == "DEFEAT":
				if not await _check_finished_report("RG01-N03", "DEFEAT", "我", "defeat-report"):
					return false
				if not await _press("battle-log"):
					return false
			return true
		if not await _command("step"):
			return false
	failure = "The rescue-path battle did not resolve"
	return false


func _check_rescue_resume() -> void:
	if app.view.get("phase") != "MISSING_SEARCH" or int(app.view.day) != 2 or int(app.view.supply) != 2:
		failure = "The in-progress investigation did not restore"
		return
	var active: Dictionary = app.view.rescue.active
	var batch: Dictionary = app.view.rescue.batches[0]
	if active.id != "CAP-0002" or batch.steps != ["tracks"] or int(batch.deadline) != 5 or not app.command_buttons.has("rescue investigate inspect marker"):
		failure = "The saved tracks, deadline or continuation control was lost"


func _ado_sample() -> void:
	if app.view.get("phase") != "EXPLORE" or app.view.region != "RG02" or app.view.site != "G":
		failure = "The benchmark must start at the archived fortress contact"
		return
	if measure != null:
		measure.begin("BATTLE-MG01")
	var preview: Node3D
	var preview_id := "INIT-S02-B" if melee_check else "INIT-S03-A"
	var preview_name := "melee" if melee_check else "bow"
	if aid_check:
		preview_name = "aid"
		for member in app.view.party:
			if member.unit_id == "M02" and member.deployed:
				preview_id = member.instance_id
				break
	if melee_check or bow_check or aid_check:
		preview = await _check_model_deployment(preview_id, preview_name)
		if preview == null:
			return
	if not await _command("fight"):
		return
	if preview != null and app.board.stage.actors.get(preview_id, {}).get("node") != preview:
		failure = "The deployment model was replaced at combat entry"
		return
	if "--ado-panel-check" in OS.get_cmdline_user_args() and not await _check_ado_panel():
		return
	var wins: Array[String] = []
	for reply in ["memory evidence MG01-W1", "memory retain MG01-W2"]:
		if not await _ado_steps(wins) or not await _command(reply):
			return
	if not await _ado_steps(wins):
		return
	if wins != ["BATTLE-MG01"] or app.ado_sound_counts.get("whistle", 0) != 1:
		failure = "No authentic victory or whistle cue from the fortress checkpoint"
	if feedback_check and not ["damage", "absorbed", "healed", "down", "settings"].all(func(key): return feedback_marks.has(key)):
		failure = "The fortress run did not cover all combat feedback and display settings"
	if melee_check:
		var audit: Dictionary = app.board.stage.audit
		var clips: Dictionary = audit.clips
		if int(audit.melee_peak) != 2 or not melee_marks.has("skill") or \
				not ["MeleeAdvance", "MeleeStop", "MeleeAttack", "GapSet", "GapHold", "GapStrike"].all(func(key): return int(clips.get(key, 0)) > 0):
			failure = "The fortress run omitted a melee model or a live core clip"
		melee_marks["handoff"] = true
	if bow_check:
		var audit: Dictionary = app.board.stage.audit
		var clips: Dictionary = audit.clips
		if int(audit.bow_peak) != 2 or not bow_marks.has("draw") or not bow_marks.has("flight") \
				or not ["BowAttack", "BowLoad", "BowRelease"].all(func(key): return int(clips.get(key, 0)) > 0):
			failure = "The fortress run omitted the two archers or a combat bow clip"
			return
		for shot in audit.bow_shots.values():
			if shot.has("aim_dot") and float(shot.aim_dot) < 0.998:
				failure = "The bow's release axis did not point at the committed target"
				return
		bow_marks["handoff"] = true
	if aid_check:
		var audit: Dictionary = app.board.stage.audit
		if int(audit.aid_peak) != 1 or int(audit.aid_contacts) < 1 or not aid_marks.has("hold") \
				or not aid_marks.has("heal") or not ["AidWalk", "AidStop", "AidRaise", "AidHold", "AidFire"].all(
					func(clip): return int(audit.clips.get(clip, 0)) > 0):
			failure = "The fortress run omitted an apothecary pose or a native heal"
			return
		aid_marks["handoff"] = true


func _ado_auto_sample() -> void:
	if app.view.get("phase") != "EXPLORE" or app.view.region != "RG02" or app.view.site != "G":
		failure = "The automatic benchmark needs the original fortress contact"
		return
	if app.board.stage.profile_assets:
		var marker_count: int = app.board._unit_markers.size()
		if marker_count == 0 or not app.board.deployment_open:
			failure = "The contact board was unavailable while preparing visuals"
			return
		var fallback_drag_target := ""
		for member in app.view.party:
			if member.deployed and member.deployable and not app.board.stage.actors.has(member.instance_id):
				var cell: Vector2i = app.board.cell_index(member.position)
				if app.board._deployment_member(app.board.coordinate_map[cell]) != member.instance_id:
					failure = "A deployment token could not be picked while its model was loading"
					return
				fallback_drag_target = member.instance_id
				break
		side_checks["contact_open"] = {
			"markers": marker_count, "models": app.board.stage.actors.size(),
			"deployment_open": true, "fight_enabled": not app.command_buttons["fight"].disabled,
			"fallback_drag_target": fallback_drag_target}
	var contact_models := {}
	if "--contact-model-check" in OS.get_cmdline_user_args():
		contact_models = await _contact_models("MG01", 1)
		if contact_models.is_empty():
			return
		var before_capture := capture
		capture = true
		await _capture("enemy-contact")
		capture = before_capture
	var prepared_rows: Dictionary = app._battle_rows.duplicate()
	if prepared_rows.is_empty() or app._combat_actions.is_visible_in_tree() or app.command_buttons.has("combat-playback"):
		failure = "The contact panel did not prepare hidden battle rows"
		return
	if measure != null:
		measure.begin("BATTLE-MG01")
	if not await _command("fight"):
		return
	var reused_rows := 0
	for actor in app.view.actors:
		var row: Button = app._battle_rows.get(actor.id)
		if row == null or row.tooltip_text != app._battle_health(actor) or not row.is_visible_in_tree():
			failure = "The fight receipt did not populate its actual battle actor: " + str(actor.id)
			return
		if prepared_rows.get(actor.id) == row:
			reused_rows += 1
	if reused_rows != prepared_rows.size() or reused_rows != app.view.actors.size():
		failure = "The original contact did not reuse all prepared battle rows"
		return
	side_checks["contact_battle_rows_reused"] = reused_rows
	if not contact_models.is_empty() and not _verify_contact_handoff(contact_models):
		return
	if not app._playback_running or app._battle_pace != 1:
		failure = "The original contact did not start continuous combat at normal speed"
		return
	if "--contact-profile-only" in OS.get_cmdline_user_args():
		app._toggle_playback()
		var stage = app.board.stage
		if not await _wait_until(func(): return not stage._has_model_work() \
				and stage.actors.size() == app.view.actors.size(), 8000):
			failure = "The contact profile could not reach the complete first battle board"
			return
		await RenderingServer.frame_post_draw
		await get_tree().process_frame
		if int(app.view.battle_view.tick) != 0 or app.client.busy:
			failure = "The contact profile advanced beyond the opening board"
			return
		side_checks["contact_profile_ready"] = {"tick": 0, "models": stage.actors.size()}
		if measure != null:
			measure.finish()
		return
	if "--cycle-window-focus" in OS.get_cmdline_user_args() and not await _check_auto_window_focus():
		return
	var panel_tick := int(app.view.battle_view.tick)
	var controls := [app.command_buttons["settings"], app.command_buttons["battle-log"]]
	var panel_children: int = app.actions.get_child_count()
	if not await _wait_until(func() -> bool: return int(app.view.battle_view.tick) >= panel_tick + 8 and not app.client.busy, 15000):
		failure = "Automatic playback did not reach the panel reuse checkpoint"
		return
	if app.actions.get_child_count() != panel_children or app.command_buttons["settings"] != controls[0] \
			or app.command_buttons["battle-log"] != controls[1] or controls[0].disabled or controls[1].disabled:
		failure = "Battle playback rebuilt or duplicated the settings and battle report buttons"
		return
	if app.board.stage.profile_assets and app.board.show_models:
		for actor in app.view.actors:
			if not app.board.stage.actors.has(actor.id):
				failure = "The model did not catch up with the active battle: " + str(actor.id)
				return
		side_checks["battle_models_ready"] = app.board.stage.actors.size()
	side_checks["steady_battle_panel"] = {"children": panel_children, "ticks": [panel_tick, int(app.view.battle_view.tick)]}
	if not await _finish_automatic_ado("auto"):
		return
	if measure != null:
		measure.finish()
	if not await _check_paused("victory"):
		return
	side_checks["automatic_ticks"] = int(app.view.battle_view.tick)
	await _capture("auto-victory")


func _contact_models(kind: String, count: int) -> Dictionary:
	var stage = app.board.stage
	var enemies: Array = app.board.map_data.get("enemy_preview", [])
	var expected := enemies.filter(func(row: Dictionary) -> bool: return row.kind == kind)
	if expected.size() != count or not await _wait_until(func() -> bool:
			return expected.all(func(row: Dictionary) -> bool: return stage.actors.has(row.id)), 12000):
		failure = "The published enemy roster was not modelled at contact"
		return {}
	var nodes := {}
	for enemy in expected:
		var token: Dictionary = stage.actors[enemy.id]
		var cell: Vector2i = app.board.cell_index(enemy.position)
		var pixel: Vector2 = app.board.coordinate_map[cell]
		var foot: Vector2 = stage.foot_pixel(enemy.id)
		if not app.board._sideways or foot.distance_to(pixel) > 1.5 \
				or token.row.facing != enemy.facing or not app.board._unit_markers[enemy.id].appearance.enemy \
				or not app.board._unit_markers[enemy.id].appearance.modelled \
				or app.board._deployment_member(_deployment_body(enemy.id)) == enemy.id:
			failure = "An enemy model did not match the side camera, marker or deployment input"
			return {}
		nodes[enemy.id] = {"node": token.node, "position": enemy.position, "facing": enemy.facing}
	return nodes


func _verify_contact_handoff(nodes: Dictionary) -> bool:
	var stage = app.board.stage
	if int(app.view.battle_view.tick) != 0 or app.board.map_data.has("enemy_preview"):
		failure = "The enemy models were not checked at battle start"
		return false
	for id in nodes:
		var token: Dictionary = stage.actors.get(id, {})
		var row: Dictionary = app._combatants.get(id, {})
		if token.get("node") != nodes[id].node or row.get("pos") != nodes[id].position or row.get("facing") != nodes[id].facing:
			failure = "A battle-start model changed position, facing or instance: " + id
			return false
	side_checks["enemy_contact_handoffs"] = nodes.keys()
	return true


func _check_root_contact_models() -> void:
	if not await _command("move G"):
		return
	var models := await _contact_models("EN01", 2)
	if models.is_empty():
		return
	await _capture("root-contact")
	var id := "INIT-S01-A"
	var version: int = app.client.frame.state_version
	var stage = app.board.stage
	var original: Vector2i = app.board.cell_index(stage.actors[id].row.pos)
	var enemy: String = models.keys().front()
	await _drag(_board_pixel(_deployment_body(enemy)), _board_screen(original), "enemy-drag")
	if int(app.client.frame.state_version) != version or app.selected_id == enemy:
		failure = "Dragging the enemy model changed the deployed roster"
		return
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(original), "friendly-slot")
	if int(app.client.frame.state_version) != version or app.selected_id != id:
		failure = "An allied model could not be dragged back to its original slot"
		return
	if await _command("fight") and _verify_contact_handoff(models):
		await _capture("root-opening")


func _check_contact_inspection() -> void:
	var board = app.board
	var enemies: Array = board.map_data.get("enemy_preview", [])
	if enemies.size() != 3 or not await _wait_until(func() -> bool:
			return enemies.all(func(row: Dictionary) -> bool: return board.stage.actors.has(row.id)), 12000):
		failure = "The fortress contact did not load its three enemy models"
		return
	await get_tree().process_frame
	var layout: Dictionary = board._contact_badges
	var seen: Array[Rect2] = []
	var evidence := {}
	for enemy in enemies:
		var badge: Dictionary = layout.get(enemy.id, {})
		if badge.is_empty() or badge.tile != board.coordinate_map[board.cell_index(enemy.position)] \
				or badge.label != enemy.badge or seen.any(func(rect: Rect2) -> bool: return rect.intersects(badge.box)):
			failure = "A contact badge was missing, displaced or overlapped"
			return
		seen.append(badge.box)
		evidence[enemy.id] = {"name": enemy.name, "badge": badge.label, "cell": enemy.position}
	if board._overlay.get_index() < board.stage.get_index():
		failure = "The contact overlay was still behind the combat models"
		return
	var spear: String = enemies.filter(func(enemy: Dictionary) -> bool: return enemy.kind == "EN17").front().id
	var ado: String = enemies.filter(func(enemy: Dictionary) -> bool: return enemy.kind == "MG01").front().id
	var saved: String = app.client.frame.files["save.json"]
	var version: int = app.client.frame.state_version
	var deploy_selection: String = app.selected_id
	if not board._show_deployment or not app.location.text.ends_with("布阵"):
		failure = "The contact board did not display its deployment grid"
		return
	await _capture("contact-plaques")
	if not await _press("inspect-enemy-" + spear) or board.contact_enemy_id != spear \
			or not app.command_buttons["inspect-enemy-" + spear].button_pressed \
			or not board.stage.actors[spear].node.visible or board.stage.actors[ado].node.visible \
			or not board.stage.contact_occluders.has(ado):
		failure = "The spear entry did not highlight its tile and reveal the model behind Ado"
		return
	await _capture("contact-spear")
	if not await _press("inspect-enemy-" + ado) or board.contact_enemy_id != ado \
			or app.command_buttons["inspect-enemy-" + spear].button_pressed or not board.stage.actors[ado].node.visible \
			or not await _press("inspect-enemy-" + ado) or not board.contact_enemy_id.is_empty() \
			or app.selected_id != deploy_selection or app.client.frame.state_version != version \
			or app.client.frame.files["save.json"] != saved:
		failure = "Switching or clearing the enemy inspection changed the deployment or save"
		return
	if not await _press("inspect-enemy-" + spear) or not await _command("fight") \
			or not board.contact_enemy_id.is_empty() or not board._contact_badges.is_empty() \
			or not board.stage.contact_occluders.is_empty() or not board.stage.actors[ado].node.visible \
			or app.command_buttons.has("inspect-enemy-" + spear) or board._show_deployment:
		failure = "The inspection hid an enemy or remained visible after starting combat"
		return
	side_checks["contact_inspection"] = {"enemies": evidence, "selected": spear, "read_only_version": version}
	await _capture("contact-battle")


func _check_auto_window_focus() -> bool:
	var window := get_window()
	if DisplayServer.get_name() == "headless" or not window.has_focus() \
			or not await _wait_until(func(): return int(app.view.battle_view.tick) >= 2 and not app.client.busy, 10000):
		failure = "The automatic fight did not reach the Windows focus check"
		return false
	var tick := int(app.view.battle_view.tick)
	var saved: String = app.client.frame.files["save.json"]
	var size_before := window.size
	window.mode = Window.MODE_MINIMIZED
	if not await _wait_until(app._window_minimized, 3000):
		failure = "Windows did not minimize the active fight"
		return false
	side_checks["focus_reported_while_minimized"] = window.has_focus()
	if not await _check_paused("minimized") or not app._playback_running \
			or int(app.view.battle_view.tick) != tick or app.client.frame.files["save.json"] != saved:
		failure = "The minimized window committed another turn or lost automatic playback intent"
		return false
	var stage = app.board.stage
	if not stage.window_hidden or stage.viewport_3d.render_target_update_mode != SubViewport.UPDATE_DISABLED:
		failure = "The hidden Windows battle board kept its render updates enabled"
		return false
	side_checks["minimized_board_rendering_disabled"] = true
	window.mode = Window.MODE_WINDOWED
	window.grab_focus()
	if not await _wait_until(func(): return window.has_focus() and int(app.view.battle_view.tick) > tick, 8000) \
			or not app._playback_running or window.size != size_before:
		failure = "Restoring the window did not restart the same automatic fight"
		return false
	if stage.window_hidden or stage.viewport_3d.render_target_update_mode != SubViewport.UPDATE_ALWAYS:
		failure = "Restoring the battle window did not restart board rendering"
		return false
	side_checks["restored_board_rendering_enabled"] = true
	side_checks["minimized_tick"] = tick
	side_checks["restored_tick"] = int(app.view.battle_view.tick)
	side_checks["restored_window"] = [window.size.x, window.size.y]
	await _capture("auto-window-restored")
	return true


func _check_minimized_contact() -> void:
	var window := get_window()
	var stage = app.board.stage
	if DisplayServer.get_name() == "headless" or app.view.phase != "EXPLORE" or app.view.site != "G" \
			or not app.board.deployment_open or stage.model != null:
		failure = "The check needs the original visible Ado contact before the shield is read"
		return
	var version := int(app.client.frame.state_version)
	var save: String = app.client.frame.files["save.json"]
	var actor_ids: Array = stage.actors.keys()
	window.mode = Window.MODE_MINIMIZED
	if not await _wait_until(func(): return app._window_minimized() and stage.window_hidden, 3000):
		failure = "The minimized contact did not reach the board renderer"
		return
	stage._load_scene(stage.MODEL_PATH, true)
	if not await _wait_until(func(): return stage.MODEL_PATH in stage._scenes_ready_to_present, 6500):
		failure = "The shield model was not read while contact was minimized"
		return
	if stage.model != null or stage.actors.keys() != actor_ids \
			or stage.viewport_3d.render_target_update_mode != SubViewport.UPDATE_DISABLED \
			or int(app.client.frame.state_version) != version or app.client.frame.files["save.json"] != save:
		failure = "The hidden contact attached actors, rendered or changed the save"
		return
	app._show_settings()
	window.mode = Window.MODE_WINDOWED
	window.grab_focus()
	if not await _wait_until(func(): return window.has_focus() and not stage.window_hidden, 3000) \
			or not stage.focused_pause or stage.model != null:
		failure = "Restoring the window did not preserve the settings pause"
		return
	if not await _press("settings-back"):
		return
	if not await _wait_until(func(): return stage.actors.has("INIT-S01-A") and not stage._has_model_work(), 6500) \
			or int(app.client.frame.state_version) != version or app.client.frame.files["save.json"] != save \
			or not app.board.deployment_open:
		failure = "The shield did not attach to the original contact after returning to the board"
		return
	side_checks["minimized_contact"] = {"shield_read": true, "hidden_actors": actor_ids.size(),
		"settings_still_open_on_restore": true, "restored_models": stage.actors.size(), "unchanged_version": version}
	if not await _command("fight") or not await _check_auto_window_focus():
		return
	if not await _press("combat-playback"):
		return


func _check_deferred_battle_sound(cue: String, tick: int, with_settings: bool) -> bool:
	var window := get_window()
	var before: int = app.client.frame.state_version
	var warning_count: int = app.sound_count
	var ado_before: Dictionary = app.ado_sound_counts.duplicate()
	app.command_buttons["step"].pressed.emit()
	window.mode = Window.MODE_MINIMIZED
	if not await _wait_until(func(): return app._window_minimized() and app.board.stage.window_hidden, 3000) \
			or not app.client.busy:
		failure = "The delayed beat did not remain in flight as Windows minimized"
		return false
	if not await _wait_ready() or int(app.view.battle_view.tick) != tick \
			or int(app.client.frame.state_version) != before + 1 or app._receipt_sounds != [cue] \
			or app.sound_count != warning_count or app.ado_sound_counts != ado_before:
		failure = "The minimized receipt missed its beat, played a sound, or queued the wrong sound"
		return false
	steps.append({"command": "step", "version": before + 1, "digest": app.client.frame.state_digest})
	if with_settings:
		app._show_settings()
	window.mode = Window.MODE_WINDOWED
	window.grab_focus()
	if not await _wait_until(func(): return window.has_focus() and not app.board.stage.window_hidden, 3000):
		failure = "The battle did not return to the foreground"
		return false
	if with_settings:
		if app.sound_count != warning_count or app.ado_sound_counts != ado_before or app._receipt_sounds != [cue]:
			failure = "Restoring with Settings open played the pending cue"
			return false
		if not await _press("settings-back"):
			return false
	var expected_ado: Dictionary = ado_before.duplicate()
	if cue != "warning":
		expected_ado[cue] = int(ado_before.get(cue, 0)) + 1
	if not app._receipt_sounds.is_empty() or app.sound_count != warning_count + int(cue == "warning") \
			or app.ado_sound_counts != expected_ado or int(app.client.frame.state_version) != before + 1 \
			or (cue == "warning" and not app.warning.text.contains("断誓横阵")):
		failure = "The foreground beat did not play exactly one cue from the saved receipt"
		return false
	side_checks[cue] = {"tick": tick, "version": before + 1, "settings_covered_restore": with_settings,
		"plays_while_minimized": 0, "plays_on_board": 1, "warning_text": app.warning.text}
	return true


func _check_minimized_battle_audio() -> void:
	var battle: Dictionary = app.view.get("battle_view", {})
	if DisplayServer.get_name() == "headless" or battle.get("encounter") != "BATTLE-MG01" \
			or int(battle.get("tick", -1)) != 19 or not get_window().has_focus() \
			or app._playback_running or app.sound_count != 0 or not app.ado_sound_counts.is_empty():
		failure = "The audio check needs the Windows Ado warning save without replayed cues"
		return
	if not await _command("step") or not await _check_deferred_battle_sound("MG01-A", 21, true):
		return
	for tick in range(22, 27):
		if not await _command("step"):
			return
		if int(app.view.battle_view.tick) != tick:
			failure = "Ado left the expected warning sequence"
			return
	await _check_deferred_battle_sound("warning", 27, false)


func _observe_aid() -> bool:
	var stage = app.board.stage
	var battle: Dictionary = app.view.battle_view
	if not aid_marks.has("stop"):
		for event in battle.events:
			if event.type != "move" or app._combatants.get(event.actor, {}).get("kind") != "M02":
				continue
			var mover: Node3D = stage.actors.get(event.actor, {}).get("node")
			if mover == null or not await _wait_until(func(): return mover.player.assigned_animation == "AidStop", 1100):
				failure = "The apothecary movement did not reach the authored stop before the next command"
				return false
			aid_marks["stop"] = int(battle.tick)
			break
	if not aid_marks.has("hold"):
		for row in battle.actors:
			if not row.has("aid_pending"):
				continue
			var pawn: Node3D = stage.actors[row.id].node
			if not await _wait_until(func(): return pawn.player.assigned_animation == "AidHold", 1200) \
					or pawn.cast_id != row.aid_pending.id:
				failure = "The actual aid windup did not reach the raised hold"
				return false
			aid_marks["hold"] = row.aid_pending.id
			await _capture("aid-windup")
			break
	if aid_marks.has("heal"):
		return true
	for event in battle.events:
		if event.type != "heal" or event.get("move") != "M02-A" or int(event.effective) <= 0:
			continue
		var action: Dictionary = stage.audit.aid_actions.get(event.action_id, {})
		if action.get("target") != event.target or action.get("effective") != event.effective:
			failure = "The capsule did not use the native healing target and value"
			return false
		if capture:
			var launched: bool = await _wait_until(func(): return stage.flying_projectiles.any(
				func(p): return p.mesh == stage.aid_capsules.get(true)), 1200)
			if not launched:
				failure = "A real heal was missing its capsule flight"
				return false
			await _capture("aid-flight")
			var color := Color("7ef0c1")
			if not await _wait_until(func(): return stage.marks.get(event.target, {}).get("color") == color, 1200):
				failure = "A real heal was missing its contact pulse"
				return false
			await _capture("aid-contact")
		aid_marks["heal"] = {"id": event.action_id, "target": event.target, "effective": event.effective}
		break
	return true


func _check_model_deployment(id: String, prefix: String) -> Node3D:
	var stage = app.board.stage
	if not await _wait_until(func(): return stage.actors.has(id), 9000):
		failure = "The contact deployment omitted the " + prefix + " model"
		return null
	var body := _deployment_body(id)
	if app.board._deployment_member(body) != id:
		failure = "The " + prefix + " model could not be picked by its body"
		return null
	var original: Vector2i = app.board.cell_index(stage.actors[id].row.pos)
	var free := original
	for cell in app.model.map.deploy_cells:
		var next: Vector2i = app.board.cell_index(cell)
		if next != original and app._deployment_target(id, next).is_empty():
			free = next
			break
	if free == original:
		failure = "No open cell could receive the " + prefix + " soldier"
		return null
	var version := int(app.client.frame.state_version)
	var model: Node3D = stage.actors[id].node
	await _drag(_board_pixel(body), _board_screen(free), prefix + "-deployment")
	if not await _wait_ready() or not _check_dropped(id, free, version + 1):
		return null
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(original), prefix + "-return-slot")
	if not await _wait_ready() or not _check_dropped(id, original, version + 2) or stage.actors[id].node != model:
		if failure.is_empty():
			failure = "Moving the " + prefix + " model recreated its instance"
		return null
	(melee_marks if prefix == "melee" else bow_marks)["deploy_swaps"] = 2
	return model


func _check_unit_marker_motion() -> void:
	var board = app.board
	var stage = board.stage
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The marker check needs a saved live battle"
		return
	if not await _wait_until(func(): return not stage._has_model_work(), 8000):
		failure = "The marker movement check still has models waiting to replace tokens"
		return
	await RenderingServer.frame_post_draw
	await _capture("marker-layout")
	if not await _command("step"):
		return
	await RenderingServer.frame_post_draw
	var draw_count: int = board.unit_marker_draws
	var label_draw_count: int = board.unit_label_draws
	var version: int = app.client.frame.state_version
	var origins := {}
	for id in board._unit_markers:
		if stage.actors.has(id):
			origins[id] = board._unit_markers[id].node.position
	var travel := 0.0
	for frame_index in range(6):
		await RenderingServer.frame_post_draw
		for id in origins:
			var origin: Vector2 = board._unit_markers[id].node.position
			if origin.distance_to(stage.foot_pixel(id)) > 0.02 or board._unit_markers[id].label.position != origin:
				failure = "A unit marker lagged behind the rendered model: " + id
				return
			travel = maxf(travel, origin.distance_to(origins[id]))
	if travel < 5.0 or board.unit_marker_draws != draw_count or board.unit_label_draws != label_draw_count:
		failure = "Travel %.2f, base redraws %d, label redraws %d" % [travel, board.unit_marker_draws - draw_count,
			board.unit_label_draws - label_draw_count]
		return
	await _capture("markers-in-motion")
	var target := "INIT-S01-A"
	if not await _press("battle-unit-" + target):
		return
	await RenderingServer.frame_post_draw
	if not board._unit_markers[target].appearance.focused or board.unit_marker_draws != draw_count + 1 \
			or board.unit_label_draws != label_draw_count or int(app.client.frame.state_version) != version:
		failure = "A focus change did not redraw just the selected marker"
		return
	side_checks["marker_motion"] = {"frame_samples": 6, "max_travel_px": travel, "movement_redraws": 0, "focus_redraws": 1,
		"label_movement_redraws": 0, "label_focus_redraws": 0}
	await _capture("marker-focused")


func _check_art_review() -> void:
	if app.view.get("phase") == "MISSING_SEARCH":
		await _check_search_chart()
		return
	if "--battle-report-read" in OS.get_cmdline_user_args():
		await _check_live_report_read()
		return
	if app.view.get("phase") == "EXPLORE" and app.view.get("region") == "RG07" \
			and app.view.get("site") in ["I", "S", "X"] \
			and not app.view.get("route", {}).get("contact_pending", false):
		await _check_wetland_map_review()
		return
	if app.view.get("phase") == "EXPLORE" and app.view.get("tutorial_area") and app.view.get("site") == "D":
		await _check_overlook_review()
		return
	var stage = app.board.stage
	if app.view.get("phase") == "TOWN":
		if not await _click_town_shortcut("muster") \
				or not await _wait_until(func(): return stage.scenery.has("departure-gate") and stage.actors.has("INIT-S01-A"), 8000):
			failure = "The town art review did not reach the playable yard"
			return
	else:
		var battle: Variant = app.view.get("battle_view")
		if battle is Dictionary and app.view.get("site") == "RESCUE":
			var target: Dictionary = app.view.rescue.target
			if target.is_empty() or target.member_ids.is_empty() or not app._battle_rescue.visible \
					or not app._battle_rescue.text.contains(target.batch_id) \
					or not app._battle_rescue.text.contains("待救回  " + "、".join(target.member_names)) \
					or app.view.actors.any(func(actor: Dictionary) -> bool: return actor.id in target.member_ids):
				failure = "The rescue field lost the captive group or put a missing person in combat"
				return
			side_checks["rescue_target"] = {"batch": target.batch_id, "members": target.member_ids, "deadline": target.deadline}
			await _check_land_field("transfer-yard", "town", 82, [])
			if failure.is_empty() and "--rescue-to-settlement" in OS.get_cmdline_user_args():
				await _rescue_battle("RESCUE_SUCCESS", target.member_ids, target.member_names, int(target.settles_on))
			return
		if battle is Dictionary and app.view.get("region") == "RG01" and not app.view.get("tutorial_return", false) \
				and app.view.get("site") in ["B2", "G"]:
			if app.view.site == "G":
				await _check_land_field("watchtower-gate", "gray_oak", 76, [Vector2i(4, 2), Vector2i(3, 3), Vector2i(3, 4)])
			else:
				await _check_land_field("north-gap", "gray_oak", 82, [])
			return
		if battle is Dictionary and battle.get("encounter") in ["RG07-N01", "RG07-N02", "RG07-N04", "RG01-N01", "RG01-N02"]:
			await _check_water_terrain_review(battle.encounter)
			return
		if not battle is Dictionary or battle.get("encounter") not in ["INTRO-EN01", "TUT01-ROOT", "BATTLE-MG01", "RG02-N01", "FX-RG02-N01", "RG02-E01"] \
				or not app.warning.visible:
			failure = "The art review requires an actual active battle warning"
			return
		if not await _wait_until(func(): return stage.battle_id == battle.id and stage.actors.size() >= 3, 8000):
			failure = "The normal battle view did not load the mapped actors"
			return
		if battle.encounter in ["INTRO-EN01", "TUT01-ROOT"]:
			var art := "approach" if battle.encounter == "INTRO-EN01" else "rootmouth"
			if app.board._field_art == null or app.board._field_art.resource_path != "res://assets/gray_oak/%s_ink_field.png" % art \
					or not ["battle-wall", "battle-fence", "battle-root"].all(func(id: String) -> bool: return stage.scenery.has(id)):
				failure = "The Gray Oak battle did not show its own painted background and three live scenery props"
				return
			side_checks["gray_oak_art"] = app.board._field_art.resource_path
		if battle.encounter in ["RG02-N01", "FX-RG02-N01"]:
			if not await _wait_until(func(): return not stage._has_model_work(), 8000):
				failure = "The fortress court still had pending models"
				return
			if not await _fortress_frame():
				return
		if battle.encounter == "RG02-E01":
			var mapped: Array = battle.actors.filter(func(row: Dictionary) -> bool:
				return row.pos is Array and (stage._supports_deployment(row.kind) if row.side == "player" else stage._supports_enemy(row.kind)))
			if not await _wait_until(func(): return mapped.all(func(row): return stage.actors.has(row.id)), 8000):
				failure = "The elite camp capture still had model placeholders for imported actors"
				return
			side_checks["trench_mapped_models"] = mapped.size()
			if not await _fortress_frame():
				return
	await _capture("review")
	side_checks["rendered_models"] = stage.actors.size()
	if "--lock-review" in OS.get_cmdline_user_args():
		await _check_warning_shape()
	if "--dual-sac-step" in OS.get_cmdline_user_args() and failure.is_empty():
		await _check_dual_sac()
	if "--ditch-step" in OS.get_cmdline_user_args() and failure.is_empty():
		if app.view.site != "L" or int(app.view.battle_view.tick) != 5:
			failure = "The trench sample needs the actual elite camp at beat five"
			return
		if not await _command("step"):
			return
		var releases: Array = app.view.battle_view.events.filter(func(event): return event.type == "release")
		var moves: Array = releases.map(func(event): return event.get("move", ""))
		if int(app.view.battle_view.tick) != 6 or "EN17-A" not in moves or "EN06-A" not in moves:
			failure = "The saved spear and shell warnings did not resolve at beat six"
			return
		side_checks["trench_releases"] = moves


func _check_dual_sac() -> void:
	var stage = app.board.stage
	var pawn = stage.actors.get("EL02-REG-1", {}).get("node")
	if app.view.site != "L" or int(app.view.battle_view.tick) != 5 or not is_instance_valid(pawn):
		failure = "The elite camp sample needs the dual-sac model at beat five"
		return
	for beat in range(6, 12):
		if not await _command("step"):
			return
		var battle: Dictionary = app.view.battle_view
		if int(battle.tick) != beat:
			failure = "The elite camp crossed an unexpected beat"
			return
		match beat:
			8:
				var casts: Array = battle.events.filter(func(event): return event.type == "windup" and event.get("move") == "EL02-A")
				var lane: Array = casts[0].cells.map(func(cell): return Vector2i(int(cell[0]), int(cell[1]))) if casts.size() == 1 else []
				side_checks["dual_sac_windup_pose"] = {"casts": casts, "pose": pawn.held_pose, "cast": pawn.cast_id,
					"yaw": pawn.rotation.y, "expected_yaw": stage._facing(5)}
				if lane != [Vector2i(2, 2), Vector2i(3, 1)] \
						or pawn.held_pose != "windup_turn" or pawn.cast_id != casts[0].action_id \
						or absf(angle_difference(pawn.rotation.y, stage._facing(5))) > 0.001:
					failure = "The second dual-sac windup did not face its announced two-cell line"
					return
				side_checks["dual_sac_windup"] = casts[0]
				await get_tree().create_timer(0.16).timeout
				await _capture("dual-sac-windup")
			9:
				var casts: Array = battle.events.filter(func(event): return event.type == "release" and event.get("move") == "EL02-A")
				if casts.size() != 1 or casts[0].cells != side_checks.dual_sac_windup.cells or int(casts[0].facing) != 5 \
						or casts[0].action_id != side_checks.dual_sac_windup.action_id \
						or pawn.held_pose != "rooted" or not pawn.releasing:
					failure = "The dual-sac release did not use the same lock or transition into the rooted pose"
					return
				side_checks["dual_sac_release"] = casts[0]
			10:
				if pawn.held_pose != "rooted":
					failure = "The elite left its rooted pose one beat early"
					return
				await _capture("dual-sac-rooted")
			11:
				if pawn.held_pose != "ready":
					failure = "The elite retained its rooted pose after the frozen effect expired"
					return
	side_checks["dual_sac_rooted_beats"] = [9, 10]


func _check_search_chart() -> void:
	var chart = app._search_chart
	var day: int = app.view.day
	var batch: String = app.view.rescue.active.id
	var state: int = chart.progress
	var pair := "--wetland-missing-pair" in OS.get_cmdline_user_args()
	var region := "苇灯湿地" if pair else "灰栎边道"
	var site := "干岛护岗" if pair else "浅湾双桥"
	var names := "弓兵 A、弓兵 B" if pair else "弓兵 A"
	if not app.area_title.text.ends_with(region) or not _panel_has("最后出现于 %s · %s" % [region, site]) or not _panel_has("待救回  " + names):
		failure = "The investigation did not display its originating expedition and missing roster"
		return
	if not chart.visible or chart._paper == null or chart.font_px != (23 if app.settings["大字"] else 19):
		failure = "The active investigation did not present its chart and configured type size"
		return
	await _capture("search-" + str(state))
	if "--search-map-click" not in OS.get_cmdline_user_args():
		return
	for index in range(state, 2):
		var invalid: Vector2 = chart.size * Vector2(chart.ANCHORS[1 - index])
		var version: int = app.client.frame.state_version
		_click_board(invalid)
		await get_tree().process_frame
		if app.client.busy or app.client.frame.state_version != version:
			failure = "An unavailable investigation clue accepted a click"
			return
		var box: Rect2 = chart._label_box(index)
		var point: Vector2 = Vector2(box.end.x - 3.0, box.get_center().y) if index == 0 else chart.size * Vector2(chart.ANCHORS[index])
		if not await _command("rescue investigate inspect " + str(chart.KEYS[index]), point):
			return
		if chart.progress != index + 1 or int(app.view.day) != day or app.view.rescue.active.id != batch:
			failure = "A clue was not attached to the original investigation on the same day"
			return
		await _capture("search-" + str(chart.progress))
	var before: int = app.client.frame.state_version
	_click_board(chart._label_box(1).get_center())
	await get_tree().process_frame
	if chart._inspect.visible or app.client.busy or app.client.frame.state_version != before:
		failure = "Completed clues remained actionable"
		return
	if pair and "--search-through-rescue" in OS.get_cmdline_user_args():
		if not await _command("rescue investigate return CONFIRM") or not await _command("town") or not await _ado_tab("rescue"):
			return
		if not _panel_has("最后出现于 苇灯湿地 · 干岛护岗") or not await _command("buy_supply 1") or not await _command("rescue " + batch + " CONFIRM"):
			if failure.is_empty():
				failure = "The rescue office did not retain the wetland encounter site"
			return
		var target: Dictionary = app.view.rescue.target
		if target.member_ids != ["INIT-S03-A", "INIT-S03-B"] or target.member_names != ["弓兵 A", "弓兵 B"] \
				or not app._battle_rescue.text.contains("待救回  " + names) or target.batch_id != batch or int(target.deadline) != 5:
			failure = "The two-person rescue lost its identities or original deadline"
			return
		await _capture("pair-battle")
		if await _rescue_battle("RESCUE_SUCCESS", target.member_ids, target.member_names, int(target.settles_on)):
			side_checks["rescued_pair"] = app.view.settlement.rescued_ids


func _check_wetland_map_review() -> void:
	var board = app.board
	var site: String = app.view.get("site", "")
	var counts := {"I": 1, "S": 5, "X": 10}
	var objects: Array = board.map_data.get("objects", [])
	if board._field_art == null or board._field_art.resource_path != "res://assets/wetland/route_ink_map.png" \
			or not board._has_route_art() or not board._route_input or objects.size() != counts.get(site):
		failure = "The wetland map art or site discovery did not match the saved route"
		return
	side_checks["wetland_map"] = {"visible_sites": objects.map(func(entry: Dictionary) -> String: return entry.id),
		"font_px": board.impact_font_size, "large_type": app.settings["大字"]}
	await _capture("wetland-map-" + site)
	if site == "I" or "--wetland-map-click" not in OS.get_cmdline_user_args():
		return
	var version: int = app.client.frame.state_version
	var distant := _route_anchor("I")
	if distant == Vector2.INF or not board._route_at(distant).is_empty():
		failure = "The distant south landing is clickable at the wrong route position"
		return
	_click_board(distant)
	await get_tree().process_frame
	if app.client.busy or app.client.frame.state_version != version:
		failure = "A click on a non-neighboring wetland site submitted a move"
		return
	var destination := "V" if site == "S" else "G"
	var matches: Array = objects.filter(func(row: Dictionary) -> bool: return row.id == destination)
	if matches.is_empty():
		failure = "The neighboring wetland site is absent from the map"
		return
	var entry: Dictionary = matches.front()
	var label: Rect2 = board._route_label_box(destination, _route_anchor(destination), board._route_label(entry))
	var point := Vector2(label.end.x - 4.0, label.get_center().y)
	if board._route_at(point) != destination or not await _command("move " + destination, point):
		failure = "The neighboring wetland site label did not submit a move"
		return
	if map_steps.is_empty() or map_steps.back() != destination or app.view.get("site") != destination:
		failure = "The wetland move bypassed the visible map label"
		return
	side_checks["wetland_map"]["clicked_label"] = destination
	await _capture("wetland-map-" + destination + "-after-click")


func _check_land_field(scene: String, directory: String, expected_ground: int, expected: Array) -> void:
	var board = app.board
	var path := "res://assets/%s/%s_ink.png" % [directory, scene.replace("-", "_")]
	if not await _wait_for_battle_models() or not await _wait_until(func(): return not board.stage._has_model_work(), 8000):
		failure = "The land encounter did not finish loading its actors"
		return
	var ground := 0
	var obstacles: Array[Vector2i] = []
	for row: Dictionary in board._layout_cells:
		var cell := Vector2i(int(row.q), int(row.r))
		if not board.coordinate_map.has(cell):
			failure = "A land encounter terrain cell has no board projection"
			return
		if row.terrain_id == "GROUND":
			ground += 1
		elif row.terrain_id == "HIGH_OBSTACLE":
			obstacles.append(cell)
	if board._field_art == null or board._field_art.resource_path != path or ground != expected_ground \
			or board._layout_cells.size() != ground + expected.size() or obstacles.size() != expected.size() \
			or not expected.all(func(cell: Vector2i) -> bool: return cell in obstacles):
		failure = "Land encounter art or terrain differs from the saved route"
		return
	side_checks["rescue_field" if scene == "transfer-yard" else "gray_oak_field"] = {"art": path, "ground": ground, "high_obstacles": obstacles.size(),
		"font_px": board.impact_font_size, "low_motion": app.settings["低动态"]}
	await _capture(scene)
	if "--gray-oak-steps" in OS.get_cmdline_user_args() or "--land-field-steps" in OS.get_cmdline_user_args():
		await _review_six_battle_steps(scene)
	elif "--board-pick" in OS.get_cmdline_user_args():
		await _check_warning_shape()


func _check_water_terrain_review(encounter: String) -> void:
	var board = app.board
	var scenes := {"RG07-N01": "dry-island", "RG07-N02": "tidal-yard", "RG07-N04": "north-levee",
		"RG01-N01": "shallow-bay", "RG01-N02": "shallow-bay"}
	var scene: String = scenes[encounter]
	var bridge_board := scene in ["shallow-bay", "tidal-yard"]
	var directory := "gray_oak" if scene == "shallow-bay" else "wetland"
	if not await _wait_for_battle_models() or not await _wait_until(func(): return not board.stage._has_model_work(), 8000):
		failure = "The water terrain encounter did not load its battle models"
		return
	if board._field_art == null or board._field_art.resource_path != "res://assets/%s/%s_ink.png" % [directory, scene.replace("-", "_")]:
		failure = "The water terrain encounter loaded the wrong painted background"
		return
	var terrain_cells: Dictionary = board._water_and_bridge_cells()
	var expected := {
		"SHALLOW_WATER": [Vector2i(1, 4), Vector2i(3, 4), Vector2i(5, 4)],
		"FIXED_BRIDGE": [Vector2i(1, 5), Vector2i(2, 5), Vector2i(4, 5), Vector2i(5, 5)],
	} if bridge_board else {
		"SHALLOW_WATER": [Vector2i(2, 3), Vector2i(5, 3), Vector2i(1, 4), Vector2i(4, 4), Vector2i(1, 5), Vector2i(4, 5)],
		"DEEP_WATER": [Vector2i(3, 3), Vector2i(4, 3), Vector2i(2, 4), Vector2i(3, 4)],
	}
	if terrain_cells.size() != expected.size():
		failure = "The battle displayed an unexpected water terrain category"
		return
	for terrain: String in expected:
		var actual: Dictionary = terrain_cells.get(terrain, {})
		if actual.size() != expected[terrain].size() or not expected[terrain].all(func(cell: Vector2i) -> bool:
				return actual.has(cell) and board.coordinate_map.has(cell)):
			failure = "The visible water or bridges did not match the frozen encounter terrain"
			return
	if bridge_board:
		var obstacles: Array = board._layout_cells.filter(func(row: Dictionary) -> bool:
			return row.get("terrain_id") == "HIGH_OBSTACLE").map(func(row: Dictionary) -> Vector2i:
			return Vector2i(int(row.q), int(row.r)))
		if obstacles.size() != 2 or Vector2i(0, 5) not in obstacles or Vector2i(3, 5) not in obstacles:
			failure = "The bridge board did not retain its two actual high obstacles"
			return
	var review_prefix := "water" if scene == "shallow-bay" else "wetland"
	side_checks[review_prefix + "_terrain"] = {"shallow": terrain_cells.SHALLOW_WATER.size(),
		"bridge": terrain_cells.FIXED_BRIDGE.size()} if bridge_board else {
		"shallow": terrain_cells.SHALLOW_WATER.size(), "deep": terrain_cells.DEEP_WATER.size()}
	side_checks[review_prefix + "_display"] = {"font_px": board.impact_font_size,
		"low_motion": app.settings["低动态"]}
	await _capture(scene)
	if ["--wetland-steps", "--water-terrain-steps"].any(func(key: String) -> bool: return key in OS.get_cmdline_user_args()):
		await _review_six_battle_steps(scene)


func _review_six_battle_steps(scene: String) -> void:
	var board = app.board
	var checked_warning := false
	for i in range(6):
		if not await _command("step"):
			return
		if not checked_warning and app.warning.visible and not board._danger_areas.is_empty():
			await _check_warning_shape()
			if not failure.is_empty():
				return
			checked_warning = true
	if not checked_warning:
		failure = "The six-beat sample did not reach a warning on " + scene
		return
	await _capture(scene + "-sixth-beat")


func _check_warning_shape() -> void:
	var board = app.board
	var traced := {}
	var action_cells := {}
	var source := ""
	for warning in board.danger.get("actions", []):
		if warning.side != "enemy":
			continue
		for pair in warning.get("locked_cells", []):
			var cell := Vector2i(int(pair[0]), int(pair[1]))
			if not board.coordinate_map.has(cell):
				continue
			if not action_cells.has(warning.action_id):
				action_cells[warning.action_id] = {"cells": {}, "source": warning.actor_id}
			action_cells[warning.action_id].cells[cell] = true
			if not traced.has(cell):
				traced[cell] = {"sources": {}, "roll_call": false}
			traced[cell].sources[warning.actor_id] = true
			traced[cell].roll_call = traced[cell].roll_call or warning.get("move_id") == "MG01-C"
			if source.is_empty():
				source = warning.actor_id
	if not board._sideways or board._show_deployment or traced.is_empty() or board._danger_cells != traced \
			or not app.location.text.contains("战斗第"):
		failure = "The warning marks did not represent the authority's locked cells"
		return
	var version := int(app.client.frame.state_version)
	var signature: String = app.client.frame.files["save.json"]
	if not await _press("battle-unit-" + source) or board.battle_focus_id != source \
			or board._danger_cells != traced or int(app.client.frame.state_version) != version \
			or app.client.frame.files["save.json"] != signature:
		failure = "Inspecting the threat did not preserve the paused save and locked cells"
		return
	var marks: Array = []
	var transform: Transform2D = board.get_viewport().get_final_transform() * board.get_global_transform_with_canvas()
	for cell: Vector2i in traced:
		var point: Vector2 = board.coordinate_map[cell]
		var at := transform * point
		marks.append({"cell": [cell.x, cell.y], "center": [at.x, at.y],
			"sources": traced[cell].sources.keys(), "focused": traced[cell].sources.has(source), "roll_call": traced[cell].roll_call})
	var contours: Array = []
	for area: Dictionary in board._danger_areas:
		if not action_cells.has(area.id) or action_cells[area.id] != {"source": area.source, "cells": area.cells}:
			failure = "A contour lost its action or included a cell the action did not lock"
			return
		action_cells.erase(area.id)
		var perimeter_edges := 0
		for cell: Vector2i in area.cells:
			perimeter_edges += 6
			for other: Vector2i in area.cells:
				var delta := cell - other
				if maxi(absi(delta.x), maxi(absi(delta.y), absi(delta.x + delta.y))) == 1:
					perimeter_edges -= 1
		var actual_edges := 0
		for path: PackedVector2Array in area.paths:
			actual_edges += path.size()
		if actual_edges != perimeter_edges:
			failure = "The contour retained internal seams or lost perimeter edges"
			return
		for cell: Vector2i in board.coordinate_map:
			var inside := false
			for path: PackedVector2Array in area.paths:
				if Geometry2D.is_point_in_polygon(board.coordinate_map[cell], path):
					inside = not inside
			if inside != area.cells.has(cell):
				failure = "The contour did not enclose exactly the locked cell centers"
				return
		contours.append({"source": area.source, "cells": area.cells.size(),
			"paths": area.paths.size(), "perimeter_edges": actual_edges})
	if not action_cells.is_empty():
		failure = "A live action had no contour"
		return
	var keys: Array = board._warning_key_layout()
	var numbered: Array = []
	if board._danger_areas.size() > 1:
		if keys.size() != board._danger_areas.size():
			failure = "A simultaneous range had no board key"
			return
		var warning_lines := Array(app.warning.text.split("\n"))
		for key: Dictionary in keys:
			var prefix := "[%d] " % key.number
			if not warning_lines.any(func(line: String) -> bool: return line.begins_with(prefix)) \
					or numbered.any(func(previous: Dictionary) -> bool: return previous.box.intersects(key.box)):
				failure = "A warning key overlapped or lost its footer row"
				return
			numbered.append({"number": key.number, "source": key.source, "focused": key.source == source, "box": key.box})
	elif not keys.is_empty() or app.warning.text.begins_with("[1]"):
		failure = "The single range was unnecessarily numbered"
		return
	side_checks["warning_marks"] = {"source": source, "marks": marks, "side_view": board._sideways,
		"contours": contours, "keys": numbered.map(func(key: Dictionary) -> Dictionary:
			return {"number": key.number, "source": key.source, "focused": key.focused}), "deployment_grid": board._show_deployment,
		"version": version, "window": [get_window().size.x, get_window().size.y]}
	await _capture("warning-focus")
	var scroll_needed: bool = app.warning_footer.get_v_scroll_bar().visible
	side_checks.warning_marks["warning_needs_scroll"] = scroll_needed
	if app.warning.text.count("\n") <= 1 and scroll_needed:
		failure = "The warning ribbon did not show both alert lines at once"
		return
	var alternatives := numbered.filter(func(key: Dictionary) -> bool: return not key.focused)
	if not alternatives.is_empty():
		var alternate: String = alternatives[0].source
		if not await _press("battle-unit-" + alternate) or board.battle_focus_id != alternate \
				or int(app.client.frame.state_version) != version or app.client.frame.files["save.json"] != signature:
			failure = "Changing warning selection wrote to the save"
			return
		side_checks.warning_marks["alternate_focus"] = alternate
		await _capture("warning-secondary")
	if "--board-pick" in OS.get_cmdline_user_args():
		await _check_board_annotation_clicks(keys, version, signature)


func _check_board_annotation_clicks(keys: Array, version: int, signature: String) -> void:
	var board = app.board
	if not await _wait_until(func() -> bool:
			return board.stage.actors.values().all(func(token: Dictionary) -> bool:
				return token.node.motion == null or not token.node.motion.is_running()), 4000):
		failure = "The paused battle still has moving units during label inspection"
		return
	await RenderingServer.frame_post_draw
	var probes: Array[Dictionary] = []
	for actor: Dictionary in app.view.actors:
		if actor.side != "player" or not board._unit_markers.has(actor.id):
			continue
		var marker: Dictionary = board._unit_markers[actor.id]
		var box: Rect2 = marker.label_box
		var point: Vector2 = marker.label.position + Vector2(box.end.x - 2.0, box.get_center().y)
		if box.has_area() and board._battle_annotation_at(point) == actor.id:
			probes.append({"id": actor.id, "point": point, "type": "badge"})
			break
	if probes.is_empty():
		failure = "The badge sample has no exposed allied label"
		return
	for key: Dictionary in keys:
		probes.append({"id": key.source, "point": key.box.get_center(), "type": "warning", "number": key.number,
			"action_id": key.id})
	var ids: Array = []
	for probe: Dictionary in probes:
		if probe.has("action_id"):
			for drawn: Dictionary in board._drawn_warning_keys:
				if drawn.id == probe.action_id:
					probe.point = drawn.box.get_center()
					break
		_mouse_motion(_board_pixel(probe.point), Vector2.ZERO, false)
		await get_tree().process_frame
		var hovered: bool = board.mouse_default_cursor_shape == Control.CURSOR_POINTING_HAND
		_click_board(probe.point)
		await get_tree().process_frame
		var row: Button = app.command_buttons["battle-unit-" + str(probe.id)]
		if board.battle_focus_id != probe.id or not row.button_pressed or not row.has_focus() or not hovered:
			failure = "Picking %s %s at %s produced %s, pressed=%s focused=%s hand=%s" % [
				probe.type, probe.id, probe.point, board.battle_focus_id, row.button_pressed, row.has_focus(), hovered]
			return
		ids.append({"type": probe.type, "id": probe.id, "number": probe.get("number")})
		if probe.get("number") == 2 or probe.type == "badge":
			await _capture("click-" + probe.type)
	var selected: String = board.battle_focus_id
	_mouse(_board_pixel(probes.back().point), true)
	_mouse(_board_pixel(probes.front().point if probes.size() > 1 else Vector2(5, 5)), false)
	await get_tree().process_frame
	if board.battle_focus_id != selected or app.client.frame.state_version != version or app.client.frame.files["save.json"] != signature:
		failure = "Inspecting the field changed focus after a mismatched release or wrote to the save"
		return
	side_checks["board_clicks"] = {"targets": ids, "version": version, "mismatched_release_ignored": true}


func _check_overlook_review() -> void:
	var stage = app.board.stage
	if app.view.get("observation") != null \
			or not await _wait_until(func(): return stage.scenery.has("D"), 8000):
		failure = "The overlook did not open at the unrecorded landmark"
		return
	var board = app.board
	var artwork: Rect2 = board._overlook_bounds()
	var art_path := "res://assets/gray_oak/overlook_cleared.png" if board._root_cleared() \
		else "res://assets/gray_oak/overlook_brushes.png"
	if board._overlook_art == null or board._overlook_art.resource_path != art_path:
		failure = "The overlook picture did not match Rootmouth's actual cleared state"
		return
	if board._field_art == null or board._field_art.resource_path != "res://assets/gray_oak/route_ink_map.png":
		failure = "The Gray Oak route map did not use its woodland backdrop"
		return
	for entry: Dictionary in board.map_data.get("objects", []):
		if board._point(entry.position).x < artwork.end.x + 20.0:
			failure = "A route pin overlaps the overlook view"
			return
	var before := int(app.client.frame.state_version)
	side_checks["root_cleared_at_overlook"] = board._root_cleared()
	side_checks["overlook_art"] = art_path
	await _capture("overlook-before")
	_click_board(artwork.get_center())
	await get_tree().process_frame
	var caption := "根口已清理" if board._root_cleared() else "旧路上有两团枝影"
	if not app._overlook_mat.visible or app._overlook_picture.texture != board._overlook_art \
			or app._overlook_picture.size.y <= artwork.size.y or not _panel_has(caption) \
			or app.command_buttons.has("move C") or app.client.busy or int(app.client.frame.state_version) != before:
		failure = "Opening the larger overlook changed the route, lost its illustration, or supplied the wrong description"
		return
	await _capture("overlook-inspect")
	_key(KEY_ESCAPE, true)
	_key(KEY_ESCAPE, false)
	if not await _wait_focus("overlook-inspect") or app._overlook_mat.visible or not await _press("overlook-inspect"):
		failure = "The enlarged overlook could not be closed with Escape and reopened from the route list"
		return
	var record_here := "--record-from-overlook" in OS.get_cmdline_user_args()
	if not record_here and not await _press("overlook-back"):
		return
	if int(app.client.frame.state_version) != before or not await _command("tutorial observe"):
		return
	if record_here:
		if not app._overlook_mat.visible or not _panel_has(app.view.observation.observed) or app.command_buttons.has("tutorial observe"):
			failure = "A recorded close inspection was lost or could be submitted twice"
			return
		await _capture("overlook-inspect-recorded")
		if not await _press("overlook-back"):
			return
	else:
		if not await _press("overlook-inspect") or not _panel_has(app.view.observation.observed) or not await _press("overlook-back"):
			failure = "The map observation did not reach the large inspection"
			return
	if int(app.client.frame.state_version) != before + 1 or app._overlook_picture.texture != null:
		failure = "Leaving the inspection wrote another action or retained the enlarged picture"
		return
	side_checks["recorded_in_enlarged_view"] = record_here
	var entries: Array = app.board.map_data.get("objects", [])
	var overlook: Array = entries.filter(func(entry): return entry.id == "D")
	if overlook.size() != 1 or app.board._route_label(overlook[0]) != "远眺 · 已记录":
		failure = "The map label did not reflect the committed observation"
		return
	var next_step := "本趟还缺根口战胜利" if not board._root_cleared() else "两战和远眺记录已齐"
	if not _panel_has(next_step) or not _panel_has("请许苇"):
		failure = "The overlook did not say whether the party could deliver its investigation"
		return
	side_checks["overlook_next_step"] = next_step
	await _capture("overlook-recorded")
	var stops: Array = entries.filter(func(entry): return entry.id == "C")
	if stops.size() != 1:
		failure = "The already discovered rest stop was missing"
		return
	var entry: Dictionary = stops[0]
	var anchor: Vector2 = app.board._point(entry.position)
	var bounds: Rect2 = app.board._route_label_box(entry.id, anchor, app.board._route_label(entry))
	var point := Vector2(bounds.end.x - 1, bounds.get_center().y)
	var distance := point.distance_to(anchor)
	if distance <= 20.0 or app.board._route_at(point) != "C":
		failure = "The route caption did not extend the normal pin target"
		return
	var version: int = app.client.frame.state_version
	_click_board(point)
	await get_tree().process_frame
	if not await _wait_ready() or int(app.client.frame.state_version) != version + 1 or app.view.site != "C" \
			or board._overlook_width != 0.0:
		failure = "Clicking the route caption did not commit one allowed movement"
		return
	steps.append({"command": "move C", "version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["route_caption_click_px_from_pin"] = distance


func _check_live_dialogue() -> void:
	var active: Variant = app.model.get("active")
	var battle: bool = app.view.get("phase") == "BATTLE"
	var expected_id := "first_telegraph" if battle else "trip-1-return"
	if not active is Dictionary or active.id != expected_id or int(active.cursor) != 0 \
			or not app.dialogue_next.is_visible_in_tree() or not app.dialogue_skip.is_visible_in_tree() \
			or not app.subtitles.text.begins_with("1/%d" % int(active.line_count)):
		failure = "The saved dialogue is not usable from its original scene"
		return
	if not battle and (not app.area_title.text.ends_with("暮汀") or not app.board._town_yard \
			or app.board._town_landmarks.is_empty() or app.board.reserve_zone.visible):
		failure = "The returned scene did not show the town without deployment"
		return
	var start_tick: int = app.view.battle_view.tick if battle else -1
	await _capture("dialogue-first")
	if not await _command("dialogue next"):
		return
	if int(app.model.active.cursor) != 1 or not app.subtitles.text.contains(app.model.active.line.text) \
			or not app.notice.text.is_empty():
		failure = "The next line or its receipt did not render correctly"
		return
	await _capture("dialogue-next")
	if battle:
		if not await _command("dialogue next") or app.dialogue_next.text != "完成阅读" \
				or not await _command("dialogue next"):
			failure = "The battlefield dialogue could not be finished"
			return
		side_checks["dialogue_start_tick"] = start_tick
		if int(app.view.battle_view.tick) != start_tick or app._playback_running:
			failure = "Reading advanced the paused battle"
			return
	elif not await _command("dialogue skip"):
		return
	var expected_status := "READ" if battle else "SKIPPED"
	var history: Array = app.model.get("history", [])
	if app.model.get("active") != null or app.dialogue_next.visible or app.dialogue_skip.visible \
			or not app.subtitles.text.is_empty() or history.back().status != expected_status:
		failure = "Dialogue did not close with the expected record"
		return
	side_checks["dialogue_status"] = expected_status
	if not battle:
		if not await _command("town") or app.view.get("phase") != "TOWN":
			failure = "Skipping dialogue prevented returning to town"
		return
	var version: int = app.client.frame.state_version
	_key(KEY_SPACE, true)
	_key(KEY_SPACE, false)
	if not await _wait_until(func() -> bool: return int(app.client.frame.state_version) > version, 3500):
		failure = "Automatic battle did not resume after reading"
		return
	_key(KEY_SPACE, true)
	_key(KEY_SPACE, false)
	await get_tree().process_frame
	if not await _wait_ready() or int(app.client.frame.state_version) != version + 1 \
			or int(app.view.battle_view.tick) != start_tick + 1 or app._playback_running:
		failure = "Resuming after dialogue did not produce one expected battle beat"
		return
	steps.append({"command": "step", "version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["dialogue_resumed_tick"] = app.view.battle_view.tick


func _check_tutorial_resume() -> void:
	if app.view.get("phase") == "TOWN":
		if app.view.rescue.get("due", []).is_empty():
			await _check_early_recovery()
		else:
			await _check_tutorial_deadline()
		return
	var from_entrance: bool = app.view.get("site") == "I" and int(app.view.supply) == 0
	var detail := "本趟还缺林道战胜利、根口战胜利、远眺点（D）观察" if from_entrance else "本趟还缺远眺点（D）观察"
	var return_for_observation := "--return-for-observation" in OS.get_cmdline_user_args()
	if return_for_observation:
		var backtrack: Button = app.command_buttons.get("move G")
		if backtrack == null or backtrack.disabled or backtrack.text != "经根口返回远眺点":
			failure = "The exit did not offer the way back to the missed observation"
			return
	if not app.view.get("tutorial_area") or not await _press("return CONFIRM", false) or not _panel_has(detail):
		failure = "The return confirmation omitted an actual scouting requirement"
		return
	if return_for_observation:
		var before: Dictionary = app.client.frame
		if not _panel_has("可取消归城并经根口返回远眺点") or not await _press("cancel") \
				or app.client.frame != before:
			failure = "The early return could not be cancelled without a transaction"
			return
		if not await _commands(["move G", "move D", "tutorial observe", "move G", "move X"]):
			return
		var backtrack: Button = app.command_buttons.get("move G")
		if backtrack == null or backtrack.text == "经根口返回远眺点" or not app.view.scouting.ready:
			failure = "The exit did not recognize the corrected investigation"
			return
		if not await _command("return CONFIRM"):
			return
		_check_settlement("SAFE_RETURN", true)
		if not app.view.scouting.delivered_here or not _panel_has("可在暮汀旧档案请许苇核对远眺记录"):
			failure = "The completed investigation did not link to the saved settlement"
		return
	await _capture("scouting-return-confirm")
	var version: int = app.client.frame.state_version
	if not await _press("confirm") or app.view.get("phase") != "RETURNED" or app.view.get("complete") \
			or int(app.client.frame.state_version) != version + 1 or not _panel_has(detail):
		failure = "An incomplete safe return was presented as a delivered investigation"
		return
	steps.append({"command": "return CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
	await _capture("scouting-incomplete")
	if not from_entrance:
		side_checks["scouting"] = app.view.scouting
		return
	if not await _command("town"):
		return
	var original_copper: int = app.view.town_roster.copper
	var cost: int = app.view.preparation.supply_price
	if not app.command_buttons["tutorial start"].disabled or not app.board._town_buttons["departure-gate"].disabled:
		failure = "The zero-supply departure was enabled"
		return
	await _capture("scouting-buy-supply")
	if not await _command("buy_supply 1") or int(app.view.supply) != 1 \
			or int(app.view.town_roster.copper) != original_copper - cost:
		failure = "The purchase did not apply the pre-archive supply quote"
		return
	if not await _confirm_tutorial_gate("tutorial start") or int(app.view.supply) != 0 or int(app.view.scouting.battles) != 0:
		failure = "The renewed scouting departure did not consume one supply and start a new investigation"
		return
	side_checks["tutorial_supply_price"] = cost


func _check_early_recovery() -> void:
	var victim := "INIT-S03-A"
	var day: int = app.view.day
	var supply: int = app.view.supply
	var departure := "tutorial start"
	var recommend := "tutorial recommend CONFIRM"
	var member: Dictionary = app.view.party.filter(func(row: Dictionary) -> bool: return row.instance_id == victim).front()
	if app.view.get("complete", false) or not app.view.rescue.is_empty() or int(member.injury_days) != 2 \
			or not app.command_buttons[departure].disabled or not app.command_buttons[recommend].disabled \
			or not app.command_buttons["member-" + victim].text.contains("旧伤 2 日") \
			or not await _press("member-" + victim):
		failure = "The early wounded roster did not explain the blocked departure"
		return
	var version: int = app.client.frame.state_version
	if not await _press("heal " + victim, false) or not _panel_has("旧伤仍需结算休整") \
			or not await _press("cancel") or int(app.client.frame.state_version) != version:
		failure = "The early treatment quote did not preserve the injury and save"
		return
	if not await _command("care " + victim) or app.view.preparation.care_scheduled != victim or int(app.view.supply) != supply - 1:
		failure = "The early care action did not reserve one supply"
		return
	if not await _press("rest CONFIRM", false) or not _panel_has("推进至第 %d 日" % (day + 1)):
		failure = "The rest confirmation omitted the next day"
		return
	await _capture("early-rest-confirm")
	version = app.client.frame.state_version
	if not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
		failure = "The rest confirmation did not commit exactly once"
		return
	steps.append({"command": "rest CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
	member = app.view.party.filter(func(row: Dictionary) -> bool: return row.instance_id == victim).front()
	if int(app.view.day) != day + 1 or int(app.view.supply) != supply - 1 or member.injury_days != 0 \
			or member.hp != member.max_hp or app.view.preparation.care_scheduled != null \
			or app.command_buttons[recommend].disabled:
		failure = "Town rest did not settle the scheduled wound care"
		return
	await _capture("early-rest-recovered")
	if not await _command(recommend) or not await _confirm_tutorial_gate(departure):
		failure = "The recovered roster could not depart again"
		return
	side_checks["early_recovery"] = {"member": victim, "day": day + 1, "hp": member.hp, "supply": app.view.supply}


func _check_tutorial_deadline() -> void:
	var due: Array = app.view.rescue.get("due", [])
	if due.is_empty() or not await _confirm_tutorial_gate("tutorial start CONFIRM", "盾兵 A"):
		failure = "The tutorial gate could not confirm the visible rescue deadline"
		return
	side_checks["tutorial_departure_deadline"] = due


func _check_rescue_expiry() -> void:
	if app.view.phase == "TOWN":
		await _check_tutorial_deadline()
		if not failure.is_empty():
			return
	var day: int = app.view.day
	var due: Array = app.view.rescue.due
	var battle: bool = app.view.phase == "BATTLE"
	var command := "flee CONFIRM" if battle else "return CONFIRM"
	var result := "COMBAT_RETREAT" if battle else "SAFE_RETURN"
	var expected_detail := "一拍追击" if battle else "本趟还缺林道战胜利"
	var version: int = app.client.frame.state_version
	if due.size() != 8 or not await _press(command, false) or not _panel_has(expected_detail) \
			or not _panel_has("第 %d 日结算时，救援将超期" % (day + 1)) \
			or not _panel_has("盾兵 A") or not _panel_has("弓兵 B") or _panel_has("INIT-S01-A"):
		failure = "The confirmation did not show the rescue deadline with readable names"
		return
	await _capture("expiry-confirmation")
	if not battle and (not await _press("cancel") or int(app.client.frame.state_version) != version):
		failure = "Cancelling return did not preserve the original save"
		return
	if battle:
		if not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
			failure = "The confirmed retreat did not commit exactly once"
			return
		steps.append({"command": command, "version": version + 1, "digest": app.client.frame.state_digest})
	elif not await _command(command):
		return
	var expired: Array = app.view.get("settlement", {}).get("expired_rescue_names", [])
	if int(app.view.day) != day + 1 or app.view.settlement.result != result \
			or expired.size() != due.size() or not _panel_has("本次结算救援超期") \
			or not _panel_has("弓兵 B") or not app.view.rescue.due.is_empty():
		failure = "The settlement omitted the actual expired rescue targets"
		return
	side_checks["rescue_expiry"] = {"day": day + 1, "names": expired, "result": result}
	await _capture("expiry-settlement")


func _confirm_tutorial_gate(command: String, expiring_member := "") -> bool:
	var version: int = app.client.frame.state_version
	var supply: int = app.view.supply
	if not await _click_town_shortcut("departure-gate") or app.confirmation.get("command") != "tutorial":
		return false
	if not expiring_member.is_empty() and not _panel_has(expiring_member):
		return false
	if not expiring_member.is_empty():
		await _capture("scouting-rescue-deadline")
	if not await _press("confirm") or int(app.client.frame.state_version) != version + 1 \
			or app.view.get("phase") != "EXPLORE" or int(app.view.supply) != supply - 1:
		return false
	steps.append({"command": command, "version": version + 1, "digest": app.client.frame.state_digest})
	return true


func _click_town_shortcut(id: String) -> bool:
	var button: Button = app.board._town_buttons.get(id)
	if button == null or not button.visible or button.disabled:
		failure = "Unavailable town shortcut: " + id
		return false
	var point := _board_pixel(button.position + button.size / 2.0)
	_mouse(point, true)
	_mouse(point, false)
	await get_tree().process_frame
	return true


func _check_town_shortcuts() -> void:
	if app.view.get("phase") != "TOWN" or not app.view.get("chapter", {}).get("archived", false):
		failure = "Town shortcuts require the archived chapter"
		return
	var version: int = app.client.frame.state_version
	var supply: int = app.view.supply
	await _capture("town-entries")
	if not await _click_town_shortcut("muster") or app.town_tab != "roster" or not app.board.deployment_open:
		failure = "The muster shortcut did not open the player's deployment"
		return
	if not await _click_town_shortcut("store") or app.town_tab != "expedition":
		failure = "The store shortcut did not open the supply and expedition panel"
		return
	await _capture("town-departure-entry")
	if not await _click_town_shortcut("departure-gate") or app.confirmation.get("command") != "depart" \
			or not _panel_has("消耗 %d 份仓库补给" % int(app.view.departure_cost)):
		failure = "The departure shortcut did not open the existing supply confirmation"
		return
	if app.board._town_buttons.values().any(func(button: Button): return button.visible):
		failure = "A town shortcut remained active while the confirmation was open"
		return
	await _capture("town-departure-confirm")
	if not await _press("cancel") or int(app.view.supply) != supply or int(app.client.frame.state_version) != version:
		failure = "Cancel at the town gate changed supply or the save"
		return
	var cost: int = app.view.departure_cost
	if not await _click_town_shortcut("departure-gate") or not await _press("confirm"):
		return
	if app.view.get("phase") != "EXPLORE" or int(app.view.supply) != supply - cost \
			or int(app.client.frame.state_version) != version + 1 \
			or app.board._town_buttons.values().any(func(button: Button): return button.visible):
		failure = "Departure did not commit exactly one existing rule command and clear the town shortcuts"
		return
	steps.append({"command": "depart CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["town_shortcuts"] = {"supply_before": supply, "supply_after": app.view.supply, "scene": app.view.region}


func _check_town_yard() -> void:
	var stage = app.board.stage
	var landmarks := ["muster", "store", "departure-gate"]
	if app.view.get("phase") != "TOWN" or not app.view.get("complete") \
			or not await _wait_until(func(): return landmarks.all(func(id): return stage.scenery.has(id)), 9000):
		failure = "The town-yard check needs the archived chapter in Mouting"
		return
	var art: Texture2D = app.board._field_art
	if art == null or art.resource_path != "res://assets/town/muster_yard_ink.png":
		failure = "The yard did not use its own painted backdrop"
		return
	await RenderingServer.frame_post_draw
	if not landmarks.all(_visible_landmark) or not app.board._unit_markers.is_empty() \
			or app.board.reserve_zone.visible or app.board.deployment_open:
		failure = "The archive scene omitted a yard prop or showed deployment controls"
		return
	await _capture("town-archive")
	var version: int = app.client.frame.state_version
	var actor := "INIT-S01-A"
	if not await _press("town-roster") or not stage.actors.has(actor) or not app.board.deployment_open:
		failure = "The same yard did not show the deployed roster"
		return
	var destination := Vector2i(-1, -1)
	for point in app.view.town_deploy_cells:
		var cell := Vector2i(int(point[0]), int(point[1]))
		if app._deployment_target(actor, cell).is_empty():
			destination = cell
			break
	if destination == Vector2i(-1, -1):
		failure = "No open town slot for the mouse drag"
		return
	var facing: int = stage.actors[actor].row.facing
	await _drag(_board_pixel(_deployment_body(actor)), _board_screen(destination), "town-drop")
	if not await _wait_ready() or not side_checks["town-drop"].allowed \
			or not _check_dropped(actor, destination, version + 1):
		failure = "The model drag did not commit a legal town deployment"
		return
	steps.append({"command": "place %s %d %d %d" % [actor, destination.x, destination.y, facing],
		"version": version + 1, "digest": app.client.frame.state_digest})
	await _capture("town-roster")
	if not await _press("town-chapter") or not stage.actors.is_empty() \
			or not app.board._unit_markers.is_empty() or int(app.client.frame.state_version) != version + 1:
		failure = "Returning to the archive left visible mock units or changed the save"
		return
	side_checks["town_yard"] = {"props": landmarks, "hidden_in_archive": true, "drag_commits": 1}


func _check_original_slot_drop() -> void:
	var id := "INIT-S01-A"
	var stage = app.board.stage
	if not app._can_edit_deployment() or not await _wait_until(func(): return stage.actors.has(id), 9000):
		failure = "The original-slot check needs the saved contact deployment"
		return
	var model: Node3D = stage.actors[id].node
	var row: Dictionary = stage.actors[id].row
	var slot := Vector2i(int(row.pos[0]), int(row.pos[1]))
	var version: int = app.client.frame.state_version
	var digest: String = app.client.frame.state_digest
	var files: Dictionary = app.client.frame.files.duplicate()
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(slot), "original-slot")
	if not await _wait_ready() or not side_checks["original-slot"].allowed \
			or int(app.client.frame.state_version) != version or app.client.frame.state_digest != digest \
			or app.client.frame.files != files or stage.actors[id].node != model:
		failure = "Dropping a model on its unchanged original slot wrote or recreated it"
		return
	side_checks["original_slot_preserved"] = true
	if not await _press("member-" + id) or not await _press("deployment-cells") \
			or not await _press_cell("cell-%d-%d" % [slot.x, slot.y]) or not await _press("facing"):
		return
	var facing: int = (int(row.facing) + 1) % 6
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(slot), "rotated-slot")
	if not await _wait_ready() or not _check_dropped(id, slot, version + 1) \
			or int(stage.actors[id].row.facing) != facing or stage.actors[id].node != model:
		failure = "Dropping on the original slot after an explicit rotation did not commit the new facing"
		return
	steps.append({"command": "place %s %d %d %d" % [id, slot.x, slot.y, facing],
		"version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["rotated_facing"] = facing


func _check_deployment_interrupts() -> void:
	var board = app.board
	var stage = board.stage
	var window := get_window()
	var id := "INIT-S01-A"
	if not mouse or DisplayServer.get_name() == "headless" or not window.has_focus() \
			or not app._can_edit_deployment() or not await _wait_until(func(): return stage.actors.has(id), 9000):
		failure = "The deployment check needs the focused Windows contact board"
		return
	var origin: Vector2i = board.cell_index(stage.actors[id].row.pos)
	var legal: Array = app.model.map.deploy_cells.map(func(cell): return board.cell_index(cell)).filter(
		func(cell): return cell != origin and app._deployment_target(id, cell).is_empty())
	if legal.size() < 2:
		failure = "The contact did not have two empty slots for the check"
		return
	var target: Vector2i = legal[0]
	var saved: Dictionary = app.client.frame.files.duplicate()
	var version: int = app.client.frame.state_version
	var selected: String = app.selected_id
	var selection_cell: Vector2i = app.selected_cell
	var cases := ["escape", "settings", "minimize"]
	for interruption in cases:
		var from := _board_pixel(_deployment_body(id))
		var destination := _board_screen(target)
		if interruption == "minimize":
			var row: Button = app.command_buttons["member-" + id]
			app._action_scroll.ensure_control_visible(row)
			await get_tree().process_frame
			from = _button_point(row)
			destination = _button_point(board.reserve_zone)
		await _hold_drag(from, destination)
		if not window.gui_is_dragging() or window.gui_get_drag_data().get("deploy_member") != id:
			failure = "No active mouse drag for " + interruption
			return
		match interruption:
			"escape":
				_key(KEY_ESCAPE, true)
				_key(KEY_ESCAPE, false)
			"settings":
				app._show_settings()
				if window.gui_is_dragging() or not app.settings_open:
					failure = "Opening Settings retained a pending deployment drag"
					return
				_key(KEY_ESCAPE, true)
				_key(KEY_ESCAPE, false)
			"minimize":
				window.mode = Window.MODE_MINIMIZED
				if not await _wait_until(func(): return app._window_minimized() and stage.window_hidden, 3000) \
						or window.gui_is_dragging():
					failure = "The actual minimized window retained a pending deployment drag"
					return
				window.mode = Window.MODE_WINDOWED
				window.grab_focus()
				if not await _wait_until(func(): return window.has_focus() and not stage.window_hidden, 3000):
					failure = "Could not restore contact for the stale button release"
					return
		_mouse(destination, false)
		await get_tree().process_frame
		if window.gui_is_dragging() or window.gui_is_drag_successful() or board._drag_label != null \
				or board._drop_allowed or app.client.busy or app.settings_open or not board.deployment_open \
				or int(app.client.frame.state_version) != version or app.client.frame.files != saved \
				or app.selected_id != selected or app.selected_cell != selection_cell:
			failure = "An interrupted drag committed, selected a stale cell, or left a preview after " + interruption
			return
		side_checks[interruption] = {"version": version, "drop_rejected": true}

	var destination := _board_screen(target)
	await _hold_drag(_board_pixel(_deployment_body(id)), destination)
	var intervening: Vector2i = legal[1]
	var facing: int = stage.actors[id].row.facing
	var place := "place %s %d %d %d"
	if not window.gui_is_dragging() or not app.client.submit("place", [id, str(intervening.x), str(intervening.y), str(facing)]) \
			or window.gui_is_dragging() or not await _wait_ready():
		failure = "Submitting another placement did not immediately cancel the held drag"
		return
	_mouse(destination, false)
	await get_tree().process_frame
	if app.client.busy or not _check_dropped(id, intervening, version + 1):
		failure = "The old release interfered with the saved placement"
		return
	steps.append({"command": place % [id, intervening.x, intervening.y, facing],
		"version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["save_in_flight"] = {"only_intervening_placement": true, "version": version + 1}
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(target), "fresh-drop")
	if not await _wait_ready() or not _check_dropped(id, target, version + 2):
		return
	steps.append({"command": place % [id, target.x, target.y, facing],
		"version": version + 2, "digest": app.client.frame.state_digest})
	await _drag(_board_pixel(_deployment_body(id)), _button_point(board.reserve_zone), "fresh-reserve")
	if not await _wait_ready() or int(app.client.frame.state_version) != version + 3 \
			or stage.actors.has(id) or not app.view.party.any(func(member): return member.instance_id == id and not member.deployed):
		failure = "A fresh drag to reserve did not withdraw the same actor once"
		return
	steps.append({"command": "deploy " + id + " off", "version": version + 3, "digest": app.client.frame.state_digest})
	side_checks["fresh_reserve"] = {"version": version + 3, "withdrawn": true}


func _check_combat_feedback() -> bool:
	var battle: Dictionary = app.view.battle_view
	var events: Dictionary = battle.impacts
	var health := {}
	for actor in battle.actors:
		if int(actor.max_hp) <= 0 or int(actor.hp) < 0 or int(actor.hp) > int(actor.max_hp):
			failure = "The life gauge could not be drawn from the saved HP values"
			return false
		health[actor.id] = [int(actor.hp), int(actor.max_hp)]
	feedback_frames[str(int(battle.tick))] = {"impacts": events, "health": health}
	if app._live_impacts != events or app.board.impacts != events:
		failure = "The feedback layer did not follow the latest saved tick"
		return false
	if not app.view.battle_memory.is_empty():
		return true
	for id in events:
		var detail: Dictionary = events[id]
		for kind in ["damage", "absorbed", "healed", "down"]:
			if detail.get(kind, 0) and not feedback_marks.has(kind):
				feedback_marks[kind] = int(battle.tick)
				await _capture("feedback-" + kind)
		if int(detail.get("healed", 0)) > 0 and app.view.phase == "BATTLE" and not feedback_marks.has("settings"):
			if not await _check_feedback_settings(id, detail, events):
				return false
	return true


func _check_feedback_settings(id: String, detail: Dictionary, events: Dictionary) -> bool:
	var version: int = app.client.frame.state_version
	if not await _press("battle-unit-" + id):
		return false
	if app.board.battle_focus_id != id or "回复 %d" % int(detail.healed) not in app._battle_detail.text:
		failure = "The selected unit did not present its effective healing"
		return false
	for key in ["settings", "战斗数字", "低动态", "settings-back"]:
		if not await _press(key):
			return false
	if not app.board.impacts.is_empty() or not app.settings["低动态"] or app.client.frame.state_version != version:
		failure = "Hiding combat numbers or enabling reduced motion affected the rule state"
		return false
	await _capture("feedback-hidden")
	for key in ["settings", "战斗数字", "settings-back"]:
		if not await _press(key):
			return false
	if app.board.impacts != events or app.client.frame.state_version != version:
		failure = "Reduced motion lost the saved combat feedback"
		return false
	await _capture("feedback-reduced")
	feedback_marks["settings"] = true
	return true


func _check_feedback_resume() -> void:
	var battle: Dictionary = app.view.get("battle_view", {})
	var events: Dictionary = battle.get("impacts", {})
	if app.view.get("phase") != "BATTLE" or events.is_empty() or not app.board.impacts.is_empty() or app._playback_running:
		failure = "Reopening a battle replayed old impact feedback or resumed unprompted"
		return
	var id: String = events.keys()[0]
	var version: int = app.client.frame.state_version
	if not await _press("battle-unit-" + id):
		return
	var actor: Dictionary = app._combatants[id]
	var hp := "生命 %d/%d" % [int(actor.hp), int(actor.max_hp)]
	if hp not in app.command_buttons["battle-unit-" + id].text or app.client.frame.state_version != version:
		failure = "Reopening did not preserve the selected unit's saved life"
		return
	feedback_marks["resumed_tick"] = int(battle.tick)
	await _capture("feedback-resumed")


func _check_gap_resume() -> void:
	if app.view.get("phase") != "BATTLE" or app._playback_running:
		failure = "The saved melee windup did not open paused"
		return
	if not await _wait_for_battle_models():
		return
	for actor in app.view.battle_view.actors:
		if not actor.has("melee_pending"):
			continue
		var pawn: Node3D = app.board.stage.actors[actor.id].node
		var cast: String = actor.melee_pending.id
		var audit: Dictionary = app.board.stage.audit
		if pawn.gap_cast != cast or pawn.player.assigned_animation != "GapHold" or int(audit.clips.get("GapSet", 0)) != 0:
			failure = "Reopening replayed the preparation or lost the melee hold"
			return
		await _capture("gap-resumed-hold")
		if not await _command("step"):
			return
		var events: Array = app.view.battle_view.events
		var hit := events.any(func(row): return row.type == "hit" and row.get("action_id") == cast)
		if not hit or int(audit.clips.get("GapStrike", 0)) != 1 or not pawn.gap_cast.is_empty():
			failure = "Continuing the saved hold did not produce one true close-range strike"
			return
		melee_marks["resumed_cast"] = cast
		return
	failure = "The saved battle had no melee windup available"


func _check_bow_resume() -> void:
	if app.view.get("phase") != "BATTLE" or app._playback_running:
		failure = "The saved archer windup did not open paused"
		return
	if not await _wait_for_battle_models():
		return
	var stage = app.board.stage
	var casts := {}
	for actor in app.view.battle_view.actors:
		if not actor.has("bow_pending"):
			continue
		var pawn: Node3D = stage.actors[actor.id].node
		var cast: String = actor.bow_pending.id
		if pawn.bow_cast != cast or pawn.player.assigned_animation != "BowAim" or int(stage.audit.clips.get("BowLoad", 0)) != 0:
			failure = "Reopening replayed the draw animation or lost the bow aim"
			return
		casts[cast] = actor.id
	if casts.size() != 2:
		failure = "The saved fortress frame did not contain both aiming archers"
		return
	await _capture("bow-resumed-aim")
	if not await _command("step"):
		return
	for cast in casts:
		var shot: Dictionary = stage.audit.bow_shots.get(cast, {})
		if shot.is_empty() or shot.hits.is_empty() or stage.actors[casts[cast]].node.bow_cast != "":
			failure = "Resuming the saved aim did not fire at a native hit target"
			return
	if int(stage.audit.bow_flights) != casts.size() or int(stage.audit.clips.get("BowRelease", 0)) != casts.size():
		failure = "Resuming the prepared arrows launched a duplicate or missing arrow"
		return
	bow_marks["resumed_casts"] = casts


func _check_projectile_close() -> void:
	await _check_bow_resume()
	if not failure.is_empty():
		return
	var stage = app.board.stage
	var active: int = stage.flying_projectiles.size()
	var hwnd := DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE)
	if active < 2 or app.client.busy or hwnd == 0:
		failure = "The close request test did not reach a committed step with live flights"
		return
	stage.set_paused(true)
	bow_marks["paused_flights_on_close"] = active
	bow_marks["close_tick"] = app.view.battle_view.tick
	bow_marks["native_window_handle"] = str(hwnd)


func _check_paused_viewport() -> void:
	await _check_bow_resume()
	if not failure.is_empty():
		return
	var stage = app.board.stage
	var viewport: SubViewport = stage.viewport_3d
	var held: Array = stage.flying_projectiles.duplicate()
	if held.size() != 2:
		failure = "The settings test needs two active arrows"
		return
	var version: int = app.client.frame.state_version
	var saved: String = app.client.frame.files["save.json"]
	app._show_settings()
	if not await _wait_until(func(): return viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED, 1000):
		failure = "The 3D board kept rendering while settings were open"
		return
	var frame := viewport.get_texture().get_image().get_data()
	var positions := held.map(func(arrow): return arrow.global_position)
	await get_tree().create_timer(0.42).timeout
	if not app.settings_open or viewport.render_target_update_mode != SubViewport.UPDATE_DISABLED \
			or frame.is_empty() or viewport.get_texture().get_image().get_data() != frame \
			or stage.flying_projectiles != held or held.map(func(arrow): return arrow.global_position) != positions:
		failure = "Settings did not keep the last board image and both flights suspended"
		return
	await _capture("settings-frozen-board")
	if not await _press("settings-back"):
		return
	if viewport.render_target_update_mode != SubViewport.UPDATE_ALWAYS \
			or not await _wait_until(func(): return stage.flying_projectiles.is_empty(), 1100) \
			or app.client.frame.state_version != version or app.client.frame.files["save.json"] != saved:
		failure = "Returning to combat did not finish the same two flights without saving again"
		return
	paused_viewport_checks = {"freeze_seconds": 0.42, "frozen_flights": held.size(),
		"frozen_image_bytes": frame.size(), "resume_rendered": true, "save_version": version, "save_sha256": saved}
	await _capture("settings-restored-board")


func _check_projectile_reopen() -> void:
	if app.view.get("phase") != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "Closing during a flight did not restore the battle paused"
		return
	var stage = app.board.stage
	var released: Array = app.view.battle_view.events.filter(func(event):
		return event.type == "release" and event.get("move") == "S03-A")
	await get_tree().create_timer(0.40).timeout
	if released.size() != 2 or int(stage.audit.bow_flights) != 0 or not stage.flying_projectiles.is_empty():
		failure = "Restoring the committed step replayed a projectile or lost the two releases"
		return
	bow_marks["reopened_committed_tick"] = app.view.battle_view.tick
	bow_marks["replay_flights"] = stage.audit.bow_flights


func _check_projectile_resize() -> void:
	await _check_bow_resume()
	if not failure.is_empty():
		return
	var stage = app.board.stage
	if stage.flying_projectiles.size() != 2 or DisplayServer.get_name() == "headless":
		failure = "The resize test needs two real flights in a Windows viewport"
		return
	stage.set_paused(true)
	var arrow: Node3D = stage.flying_projectiles[0]
	var pawn: Node3D = stage.actors["INIT-S03-A"].node
	var bow_offset: Vector3 = arrow.global_position - pawn.destination
	var version: int = app.client.frame.state_version
	var window := get_window()
	var before := window.size
	var old_viewport: Vector2i = stage.viewport_3d.size
	var old_display := window.get_final_transform()
	window.size = Vector2i(1024, 720)
	if not await _wait_until(func(): return window.size != before and window.get_final_transform() != old_display, 3000):
		failure = "Windows did not apply the requested window size"
		return
	if not _check_ground_projection("resized") or app.client.frame.state_version != version:
		if failure.is_empty():
			failure = "Resizing submitted an unexpected rule action"
		return
	if not is_instance_valid(arrow) or stage.flying_projectiles.size() != 2:
		failure = "Resizing damaged the paused projectile pool"
		return
	var shift: Vector3 = arrow.global_position - pawn.destination - bow_offset
	bow_marks["resize_flight_anchor_error_m"] = shift.length()
	bow_marks["resize_window"] = [window.size.x, window.size.y]
	bow_marks["resize_logical_viewport"] = [stage.viewport_3d.size.x, stage.viewport_3d.size.y]
	await _capture("projectiles-resized")
	window.size = before
	if not await _wait_until(func(): return window.size == before and stage.viewport_3d.size == old_viewport \
			and window.get_final_transform() == old_display, 3000) \
			or not _check_ground_projection("restored") or app.client.frame.state_version != version:
		if failure.is_empty():
			failure = "Restoring the original window changed the live battle state"
		return


func _check_sidecar_reconnect() -> void:
	var version: int = app.client.frame.state_version
	var tick := int(app.view.battle_view.tick)
	var epoch: String = app.client.frame.connection_epoch
	var unresolved := "--unresolved-reconnect" in OS.get_cmdline_user_args()
	if not await _press("combat-playback") or not await _wait_until(func(): return app.client.blocked, 9000):
		failure = "The active fight did not lose its reply"
		return
	if not app.client.can_reconnect or not app._playback_running or app.client.pending.is_empty() \
			or int(app.client.frame.state_version) != version:
		failure = "The interrupted battle lost its pending request or its last acknowledged state"
		return
	var request: String = app.client.pending.request_id
	await _capture("sidecar-interrupted")
	var reconnect: Button = app.command_buttons.get("reconnect")
	if reconnect == null or reconnect.disabled:
		failure = "No native reconnect control after transport failure"
		return
	var point := _button_point(reconnect)
	_mouse(point, true)
	_mouse(point, false)
	await get_tree().process_frame
	var deadline := Time.get_ticks_msec() + 10000
	while app.client.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if app.client.busy:
		failure = "Reconnecting did not settle"
		return
	side_checks["recovered_request"] = request
	if unresolved:
		if not app.client.blocked or app.client.can_reconnect or app.command_buttons.has("reconnect") \
				or app.client.pending.get("request_id") != request or int(app.client.frame.state_version) != version:
			failure = "An unresolved transaction did not stay blocked with the same pending request"
			return
	else:
		if app.client.blocked or not app.client.pending.is_empty() or app.client.frame.connection_epoch == epoch \
				or int(app.client.frame.state_version) != version + 1 or int(app.view.battle_view.tick) != tick + 1 \
				or app._playback_running or not app._live_impacts.is_empty() or not await _check_paused("reconnected"):
			failure = "The recovered receipt did not restore exactly one committed beat and stay paused"
			return
		steps.append({"command": "step", "version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["reconnect_unresolved"] = unresolved
	await _capture("sidecar-reconnected")


func _check_busy_close() -> void:
	if app.view.get("phase") != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The close-during-save test needs a paused battle"
		return
	var before: int = app.client.frame.state_version
	var hwnd := DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE)
	var close_while_busy: Array[bool] = []
	get_window().close_requested.connect(func() -> void:
		close_while_busy.append(app.client.busy)
	, CONNECT_ONE_SHOT)
	if hwnd == 0 or not app.client.submit("step", []) or not app.client.busy:
		failure = "The Windows test did not start a real pending battle command"
		return
	var request: String = app.client.pending.request_id
	app.client.busy_changed.connect(func(value: bool) -> void:
		if value or close_while_busy.is_empty() or not close_while_busy[0]:
			return
		var frame: Dictionary = app.client.frame
		var settled: bool = int(frame.state_version) == before + 1 and app.client.pending.is_empty()
		var receipt := FileAccess.open(app.data_dir.path_join(app.case_name + ".busy-close.json"), FileAccess.WRITE)
		if receipt == null:
			return
		receipt.store_string(JSON.stringify({"scenario": "busy-close", "passed": settled,
			"steps": [{"command": "step", "version": frame.state_version, "digest": frame.state_digest}],
			"files": frame.files, "state_digest": frame.state_digest,
			"bow_checks": {"guarded_close_request": request, "received_windows_close": true,
				"close_tick": app.view.battle_view.tick}}, "  "))
		receipt.close()
	, CONNECT_ONE_SHOT)
	var armed := FileAccess.open(app.data_dir.path_join(app.case_name + ".close-armed.json"), FileAccess.WRITE)
	if armed == null:
		failure = "The OS close sender could not be armed"
		return
	armed.store_string(JSON.stringify({"scenario": "busy-close-armed", "native_window_handle": str(hwnd)}))
	armed.close()
	if not await _wait_until(func(): return not close_while_busy.is_empty(), 1500) \
			or not close_while_busy[0]:
		bow_marks["received_windows_close"] = close_while_busy
		failure = "The window did not acknowledge the close request while the save was pending"
		return
	await get_tree().create_timer(3.0).timeout
	failure = "The application still waited for another close after the save finished"


func _check_aid_resume() -> void:
	if app.view.get("phase") != "BATTLE" or app._playback_running:
		failure = "The saved aid windup did not reopen paused"
		return
	if not await _wait_for_battle_models():
		return
	var stage = app.board.stage
	for actor in app.view.battle_view.actors:
		if not actor.has("aid_pending"):
			continue
		var pawn: Node3D = stage.actors[actor.id].node
		var cast: String = actor.aid_pending.id
		if pawn.cast_id != cast or pawn.player.assigned_animation != "AidHold" or not stage.audit.aid_actions.is_empty():
			failure = "Reopening replayed the old release or did not restore the aid hold"
			return
		await _capture("aid-resumed-hold")
		if not await _command("step") or not await _observe_aid():
			return
		if not await _wait_until(func(): return int(stage.audit.aid_contacts) > 0, 1200):
			failure = "The resumed aid never reached contact"
			return
		if aid_marks.get("heal", {}).get("id") != cast or not pawn.cast_id.is_empty() \
				or int(stage.audit.aid_contacts) != 1 or int(stage.audit.aid_flights) != 1:
			failure = "Resuming the pending aid did not produce exactly one native heal and treatment effect"
			return
		aid_marks["resumed_cast"] = cast
		return
	failure = "The saved battle had no aid windup available"


func _check_crossbow(restore: bool) -> void:
	var stage = app.board.stage
	var id := ""
	for member in app.view.party:
		if member.unit_id == "M03" and member.deployed:
			id = member.instance_id
			break
	if id.is_empty():
		failure = "The archived formation has no deployed crossbow actor"
		return
	if not restore:
		var model := await _check_model_deployment(id, "crossbow")
		if model == null or not await _command("fight"):
			return
		if stage.actors.get(id, {}).get("node") != model:
			failure = "The crossbow model was replaced on entering battle"
			return
		crossbow_marks["handoff"] = true
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The crossbow battle did not open with live models and paused controls"
		return
	var pawn: Node3D = stage.actors.get(id, {}).get("node")
	if pawn == null:
		failure = "The crossbow battle did not render the recruited actor"
		return
	var row: Dictionary = app._combatants[id]
	for index in range(12):
		if row.has("bow_pending") or restore:
			break
		if not await _command("step"):
			return
		row = app._combatants.get(id, {})
	if not row.has("bow_pending"):
		failure = "The archived battle did not reach a real crossbow windup"
		return
	var cast: String = row.bow_pending.id
	if not await _wait_until(func(): return pawn.player.assigned_animation == "BreachHold", 1200) \
			or pawn.bow_cast != cast or (restore and not stage.audit.crossbow_shots.is_empty()):
		failure = "The native crossbow lock did not produce the saved hold pose"
		return
	await _capture("crossbow-hold")
	var flights := int(stage.audit.crossbow_flights)
	if not await _command("step"):
		return
	var shot: Dictionary = stage.audit.crossbow_shots.get(cast, {})
	var found: Array = app.view.battle_view.events.filter(func(event):
		return event.type == "hit" and event.get("action") == "M03-A" and event.get("action_id") == cast)
	if found.size() != 1 or shot.get("hits") != [found[0].target] or float(shot.get("aim_dot", 0.0)) < 0.998:
		failure = "The breach bolt did not use its native target and release axis"
		return
	if not await _wait_until(func(): return int(stage.audit.crossbow_flights) == flights + 1, 1200):
		failure = "The valid breach release did not launch a pooled bolt"
		return
	await _capture("crossbow-flight")
	if not await _wait_until(func(): return pawn.player.assigned_animation == "BreachReload", 1200):
		failure = "The breach clip did not hand off to its authored reload"
		return
	await _capture("crossbow-reload")
	crossbow_marks["release"] = {"id": cast, "target": found[0].target,
		"damage": found[0].actual_hp_damage, "resumed": restore}


func _check_mist(restore: bool) -> void:
	var id := ""
	for member in app.view.party:
		if member.unit_id == "M04" and member.deployed:
			id = member.instance_id
			break
	if id.is_empty():
		failure = "The archived formation has no deployed mist caster"
		return
	var stage = app.board.stage
	if not restore:
		var model := await _check_model_deployment(id, "mist")
		if model == null or not await _command("fight"):
			return
		if stage.actors.get(id, {}).get("node") != model:
			failure = "The mist caster did not keep its deployed model on entering battle"
			return
		mist_marks["handoff"] = true
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The mist caster did not open in the live battle at the saved pace"
		return
	var pawn: Node3D = stage.actors.get(id, {}).get("node")
	if pawn == null:
		failure = "The recruited mist caster did not receive its scene"
		return
	var row: Dictionary = app._combatants[id]
	for index in range(24):
		if row.has("mist_pending") or restore:
			break
		if not await _command("step"):
			return
		row = app._combatants.get(id, {})
	if not row.has("mist_pending"):
		failure = "The archived encounter did not produce the native counterspell"
		return
	var cast: String = row.mist_pending.id
	if not await _wait_until(func(): return pawn.player.assigned_animation == "MistHold", 1200) \
			or pawn.cast_id != cast or (restore and not stage.audit.mist_casts.is_empty()):
		failure = "The active native mist windup did not use the authored hold"
		return
	await _capture("mist-hold")
	if not await _command("step"):
		return
	var shot: Dictionary = stage.audit.mist_casts.get(cast, {})
	var events: Array = app.view.battle_view.events
	var hit := events.filter(func(event): return event.type == "hit" and event.get("action_id") == cast)
	var delays := events.filter(func(event): return event.type == "cast_delayed" and event.actor == id)
	if hit.size() != 1 or delays.size() != 1 or shot.get("target") != hit[0].target \
			or float(shot.get("aim_dot", 0.0)) < 0.998 or delays[0].target != hit[0].target:
		failure = "The mist effect did not match the native hit and delayed enemy cast"
		return
	var delay: Dictionary = delays[0]
	if not await _wait_until(func(): return stage.flying_projectiles.any(func(p): return p.mesh == stage.mist_visual), 1200):
		failure = "The actual mist release did not show its palm effect"
		return
	await _capture("mist-flight")
	if not await _wait_until(func(): return stage.marks.get(delay.target, {}).get("label") == "延咒", 1200):
		failure = "The actual delay did not mark the enemy cast on contact"
		return
	if stage.audit.mist_flights != 1 or not pawn.cast_id.is_empty():
		failure = "The counterspell step created a second spell or retained the old lock"
		return
	var feedback := "延至第 %d 拍" % int(delay.release_tick)
	var snapshot: Dictionary = app.view.battle_view
	if feedback not in app.board.impact_text(app.board.impacts.get(delay.target, {})) \
			or not _report_mentions(app._combat_log(snapshot), feedback):
		failure = "The delayed beat was missing from the hit badge or the battle report"
		return
	await _capture("mist-delay")
	mist_marks["release"] = {"id": cast, "target": delay.target, "enemy_cast": delay.cast_id,
		"due": delay.release_tick, "damage": hit[0].actual_hp_damage, "resumed": restore}
	mist_marks["feedback"] = feedback


func _check_mercenary_mix() -> void:
	var deployed: Array = app.view.party.filter(func(member): return member.deployed)
	var kinds := deployed.map(func(member): return member.unit_id)
	kinds.sort()
	if app.view.get("phase") != "EXPLORE" or kinds != ["M01", "M02", "M03", "M04"]:
		failure = "The mixed mercenary test needs four deployed classes at contact"
		return
	if measure != null:
		measure.begin("RG07-N01")
	if not await _command("fight") or not await _wait_for_battle_models():
		return
	if not app._playback_running:
		failure = "The mixed mercenary battle did not start automatic combat"
		return
	await _capture("mercenary-mixed-open")
	if not await _wait_until(func(): return app.view.get("phase") != "BATTLE", 60000):
		failure = "The mixed mercenaries did not finish battle automatically"
		return
	if measure != null:
		measure.finish()
	var results: Array = app.view.get("battle_results", [])
	var result: Dictionary = results[-1] if not results.is_empty() else {}
	var audit: Dictionary = app.board.stage.audit
	if result.get("encounter_id") != "RG07-N01" or result.get("result") != "VICTORY" \
			or not ["spear_peak", "aid_peak", "crossbow_peak", "mist_peak"].all(func(key): return int(audit[key]) == 1):
		failure = "The mixed 3D party did not record all four models and the expected victory"
		return
	if int(audit.spear_releases) < 1 or int(audit.aid_contacts) < 1 or int(audit.crossbow_flights) < 1 \
			or int(audit.mist_flights) < 1:
		failure = "The mixed battle omitted a native combat effect from one class"
		return
	if DisplayServer.get_name() != "headless" and (int(audit.mimic_peak) != 1 or not audit.mimic_prepared_before_battle):
		failure = "The mixed battle did not render its prepared mimic"
		return
	mercenary_checks = {"party": kinds, "result": result.result, "tick": app.view.battle_view.tick}
	await _capture("mercenary-mixed-result")


func _check_echo_delay() -> void:
	await _check_mist(true)
	if not failure.is_empty():
		return
	var evidence: Dictionary = mist_marks.release
	var stage = app.board.stage
	var pawn = stage.actors.get(evidence.target, {}).get("node")
	var pending: Dictionary = app._combatants[evidence.target].get("echo_pending", {})
	if pawn == null or not pawn.winding or pending.get("id") != evidence.enemy_cast \
			or int(pending.get("due", 0)) != int(evidence.due) or stage.audit.echo_peak != 2:
		failure = "The two shell models did not restore the locked echo and its revised beat"
		return
	var cast: String = evidence.enemy_cast
	var locked: Array = pending.cells
	if not await _command("step"):
		return
	if not pawn.winding or stage.audit.echo_releases.has(cast) or int(app.view.battle_view.tick) != int(evidence.due) - 1:
		failure = "The delayed shell released on the earlier beat"
		return
	var held_shell: Quaternion = pawn.skeleton.get_bone_pose_rotation(pawn.shell)
	await _capture("echo-delayed-hold")
	if not await _command("step"):
		return
	var release: Dictionary = stage.audit.echo_releases.get(cast, {})
	var events: Array = app.view.battle_view.events
	var missed := events.any(func(event): return event.type == "skill_miss" and event.get("action_id") == cast)
	if release.get("cells") != locked or release.get("actor") != evidence.target or not pawn.sounding \
			or pawn.winding or int(app.view.battle_view.tick) != int(evidence.due) or not missed:
		failure = "The shell animation did not match its exact delayed release and native miss"
		return
	await get_tree().create_timer(0.18).timeout
	var sounding_shell: Quaternion = pawn.skeleton.get_bone_pose_rotation(pawn.shell)
	var pose_delta := held_shell.angle_to(sounding_shell)
	if pose_delta < 0.12 or not is_equal_approx(pawn.scale.x, 0.72):
		failure = "The shell pose or board footprint did not match the staged model"
		return
	echo_checks = {"release_tick": int(evidence.due), "caster": evidence.target, "cast": cast,
		"cells": locked, "native_miss": missed, "staged_models": stage.audit.echo_peak,
		"display_scale": pawn.scale.x, "shell_pose_delta_rad": pose_delta}
	await _capture("echo-release")


func _check_sting_resume() -> void:
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The sting checkpoint did not open in a paused live battle"
		return
	var stage = app.board.stage
	var caster := "EN03-REG-4"
	var pawn = stage.actors.get(caster, {}).get("node")
	var pending: Dictionary = app._combatants.get(caster, {}).get("sting_pending", {})
	var cells: Array = pending.get("cells", [])
	if pawn == null or not pawn.winding or cells.size() != 1 or stage.audit.wasp_peak != 1 \
			or not is_equal_approx(pawn.scale.x, 0.66) or not stage.audit.sting_releases.is_empty():
		failure = "The wasp did not restore its locked sting on the board"
		return
	var cast: String = pending.id
	var due := int(pending.due)
	var ground: float = pawn.position.y
	var bone: int = pawn.wings[0]
	var held: Quaternion = pawn.skeleton.get_bone_pose_rotation(bone)
	var wing_delta := 0.0
	for frame in range(12):
		await get_tree().process_frame
		var pose: Quaternion = pawn.skeleton.get_bone_pose_rotation(bone)
		wing_delta = maxf(wing_delta, held.angle_to(pose))
	if wing_delta < 0.04 or not is_equal_approx(pawn.position.y, ground) \
			or int(app.view.battle_view.tick) != due - 1:
		failure = "The held sting changed the board position or did not animate its wings"
		return
	await _capture("sting-windup")
	if not await _command("step"):
		return
	var release: Dictionary = stage.audit.sting_releases.get(cast, {})
	var events: Array = app.view.battle_view.events
	var missed := events.any(func(event): return event.type == "skill_miss" and event.get("action_id") == cast)
	var hit := events.any(func(event): return event.type == "hit" and event.get("action_id") == cast)
	if release.get("cells") != cells or release.get("actor") != caster or not pawn.stinging \
			or pawn.winding or int(app.view.battle_view.tick) != due or (not missed and not hit) \
			or not is_equal_approx(pawn.position.y, ground):
		failure = "The grounded sting did not use the saved target cell on the native release beat"
		return
	var darts: Array = stage.flying_projectiles.filter(func(shot): return shot.mesh == stage.sting_visual)
	if darts.size() != 1 or stage.audit.sting_flights != 1 or release.get("missed") != missed:
		failure = "The native release did not launch one dart with the committed outcome"
		return
	var dart: MeshInstance3D = darts[0]
	await _capture("sting-flight")
	if not await _wait_until(func(): return not dart.visible, 1200):
		failure = "The sting did not return to the shared projectile pool"
		return
	var endpoint: Vector3 = stage._world(stage._at(cells[0])) + Vector3.UP * (0.10 if missed else 0.86)
	var error := dart.to_global(Vector3.UP * stage.STING_NOSE).distance_to(endpoint)
	if error > 0.0001 or stage.spare_projectiles.count(dart) != 1 \
			or (missed and stage.marks.get(cast, {}).get("label") != "放空"):
		failure = "The sting did not finish at its original locked cell or registered more than once"
		return
	sting_checks = {"release_tick": due, "caster": caster, "cast": cast, "cells": cells,
		"native_miss": missed, "native_hit": hit, "wing_delta_rad": wing_delta, "ground_y": ground,
		"endpoint_error_m": error, "returned_to_pool": true}
	await _capture("sting-release")


func _check_live_shields() -> void:
	var snapshot: Dictionary = app.view.get("battle_view", {})
	if app.view.get("phase") != "BATTLE" or app._playback_running:
		failure = "The shield checkpoint did not reopen paused"
		return
	if snapshot.encounter == "RG02-N01":
		await _check_live_shared_pool()
		return
	var guard := "INIT-S01-A"
	var runner := "INIT-S02-A"
	if snapshot.encounter != "TUT01-ROOT" or int(snapshot.tick) != 0 \
			or not _panel_has("生效方案 · 同步盾列") \
			or not await _press("battle-unit-" + guard) \
			or not _showing_private_shields([guard, runner], 12) or not app._battle_detail.text.contains("自身护盾 12"):
		failure = "The two opening shields and plan were missing from the native HUD"
		return
	await _capture("opening-shields")
	if not await _commands(["step", "step", "step"]) or not _showing_private_shields([guard, runner], 7) \
			or int(app._combatants[guard].hp) != 29 or int(app._combatants[runner].hp) != 24 \
			or not app._battle_detail.text.contains("自身护盾 7") or not app._battle_detail.text.contains("抵消 5"):
		failure = "Shield consumption was not shown independently of health"
		return
	side_checks["private_shields"] = {"members": [guard, runner], "opened": 12, "after_hit": 7, "tick": app.view.battle_view.tick}
	await _capture("absorbed-shields")


func _showing_private_shields(members: Array, expected: int) -> bool:
	for id in members:
		var row: Dictionary = app._combatants.get(id, {})
		var badge: Dictionary = app.board._unit_markers.get(id, {})
		var button: Button = app.command_buttons.get("battle-unit-" + id)
		if int(row.get("private_shield", 0)) != expected or badge.is_empty() or not badge.appearance.barrier \
				or button == null or not button.text.contains("自身盾 %d" % expected):
			return false
	return true


func _check_live_shared_pool() -> void:
	var guard := "EN04-REG-2"
	var ward := "EN01-REG-3"
	if int(app.view.battle_view.tick) != 2 or not await _press("battle-unit-" + ward) \
			or not await _command("step") or not _showing_shared_pool(guard, ward, 16):
		failure = "The two recipients did not display a single 16-point shield pool"
		return
	await _capture("shared-shield-pool")
	if not await _commands(["step", "step"]) or not _showing_shared_pool(guard, ward, 12):
		failure = "The shared pool did not fall to 12 for both recipients"
		return
	await _capture("shared-shield-consumed")
	if not await _command("step") or int(app.view.battle_view.tick) != 6 \
			or app._combatants[guard].has("shared_protection") or app._combatants[ward].has("shared_protection") \
			or app.board._unit_markers[guard].appearance.shared_shield or app.board._unit_markers[ward].appearance.shared_shield \
			or app._battle_detail.text.contains("共享盾池"):
		failure = "An expired shield pool remained on the board or in the detail panel"
		return
	side_checks["shared_shield"] = {"owner": guard, "ward": ward, "amounts": [16, 12, 0], "ticks": [3, 5, 6]}


func _showing_shared_pool(guard: String, ward: String, expected: int) -> bool:
	var owner_pools: Array = app._combatants[guard].get("shared_protection", [])
	var ward_pools: Array = app._combatants[ward].get("shared_protection", [])
	return owner_pools.size() == 1 and ward_pools == owner_pools and owner_pools[0].owner == guard \
		and int(owner_pools[0].amount) == expected and int(owner_pools[0].expires) == 5 \
		and app.board._unit_markers[guard].appearance.shared_shield and app.board._unit_markers[ward].appearance.shared_shield \
		and app._battle_detail.text.contains("共享盾池 %d" % expected) and app._battle_detail.text.contains("至第 5 拍")


func _check_guard_feedback() -> void:
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The protection checkpoint did not open in a paused live battle"
		return
	var guard := "EN04-REG-2"
	var ward := "EN01-REG-3"
	var stage = app.board.stage
	if not await _wait_until(func(): return stage.actors.has(guard) and not stage._has_model_work(), 8000):
		failure = "The saved guard model was unavailable after background loading"
		return
	if not await _fortress_frame():
		return
	var pawn = stage.actors.get(guard, {}).get("node")
	if pawn == null or pawn.player.current_animation != "EN04Ready" or pawn.guarded:
		failure = "The ring guard did not restore its round-shield model in the ready pose"
		return
	var original_y: float = pawn.skeleton.get_bone_global_pose(pawn.plate_bone).origin.y
	if not await _command("step"):
		return
	var snapshot: Dictionary = app.view.battle_view
	var pool: Array = snapshot.events.filter(func(event): return event.type == "shared_shield" and event.actor == guard)
	var cards: Dictionary = app.board.impacts
	if int(snapshot.tick) != 3 or pool.size() != 1 or pool[0].members != [guard, ward] \
			or int(pool[0].amount) != 16 or int(pool[0].expires) != 5 \
			or int(cards.get(guard, {}).get("shared_shield", 0)) != 16 or cards.get(ward, {}).has("shared_shield") \
			or not "共享盾 +16" in app.board.impact_text(cards[guard]) \
			or not _report_mentions(app._combat_log(snapshot), "提供 16 点共享护盾，持续至第 5 拍"):
		failure = "The board or report counted the shared shield as separate grants"
		return
	if not pawn.guarded or int(stage.audit.clips.get("EN04Raise", 0)) != 1 \
			or not await _wait_until(func(): return pawn.player.current_animation == "EN04Hold", 1000):
		failure = "The committed shared shield did not raise the model's round shield"
		return
	var raised_y: float = pawn.skeleton.get_bone_global_pose(pawn.plate_bone).origin.y
	if raised_y - original_y < 0.20:
		failure = "The shield grip did not rise into the held pose"
		return
	await _capture("guard-shared-pool")
	if "--lock-review" in OS.get_cmdline_user_args():
		await _check_warning_shape()
		if not failure.is_empty():
			return
	if not await _commands(["step", "step"]):
		return
	snapshot = app.view.battle_view
	var redirects: Array = snapshot.events.filter(func(event): return event.type == "guard_redirect" and event.actor == guard)
	if int(snapshot.tick) != 5 or redirects.size() != 1 or redirects[0].ward != ward:
		failure = "The baseline guard did not redirect one hit on beat five"
		return
	var redirect: Dictionary = redirects[0]
	var hits: Array = snapshot.events.filter(func(event): return event.type == "hit" \
		and event.get("action_id") == redirect.action_id and event.actor == redirect.attacker)
	var hit_card: Dictionary = app.board.impacts.get(guard, {})
	if hits.size() != 1 or hits[0].target != guard or int(hits[0].actual_hp_damage) != 0 \
			or int(hits[0].absorbed) != 4 or hit_card.get("ward") != ward \
			or not "代受" in app.board.impact_text(hit_card) \
			or not _report_mentions(app._combat_log(snapshot), "为 %s 代受攻击" % app._combatant_name(ward)):
		failure = "The guard card or report did not match the redirected hit and its actual absorption"
		return
	if not await _wait_until(func(): return int(stage.audit.clips.get("EN04Brace", 0)) == 1, 1300):
		failure = "The model did not brace at the redirected impact"
		return
	guard_checks = {"shield_tick": 3, "shared_grant": pool[0], "redirect_tick": 5,
		"redirect": redirect, "final_hit": hits[0], "card": app.board.impact_text(hit_card),
		"shield_grip_lift_m": raised_y - original_y, "pose_clips": stage.audit.clips.duplicate()}
	await _capture("guard-redirect")


func _check_enemy_spear_resume() -> void:
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The enemy spear checkpoint did not reopen paused"
		return
	var id := "EN17-STORY-3"
	var stage = app.board.stage
	var pawn = stage.actors.get(id, {}).get("node")
	var pending: Dictionary = app._combatants.get(id, {}).get("spear_pending", {})
	var lock: Array = pending.get("cells", [])
	if pawn == null or not pawn.enemy or lock.size() != 2 or pawn.cast_id != pending.id \
			or pawn.lock_cells != lock or pawn.player.assigned_animation != "EN17Hold" \
			or stage.audit.enemy_spear_peak != 1 or not stage.audit.enemy_spear_releases.is_empty():
		failure = "The enemy did not restore its authored hold and both native cells"
		return
	var aim: Vector3 = stage._world(stage._at(lock[0])) - stage._world(stage._at(pending.origin))
	var shaft: Vector3 = pawn.spear_axis()
	var dot := Vector2(aim.x, aim.z).normalized().dot(Vector2(shaft.x, shaft.z).normalized())
	if dot < 0.998:
		failure = "The staged enemy spear did not point along its authoritative lock"
		return
	await _capture("enemy-spear-hold")
	if not await _command("step"):
		return
	var release: Dictionary = stage.audit.enemy_spear_releases.get(pending.id, {})
	var events: Array = app.view.battle_view.events
	var hits := events.filter(func(event): return event.type == "hit" and event.get("action_id") == pending.id)
	if release.get("cells") != lock or release.get("actor") != id or pawn.player.assigned_animation != "EN17Thrust" \
			or int(app.view.battle_view.tick) != int(pending.due) or hits.size() != 1 or int(hits[0].actual_hp_damage) != 8:
		failure = "The enemy thrust did not match the native release, target and damage"
		return
	enemy_spear_checks = {"actor": id, "cast": pending.id, "cells": lock, "aim_dot": dot,
		"release_tick": int(pending.due), "target": hits[0].target, "damage": hits[0].actual_hp_damage}
	await _capture("enemy-spear-thrust")


func _check_skeleton_encounter() -> void:
	if app.view.phase != "BATTLE" or app._playback_running or not await _wait_for_battle_models():
		failure = "The fortress skeleton encounter did not restore paused"
		return
	var stage = app.board.stage
	var archer := "EN22-FX-3"
	var swordsman := "EN21-FX-2"
	var pawn = stage.actors.get(archer, {}).get("node")
	var guard = stage.actors.get(swordsman, {}).get("node")
	var pending: Dictionary = app._combatants.get(archer, {}).get("bone_pending", {})
	var lock: Array = pending.get("cells", [])
	var expected := [Vector2i(2, 4), Vector2i(2, 3), Vector2i(2, 2), Vector2i(2, 1)]
	var archer_clip: String = "" if pawn == null else pawn.player.assigned_animation
	var guard_clip: String = "" if guard == null else guard.player.assigned_animation
	if pawn == null or guard == null or lock.map(func(cell): return Vector2i(int(cell[0]), int(cell[1]))) != expected \
			or pawn.cast_id != pending.id or archer_clip != "EN22Hold" or guard_clip != "EN21Ready" \
			or not stage.audit.bone_arrows.is_empty():
		failure = "The native four-cell draw did not restore with the skeleton models: %s / %s / %s" % [lock, archer_clip, guard_clip]
		return
	var axis: Vector3 = stage._world(stage._at(lock[0])) - stage._world(stage._at(pending.origin))
	if axis.normalized().dot(pawn.global_basis.z) < 0.998:
		failure = "The bone bow did not face along its locked line"
		return
	await _capture("bone-bow-hold")
	if not await _commands(["step", "step"]):
		return
	var release: Dictionary = stage.audit.bone_arrows.get(pending.id, {})
	var events: Array = app.view.battle_view.events
	if int(app.view.battle_view.tick) != 4 or release.get("cells") != lock \
			or release.get("landing") != lock[1] or release.get("blocked_by") != swordsman or not release.get("miss", false) \
			or not release.get("hits", []).is_empty() or not events.any(func(event):
				return event.type == "skill_miss" and event.action_id == pending.id):
		failure = "The bone arrow did not stop at the native ally blocker along the saved line"
		return
	if not await _wait_until(func(): return int(stage.audit.bone_arrow_flights) == 1, 1200):
		failure = "The bone arrow did not use one pooled flight"
		return
	await _capture("bone-arrow-flight")
	if not await _wait_until(func(): return stage.marks.get(pending.id, {}).get("label") == "受阻", 1200):
		failure = "The blocked arrow did not display the blocked marker at the flight end"
		return
	await _capture("bone-arrow-blocked")
	if not await _command("step"):
		return
	var snapshot: Dictionary = app.view.battle_view
	var shields: Array = snapshot.events.filter(func(event): return event.type == "private_shield" and event.actor == swordsman)
	var card: Dictionary = app.board.impacts.get(swordsman, {})
	if int(snapshot.tick) != 5 or shields.size() != 1 or shields[0].target != swordsman \
			or int(shields[0].amount) != 10 or int(shields[0].expires) != 7 \
			or int(stage.audit.clips.get("EN21Raise", 0)) != 1 or not "架刀 +10" in app.board.impact_text(card) \
			or not _report_mentions(app._combat_log(snapshot), "10 点自身护盾，持续至第 7 拍"):
		failure = "The swordsman's blade guard did not match its private shield"
		return
	skeleton_checks = {"release": release, "archer_cast": pending.id, "private_shield": shields[0],
		"flight_count": stage.audit.bone_arrow_flights, "guard_card": app.board.impact_text(card)}
	await get_tree().create_timer(0.36).timeout
	await _capture("bone-blade-guard")


func _check_bow_flight_lifetime() -> void:
	var stage = app.board.stage
	if app.view.get("phase") != "BATTLE" or not await _wait_for_battle_models() or not stage.actors.has("INIT-S03-A"):
		failure = "The flight lifetime check needs a staged bow model"
		return
	var version: int = app.client.frame.state_version
	var pawn: Node3D = stage.actors["INIT-S03-A"].node
	var mesh: Mesh = pawn.arrow_mesh
	var start: Vector3 = pawn.arrow_origin()
	var landing := start + Vector3(2, 0, 0)
	stage._launch_arrow(mesh, start, landing, 0.5)
	var arrow: MeshInstance3D = stage.flying_projectiles[-1]
	stage.clear_battle()
	await get_tree().create_timer(0.60).timeout
	if not is_instance_valid(arrow) or arrow.visible or stage.spare_projectiles.count(arrow) != 1 \
			or not stage.flying_projectiles.is_empty() or not stage.projectile_tweens.is_empty():
		failure = "A flight interrupted by leaving the battle was not parked exactly once"
		return
	stage._launch_arrow(mesh, start, landing, 0.08)
	if stage.flying_projectiles.back() != arrow or not arrow.visible or stage.spare_projectiles.has(arrow):
		failure = "The next flight did not safely reuse the parked arrow"
		return
	await get_tree().create_timer(0.20).timeout
	if not stage.projectile_tweens.is_empty() or stage.spare_projectiles.count(arrow) != 1 or app.client.frame.state_version != version:
		failure = "The reused flight did not return cleanly without a rule write"
		return
	stage._launch_projectile(stage._aid_capsule(true), start, landing, 0.08, 0.065, true)
	if stage.flying_projectiles.back() != arrow or not arrow.visible or not arrow.mesh is SphereMesh:
		failure = "The same pooled mesh could not safely switch from an arrow to an aid capsule"
		return
	await get_tree().create_timer(0.20).timeout
	if not stage.projectile_tweens.is_empty() or stage.spare_projectiles.count(arrow) != 1 or app.client.frame.state_version != version:
		failure = "The reused capsule did not return cleanly without a rule write"
		return
	bow_marks["parked_mesh_reused_as_capsule"] = true
	bow_marks["parked_flight_reused"] = true


func _wait_for_battle_models() -> bool:
	var stage = app.board.stage
	var id: String = app.view.battle_view.id
	if await _wait_until(func(): return stage.battle_id == id and not stage.actors.is_empty(), 9000):
		return true
	failure = "The staged models were unavailable after warming the viewport"
	return false


func _check_ado_panel() -> bool:
	var step: Button = app.command_buttons["step"]
	if not await _command("step"):
		return false
	if step != app.command_buttons["step"] or not await _wait_focus("step"):
		failure = "The live Ado panel lost its step control or keyboard focus"
		return false
	if not await _press("flee CONFIRM", false):
		return false
	if not await _wait_focus("cancel") or app.command_buttons.has("step"):
		failure = "Ado's retreat confirmation did not replace the live action panel"
		return false
	if not await _press("cancel") or not await _wait_focus("flee CONFIRM"):
		failure = "Cancelling Ado's retreat did not restore focus"
		return false
	for key in ["settings", "大字", "settings-back"]:
		if not await _press(key):
			return false
	if not app.settings["大字"] or app.warning_footer.custom_minimum_size.y != 79.0:
		failure = "Ado's battle panel did not apply the large-text setting"
		return false
	return true


func _check_ground_projection(phase: String) -> bool:
	var stage = app.board.stage
	var maximum := 0.0
	for pixel: Vector2 in app.board.coordinate_map.values():
		var cached: Vector3 = stage._world(pixel)
		var actual: Vector3 = stage._project_floor(pixel)
		maximum = maxf(maximum, cached.distance_to(actual))
	if maximum > 0.00012 or app.board.coordinate_map.is_empty():
		failure = "Cached projection no longer matched the board camera"
		return false
	side_checks["projection_" + phase] = {"cells": app.board.coordinate_map.size(), "max_error_m": maximum}
	return true


func _side_controls() -> void:
	if app.view.get("phase") != "EXPLORE" or app.view.site != "G" or not app.board._sideways:
		failure = "The side-view check needs the saved fortress contact"
		return
	var member: Dictionary = {}
	var occupied := Vector2i.ZERO
	var other_id := ""
	var free := Vector2i(999, 999)
	var allowed: Array = app.model.map.deploy_cells
	for row in app.view.party:
		if not row.deployed or row.position not in allowed or not row.deployable:
			continue
		if member.is_empty():
			member = row
		else:
			occupied = Vector2i(int(row.position[0]), int(row.position[1]))
			other_id = row.instance_id
			break
	if member.is_empty() or occupied == Vector2i.ZERO:
		failure = "The checkpoint has no paired deployment tokens"
		return
	var id: String = member.instance_id
	var original := Vector2i(int(member.position[0]), int(member.position[1]))
	var stage = app.board.stage
	var opponents: Array = app.model.map.get("enemy_preview", [])
	if opponents.size() != 3 or not app.board.reserve_zone.visible:
		failure = "The contact screen omitted scouting information or the reserve target"
		return
	if not await _wait_until(func(): return stage.actors.has(id), 9000):
		failure = "Selected shield soldier had no deployment model"
		return
	if not _check_ground_projection("contact"):
		return
	var body_point := _deployment_body(id)
	if app.board._deployment_member(body_point) != id:
		failure = "The visible shield soldier could not be selected by its body"
		return
	for cell in allowed:
		var candidate := Vector2i(int(cell[0]), int(cell[1]))
		if candidate != original and app._deployment_target(id, candidate).is_empty():
			free = candidate
			break
	if not app.board.coordinate_map.has(free):
		failure = "No free slot to exercise actual deployment"
		return
	var version: int = app.client.frame.state_version
	await _drag(_board_pixel(body_point), _board_screen(occupied), "swap-positions")
	if not await _wait_ready() or not _check_dropped(id, occupied, version + 1) or not _check_dropped(other_id, original, version + 1):
		return
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(original), "swap-back")
	if not await _wait_ready() or not _check_dropped(id, original, version + 2) or not _check_dropped(other_id, occupied, version + 2):
		return
	await _drag(_board_pixel(_deployment_body(id)), _board_screen(free), "drop-board")
	if not await _wait_ready() or not _check_dropped(id, free, version + 3):
		return
	var reserve: Vector2 = app.get_viewport().get_final_transform() * app.board.reserve_zone.get_global_rect().get_center()
	await _drag(_board_pixel(_deployment_body(id)), reserve, "drop-reserve")
	if not await _wait_ready() or int(app.client.frame.state_version) != version + 4 or stage.actors.has(id):
		failure = "Dropping into reserve did not withdraw one deployed model"
		return
	var entry: Button = app.command_buttons["member-" + id]
	app._action_scroll.ensure_control_visible(entry)
	await get_tree().process_frame
	version = int(app.client.frame.state_version)
	await _drag(_button_point(entry), _board_screen(occupied), "drop-occupied")
	if int(app.client.frame.state_version) != version:
		failure = "A reserve unit was allowed to displace a deployed teammate"
		return
	await _drag(_button_point(entry), _board_screen(original), "drop-roster")
	if not await _wait_ready() or not _check_dropped(id, original, version + 1):
		return
	await _capture("side-deployment")
	if not await _press("deployment-cells"):
		return
	await _capture("side-slot-grid")
	if not await _press_cell("cell-%d-%d" % [original.x, original.y]):
		return
	var preview: Node3D = stage.actors[id].node
	if not await _command("fight"):
		return
	var actual_enemy_cells: Array = []
	for actor in app.view.actors:
		if actor.side == "enemy":
			actual_enemy_cells.append(app.board.cell_index(actor.pos))
	if opponents.map(func(row): return app.board.cell_index(row.position)) != actual_enemy_cells:
		failure = "The public enemy preview did not match actual opening positions"
		return
	if app.board.reserve_zone.visible or app.model.map.has("enemy_preview"):
		failure = "Deployment controls or enemy preview remained after starting combat"
		return
	side_checks["scouted_enemies"] = opponents
	if not stage.actors.has(id) or stage.actors[id].node != preview or stage.deployment_handoffs < 1:
		failure = "Combat did not reuse the deployment model"
		return
	side_checks["reused_models"] = stage.deployment_handoffs
	if not _check_ground_projection("battle"):
		return
	if not await _wait_until(_travelling_foot, 5000):
		failure = "No moving model crossed between two tiles"
		return
	await _capture("side-moving-foot")
	if not await _wait_until(func(): return int(app.view.battle_view.tick) >= 2, 12000):
		failure = "Confirming the fight did not begin automatic advancement"
		return
	await _capture("side-playing")
	_key(KEY_SPACE, true)
	_key(KEY_SPACE, false)
	if not await _check_paused("manual") or not app.command_buttons.has("step") or not app.command_buttons["step"].visible:
		if failure.is_empty():
			failure = "Pausing did not expose single-step control"
		return
	await _capture("side-paused")
	if not await _check_battle_hud(id):
		return
	var settings_file := ConfigFile.new()
	var pace_order: Array[int] = []
	for expected in [2, 0, 1, 2]:
		if not await _press("combat-pace") or app._battle_pace != expected:
			failure = "The pace button failed to cycle through all three choices"
			return
		var loaded := settings_file.load(app.data_dir.path_join("display.cfg"))
		if loaded != OK or settings_file.get_value("presentation", "battle_pace") != expected:
			failure = "The battle pace choice was not persisted"
			return
		pace_order.append(expected)
	side_checks["pace_cycle"] = pace_order
	if not await _press("combat-playback"):
		return
	var fresh_warning := await _wait_until(func(): return app._new_warning and not app._battle_timer.is_stopped(), 10000)
	if not fresh_warning or app._battle_timer.wait_time < 0.55:
		failure = "Fast mode failed to reserve time for a fresh danger warning"
		return
	side_checks["fast_warning_seconds"] = app._battle_timer.wait_time
	await _capture("side-fast-warning")
	var has_events := await _wait_until(func(): return not app.view.battle_view.recent.is_empty(), 8000)
	if not has_events or not is_instance_valid(app._live_battle_log) or app._live_battle_log._entries.is_empty():
		failure = "The live battle log did not refresh with actual events"
		return
	await _capture("side-live-log")
	if not await _finish_automatic_ado("side") or not await _check_paused("victory"):
		return
	await _capture("side-victory")
	if not await _check_finished_report():
		return


func _finish_automatic_ado(prefix: String) -> bool:
	var combat_controls := {}
	for id in ["combat-playback", "combat-pace", "battle-log", "settings"]:
		combat_controls[id] = app.command_buttons[id]
	var restored_panels: Array[String] = []
	var reading_seconds: Dictionary = {}
	for reply in ["memory evidence MG01-W1", "memory retain MG01-W2"]:
		var section: String = reply.get_slice(" ", 2)
		var response := "铜哨缺口把回撤的第二声截断了" if section == "MG01-W1" else "我记得那半声了"
		if not await _wait_until(func(): return app.view.battle_memory.get("id", "") == section, 48000):
			failure = "Automatic battle did not reach " + section
			return false
		if not await _check_paused(section):
			return false
		if app.command_buttons.has("combat-playback") or combat_controls["combat-playback"].is_visible_in_tree():
			failure = "The memory choice left a live combat control visible"
			return false
		if _panel_has(response) or response in app.subtitles.text:
			failure = "The memory reply appeared before the committed choice: " + section
			return false
		await _capture(prefix + "-" + section)
		if not await _command(reply):
			return false
		if not (response in app.subtitles.text) or app._battle_timer.wait_time < 4.4:
			failure = "The committed reply or its reading time was missing: " + section
			return false
		reading_seconds[section] = app._battle_timer.wait_time
		await _capture(prefix + "-" + section + "-reply")
		for id in combat_controls:
			if app.command_buttons.get(id) != combat_controls[id] or not combat_controls[id].is_visible_in_tree() \
					or combat_controls[id].disabled:
				failure = "The memory choice did not restore the active combat controls: " + id
				return false
		restored_panels.append(section)
	side_checks["memory_panel_reuse"] = restored_panels
	side_checks["memory_reply_reading_seconds"] = reading_seconds
	if not await _wait_until(func(): return app.view.get("phase") != "BATTLE", 48000):
		failure = "Automatic battle did not settle"
		return false
	var results: Array = app.view.get("battle_results", [])
	if results.is_empty() or results[-1].result != "VICTORY" or app.ado_sound_counts.get("whistle", 0) != 1:
		failure = "Automatic battle did not produce the expected victory and whistle"
		return false
	return true


func _check_battle_hud(ally_id: String) -> bool:
	var version: int = app.client.frame.state_version
	if not await _press("battle-unit-EN04-STORY-2"):
		return false
	if app.board.battle_focus_id != "EN04-STORY-2" or "甲环卫" not in app._battle_detail.text:
		failure = "Selecting a hostile row did not select the board marker"
		return false
	await _capture("side-unit-target")
	var point := _board_pixel(_deployment_body(ally_id))
	_mouse(point, true)
	_mouse(point, false)
	await get_tree().process_frame
	if app.board.battle_focus_id != ally_id or not app.command_buttons["battle-unit-" + ally_id].button_pressed:
		failure = "Clicking the friendly model did not select its roster row"
		return false
	if not await _press("battle-log"):
		return false
	if not app._battle_log_open or not app.command_buttons.has("combat-playback") or app.client.frame.state_version != version:
		failure = "Opening battle notes affected the playback controls or native save"
		return false
	side_checks["battle_focus_checks"] = ["roster-to-board", "board-to-roster"]
	return true


func _check_live_report_read() -> void:
	var snapshot: Dictionary = app.view.get("battle_view", {})
	if app.view.get("phase") != "BATTLE" or snapshot.get("recent", []).is_empty() \
			or not await _wait_for_battle_models() \
			or not await _wait_until(func(): return not app.board.stage._has_model_work(), 8000):
		failure = "A paused saved battle with actual recent events is required"
		return
	var version: int = app.client.frame.state_version
	if not await _press("battle-log") or not await _check_report_rows(app._live_battle_log, snapshot):
		failure = "The live battle report did not display its stored events"
		return
	await _capture("battle-report-live")
	if not await _press("battle-log") or not app._battle_roster.is_visible_in_tree() \
			or app.client.frame.state_version != version or app._playback_running:
		failure = "Reading the battle report changed the save, playback or roster"


func _check_finished_report(encounter := "BATTLE-MG01", outcome := "VICTORY", actor_text := "阿铎",
		mark := "side-post-report") -> bool:
	var snapshot: Dictionary = app.view.get("battle_view", {})
	if not snapshot.get("finished", false) or snapshot.get("result") != outcome or snapshot.get("encounter") != encounter:
		failure = "The saved result or encounter is missing from the latest battle report"
		return false
	var version: int = app.client.frame.state_version
	if not await _press("battle-log"):
		return false
	var reports: Array = app.actions.get_children().filter(func(control): return control.get_script() == app.CombatLog)
	if not app._battle_log_open or reports.size() != 1 or app.client.frame.state_version != version:
		failure = "The stored timeline or its read-only navigation was incomplete"
		return false
	var log = reports[0]
	if not _report_mentions(log._entries, actor_text) or not _report_mentions(log._entries, "倒地") \
			or not await _check_report_rows(log, snapshot):
		failure = "The stored timeline did not display the actual report rows"
		return false
	side_checks["stored_battle_events"] = snapshot.recent.size()
	await _capture(mark)
	return true


func _report_mentions(entries: Array[Dictionary], text: String) -> bool:
	return entries.any(func(entry: Dictionary) -> bool: return text in entry.detail)


func _check_report_rows(log: Control, snapshot: Dictionary) -> bool:
	await RenderingServer.frame_post_draw
	var entries: Array[Dictionary] = app._combat_log(snapshot)
	if log._entries != entries or entries.is_empty():
		return false
	var font_px := 20 if app.settings["大字"] else 16
	var detail_x: float = log._rows[0].detail.position.x
	var wrapped := 0
	for index in entries.size():
		var row: Dictionary = log._rows[index]
		var tick: Label = row.beat
		var detail: Label = row.detail
		if not row.container.is_visible_in_tree() or detail.text != entries[index].detail \
				or tick.text != "第 %d 拍" % entries[index].tick \
				or detail.get_theme_font_size("font_size") != font_px \
				or not is_equal_approx(detail.position.x, detail_x) or detail.position.x < tick.size.x \
				or not is_equal_approx(tick.position.y, detail.position.y):
			return false
		if detail.get_line_count() > 1:
			wrapped += 1
	side_checks["report_layout"] = {"rows": entries.size(), "font_px": font_px, "wrapped": wrapped}
	return true


func _board_screen(cell: Vector2i) -> Vector2:
	return _board_pixel(app.board.coordinate_map[cell])


func _board_pixel(pixel: Vector2) -> Vector2:
	return app.get_viewport().get_final_transform() * (app.board.get_global_transform_with_canvas() * pixel)


func _deployment_body(id: String) -> Vector2:
	var stage = app.board.stage
	var root: Vector3 = stage.actors[id].node.global_position
	return stage.camera.unproject_position(root + Vector3.UP * 1.08)


func _travelling_foot() -> bool:
	var stage = app.board.stage
	for id in stage.actors:
		var token: Dictionary = stage.actors[id]
		var root: Vector3 = token.node.global_position
		if root.distance_to(token.node.destination) > 0.22 and token.node.motion != null and token.node.motion.is_running():
			var gap: float = stage.foot_pixel(id).distance_to(stage._at(token.row.pos))
			if gap > 9.0:
				side_checks["travel_sample_px_from_destination"] = gap
				return true
	return false


func _hold_drag(from: Vector2, to: Vector2) -> void:
	_mouse_motion(from, Vector2.ZERO, false)
	_mouse(from, true)
	await get_tree().process_frame
	var halfway := from.lerp(to, 0.50)
	_mouse_motion(halfway, halfway - from, true)
	await get_tree().process_frame
	_mouse_motion(to, to - halfway, true)
	await get_tree().process_frame
	await get_tree().process_frame


func _drag(from: Vector2, to: Vector2, mark: String) -> void:
	await _hold_drag(from, to)
	side_checks[mark] = {"screen": str(to), "local_pointer": str(app.board._pointer),
		"cell": str(app.board._drop_cell), "allowed": app.board._drop_allowed}
	await _capture(mark)
	_mouse(to, false)
	await get_tree().process_frame


func _check_dropped(id: String, expected: Vector2i, version: int) -> bool:
	for member in app.view.party:
		if member.instance_id == id and member.deployed and app.board.cell_index(member.position) == expected \
			and int(app.client.frame.state_version) == version:
			side_checks["drag-" + str(version)] = [expected.x, expected.y]
			return true
	failure = "The mouse drop did not commit one deployment at " + str(expected)
	return false


func _check_paused(reason: String) -> bool:
	if not await _wait_ready():
		return false
	var version: int = app.client.frame.state_version
	await get_tree().create_timer(0.90).timeout
	if int(app.client.frame.state_version) != version or app.client.busy or not app._battle_timer.is_stopped():
		failure = "Battle advanced while stopped at " + reason
		return false
	side_checks[reason] = version
	return true


func _wait_until(condition: Callable, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while not condition.call() and Time.get_ticks_msec() < deadline and not app.client.blocked:
		await get_tree().process_frame
	return condition.call()


func _run() -> void:
	if mode == "session-busy":
		await _check_session_busy()
	elif mode == "late-ado-model":
		if await _wait_ready():
			await _check_late_ado_model()
	elif mode == "minimized-contact":
		if await _wait_ready():
			await _check_minimized_contact()
	elif mode == "minimized-battle-audio":
		if await _wait_ready():
			await _check_minimized_battle_audio()
	elif mode == "deployment-interrupt":
		if await _wait_ready():
			await _check_deployment_interrupts()
	elif mode == "book-slot-swap":
		if await _wait_ready():
			await _check_book_slot_swap()
	elif mode == "commission-receipt":
		if await _wait_ready():
			await _check_commission_receipt()
	elif mode not in ["boot", "resume", "chapter", "chapter-resume", "chapter-delivery", "archive-progress", "ado-remembrance", "ado-remembrance-resume", "whistle-commission", "whistle-resume", "ado-early", "ado-late", "sev-report-route", "sev-report-resume", "sev-awakening", "sev-remembrance", "sev-remembrance-resume", "sev-awakened-resume", "mg03-report-route", "mg03-report-resume", "mg04-report-route", "mg04-report-resume", "research-route", "research-resume", "research-early", "finale-route", "finale-defeat", "finale-training", "finale-resume", "ado-sample", "ado-auto-sample", "ado-grip", "side-controls", "deployment-slot", "town-yard", "town-construction", "town-logistics", "consumable-flow", "town-shortcuts", "tutorial-resume", "root-contact-models", "contact-inspection", "field-plan", "field-spoils", "handbook-event", "equipment-flow", "skill-book-flow", "book-market", "book-target", "book-research", "skill-tactics", "live-shields", "rescue-expiry", "live-dialogue", "art-review", "unit-marker-motion", "battle-report-resume", "battle-report-town", "battle-feedback-resume", "gap-resume", "bow-resume", "aid-resume", "crossbow-contact", "crossbow-resume", "mist-contact", "mist-resume", "mercenary-mix", "echo-delay", "sting-resume", "guard-feedback", "enemy-spear-resume", "skeleton-encounter", "bow-flight-lifetime", "projectile-close", "paused-viewport", "projectile-reopen", "projectile-resize", "busy-close", "sidecar-reconnect", "receipt-boot", "startup-help", "fortress-branches", "rescue", "rescue-resume", "spear-resume", "shield-fixtures", "spear-fixtures", "spear", "spear-dual", "full", "full-mouse", "unclaimed", "unobserved", "early", "flee", "contact", "access", "defeat", "repeat-input"]:
		failure = "Unknown smoke scenario: " + mode
	elif mode == "receipt-boot":
		await _check_receipt_boot()
	elif mode == "startup-help":
		await _check_startup_help()
	elif await _wait_ready():
		if measure != null:
			var ready: Button = app.command_buttons.get("opening")
			if mode == "resume":
				ready = app.command_buttons.get("settings")
			elif mode in ["ado-sample", "ado-auto-sample", "mercenary-mix"]:
				ready = app.command_buttons.get("fight")
			if not await measure.ready_probe(app, ready):
				failure = "No visible and operable startup control"
		if mode in ["shield-fixtures", "spear-fixtures"]:
			var checks: Script = load("res://spear_checks.gd" if mode == "spear-fixtures" else "res://shield_checks.gd")
			var runner: Node = checks.new()
			add_child(runner)
			failure = await runner.verify(app)
		elif mode == "ado-grip":
			var runner = preload("res://ado_checks.gd").new()
			add_child(runner)
			failure = await runner.verify(app, capture)
			grip_checks = {"sampled_poses": runner.checked_poses, "max_grip_offset_m": runner.largest_offset,
				"hand_surface_vertices_near_grip": runner.skin_contacts}
		elif mode == "resume":
			if app.view.get("phase") != "RETURNED" or not app.client.pending.is_empty():
				failure = "Completed campaign did not restore"
			else:
				_check_settlement("SAFE_RETURN", true)
		elif mode == "spear-resume":
			await _spear_resume()
		elif mode == "chapter-resume":
			_check_chapter()
		elif mode in ["whistle-commission", "whistle-resume"]:
			await _check_early_whistle(mode == "whistle-resume")
		elif mode == "chapter-delivery":
			await _check_chapter_delivery()
		elif mode == "archive-progress":
			await _check_archive_progress()
		elif mode in ["ado-remembrance", "ado-remembrance-resume"]:
			await _check_ado_remembrance(mode == "ado-remembrance-resume")
		elif mode == "field-spoils":
			await _check_field_spoils()
		elif mode == "handbook-event":
			await _check_handbook_event()
		elif mode == "rescue-resume":
			_check_rescue_resume()
		elif mode == "side-controls":
			await _side_controls()
		elif mode == "art-review":
			await _check_art_review()
		elif mode == "tutorial-resume":
			await _check_tutorial_resume()
		elif mode == "root-contact-models":
			await _check_root_contact_models()
		elif mode == "contact-inspection":
			await _check_contact_inspection()
		elif mode == "field-plan":
			await _check_field_plan()
		elif mode == "equipment-flow":
			await _check_equipment_flow()
		elif mode == "skill-book-flow":
			await _check_skill_book_flow()
		elif mode == "book-market":
			await _check_book_market()
		elif mode == "town-construction":
			await _check_town_construction()
		elif mode == "town-logistics":
			await _check_town_logistics()
		elif mode == "consumable-flow":
			await _check_consumable_flow()
		elif mode == "book-target":
			await _check_book_target()
		elif mode == "book-research":
			await _check_book_research()
		elif mode == "skill-tactics":
			await _check_skill_tactics()
		elif mode == "live-shields":
			await _check_live_shields()
		elif mode == "rescue-expiry":
			await _check_rescue_expiry()
		elif mode == "live-dialogue":
			await _check_live_dialogue()
		elif mode == "town-shortcuts":
			await _check_town_shortcuts()
		elif mode == "town-yard":
			await _check_town_yard()
		elif mode == "deployment-slot":
			await _check_original_slot_drop()
		elif mode == "unit-marker-motion":
			await _check_unit_marker_motion()
		elif mode == "battle-report-resume":
			await _check_finished_report()
		elif mode == "battle-feedback-resume":
			await _check_feedback_resume()
		elif mode == "gap-resume":
			await _check_gap_resume()
		elif mode == "bow-resume":
			await _check_bow_resume()
		elif mode == "aid-resume":
			await _check_aid_resume()
		elif mode in ["crossbow-contact", "crossbow-resume"]:
			await _check_crossbow(mode == "crossbow-resume")
		elif mode in ["mist-contact", "mist-resume"]:
			await _check_mist(mode == "mist-resume")
		elif mode == "mercenary-mix":
			if failure.is_empty():
				await _check_mercenary_mix()
		elif mode == "echo-delay":
			await _check_echo_delay()
		elif mode == "sting-resume":
			await _check_sting_resume()
		elif mode == "guard-feedback":
			await _check_guard_feedback()
		elif mode == "enemy-spear-resume":
			await _check_enemy_spear_resume()
		elif mode == "skeleton-encounter":
			await _check_skeleton_encounter()
		elif mode == "bow-flight-lifetime":
			await _check_bow_flight_lifetime()
		elif mode == "projectile-close":
			await _check_projectile_close()
		elif mode == "paused-viewport":
			await _check_paused_viewport()
		elif mode == "projectile-reopen":
			await _check_projectile_reopen()
		elif mode == "projectile-resize":
			await _check_projectile_resize()
		elif mode == "sidecar-reconnect":
			await _check_sidecar_reconnect()
		elif mode == "busy-close":
			await _check_busy_close()
		elif mode == "battle-report-town":
			if app.view.get("phase") != "TOWN":
				failure = "The archived rescue report must open in town"
			else:
				await _check_finished_report("GR02E", "VICTORY", "甲环卫", "town-report")
		elif mode in ["sev-report-route", "sev-awakening"]:
			await _sev_route()
		elif mode == "sev-remembrance":
			await _sev_remembrance()
		elif mode == "sev-remembrance-resume":
			await _sev_remembrance_resume()
		elif mode == "sev-awakened-resume":
			await _check_sev_awakened()
		elif mode == "sev-report-resume":
			await _check_hunt_report_archive("MG02", "SB-X02", "sev")
		elif mode == "mg03-report-route":
			await _chapter_three_hunt("MG03", "RG04", "SB-X03", 1)
		elif mode == "mg03-report-resume":
			await _check_hunt_report_archive("MG03", "SB-X03", "mg03")
		elif mode == "mg04-report-route":
			await _chapter_three_hunt("MG04", "RG05", "SB-X04", 2)
		elif mode == "mg04-report-resume":
			await _check_hunt_report_archive("MG04", "SB-X04", "mg04")
		elif mode in ["research-route", "research-early"]:
			await _campaign_research_route()
		elif mode == "research-resume":
			await _check_campaign_research()
		elif mode in ["finale-route", "finale-defeat", "finale-training"]:
			await _campaign_finale_route()
		elif mode == "finale-resume":
			await _check_campaign_ending(app.view.get("finale", {}).get("ending", {}).get("id", "FIN-A"))
		elif mode == "ado-sample":
			if failure.is_empty():
				await _ado_sample()
		elif mode == "ado-auto-sample":
			if failure.is_empty():
				await _ado_auto_sample()
		elif mode != "boot" and await _opening():
			if mode in ["full", "full-mouse", "unclaimed", "unobserved", "chapter", "ado-early", "ado-late", "fortress-branches", "rescue"] or spear_count > 0:
				await _full()
				if mode == "rescue" and failure.is_empty():
					await _chapter_flow()
					if failure.is_empty():
						await _rescue_route()
				if mode in ["ado-early", "ado-late", "fortress-branches"] and failure.is_empty():
					await _chapter_flow(mode != "ado-late")
					if failure.is_empty() and _quiet_ado():
						for key in ["settings", "静音", "低动态", "settings-back"]:
							if not await _press(key):
								break
					if failure.is_empty():
						await _ado_route()
				if mode == "chapter" and failure.is_empty():
					await _chapter_flow()
					var evidence: Dictionary = app.board.stage.audit
					var gray_oak_props := ["B_SUPPORT", "C", "D", "battle-wall", "battle-fence", "battle-root"]
					if app.board.show_models and (
						evidence.mimic_peak != 2 or evidence.mimic_releases < 1
						or evidence.mimic_downs != 3 or not evidence.field_props.has_all(gray_oak_props)
					):
						failure = "Gray Oak battlefield or landmark placement was incomplete"
				if spear_count > 0 and app.board.show_models and app.board.show_spear and (app.board.stage.audit.spear_peak != spear_count or app.board.stage.audit.spear_hits < 2):
					failure = "The tutorial did not render the recruited spear actors and real hits"
			elif mode == "early":
				if await _command("return CONFIRM"):
					_check_settlement("SAFE_RETURN", false)
			elif mode == "flee":
				if await _commands(["move A", "fight", "flee CONFIRM"]):
					_check_settlement("COMBAT_RETREAT", false)
			elif mode == "contact":
				await _contact()
			elif mode == "access":
				await _accessibility()
			elif mode == "defeat":
				await _defeat()
			elif mode == "repeat-input":
				await _repeat_input()
	var result := {"scenario": mode, "passed": failure.is_empty(), "failure": failure, "steps": steps,
		"state_digest": app.client.frame.get("state_digest"), "domain_sequence": app.client.frame.get("domain_sequence"),
		"files": app.client.frame.get("files"), "warnings_played": app.sound_count, "elapsed_ms": Time.get_ticks_msec() - began}
	result["shield_visuals"] = app.board.stage.audit
	result["sidecar_reads"] = {"inline": app.client.views_in_receipts, "snapshots": app.client.snapshot_requests,
		"battle_boards_reused": app.client.battle_boards_reused}
	result["ado_audio"] = app.ado_sound_counts
	result["ado_modes"] = {"muted": app.settings["静音"], "reduced": app.settings["低动态"]}
	if not fortress_frames.is_empty():
		result["fortress_frames"] = fortress_frames
	if not grip_checks.is_empty():
		result["grip_checks"] = grip_checks
	if not side_checks.is_empty():
		result["side_controls"] = side_checks
	if map_route_check:
		result["map_sites_clicked"] = map_steps
	if not feedback_frames.is_empty():
		result["combat_feedback"] = feedback_frames
	if not feedback_marks.is_empty():
		result["feedback_checks"] = feedback_marks
	if not melee_marks.is_empty():
		result["melee_checks"] = melee_marks
	if not bow_marks.is_empty():
		result["bow_checks"] = bow_marks
	if not aid_marks.is_empty():
		result["aid_checks"] = aid_marks
	if not crossbow_marks.is_empty():
		result["crossbow_checks"] = crossbow_marks
	if not mist_marks.is_empty():
		result["mist_checks"] = mist_marks
	if not mercenary_checks.is_empty():
		result["mercenary_checks"] = mercenary_checks
	if not echo_checks.is_empty():
		result["echo_checks"] = echo_checks
	if not sting_checks.is_empty():
		result["sting_checks"] = sting_checks
	if not guard_checks.is_empty():
		result["guard_checks"] = guard_checks
	if not paused_viewport_checks.is_empty():
		result["paused_viewport_checks"] = paused_viewport_checks
	if not enemy_spear_checks.is_empty():
		result["enemy_spear_checks"] = enemy_spear_checks
	if not skeleton_checks.is_empty():
		result["skeleton_checks"] = skeleton_checks
	if measure != null:
		result["frame_intervals_usec"] = measure.frames
		if not measure.render_frames.is_empty():
			result["render_profile"] = {"columns": ["frame_ms", "process_ms", "board_cpu_ms",
				"board_gpu_ms", "board_draw_calls", "board_primitives"], "scenes": measure.render_frames}
			result["frame_transitions"] = {
				"columns": ["frame_usec", "previous_draw", "current_version", "current_tree_usec", "tree_started_usec"],
				"draw_columns": ["version", "memory", "tree_to_draw_usec", "draw_usec"],
				"scenes": measure.transition_frames}
			result["receipt_timings"] = app.client.receipt_timings
			result["contact_hint_timing"] = app.client.contact_hint_timing
			result["panel_timings"] = app.panel_timings
			result["contact_timings"] = app.board.stage.contact_timings
			result["field_art_timings"] = app.board.field_art_timings
			result["asset_load_timings"] = app.board.stage.asset_load_timings
			result["model_dispatch_timings"] = app.board.stage.model_dispatch_timings
			result["actor_attachment_timings"] = app.board.stage.actor_attachment_timings
	var report := FileAccess.open(app.data_dir.path_join(app.case_name + "." + mode + ".json"), FileAccess.WRITE)
	if report != null:
		report.store_string(JSON.stringify(result, "  "))
		report.close()
	print("P06 ", mode, " ", failure if not failure.is_empty() else "PASS", " / ", steps.size(), " commits")
	if mode == "projectile-close" and failure.is_empty():
		await get_tree().create_timer(12.0).timeout
		push_error("No final OS close request received during the close test")
		get_tree().quit(2)
		return
	get_tree().quit(0 if failure.is_empty() else 1)


func _sample_scene(name: String) -> void:
	await get_tree().create_timer(0.45).timeout
	measure.begin(name)
	await measure.wait_samples(315)
	measure.finish()


func _spear_resume() -> void:
	var stage = app.board.stage
	for token in stage.actors.values():
		var id: String = token.row.get("spear_pending", {}).get("id", "")
		if id.is_empty():
			continue
		if token.node.cast_id != id or token.node.player.current_animation != "M01_Tripo_02_LaneHold":
			failure = "The saved spear lock did not resume into hold"
			return
		if stage.audit.spear_windups != 0 or not await _command("step"):
			failure = "The saved spear windup was replayed"
			return
		if stage.audit.spear_releases != 1 or stage.audit.spear_hits != 1:
			failure = "Resumed cast did not produce its authoritative release and hit"
		return
	failure = "No saved spear windup to restore"


func _repeat_input() -> void:
	if not await _commands(["move A", "fight"]):
		return
	await get_tree().process_frame
	if not _has_focus("combat-playback"):
		failure = "Starting combat did not focus the playback control"
		return
	_key(KEY_TAB, true)
	_key(KEY_TAB, false)
	if not await _wait_focus("step"):
		failure = "The single-step button was unreachable after pausing"
		return
	var version := int(app.client.frame["state_version"])
	_key(KEY_ENTER, true)
	for i in range(6):
		await get_tree().process_frame
		_key(KEY_ENTER, true, true)
	_key(KEY_ENTER, false)
	await get_tree().process_frame
	if not await _wait_ready():
		return
	if int(app.client.frame["state_version"]) != version + 1:
		failure = "Holding Enter did not submit exactly one beat"
		return
	mouse = true
	if not await _command("step"):
		return
	var frame: Dictionary = app.client.frame
	var point := _button_point(app.command_buttons["step"])
	_mouse(point, true, true)
	_mouse(point, false)
	await get_tree().process_frame
	if not await _wait_ready():
		return
	if app.client.frame["state_version"] != frame["state_version"] or app.client.frame["files"] != frame["files"]:
		failure = "The second click advanced another beat after the first receipt"
		return
	await _command("step")


func _contact() -> void:
	if not await _commands(["move A", "retreat"]):
		return
	for key in app.command_buttons.keys():
		if key.begins_with("walkto "):
			if await _commands([key, "interact I", "return CONFIRM"]) and app.view.get("complete"):
				failure = "Avoiding a fight completed the investigation"
			return
	failure = "Cannot return to the entrance from the contact boundary"


func _accessibility() -> void:
	if not await _commands(["move A", "fight", "step", "step", "step"]):
		return
	var digest: String = app.client.frame["state_digest"]
	var files: Dictionary = app.client.frame["files"].duplicate()
	if not await _press("settings") or not await _press("volume") or not await _press("静音") or not await _press("大字") or not await _press("低动态") or not await _press("settings-back"):
		return
	if not app.warning.visible or app.audio.playing or not app.settings["大字"] or app.volume != 75 or app.client.frame["state_digest"] != digest or app.client.frame["files"] != files:
		failure = "Accessibility settings changed the authority or hid the warning"
	await _capture("accessible-warning")


func _defeat() -> void:
	if not await _command("move A"):
		return
	var solo_id := "INIT-S02-A" if melee_check else "INIT-S03-B"
	for member in app.view["party"].duplicate():
		var id: String = member["instance_id"]
		if member["deployed"] and id != solo_id:
			if not await _press("member-" + id) or not await _command("deploy " + id + " off"):
				return
	for battle in ["A", "G"]:
		if not await _command("fight"):
			return
		var advanced := 0
		while app.view.get("phase") == "BATTLE" and advanced < 150:
			if not await _command("step"):
				return
			advanced += 1
			if (melee_check or bow_check) and app.view.get("phase") == "BATTLE":
				await get_tree().create_timer(0.12).timeout
		var settlement: Variant = app.view.get("settlement")
		if settlement is Dictionary and settlement.get("result") in ["DEFEAT", "TOTAL_DEFEAT"]:
			_check_settlement(settlement["result"], false)
			if (melee_check or bow_check) and failure.is_empty():
				var stage = app.board.stage
				var pawn: Variant = stage.actors.get(solo_id, {}).get("node")
				if pawn == null or not await _wait_until(func() -> bool:
						return is_instance_valid(pawn) and pawn.fallen and pawn.player.current_animation_position > 1.40, 1750):
					failure = "The real defeat did not hold the model's down pose"
					return
				var hit := "MeleeHit" if melee_check else "BowHitFront"
				var down := "MeleeDown" if melee_check else "BowDown"
				if int(stage.audit.clips.get(hit, 0)) == 0 or int(stage.audit.clips.get(down, 0)) != 1:
					failure = "The real defeat did not distinguish surviving hits and knockdown"
					return
				(melee_marks if melee_check else bow_marks)["native_down"] = true
				await _capture("melee-down" if melee_check else "bow-down")
			return
		if battle == "A" and not await _commands(["move B_MATERIAL", "move C", "move D", "move G"]):
			return
	failure = "The one-member formation did not produce a defeat"
func _check_field_plan() -> void:
	var offer: Button = app.command_buttons.get("tutorial plan PL01")
	if app.view.get("site") != "A" or offer == null or offer.text.contains("PL01") \
			or not await _command("tutorial plan PL01") or not _panel_has("已登记「") \
			or not _panel_has("战前方案 · 已采用 0/3") or not app.notice.text.is_empty():
		failure = "The cleared road did not offer a named plan and a readable receipt"
		return
	if not await _command("move B_SUPPORT") or app.notice.text != "已到达护运站。" \
			or not await _command("tutorial support INIT-S02-A") \
			or not _panel_has("近战兵 A获得一次 12 点战前护盾") or not app.notice.text.is_empty():
		failure = "The field support receipt did not identify the actual recipient and effect"
		return
	await _capture("scouting-support-receipt")
	if not await _commands(["move A", "move B_MATERIAL", "tutorial materials"]) \
			or not _panel_has("已领取材料 · 安全归城后入库") or not app.notice.text.is_empty():
		failure = "The materials receipt did not present the collected choice"
		return
	if not await _commands(["move C", "move D", "tutorial observe"]) or app.notice.text != "远眺记录已保存。":
		failure = "The saved observation did not present a readable confirmation"
		return
	if not await _command("move G") or not app.notice.text.begins_with("接敌边界 · 根口") \
			or not app.subtitles.text.contains("盾兵 A") or "INIT-" in app.subtitles.text:
		failure = "The root contact exposed raw commands or an internal speaker ID"
		return
	if not await _command("plan PL01") or app.view.equipped_plans != ["PL01"] \
			or not _panel_has("战前方案 · 已采用 1/3") or not app.command_buttons.has("plan clear"):
		failure = "The accepted plan could not be applied directly at contact"
		return
	await _capture("scouting-plan-applied")
	if not await _command("fight") or app.view.battle_view.encounter != "TUT01-ROOT" \
			or int(app.view.battle_view.tick) != 0 or app.command_buttons.has("plan clear"):
		failure = "The root battle did not start after the field plan was applied"
		return
	side_checks["field_plan"] = "PL01"


func _check_equipment_flow() -> void:
	if app.view.get("phase") == "TOWN":
		await _check_equipment_replacement()
		return
	var first := "INIT-S03-A"
	var second := "INIT-S03-B"
	var item := "EQ-000001"
	var wear := "equip " + first + " " + item
	if not await _commands(["move G", "tutorial cache EF03"]) or not _panel_has("已领取「精致的投射弦架」") \
			or not await _press("field-gear") or not await _press("gear-member-" + first):
		failure = "Claimed root loot was not accessible from the field inventory"
		return
	var version: int = app.client.frame.state_version
	if not await _press(wear, false) or not _panel_has("槽位 · 武器") or not _panel_has("物攻 +2") \
			or not _panel_has("汲生"):
		failure = "The weapon confirmation omitted the actual slot, effect or stat change"
		return
	await _capture("field-gear-confirm")
	if not await _press("cancel") or int(app.client.frame.state_version) != version or not await _command(wear) \
			or not _panel_has("武器 · 精致的投射弦架"):
		failure = "Cancelling or equipping from the field inventory failed"
		return
	if not await _commands(["move X", "return CONFIRM", "town"]) or app.view.get("complete", false) \
			or not await _press("member-" + first) or not _panel_has("武器 · 精致的投射弦架"):
		failure = "The incomplete scouting return did not preserve the worn weapon"
		return
	var remove := "unequip " + first + " weapon"
	version = app.client.frame.state_version
	if not await _press(remove, false) or not _panel_has("放回仓库") or not _panel_has("物攻 -2") \
			or not _panel_has("卸下词条 · 汲生"):
		failure = "The removal dialog did not describe the warehouse and stat change"
		return
	await _capture("town-gear-remove")
	if not await _press("confirm") or int(app.client.frame.state_version) != version + 1:
		failure = "Removing the weapon did not commit exactly once"
		return
	steps.append({"command": remove, "version": version + 1, "digest": app.client.frame.state_digest})
	if not await _press("member-" + second) or not await _command("equip " + second + " " + item) \
			or not _panel_has("武器 · 精致的投射弦架"):
		failure = "The weapon could not be moved to a second archer before chapter delivery"
		return
	side_checks["field_equipment"] = {"item": item, "field_owner": first, "town_owner": second}
	await _capture("town-gear-equipped")


func _check_equipment_replacement() -> void:
	var owner := "INIT-S03-B"
	var gear: Dictionary = app.view.equipment
	var old: Dictionary = gear.worn[owner].front()
	var replacement: Dictionary = gear.inventory.front()
	var command: String = "equip " + owner + " " + replacement.id
	if not await _press("member-" + owner) or not await _press(command, false) \
			or not _panel_has("放回仓库 · " + old.name) or not _panel_has("物攻 -1") \
			or not _panel_has("卸下词条 · 汲生"):
		failure = "The slot replacement quote did not match the two actual weapons"
		return
	await _capture("town-gear-swap")
	var version: int = app.client.frame.state_version
	if not await _press("confirm") or int(app.client.frame.state_version) != version + 1 \
			or app.view.equipment.worn[owner].front().id != replacement.id \
			or not app.view.equipment.inventory.any(func(item: Dictionary) -> bool: return item.id == old.id):
		failure = "The replacement did not return the original instance to the warehouse"
		return
	steps.append({"command": command, "version": version + 1, "digest": app.client.frame.state_digest})
	side_checks["equipment_swap"] = {"old": old.id, "new": replacement.id, "owner": owner}


func _check_book_research() -> void:
	var accept := "book task accept SB-T01"
	var reward := "book choice SB-T01 SB-D03 CONFIRM"
	if app.view.get("phase") == "TOWN":
		if not await _press("town-skills") or not await _press("book-research") \
				or not _panel_has("近战研习") or not _panel_has("远击研习") or not _panel_has("战地照护") \
				or not await _command(accept):
			failure = "The unlocked book room omitted the research choices"
			return
		var enrolled: Dictionary = app.view.book_research[0]
		if not enrolled.accepted or enrolled.claimable or int(enrolled.banked) != 0 \
				or int(enrolled.pending) != 0 or not _panel_has("已入账 · 0/3 场") \
				or app.command_buttons.has(accept) or app.command_buttons.has(reward):
			failure = "Accepting the research improperly counted earlier battles or enabled an immediate reward"
			return
		await _capture("research-accepted")
		return
	if app.view.get("phase") == "BATTLE":
		if not await _command("step") or app.view.settlement.result != "DEFEAT" \
				or not _panel_has("近战研习 · 本趟 1 场未入账") or _panel_has("可在暮汀「技能书 → 研习委托」领取奖励"):
			failure = "The lost research was counted in the defeat settlement"
			return
		await _capture("research-lost")
		return
	if app.view.book_research.is_empty() or int(app.view.book_research[0].pending) != 3 \
			or int(app.view.book_research[0].banked) != 0 or not _panel_has("近战研习 · 3 场待归城入账"):
		failure = "The actual expedition's qualifying victories were unavailable or already banked"
		return
	await _capture("research-carried")
	if not await _command("return CONFIRM") or not _panel_has("近战研习 · 本趟入账 3 场") \
			or not _panel_has("可在暮汀「技能书 → 研习委托」领取奖励"):
		failure = "With three actual victories, safe return did not unlock the expected reward"
		return
	await _capture("research-settled")
	if not await _command("town") or not await _press("town-skills") or not await _press("book-research"):
		return
	var day := int(app.view.day)
	var stock := int(app.view.get("skill_books", {}).get("stock", {}).get("SB-D03", 0))
	var copper := int(app.view.town_roster.copper)
	if not _panel_has("已达成 · 自选奖励 1 本") or not await _press(reward, false) \
			or not _panel_has("1 本「横扫」放入暮汀书库"):
		failure = "The research reward preview did not show the unlocked selected book"
		return
	await _capture("research-choice")
	if not await _press("cancel") or not await _command(reward):
		return
	if not _panel_has("已领奖 · 横扫") or app.command_buttons.has(reward) \
			or int(app.view.skill_books.stock["SB-D03"]) != stock + 1 \
			or int(app.view.day) != day or int(app.view.town_roster.copper) != copper:
		failure = "Claiming the single research reward changed its actual cost or left it redeemable"
		return
	await _capture("research-rewarded")


func _check_book_target() -> void:
	if app.view.get("phase") == "BATTLE":
		if not await _command("step") or app.view.settlement.result != "DEFEAT" \
				or not _panel_has("定向「重劈」 · 2/2 → 2/2") \
				or not _panel_has("目标书未带回，定向进度保留"):
			failure = "Losing the target book did not preserve the earned guarantee"
			return
		await _capture("target-lost")
		return
	var rewards: Dictionary = app.view.get("field_book_rewards", {})
	if rewards.get("target", {}).get("name") != "重劈":
		failure = "The expedition did not show its saved ordinary book target"
		return
	if int(rewards.target.progress) == 1:
		if not await _command("return CONFIRM") or not _panel_has("定向「重劈」 · 1/2 → 2/2") \
				or not _panel_has("下趟首次领取普通书将替换为目标书"):
			failure = "The second non-target book did not fill the meter"
			return
		await _capture("target-filled")
		if not await _command("town") or not await _press("town-expedition"):
			return
		while int(app.view.supply) < int(app.view.departure_cost):
			if not await _command("buy_supply 1"):
				return
		var version := int(app.client.frame.state_version)
		if not await _press("depart CONFIRM", false) or not _panel_has("本趟普通技能书额度 · 1 本") \
				or not _panel_has("出发时锁定技能书定向「重劈」 · 2/2") \
				or not _panel_has("本趟首次领取的普通书将替换为目标书"):
			failure = "Departure omitted the actual cap or the completed guarantee"
			return
		await _capture("target-departure")
		if not await _press("confirm") or int(app.client.frame.state_version) != version + 1 \
				or not app.view.field_book_rewards.target.guaranteed:
			failure = "The completed book guarantee was not frozen for the ordinary trip"
			return
		steps.append({"command": "depart CONFIRM", "version": version + 1, "digest": app.client.frame.state_digest})
		return
	var book: Dictionary = app.view.handbook_event.get("book", {})
	var button: Button = app.command_buttons.get("choose BOOK")
	if book.get("id") != "SB-D02" or not rewards.target.guaranteed or button == null \
			or "领取定向手册" not in button.text or not _panel_has("本趟已领 0/1") \
			or app.command_buttons.has("choose FORTUNE"):
		failure = "The frozen targeted handbook did not replace the ordinary display at its source"
		return
	await _capture("target-offer")
	if not await _command("choose BOOK") or not _panel_has("目标书已在行囊") \
			or not _panel_has("本趟已领 1/1") or app.view.field_book_rewards.target.guaranteed:
		failure = "Claiming the replacement consumed the wrong number of rewards"
		return
	var route_file: String = app.data_dir.path_join(app.case_name + ".return-route.json")
	var route: Variant = JSON.parse_string(FileAccess.get_file_as_string(route_file))
	if not route is Array:
		failure = "The comparison route to the safe return point was missing"
		return
	if not await _commands(route) or not await _command("return CONFIRM"):
		return
	if not _panel_has("定向「重劈」 · 2/2 → 0/2") or not _panel_has("目标书已入库，定向进度清零"):
		failure = "The target book did not reset progress on the real settlement"
		return
	await _capture("target-banked")


func _pouch_row(id: String) -> Dictionary:
	for item: Dictionary in app.view.get("consumables", {}).get("items", []):
		if item.id == id:
			return item
	return {}


func _check_consumable_flow() -> void:
	var material: Dictionary = app.view.get("material_goal", {})
	var site := str(app.view.get("site", ""))
	var event: Dictionary = app.view.get("handbook_event", {})
	var offers: Array = event.get("choices", []).filter(func(choice): return choice.get("fixed", {}).get("herb", 0) == 2)
	if material.get("site") != site or offers.size() != 1 or material.get("picked", false):
		failure = "Consumable review needs a real unclaimed herb commission on site"
		return
	await _capture("herb-site")
	if not await _command("choose " + str(offers[0].id)):
		return
	if not app.view.material_goal.picked or not _panel_has("待归城入库"):
		failure = "Claimed herbs were not represented as carried materials"
		return
	if not await _commands(["move V", "move B1", "move U", "move I", "return CONFIRM"]):
		return
	if int(app.view.settlement.materials.get("herb", 0)) != 2 or not await _command("town") \
			or not await _press("town-items"):
		failure = "Safe return did not bank the material commission"
		return
	var recipes: Array = app.view.consumables.items.filter(func(item): return item.has("recipe"))
	if recipes.map(func(item): return item.id) != ["CO01", "CO03", "CO04", "CO05", "CO06", "CO10"]:
		failure = "The completed workshop did not expose the six level-one recipes"
		return
	if not await _command("supply commission off") or not await _press("pouch-item-CO01"):
		return
	var day := int(app.view.day)
	var copper := int(app.view.town_roster.copper)
	var version := int(app.client.frame.state_version)
	if not await _press("craft CO01", false) or not _panel_has("2 铜、1 木纤、2 草药") \
			or not _panel_has("携行占用 0/4 → 1/4"):
		failure = "Crafting did not preview the actual cost and carrying slot"
		return
	await _capture("craft-ointment")
	if not await _press("cancel") or int(app.client.frame.state_version) != version \
			or int(app.view.town_roster.copper) != copper:
		failure = "Canceling the recipe mutated the save or bank"
		return
	if not await _command("craft CO01"):
		return
	if int(app.view.town_roster.copper) != copper - 2 or int(app.view.day) != day or not _panel_has("当前无人可有效治疗"):
		failure = "Crafting changed the day or allowed waste on a full-health roster"
		return
	if not await _command("stash CO01") or int(_pouch_row("CO01").stored) != 1 or int(app.view.consumables.slots) != 0 \
			or not await _command("take CO01") or int(_pouch_row("CO01").carried) != 1:
		failure = "Stored or reissued consumable did not move exactly one real item"
		return
	if not await _press("pouch-list") or not await _press("pouch-item-CO03") or not await _command("craft CO03") \
			or not await _press("town-expedition") or not await _commands(["depart CONFIRM", "move U", "move B1"]):
		return
	var guard := "INIT-S01-A"
	if not await _press("field-items") or not await _press("pouch-item-CO03") or not await _press("pouch-target-" + guard) \
			or not await _command("use CO03 " + guard):
		return
	if int(app.view.consumables.slots) != 2 or int(app.view.consumables.reserved) != 1:
		failure = "The used guard preparation did not reserve its former carrying slot"
		return
	await _capture("preparation-occupancy")
	if not await _press("field-items") or not await _command("fight"):
		return
	var actors: Array = app.view.battle_view.actors
	if not actors.any(func(actor): return actor.id == guard and int(actor.get("private_shield", 0)) >= 8) \
			or app.command_buttons.has("field-items") or app.command_buttons.keys().any(func(key): return str(key).begins_with("use ")):
		failure = "The preparation did not apply to the selected pawn, or consumables were usable during battle"
		return
	for tick in range(60):
		if app.view.get("phase") != "BATTLE":
			break
		if not await _command("step"):
			return
	var battle: Variant = app.view.get("battle_view")
	if app.view.get("phase") != "EXPLORE" or not battle is Dictionary or battle.result != "VICTORY":
		failure = "The healing check did not reach a real post-battle injury"
		return
	if not await _press("field-items") or not await _press("pouch-item-CO01"):
		return
	var options: Array = _pouch_row("CO01").targets
	if options.is_empty():
		failure = "The battle left no valid treatment target"
		return
	var target: Dictionary = options[0]
	var medicine := "use CO01 " + str(target.id)
	if not await _press("pouch-target-" + str(target.id)) or not await _press(medicine, false) \
			or not _panel_has("回复 %d" % int(target.heals)):
		failure = "The treatment confirmation did not show its actual recoverable health"
		return
	await _capture("field-heal-preview")
	if not await _press("cancel") or not await _command(medicine):
		return
	var treated: Array = app.view.party.filter(func(m): return m.instance_id == target.id)
	if treated.size() != 1 or int(treated[0].hp) != int(target.hp) + int(target.heals) \
			or int(app.view.consumables.slots) != 1 or int(app.view.consumables.reserved) != 1:
		failure = "Treatment did not match the preview or release exactly one carrying slot"
		return
	if not await _press("field-items") or not await _commands(["move U", "move I", "return CONFIRM"]):
		return
	side_checks["consumables"] = {"herbs_banked": 2, "level_one_recipes": recipes.size(), "shield_recipient": guard,
		"heal_recipient": target.id, "actual_heal": int(target.heals), "heal_overflow": int(target.overflow),
		"battle_ticks": int(battle.tick)}


func _check_town_logistics() -> void:
	var trainee := "INIT-S01-C"
	var first := "INIT-S01-A"
	var original := "INIT-S02-A"
	var replacement := "INIT-S03-B"
	if app.view.get("phase") != "TOWN" or not await _press("town-logistics"):
		failure = "Logistics needs a prepared town save"
		return
	var before: Dictionary = app.view.town_services.funds.duplicate()
	var day := int(app.view.day)
	var service_id: String = app.view.town_services.order_id
	if not await _command("service training %s:1 %s CONFIRM" % [trainee, service_id]):
		return
	if not app.view.town_services.training.pending.any(func(m): return m.id == trainee) or int(app.view.day) != day \
			or int(app.view.town_services.funds.copper) != int(before.copper) - 6 \
			or int(app.view.town_services.funds.supply) != int(before.supply) - 1:
		failure = "Training payment did not queue the expected member without advancing the day"
		return
	await _capture("training-queued")
	if not await _press("town-roster") or app.command_buttons.has("squad " + trainee + " on") \
			or not await _press("town-logistics"):
		failure = "The training member was available for the travelling roster"
		return
	if not await _press("outfit-unit-" + first) or not await _press("outfit-unit-" + original):
		return
	var purchase := "outfit buy defense %s,%s %s CONFIRM" % [first, original, app.view.town_services.order_id]
	var version := int(app.client.frame.state_version)
	if not await _press(purchase, false) or not _panel_has("8 铜、1 公共结晶、1 补给") \
			or not _panel_has("附加费 4 铜、1 补给") \
			or app.actions.get_children().filter(func(node): return node is Button and node.text == "设置").size() != 1:
		failure = "The second service confirmation omitted the shared surcharge"
		return
	await _capture("outfit-second-service")
	if not await _press("cancel") or int(app.client.frame.state_version) != version:
		failure = "Cancelling the quote changed the save"
		return
	if not await _command(purchase):
		return
	var paid: Dictionary = app.view.town_services.funds.duplicate()
	if int(paid.copper) != int(before.copper) - 14 or int(paid.crystal) != int(before.crystal) - 1 \
			or int(paid.supply) != int(before.supply) - 2 or int(app.view.town_services.used) != 2:
		failure = "Completed orders did not debit both services and their surcharge exactly once"
		return
	if not await _press("outfit-edit") or not await _press("outfit-unit-" + original) \
			or not await _press("outfit-unit-" + replacement) \
			or not await _command("outfit targets %s,%s" % [first, replacement]):
		return
	if app.view.town_services.funds != paid or not await _command("rest CONFIRM"):
		failure = "Free retargeting debited the service again, or the training settlement failed"
		return
	var ready: Dictionary = app.view.town_services
	if not ready.defense.ready or ready.defense.targets.map(func(m): return m.id) != [first, replacement] \
			or not ready.training.settled.any(func(m): return m.id == trainee and int(m.xp) == 1) \
			or int(app.view.day) != day + 1 or int(ready.used) != 0:
		failure = "Rest failed to settle training, refresh service capacity or retain ready defense"
		return
	await _capture("training-settled")
	if not await _press("town-expedition") or not await _press("depart CONFIRM", false) \
			or not _panel_has("防御整备") or not _panel_has("物防、魔防各 +6"):
		failure = "The departure preview omitted the selected defense service"
		return
	if not await _press("cancel") or not await _commands(["depart CONFIRM", "move U", "move B1", "fight"]):
		return
	var granted: Array = app.view.actors.filter(func(m): return int(m.get("town_defense_bonus", 0)) == 6)
	var ids: Array = granted.map(func(m): return m.id)
	if ids.size() != 2 or first not in ids or replacement not in ids \
			or not await _press("battle-unit-" + replacement) or "物防、魔防各 +6" not in app._battle_detail.text:
		failure = "The battle receipt or unit detail granted defense to the wrong targets"
		return
	await _capture("outfit-battle")
	if not await _commands(["flee CONFIRM", "town"]):
		return
	if app.view.town_services.defense.ready:
		failure = "The used outfitting service did not expire after settlement"
		return
	side_checks["logistics"] = {"trained": trainee, "experience": 1, "second_service": [8, 1, 1],
		"battle_targets": ids, "defense_each": 6, "expired_on_return": true}


func _construction_project(key: String) -> Dictionary:
	for project: Dictionary in app.view.construction.projects:
		if project.key == key:
			return project
	return {}


func _check_town_construction() -> void:
	if app.view.get("phase") != "TOWN" or not await _press("town-construction"):
		failure = "Construction needs a commissioned town save"
		return
	var day := int(app.view.day)
	var funds: Dictionary = app.view.construction.funds.duplicate()
	if not app.view.get("complete", false):
		if not _construction_project("armory").quote.blocker.begins_with("交存首章") \
				or not await _press("construction-project-hospital"):
			failure = "The first chapter did not expose the hospital while locking the armory"
			return
		await _check_first_construction(funds, day)
		return
	if not await _press("construction-project-lamp_store"):
		return
	var lamp := _construction_project("lamp_store")
	if lamp.has("order"):
		if int(lamp.level) != 0 or int(lamp.order.progress) != 1 or int(app.view.preparation.medical_cap) != 2:
			failure = "Reopened construction advanced or applied its effect before the next settlement"
			return
		if not await _command("rest CONFIRM"):
			return
		lamp = _construction_project("lamp_store")
		if lamp.has("order") or int(lamp.level) != 1 or int(app.view.preparation.medical_cap) != 3 \
				or app.view.construction.funds != funds or int(app.view.day) != day + 1:
			failure = "The next settlement did not finish the observation station and enable the third medical supply"
			return
		side_checks["completed_construction"] = lamp
		await _capture("construction-complete")
	else:
		if _construction_project("armory").quote.blocker != "" or int(app.view.preparation.medical_cap) != 2:
			failure = "First chapter archive did not unlock the armory or the save had an unexpected medical capacity"
			return
		var order_id: String = app.view.construction.order_id
		if not await _command("facility build lamp_store 1 %s CONFIRM" % order_id) or not await _command("rest CONFIRM"):
			return
		lamp = _construction_project("lamp_store")
		if int(lamp.level) != 0 or int(lamp.order.progress) != 1 or int(app.view.preparation.medical_cap) != 2 \
				or int(app.view.day) != day + 1:
			failure = "The first settlement did not leave the observation station halfway complete"
			return
		side_checks["construction_in_progress"] = lamp.order
		await _capture("construction-progress")


func _check_first_construction(funds: Dictionary, day: int) -> void:
	var order_id: String = app.view.construction.order_id
	var build := "facility build hospital 1 %s CONFIRM" % order_id
	var version := int(app.client.frame.state_version)
	if not await _press(build, false) or not _panel_has("支付 20 铜和 4 公共结晶") or not _panel_has("2 次后续行动"):
		failure = "The hospital quote omitted exact cost or settlement duration"
		return
	await _capture("construction-quote")
	if not await _press("cancel") or int(app.client.frame.state_version) != version or app.view.construction.funds != funds:
		failure = "Dismissing the building quote changed the save"
		return
	if not await _command(build):
		return
	var hospital := _construction_project("hospital")
	if int(app.view.day) != day or int(hospital.order.progress) != 0 or int(hospital.level) != 0 \
			or int(app.view.construction.funds.copper) != int(funds.copper) - 20 \
			or int(app.view.construction.funds.crystal) != int(funds.crystal) - 4 \
			or int(app.view.construction.occupied) != 1 or _construction_project("lamp_store").quote.blocker != "施工位已占用":
		failure = "Payment advanced the day or the shared construction site remained available"
		return
	if not await _command("facility cancel %s CONFIRM" % order_id):
		return
	if int(app.view.day) != day or app.view.construction.funds != funds or int(app.view.construction.occupied) != 0:
		failure = "Zero-progress cancellation did not refund the full cost and release the site"
		return
	var next_id: String = app.view.construction.order_id
	if next_id == order_id or not await _command("facility build hospital 1 %s CONFIRM" % next_id) \
			or not await _command("rest CONFIRM"):
		failure = "The cancelled order ID was reused or the replacement did not advance"
		return
	var cancel := "facility cancel %s CONFIRM" % next_id
	if int(_construction_project("hospital").order.progress) != 1 or not await _press(cancel, false) \
			or not _panel_has("退回 10 铜和 0 公共结晶"):
		failure = "The partial cancellation did not quote the remaining share of the copper"
		return
	await _capture("construction-refund")
	if not await _press("cancel") or not await _command(cancel):
		return
	if int(app.view.day) != day + 1 or int(app.view.construction.funds.copper) != int(funds.copper) - 10 \
			or int(app.view.construction.funds.crystal) != int(funds.crystal) - 4 or int(app.view.construction.occupied) != 0:
		failure = "Partial cancellation refunded the wrong resources or left an occupied site"
		return
	side_checks["construction_refunds"] = {"zero": [20, 4], "partial": [10, 0], "order_ids": [order_id, next_id]}


func _check_book_market() -> void:
	var early: bool = not app.view.get("complete", false)
	var buyer := "N-0001" if early else "N-0002"
	var id := "SB-D02" if early else "SB-X01"
	var price := 8 if early else 20
	if not await _press("town-skills") or not await _press("bookstore"):
		return
	if early:
		if app.view.book_market.offers.size() != 12 or app.command_buttons.has("bookstore-stage-I") \
				or app.command_buttons.has("bookstore-stage-X") or app.board.deployment_open \
				or not await _press("bookstore-book-" + id) \
				or not _panel_has("采购需要一名适配且尚未学过此书") \
				or app.command_buttons.has("book buy " + buyer + " " + id):
			failure = "An empty early library exposed the wrong market or a purchase without an eligible member"
			return
		if not await _press("town-roster") or not await _command("recruit M01") \
				or not await _press("town-skills") or not await _press("bookstore"):
			return
	else:
		if not app.view.hunt.reported or not app.command_buttons.has("bookstore-stage-I") \
				or not await _press("bookstore-stage-X") or app.view.book_market.offers[id].price != 20:
			failure = "The archived chapter or first Ado report did not unlock the expected shelf"
			return
	if not await _press("bookstore-book-" + id):
		return
	var offer: Dictionary = app.view.book_market.offers[id]
	var copper := int(app.view.town_roster.copper)
	var day := int(app.view.day)
	var version := int(app.client.frame.state_version)
	var command := "book buy " + buyer + " " + id
	if not await _press(command, false) or not _panel_has("支付 %d 铜" % price) or not _panel_has("放入暮汀书库"):
		failure = "The purchase preview omitted the actual cost or destination"
		return
	await _capture("market-buy")
	if not await _press("cancel") or int(app.view.town_roster.copper) != copper \
			or int(app.client.frame.state_version) != version or not await _command(command):
		failure = "Cancel or confirmation did not apply the actual transaction boundary"
		return
	if int(app.view.town_roster.copper) != copper - price or int(app.view.day) != day \
			or int(app.view.skill_books.stock[id]) != int(offer.stock) + 1 \
			or id in app.view.skill_books.members[buyer].learned:
		failure = "Buying did not add one copy to the shared library without learning or spending a day"
		return
	side_checks["market_buy"] = {"book": id, "cost": price, "buyer": buyer, "day": day}
	if early:
		return
	if app.command_buttons.has("book target " + id) or not await _press("bookstore-list") \
			or not await _press("bookstore-stage-B") or not await _press("bookstore-book-SB-D02") \
			or not await _command("book target SB-D02") or app.view.book_market.target.id != "SB-D02":
		failure = "The late market failed to apply an eligible ordinary target"
		return
	await _capture("market-target")
	if not await _press("town-expedition") or not await _press("depart CONFIRM", false) \
			or not _panel_has("出发时锁定技能书定向「重劈」 · 0/2"):
		failure = "The departure preview omitted the saved target"
		return
	await _capture("market-departure")
	if not await _press("cancel") or not await _command("depart CONFIRM"):
		return
	side_checks["market_target"] = "SB-D02"


func _check_book_slot_swap() -> void:
	var learner := "N-0001"
	var entry := "member-" + learner
	if app.view.phase == "TOWN" or not app.view.route.get("contact_pending", false):
		if not await _press("town-skills" if app.view.phase == "TOWN" else "field-skills"):
			return
		entry = "book-member-" + learner
	if app.selected_id != learner and not await _press(entry):
		return
	var member: Dictionary = app.view.skill_books.members[learner]
	var args := OS.get_cmdline_user_args()
	var full := ["SB-B01", "SB-D05"]
	var incoming := "SB-P01"
	var slot := 1 if "--slot-two" in args else 0
	var next := full.duplicate()
	next[slot] = incoming
	if "--reopen-swap" in args:
		if member.equipped != next or not app.command_buttons.has("book-swap-%s-%s" % [learner, full[slot]]):
			failure = "Reopening did not restore the replaced book and the untouched slot"
			return
		await _capture("reopened-slots")
		return
	if member.equipped != full or incoming not in member.learned:
		failure = "The slot sample needs two occupied slots and a third learned manual"
		return
	var key := "book-swap-%s-%s" % [learner, incoming]
	var commit := "book equip " + learner + " " + " ".join(next)
	var original: Dictionary = app.client.frame
	if not await _press(key) or not _panel_has("换入 · 连击心得") or not await _wait_focus("book equip N-0001 SB-P01 SB-D05"):
		failure = "The swap chooser did not open on its first destination"
		return
	var destinations := {"book equip N-0001 SB-P01 SB-D05": "替换书槽 1 · 振奋战吼", "book equip N-0001 SB-B01 SB-P01": "替换书槽 2 · 瞄准射击"}
	for action in destinations:
		var button: Button = app.command_buttons.get(action)
		if button == null or button.disabled or button.text != destinations[action] or not app._action_scroll.get_global_rect().has_point(button.get_global_rect().get_center()):
			failure = "The swap chooser did not expose both occupied slot destinations"
			return
	await _capture("choose-slot")
	if mouse:
		if not await _press("book-swap-cancel"):
			return
	else:
		_key(KEY_ESCAPE, true)
		_key(KEY_ESCAPE, false)
	if not await _wait_focus(key) or app.client.frame != original or not await _press(key) or not await _command(commit):
		failure = "Cancelling or confirming the full-slot choice did not follow the existing book command"
		return
	var after: Dictionary = app.view.skill_books.members[learner]
	if int(app.client.frame.state_version) != int(original.state_version) + 1 or after.equipped != next \
			or after.learned != member.learned or app.command_buttons.has("book-swap-cancel") \
			or not await _wait_focus("book-swap-%s-%s" % [learner, full[slot]]):
		failure = "Replacing a book altered another slot or submitted more than one change"
		return
	side_checks["slot_change"] = {"before": full, "after": next, "slot": slot + 1}
	await _capture("replaced-slot")
	if "--fight-after-slot" in args:
		var party: Array = app.view.party.filter(func(row): return row.instance_id == learner)
		if party.size() != 1:
			failure = "The prepared learner was not with the party"
			return
		if not party[0].deployed and not await _command("deploy " + learner + " on"):
			return
		if not await _command("fight") or app.command_buttons.has(key) or app.view.phase != "BATTLE":
			failure = "The saved formation did not enter combat after the slot change"
			return
		if not await _commands(["step", "step"]):
			return
		await _capture("swapped-battle")


func _check_skill_book_flow() -> void:
	var learner := "N-0002"
	var basic := "SB-B01"
	var boss := "SB-X01"
	var day: int = app.view.day
	var copper: int = app.view.town_roster.copper
	if not app.view.hunt.reported or not await _press("town-skills") \
			or not _panel_has("振奋战吼 ×1") or not _panel_has("守誓回斩 ×1") \
			or not await _press("book-member-" + learner):
		failure = "The delivered book inventory and compatible learner were not accessible"
		return
	var learning := "book learn " + learner + " " + boss
	var version: int = app.client.frame.state_version
	if not await _press(learning, false) or not _panel_has("消耗 1 本「守誓回斩」") \
			or not _panel_has("准备 1 拍 · 冷却 5 拍") or not _panel_has("生命上限"):
		failure = "The learn confirmation omitted the source, timing or effect"
		return
	await _capture("book-learn")
	if not await _press("cancel") or int(app.client.frame.state_version) != version \
			or not await _commands(["book learn " + learner + " " + basic, learning]):
		failure = "Learning or cancelling a study did not respect the commit boundary"
		return
	if not app.view.skill_books.stock.is_empty() or int(app.view.day) != day or int(app.view.town_roster.copper) != copper \
			or app.view.skill_books.members[learner].learned != [basic, boss]:
		failure = "Learning spent something other than one copy of each book"
		return
	if not await _commands(["book equip " + learner + " " + basic, "book equip " + learner + " " + basic + " " + boss]) \
			or not _panel_has("书槽 1 · 振奋战吼") or not _panel_has("书槽 2 · 守誓回斩"):
		failure = "The two distinct learned books could not occupy both slots"
		return
	await _capture("book-slots")
	if not await _press("town-expedition") or not await _command("depart CONFIRM") \
			or not await _press("field-skills") or not _panel_has("书槽 2 · 守誓回斩"):
		failure = "The learned books did not travel with the selected mercenary"
		return
	if not await _commands(["move U", "move B1", "book equip " + learner + " " + boss]) \
			or app.view.skill_books.members[learner].equipped != [boss] \
			or not _panel_has("书槽 1 · 守誓回斩") or not _panel_has("书槽 2 · 空"):
		failure = "At contact the learned books could not be swapped without studying again"
		return
	await _capture("book-contact")
	if not await _command("fight") or app.view.battle_view.encounter != "RG01-N02" \
			or app.command_buttons.has("book equip " + learner + " clear"):
		failure = "The battle did not start after book configuration"
		return
	for beat in range(8):
		if not await _command("step"):
			return
	var battle: Dictionary = app.view.battle_view
	var matches: Array = battle.recent.filter(func(event: Dictionary) -> bool:
		return event.type == "release" and event.get("move") == "SK-SB-X01" and event.actor == learner)
	if int(battle.tick) != 8 or matches.size() != 1 or not await _press("battle-log") \
			or not _report_mentions(app._live_battle_log._entries, "守誓回斩"):
		failure = "The equipped Ado reward did not actually release from the learned mercenary"
		return
	side_checks["skill_book_flow"] = {"learner": learner, "learned": [basic, boss], "release_tick": 8}
	await _capture("book-battle")


func _check_skill_tactics() -> void:
	var member := "N-0002"
	var signature := "SK-SB-X01"
	var core := "M01-A"
	var main := "book main " + member + " "
	var toggle := "book auto " + member + " "
	var reorder := "book queue " + member + " " + signature + " " + core
	if not app.view.route.get("contact_pending", false):
		failure = "The automatic skill fixture requires a battle deployment"
		return
	if not await _press("member-" + member):
		return
	if app.selected_id != member:
		await _capture("tactics-member-selection")
		failure = "The member row did not select the requested unit: " + str(app.selected_id)
		return
	if not await _press("skill-tactics-" + member):
		return
	if not _panel_has("主要接敌方式 · 自动"):
		await _capture("tactics-panel-closed")
		failure = "The selected member did not expose automatic skill configuration"
		return
	if not await _command(main + signature) or not _panel_has("主要接敌方式 · 守誓回斩") \
			or not await _command(toggle + signature + " off") or not _panel_has("主要接敌方式 · 自动") \
			or app.command_buttons.has(main + signature):
		failure = "Disabling the selected approach did not restore automatic approach"
		return
	if not await _commands([toggle + signature + " on", reorder, toggle + core + " off", main + "BASIC"]) \
			or not _panel_has("主要接敌方式 · 普攻距离") or not await _command(main + signature):
		failure = "The queue, individual switch or primary approach could not be committed"
		return
	var tactics: Dictionary = app.view.skill_books.members[member]
	if tactics.moves.map(func(move: Dictionary): return move.id) != [signature, core] \
			or not tactics.moves[0].enabled or tactics.moves[1].enabled or tactics.main != signature:
		failure = "The saved tactics do not show the chosen order and switches"
		return
	await get_tree().process_frame
	if app.get_viewport().gui_get_focus_owner() != app.command_buttons[main + "BASIC"]:
		failure = "The applied main attack moved focus away from the tactical settings"
		return
	await _capture("configured-tactics")
	if not await _command("fight") or not app._playback_running \
			or not await _wait_until(func() -> bool:
				return int(app.view.battle_view.tick) >= 6 and not app.client.busy, 10000):
		failure = "The configured encounter did not reach the sixth automatic beat"
		return
	_key(KEY_SPACE, true)
	_key(KEY_SPACE, false)
	await get_tree().process_frame
	if not await _wait_ready() or int(app.view.battle_view.tick) != 6 or app._playback_running \
			or not await _press("battle-log") \
			or not _report_mentions(app._live_battle_log._entries, "守誓回斩"):
		failure = "The configured skill did not release on the expected automatic beat"
		return
	if not await _check_report_rows(app._live_battle_log, app.view.battle_view):
		failure = "The live battle report did not display aligned and readable rows"
		return
	side_checks["skill_tactics"] = {"order": [signature, core], "stopped": core, "main": signature, "release_tick": 6}
	await _capture("tactics-battle")


func _check_late_ado_model() -> void:
	var stage = app.board.stage
	var from_contact: bool = app.view.phase == "EXPLORE"
	var shield_delayed := "--delay-shield-start" in OS.get_cmdline_user_args()
	var ready_signal := get_tree().process_frame
	if not ready_signal.is_connected(stage._dispatch_models):
		failure = "The Ado model was not queued for background dispatch"
		return
	# Hold dispatch until after the user action so the result does not depend on storage speed.
	ready_signal.disconnect(stage._dispatch_models)
	if from_contact:
		if shield_delayed:
			for member: Dictionary in app.view.party:
				if member.unit_id == "S01" and member.deployed:
					var cell: Vector2i = app.board.cell_index(member.position)
					if app.board._deployment_member(app.board.coordinate_map[cell]) != member.instance_id:
						failure = "The delayed shield could not be picked on the contact board"
						return
		if not await _command("fight") or not await _press("combat-playback"):
			return
	else:
		if not await _press("settings") or not stage.focused_pause:
			failure = "Settings did not pause the battle presentation"
			return
	var battle: Dictionary = app.view.battle_view
	var boss: Dictionary = {}
	for actor in battle.actors:
		if actor.kind == "MG01":
			boss = actor
			break
	if boss.is_empty() or app._playback_running or (not from_contact and not boss.has("boss_pending")):
		failure = "The boss battle did not pause at its saved state"
		return
	if not shield_delayed and (stage.actors.has(boss.id) or not app.board._unit_markers.has(boss.id)):
		failure = "Ado did not use a fallback marker before the load"
		return
	var version: int = app.client.frame.state_version
	var old_events: int = stage.audit.events
	var old_releases: int = stage.audit.ado_releases
	if shield_delayed:
		var markers: Array[String] = []
		for actor: Dictionary in battle.actors:
			if actor.kind == "S01" and app.board._unit_markers.has(actor.id) and not stage.actors.has(actor.id):
				markers.append(actor.id)
		if markers.is_empty() or stage.model != null or stage.warmup_pawn != null:
			failure = "The shield pieces were unavailable while the base scene was delayed"
			return
		if app.board.coordinate_map.is_empty():
			failure = "Delaying the shield prevented the actual battle board from opening"
			return
		side_checks["initial_shield_markers"] = markers
		stage._load_scene(stage.MODEL_PATH, true)
	stage._wake_model_dispatch()
	if not from_contact:
		if not await _wait_until(func() -> bool: return stage.ADO_PATH in stage._scenes_ready_to_present, 6000) \
				or stage.actors.has(boss.id) or not stage.focused_pause:
			failure = "Reading the asset in settings changed the paused presentation or failed to finish"
			return
		if not await _press("settings-back"):
			return
	if not await _wait_until(func() -> bool: return stage.actors.has(boss.id), 7000) \
			or int(app.client.frame.state_version) != version or stage.audit.events != old_events \
			or stage.audit.ado_releases != old_releases:
		failure = "The late model did not arrive at the same saved state without renewed events"
		return
	if not await _wait_until(func() -> bool:
			return not stage._has_model_work() and stage.actors.size() == battle.actors.size(), 6000) \
			or int(app.client.frame.state_version) != version:
		failure = "The saved roster did not finish attaching while combat was stopped: %d/%d" % [
			stage.actors.size(), battle.actors.size()]
		return
	var pawn = stage.actors[boss.id].node
	var lock: Dictionary = boss.get("boss_pending", {})
	if not lock.is_empty() and (pawn.cast_id != lock.id or pawn.pending != lock.move_id):
		failure = "The late Ado model lost its saved windup"
		return
	side_checks["late_model"] = {"started_from_contact": from_contact, "tick": int(battle.tick),
		"version": version, "pending_move": pawn.pending, "old_events_replayed": 0,
		"finished_read_while_settings_open": not from_contact, "models": stage.actors.size(),
		"model_reads": stage.asset_load_timings.duplicate(true)}
	if not from_contact and not await _command("step"):
		return


func _check_session_busy() -> void:
	if not await _wait_until(func() -> bool: return app.client.blocked and not app.client.busy, 12000) \
			or not app.client.can_reconnect or not app.model.is_empty() or not app.client.pending.is_empty() \
			or "此试玩会话正在使用" not in app.notice.text or _panel_has("--recover"):
		failure = "The second window did not recognize a busy session"
		return
	var waiting: String = app.data_dir.path_join("session-busy.waiting")
	var marker := FileAccess.open(waiting, FileAccess.WRITE)
	if marker == null:
		failure = "Could not signal the session lock check"
		return
	side_checks["occupied_notice"] = app.notice.text
	marker.store_string(app.notice.text)
	marker.close()
	var released: String = app.data_dir.path_join("session-busy.released")
	var deadline := Time.get_ticks_msec() + 8000
	while not FileAccess.file_exists(released) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if not FileAccess.file_exists(released):
		failure = "The first window did not release the session in time"
		return
	if not await _press("reconnect"):
		return
	if not app.client.pending.is_empty() or int(app.client.frame.get("state_version", -1)) != 1 \
			or int(app.view.get("battle_view", {}).get("tick", -1)) != 3 or app._playback_running:
		failure = "Retry did not restore the existing paused battle"
		return
	await _check_paused("retried_paused")


func _check_startup_help() -> void:
	if not await _wait_until(func() -> bool: return app.client.blocked and not app.client.busy, 12000) \
			or not app.model.is_empty() or not _panel_has("无法打开试玩会话") \
			or not _panel_has("--recover") or not app.command_buttons.has("session-folder"):
		failure = "The damaged save did not expose its session folder and backup recovery guidance"
		return
	await _capture("startup-help")


func _check_receipt_boot() -> void:
	if "--unverified-session" in OS.get_cmdline_user_args():
		if not await _wait_until(func() -> bool: return app.client.blocked and not app.client.busy, 12000) \
				or not app.model.is_empty() or not _panel_has("无法打开试玩会话") \
				or not app.command_buttons.has("runtime-log") or app.client.can_reconnect:
			failure = "The unverified checkpoint was published or its diagnostic was lost"
			return
		var log := FileAccess.get_file_as_string(app.client.runtime_log)
		if "RECOVERY_REQUIRED" not in log:
			failure = "The persisted runtime log did not record the recovery reason"
			return
		await _capture("receipt-blocked")
	else:
		if not await _wait_ready():
			return
		if not app.client.pending.is_empty() or app.client.frame.state_version != 1 \
				or int(app.view.battle_view.tick) != 3 or app._playback_running:
			failure = "The unacknowledged committed beat did not resume exactly once"
			return
		await _capture("receipt-restored")
	side_checks["runtime_log"] = app.client.runtime_log.get_file()
	side_checks["pending_preserved"] = not app.client.pending.is_empty()



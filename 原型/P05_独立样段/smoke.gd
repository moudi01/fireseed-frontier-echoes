extends Node

var app: Control
var steps: Array = []
var failure := ""
var mode := ""
var began := 0
var mouse := false
var capture := false


func start(root: Control, scenario: String) -> void:
	app = root
	mode = scenario
	mouse = mode == "full-mouse"
	capture = "--capture" in OS.get_cmdline_user_args()
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
		app.actions.get_parent().ensure_control_visible(button)
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


func _button_point(button: Button) -> Vector2:
	return button.get_viewport().get_final_transform() * button.get_global_rect().get_center()


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


func _capture(mark: String) -> void:
	if not capture:
		return
	await RenderingServer.frame_post_draw
	var image := app.get_viewport().get_texture().get_image()
	if image == null or image.save_png(app.data_dir.path_join(app.case_name + "." + mark + ".png")) != OK:
		failure = "Cannot capture viewport: " + mark


func _command(key: String) -> bool:
	var before := int(app.client.frame.get("state_version", -1))
	if not await _press(key):
		return false
	var frame: Dictionary = app.client.frame
	if int(frame["state_version"]) != before + 1:
		failure = "Command was not committed: " + key + " / " + app.notice.text
		return false
	steps.append({"command": key, "version": frame["state_version"], "digest": frame["state_digest"],
		"phase": app.view.get("phase"), "site": app.view.get("site")})
	return true


func _commands(keys: Array) -> bool:
	for key in keys:
		if not await _command(key):
			return false
	return true


func _fight(expected: String) -> bool:
	if not await _command("fight"):
		return false
	var saw_warning := false
	for i in range(160):
		if app.view.get("phase") != "BATTLE":
			var reports: Array = app.view.get("battle_results", [])
			if not reports.is_empty() and reports[-1]["encounter_id"] == expected and reports[-1]["result"] == "VICTORY" and saw_warning:
				return true
			failure = "Unexpected result or missing warning for " + expected
			return false
		if not await _command("step"):
			return false
		if app.warning.visible and not saw_warning:
			await _capture(expected + "-warning")
		saw_warning = saw_warning or app.warning.visible
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
	if mode == "access":
		if not await _confirmation_focus() or not await _keyboard_deploy():
			return false
	return await _command("tutorial start")


func _confirmation_focus() -> bool:
	var version := int(app.client.frame["state_version"])
	var files: Dictionary = app.client.frame["files"].duplicate()
	if not await _press("tutorial start", false) or not _has_focus("cancel"):
		failure = "The departure confirmation did not focus Cancel"
		return false
	if not await _press("settings", false) or not app.settings_open or not _has_focus("volume"):
		failure = "Settings over the departure confirmation did not focus Volume"
		return false
	_key(KEY_ESCAPE, true)
	await get_tree().process_frame
	_key(KEY_ESCAPE, true, true)
	_key(KEY_ESCAPE, false)
	await get_tree().process_frame
	if app.settings_open or app.confirmation.is_empty() or not _has_focus("settings"):
		failure = "Closing settings did not restore its entry in the confirmation"
		return false
	_key(KEY_ESCAPE, true)
	_key(KEY_ESCAPE, false)
	await get_tree().process_frame
	if not app.confirmation.is_empty() or not _has_focus("tutorial start"):
		failure = "Cancel did not restore the departure button"
		return false
	if int(app.client.frame["state_version"]) != version or app.client.frame["files"] != files:
		failure = "Closing the confirmation changed the authority"
		return false
	return true


func _has_focus(key: String) -> bool:
	return app.command_buttons.has(key) and app.get_viewport().gui_get_focus_owner() == app.command_buttons[key]


func _keyboard_deploy() -> bool:
	for member in app.view["party"]:
		if not member["deployed"] or not member["position"] in app.view["town_deploy_cells"]:
			continue
		var member_id: String = member["instance_id"]
		var point: Array = member["position"]
		var face := (int(member["facing"]) + 1) % 6
		return await _press("member-" + member_id) and await _press("cell-%d-%d" % point) and await _press("facing") and await _command("place %s %d %d %d" % [member_id, point[0], point[1], face])
	failure = "No deployed member on a legal town cell"
	return false


func _full() -> void:
	if not await _commands(["move A"]) or not await _fight("INTRO-EN01"):
		return
	var material := "tutorial materials PASS" if mouse else "tutorial materials"
	if not await _commands(["tutorial plan PL01", "move B_SUPPORT", "tutorial support PASS", "move A", "move B_MATERIAL",
		material, "move A", "move B_MATERIAL"]):
		return
	if app.command_buttons.has("tutorial materials") or app.command_buttons.has("tutorial materials PASS"):
		failure = "Revisiting the materials branch re-opened a settled choice"
		return
	if not await _commands(["move C", "move D"]):
		return
	if app.view.get("observation") != null:
		failure = "Reaching D created a false observation"
		return
	if mode != "unobserved" and not await _command("tutorial observe"):
		return
	if not await _command("move G") or not await _fight("TUT01-ROOT"):
		return
	if app.model.get("active", {}).get("id", "") != "trip-1-root_win":
		failure = "The authority did not show G's distant voice"
		return
	var offers: Array = app.view.get("gear_offers", [])
	if offers.is_empty():
		failure = "The reward was not presented"
		return
	if mode not in ["unclaimed", "unobserved"] and not await _command("tutorial cache " + offers[0]):
		return
	if not await _commands(["move X", "return CONFIRM"]):
		return
	if app.warning.visible or app.sound_count < 2:
		failure = "Missing final danger clear or warning audio dispatch"
		return
	_check_settlement("SAFE_RETURN", mode != "unobserved")
	await _capture("settlement")


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


func _run() -> void:
	if mode not in ["resume", "full", "full-mouse", "unclaimed", "unobserved", "early", "flee", "contact", "access", "defeat", "repeat-input"]:
		failure = "Unknown smoke scenario: " + mode
	elif await _wait_ready():
		if mode == "resume":
			if app.view.get("phase") != "RETURNED" or not app.client.pending.is_empty():
				failure = "Completed campaign did not restore"
			else:
				_check_settlement("SAFE_RETURN", true)
		elif await _opening():
			if mode in ["full", "full-mouse", "unclaimed", "unobserved"]:
				await _full()
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
	var report := FileAccess.open(app.data_dir.path_join(app.case_name + "." + mode + ".json"), FileAccess.WRITE)
	if report != null:
		report.store_string(JSON.stringify(result, "  "))
		report.close()
	print("P05 ", mode, " ", failure if not failure.is_empty() else "PASS", " / ", steps.size(), " commits")
	get_tree().quit(0 if failure.is_empty() else 1)


func _repeat_input() -> void:
	if not await _commands(["move A", "fight"]):
		return
	await get_tree().process_frame
	if not _has_focus("step"):
		failure = "Starting combat did not focus the advance button"
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
	for member in app.view["party"].duplicate():
		var id: String = member["instance_id"]
		if member["deployed"] and id != "INIT-S03-B":
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
		var settlement: Variant = app.view.get("settlement")
		if settlement is Dictionary and settlement.get("result") in ["DEFEAT", "TOTAL_DEFEAT"]:
			_check_settlement(settlement["result"], false)
			return
		if battle == "A" and not await _commands(["move B_MATERIAL", "move C", "move D", "move G"]):
			return
	failure = "The one-member formation did not produce a defeat"

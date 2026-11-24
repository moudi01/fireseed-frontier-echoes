extends Control

const Pipe = preload("res://pipe_client.gd")
const Board = preload("res://hex_board.gd")
const INK := Color("e9dbc0")
const MUTED := Color("a7b8ac")
const GOLD := Color("e7bd75")
const ALERT := Color("f7ac8e")
const PLACES := {"I": "入口", "A": "林道接敌", "B_SUPPORT": "护运站", "B_MATERIAL": "材料匣", "C": "歇脚点", "D": "远眺点", "G": "根口", "X": "归路"}
const REASONS := {"SAFE_RETURN": "安全归城", "COMBAT_RETREAT": "追击后撤退", "DEFEAT": "战斗败北", "VICTORY": "胜利", "RETREAT": "撤退"}
const WARNING_LEVEL_DB := -9.0

var client: Node
var board: Control
var actions: VBoxContainer
var warning: Label
var location: Label
var save_info: Label
var notice: Label
var subtitles: Label
var audio: AudioStreamPlayer
var case_name := "rg01"
var data_dir: String
var bundle: String
var model: Dictionary = {}
var view: Dictionary = {}
var selected_id := ""
var selected_cell := Vector2i(-999, -999)
var selected_facing := 0
var confirmation: Dictionary = {}
var seen_warnings: Dictionary = {}
var sound_count := 0
var save_version := -1
var settings := {"音效": true, "音乐": true, "静音": false, "大字": false, "低动态": false}
var volume := 100
var settings_open := false
var opened := false
var captions_open := false
var caption_index := 0
var initial_snapshot := true
var command_buttons: Dictionary = {}
var ui_font: Font
var focus_key := ""


func _ready() -> void:
	get_tree().auto_accept_quit = false
	var base: String
	if OS.has_feature("template"):
		base = OS.get_executable_path().get_base_dir()
	else:
		base = ProjectSettings.globalize_path("res://build")
	bundle = base.path_join("sidecar")
	data_dir = base.path_join("data")
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--case="):
			case_name = item.trim_prefix("--case=")
		elif item.begins_with("--sidecar="):
			bundle = item.trim_prefix("--sidecar=")
		elif item.begins_with("--data="):
			data_dir = item.trim_prefix("--data=")
	var check := RegEx.create_from_string("^[A-Za-z0-9_-]{1,80}$")
	if check.search(case_name) == null:
		push_error("Invalid P05 session name")
		get_tree().quit(2)
		return
	_load_settings()
	_build()
	client = Pipe.new()
	add_child(client)
	client.refreshed.connect(_refresh)
	client.notice.connect(_notice)
	client.busy_changed.connect(_busy)
	client.boot(bundle, data_dir, case_name)
	for item in OS.get_cmdline_user_args():
		if item.begins_with("--smoke="):
			var test_script: Script = load("res://smoke.gd")
			if test_script == null or not test_script.can_instantiate():
				get_tree().quit(2)
				return
			var runner: Node = test_script.new()
			add_child(runner)
			runner.start(self, item.trim_prefix("--smoke="))


func _box(fill: String, edge: String, radius: int, padding: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(fill)
	style.border_color = Color(edge)
	style.set_border_width_all(1)
	style.set_corner_radius_all(radius)
	for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		style.set_content_margin(side, padding)
	return style


func _build() -> void:
	var system_font := SystemFont.new()
	system_font.font_names = PackedStringArray(["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI"])
	ui_font = system_font
	theme = Theme.new()
	theme.default_font = ui_font
	theme.default_font_size = 16
	theme.set_stylebox("normal", "Button", _box("23373a", "46615e", 7, 10))
	theme.set_stylebox("hover", "Button", _box("324c4b", "81a99c", 7, 10))
	theme.set_stylebox("pressed", "Button", _box("51462e", "d5a358", 7, 10))
	theme.set_stylebox("focus", "Button", _box("00000000", "e7bd75", 7, 10))
	theme.set_stylebox("disabled", "Button", _box("182628", "2c3c39", 7, 10))
	for group in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		theme.set_color(group, "Button", INK)

	var outer := PanelContainer.new()
	outer.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	outer.add_theme_stylebox_override("panel", _box("0f1819", "24312c", 0, 25))
	add_child(outer)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 12)
	outer.add_child(stack)

	var header := HBoxContainer.new()
	stack.add_child(header)
	var title := VBoxContainer.new()
	title.size_flags_horizontal = SIZE_EXPAND_FILL
	header.add_child(title)
	_label(title, "火种计划  /  灰栎边道", INK, 31)
	location = _label(title, "暮汀", MUTED, 17)
	save_info = _label(header, "正在打开存档", GOLD, 15)
	save_info.autowrap_mode = TextServer.AUTOWRAP_OFF
	save_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	save_info.custom_minimum_size.x = 168

	var body := HBoxContainer.new()
	body.size_flags_vertical = SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 15)
	stack.add_child(body)
	var map_column := VBoxContainer.new()
	map_column.size_flags_horizontal = SIZE_EXPAND_FILL
	body.add_child(map_column)
	board = Board.new()
	board.font = ui_font
	board.custom_minimum_size = Vector2(370, 330)
	board.size_flags_vertical = SIZE_EXPAND_FILL
	board.cell_selected.connect(_board_cell)
	map_column.add_child(board)
	warning = _label(map_column, "", ALERT, 17)
	warning.visible = false

	var panel := PanelContainer.new()
	panel.custom_minimum_size.x = 365
	panel.add_theme_stylebox_override("panel", _box("172527", "41524c", 9, 13))
	body.add_child(panel)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	panel.add_child(scroll)
	actions = VBoxContainer.new()
	actions.size_flags_horizontal = SIZE_EXPAND_FILL
	actions.add_theme_constant_override("separation", 6)
	scroll.add_child(actions)

	subtitles = _label(stack, "", INK, 18)
	subtitles.custom_minimum_size.y = 32
	notice = _label(stack, "正在连接旁载运行时…", MUTED, 15)
	audio = AudioStreamPlayer.new()
	audio.stream = _make_warning_sound()
	_apply_volume()
	add_child(audio)


func _label(parent: Control, text: String, color: Color, pixels: int) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", color)
	label.add_theme_font_size_override("font_size", pixels)
	parent.add_child(label)
	return label


func _button(text: String, key: String, fn: Callable, enabled := true) -> Button:
	var entry := Button.new()
	entry.text = text
	entry.alignment = HORIZONTAL_ALIGNMENT_LEFT
	entry.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	entry.disabled = not enabled
	entry.focus_mode = Control.FOCUS_ALL
	entry.focus_entered.connect(func() -> void: focus_key = key)
	entry.pressed.connect(fn)
	actions.add_child(entry)
	command_buttons[key] = entry
	return entry


func _input_action(text: String, command: String, args: Array, consequence := "") -> void:
	var key := " ".join([command] + args)
	_button(text, key, func() -> void:
		if consequence.is_empty():
			client.submit(command, args)
		else:
			confirmation = {"command": command, "args": args, "text": consequence, "back": key}
			focus_key = "cancel"
			_render()
		, not client.busy and not client.blocked)


func _refresh(row: Dictionary) -> void:
	model = row.get("presentation", {})
	view = model.get("slice", {})
	if row.get("files", {}).get("save.json") != null:
		save_version = int(view.get("save_version", 0))
	if int(row["state_version"]) > 0 or view.get("commissioned", false):
		opened = true
	if initial_snapshot and notice.text == "正在连接旁载运行时…":
		notice.text = ""
	_set_danger()
	initial_snapshot = false


func _set_danger() -> void:
	var current: Variant = model.get("danger")
	var lines: Array[String] = []
	var unsounded := false
	if current is Dictionary:
		for intent in current.get("actions", []):
			if intent.get("side") != "enemy":
				continue
			var key := "%s/%s" % [current["battle_id"], intent["action_id"]]
			if not seen_warnings.has(key):
				seen_warnings[key] = true
				unsounded = true
			var locked: Array = intent.get("locked_cells", [])
			var cells: Array[String] = []
			for point in locked:
				cells.append("%d,%d" % [int(point[0]), int(point[1])])
			var target: Variant = intent.get("target")
			var where := "锁定格 " + " / ".join(cells) if not cells.is_empty() else "目标 " + str(target) if target != null else "攻击起手"
			lines.append("⚠ %s   %s   剩余 %d 拍" % [intent.get("move_id", "预警"), where, maxi(0, int(intent.get("due", current["tick"])) - int(current["tick"]))])
	warning.text = "\n".join(lines)
	warning.visible = not lines.is_empty()
	if lines.is_empty():
		audio.stop()
	elif unsounded and not initial_snapshot and volume > 0 and not settings["静音"] and settings["音效"]:
		audio.play()
		sound_count += 1


func _make_warning_sound() -> AudioStreamWAV:
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = 24000
	var wave := PackedByteArray()
	wave.resize(8640)
	for i in range(4320):
		var time := float(i) / 24000.0
		var offset := time if time < 0.075 else time - 0.10
		var gain := clampf(minf(offset / 0.009, (0.074 - offset) / 0.02), 0, 1)
		var frequency := 660.0 if time < 0.075 else 880.0
		wave.encode_s16(i * 2, int(7800.0 * gain * sin(TAU * frequency * offset)))
	stream.data = wave
	return stream


func _notice(message: String) -> void:
	notice.text = message


func _busy(value: bool) -> void:
	if value:
		for control in command_buttons.values():
			control.disabled = true
		save_info.text = "正在处理"
	else:
		_render()


func _display_location() -> String:
	var phase: String = view.get("phase", "TOWN")
	if phase in ["TOWN", "RETURNED", "FAILED"]:
		return "暮汀   /   行动日 %d   /   补给 %d" % [int(view.get("day", 0)), int(view.get("supply", 0))]
	var site := str(view.get("site", ""))
	var label: String = PLACES.get(site, "已探索道路")
	var danger: Variant = model.get("danger")
	if danger is Dictionary:
		return "%s   /   战斗第 %d 拍" % [label, int(danger["tick"])]
	return "侦路   /   " + label


func _render() -> void:
	for node in actions.get_children():
		actions.remove_child(node)
		node.queue_free()
	command_buttons.clear()
	theme.default_font_size = 24 if settings["大字"] else 16
	location.text = _display_location()
	_render_subtitle()
	save_info.text = "结果待核实" if client.blocked else "已保存 · 版本 %d" % save_version if save_version >= 0 else "存档尚未确认"
	subtitles.add_theme_font_size_override("font_size", 27 if settings["大字"] else 18)
	warning.add_theme_font_size_override("font_size", 25 if settings["大字"] else 17)
	board.update_board(model if opened else {}, selected_id)
	if settings_open:
		_label(actions, "设置", GOLD, 23)
		_button("主音量 · %d%%" % volume, "volume", _cycle_volume)
		for setting in settings.keys():
			_button(setting + (" · 开" if settings[setting] else " · 关"), setting, _toggle.bind(setting))
		_button("返回", "settings-back", _close_settings)
	elif not confirmation.is_empty():
		_label(actions, "确认操作", GOLD, 23)
		_label(actions, confirmation["text"], INK, 19)
		_button("取消", "cancel", _cancel_confirmation)
		_button("确认", "confirm", _confirm)
		_button("设置", "settings", _show_settings)
	else:
		var phase: String = view.get("phase", "")
		if (not opened or captions_open) and not view.is_empty():
			_opening_actions()
		elif phase == "TOWN":
			_town_actions()
		elif phase in ["RETURNED", "FAILED"]:
			_settlement_actions()
		elif phase == "EXPLORE":
			_explore_actions()
		elif phase == "BATTLE":
			_battle_actions()
		if opened and not captions_open and not view.get("opening_lines", []).is_empty():
			_button("回看开场字幕", "opening-replay", _replay_opening)
		_button("设置", "settings", _show_settings)
		_button("退出样段", "quit", _quit)
	if command_buttons.has(focus_key) and not command_buttons[focus_key].disabled:
		command_buttons[focus_key].call_deferred("grab_focus")
	else:
		for control in command_buttons.values():
			if not control.disabled:
				control.call_deferred("grab_focus")
				break


func _render_subtitle() -> void:
	var lines: Array = view.get("opening_lines", [])
	var line: Variant = null
	if (not opened or captions_open) and not lines.is_empty():
		line = lines[caption_index]
	else:
		var active: Variant = model.get("active")
		if active is Dictionary:
			line = active["line"]
	subtitles.text = "%s   %s" % [line["speaker"], line["text"]] if line is Dictionary else ""


func _opening_actions() -> void:
	var count: int = view.get("opening_lines", []).size()
	_label(actions, "暮汀门前", GOLD, 26)
	if count > 1:
		_label(actions, "%d / %d" % [caption_index + 1, count], MUTED, 16)
		_button("下一句字幕", "subtitle-next", _turn_caption.bind(1), caption_index + 1 < count)
		_button("上一句字幕", "subtitle-prev", _turn_caption.bind(-1), caption_index > 0)
	_button("返回" if captions_open else "进入城镇", "opening", _open_town)


func _turn_caption(offset: int) -> void:
	caption_index += offset
	_render()


func _town_actions() -> void:
	if view.get("complete", false):
		_settlement_actions()
		return
	if not view.get("commissioned", false):
		_label(actions, "暮汀委任", GOLD, 24)
		_input_action("接受委任", "quest", ["commission", "CONFIRM"], "接受侦路委任并登记初始队伍。")
		return
	_label(actions, "出发前整备", GOLD, 24)
	if view.get("settlement") is Dictionary:
		_summary()
	_input_action("采用建议部署", "tutorial", ["recommend", "CONFIRM"], "将建议部署应用于当前可用的初始队员。")
	_input_action("出发 · 消耗 1 补给", "tutorial", ["start"], "前往灰栎边道。消耗 1 补给。")
	_member_actions(view.get("town_deploy_cells", []))


func _settlement_actions() -> void:
	_label(actions, "侦路调查已交付" if view.get("complete", false) else "远征结算", GOLD, 24)
	_summary()


func _explore_actions() -> void:
	var site := str(view.get("site", ""))
	var route: Dictionary = view.get("route", {})
	_label(actions, PLACES.get(site, "道路与现场"), GOLD, 24)
	if route.get("contact_pending", false):
		_input_action("确认开战", "fight", [], "以当前部署进入战斗。")
		_input_action("返回接敌边界外", "retreat", [])
		var map_data: Dictionary = model.get("map", {})
		_member_actions(map_data.get("deploy_cells", []))
		return
	var choices: Dictionary = view.get("choices", {})
	var choice_key := {"A": "plan", "B_SUPPORT": "support", "B_MATERIAL": "materials", "G": "cache"}.get(site, "") as String
	if choices.has(choice_key):
		_label(actions, "已处理 · " + str(choices[choice_key]["choice"]), MUTED, 16)
	else:
		_site_actions(site)
	if route.get("safe_return", false):
		_input_action("确认归城", "return", ["CONFIRM"], "结束本趟远征并按实际结果归城。")
	for place in route.get("neighbors", []):
		_input_action("前往 " + PLACES.get(place, place), "move", [place])
	if site == "<null>" or site.is_empty():
		for place in route.get("nearby", []):
			_input_action("交互 " + PLACES.get(place, place), "interact", [place])
		var map_data: Dictionary = model.get("map", {})
		for node in map_data.get("objects", []):
			if node.get("id") != "I":
				continue
			var pos: Array = node["position"]
			_input_action("沿已知道路返回入口", "walkto", [str(int(pos[0])), str(int(pos[1]))])


func _site_actions(site: String) -> void:
	match site:
		"A":
			for plan in view.get("plans", []):
				_input_action("登记方案 " + plan, "tutorial", ["plan", plan], "登记这份方案，或返回继续侦路。")
			if not view.get("plans", []).is_empty():
				_input_action("放弃登记方案", "tutorial", ["plan", "PASS"], "结束本站的方案选择。")
		"B_SUPPORT":
			for member in view.get("party", []):
				if float(member.get("hp", 0)) > 0:
					_input_action("请求支援 · " + _name(member), "tutorial", ["support", member["instance_id"]], "为此队员确认本次支援。")
			_input_action("放弃支援", "tutorial", ["support", "PASS"], "结束本站的支援选择。")
		"B_MATERIAL":
			_input_action("领取材料", "tutorial", ["materials"], "确认领取材料匣中的物资。")
			_input_action("放弃材料", "tutorial", ["materials", "PASS"], "结束本站的材料选择。")
		"D":
			if view.get("observation") is Dictionary:
				_label(actions, view["observation"]["observed"], INK, 16)
			else:
				_input_action("观察并记录", "tutorial", ["observe"])
		"G":
			if not view.get("gear_offers", []).is_empty():
				if view.get("gear_claims", 0) > 0:
					for item in view["gear_offers"]:
						_input_action("领取装备 · " + item, "tutorial", ["cache", item], "消耗一次领取额度，装备收入行囊，当前尚未穿戴。")
				else:
					_label(actions, "本趟装备领取额度已用完。", MUTED, 16)
				_input_action("放弃装备", "tutorial", ["cache", "PASS"], "结束本场战后的装备选择。")


func _battle_actions() -> void:
	_label(actions, "战斗", GOLD, 24)
	_input_action("推进一拍", "step", [])
	_input_action("撤退", "flee", ["CONFIRM"], "撤退时将结算一拍追击，依据实际结果判定撤退或战败。")
	for actor in view.get("actors", []):
		_label(actions, "%s   生命 %s" % [_name(actor), actor.get("hp")], MUTED, 16)


func _name(member: Dictionary) -> String:
	var label: Variant = member.get("name")
	return str(label) if label is String and not label.is_empty() else str(member.get("instance_id", member.get("id", "队员")))


func _member_actions(cells: Array) -> void:
	for member in view.get("party", []):
		var member_id: String = member["instance_id"]
		_button(("◆ " if member["deployed"] else "◇ ") + _name(member), "member-" + member_id, _choose_member.bind(member_id))
		if member_id == selected_id:
			_input_action("撤下部署" if member["deployed"] else "加入部署", "deploy", [member_id, "off" if member["deployed"] else "on"])
			var has_selected_cell := false
			for cell in cells:
				var pos := Vector2i(int(cell[0]), int(cell[1]))
				var selected := pos == selected_cell
				has_selected_cell = has_selected_cell or selected
				_button(("已选 " if selected else "阵位 ") + "%d,%d" % [pos.x, pos.y], "cell-%d-%d" % [pos.x, pos.y], _board_cell.bind(pos))
			if has_selected_cell:
				_button("旋转朝向 · %d" % selected_facing, "facing", _rotate_facing)
				_input_action("确认阵位", "place", [member_id, str(selected_cell.x), str(selected_cell.y), str(selected_facing)])


func _summary() -> void:
	var summary: Variant = view.get("settlement")
	if summary is Dictionary:
		var result: String = summary.get("result", "归城")
		_label(actions, REASONS.get(result, result) + " · %d 场战斗" % int(summary.get("battles", 0)), INK, 19)
		for key in ["banked", "materials"]:
			if summary.has(key) and not summary[key].is_empty():
				var labels := {"copper": "铜", "crystal": "结晶", "iron": "铁", "herb": "草药", "supply": "补给"}
				var items: Array[String] = []
				for item in summary[key].keys():
					items.append(str(labels.get(item, item)) + " ×" + str(int(summary[key][item])))
				_label(actions, ("入库  " if key == "banked" else "材料  ") + "  /  ".join(items), MUTED, 16)
		for item in summary.get("returned_loose_equipment", []):
			_label(actions, "带回装备  %s · 尚未穿戴" % item.get("template_id", ""), MUTED, 16)
		for member in view.get("party", []):
			if int(member.get("injury_days", 0)) > 0:
				_label(actions, "%s  休整 %d 日" % [_name(member), int(member["injury_days"])], MUTED, 16)
	if not view.get("complete", false):
		_label(actions, "调查尚未交付。完成两战、D 点观察并安全归城。", MUTED, 16)


func _choose_member(id: String) -> void:
	selected_id = id
	selected_cell = Vector2i(-999, -999)
	for member in view.get("party", []):
		if member["instance_id"] == id:
			selected_facing = int(member["facing"])
			break
	_render()


func _rotate_facing() -> void:
	selected_facing = (selected_facing + 1) % 6
	_render()


func _board_cell(cell: Vector2i) -> void:
	if selected_id.is_empty() or client.busy or client.blocked or settings_open or captions_open or not confirmation.is_empty():
		return
	selected_cell = cell
	_render()


func _confirm() -> void:
	var action := confirmation
	confirmation = {}
	focus_key = action["back"]
	client.submit(action["command"], action["args"])


func _cancel_confirmation() -> void:
	focus_key = confirmation.get("back", "")
	confirmation = {}
	_render()


func _open_town() -> void:
	opened = true
	if captions_open:
		focus_key = "opening-replay"
	captions_open = false
	_render()


func _replay_opening() -> void:
	caption_index = 0
	captions_open = true
	_render()


func _show_settings() -> void:
	settings_open = true
	focus_key = "volume"
	_render()


func _close_settings() -> void:
	settings_open = false
	focus_key = "settings"
	_render()


func _toggle(key: String) -> void:
	settings[key] = not settings[key]
	_apply_volume()
	_save_settings()


func _cycle_volume() -> void:
	volume = volume - 25 if volume > 0 else 100
	_apply_volume()
	_save_settings()


func _apply_volume() -> void:
	audio.volume_db = WARNING_LEVEL_DB + linear_to_db(maxf(float(volume) / 100.0, 0.0001))
	if volume == 0 or settings["静音"] or not settings["音效"]:
		audio.stop()


func _save_settings() -> void:
	var file := ConfigFile.new()
	for entry in settings.keys():
		file.set_value("presentation", entry, settings[entry])
	file.set_value("presentation", "volume", volume)
	if file.save(data_dir.path_join("display.cfg")) != OK:
		notice.text = "本次显示设置已生效，设置文件未能保存。"
	_render()


func _load_settings() -> void:
	var file := ConfigFile.new()
	if file.load(data_dir.path_join("display.cfg")) == OK:
		for key in settings.keys():
			var found: Variant = file.get_value("presentation", key, settings[key])
			if found is bool:
				settings[key] = found
		var stored_volume: Variant = file.get_value("presentation", "volume", 100)
		if stored_volume is int and stored_volume in [0, 25, 50, 75, 100]:
			volume = stored_volume


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.is_echo() and (event.is_action("ui_accept") or event.is_action("ui_cancel")):
		get_viewport().set_input_as_handled()
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.double_click:
		get_viewport().set_input_as_handled()


func _unhandled_key_input(event: InputEvent) -> void:
	if not event.is_action_pressed("ui_cancel"):
		return
	if settings_open:
		_close_settings()
	elif not confirmation.is_empty():
		_cancel_confirmation()
	else:
		return
	get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_quit()


func _quit() -> void:
	if client != null and client.busy:
		notice.text = "等待正在提交的操作完成后再退出。"
		return
	get_tree().quit()

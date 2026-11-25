extends Control

const Pipe = preload("res://pipe_client.gd")
const Board = preload("res://hex_board.gd")
const ArchivePage = preload("res://archive_page.gd")
const OpeningArt = preload("res://opening_art.gd")
const SearchChart = preload("res://search_chart.gd")
const CombatTile = preload("res://combat_tile.gd")
const CombatLog = preload("res://combat_log.gd")
const ADO_HUD_PORTRAIT = preload("res://assets/fortress/ado_hud.png")
const INK := Color("e9dbc0")
const MUTED := Color("a7b8ac")
const GOLD := Color("e7bd75")
const ALERT := Color("f7ac8e")
const PLACES := {"I": "入口", "A": "林道接敌", "B_SUPPORT": "护运站", "B_MATERIAL": "材料匣", "C": "歇脚点", "D": "远眺点", "G": "根口", "X": "归路"}
const STANCES := {"advance": "推进", "hold": "固守", "flank": "包抄", "evade": "避险"}
const PANEL_LARGE_TEXT := {15: 20, 16: 22, 17: 23, 18: 24, 19: 26, 23: 30, 24: 31, 26: 33}
const GEAR_SLOTS := {"weapon": "武器", "armor": "护甲"}
const GEAR_STATS := {"hp": "生命上限", "physical_attack": "物攻", "magic_attack": "魔攻",
	"healing_power": "治疗强度", "physical_defense": "物防", "magic_defense": "魔防"}
const ADO_MOVE_NAMES := {"MG01-A": "断誓横阵", "MG01-B": "留守壁垒", "MG01-C": "归队点名"}
const ADO_CUES := {
	"MG01-A": preload("res://assets/fortress/audio/mg01-a.wav"),
	"MG01-B": preload("res://assets/fortress/audio/mg01-b.wav"),
	"MG01-C": preload("res://assets/fortress/audio/mg01-c.wav"),
	"whistle": preload("res://assets/fortress/audio/whistle.wav"),
}
const WARNING_CUE := preload("res://assets/fortress/audio/warning.wav")
const REASONS := {"SAFE_RETURN": "安全归城", "COMBAT_RETREAT": "追击后撤退", "DEFEAT": "战斗败北", "VICTORY": "胜利", "RETREAT": "撤退",
	"RESCUE_SUCCESS": "成功救回队员", "SEARCH_RETURN": "调查记录已带回", "LOCATION_CONFIRMED": "转运点已确认", "SEARCH_EXPIRED": "调查归城时已超过搜救期限"}
const WARNING_LEVEL_DB := -9.0
const CARGO_NAMES := {"copper": "铜", "crystal": "结晶", "iron": "铁料", "fiber": "木纤", "herb": "草药",
	"supply": "补给", "crystal_shard": "晶屑"}
const BOOK_STAGES := {"B": "基础", "I": "进阶", "E": "专精", "X": "专属"}
const BATTLE_PACES := ["慢速", "常速", "快速"]
const BATTLE_DELAYS := [Vector2(0.58, 0.96), Vector2(0.30, 0.68), Vector2(0.18, 0.56)]
const MEMORY_REPLY_SECONDS := 4.5

var client: Node
var board: Control
var actions: VBoxContainer
var area_title: Label
var warning: Label
var warning_footer: ScrollContainer
var _warning_plate: PanelContainer
var _frame: PanelContainer
var _side_panel: PanelContainer
var _field_style := false
var _field_frame: StyleBoxFlat
var _field_panel: StyleBoxFlat
var _standard_frame: StyleBoxFlat
var _standard_panel: StyleBoxFlat
var _field_toolbar: PanelContainer
var _battle_controls: HBoxContainer
var _contact_controls: HBoxContainer
var _subtitle_row: HBoxContainer
var _field_title_font: Font
var location: Label
var save_info: Label
var notice: Label
var _navigation_committed := false
var subtitles: Label
var dialogue_next: Button
var dialogue_skip: Button
var audio: AudioStreamPlayer
var case_name := "rg01"
var data_dir: String
var bundle: String
var model: Dictionary = {}
var view: Dictionary = {}
var selected_id := ""
var selected_cell := Vector2i(-999, -999)
var selected_facing := 0
var deployment_cells_open := false
var confirmation: Dictionary = {}
var seen_warnings: Dictionary = {}
var sound_count := 0
var ado_cues_seen: Dictionary = {}
var ado_sounds: Dictionary = {}
var ado_sound_counts: Dictionary = {}
var _receipt_sounds: Array[String] = []
var save_version := -1
var settings := {"音效": true, "音乐": true, "静音": false, "大字": false, "低动态": false, "战斗数字": true}
var volume := 100
var settings_open := false
var opened := false
var captions_open := false
var _asked_about_old_company := false
var town_tab := "chapter"
var construction_project := ""
var outfit_selection: Array[String] = []
var outfit_editing := false
var chapter_history_open := false
var _archive_list_scroll := 0
var _archive_record_id := ""
var _archive_page: ArchivePage
var remembrance_history_open := false
var field_gear_open := false
var field_books_open := false
var field_items_open := false
var pouch_item := ""
var pouch_targets: Array[String] = []
var bookstore_open := false
var bookstore_stage := "B"
var bookstore_book := ""
var book_research_open := false
var tactics_member_id := ""
var _book_swap_key := ""
var books_open := false
var _previewed_book: Dictionary = {}
var whistle_open := false
var caption_index := 0
var _opening_art: OpeningArt
var _search_chart: SearchChart
var _overlook_open := false
var _overlook_mat := ColorRect.new()
var _overlook_picture := TextureRect.new()
var initial_snapshot := true
var command_buttons: Dictionary = {}
var ui_font: Font
var focus_key := ""
var profile_panels := false
var panel_timings: Array[Dictionary] = []
var _action_scroll: ScrollContainer
var _combat_actions: VBoxContainer
var _general_actions: VBoxContainer
var _confirmation_actions: VBoxContainer
var _combat_buttons: Dictionary = {}
var _general_buttons: Dictionary = {}
var _confirmation_buttons: Dictionary = {}
var _confirmation_text: Label
var _battle_heading: Label
var _battle_plans: Label
var _battle_rescue: Label
var _battle_roster: VBoxContainer
var _enemy_heading: Label
var _ally_heading: Label
var _leaders: VBoxContainer
var _foes: GridContainer
var _allies: GridContainer
var _battle_rows: Dictionary = {}
var _battle_log_open := false
var _live_battle_log: CombatLog
var _battle_detail: Label
var _battle_inspected := ""
var _combatants: Dictionary = {}
var _live_impacts: Dictionary = {}
var _battle_timer: Timer
var _playback_battle := ""
var _playback_running := false
var _default_playback := true
var _committed_memory_window := ""
var _memory_reply := ""
var _new_warning := false
var _battle_pace := 1
var _window_was_minimized := false
var _close_after_save := false
var _closing := false
var _restore_after_reconnect := false
var _logged_location: Array = []


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
		elif item.begins_with("--smoke="):
			_default_playback = "--auto-combat-check" in OS.get_cmdline_user_args()
	var check := RegEx.create_from_string("^[A-Za-z0-9_-]{1,80}$")
	if check.search(case_name) == null:
		push_error("Invalid P06 session name")
		get_tree().quit(2)
		return
	var build_id := FileAccess.get_file_as_string(bundle.path_join("release-id.txt")).strip_edges() \
		if FileAccess.file_exists(bundle.path_join("release-id.txt")) else "unlabelled"
	print("P06 start build=%s pid=%d case=%s" % [build_id, OS.get_process_id(), case_name])
	_load_settings()
	if DisplayServer.get_name() != "headless":
		# The stage connects its asset dispatcher when the board enters the tree.
		get_tree().process_frame.connect(_sync_window_minimize)
	_build()
	_battle_timer = Timer.new()
	_battle_timer.one_shot = true
	add_child(_battle_timer)
	_battle_timer.timeout.connect(_advance_automatically)
	get_window().focus_entered.connect(_resume_visible_presentation)
	get_window().focus_exited.connect(_suspend_window_input)
	client = Pipe.new()
	add_child(client)
	_build_combat_actions()
	client.refreshed.connect(_refresh)
	client.notice.connect(_notice)
	client.busy_changed.connect(_busy)
	client.contact_model_hint.connect(board.stage.prefetch_contact_models)
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


func _build_field_style() -> void:
	_field_frame = _box("1c1713", "3c3329", 0, 17)
	_field_panel = _box("241c17", "49382b", 4, 12)
	theme.set_type_variation("FieldButton", "Button")
	theme.set_stylebox("normal", "FieldButton", _box("332b22", "594b39", 2, 8))
	theme.set_stylebox("hover", "FieldButton", _box("4a3d2d", "947b58", 2, 8))
	theme.set_stylebox("pressed", "FieldButton", _box("544329", "c09c63", 2, 8))
	theme.set_stylebox("disabled", "FieldButton", _box("2b251f", "413830", 2, 8))
	theme.set_color("font_disabled_color", "FieldButton", Color("a09482"))
	theme.set_type_variation("FieldPrimary", "FieldButton")
	theme.set_stylebox("normal", "FieldPrimary", _box("d8b982", "f1d499", 2, 9))
	theme.set_stylebox("hover", "FieldPrimary", _box("eed3a1", "ffebb9", 2, 9))
	theme.set_stylebox("pressed", "FieldPrimary", _box("c19c62", "f1d499", 2, 9))
	var focus := _box("00000000", "f4d492", 2, 8)
	focus.set_border_width_all(2)
	theme.set_stylebox("focus", "FieldButton", focus)
	var primary_focus := focus.duplicate() as StyleBoxFlat
	primary_focus.border_color = Color("72502d")
	primary_focus.set_border_width_all(3)
	theme.set_stylebox("focus", "FieldPrimary", primary_focus)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		theme.set_color(state, "FieldPrimary", Color("2b2118"))
	theme.set_type_variation("FieldUnit", "FieldButton")
	var folio := _box("262119", "4e4132", 0, 6)
	folio.set_border_width_all(0)
	folio.set_border_width(SIDE_BOTTOM, 1)
	theme.set_stylebox("normal", "FieldUnit", folio)
	for type in ["CombatTile", "CombatLeader"]:
		theme.set_type_variation(type, "FieldButton")
		var leader: bool = type == "CombatLeader"
		theme.set_stylebox("normal", type, _box("38241c" if leader else "2e251d", "8a5940" if leader else "524033", 4, 3))
		theme.set_stylebox("hover", type, _box("443124", "a18154", 4, 3))
		theme.set_stylebox("pressed", type, _box("3b3327", "e3b878", 4, 3))
		theme.set_stylebox("hover_pressed", type, _box("443625", "e3b878", 4, 3))
	theme.set_type_variation("FieldScroll", "VScrollBar")
	var scroll_track := _box("00000000", "00000000", 1, 0)
	scroll_track.set_content_margin(SIDE_LEFT, 2)
	scroll_track.set_content_margin(SIDE_RIGHT, 2)
	theme.set_stylebox("scroll", "FieldScroll", scroll_track)
	theme.set_stylebox("scroll_focus", "FieldScroll", scroll_track)
	for state in ["grabber", "grabber_highlight", "grabber_pressed"]:
		var grip := _box("8a6e50" if state == "grabber" else "c09d6c", "00000000", 1, 0)
		grip.set_content_margin(SIDE_LEFT, 2)
		grip.set_content_margin(SIDE_RIGHT, 2)
		theme.set_stylebox(state, "FieldScroll", grip)


func _apply_field_style(active: bool) -> void:
	if _field_style == active:
		return
	_field_style = active
	_frame.add_theme_stylebox_override("panel", _field_frame if active else _standard_frame)
	_side_panel.add_theme_stylebox_override("panel", _field_panel if active else _standard_panel)
	_side_panel.custom_minimum_size.x = 350.0 if active else 365.0
	_action_scroll.get_v_scroll_bar().theme_type_variation = &"FieldScroll" if active else &""
	if active:
		area_title.add_theme_font_override("font", _field_title_font)
	else:
		area_title.remove_theme_font_override("font")
	location.add_theme_color_override("font_color", Color("c2ae91") if active else MUTED)
	for key in _confirmation_buttons:
		var button: Button = _confirmation_buttons[key]
		button.theme_type_variation = ("FieldPrimary" if key == "confirm" else "FieldButton") if active else &""
	for button in [dialogue_next, dialogue_skip]:
		button.theme_type_variation = &"FieldButton" if active else &""


func _build() -> void:
	var system_font := SystemFont.new()
	system_font.font_names = PackedStringArray(["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI"])
	ui_font = system_font
	var title_font := SystemFont.new()
	title_font.font_names = PackedStringArray(["KaiTi", "SimSun", "Noto Serif CJK SC"])
	_field_title_font = title_font
	theme = Theme.new()
	theme.default_font = ui_font
	theme.default_font_size = 16
	for pixels: int in PANEL_LARGE_TEXT:
		theme.set_type_variation("PanelText%d" % pixels, &"Label")
	_set_panel_text_size(settings["大字"])
	theme.set_stylebox("normal", "Button", _box("23373a", "46615e", 7, 10))
	theme.set_stylebox("hover", "Button", _box("324c4b", "81a99c", 7, 10))
	theme.set_stylebox("pressed", "Button", _box("51462e", "d5a358", 7, 10))
	theme.set_stylebox("focus", "Button", _box("00000000", "e7bd75", 7, 10))
	theme.set_stylebox("disabled", "Button", _box("182628", "2c3c39", 7, 10))
	for group in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		theme.set_color(group, "Button", INK)
	_build_field_style()

	_frame = PanelContainer.new()
	_frame.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_standard_frame = _box("0f1819", "24312c", 0, 25)
	_frame.add_theme_stylebox_override("panel", _standard_frame)
	add_child(_frame)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 12)
	_frame.add_child(stack)

	var header := HBoxContainer.new()
	stack.add_child(header)
	var title := VBoxContainer.new()
	title.size_flags_horizontal = SIZE_EXPAND_FILL
	header.add_child(title)
	area_title = _label(title, "火种计划  /  灰栎边道", INK, 31)
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
	map_column.add_theme_constant_override("separation", 4)
	body.add_child(map_column)
	board = Board.new()
	board.font = ui_font
	board.show_models = "--pieces" not in OS.get_cmdline_user_args()
	board.show_spear = "--spear-pieces" not in OS.get_cmdline_user_args()
	board.custom_minimum_size = Vector2(370, 330)
	board.size_flags_vertical = SIZE_EXPAND_FILL
	board.cell_selected.connect(_board_cell)
	board.deployment_dropped.connect(_deploy_drop)
	board.deployment_selected.connect(_choose_member)
	board.deployment_withdrawn.connect(_deploy_to_reserve)
	board.battle_actor_selected.connect(_inspect_battle_actor)
	board.route_site_selected.connect(_route_site)
	board.overlook_requested.connect(func() -> void: _activate_board_action("overlook-inspect"))
	board.town_shortcut_selected.connect(_activate_town_shortcut)
	board.deployment_target = _deployment_target
	map_column.add_child(board)
	_search_chart = SearchChart.new()
	board.add_child(_search_chart)
	_search_chart.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_search_chart.clue_selected.connect(func(clue: String) -> void:
		_activate_board_action("rescue investigate inspect " + clue))
	_overlook_mat.color = Color("172222")
	_overlook_mat.hide()
	board.add_child(_overlook_mat)
	_overlook_mat.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlook_picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_overlook_picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_overlook_picture.mouse_filter = MOUSE_FILTER_IGNORE
	_overlook_mat.add_child(_overlook_picture)
	_overlook_picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 12)
	_archive_page = ArchivePage.new()
	board.add_child(_archive_page)
	_archive_page.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_opening_art = OpeningArt.new()
	_opening_art.mouse_filter = Control.MOUSE_FILTER_STOP
	_opening_art.hide()
	board.add_child(_opening_art)
	_opening_art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_warning_plate = PanelContainer.new()
	var warning_style := _box("2d211a", "74513a", 2, 2)
	warning_style.set_border_width(SIDE_LEFT, 3)
	warning_style.set_content_margin(SIDE_LEFT, 11)
	_warning_plate.add_theme_stylebox_override("panel", warning_style)
	_warning_plate.hide()
	map_column.add_child(_warning_plate)
	warning_footer = ScrollContainer.new()
	warning_footer.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	warning_footer.custom_minimum_size.y = 56.0
	_warning_plate.add_child(warning_footer)
	warning = _label(warning_footer, "", Color("ffcd9c"), 17)
	warning.size_flags_horizontal = SIZE_EXPAND_FILL
	warning.size_flags_vertical = SIZE_EXPAND_FILL
	warning.mouse_filter = Control.MOUSE_FILTER_PASS
	warning.custom_minimum_size.y = 28.0
	warning.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	warning.add_theme_constant_override("line_spacing", 2)
	warning.visible = false

	_side_panel = PanelContainer.new()
	_side_panel.custom_minimum_size.x = 365
	_standard_panel = _box("172527", "41524c", 9, 13)
	_side_panel.add_theme_stylebox_override("panel", _standard_panel)
	body.add_child(_side_panel)
	_action_scroll = ScrollContainer.new()
	_action_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_action_scroll.follow_focus = true
	_side_panel.add_child(_action_scroll)
	var pages := VBoxContainer.new()
	pages.size_flags_horizontal = SIZE_EXPAND_FILL
	_action_scroll.add_child(pages)
	pages.minimum_size_changed.connect(_refresh_action_scroll_bounds)
	_general_actions = VBoxContainer.new()
	_combat_actions = VBoxContainer.new()
	_confirmation_actions = VBoxContainer.new()
	for page in [_general_actions, _combat_actions, _confirmation_actions]:
		page.add_theme_constant_override("separation", 6)
		pages.add_child(page)
	_combat_actions.hide()
	_confirmation_actions.hide()
	actions = _confirmation_actions
	command_buttons = _confirmation_buttons
	_label(actions, "确认操作", GOLD, 23)
	_confirmation_text = _label(actions, "", INK, 19)
	_button("取消", "cancel", _cancel_confirmation)
	_button("确认", "confirm", _confirm)
	_button("设置", "settings", _show_settings)
	_button("退出样段", "quit", _quit)
	actions = _general_actions
	command_buttons = _general_buttons

	_field_toolbar = PanelContainer.new()
	_field_toolbar.custom_minimum_size.y = 49.0
	_field_toolbar.add_theme_stylebox_override("panel", _box("2b2119", "644b34", 3, 5))
	_field_toolbar.hide()
	stack.add_child(_field_toolbar)
	_battle_controls = HBoxContainer.new()
	_battle_controls.add_theme_constant_override("separation", 8)
	_field_toolbar.add_child(_battle_controls)
	_contact_controls = HBoxContainer.new()
	_contact_controls.add_theme_constant_override("separation", 8)
	_field_toolbar.add_child(_contact_controls)
	_subtitle_row = HBoxContainer.new()
	_subtitle_row.add_theme_constant_override("separation", 10)
	stack.add_child(_subtitle_row)
	subtitles = _label(_subtitle_row, "", INK, 18)
	subtitles.size_flags_horizontal = SIZE_EXPAND_FILL
	subtitles.custom_minimum_size.y = 32
	dialogue_next = _button("下一句", "dialogue next", _advance_dialogue.bind("next"), false, _subtitle_row)
	dialogue_skip = _button("跳过对白", "dialogue skip", _advance_dialogue.bind("skip"), false, _subtitle_row)
	for button in [dialogue_next, dialogue_skip]:
		button.autowrap_mode = TextServer.AUTOWRAP_OFF
		button.size_flags_vertical = SIZE_SHRINK_CENTER
		button.hide()
	notice = _label(stack, "正在连接旁载运行时…", MUTED, 15)
	audio = AudioStreamPlayer.new()
	audio.stream = WARNING_CUE
	add_child(audio)
	for key in ADO_CUES:
		var voice := AudioStreamPlayer.new()
		voice.stream = ADO_CUES[key]
		add_child(voice)
		ado_sounds[key] = voice
	_apply_volume()


func _set_panel_text_size(large: bool) -> void:
	for pixels: int in PANEL_LARGE_TEXT:
		theme.set_font_size("font_size", "PanelText%d" % pixels, PANEL_LARGE_TEXT[pixels] if large else pixels)


func _label(parent: Control, text: String, color: Color, pixels: int) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", color)
	if pixels in PANEL_LARGE_TEXT and (_confirmation_actions != null and parent == _confirmation_actions
			or _general_actions != null and (parent == _general_actions or _general_actions.is_ancestor_of(parent))):
		label.theme_type_variation = "PanelText%d" % pixels
	else:
		label.add_theme_font_size_override("font_size", pixels)
	parent.add_child(label)
	return label


func _new_button(text: String, key: String, fn: Callable, enabled: bool, control: Button = null) -> Button:
	var entry := control if control != null else Button.new()
	entry.text = text
	entry.alignment = HORIZONTAL_ALIGNMENT_LEFT
	entry.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	entry.disabled = not enabled
	entry.focus_mode = Control.FOCUS_ALL
	if _field_style or actions == _combat_actions:
		entry.theme_type_variation = "FieldPrimary" if key in ["fight", "combat-playback"] else "FieldButton"
		if entry.theme_type_variation == &"FieldPrimary":
			entry.alignment = HORIZONTAL_ALIGNMENT_CENTER
	entry.focus_entered.connect(func() -> void: focus_key = key)
	entry.pressed.connect(fn)
	return entry


func _button(text: String, key: String, fn: Callable, enabled := true, parent: Container = null) -> Button:
	var entry := _new_button(text, key, fn, enabled)
	(actions if parent == null else parent).add_child(entry)
	command_buttons[key] = entry
	return entry


func _input_action(text: String, command: String, args: Array, consequence := "", allowed := true,
		parent: Container = null, focus_after := "") -> Button:
	var key := " ".join([command] + args)
	var control := _button(text, key, func() -> void:
		if consequence.is_empty():
			if client.submit(command, args):
				if command == "move" and not args.is_empty():
					board.prepare_field_art(str(args[0]))
				if not focus_after.is_empty():
					focus_key = focus_after
		else:
			confirmation = {"command": command, "args": args, "text": consequence, "back": key}
			focus_key = "cancel"
			_render()
		, allowed and not client.busy and not client.blocked, parent)
	if parent != null:
		control.autowrap_mode = TextServer.AUTOWRAP_OFF
	return control


func _refresh(row: Dictionary) -> void:
	_book_swap_key = ""
	if _restore_after_reconnect:
		board.reset_battle_presentation()
		_live_impacts = {}
		_restore_after_reconnect = false
		print("P06 reconnected version=%d" % int(row.state_version))
	var previous: Variant = view.get("settlement")
	var previous_battle: Variant = view.get("battle_view")
	var previous_whistle: String = view.get("whistle", {}).get("stage", "")
	var previous_chapter: Dictionary = view.get("chapter", {})
	var previous_hunt: Dictionary = view.get("hunt", {})
	var returned_report := _pending_hunt_report(view, true)
	var previous_battle_memory: Dictionary = view.get("battle_memory", {})
	var was_commissioned: bool = view.get("commissioned", false)
	var previous_phase: String = view.get("phase", "")
	var returned_scouting: bool = view.get("scouting", {}).get("delivered_here", false)
	var previous_map: Variant = model.get("map")
	model = row.get("presentation", {})
	view = model.get("slice", {})
	if _navigation_committed:
		_show_navigation_receipt(previous_map)
		_navigation_committed = false
	var battle: Variant = view.get("battle_view")
	var phase: String = view.get("phase", "")
	_memory_reply = ""
	if not _committed_memory_window.is_empty():
		var receipt: Dictionary = view.get("hunt", {}).get("memory_reply", {}) if phase == "TOWN" else (
			battle.get("memory_reply", {}) if battle is Dictionary else {})
		if receipt.get("id") == _committed_memory_window:
			var line: Dictionary = receipt.line
			_memory_reply = "%s   %s" % [line.speaker, line.text]
		_committed_memory_window = ""
	if phase not in ["TOWN", "EXPLORE"]:
		tactics_member_id = ""
	if phase != "TOWN" or view.get("chapter", {}).get("books", []).is_empty():
		books_open = false
		_previewed_book = {}
	if phase != "EXPLORE":
		field_gear_open = false
		field_books_open = false
		if field_items_open:
			field_items_open = false
			pouch_item = ""
			pouch_targets.clear()
	var in_battle := phase == "BATTLE" and battle is Dictionary
	var context := [phase, view.get("region", ""), view.get("site", ""),
		battle.get("encounter", "") if in_battle else ""]
	if context != _logged_location:
		_logged_location = context
		print("P06 state version=%d phase=%s region=%s site=%s encounter=%s tick=%d" % [
			int(row.state_version), context[0], context[1], context[2], context[3],
			int(battle.tick) if in_battle else -1])
	if not battle is Dictionary or not previous_battle is Dictionary or previous_battle.id != battle.id:
		_live_impacts = {}
	elif int(battle.tick) > int(previous_battle.tick):
		_live_impacts = battle.get("impacts", {}) if row.get("status") == "COMMITTED" else {}
	_combatants.clear()
	if battle is Dictionary:
		for actor in battle.actors:
			_combatants[actor.id] = actor
	var live_id: String = battle.id if in_battle else ""
	if live_id != _playback_battle:
		_playback_battle = live_id
		_playback_running = _default_playback and not live_id.is_empty() and not initial_snapshot
		_battle_inspected = ""
		_battle_log_open = false
		board.focus_battle_actor("")
	if phase == "TOWN":
		var chapter: Dictionary = view.get("chapter", {})
		var report := _pending_hunt_report(view) if initial_snapshot else returned_report
		if previous is Dictionary and previous.get("result") in ["DEFEAT", "RESCUE_SUCCESS", "SEARCH_RETURN", "LOCATION_CONFIRMED", "SEARCH_EXPIRED"] and not view.get("rescue", {}).is_empty():
			town_tab = "rescue"
		elif not report.is_empty() and (initial_snapshot or previous_phase == "RETURNED"):
			town_tab = "chapter"
			focus_key = "quest report %s CONFIRM" % report.id
			notice.text = ""
		elif (initial_snapshot or returned_scouting) and not chapter.is_empty() and not chapter.archived:
			town_tab = "chapter"
			focus_key = "quest archive CONFIRM" if chapter.reviewed else "quest review CONFIRM"
		elif not previous_chapter.is_empty() and row.get("status") == "COMMITTED":
			if not previous_chapter.archived and chapter.get("archived", false):
				focus_key = "town-expedition"
			elif not previous_chapter.reviewed and chapter.get("reviewed", false):
				focus_key = "quest archive CONFIRM"
			elif previous_chapter.book_selected.is_empty() and not chapter.get("book_selected", {}).is_empty():
				notice.text = "「%s」已放入书库。" % chapter.book_selected.name
				focus_key = "chapter-history"
	if row.get("files", {}).get("save.json") != null:
		save_version = int(view.get("save_version", 0))
	if int(row["state_version"]) > 0 or view.get("commissioned", false):
		opened = true
	if initial_snapshot and notice.text in ["正在连接旁载运行时…", "正在重新连接并核对存档…"]:
		notice.text = ""
	if not was_commissioned and row.get("status") == "COMMITTED" and not view.get("commission_receipt", {}).is_empty():
		notice.text = "委任已接受。" + _commission_grant_text(view.commission_receipt)
		focus_key = "tutorial recommend CONFIRM"
	if phase == "TOWN" and not previous_whistle.is_empty() and row.get("status") == "COMMITTED":
		var next: String = view.get("whistle", {}).get("stage", "")
		if next != previous_whistle:
			notice.text = ""
			match next:
				"witness": focus_key = "quest MG01 witness"
				"collect": focus_key = "quest MG01 collect CONFIRM"
				"done":
					var hunt: Dictionary = view.get("hunt", {})
					if hunt.get("defeated", false) and not hunt.awakened and hunt.evidence:
						focus_key = "remember MG01"
					else:
						focus_key = "town-expedition" if view.get("chapter", {}).get("archived", false) else "whistle-section"
	if phase == "TOWN":
		var hunt: Dictionary = view.get("hunt", {})
		var recall: Dictionary = hunt.get("memory", {})
		var prior_recall: Dictionary = previous_hunt.get("memory", {})
		if recall.get("id") != prior_recall.get("id"):
			if recall.is_empty():
				focus_key = "remembrance-history" if hunt.awakened else "remember MG01"
			else:
				focus_key = "remember %s %s" % [recall.choice, recall.id] if recall.enabled else "remember close"
	elif phase == "BATTLE":
		var memory: Dictionary = view.get("battle_memory", {})
		if not memory.is_empty() and memory.get("id") != previous_battle_memory.get("id"):
			focus_key = "memory %s %s" % [memory.choice if memory.enabled else "skip", memory.id]
	_receipt_sounds.clear()
	_set_danger()
	_set_ado_audio()
	initial_snapshot = false


func _set_danger() -> void:
	var current: Variant = model.get("danger")
	var lines: Array[String] = []
	var location_details: Array[String] = []
	var unsounded := false
	if current is Dictionary:
		var numbers := Board.warning_numbers(current)
		for intent in current.get("actions", []):
			if intent.get("side") != "enemy":
				continue
			var key := "%s/%s" % [current["battle_id"], intent["action_id"]]
			if not seen_warnings.has(key):
				seen_warnings[key] = true
				unsounded = true
			var locked: Array = intent.get("locked_cells", [])
			var target: Variant = intent.get("target")
			var where := "%d 格范围" % locked.size() if not locked.is_empty() else "攻击起手"
			if target != null and locked.is_empty():
				where = "自身" if target == intent.actor_id else "目标 " + _combatant_name(str(target))
			var move_id: String = intent.get("move_id", "预警")
			if move_id == "MG01-B":
				where = "蓄势护盾"
			var move_name := _combat_move(move_id)
			var remaining := maxi(0, int(intent.get("due", current["tick"])) - int(current["tick"]))
			var timer := "%d 拍后" % remaining if remaining > 0 else "本拍释放"
			var marker := "[%d]" % numbers[intent.action_id] if numbers.has(intent.action_id) else "△"
			lines.append("%s  %s   ·   %s   ·   %s   ·   %s" % [marker, move_name, timer, _combatant_name(intent.actor_id), where])
			if not locked.is_empty():
				var cells: Array[String] = []
				for point in locked:
					cells.append("%d,%d" % [int(point[0]), int(point[1])])
				location_details.append("%s · %s" % [move_name, " / ".join(cells)])
	warning.text = "\n".join(lines)
	warning.tooltip_text = "\n".join(location_details)
	warning.visible = not lines.is_empty()
	_warning_plate.self_modulate.a = 1.0 if warning.visible else 0.0
	_new_warning = unsounded
	if lines.is_empty():
		audio.stop()
	elif unsounded and not initial_snapshot and _effects_enabled():
		_receipt_sounds.append("warning")


func _set_ado_audio() -> void:
	var battle: Variant = view.get("battle_view")
	if battle is Dictionary and battle.get("encounter") == "BATTLE-MG01":
		for event in battle.events:
			var key: String = event.get("move", "")
			if event.type == "release" and ADO_MOVE_NAMES.has(key):
				_play_ado_cue(key, event.event_id)
	var whistle: String = view.get("whistle_cue", "")
	if not whistle.is_empty():
		_play_ado_cue("whistle", whistle)


func _play_ado_cue(key: String, event_id: String) -> void:
	if ado_cues_seen.has(event_id):
		return
	ado_cues_seen[event_id] = true
	if not initial_snapshot and _effects_enabled():
		_receipt_sounds.append(key)


func _effects_enabled() -> bool:
	return volume > 0 and not settings["静音"] and settings["音效"]


func _flush_receipt_sounds() -> void:
	if _receipt_sounds.is_empty() or client.busy or client.blocked or settings_open or captions_open \
			or not confirmation.is_empty() or _window_was_minimized or not _window_allows_playback():
		return
	if _effects_enabled():
		for key in _receipt_sounds:
			if key == "warning":
				audio.play()
				sound_count += 1
			else:
				ado_sounds[key].play()
				ado_sound_counts[key] = int(ado_sound_counts.get(key, 0)) + 1
	_receipt_sounds.clear()


func _notice(message: String, command := "", args: Array = []) -> void:
	_navigation_committed = command in ["move", "walkto", "interact"]
	if not initial_snapshot and command in ["memory", "remember"] and args.size() == 2 \
			and args[0] in ["evidence", "retain"]:
		_committed_memory_window = args[1]
	var tutorial_action: String = args[0] if command == "tutorial" and not args.is_empty() else ""
	var book_setup: bool = command == "book" and not args.is_empty() \
		and args[0] in ["learn", "equip", "queue", "auto", "main"]
	if _navigation_committed or command in ["dialogue", "plan", "memory", "remember"] \
			or tutorial_action in ["plan", "support", "materials", "cache"] or book_setup:
		notice.text = ""
	elif tutorial_action == "observe":
		notice.text = "远眺记录已保存。"
	elif tutorial_action == "start":
		notice.text = "已进入灰栎边道。点击道路相连的地点前进。"
	elif command == "book" and args == ["claim"]:
		notice.text = "战利书已放入行囊。"
	elif command == "book" and args == ["drop"]:
		notice.text = "已放弃此处战利书。"
	elif command == "book" and not args.is_empty() and args[0] == "buy":
		notice.text = "购买的技能书已入库。"
	elif command == "book" and args.size() == 2 and args[0] == "target":
		notice.text = "已清除技能书定向。" if args[1] == "clear" else "技能书定向已保存，将在出发时锁定。"
		focus_key = "bookstore" if bookstore_book.is_empty() else "bookstore-list"
	elif command == "book" and args.size() == 3 and args[0] == "task":
		notice.text = "研习委托已接取。"
		focus_key = "book-research"
	elif command == "book" and args.size() == 4 and args[0] == "choice" and str(args[1]).begins_with("SB-T"):
		notice.text = "研习奖励已放入书库。"
		focus_key = "book-research"
	elif command == "choose" and args == ["BOOK"]:
		notice.text = "手册已放入行囊。"
	elif command == "facility":
		match args[0]:
			"build": notice.text = "已付款开工，后续行动结算推进施工。"
			"cancel": notice.text = "施工已撤销，退款已入库。"
			"pause": notice.text = "施工已暂停。"
			"resume": notice.text = "施工已恢复。"
		focus_key = "construction-list"
	elif command == "service":
		notice.text = "补训已付款。该成员留城，下次行动结算获得 1 经验。"
		focus_key = "rest CONFIRM"
	elif command == "outfit":
		notice.text = "防御整备已付款，等待下次出发。" if args[0] == "buy" else "已保存新的整备对象。"
		outfit_selection.clear()
		outfit_editing = false
		focus_key = "outfit-edit"
	elif command in ["craft", "stash", "take", "use", "discard"]:
		var messages := {"craft": "已制作 1 份，放入携行袋。", "stash": "已存入暮汀物品库。",
			"take": "已取出 1 份，放入携行袋。", "use": "已使用 1 份随身道具。", "discard": "已丢弃 1 份随身道具。"}
		notice.text = messages[command]
		pouch_targets.clear()
		focus_key = "pouch-list"
	elif command == "supply":
		notice.text = "已取消材料委托。" if args[1] == "off" else "已登记材料委托。常规远征出发时锁定领取地点。"
	elif command == "quest" and args == ["commission", "CONFIRM"]:
		notice.text = "委任记录已核对。"
	elif message.begins_with("进入逐拍战斗") or message.begins_with("战斗推进完成。未分胜负可继续"):
		notice.text = ""
	elif message.begins_with("搜救所·失联调查"):
		notice.text = ""
	else:
		notice.text = message.trim_prefix("战斗推进完成。未分胜负可继续；")


func _show_navigation_receipt(previous_map: Variant) -> void:
	var site: Variant = view.get("site")
	var current_map: Variant = model.get("map")
	if view.get("route", {}).get("contact_pending", false):
		notice.text = "接敌边界 · %s。可以调整部署、确认开战或退回。" % _site_name(str(site), "前方")
	elif site is String and not site.is_empty():
		notice.text = "已到达%s。" % _site_name(site, "现场")
	elif previous_map is Dictionary and current_map is Dictionary and current_map.steps == previous_map.steps:
		notice.text = "队伍停在原处。"
	else:
		notice.text = "队伍已沿道路前进。"


func _busy(value: bool) -> void:
	if value:
		_battle_timer.stop()
		board.deployment_open = false
		board.set_route_input(false)
		board.set_town_shortcuts({})
		for key in command_buttons:
			command_buttons[key].disabled = key != "combat-playback" and not key.begins_with("battle-unit-") \
				and (key != "battle-log" or view.get("phase") != "BATTLE")
		save_info.text = "正在处理"
	elif _close_after_save:
		_quit.call_deferred()
	else:
		_render()
		board.finish_field_art_prefetch()


func _display_location() -> String:
	var phase: String = view.get("phase", "TOWN")
	if phase in ["TOWN", "RETURNED", "FAILED", "FIN_C"]:
		return "暮汀   /   行动日 %d   /   补给 %d" % [int(view.get("day", 0)), int(view.get("supply", 0))]
	if phase == "MISSING_SEARCH":
		return "失联调查   /   计划第 %d 日归城" % int(view.rescue.active.returns_on)
	var site := str(view.get("site", ""))
	var label := "巡队转运点" if site == "RESCUE" else _site_name(site, "已探索道路")
	if phase == "EXPLORE" and view.get("route", {}).get("contact_pending", false):
		return label + "   /   布阵"
	var danger: Variant = model.get("danger")
	if danger is Dictionary:
		return "%s   /   战斗第 %d 拍" % [label, int(danger["tick"])]
	return str(view.get("region_name", "侦路")) + "   /   " + label if not view.get("tutorial_area", false) else "侦路   /   " + label


func _site_name(site: String, fallback: String) -> String:
	if view.get("tutorial_area", false):
		return PLACES.get(site, fallback)
	return view.get("route", {}).get("site_names", {}).get(site, fallback)


func _clear_actions(page: VBoxContainer, buttons: Dictionary) -> void:
	for node in page.get_children():
		page.remove_child(node)
		node.queue_free()
	buttons.clear()


func _refresh_action_scroll_bounds() -> void:
	# ScrollContainer measures its children when calculating its minimum size.
	_action_scroll.get_minimum_size()
	_action_scroll.queue_sort()


func _render() -> void:
	var started := Time.get_ticks_usec() if profile_panels else 0
	var previous_actions := actions
	var phase: String = view.get("phase", "")
	var snapshot: Variant = view.get("battle_view")
	var opening_lines: Array = view.get("opening_lines", [])
	var showing_opening: bool = not client.blocked and (not opened or captions_open) and not opening_lines.is_empty()
	var show_confirmation: bool = not client.blocked and not settings_open and not confirmation.is_empty()
	var show_combat: bool = opened and not client.blocked and not captions_open and not settings_open \
		and confirmation.is_empty() and phase == "BATTLE" and snapshot is Dictionary \
		and view.get("battle_memory", {}).is_empty()
	var field: bool = opened and not showing_opening and (phase == "BATTLE" or view.get("route", {}).get("contact_pending", false))
	_apply_field_style(field)
	for control in _contact_controls.get_children():
		_contact_controls.remove_child(control)
		control.queue_free()
	if show_confirmation:
		actions = _confirmation_actions
		command_buttons = _confirmation_buttons
	elif show_combat:
		actions = _combat_actions
		command_buttons = _combat_buttons
	else:
		actions = _general_actions
		command_buttons = _general_buttons
		_clear_actions(actions, command_buttons)
	var font_size := 24 if settings["大字"] else 16
	if theme.default_font_size != font_size:
		theme.default_font_size = font_size
		_set_panel_text_size(settings["大字"])
		subtitles.add_theme_font_size_override("font_size", 27 if settings["大字"] else 18)
		warning.add_theme_font_size_override("font_size", 25 if settings["大字"] else 17)
		warning_footer.custom_minimum_size.y = 79.0 if settings["大字"] else 56.0
	var region := str(view.get("region_name", ""))
	if showing_opening or phase in ["TOWN", "RETURNED", "FAILED", "FIN_C"]:
		region = "暮汀"
	elif phase == "MISSING_SEARCH":
		region = str(view.rescue.active.get("origin_region", ""))
		if region.is_empty():
			region = "失联调查"
	elif view.get("site") == "RESCUE":
		region = "巡队转运点"
	elif region.is_empty():
		region = "灰栎边道"
	area_title.text = region if field else "火种计划  /  " + region
	location.text = "暮汀北门 · 独返" if showing_opening else _display_location()
	save_info.text = "结果待核实" if client.blocked else "正在处理" if client.busy else "已保存 · 版本 %d" % save_version if save_version >= 0 else "存档尚未确认"
	save_info.visible = not field or client.blocked
	_warning_plate.visible = field and phase == "BATTLE"
	_field_toolbar.visible = field
	_battle_controls.visible = show_combat
	if phase != "EXPLORE" or not view.get("tutorial_area", false) or view.get("site") != "D":
		_overlook_open = false
	board.set_route_input(opened and phase == "EXPLORE" and not _overlook_open and not field_items_open and not _show_deployment() and not captions_open \
		and not settings_open and confirmation.is_empty() and not client.busy and not client.blocked)
	board.impacts = _live_impacts if settings["战斗数字"] and not settings_open and not captions_open and confirmation.is_empty() else {}
	board.impact_font_size = 19 if settings["大字"] else 15
	var board_started := Time.get_ticks_usec() if profile_panels else 0
	board.update_board(model if opened else {}, selected_id, save_version, settings["低动态"], settings_open,
		_show_deployment())
	_search_chart.present(view.get("rescue", {}) if opened and phase == "MISSING_SEARCH" else {}, settings["大字"],
		not showing_opening and not settings_open and confirmation.is_empty() and not client.busy and not client.blocked)
	_overlook_mat.visible = _overlook_open and not showing_opening and not client.blocked and not settings_open and confirmation.is_empty()
	_overlook_picture.texture = board._overlook_art if _overlook_mat.visible else null
	_opening_art.present(str(opening_lines[caption_index].get("id", "TD001")) if showing_opening else "")
	if not (opened and phase == "TOWN" and (chapter_history_open or books_open) and not showing_opening and not settings_open
			and not client.blocked and (confirmation.is_empty() or books_open) and view.get("hunt", {}).get("memory", {}).is_empty()):
		_archive_page.dismiss()
	board.deployment_open = _can_edit_deployment()
	var actions_started := Time.get_ticks_usec() if profile_panels else 0
	if show_combat:
		_update_combat_actions(snapshot)
	elif client.blocked:
		var opening_failed: bool = model.is_empty() and not client.can_reconnect
		var title := "无法打开试玩会话" if opening_failed else (
			"运行时连接中断" if client.can_reconnect else "存档状态待核实")
		_label(actions, title, GOLD, 23)
		if client.can_reconnect:
			_button("重新连接", "reconnect", _reconnect_runtime, not client.busy)
		if DirAccess.dir_exists_absolute(data_dir):
			_button("打开会话目录", "session-folder", _open_session_directory)
		if not client.runtime_log.is_empty() and FileAccess.file_exists(client.runtime_log):
			_button("打开运行时日志", "runtime-log", _open_runtime_log)
		if opening_failed and FileAccess.file_exists(data_dir.path_join("runs").path_join(case_name).path_join("save.json.bak")):
			_label(actions, "主档损坏时，试玩入口的 --recover 可从校验后的备份新建会话。", MUTED, 16)
		_button("退出样段", "quit", _quit)
	elif settings_open:
		_label(actions, "设置", GOLD, 23)
		_button("主音量 · %d%%" % volume, "volume", _cycle_volume)
		for setting in settings.keys():
			_button(setting + (" · 开" if settings[setting] else " · 关"), setting, _toggle.bind(setting))
		_button("返回", "settings-back", _close_settings)
		if field and not opening_lines.is_empty():
			_button("回看开场字幕", "opening-replay", _replay_opening)
	elif show_confirmation:
		if books_open and confirmation.get("command") == "book":
			for book: Dictionary in view.chapter.books:
				if book.id == confirmation.args[2]:
					_preview_chapter_book(book)
					break
		_confirmation_text.text = confirmation["text"]
		for control in command_buttons.values():
			control.disabled = client.busy
	else:
		if opened and not captions_open and phase in ["EXPLORE", "RETURNED", "FAILED", "TOWN"] and snapshot is Dictionary:
			if snapshot.get("finished", false) and not _show_deployment() \
					and not chapter_history_open and not remembrance_history_open and not books_open and not _overlook_open \
					and view.get("hunt", {}).get("memory", {}).is_empty():
				_finished_battle(snapshot)
		if (not opened or captions_open) and not view.is_empty():
			_opening_actions()
		elif phase == "TOWN":
			_town_actions()
		elif phase in ["RETURNED", "FAILED"]:
			_settlement_actions()
		elif phase == "EXPLORE":
			_explore_actions()
		elif phase == "BATTLE":
			var memory: Dictionary = view.get("battle_memory", {})
			if not memory.is_empty():
				_memory_actions(memory, "memory")
		elif phase == "MISSING_SEARCH":
			_search_actions()
		elif phase == "FIN_C":
			_label(actions, "本轮结束 · 名册已无可救回人员", ALERT, 23)
			_rescue_office(false)
		if opened and not captions_open and not view.get("opening_lines", []).is_empty():
			_button("回看开场字幕", "opening-replay", _replay_opening)
	if not show_combat and not show_confirmation:
		if _contact_controls.get_child_count() > 0:
			var settings_button := _button("设置", "settings", _show_settings, true, _contact_controls)
			settings_button.autowrap_mode = TextServer.AUTOWRAP_OFF
		else:
			if not settings_open:
				_button("设置", "settings", _show_settings)
			_button("退出游戏" if field else "退出样段", "quit", _quit)
		if phase == "EXPLORE" and _show_deployment() and not client.busy and not client.blocked:
			_prepare_contact_battle_rows()
	_contact_controls.visible = _contact_controls.get_child_count() > 0
	_field_toolbar.self_modulate.a = 1.0 if show_combat or _contact_controls.visible else 0.0
	var switch_started := Time.get_ticks_usec() if profile_panels else 0
	# Populate the incoming page before asking the shared scroll container to lay it out.
	if previous_actions != actions:
		previous_actions.hide()
		actions.show()
	var footer_started := Time.get_ticks_usec() if profile_panels else 0
	_render_subtitle()
	var reading_records: bool = not client.blocked and not settings_open and not captions_open \
		and (chapter_history_open or remembrance_history_open or books_open)
	notice.visible = not reading_records and (not field or not notice.text.is_empty())
	_subtitle_row.visible = not reading_records and (not field or not subtitles.text.is_empty() or dialogue_next.visible)
	if command_buttons.has(focus_key) and not command_buttons[focus_key].disabled:
		if command_buttons[focus_key].visible:
			command_buttons[focus_key].call_deferred("grab_focus")
		elif command_buttons.has("combat-playback"):
			command_buttons["combat-playback"].call_deferred("grab_focus")
	else:
		for control in command_buttons.values():
			if not control.disabled and control.visible:
				control.call_deferred("grab_focus")
				break
	_render_town_shortcuts()
	_resume_visible_presentation()
	if profile_panels:
		panel_timings.append({"version": int(client.frame.get("state_version", -1)),
			"started_usec": started, "layout_usec": board_started - started,
			"board_usec": actions_started - board_started, "actions_usec": switch_started - actions_started,
			"page_switch_usec": footer_started - switch_started,
			"footer_usec": Time.get_ticks_usec() - footer_started, "confirmation": show_confirmation})


func _render_town_shortcuts() -> void:
	var entries := {}
	if opened and view.get("phase") == "TOWN" and not captions_open and not settings_open \
			and confirmation.is_empty() and not client.busy and not client.blocked:
		var complete: bool = view.get("complete", false)
		var candidates := {
			"muster": ["town-roster" if complete else "tutorial recommend CONFIRM", "队伍整备" if complete else "建议部署"],
			"store": ["town-expedition", "远征与补给"],
			"departure-gate": ["depart CONFIRM" if complete else " ".join(["tutorial"] + _tutorial_departure_args()), "出发"],
		}
		for id in candidates:
			var choice: Array = candidates[id]
			var button: Button = command_buttons.get(choice[0])
			if button != null and (not button.disabled or id == "departure-gate"):
				entries[id] = {"key": choice[0], "label": choice[1], "description": button.text, "disabled": button.disabled}
	board.set_town_shortcuts(entries)


func _activate_town_shortcut(key: String) -> void:
	var button: Button = command_buttons.get(key)
	if button == null or button.disabled or client.busy or client.blocked:
		return
	button.grab_focus()
	button.pressed.emit()


func _reconnect_runtime() -> void:
	if client.reconnect():
		_playback_running = false
		initial_snapshot = true
		_restore_after_reconnect = true
		notice.text = "正在重新连接并核对存档…"


func _open_session_directory() -> void:
	if OS.shell_open(data_dir) != OK:
		notice.text = "无法打开会话目录。\n" + data_dir


func _open_runtime_log() -> void:
	if OS.shell_open(client.runtime_log) != OK:
		notice.text = "无法打开运行时日志。\n" + client.runtime_log


func _render_subtitle() -> void:
	var lines: Array = view.get("opening_lines", [])
	var line: Variant = null
	var active: Variant = null
	if (not opened or captions_open) and not lines.is_empty():
		line = lines[caption_index]
	else:
		active = model.get("active")
		if active is Dictionary and (active.get("id") == "opening" or chapter_history_open or remembrance_history_open):
			active = null
		if active is Dictionary:
			line = active["line"]
			if view.get("phase") == "TOWN" and notice.text == line["text"]:
				notice.text = ""
	var can_read: bool = opened and not captions_open and active is Dictionary and not settings_open \
		and confirmation.is_empty() and not client.blocked \
		and view.get("battle_memory", {}).is_empty() and view.get("hunt", {}).get("memory", {}).is_empty()
	var show_memory_reply: bool = not _memory_reply.is_empty() and not captions_open and not settings_open \
		and confirmation.is_empty() and not client.blocked and not remembrance_history_open
	if show_memory_reply:
		can_read = false
	dialogue_next.visible = can_read
	dialogue_skip.visible = can_read
	if can_read:
		var cursor := int(active.cursor) + 1
		var count := int(active.line_count)
		dialogue_next.text = "完成阅读" if cursor == count else "下一句"
		dialogue_next.disabled = client.busy
		dialogue_skip.disabled = client.busy
		command_buttons["dialogue next"] = dialogue_next
		command_buttons["dialogue skip"] = dialogue_skip
		subtitles.text = "%d/%d   %s   %s" % [cursor, count, line.speaker, line.text]
	else:
		command_buttons.erase("dialogue next")
		command_buttons.erase("dialogue skip")
		subtitles.text = _memory_reply if show_memory_reply else (
			"%s   %s" % [line.speaker, line.text] if line is Dictionary else "")


func _advance_dialogue(action: String) -> void:
	client.submit("dialogue", [action])


func _opening_actions() -> void:
	var count: int = view.get("opening_lines", []).size()
	_label(actions, "暮汀北门", GOLD, 26)
	if count > 1:
		_label(actions, "%d / %d" % [caption_index + 1, count], MUTED, 16)
		_button("下一句字幕", "subtitle-next", _turn_caption.bind(1), caption_index + 1 < count)
		_button("上一句字幕", "subtitle-prev", _turn_caption.bind(-1), caption_index > 0)
	if captions_open:
		_button("返回", "opening", _open_town)
	elif count > 0 and caption_index == count - 1:
		_button("重新打开", "opening-reopen-record", _open_town.bind(true))
		_button("谁回来过", "opening-ask", _open_town.bind(true))
		_button("先让我进去", "opening", _open_town)
	else:
		_button("跳过开场，进入暮汀", "opening", _open_town)


func _turn_caption(offset: int) -> void:
	caption_index += offset
	if caption_index == view.get("opening_lines", []).size() - 1:
		focus_key = "opening" if captions_open else "opening-reopen-record"
	_render()


func _town_actions() -> void:
	if not view.get("commissioned", false):
		_label(actions, "暮汀委任", GOLD, 24)
		if _asked_about_old_company:
			_label(actions, "沈砚　旧队档案缺了几页。等你把灰栎边道的调查带回来，我请许苇把余下的旧日志给你看。", MUTED, 16)
		_label(actions, "沈砚　城墙可以晚修一截，回来的路不能再少一条。\n秦姨　报名的人有名字，回来的时候照着名字点。", INK, 16)
		_input_action("接受委任", "quest", ["commission", "CONFIRM"],
			"接受灰栎边道侦路委任\n登记 3 名盾兵、3 名近战兵和 2 名弓兵。\n配发 60 铜、12 结晶和 6 补给。")
		return
	var hunt: Dictionary = view.get("hunt", {})
	if not hunt.get("memory", {}).is_empty():
		_memory_actions(hunt.memory, "remember")
		return
	if books_open:
		_chapter_book_choices()
		return
	if chapter_history_open or remembrance_history_open:
		_chapter_actions()
		return
	var complete: bool = view.get("complete", false)
	var has_records: bool = not view.get("rescue", {}).is_empty()
	var has_books: bool = not view.get("skill_books", {}).is_empty() or not view.get("book_market", {}).get("offers", {}).is_empty()
	if complete:
		_button("旧档案", "town-chapter", _town_tab.bind("chapter"), town_tab != "chapter")
	_button("队伍与装备" if complete else "出发前整备", "town-roster", _town_tab.bind("roster"), town_tab != "roster")
	if has_books:
		_button("技能书", "town-skills", _town_tab.bind("skills"), town_tab != "skills")
	if view.get("chapter", {}).get("archived", false):
		_button("远征与补给", "town-expedition", _town_tab.bind("expedition"), town_tab != "expedition")
	_button("城镇施工", "town-construction", _town_tab.bind("construction"), town_tab != "construction")
	_button("随身道具", "town-items", _town_tab.bind("items"), town_tab != "items")
	var logistics: Dictionary = view.get("town_services", {})
	if not logistics.is_empty():
		_button("后勤服务", "town-logistics", _town_tab.bind("logistics"), town_tab != "logistics")
	if has_records:
		_button("搜救所", "town-rescue", _town_tab.bind("rescue"), town_tab != "rescue")
	if town_tab == "rescue" and has_records:
		_rescue_office()
		return
	if town_tab == "skills" and has_books:
		_skill_book_room()
		return
	if town_tab == "construction":
		_construction_actions()
		return
	if town_tab == "items":
		_consumables_actions(true)
		return
	if town_tab == "logistics" and not logistics.is_empty():
		_logistics_actions(logistics)
		return
	if town_tab == "chapter" and complete:
		_chapter_actions()
		return
	if town_tab == "expedition" and view.get("chapter", {}).get("archived", false):
		_expedition_actions()
		return
	_label(actions, "队伍整备" if view.get("complete", false) else "出发前整备", GOLD, 24)
	if view.get("settlement") is Dictionary:
		_summary()
	var party: Array = view.get("party", [])
	if not view.get("complete", false):
		var can_recommend := not party.any(func(member: Dictionary) -> bool: return int(member.injury_days) > 0)
		_input_action("采用建议部署", "tutorial", ["recommend", "CONFIRM"],
			"将建议部署应用于当前可用的初始队员。", can_recommend)
		var has_supply := int(view.supply) >= 1
		var blocker: String = view.preparation.get("deployment_error", "")
		if not blocker.is_empty():
			_label(actions, blocker + "。", ALERT, 16)
		_input_action("出发 · 消耗 1 补给", "tutorial", _tutorial_departure_args(),
			_day_consequence("前往灰栎边道。消耗 1 补给。"), has_supply and blocker.is_empty())
		if not has_supply:
			_label(actions, "补给不足。采购后可再次出发。", ALERT, 16)
			_buy_supply()
	if not view.get("chapter", {}).get("archived", false):
		_rest_action()
	if not view.get("complete", false):
		_whistle_section()
	var treasury: Dictionary = view.get("town_roster", {})
	var expedition := 0
	var deployed := 0
	for member in party:
		expedition += int(member.cost)
		if member.deployed:
			deployed += int(member.cost)
	_label(actions, "出征 %d/%d · 战斗 %d/%d Cost" % [expedition, int(view.budget.expedition),
		deployed, int(view.budget.battle)], MUTED, 16)
	if not treasury.is_empty():
		var price := int(treasury.spear_price)
		_input_action("招募护运枪卫 · %d 铜" % price, "recruit", ["M01"],
			"支付 %d 铜，枪兵加入留城名册，出征 Cost 为 2。" % price, int(treasury.copper) >= price)
		for recruit in view.get("preparation", {}).get("recruits", []):
			_input_action("招募%s · %d 铜" % [recruit.name, price], "recruit", [recruit.id],
				"支付 %d 铜，加入留城名册，出征 Cost 为 2。" % price, int(treasury.copper) >= price)
		if not treasury.home.is_empty():
			_label(actions, "留城名册", GOLD, 16)
			for member in treasury.home:
				if logistics.get("training", {}).get("pending", []).any(func(row): return row.id == member.instance_id):
					_label(actions, _name(member) + " · 等待补训结算", MUTED, 16)
					continue
				var eligible := int(member.hp) > 0 and int(member.injury_days) == 0 and expedition + int(member.cost) <= int(view.budget.expedition)
				_input_action("随队 · " + _name(member), "squad", [member.instance_id, "on"], "", eligible)
				if _can_manage_gear(member) or int(member.get("heal_cost", 0)) > 0 or int(member.injury_days) > 0 \
						or int(member.get("next_xp", 0)) > 0 and int(member.xp) >= int(member.next_xp):
					_button("状态 · " + _name(member), "member-" + member.instance_id, _choose_member.bind(member.instance_id))
					if member.instance_id == selected_id:
						_equipment_actions(member)
						_recovery_actions(member)
	_member_actions(view.get("town_deploy_cells", []))


func _town_tab(tab: String) -> void:
	_book_swap_key = ""
	books_open = false
	_previewed_book = {}
	chapter_history_open = false
	remembrance_history_open = false
	construction_project = ""
	outfit_selection.clear()
	outfit_editing = false
	pouch_item = ""
	pouch_targets.clear()
	bookstore_open = false
	bookstore_book = ""
	book_research_open = false
	town_tab = tab
	focus_key = "construction-project-hospital" if tab == "construction" else (
		"town-chapter" if tab != "chapter" else "town-roster")
	_render()


func _chapter_actions() -> void:
	if remembrance_history_open:
		_label(actions, "阿铎 · 已提交的追忆对白", GOLD, 24)
		_button("返回旧档案", "remembrance-history", _toggle_remembrance_history)
		var records: Array = view.hunt.memory_records
		for index in records.size():
			var record: Dictionary = records[index]
			if record.committed:
				_label(actions, "第 %d 段" % (index + 1), INK, 17)
				for line in record.lines:
					_label(actions, "%s  %s" % [line.speaker, line.text], MUTED, 16)
		return
	var chapter: Dictionary = view.get("chapter", {})
	if chapter_history_open:
		_chapter_history(chapter)
		return
	_label(actions, "暮汀 · 旧档案", GOLD, 24)
	if not chapter.get("reviewed", false):
		_label(actions, "调查已交回 · 待核对旧日志", MUTED, 16)
		_input_action("请许苇核对调查", "quest", ["review", "CONFIRM"],
			"请许苇将远眺记录与旧日志核对。\n" + chapter.observation)
	elif not chapter.get("archived", false):
		_label(actions, "旧日志已核对 · 待交存", MUTED, 16)
		_label(actions, chapter.review_exchange, MUTED, 16)
		var next_budget: Dictionary = chapter.archive_budget
		_input_action("交存调查与旧名册", "quest", ["archive", "CONFIRM"],
			"完成首章\n出征预算 %d → %d Cost\n战斗预算 %d → %d Cost\n应召印 ×%d\n自选基础技能书 ×1\n任务物品「%s」" % [
				int(view.budget.expedition), int(next_budget.expedition), int(view.budget.battle), int(next_budget.battle),
				int(chapter.archive_seals), chapter.archive_item])
	else:
		_label(actions, "首章已交档 · 应召印库存 %d 枚" % int(chapter.seals), INK, 17)
		_label(actions, "出征预算 %d Cost · 战斗预算 %d Cost" % [int(view.budget.expedition), int(view.budget.battle)], MUTED, 16)
	_button("查阅交档记录", "chapter-history", _toggle_chapter_history)
	if chapter.archived:
		var selected: Dictionary = chapter.get("book_selected", {})
		if not selected.is_empty():
			_label(actions, _chapter_book_text(selected), MUTED, 16)
		elif not chapter.get("books", []).is_empty():
			_button("自选一本基础技能书", "chapter-books", _toggle_books)
		if int(chapter.seals) > 0:
			_input_action("应召一名英雄 · 1 枚应召印", "summon", [chapter.summon_id, "CONFIRM"],
				"使用一枚应召印，应召一名尚未获得的英雄。")
		_hunt_archive()
		var sev: Dictionary = view.sev_hunt
		if sev.defeated:
			_hunt_report(sev)
		_label(actions, "阿铎 · 裂口铜哨", GOLD, 17)
		var whistle: Dictionary = view.whistle
		if whistle.get("stage") == "record":
			_label(actions, chapter.whistle_clue, MUTED, 16)
		_whistle_actions(whistle)
	else:
		_whistle_section()


func _chapter_history(chapter: Dictionary) -> void:
	_label(actions, "交档记录", GOLD, 24)
	_button("返回旧档案", "chapter-history", _toggle_chapter_history)
	var records: Array = chapter.history.duplicate(true)
	for record: Dictionary in records:
		if record.get("commission", false):
			record.text = _commission_grant_text(view.commission_receipt)
		if record.id == "ST-104":
			var budget: Dictionary = chapter.archive_budget
			var details := PackedStringArray([record.text,
				"交档后出征预算 %d Cost · 战斗预算 %d Cost" % [int(budget.expedition), int(budget.battle)],
				"首交发放应召印 ×%d" % int(chapter.archive_seals)])
			if chapter.choice_granted:
				details.append("登记基础技能书自选权益 ×1")
			if not chapter.book_selected.is_empty():
				details.append(_chapter_book_text(chapter.book_selected))
			record.text = "\n".join(details)
	if records.is_empty():
		return
	if _archive_record_id.is_empty():
		_archive_record_id = records.back().id
	var hunt: Dictionary = view.get("hunt", {})
	if hunt.get("reported", false):
		records.append({"id": "report", "title": "阿铎讨伐报告", "day": hunt.report_delivery_day,
			"text": "\n".join(_hunt_report_lines(hunt))})
	var sev: Dictionary = view.get("sev_hunt", {})
	if sev.get("reported", false):
		records.append({"id": "report-MG02", "title": "%s讨伐报告" % sev.name, "day": sev.report_delivery_day,
			"text": "\n".join(_hunt_report_lines(sev))})
	var collection: Dictionary = view.get("whistle", {}).get("collection", {})
	if not collection.is_empty():
		records.append({"id": "whistle", "title": "裂口铜哨", "day": collection.day,
			"text": _whistle_receipt_text(collection)})
	for record: Dictionary in records:
		var id: String = record.id
		var button := _button(record.title, "archive-" + id, _choose_archive_record.bind(id))
		if id == _archive_record_id:
			var active := _box("304039", "d7ae69", 3, 8)
			button.add_theme_stylebox_override("normal", active)
			button.add_theme_stylebox_override("hover", active)
			button.add_theme_color_override("font_color", GOLD)
			_archive_page.show_record(record, settings["大字"])


func _choose_archive_record(id: String) -> void:
	_archive_record_id = id
	focus_key = "archive-" + id
	_render()


func _chapter_book_text(book: Dictionary) -> String:
	var receipt := "已领技能书 · " + str(book.name)
	if book.claimed_day != null:
		receipt += " · 第 %d 日" % int(book.claimed_day)
	return receipt + "\n书库现存 %d 本" % int(book.count)


func _commission_grant_text(receipt: Dictionary) -> String:
	var text := "初次登记 %d 名队员。" % int(receipt.members)
	var resources: Dictionary = receipt.resources
	if resources.has_all(["copper", "crystal", "supply"]):
		text += "配发 %d 铜、%d 结晶和 %d 补给。" % [
			int(resources.copper), int(resources.crystal), int(resources.supply)]
	return text


func _toggle_chapter_history() -> void:
	if not chapter_history_open:
		_archive_list_scroll = _action_scroll.scroll_vertical
		_archive_record_id = ""
	chapter_history_open = not chapter_history_open
	focus_key = "chapter-history"
	_render()
	_action_scroll.set_deferred("scroll_vertical", 0 if chapter_history_open else _archive_list_scroll)


func _toggle_books() -> void:
	books_open = not books_open
	if books_open:
		_archive_list_scroll = _action_scroll.scroll_vertical
		_previewed_book = view.chapter.books[0]
		focus_key = "book choice ST-104 %s CONFIRM" % _previewed_book.id
	else:
		_previewed_book = {}
		focus_key = "chapter-books"
	_render()
	_action_scroll.set_deferred("scroll_vertical", 0 if books_open else _archive_list_scroll)


func _chapter_book_choices() -> void:
	_label(actions, "自选一本基础技能书", GOLD, 24)
	_button("返回旧档案", "chapter-books", _toggle_books)
	for book: Dictionary in view.chapter.books:
		var entry := _input_action(book.name, "book", ["choice", "ST-104", book.id, "CONFIRM"],
			"领取「%s」，使用本次首章自选权益。入库后可在暮汀学习。\n%s\n%s" % [
				book.name, book.timing, book.summary])
		entry.focus_entered.connect(_preview_chapter_book.bind(book))
		entry.gui_input.connect(_point_at_chapter_book.bind(entry))
	_preview_chapter_book(_previewed_book)


func _point_at_chapter_book(event: InputEvent, entry: Button) -> void:
	if event is InputEventMouseMotion and event.relative != Vector2.ZERO and not entry.has_focus():
		entry.grab_focus()


func _preview_chapter_book(book: Dictionary) -> void:
	if not books_open or book.is_empty() or settings_open or captions_open or client.blocked:
		return
	_previewed_book = book
	_archive_page.show_document(book.id, "首章自选 · 基础技能书", book.name,
		"%s\n\n%s" % [book.timing, book.summary], settings["大字"])
	_archive_page.show_readers(book.get("learners", []), book.get("known", []), settings["大字"])


func _whistle_section() -> void:
	var whistle: Dictionary = view.get("whistle", {})
	if whistle.is_empty():
		return
	var prompt := "铜哨已领 · 查看委托" if whistle.stage == "done" else "铜哨寄存"
	_button("收起铜哨委托" if whistle_open else prompt, "whistle-section", _toggle_whistle)
	if whistle_open:
		_whistle_actions(whistle)


func _toggle_whistle() -> void:
	whistle_open = not whistle_open
	focus_key = "whistle-section"
	_render()


func _whistle_actions(whistle: Dictionary) -> void:
	for text: String in [whistle.get("record", ""), whistle.get("witness", "")]:
		if not text.is_empty():
			_label(actions, text, MUTED, 16)
	match whistle.get("stage", ""):
		"record":
			_input_action("查阅铜哨寄存登记", "quest", ["MG01", "record"])
		"witness":
			_input_action("向秦姨核对证词", "quest", ["MG01", "witness"])
		"collect":
			var price := int(whistle.price)
			var copper := int(view.town_roster.copper)
			if copper < price:
				_label(actions, "修缮还差 %d 铜" % (price - copper), ALERT, 16)
			_input_action("修缮并取回铜哨 · %d 铜" % price, "quest", ["MG01", "collect", "CONFIRM"],
				"支付 %d 铜取回同一件裂口铜哨。" % price, copper >= price)
		"done":
			_label(actions, "裂口铜哨已入任务物品", MUTED, 16)
			_whistle_receipt(whistle)
		"field":
			_label(actions, "这件铜哨已登记为现场自取。", MUTED, 16)


func _whistle_receipt(whistle: Dictionary) -> void:
	var collection: Dictionary = whistle.get("collection", {})
	if not collection.is_empty():
		_label(actions, _whistle_receipt_text(collection), MUTED, 16)


func _whistle_receipt_text(collection: Dictionary) -> String:
	return "裂口铜哨 · 第 %d 日修缮取回 · 支付 %d 铜" % [int(collection.day), int(collection.copper)]


func _hunt_reward(hunt: Dictionary) -> String:
	return "「%s」×1 · 应召印 ×%d" % [hunt.report_book.name, int(hunt.report_seals)]


func _hunt_report_lines(hunt: Dictionary) -> PackedStringArray:
	var lines := PackedStringArray()
	if hunt.report_ready and hunt.victory_day != null:
		lines.append("第 %d 日胜利 · 第 %d 日安全归城" % [int(hunt.victory_day), int(hunt.report_return_day)])
	if hunt.reported:
		lines.append("报告已交存 · 首交奖励\n" + _hunt_reward(hunt))
		lines.append("第 %d 日交存" % int(hunt.report_delivery_day))
		lines.append("「%s」现存 %d 本" % [hunt.report_book.name, int(hunt.report_book.count)])
	return lines


func _pending_hunt_report(slice: Dictionary, this_return := false) -> Dictionary:
	for key in ["hunt", "sev_hunt"]:
		var hunt: Dictionary = slice.get(key, {})
		if hunt.get("report_ready", false) and not hunt.reported \
				and (not this_return or hunt.report_this_return):
			return hunt
	return {}


func _hunt_report(hunt: Dictionary) -> void:
	var title := "%s讨伐报告" % hunt.name
	_label(actions, title, GOLD, 17)
	for line in _hunt_report_lines(hunt):
		_label(actions, line, MUTED, 16)
	if hunt.reported:
		return
	if hunt.report_ready:
		_input_action("交存" + title, "quest", ["report", hunt.id, "CONFIRM"],
			"交存安全归城的胜利报告\n首交奖励\n" + _hunt_reward(hunt))
	else:
		_label(actions, "已记录胜利，报告等待安全归城。", MUTED, 16)


func _hunt_archive() -> void:
	var hunt: Dictionary = view.get("hunt", {})
	if not hunt.get("defeated", false):
		return
	_hunt_report(hunt)
	_label(actions, "阿铎 · 追忆", GOLD, 17)
	var records: Array = hunt.memory_records
	if hunt.awakened:
		_label(actions, "阿铎已保留记忆", INK, 16)
	elif hunt.evidence:
		var first: Dictionary = records[0]
		var caption := "凭铜哨和证词开始追忆"
		if first.committed:
			caption = "继续追忆 · 第 2 段"
		elif first.skipped:
			caption = "继续追忆 · 补做第 1 段"
		_input_action(caption, "remember", ["MG01"])
	else:
		var missing: PackedStringArray = []
		if not hunt.has_whistle:
			missing.append("裂口铜哨")
		if not hunt.has_testimony:
			missing.append("秦姨核实的证词")
		_label(actions, "追忆尚缺" + "、".join(missing) + "。", MUTED, 16)
	if records.any(func(record: Dictionary) -> bool: return record.committed):
		_button("回看已提交的追忆对白", "remembrance-history", _toggle_remembrance_history)


func _toggle_remembrance_history() -> void:
	remembrance_history_open = not remembrance_history_open
	_memory_reply = ""
	focus_key = "remembrance-history"
	_render()
	if remembrance_history_open:
		_action_scroll.set_deferred("scroll_vertical", 0)


func _day_consequence(text: String) -> String:
	var due: Array = view.get("rescue", {}).get("due", [])
	return _with_expiry_warning(text, due)


func _tutorial_departure_args() -> Array:
	return ["start", "CONFIRM"] if not view.get("rescue", {}).get("due", []).is_empty() else ["start"]


func _with_expiry_warning(text: String, due: Array) -> String:
	if due.is_empty():
		return text
	var labels := {}
	for batch in view.get("rescue", {}).get("batches", []):
		for member in batch.members:
			labels[member.instance_id] = _name(member)
	var names := due.map(func(id): return labels.get(id, id))
	return text + "\n第 %d 日结算时，救援将超期\n%s" % [int(view.day) + 1, "、".join(names)]


func _buy_supply() -> void:
	var price := int(view.preparation.supply_price)
	_input_action("采购 1 份补给 · %d 铜" % price, "buy_supply", ["1"], "支付 %d 铜。" % price, int(view.town_roster.copper) >= price)


func _rest_action() -> void:
	_input_action("休整一日", "rest", ["CONFIRM"],
		_day_consequence("推进至第 %d 日，结算随队和留城队员的旧伤，并减轻侵蚀。" % (int(view.day) + 1)))


func _select_construction(project: String) -> void:
	focus_key = "construction-project-" + construction_project if project.is_empty() else "construction-list"
	construction_project = project
	_render()


func _construction_status(project: Dictionary) -> String:
	var order: Dictionary = project.get("order", {})
	if not order.is_empty():
		return "Lv%d %s · %d/%d" % [int(order.target), "暂停" if order.paused else "在建", int(order.progress), int(order.required)]
	if project.has("legacy_remaining"):
		return "Lv1 在建 · 还需 %d 次结算" % int(project.legacy_remaining)
	if int(project.level) > 0:
		return "Lv%d 已竣工" % int(project.level)
	var quote: Dictionary = project.quote
	return "%d 铜 · %d 公共结晶" % [int(quote.paid.copper), int(quote.paid.crystal)] if quote.blocker.is_empty() else quote.blocker


func _construction_actions() -> void:
	var work: Dictionary = view.construction
	_label(actions, "暮汀 · 城镇施工", GOLD, 24)
	_label(actions, "库存 %d 铜 · %d 公共结晶\n施工位 %d/%d" % [
		int(work.funds.copper), int(work.funds.crystal), int(work.occupied), int(work.workers)], INK, 17)
	for project: Dictionary in work.projects:
		if construction_project.is_empty():
			_button("%s · %s" % [project.name, _construction_status(project)], "construction-project-" + project.key,
				_select_construction.bind(project.key))
		elif project.key == construction_project:
			_button("返回施工列表", "construction-list", _select_construction.bind(""))
			_construction_detail(project, work.order_id)
	if int(work.occupied) > 0:
		_rest_action()


func _construction_detail(project: Dictionary, next_id: String) -> void:
	_label(actions, project.name + " · " + _construction_status(project), GOLD, 19)
	_label(actions, project.effect, MUTED, 16)
	var order: Dictionary = project.get("order", {})
	if not order.is_empty():
		if order.rush:
			_label(actions, "已支付赶工费用，须等本次行动结算后调整。", MUTED, 16)
			return
		var refund: Dictionary = order.refund
		_input_action("撤销施工", "facility", ["cancel", order.id, "CONFIRM"],
			"撤销%s施工。退回 %d 铜和 %d 公共结晶。" % [project.name, int(refund.copper), int(refund.crystal)])
		if order.pause:
			_input_action("暂停施工", "facility", ["pause", order.id, "CONFIRM"], "保留%s已付费用和进度，释放施工位。" % project.name)
		if order.resume:
			_input_action("恢复施工", "facility", ["resume", order.id, "CONFIRM"], "恢复%s施工，占用一个自然施工位。" % project.name)
	elif project.has("quote"):
		var quote: Dictionary = project.quote
		var copper := int(quote.paid.copper)
		var crystal := int(quote.paid.crystal)
		var required := int(quote.required)
		_label(actions, "Lv1 工期 · %d 次行动结算" % required, MUTED, 16)
		_input_action("开工 · %d 铜 · %d 公共结晶" % [copper, crystal], "facility", ["build", project.key, "1", next_id, "CONFIRM"],
			"建设%s Lv1。支付 %d 铜和 %d 公共结晶。\n开工不耗日，%d 次后续行动结算后竣工。" % [project.name, copper, crystal, required],
			quote.blocker.is_empty())
	elif int(project.level) > 0 and project.key in ["barracks", "armory"]:
		_button("办理后勤服务", "construction-logistics", _town_tab.bind("logistics"))
		if project.key == "armory":
			_button("制作随身道具", "construction-items", _town_tab.bind("items"))


func _service_cost(cost: Dictionary) -> String:
	var labels := {"copper": "铜", "crystal": "公共结晶", "supply": "补给",
		"fiber": "木纤", "herb": "草药", "iron": "铁料", "crystal_shard": "晶屑"}
	var parts: PackedStringArray = []
	for resource in labels:
		if int(cost.get(resource, 0)) > 0:
			parts.append("%d %s" % [int(cost[resource]), labels[resource]])
	return "、".join(parts)


func _toggle_field_items() -> void:
	field_items_open = not field_items_open
	pouch_item = ""
	pouch_targets.clear()
	focus_key = "field-items"
	_render()


func _select_pouch_item(id: String) -> void:
	focus_key = "pouch-item-" + pouch_item if id.is_empty() else "pouch-list"
	pouch_item = id
	pouch_targets.clear()
	_render()


func _toggle_pouch_target(id: String) -> void:
	if pouch_targets.has(id):
		pouch_targets.erase(id)
	else:
		pouch_targets.append(id)
	focus_key = "pouch-target-" + id
	_render()


func _consumables_actions(town: bool) -> void:
	var bag: Dictionary = view.get("consumables", {})
	var slots := int(bag.get("slots", 0))
	var reserved := int(bag.get("reserved", 0))
	_label(actions, "随身道具", GOLD, 24)
	_label(actions, "携行占用 %d/4 · 准备占位 %d" % [slots, reserved], INK, 17)
	if slots >= 4:
		_label(actions, "携行袋已满。", MUTED, 16)
	var items: Array = bag.get("items", [])
	for item: Dictionary in items:
		if item.id == pouch_item:
			_button("返回道具列表", "pouch-list", _select_pouch_item.bind(""))
			_consumable_detail(item, town, slots)
			return
	if town and int(bag.get("workshop", 0)) == 0:
		_label(actions, "一级工坊竣工后开放制作。", MUTED, 16)
	if items.is_empty():
		_label(actions, "没有可管理的随身道具。", MUTED, 16)
	for item: Dictionary in items:
		var counts: PackedStringArray = []
		if int(item.carried) > 0:
			counts.append("携带 %d" % int(item.carried))
		if int(item.stored) > 0:
			counts.append("库中 %d" % int(item.stored))
		if item.has("recipe") and counts.is_empty():
			counts.append("工坊配方")
		_button(item.name + " · " + " / ".join(counts), "pouch-item-" + item.id, _select_pouch_item.bind(item.id))
	if town:
		_material_commission_actions()


func _material_commission_actions() -> void:
	var goal: Dictionary = view.get("material_goal", {})
	if goal.get("options", []).is_empty():
		return
	_label(actions, "材料委托", GOLD, 18)
	for option in goal.options:
		var amount := _service_cost(option.materials)
		var active: bool = option.id == goal.current
		_input_action(("已登记 · " if active else "定向 · ") + amount, "supply", ["commission", option.id],
			"在符合条件的常规远征中锁定材料地点。\n地区 · %s\n到场领取 %s，安全归城后入库。" % [
				"、".join(option.regions), amount], not active)
	if goal.current != null:
		_input_action("取消材料委托", "supply", ["commission", "off"])


func _consumable_detail(item: Dictionary, town: bool, slots: int) -> void:
	_label(actions, item.name, GOLD, 19)
	_label(actions, item.effect, INK, 16)
	_label(actions, "携带 %d · 库中 %d" % [int(item.carried), int(item.stored)] if town else "携带 %d" % int(item.carried), MUTED, 16)
	if town and item.has("recipe"):
		var cost := _service_cost(item.recipe.costs)
		if not item.recipe.short.is_empty():
			_label(actions, "仓库还缺 " + _service_cost(item.recipe.short), MUTED, 16)
		_input_action("制作 1 份 · " + cost, "craft", [item.id],
			"支付 %s，制作 1 份%s并放入携行袋。\n携行占用 %d/4 → %d/4，制作不推进行动日。" % [
				cost, item.name, slots, slots + 1], slots < 4 and item.recipe.short.is_empty())
	if town and int(item.stored) > 0:
		_input_action("取出 1 份", "take", [item.id], "", slots < 4)
	if int(item.carried) == 0:
		return
	if town:
		_input_action("存入物品库 1 份", "stash", [item.id])
	else:
		_input_action("丢弃 1 份", "discard", [item.id], "丢弃 1 份%s，腾出 1 个携行格。" % item.name)
	if not item.use_blocker.is_empty():
		_label(actions, item.use_blocker, MUTED, 16)
		return
	_use_consumable(item, slots)


func _use_consumable(item: Dictionary, slots: int) -> void:
	var cap := int(item.target_cap)
	var effect: String = item.effect
	if not item.healing:
		effect += "\n使用后保留 1 个准备占位，至本趟结算。"
	if cap == 0:
		_input_action("使用 1 份", "use", [item.id], effect)
		return
	_label(actions, "选择对象 · %d/%d" % [pouch_targets.size(), cap], MUTED, 16)
	var preview: PackedStringArray = []
	for target in item.targets:
		var selected := pouch_targets.has(target.id)
		var detail: String = target.name
		if item.healing:
			detail += " · 生命 %d/%d · 回复 %d" % [int(target.hp), int(target.max_hp), int(target.heals)]
			if int(target.overflow) > 0:
				detail += " · 溢出 %d" % int(target.overflow)
		var button := _button(detail, "pouch-target-" + target.id, _toggle_pouch_target.bind(target.id), selected or pouch_targets.size() < cap)
		button.toggle_mode = true
		button.set_pressed_no_signal(selected)
		if selected:
			preview.append(detail)
	var keys := ",".join(pouch_targets)
	if item.healing:
		effect = "携行占用 %d/4 → %d/4。" % [slots, slots - 1]
	_input_action("使用 1 份", "use", [item.id, keys], "使用 1 份%s。\n%s\n%s" % [
		item.name, "\n".join(preview), effect], not keys.is_empty() and keys.length() <= 256)


func _service_surcharge(extra: Dictionary) -> String:
	return "\n已含第二项服务附加费 %s，并用 1 点准备额。" % _service_cost(extra) if not extra.is_empty() else ""


func _logistics_actions(logistics: Dictionary) -> void:
	_label(actions, "暮汀 · 后勤服务", GOLD, 24)
	_label(actions, "本行动已用 %d/2 项 · 库存 %s" % [int(logistics.used), _service_cost(logistics.funds)], MUTED, 16)
	if not logistics.training.is_empty():
		_training_actions(logistics.training, logistics.order_id, int(logistics.day_due))
	if not logistics.defense.is_empty():
		_defense_actions(logistics.defense, logistics.order_id)
	if not logistics.training.get("pending", []).is_empty():
		_rest_action()


func _training_actions(training: Dictionary, order_id: String, day_due: int) -> void:
	_label(actions, "营房补训", GOLD, 18)
	for member in training.settled:
		_label(actions, "%s · 已获得 %d 经验" % [member.name, int(member.xp)], INK, 16)
	if not training.pending.is_empty():
		for member in training.pending:
			_label(actions, "%s · 留城 · 第 %d 日结算 +%d 经验" % [member.name, day_due, int(member.xp)], INK, 16)
		return
	if training.options.is_empty():
		_label(actions, "可安排有出战记录的留城成员补训，等级受带教者与章卡限制。", MUTED, 16)
	for option in training.options:
		if not option.blocker.is_empty():
			_label(actions, "%s · %s" % [option.name, option.blocker], MUTED, 16)
			continue
		var cost := _service_cost(option.paid)
		_input_action("补训 %s · %s" % [option.name, cost], "service", ["training", option.id + ":1", order_id, "CONFIRM"],
			"支付 %s。%s 本次须留城，第 %d 日行动结算时获得 1 经验。" % [cost, option.name, day_due] + _service_surcharge(option.extra))


func _defense_actions(defense: Dictionary, order_id: String) -> void:
	_label(actions, "工坊整备", GOLD, 18)
	if defense.spec.mode == "medicine":
		_label(actions, "强化药箱已付款，等待下次出发。", INK, 16)
		return
	var amount := int(defense.spec.amount)
	var cap := int(defense.spec.target_cap)
	if defense.ready and not outfit_editing:
		var names: PackedStringArray = []
		for member in defense.targets:
			names.append(member.name if member.travels else member.name + "（留城）")
		_label(actions, "待出发 · 物防、魔防各 +%d\n%s" % [amount, "、".join(names)], INK, 16)
		_button("改选整备对象", "outfit-edit", _edit_outfit, not defense.options.is_empty())
		return
	var blocker: String = defense.get("blocker", "")
	if not blocker.is_empty():
		_label(actions, blocker, MUTED, 16)
		return
	if defense.options.is_empty():
		_label(actions, "整备需要至少一名健康的随行成员。", MUTED, 16)
		return
	_label(actions, "选 %d/%d 人 · 下趟每场出战时物防、魔防各 +%d" % [outfit_selection.size(), cap, amount], INK, 16)
	for member in defense.options:
		var selected := outfit_selection.has(member.id)
		var control := _button(member.name + (" · 上阵" if member.deployed else " · 预备"), "outfit-unit-" + member.id,
			_toggle_outfit_target.bind(member.id), selected or outfit_selection.size() < cap)
		control.toggle_mode = true
		control.set_pressed_no_signal(selected)
	var keys := ",".join(outfit_selection)
	if defense.ready:
		_input_action("保存整备对象", "outfit", ["targets", keys], "", not keys.is_empty())
		_button("取消改选", "outfit-edit-cancel", _cancel_outfit_edit)
	else:
		var cost := _service_cost(defense.paid)
		var targets: Array = defense.options.filter(func(member): return outfit_selection.has(member.id))
		var names := "、".join(targets.map(func(member): return member.name))
		_input_action("购买防御整备 · " + cost, "outfit", ["buy", "defense", keys, order_id, "CONFIRM"],
			"支付 %s。绑定下次出发。\n%s出战时，物防、魔防各 +%d。出发前可免费改选。" % [cost, names, amount]
			+ _service_surcharge(defense.extra), not keys.is_empty())


func _edit_outfit() -> void:
	outfit_editing = true
	var defense: Dictionary = view.town_services.defense
	var available: Array = defense.options.map(func(member): return member.id)
	outfit_selection.assign(defense.targets.map(func(member): return member.id).filter(func(id): return available.has(id)))
	focus_key = "outfit-edit-cancel"
	_render()


func _cancel_outfit_edit() -> void:
	outfit_editing = false
	outfit_selection.clear()
	focus_key = "outfit-edit"
	_render()


func _toggle_outfit_target(id: String) -> void:
	if outfit_selection.has(id):
		outfit_selection.erase(id)
	else:
		outfit_selection.append(id)
	focus_key = "outfit-unit-" + id
	_render()


func _expedition_actions() -> void:
	var hunts: Array[Dictionary] = [view.hunt, view.sev_hunt]
	var selected: Dictionary = {}
	for hunt in hunts:
		if hunt.selected:
			selected = hunt
			break
	var prep: Dictionary = view.preparation
	var cost := int(view.departure_cost)
	var supply := int(view.supply)
	var copper := int(view.town_roster.copper)
	_label(actions, "远征与补给", GOLD, 24)
	if selected.is_empty():
		for hunt in hunts:
			if not hunt.defeated:
				_input_action("选定%s讨伐" % hunt.name, "challenge", [hunt.id])
		_label(actions, "当前路线 · 常规短途", MUTED, 17)
	else:
		_label(actions, "讨伐%s · %s" % [selected.name, " → ".join(selected.route)], INK, 18)
		if selected.id == "MG01" and not selected.evidence:
			_label(actions, "可出征。带上旧档案的铜哨与证词，可在战中出示。", MUTED, 16)
		_input_action("取消讨伐安排", "challenge", ["cancel"])
	var blocker := str(prep.deployment_error)
	if supply < cost:
		_label(actions, "出发需 %d 份补给，现有 %d 份。" % [cost, supply], ALERT, 16)
	if not blocker.is_empty():
		_label(actions, blocker + "。可回队伍与装备调整。", ALERT, 16)
	var route := "常规短途" if selected.is_empty() else "%s讨伐" % selected.name
	var departure := "前往%s，消耗 %d 份仓库补给。" % [route, cost]
	var market: Dictionary = view.get("book_market", {})
	if market.has("departure_cap"):
		departure += "\n本趟普通技能书额度 · %d 本" % int(market.departure_cap)
	if not market.get("target", {}).is_empty():
		departure += "\n出发时锁定技能书定向「%s」 · %d/2" % [market.target.name, int(market.progress)]
		if int(market.progress) >= 2:
			departure += "\n本趟首次领取的普通书将替换为目标书。"
	var defense: Dictionary = view.get("town_services", {}).get("defense", {})
	if defense.get("ready", false) and defense.spec.mode == "defense":
		var targets: Array = defense.targets.filter(func(member): return member.travels)
		if not targets.is_empty():
			departure += "\n防御整备 · %s · 出战时物防、魔防各 +%d" % [
				"、".join(targets.map(func(member): return member.name)), int(defense.spec.amount)]
	var material: Dictionary = view.get("material_goal", {})
	if selected.is_empty():
		for option in material.get("options", []):
			if option.id == material.current:
				departure += "\n材料委托 · " + _service_cost(option.materials)
				break
	_input_action("出发 · 消耗 %d 补给" % cost, "depart", ["CONFIRM"],
		_day_consequence(departure), supply >= cost and blocker.is_empty())
	_label(actions, "库存 %d 铜 · %d 补给 · 携带救护 %d 份" % [copper, supply, int(view.medical)], INK, 17)
	_buy_supply()
	var packed := int(view.medical)
	if packed < int(prep.medical_cap):
		_input_action("打包 1 份额外救护", "pack_medical", [str(packed + 1)], "从仓库划转 1 份补给供途中救护。", supply > 0)
	if packed > 0:
		_input_action("放回 1 份额外救护", "pack_medical", [str(packed - 1)])
	_rest_action()
	_input_action("城镇维护一日", "maintain", ["CONFIRM"], _day_consequence("推进 1 个行动日，按现有资产结算维护补差。"))
	_plan_actions()


func _plan_actions() -> void:
	var owned: Array = view.get("owned_plans", [])
	if owned.is_empty():
		return
	var equipped: Array = view.get("equipped_plans", [])
	_label(actions, "战前方案 · 已采用 %d/3" % equipped.size(), GOLD, 17)
	for plan in owned:
		var enabled := equipped.has(plan.id)
		var next := equipped.duplicate()
		if enabled:
			next.erase(plan.id)
		else:
			next.append(plan.id)
		if next.is_empty():
			next.append("clear")
		var title := ("撤下" if enabled else "采用") + " · " + str(plan.name)
		_input_action(title, "plan", next, "", next.size() <= 3)
		command_buttons["plan " + " ".join(next)].tooltip_text = plan.rule
	if equipped.size() > 1:
		_input_action("撤下战前方案", "plan", ["clear"])


func _memory_actions(memory: Dictionary, command: String) -> void:
	var recall := command == "remember"
	_label(actions, "%s · %s" % [memory.general, "追忆" if recall else "战斗暂停"], GOLD, 24)
	_label(actions, "第 %d / 2 段" % int(memory.number), MUTED, 16)
	if memory.enabled:
		var lead: Dictionary = memory.lead
		var choice := "出示%s与证词" % memory.item
		if memory.choice == "evidence":
			_label(actions, "%s  %s" % [lead.speaker, lead.text], INK, 19)
		else:
			choice = "%s  %s" % [lead.speaker, lead.text]
		_input_action(choice, command, [memory.choice, memory.id])
	else:
		_label(actions, "请先暂离追忆，再进入并补做第 1 段。" if recall else "第 1 段尚未提交。胜利后可在暮汀补做。", MUTED, 16)
	_input_action("跳过这段记忆", command, ["skip", memory.id])
	if recall:
		_input_action("暂离追忆", "remember", ["close"])


func _settlement_actions() -> void:
	var scouting_delivered: bool = view.get("scouting", {}).get("delivered_here", false)
	_label(actions, "侦路调查已交付" if scouting_delivered else "远征结算", GOLD, 24)
	_summary()
	var hunt := _pending_hunt_report(view, true)
	if view.get("phase") == "RETURNED" and not hunt.is_empty():
		_label(actions, "%s讨伐报告可在暮汀旧档案交存。" % hunt.name, INK, 17)
		_input_action("返回暮汀旧档案", "town", [])
	elif scouting_delivered:
		_label(actions, "可在暮汀旧档案请许苇核对远眺记录。", INK, 17)
		_input_action("返回暮汀旧档案", "town", [])
	elif view.get("phase") in ["RETURNED", "FAILED"]:
		_input_action("返回暮汀整备", "town", [])


func _rescue_office(can_act := true) -> void:
	var rescue: Dictionary = view.get("rescue", {})
	_label(actions, "搜救所", GOLD, 24)
	for batch in rescue.get("batches", []):
		if not batch.members.is_empty():
			_rescue_batch(batch, int(rescue.cost), can_act)
		if not batch.recovered.is_empty():
			_label(actions, "%s · 已救回" % batch.id, INK, 16)
			for member in batch.recovered:
				_label(actions, _name(member), MUTED, 16)
		if not batch.lost.is_empty():
			_label(actions, "%s · 第 %d 日到期，人员已永久损失" % [batch.id, int(batch.deadline)], ALERT, 16)
			for member in batch.lost:
				_label(actions, _name(member), MUTED, 16)
	if can_act:
		_label(actions, "仓库补给 %d" % int(view.supply), MUTED, 16)
		_buy_supply()
		_rest_action()


func _rescue_batch(batch: Dictionary, cost: int, can_act: bool) -> void:
	var deadline := int(batch.deadline)
	var tomorrow := int(view.day) + 1
	_label(actions, "%s · %s" % [batch.id, "转运点已确认" if batch.known else "失联 · 去向待查"], GOLD, 18)
	_label(actions, "第 %d 日登记 · 最迟第 %d 日救回" % [int(batch.day), deadline], INK, 16)
	if not str(batch.origin_region).is_empty():
		_label(actions, "最后出现于 %s · %s" % [batch.origin_region, batch.origin_site_name], MUTED, 16)
	for member in batch.members:
		var gear_names: Array = member.get("equipment_names", [])
		var gear := " · 原装备 " + "、".join(gear_names) if not gear_names.is_empty() else ""
		_label(actions, _name(member) + gear, MUTED, 16)
	if not can_act:
		return
	var supply_ok := int(view.supply) >= cost
	var blocker: String = view.preparation.deployment_error
	if not blocker.is_empty():
		_label(actions, blocker + "。请先调整救援小队。", ALERT, 16)
	if not supply_ok:
		_label(actions, "需要 %d 份仓库补给。" % cost, ALERT, 16)
	var ready := supply_ok and blocker.is_empty()
	if batch.known:
		var detail := "%s 救援需一战，计划第 %d 日归城。" % [batch.id, tomorrow]
		_input_action("出发救援 · %d 补给" % cost, "rescue", [batch.id, "CONFIRM"],
			_with_expiry_warning(detail, batch.other_due), ready and tomorrow <= deadline)
	else:
		_label(actions, "已核对行进痕迹" if "tracks" in batch.steps else "待核对行进痕迹", MUTED, 16)
		if not batch.can_finish_in_time:
			_label(actions, "调查后最早第 %d 日可救回，已赶不上原期限。" % (tomorrow + 1), ALERT, 16)
		var detail := "%s 调查无战斗，计划第 %d 日归城。随后最早第 %d 日可救回。" % [batch.id, tomorrow, tomorrow + 1]
		if not batch.can_finish_in_time:
			detail += "\n最早救回日已超过第 %d 日期限。" % deadline
		_input_action("出发调查 · %d 补给" % cost, "rescue", ["investigate", "start", batch.id, "CONFIRM"], _day_consequence(detail), ready)


func _search_actions() -> void:
	var active: Dictionary = view.rescue.active
	for batch in view.rescue.batches:
		if batch.id != active.id:
			continue
		_label(actions, "失联调查 · " + batch.id, GOLD, 24)
		var px := 21 if settings["大字"] else 16
		_label(actions, "计划第 %d 日归城 · 最迟第 %d 日救回" % [int(active.returns_on), int(batch.deadline)], INK, px)
		var names: Array = batch.members.map(func(member: Dictionary) -> String: return _name(member))
		_label(actions, "待救回  " + "、".join(names), INK, px)
		_label(actions, "最后出现于 %s · %s" % [batch.origin_region, batch.origin_site_name], MUTED, px)
		if "tracks" not in batch.steps:
			_input_action("核对行进痕迹", "rescue", ["investigate", "inspect", "tracks"])
		elif "marker" not in batch.steps:
			_label(actions, "行进痕迹已记录", MUTED, 16)
			_input_action("沿交接标记查找转运点", "rescue", ["investigate", "inspect", "marker"])
		else:
			_label(actions, "两项线索已齐，回城交存后确认转运点。", INK, 16)
		var detail := "结束本次调查，结算至第 %d 日。已核对的线索会保留。" % int(active.returns_on)
		_input_action("返回暮汀交存调查", "rescue", ["investigate", "return", "CONFIRM"], _with_expiry_warning(detail, active.due))
		break


func _toggle_overlook() -> void:
	_overlook_open = not _overlook_open
	focus_key = "tutorial observe" if _overlook_open and not view.get("observation") is Dictionary else (
		"overlook-back" if _overlook_open else "overlook-inspect")
	_render()


func _explore_actions() -> void:
	if _overlook_open:
		_label(actions, "望向根口", GOLD, 24)
		_label(actions, "根口已清理" if board._root_cleared() else "旧路上有两团枝影", INK, 17)
		_overlook_observation_actions()
		_button("返回路线图", "overlook-back", _toggle_overlook)
		return
	var site := str(view.get("site", ""))
	var route: Dictionary = view.get("route", {})
	_label(actions, _site_name(site, "道路与现场"), GOLD, 24)
	if field_items_open:
		_button("返回路线", "field-items", _toggle_field_items)
		_consumables_actions(false)
		return
	var bag: Dictionary = view.get("consumables", {})
	if not bag.is_empty():
		_button("随身道具 · %d/4" % int(bag.slots), "field-items", _toggle_field_items)
	var scouting: Dictionary = view.get("scouting", {})
	var return_to_overlook: bool = site == "X" and int(scouting.get("battles", 0)) == 2 \
		and not scouting.observed and "G" in route.get("neighbors", [])
	if not scouting.is_empty():
		var observed := "远眺已记录" if scouting.observed else "远眺待记录"
		_label(actions, "侦路调查 · 两战 %d/2 · %s" % [int(scouting.battles), observed], MUTED, 16)
	if route.get("contact_pending", false):
		var map_data: Dictionary = model.get("map", {})
		var enemies: Array = map_data.get("enemy_preview", [])
		var blocker := str(route.get("deployment_error", ""))
		if not blocker.is_empty():
			_label(actions, blocker, ALERT, 16)
		_input_action("确认开战", "fight", [], "按当前部署开战。战斗会自动推进，可按空格暂停。", blocker.is_empty(), _contact_controls)
		command_buttons["fight"].custom_minimum_size.x = 154.0
		_input_action("返回道路", "retreat", [], "", true, _contact_controls)
		var spacer := Control.new()
		spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		spacer.size_flags_horizontal = SIZE_EXPAND_FILL
		_contact_controls.add_child(spacer)
		if not enemies.is_empty():
			_label(actions, "来敌 %d 人 · 点击定位" % enemies.size(), MUTED, 16)
			var group := ButtonGroup.new()
			group.allow_unpress = true
			for enemy in enemies:
				var entry := _button("%s  %s" % [enemy.badge, enemy.name], "inspect-enemy-" + enemy.id,
					board.select_contact_enemy.bind(enemy.id), not client.busy)
				entry.theme_type_variation = &"FieldUnit"
				entry.toggle_mode = true
				entry.button_group = group
				entry.set_pressed_no_signal(board.contact_enemy_id == enemy.id)
		_plan_actions()
		_member_actions(map_data.get("deploy_cells", []))
		return
	if "G" in route.get("cleared", []):
		if view.get("region") == "RG02" and view.get("hunt", {}).get("report_pending_return", false):
			_label(actions, "主堡战已结束。可经北堡出口归城，也可沿原路返回入口。安全归城后可交存报告。", INK, 16)
		elif _sev_report_pending_return():
			_label(actions, "赛芙战已结束。可经北林海出口归城，也可沿原路返回入口。安全归城后可交存报告。", INK, 16)
	if view.get("tutorial_area", false):
		var choices: Dictionary = view.get("choice_notes", {})
		var choice_key := {"A": "plan", "B_SUPPORT": "support", "B_MATERIAL": "materials", "G": "cache"}.get(site, "") as String
		if choices.has(choice_key):
			_label(actions, choices[choice_key], MUTED, 16)
		else:
			_site_actions(site)
	_field_book_spoils()
	_field_handbook_event()
	for task in view.get("book_research", []):
		if int(task.pending) > 0:
			_label(actions, "%s · %d 场待归城入账" % [task.name, int(task.pending)], MUTED, 16)
	var material: Dictionary = view.get("material_goal", {})
	if not material.is_empty():
		var where: String = material.region if material.region_id != view.region else _site_name(material.site, material.region)
		var status: String = "已领取，待归城入库" if material.picked else ("本站已选择其他结果" if material.closed else "待领取")
		_label(actions, "材料委托 · %s · %s · %s" % [_service_cost(material.materials), where, status], MUTED, 16)
	_plan_actions()
	_field_equipment()
	_field_skill_books()
	if route.get("station", false):
		_input_action("使用本区救护箱", "station", [], "消耗本站一次救护，恢复受伤的站立队员。")
	if route.get("camp", false):
		_input_action("使用边界营地", "camp", [], "使用本处一次营地恢复站立队员并减轻侵蚀。")
	if route.get("medical", false):
		_input_action("使用额外救护 · 剩余 %d 份" % int(view.medical), "medical", [], "消耗 1 份随队救护，恢复受伤的站立队员。")
	for entry in route.get("next_regions", []):
		_input_action("跨区前往 " + entry.name, "next", [entry.id, "CONFIRM"], "离开本区，前往%s。" % entry.name)
	if route.get("safe_return", false):
		var consequence := _return_consequence(scouting)
		if return_to_overlook:
			consequence += "\n如要本趟交付，可取消归城并经根口返回远眺点。"
		var carried := _cargo_amounts(view.get("field_book_rewards", {}).get("carried", {}))
		if not carried.is_empty():
			consequence += "\n随队技能书将入库\n" + carried
		_input_action("确认归城", "return", ["CONFIRM"], _day_consequence(consequence))
	for place in route.get("neighbors", []):
		var caption := "经根口返回远眺点" if return_to_overlook and place == "G" else "前往 " + _site_name(place, place)
		_input_action(caption, "move", [place])
	if site == "<null>" or site.is_empty():
		for place in route.get("nearby", []):
			_input_action("交互 " + _site_name(place, place), "interact", [place])
		var map_data: Dictionary = model.get("map", {})
		for node in map_data.get("objects", []):
			if node.get("id") != "I":
				continue
			var pos: Array = node["position"]
			_input_action("沿已知道路返回入口", "walkto", [str(int(pos[0])), str(int(pos[1]))])


func _sev_report_pending_return() -> bool:
	var sev: Dictionary = view.get("sev_hunt", {})
	return sev.get("report_pending_return", false) and view.get("region") == sev.region


func _return_consequence(scouting: Dictionary) -> String:
	if scouting.is_empty():
		if _sev_report_pending_return():
			return "安全归城后，可在暮汀旧档案交存赛芙讨伐报告。"
		if view.get("hunt", {}).get("report_pending_return", false):
			return "安全归城后，可在暮汀旧档案交存阿铎讨伐报告。"
		return "结束本趟远征并按实际结果归城。"
	if scouting.ready:
		return "安全归城将交付本趟侦路调查。"
	var missing := _scouting_missing(scouting)
	if missing.is_empty():
		return "可以安全归城。当前存档无法交付侦路调查。"
	return "可以提前归城。本趟还缺%s。再次出发会开启新一趟侦路。" % missing


func _scouting_missing(scouting: Dictionary) -> String:
	var names := {"INTRO-EN01": "林道战胜利", "TUT01-ROOT": "根口战胜利"}
	var missing: PackedStringArray = []
	for encounter in scouting.get("missing_battles", []):
		missing.append(names[encounter])
	if not scouting.get("observed", false):
		missing.append("远眺点（D）观察")
	return "、".join(missing)


func _site_actions(site: String) -> void:
	match site:
		"A":
			for plan in view.get("plan_offers", []):
				_input_action("登记 · " + plan.name, "tutorial", ["plan", plan.id],
					"登记「%s」后可在战前方案中采用。\n%s" % [plan.name, plan.rule])
			if not view.get("plan_offers", []).is_empty():
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
			if board._overlook_art != null:
				_button("放大远眺图", "overlook-inspect", _toggle_overlook)
			_overlook_observation_actions()
		"G":
			if not view.get("gear_offers", []).is_empty():
				if view.get("gear_claims", 0) > 0:
					for item in view["gear_offers"]:
						var compatible: bool = item in view.get("gear_compatible", [])
						var detail := "队伍中有适配兵种" if compatible else "队伍中暂无适配兵种"
						var gear: String = view.get("gear_offer_names", {}).get(item, item)
						_input_action("领取装备 · " + gear + "  /  " + detail, "tutorial", ["cache", item],
							"消耗一次领取额度，装备收入行囊。%s。" % detail)
				else:
					_label(actions, "本趟装备领取额度已用完。", MUTED, 16)
				_input_action("放弃装备", "tutorial", ["cache", "PASS"], "结束本场战后的装备选择。")


func _overlook_observation_actions() -> void:
	if view.get("observation") is Dictionary:
		_label(actions, view["observation"]["observed"], INK, 16)
		var scouting: Dictionary = view.get("scouting", {})
		if not view.get("complete", false) and not scouting.is_empty():
			if scouting.ready:
				_label(actions, "两战和远眺记录已齐。安全归城后，请许苇在旧档案核对。", MUTED, 16)
			elif not scouting.missing_battles.is_empty():
				_label(actions, "本趟还缺%s。补齐后安全归城，再请许苇核对旧日志。" % _scouting_missing(scouting), MUTED, 16)
	else:
		_input_action("观察并记录", "tutorial", ["observe"])


func _build_combat_actions() -> void:
	actions = _combat_actions
	command_buttons = _combat_buttons
	_battle_heading = _label(actions, "", GOLD, 24)
	_battle_plans = _label(actions, "", MUTED, 16)
	_battle_rescue = _label(actions, "", INK, 16)
	var playback := _button("继续战斗", "combat-playback", _toggle_playback, true, _battle_controls)
	playback.tooltip_text = "空格 · 暂停或继续战斗"
	playback.custom_minimum_size.x = 154.0
	_input_action("下一拍", "step", [], "", true, _battle_controls)
	var pace := _button(_pace_label(), "combat-pace", _cycle_battle_pace, true, _battle_controls)
	pace.tooltip_text = "点击切换慢速、常速和快速"
	var spacer := Control.new()
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spacer.size_flags_horizontal = SIZE_EXPAND_FILL
	_battle_controls.add_child(spacer)
	_button("战报", "battle-log", _toggle_battle_log, true, _battle_controls)
	_button("撤退", "flee CONFIRM", _request_retreat, true, _battle_controls)
	_button("设置", "settings", _show_settings, true, _battle_controls)
	for button: Button in command_buttons.values():
		button.autowrap_mode = TextServer.AUTOWRAP_OFF
		button.alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.custom_minimum_size.y = 37.0
	_live_battle_log = CombatLog.new()
	actions.add_child(_live_battle_log)
	_battle_roster = VBoxContainer.new()
	_battle_roster.add_theme_constant_override("separation", 7)
	actions.add_child(_battle_roster)
	_enemy_heading = _label(_battle_roster, "敌阵", Color("e7a17b"), 19)
	_leaders = VBoxContainer.new()
	_battle_roster.add_child(_leaders)
	_foes = _add_unit_grid(_battle_roster)
	_ally_heading = _label(_battle_roster, "我方", Color("a6c8b5"), 19)
	_allies = _add_unit_grid(_battle_roster)
	_battle_detail = _label(_battle_roster, "", GOLD, 15)
	for detail in [_battle_plans, _battle_rescue, _live_battle_log, _battle_detail]:
		detail.hide()
	actions = _general_actions
	command_buttons = _general_buttons


func _add_unit_grid(parent: Container) -> GridContainer:
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 6)
	parent.add_child(grid)
	return grid


func _request_retreat() -> void:
	var withdrawal := "撤退时将结算一拍追击。成功撤出可带回行囊物资，战败时会丢失。"
	var carried := _cargo_amounts(view.get("field_book_rewards", {}).get("carried", {}))
	if not carried.is_empty():
		withdrawal += "\n随队技能书\n" + carried
	confirmation = {"command": "flee", "args": ["CONFIRM"], "text": _day_consequence(withdrawal), "back": "flee CONFIRM"}
	focus_key = "cancel"
	_render()


func _prepare_contact_battle_rows() -> void:
	var roster: Array = []
	for member in view.get("party", []):
		if member.deployed and member.deployable:
			roster.append({"id": member.instance_id, "kind": member.unit_id, "side": "player"})
	roster.append_array(model.get("map", {}).get("enemy_preview", []))
	_sync_battle_rows(roster)


func _sync_battle_rows(roster: Array) -> void:
	var ids := roster.map(func(actor): return actor.id)
	if ids == _battle_rows.keys():
		return
	for id in _battle_rows:
		if id not in ids:
			_combat_buttons.erase("battle-unit-" + id)
			var tile: Button = _battle_rows[id]
			tile.get_parent().remove_child(tile)
			tile.queue_free()
	var rows := {}
	var positions := {_leaders: 0, _foes: 0, _allies: 0}
	for actor: Dictionary in roster:
		var id: String = actor.id
		var leader: bool = actor.get("kind") == "MG01" and actor.side == "enemy"
		var parent: Container = _leaders if leader else (_foes if actor.side == "enemy" else _allies)
		var tile: CombatTile = _battle_rows.get(id)
		if tile == null:
			tile = CombatTile.new()
			_new_button("", "battle-unit-" + id, _inspect_battle_actor.bind(id), true, tile)
			tile.setup(ADO_HUD_PORTRAIT if leader else null)
			parent.add_child(tile)
		if tile.get_index() != positions[parent]:
			parent.move_child(tile, positions[parent])
		positions[parent] += 1
		rows[id] = tile
	for group: Container in positions:
		group.visible = positions[group] > 0
	_battle_rows = rows


func _update_combat_actions(snapshot: Dictionary) -> void:
	var target: Dictionary = view.get("rescue", {}).get("target", {})
	_battle_heading.text = "战报" if _battle_log_open else ("转运点救援" if not target.is_empty() else "")
	_battle_heading.visible = not _battle_heading.text.is_empty()
	var plans: Array = snapshot.get("plan_names", [])
	_battle_plans.visible = not plans.is_empty()
	if _battle_plans.visible:
		_battle_plans.text = "生效方案 · " + "、".join(plans)
	_battle_rescue.visible = not target.is_empty()
	if _battle_rescue.visible:
		_battle_rescue.text = "%s · %d 人 · 最迟第 %d 日" % [target.batch_id, target.member_ids.size(), int(target.deadline)]
		_battle_rescue.text += "\n待救回  " + "、".join(target.get("member_names", target.member_ids))
		var px := 21 if settings["大字"] else 16
		if _battle_rescue.get_theme_font_size("font_size") != px:
			_battle_rescue.add_theme_font_size_override("font_size", px)
	_live_battle_log.visible = _battle_log_open
	_battle_roster.visible = not _battle_log_open
	command_buttons["battle-log"].text = "关闭战报" if _battle_log_open else "战报"
	if _battle_log_open:
		for id in _battle_rows:
			command_buttons.erase("battle-unit-" + id)
		_live_battle_log.update_entries(_combat_log(snapshot), 20 if settings["大字"] else 16)
	else:
		var roster: Array = view.get("actors", [])
		_sync_battle_rows(roster)
		var total := 0
		var standing := 0
		for actor in roster:
			var tile: CombatTile = _battle_rows[actor.id]
			command_buttons["battle-unit-" + actor.id] = tile
			tile.update_actor(actor, _battle_health(actor), settings["大字"])
			if actor.side == "player":
				total += 1
				standing += int(int(actor.hp) > 0)
		_enemy_heading.visible = _leaders.visible or _foes.visible
		_ally_heading.visible = total > 0
		_ally_heading.text = "我方  %d / %d" % [standing, total]
		_update_battle_focus()
	for key in command_buttons:
		command_buttons[key].disabled = client.busy and key in ["step", "flee CONFIRM", "combat-pace"]
	command_buttons["combat-playback"].text = "Ⅱ  暂停" if _playback_running else "▶  继续战斗"
	command_buttons["step"].visible = not _playback_running
	command_buttons["combat-pace"].text = _pace_label()


func _can_toggle_playback() -> bool:
	return client != null and not client.blocked and not _close_after_save and opened and not _playback_battle.is_empty() \
		and view.get("battle_memory", {}).is_empty() and not settings_open and not captions_open and confirmation.is_empty()


func _toggle_playback() -> void:
	if not _can_toggle_playback():
		return
	_playback_running = not _playback_running
	focus_key = "combat-playback"
	command_buttons["combat-playback"].text = "暂停战斗 · 空格" if _playback_running else "继续战斗 · 空格"
	command_buttons["step"].visible = not _playback_running
	command_buttons["combat-playback"].grab_focus()
	_schedule_battle()


func _schedule_battle() -> void:
	if not _playback_running or not _can_toggle_playback() or client.busy \
		or not _window_allows_playback():
		_battle_timer.stop()
	elif _battle_timer.is_stopped():
		var delay: Vector2 = BATTLE_DELAYS[_battle_pace]
		var seconds := delay.y if _new_warning else delay.x
		_battle_timer.start(MEMORY_REPLY_SECONDS if not _memory_reply.is_empty() else seconds)


func _sync_window_minimize() -> void:
	var minimized := _window_minimized()
	if minimized != _window_was_minimized:
		_window_was_minimized = minimized
		if minimized:
			_suspend_window_input()
		board.stage.set_window_hidden(minimized)
		_resume_visible_presentation()


func _suspend_window_input() -> void:
	_battle_timer.stop()
	board.cancel_deployment_drag()


func _resume_visible_presentation() -> void:
	_flush_receipt_sounds()
	_schedule_battle()


func _window_minimized() -> bool:
	return DisplayServer.window_get_mode(get_window().get_window_id()) == DisplayServer.WINDOW_MODE_MINIMIZED


func _window_allows_playback() -> bool:
	return DisplayServer.get_name() == "headless" or (get_window().has_focus() and not _window_minimized())


func _pace_label() -> String:
	return "节奏 · " + BATTLE_PACES[_battle_pace]


func _cycle_battle_pace() -> void:
	if not _can_toggle_playback() or client.busy:
		return
	_battle_pace = posmod(_battle_pace + 1, BATTLE_PACES.size())
	focus_key = "combat-pace"
	_battle_timer.stop()
	_save_settings()


func _advance_automatically() -> void:
	if _playback_running and _can_toggle_playback() and not client.busy and _window_allows_playback():
		client.submit("step", [])


func _battle_health(actor: Dictionary) -> String:
	var phase := " · 阶段 %d" % int(actor.boss_phase) if actor.has("boss_phase") else ""
	var health := "倒地" if int(actor.hp) <= 0 else "生命 %d/%d" % [int(actor.hp), int(actor.max_hp)]
	var other_shield := int(actor.get("private_shield", 0)) - int(actor.get("boss_barrier", 0))
	var protection := " · 自身盾 %d" % other_shield if other_shield > 0 else ""
	if actor.has("shared_protection"):
		protection += " · 共享盾"
	return "%s   %s%s%s" % [_combatant_name(actor.id), health, phase, protection]


func _combatant_name(id: String) -> String:
	var actor: Dictionary = _combatants.get(id, {})
	return ("%s %s" % [actor.get("badge", ""), actor.get("display_name", "单位")]).strip_edges() if not actor.is_empty() else "单位"


func _combat_move(id: String) -> String:
	var snapshot: Variant = view.get("battle_view")
	var fallback := "普攻" if id == "BASIC" else "招式"
	if snapshot is Dictionary:
		return snapshot.get("move_names", {}).get(id, ADO_MOVE_NAMES.get(id, fallback))
	return ADO_MOVE_NAMES.get(id, fallback)


func _inspect_battle_actor(id: String) -> void:
	if _playback_battle.is_empty() or settings_open or captions_open or not confirmation.is_empty():
		return
	if not view.get("battle_memory", {}).is_empty() or not _combatants.has(id):
		return
	_battle_inspected = id
	focus_key = "battle-unit-" + id
	if _battle_log_open:
		_battle_log_open = false
		_render()
	else:
		_update_battle_focus()
		if command_buttons.has(focus_key):
			command_buttons[focus_key].grab_focus()


func _update_battle_focus() -> void:
	for id in _battle_rows:
		_battle_rows[id].set_pressed_no_signal(id == _battle_inspected)
	board.focus_battle_actor(_battle_inspected)
	var actor: Dictionary = _combatants.get(_battle_inspected, {})
	_battle_detail.visible = not actor.is_empty()
	if actor.is_empty():
		return
	_battle_detail.text = _combatant_name(actor.id)
	_battle_detail.tooltip_text = ""
	if actor.get("pos") is Array:
		var cell := Board.cell_index(actor.pos)
		_battle_detail.tooltip_text = "位置 %d,%d" % [cell.x, cell.y]
	var own_shield := int(actor.get("private_shield", 0))
	if own_shield > 0:
		_battle_detail.text += "\n自身护盾 %d" % own_shield
	if int(actor.get("town_defense_bonus", 0)) > 0:
		_battle_detail.text += "\n工坊整备 · 物防、魔防各 +%d" % int(actor.town_defense_bonus)
	for pool in actor.get("shared_protection", []):
		_battle_detail.text += "\n共享盾池 %d · %s · 至第 %d 拍" % [
			int(pool.amount), _combatant_name(pool.owner), int(pool.expires)]
	var battle: Dictionary = view.battle_view
	var impact: Dictionary = battle.get("impacts", {}).get(actor.id, {})
	if not impact.is_empty():
		_battle_detail.text += "\n第 %d 拍 · %s" % [int(battle.tick), Board.impact_text(impact)]
	_battle_detail.visible = _battle_detail.text.contains("\n")


func _toggle_battle_log() -> void:
	_battle_log_open = not _battle_log_open
	_action_scroll.scroll_vertical = 0
	focus_key = "battle-log"
	_render()


func _finished_battle(snapshot: Dictionary) -> void:
	var result: String = REASONS.get(snapshot.result, "已结束")
	var allies := 0
	var standing := 0
	for actor in snapshot.actors:
		if actor.side == "player":
			allies += 1
			if float(actor.hp) > 0:
				standing += 1
	_label(actions, "最近一战 · %s · %d 拍\n我方站立 %d/%d" % [result, int(snapshot.tick), standing, allies], GOLD, 17)
	_button("收起战报" if _battle_log_open else "查看战报", "battle-log", _toggle_battle_log)
	if _battle_log_open:
		var log := CombatLog.new()
		log.divider = Color("3d5654")
		actions.add_child(log)
		log.update_entries(_combat_log(snapshot), 20 if settings["大字"] else 16)


func _combat_log(snapshot: Dictionary) -> Array[Dictionary]:
	var entries: Array[Dictionary] = []
	for event in snapshot.get("recent", []):
		var actor := _combatant_name(event.get("actor", ""))
		var move := _combat_move(event.get("move", ""))
		var detail := ""
		match event.type:
			"release":
				detail = actor + " 施展" + move
			"heal":
				detail = "%s 使 %s 回复 %d 生命" % [actor, _combatant_name(event.target), int(event.effective)]
			"cast_delayed":
				detail = "%s 将 %s 的施法延至第 %d 拍" % [actor, _combatant_name(event.target), int(event.release_tick)]
			"guard_redirect":
				detail = "%s 为 %s 代受攻击" % [actor, _combatant_name(event.ward)]
			"shared_shield":
				var recipients: PackedStringArray = []
				for id in event.members:
					recipients.append(_combatant_name(id))
				detail = "%s 为 %s 提供 %d 点共享护盾，持续至第 %d 拍" % [actor,
					"、".join(recipients), int(event.amount), int(event.expires)]
			"skill_miss":
				detail = actor + " 的" + move + "落空"
			"down":
				detail = actor + " 倒地"
			"boss_phase":
				detail = "%s 进入第 %d 阶段" % [actor, int(event.phase)]
			"boss_private_shield":
				detail = "%s 获得 %s 护盾" % [actor, str(event.amount).trim_suffix(".0")]
			"private_shield":
				detail = "%s 架刀获得 %d 点自身护盾，持续至第 %d 拍" % [actor, int(event.amount), int(event.expires)]
			"boss_memory_choice":
				detail = "已记录阿铎的记忆选择"
			"hit":
				detail = "%s 命中 %s，伤害 %s，吸收 %s" % [actor, _combatant_name(event.get("target", "")),
					str(event.get("actual_hp_damage", 0)).trim_suffix(".0"), str(event.get("absorbed", 0)).trim_suffix(".0")]
		if not detail.is_empty():
			entries.append({"tick": int(event.tick), "detail": detail})
	return entries


func _name(member: Dictionary) -> String:
	return str(member.get("display_name", "队员"))


func _recovery_actions(member: Dictionary) -> void:
	var prep: Dictionary = view.get("preparation", {})
	if prep.is_empty():
		return
	var copper := int(view.town_roster.copper)
	var id: String = member.instance_id
	var cost := int(member.get("heal_cost", 0))
	var injured := int(member.injury_days) > 0
	if cost > 0:
		var detail := "支付 %d 铜，恢复该队员的生命。" % cost
		if injured:
			detail += "旧伤仍需结算休整。"
		_input_action("恢复生命 · %d 铜" % cost, "heal", [id], detail, copper >= cost)
	if injured:
		_label(actions, "旧伤剩余 %d 日" % int(member.injury_days), ALERT, 16)
		_input_action("安排伤护 · 1 补给", "care", [id], "下一行动日额外缩短 1 日旧伤。", int(view.supply) > 0 and prep.care_scheduled == null)
	var xp := int(member.get("next_xp", 0))
	if xp > 0:
		_label(actions, "经验 %d/%d" % [int(member.xp), xp], MUTED, 15)
		var price := int(prep.level_price)
		if int(member.xp) >= xp:
			_input_action("升级 · %d 铜" % price, "level_up", [id], "消耗 %d 经验及 %d 铜。" % [xp, price], copper >= price)


func _field_equipment() -> void:
	var gear: Dictionary = view.get("equipment", {})
	if gear.get("inventory", []).is_empty() and gear.get("worn", {}).is_empty():
		return
	_button("收起行囊装备" if field_gear_open else "查看行囊装备", "field-gear", _toggle_field_gear)
	if not field_gear_open:
		return
	var any_member := false
	for member in view.get("party", []):
		if not _can_manage_gear(member):
			continue
		any_member = true
		var id: String = member.instance_id
		_button("装备 · " + _name(member), "gear-member-" + id, _choose_member.bind(id), id != selected_id)
		if selected_id == id:
			_equipment_actions(member)
	if not any_member:
		_label(actions, "当前随队没有适配行囊装备的成员。", MUTED, 16)


func _field_book_spoils() -> void:
	var rewards: Dictionary = view.get("field_book_rewards", {})
	if rewards.has("cap"):
		_label(actions, "普通技能书 · 本趟已领 %d/%d" % [int(rewards.used), int(rewards.cap)], MUTED, 16)
	var target: Dictionary = rewards.get("target", {})
	if not target.is_empty():
		var detail := "定向「%s」 · %d/2" % [target.name, int(target.progress)]
		if target.carried:
			detail += " · 目标书已在行囊"
		elif target.guaranteed:
			detail += " · 首次领取替换为目标书"
		_label(actions, detail, MUTED, 16)
	var carried := _cargo_amounts(rewards.get("carried", {}))
	if not carried.is_empty():
		_label(actions, "行囊技能书 · 待归城入库\n" + carried, MUTED, 16)
	var offer: Dictionary = rewards.get("offer", {})
	if offer.is_empty():
		return
	var book: Dictionary = offer.book
	var source := "定向战利书" if target.get("guaranteed", false) and offer.can_claim else "战利书"
	_label(actions, "%s · 「%s」" % [source, book.name], GOLD, 17)
	if offer.can_claim:
		_label(actions, "离开此处会放弃这本书。", MUTED, 16)
		_input_action("领取到行囊", "book", ["claim"],
			"领取「%s」，使用 1 个本趟技能书额度。安全带回后入库。\n%s\n%s" % [book.name, book.timing, book.summary])
	else:
		_label(actions, "本趟技能书领取额度已用完。", MUTED, 16)
	_input_action("放弃此处战利书", "book", ["drop"], "放弃「%s」，结束这处的战利书领取。" % book.name)


func _field_handbook_event() -> void:
	var event: Dictionary = view.get("handbook_event", {})
	if event.is_empty():
		return
	_label(actions, event.name, GOLD, 18)
	if event.has("resolved"):
		_label(actions, "本站已处理 · " + event.resolved, INK, 16)
		return
	_label(actions, event.description, MUTED, 16)
	_label(actions, "本站只能选一项。可以暂离后回访。", MUTED, 16)
	if event.has("book"):
		var book: Dictionary = event.book
		var guaranteed: bool = view.get("field_book_rewards", {}).get("target", {}).get("guaranteed", false) and event.can_claim
		var name := ("领取定向手册 · " if guaranteed else "领取手册 · ") + str(book.name)
		_input_action(name, "choose", ["BOOK"],
			"将「%s」加入行囊，安全带回后入库。占 1 个技能书额度，结束本站其他选项。\n%s\n%s" % [
				book.name, book.timing, book.summary], event.can_claim)
	for option in event.choices:
		var materials: bool = option.kind == "materials"
		var description := "将一件装备放入行囊。"
		if materials:
			var amount := ("当地材料 ×%d" % int(option.units)) if option.fixed.is_empty() else _cargo_amounts(option.fixed)
			description = "将%s加入行囊，安全带回后入库。" % amount
		if int(option.erosion) > 0:
			description += "随队人员侵蚀 +%d。" % int(option.erosion)
		if not option.allowed:
			_label(actions, "本趟%s额度不足。" % ("材料" if materials else "装备"), ALERT, 16)
		_input_action(option.label, "choose", [option.id],
			description + "结束本站其他选项。", option.allowed)


func _toggle_field_gear() -> void:
	field_gear_open = not field_gear_open
	_render()


func _available_gear(member: Dictionary) -> Array:
	var kind: String = "H01" if member.unit_id == "CMD" else member.unit_id
	var inventory: Array = view.get("equipment", {}).get("inventory", [])
	return inventory.filter(func(item: Dictionary) -> bool: return kind in item.allowed)


func _can_manage_gear(member: Dictionary) -> bool:
	return not member.equipment.is_empty() or not _available_gear(member).is_empty()


func _gear_stat_change(worn: Dictionary, replacement: Dictionary, cost: String) -> String:
	var before: Dictionary = worn.get("stats", {}).get(cost, {})
	var after: Dictionary = replacement.get("stats", {}).get(cost, {})
	var changes: PackedStringArray = []
	for key in GEAR_STATS:
		var delta := int(after.get(key, 0)) - int(before.get(key, 0))
		if delta != 0:
			changes.append("%s %s%d" % [GEAR_STATS[key], "+" if delta > 0 else "", delta])
	return "、".join(changes)


func _equipment_actions(member: Dictionary) -> void:
	var gear: Dictionary = view.get("equipment", {})
	if gear.is_empty():
		return
	var id: String = member.instance_id
	var cost := str(int(member.cost))
	var source: String = gear.location
	var worn_by_slot := {}
	for item in gear.worn.get(id, []):
		worn_by_slot[item.slot] = item
		var title: String = GEAR_SLOTS[item.slot] + " · " + item.name
		var stats := _gear_stat_change({}, item, cost)
		if not stats.is_empty():
			title += "\n" + stats
		if not item.effects.is_empty():
			title += " · " + "、".join(item.effects)
		_label(actions, title, MUTED, 16)
		var removal := _gear_stat_change(item, {}, cost)
		var detail := "将「%s」放回%s。" % [item.name, source]
		if not removal.is_empty():
			detail += "\n属性变化 · " + removal
		if not item.effects.is_empty():
			detail += "\n卸下词条 · " + "、".join(item.effects)
		_input_action("卸下" + GEAR_SLOTS[item.slot], "unequip", [id, item.slot], detail)
	for item in _available_gear(member):
		var worn: Dictionary = worn_by_slot.get(item.slot, {})
		var detail := "为%s穿戴「%s」。\n槽位 · %s" % [_name(member), item.name, GEAR_SLOTS[item.slot]]
		if not worn.is_empty():
			detail += "\n放回%s · %s" % [source, worn.name]
		var change := _gear_stat_change(worn, item, cost)
		if not change.is_empty():
			detail += "\n属性变化 · " + change
		var removed: Array = worn.get("effects", []).filter(func(effect): return effect not in item.effects)
		if not removed.is_empty():
			detail += "\n卸下词条 · " + "、".join(removed)
		if not item.effects.is_empty():
			detail += "\n穿戴词条 · " + "、".join(item.effects)
		var label := "加工中 · " if item.locked else "穿戴 · " if worn.is_empty() else "更换 · "
		_input_action(label + str(item.name), "equip", [id, item.id], detail, not item.locked)


func _skill_book_room() -> void:
	var books: Dictionary = view.get("skill_books", {})
	var market: Dictionary = view.get("book_market", {})
	if bookstore_open:
		_bookstore_actions(market)
		return
	var research: Array = view.get("book_research", [])
	if book_research_open:
		_book_research_actions(research)
		return
	_label(actions, "技能书", GOLD, 24)
	if not market.get("offers", {}).is_empty():
		_button("采购与定向", "bookstore", _toggle_bookstore)
	if not research.is_empty():
		var ready := research.any(func(task: Dictionary) -> bool: return task.claimable)
		_button("研习委托 · 有奖励可领" if ready else "研习委托", "book-research", _toggle_book_research)
	for id in books.get("stock", {}):
		_label(actions, "%s ×%d" % [books.catalog[id].name, int(books.stock[id])], INK, 16)
	if books.get("members", {}).is_empty():
		_label(actions, "可由符合能力要求的佣兵或英雄学习。", MUTED, 16)
	_book_members()


func _book_research_actions(tasks: Array) -> void:
	_label(actions, "暮汀 · 研习委托", GOLD, 24)
	_button("返回书库", "book-research", _toggle_book_research)
	_label(actions, "接取后开始记录合格胜利。每场最多计一次，安全归城才入账。", MUTED, 16)
	for task in tasks:
		_label(actions, task.name, GOLD, 18)
		if not task.selected.is_empty():
			_label(actions, "已领奖 · " + str(task.selected.name), INK, 16)
			continue
		if task.claimable:
			_label(actions, "已达成 · 自选奖励 1 本", INK, 16)
			for book in task.candidates:
				_input_action("领取 · " + str(book.name), "book", ["choice", task.id, book.id, "CONFIRM"],
					"将 1 本「%s」放入暮汀书库。每项研习可自选一次。\n%s\n%s" % [book.name, book.timing, book.summary])
			continue
		_label(actions, task.description, MUTED, 16)
		if task.accepted:
			_label(actions, "已入账 · %d/3 场" % int(task.banked), INK, 16)
		else:
			var rewards: Array = task.candidates.map(func(book: Dictionary): return book.name)
			_label(actions, "达成后从%s中选 1 本。" % "、".join(rewards), MUTED, 16)
			_input_action("接取 · " + str(task.name), "book", ["task", "accept", task.id])


func _toggle_book_research() -> void:
	book_research_open = not book_research_open
	focus_key = "book-research"
	_render()


func _bookstore_actions(market: Dictionary) -> void:
	_label(actions, "暮汀 · 技能书采购", GOLD, 24)
	var copper := int(view.town_roster.copper)
	_label(actions, "库存 %d 铜" % copper, INK, 16)
	var target: Dictionary = market.target
	if target.is_empty():
		_label(actions, "出征定向 · 未指定", MUTED, 16)
	else:
		_label(actions, "出征定向 · %s · %d/2" % [target.name, int(market.progress)], MUTED, 16)
	var book: Dictionary = market.offers.get(bookstore_book, {})
	if book.is_empty():
		_button("返回书库", "bookstore", _toggle_bookstore)
		if not target.is_empty():
			_input_action("清除定向", "book", ["target", "clear"], "清除当前目标和 %d/2 定向进度。" % int(market.progress))
		for stage in BOOK_STAGES:
			if market.offers.values().any(func(row: Dictionary) -> bool: return row.stage == stage):
				_button(BOOK_STAGES[stage], "bookstore-stage-" + stage, _bookstore_filter.bind(stage), stage != bookstore_stage)
		for row in market.offers.values():
			if row.stage == bookstore_stage:
				_button("%s · %d 铜" % [row.name, int(row.price)], "bookstore-book-" + row.id, _bookstore_select.bind(row.id))
		return
	_button("返回书目", "bookstore-list", _bookstore_select.bind(""))
	_label(actions, "「%s」 · %d 铜 · 当前库存 %d 本" % [book.name, int(book.price), int(book.stock)], GOLD, 18)
	_label(actions, book.timing + "\n" + book.summary, MUTED, 16)
	if book.buyers.is_empty():
		_label(actions, "采购需要一名适配且尚未学过此书的佣兵或英雄。", MUTED, 16)
	elif copper < int(book.price):
		_label(actions, "采购还差 %d 铜。" % (int(book.price) - copper), ALERT, 16)
	for id in book.buyers:
		var buyer: String = market.buyers[id]
		_input_action("为%s采购 · %d 铜" % [buyer, int(book.price)], "book", ["buy", id, book.id],
			"支付 %d 铜，将 1 本「%s」放入暮汀书库。采购后可在书库另行学习。" % [int(book.price), book.name], copper >= int(book.price))
	if book.stage != "X" and book.id != target.get("id"):
		var detail := "将「%s」设为技能书掉落目标。出发时锁定，安全带回其他普通书可累计进度。\n到 2/2 后，下趟首次领取普通书会替换为目标书，目标书入库后清零。" % book.name
		if not target.is_empty():
			detail += "\n更换目标会清除已有的 %d/2 进度。" % int(market.progress)
		_input_action("设为出征定向", "book", ["target", book.id], detail)


func _toggle_bookstore() -> void:
	bookstore_open = not bookstore_open
	bookstore_book = ""
	focus_key = "bookstore"
	_render()


func _bookstore_filter(stage: String) -> void:
	bookstore_stage = stage
	focus_key = "bookstore"
	_render()


func _bookstore_select(id: String) -> void:
	focus_key = "bookstore-list" if not id.is_empty() else "bookstore-book-" + bookstore_book
	bookstore_book = id
	_render()


func _field_skill_books() -> void:
	if view.get("skill_books", {}).get("members", {}).is_empty():
		return
	_button("收起技能书" if field_books_open else "调整技能书", "field-skills", _toggle_field_skills)
	if field_books_open:
		_book_members()


func _toggle_field_skills() -> void:
	_book_swap_key = ""
	field_books_open = not field_books_open
	_render()


func _book_members() -> void:
	var members: Dictionary = view.get("skill_books", {}).get("members", {})
	for id in members:
		var row: Dictionary = members[id]
		_button(row.name, "book-member-" + id, _choose_member.bind(id), id != selected_id)
		if id == selected_id:
			_skill_book_actions(id)


func _skill_book_actions(id: String) -> void:
	var library: Dictionary = view.get("skill_books", {})
	var member: Dictionary = library.get("members", {}).get(id, {})
	if member.is_empty():
		return
	var equipped: Array = member.equipped
	for i in range(2):
		var name: String = library.catalog[equipped[i]].name if i < equipped.size() else "空"
		_label(actions, "书槽 %d · %s" % [i + 1, name], MUTED, 16)
	for study in member.study:
		var book: Dictionary = library.catalog[study.id]
		var label: String = "学习 · " + book.name
		if not study.blocked.is_empty():
			label = book.name + " · " + study.blocked
		_input_action(label, "book", ["learn", id, study.id],
			"消耗 1 本「%s」供%s学习。\n%s\n%s" % [book.name, member.name, book.timing, book.summary],
			study.blocked.is_empty())
	for bid in member.learned:
		var book: Dictionary = library.catalog[bid]
		var already := equipped.has(bid)
		if not already and equipped.size() == 2:
			_book_swap_actions(id, book, equipped, library.catalog)
			continue
		var next := equipped.duplicate()
		if already:
			next.erase(bid)
		else:
			next.append(bid)
		var args := ["equip", id] + (["clear"] if next.is_empty() else next)
		_input_action(("卸下 · " if already else "装入 · ") + book.name, "book", args, "", next.size() <= 2)
		command_buttons["book " + " ".join(args)].tooltip_text = "%s\n%s" % [book.timing, book.summary]
	if not member.moves.is_empty():
		var open := tactics_member_id == id
		_button("收起自动战斗设置" if open else "自动战斗设置", "skill-tactics-" + id, _toggle_tactics.bind(id))
		if open:
			_tactics_actions(id, member)


func _book_swap_actions(id: String, book: Dictionary, equipped: Array, catalog: Dictionary) -> void:
	var key := "book-swap-%s-%s" % [id, book.id]
	if _book_swap_key != key:
		var first_slot := "book equip %s %s %s" % [id, book.id, equipped[1]]
		var choose := _button("换入 · " + str(book.name), key, _begin_book_swap.bind(key, first_slot))
		choose.tooltip_text = "%s\n%s" % [book.timing, book.summary]
		return
	actions.add_child(HSeparator.new())
	_label(actions, "换入 · " + str(book.name), GOLD, 18)
	for slot in equipped.size():
		var next := equipped.duplicate()
		next[slot] = book.id
		var replaced: String = equipped[slot]
		_input_action("替换书槽 %d · %s" % [slot + 1, catalog[replaced].name], "book", ["equip", id] + next,
			"", true, null, "book-swap-%s-%s" % [id, replaced])
	_button("取消换入", "book-swap-cancel", _cancel_book_swap)


func _begin_book_swap(key: String, first_slot: String) -> void:
	_book_swap_key = key
	focus_key = first_slot
	_render()
	_action_scroll.call_deferred("ensure_control_visible", command_buttons["book-swap-cancel"])


func _cancel_book_swap() -> void:
	focus_key = _book_swap_key
	_book_swap_key = ""
	_render()


func _toggle_tactics(id: String) -> void:
	tactics_member_id = "" if tactics_member_id == id else id
	_render()


func _tactics_actions(id: String, member: Dictionary) -> void:
	var moves: Array = member.moves
	var order := moves.map(func(move: Dictionary): return move.id)
	var main_names := {"AUTO": "自动", "BASIC": "普攻距离"}
	_label(actions, "自动施放顺序", GOLD, 17)
	for i in range(moves.size()):
		var move: Dictionary = moves[i]
		main_names[move.id] = move.name
		var row := HBoxContainer.new()
		actions.add_child(row)
		var name := _label(row, "%d  %s" % [i + 1, move.name], INK if move.enabled else MUTED, 16)
		name.size_flags_horizontal = SIZE_EXPAND_FILL
		var switch_to := "off" if move.enabled else "on"
		var switch_back := "on" if move.enabled else "off"
		if i > 0:
			var next := order.duplicate()
			next.remove_at(i)
			next.insert(i - 1, move.id)
			_input_action("上移", "book", ["queue", id] + next, "", true, row,
				"book auto %s %s %s" % [id, move.id, switch_to])
		_input_action("停用" if move.enabled else "启用", "book",
			["auto", id, move.id, switch_to], "", true, row,
			"book auto %s %s %s" % [id, move.id, switch_back])
	_label(actions, "主要接敌方式 · " + str(main_names.get(member.main, "自动")), GOLD, 17)
	for mode in ["AUTO", "BASIC"] + member.main_choices:
		var next_focus := "AUTO" if mode == "BASIC" else "BASIC"
		_input_action("接敌 · " + main_names[mode], "book", ["main", id, mode], "", member.main != mode, null,
			"book main %s %s" % [id, next_focus])


func _member_actions(cells: Array) -> void:
	if not cells.is_empty():
		_label(actions, "拖到空格上阵，拖动已上阵队员可换位", MUTED, 16)
	for member in view.get("party", []):
		var member_id: String = member["instance_id"]
		var injury_days := int(member.injury_days)
		var title := ("◆ " if member.deployed else "◇ ") + _name(member)
		if injury_days > 0:
			title += " · 旧伤 %d 日" % injury_days
		var entry := _button(title, "member-" + member_id, _choose_member.bind(member_id))
		entry.set_drag_forwarding(board.begin_deployment_drag.bind(member_id), Callable(), Callable())
		if member_id == selected_id:
			if view.get("complete", false):
				_label(actions, "Lv%d · 生命 %d/%d" % [int(member.level), int(member.hp), int(member.max_hp)], MUTED, 15)
			_equipment_actions(member)
			if view.get("phase") == "EXPLORE":
				_skill_book_actions(member_id)
			if view.get("phase") == "TOWN" and not view.get("town_roster", {}).is_empty():
				_recovery_actions(member)
				_input_action("留城 · " + _name(member), "squad", [member_id, "off"])
			_input_action("撤下部署" if member.deployed else "加入部署", "deploy",
				[member_id, "off" if member.deployed else "on"], "", member.deployed or (member.deployable and injury_days == 0))
			if view.get("complete", false):
				for stance in STANCES:
					_input_action(("当前 · " if member.stance == stance else "改为 ") + STANCES[stance], "stance", [member_id, stance], "", member.stance != stance)
			_deployment_cells(member_id, cells)


func _deployment_cells(id: String, cells: Array) -> void:
	if cells.is_empty():
		return
	var selected := cells.any(func(point): return Board.cell_index(point) == selected_cell)
	var caption := "收起阵位" if deployment_cells_open else "选择阵位"
	if selected:
		caption += " · %d,%d" % [selected_cell.x, selected_cell.y]
	_button(caption, "deployment-cells", _toggle_deployment_cells)
	if selected:
		_button("旋转朝向 · %d" % selected_facing, "facing", _rotate_facing)
		_input_action("确认阵位", "place", [id, str(selected_cell.x), str(selected_cell.y), str(selected_facing)])
	if not deployment_cells_open:
		return
	var grid := GridContainer.new()
	grid.columns = 3
	actions.add_child(grid)
	for cell in cells:
		var pos := Board.cell_index(cell)
		var slot := _button("%d,%d" % [pos.x, pos.y], "cell-%d-%d" % [pos.x, pos.y],
			_board_cell.bind(pos), true, grid)
		slot.alignment = HORIZONTAL_ALIGNMENT_CENTER
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL


func _summary() -> void:
	var summary: Variant = view.get("settlement")
	if summary is Dictionary:
		var result: String = summary.get("result", "归城")
		_label(actions, REASONS.get(result, result) + " · %d 场战斗" % int(summary.get("battles", 0)), INK, 19)
		for pair in [["入库", "banked"], ["入库材料", "materials"], ["入库技能书", "banked_book_names"]]:
			var text := _cargo_amounts(summary.get(pair[1], {}))
			if not text.is_empty():
				_label(actions, pair[0] + "  " + text, MUTED, 16)
		var progress: Dictionary = summary.get("book_target_progress", {})
		if not progress.is_empty():
			_label(actions, "定向「%s」 · %d/2 → %d/2" % [progress.name, int(progress.before), int(progress.after)], INK, 16)
			if progress.target_banked:
				_label(actions, "目标书已入库，定向进度清零。", MUTED, 16)
			elif progress.target_lost:
				_label(actions, "目标书未带回，定向进度保留。", MUTED, 16)
			elif int(progress.after) == 2 and int(progress.before) < 2:
				_label(actions, "下趟首次领取普通书将替换为目标书。", MUTED, 16)
		for task in summary.get("book_research_settlement", []):
			var detail := "本趟入账 %d 场" % int(task.count) if task.banked else "本趟 %d 场未入账" % int(task.count)
			_label(actions, "%s · %s" % [task.name, detail], INK if task.banked else ALERT, 16)
			if task.reward_ready:
				_label(actions, "可在暮汀「技能书 → 研习委托」领取奖励。", MUTED, 16)
		for gear in summary.get("returned_gear_names", []):
			_label(actions, "带回装备  %s · 尚未穿戴" % gear, MUTED, 16)
		var consumables: Array = summary.get("returned_consumable_names", [])
		if not consumables.is_empty():
			_label(actions, "带回携行道具  " + "、".join(consumables), MUTED, 16)
		var lost: Dictionary = summary.get("lost_cargo", {})
		for pair in [["损失物资", lost.get("pending", {})], ["损失材料", lost.get("materials", {})],
				["损失技能书", summary.get("lost_book_names", {})]]:
			var text := _cargo_amounts(pair[1])
			if not text.is_empty():
				_label(actions, pair[0] + "  " + text, ALERT, 16)
		for pair in [["损失行囊装备", "lost_gear_names"], ["损失携行道具", "lost_consumable_names"]]:
			var names: Array = summary.get(pair[1], [])
			if not names.is_empty():
				_label(actions, pair[0] + "  " + "、".join(names), ALERT, 16)
		if int(lost.get("medical", 0)) > 0:
			_label(actions, "损失随队救护 ×%d" % int(lost.medical), ALERT, 16)
		for member in view.get("party", []):
			if int(member.get("injury_days", 0)) > 0:
				_label(actions, "%s  休整 %d 日" % [_name(member), int(member["injury_days"])], MUTED, 16)
		for key in ["missing_ids", "captured_ids", "rescued_ids"]:
			var ids: Array = summary.get(key, [])
			if ids.is_empty():
				continue
			var label: String = {"missing_ids": "失联", "captured_ids": "被俘", "rescued_ids": "已救回"}[key]
			var names := ids.map(func(id): return summary.get("member_labels", {}).get(id, "队员"))
			_label(actions, "%s  %s" % [label, "、".join(names)], INK if key == "rescued_ids" else ALERT, 16)
		var expired: Array = summary.get("expired_rescue_names", [])
		if not expired.is_empty():
			_label(actions, "本次结算救援超期 · " + "、".join(expired), ALERT, 16)
		if summary.has("capture_batch"):
			_label(actions, "最迟第 %d 日救回 · 回城后前往搜救所" % int(summary.capture_batch.deadline), MUTED, 16)
		if summary.has("rescued_injury_days"):
			_label(actions, "救回人员留城休养 %d 日" % int(summary.rescued_injury_days), MUTED, 16)
	if not view.get("complete", false) and view.get("tutorial_return", false):
		var missing := _scouting_missing(view.get("scouting", {}))
		var detail := "本趟还缺%s。" % missing if not missing.is_empty() else "交付须具备本趟的安全归城记录。"
		_label(actions, "调查尚未交付。" + detail, MUTED, 16)


func _cargo_amounts(rows: Dictionary) -> String:
	var items: PackedStringArray = []
	for id in rows:
		var count := int(rows[id])
		if count != 0:
			items.append("%s ×%d" % [CARGO_NAMES.get(id, id), count])
	return "  /  ".join(items)


func _choose_member(id: String) -> void:
	_book_swap_key = ""
	selected_id = id
	selected_cell = Vector2i(-999, -999)
	deployment_cells_open = false
	for member in view.get("party", []):
		if member["instance_id"] == id:
			selected_facing = int(member["facing"])
			break
	_render()


func _rotate_facing() -> void:
	selected_facing = (selected_facing + 1) % 6
	_render()


func _toggle_deployment_cells() -> void:
	deployment_cells_open = not deployment_cells_open
	focus_key = "deployment-cells"
	_render()


func _board_cell(cell: Vector2i) -> void:
	if selected_id.is_empty() or not _can_edit_deployment():
		return
	selected_cell = cell
	deployment_cells_open = false
	focus_key = "facing"
	_render()


func _route_site(site: String) -> void:
	var action: String = view.get("route", {}).get("map_actions", {}).get(site, "")
	if not action.is_empty():
		_activate_board_action(action + " " + site)


func _activate_board_action(key: String) -> void:
	if client.busy or client.blocked or settings_open or captions_open or not confirmation.is_empty():
		return
	var entry: Variant = command_buttons.get(key)
	if entry is Button and not entry.disabled:
		focus_key = key
		entry.pressed.emit()


func _can_edit_deployment() -> bool:
	return _show_deployment() and not field_items_open and not client.busy and not client.blocked and not settings_open and confirmation.is_empty()


func _show_deployment() -> bool:
	if not opened or captions_open:
		return false
	if view.get("phase") == "TOWN":
		return view.get("commissioned", false) and town_tab not in ["skills", "construction", "logistics", "items"] \
			and (not view.get("complete", false) or town_tab == "roster") \
			and view.get("hunt", {}).get("memory", {}).is_empty()
	return view.get("phase") == "EXPLORE" and view.get("route", {}).get("contact_pending", false)


func _deployment_target(id: String, cell: Vector2i) -> Dictionary:
	if not _can_edit_deployment():
		return {"error": "当前不能部署"}
	var slots: Array = view.get("town_deploy_cells", []) if view.get("phase") == "TOWN" else model.get("map", {}).get("deploy_cells", [])
	if not slots.any(func(point): return Board.cell_index(point) == cell):
		return {"error": "请放在己方部署格"}
	var spent := 0
	var member: Dictionary = {}
	var occupants: Array = []
	for row in view.get("party", []):
		if row.instance_id == id:
			member = row
		elif row.deployed and Board.cell_index(row.position) == cell:
			occupants.append(row)
		if row.deployed:
			spent += int(row.cost)
	if member.is_empty() or not member.deployable or int(member.injury_days) > 0:
		return {"error": "队员当前无法上阵"}
	if not occupants.is_empty():
		if not member.deployed:
			return {"error": "预备队员需放在空格"}
		var origin := Board.cell_index(member.position)
		if occupants.size() != 1 or origin == cell or not slots.any(func(point): return Board.cell_index(point) == origin):
			return {"error": "原阵位无法交换"}
		for row in view.get("party", []):
			if row.instance_id != id and row.deployed and Board.cell_index(row.position) == origin:
				return {"error": "原阵位已有重叠队员"}
		var other: Dictionary = occupants[0]
		if not other.deployable or int(other.injury_days) > 0:
			return {"error": "对方当前无法上阵"}
		return {"swap": other.instance_id, "hint": "交换 " + _name(other)}
	if not member.deployed and spent + int(member.cost) > int(view.budget.battle):
		return {"error": "超过战斗 Cost"}
	if member.deployed and Board.cell_index(member.position) == cell \
			and (selected_id != id or selected_facing == int(member.facing)):
		return {"unchanged": true, "hint": "原阵位"}
	return {}


func _deploy_drop(id: String, cell: Vector2i) -> void:
	var destination := _deployment_target(id, cell)
	if destination.has("error"):
		_notice(destination.error)
		return
	if destination.get("unchanged", false):
		return
	for member in view.party:
		if member.instance_id == id:
			selected_facing = selected_facing if selected_id == id else int(member.facing)
			selected_id = id
			selected_cell = cell
			deployment_cells_open = false
			focus_key = "member-" + id
			var args := [id, str(cell.x), str(cell.y), str(selected_facing)]
			if destination.has("swap"):
				args.append(destination.swap)
			client.submit("deploy_at", args)
			return


func _deploy_to_reserve(id: String) -> void:
	if not _can_edit_deployment():
		return
	for member in view.party:
		if member.instance_id == id and member.deployed:
			selected_id = id
			selected_facing = int(member.facing)
			selected_cell = Vector2i(-999, -999)
			deployment_cells_open = false
			focus_key = "member-" + id
			client.submit("deploy", [id, "off"])
			return


func _confirm() -> void:
	var action := confirmation
	confirmation = {}
	focus_key = action["back"]
	client.submit(action["command"], action["args"])


func _cancel_confirmation() -> void:
	focus_key = confirmation.get("back", "")
	confirmation = {}
	_render()


func _open_town(ask_about_old_company: bool = false) -> void:
	opened = true
	if captions_open:
		focus_key = "opening-replay"
	elif not view.get("commissioned", false):
		_asked_about_old_company = ask_about_old_company
		focus_key = "quest commission CONFIRM"
	captions_open = false
	_render()


func _replay_opening() -> void:
	caption_index = 0
	captions_open = true
	focus_key = "subtitle-next"
	_render()


func _show_settings() -> void:
	settings_open = true
	focus_key = "volume"
	_render()


func _close_settings() -> void:
	settings_open = false
	focus_key = "cancel" if not confirmation.is_empty() else "settings"
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
	for voice in ado_sounds.values():
		voice.volume_db = audio.volume_db + 2.0
		if volume == 0 or settings["静音"] or not settings["音效"]:
			voice.stop()
	if volume == 0 or settings["静音"] or not settings["音效"]:
		audio.stop()


func _save_settings() -> void:
	var file := ConfigFile.new()
	for entry in settings.keys():
		file.set_value("presentation", entry, settings[entry])
	file.set_value("presentation", "volume", volume)
	file.set_value("presentation", "battle_pace", _battle_pace)
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
		var stored_pace: Variant = file.get_value("presentation", "battle_pace", 1)
		if stored_pace is int and stored_pace >= 0 and stored_pace < BATTLE_PACES.size():
			_battle_pace = stored_pace


func _input(event: InputEvent) -> void:
	if _archive_page != null and _archive_page.visible and event is InputEventKey and event.pressed \
			and event.keycode in [KEY_PAGEUP, KEY_PAGEDOWN]:
		var direction := -1 if event.keycode == KEY_PAGEUP else 1
		_archive_page.scroll.scroll_vertical += direction * int(_archive_page.scroll.size.y * 0.85)
		get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and event.keycode == KEY_SPACE and _can_toggle_playback():
		if not event.is_echo():
			_toggle_playback()
		get_viewport().set_input_as_handled()
		return
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
	elif not _book_swap_key.is_empty() and command_buttons.has("book-swap-cancel"):
		_cancel_book_swap()
	elif books_open and not captions_open and not client.blocked:
		_toggle_books()
	elif _overlook_mat.visible:
		_toggle_overlook()
	elif chapter_history_open and not captions_open and not client.blocked:
		_toggle_chapter_history()
	else:
		return
	get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_quit()


func _quit() -> void:
	if _closing:
		return
	var cancelled_snapshot := false
	if client != null and client.busy:
		cancelled_snapshot = client.cancel_snapshot_for_close()
		if not cancelled_snapshot:
			_close_after_save = true
			notice.text = "等待正在提交的操作完成后再退出。"
			notice.show()
			return
	_closing = true
	if _battle_timer != null:
		_battle_timer.stop()
	var models := Vector2i.ZERO
	if board != null and board.stage != null:
		models = board.stage.stop_background_loading()
	if client != null:
		var has_pending: bool = not client.pending.is_empty()
		var reason := "window_closed"
		if cancelled_snapshot:
			reason = "snapshot_cancelled"
		elif has_pending:
			reason = "pending_preserved"
		elif _close_after_save:
			reason = "after_receipt"
		print("P06 exit version=%d queued=%s pending=%s reason=%s active_models=%d queued_models=%d" % [
			int(client.frame.get("state_version", -1)), _close_after_save, has_pending, reason, models.x, models.y])
	get_tree().quit()

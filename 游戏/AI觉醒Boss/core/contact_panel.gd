extends PanelContainer
## 041 standalone contact-demo control panel. Emits requests only; owns no battle state.

signal pause_requested
signal step_requested
signal speed_requested
signal sound_requested
signal replay_requested
signal focus_requested
signal comparison_requested
signal quit_requested

const THEME=preload("res://core/interface_theme.gd")
const NOTE="真实规则独立预置，不读取战役进度；F11全屏，滚轮缩放"

var status: Label
var pause_button: Button
var speed_button: Button
var sound_button: Button
var focus_button: Button
var comparison_button: Button

func _ready() -> void:
	theme = THEME.create()
	_compact_panel_style()
	set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	offset_left = 20
	offset_right = -20
	offset_top = 14

	var stack = VBoxContainer.new()
	stack.add_theme_constant_override("separation", 2)
	add_child(stack)

	var title = Label.new()
	title.text = "林道攻防 · 出手与命中"
	title.add_theme_font_size_override("font_size", 18)
	title.tooltip_text = NOTE
	stack.add_child(title)

	var first_row = HBoxContainer.new()
	first_row.add_theme_constant_override("separation", 6)
	stack.add_child(first_row)
	pause_button = _add_button(first_row, "暂停", pause_requested)
	_add_button(first_row, "单步", step_requested)
	speed_button = _add_button(first_row, "1倍", speed_requested)
	sound_button = _add_button(first_row, "声音：开", sound_requested)

	var second_row = HBoxContainer.new()
	second_row.add_theme_constant_override("separation", 6)
	stack.add_child(second_row)
	_add_button(second_row, "重播", replay_requested)
	focus_button = _add_button(second_row, "近看对战 / 全场", focus_requested)
	comparison_button = _add_button(second_row, "接触表现040基线", comparison_requested)
	_add_button(second_row, "退出", quit_requested)

	status = Label.new()
	status.autowrap_mode = TextServer.AUTOWRAP_OFF
	status.clip_text = true
	status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	status.custom_minimum_size = Vector2(0, 22)
	status.add_theme_font_size_override("font_size", 16)
	status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status.tooltip_text = NOTE
	stack.add_child(status)

func _compact_panel_style() -> void:
	var panel_style: StyleBox = get_theme_stylebox("panel").duplicate()
	panel_style.content_margin_top = 3
	panel_style.content_margin_bottom = 3
	add_theme_stylebox_override("panel", panel_style)

func _add_button(parent: Node, text: String, target: Signal) -> Button:
	var button = Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(0, 30)
	button.clip_text = true
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.size_flags_stretch_ratio = 1.0
	button.pressed.connect(func() -> void: target.emit())
	parent.add_child(button)
	for state in ["normal", "hover", "pressed", "disabled", "focus"]:
		var style: StyleBox = get_theme_stylebox(state, "Button").duplicate()
		style.content_margin_top = 2
		style.content_margin_bottom = 2
		button.add_theme_stylebox_override(state, style)
	return button

func update_controls(paused: bool, speed: float, sound_on: bool, contact_on: bool, focus_label: String) -> void:
	if pause_button == null:
		return
	pause_button.text = "继续" if paused else "暂停"
	if is_equal_approx(speed, roundf(speed)):
		speed_button.text = "%d倍" % int(roundf(speed))
	else:
		speed_button.text = "%.1f倍" % speed
	sound_button.text = "声音：开" if sound_on else "声音：关"
	focus_button.text = focus_label if not focus_label.is_empty() else "近看对战 / 全场"
	comparison_button.text = "接触表现042" if contact_on else "接触表现040基线"

func set_status(value: String) -> void:
	if status != null:
		status.text = value
		status.tooltip_text = value if not value.is_empty() else NOTE

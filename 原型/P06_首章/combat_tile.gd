extends Button

const PAPER := Color("f8ead3")
const SUBTLE := Color("cdb99c")
const FRIEND := Color("94c3ac")
const HOSTILE := Color("e7a17b")

var _portrait: TextureRect
var _badge: Label
var _unit_name: Label
var _health: Label
var _shield: Label
var _meter: ProgressBar
var _meter_fill: StyleBoxFlat
var _large_text := false


func setup(art: Texture2D) -> void:
	theme_type_variation = &"CombatLeader" if art != null else &"CombatTile"
	size_flags_horizontal = SIZE_EXPAND_FILL
	toggle_mode = true
	if art != null:
		_portrait = TextureRect.new()
		_portrait.texture = art
		_portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		_portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		_portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_portrait)
		_portrait.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
		_portrait.offset_left = 3
		_portrait.offset_right = -3
		_portrait.offset_top = 3
		_portrait.offset_bottom = -3
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 2)
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(content)
	content.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	content.offset_left = 9
	content.offset_right = -9
	content.offset_top = 6
	content.offset_bottom = -6
	var title: Container = content if art != null else HBoxContainer.new()
	if title != content:
		title.mouse_filter = Control.MOUSE_FILTER_IGNORE
		content.add_child(title)
	_badge = _label(title, SUBTLE)
	_unit_name = _label(title, PAPER)
	_unit_name.size_flags_horizontal = SIZE_EXPAND_FILL
	_unit_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var vitals := HBoxContainer.new()
	vitals.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(vitals)
	_health = _label(vitals, PAPER)
	_shield = _label(vitals, Color("efd08c"))
	_shield.size_flags_horizontal = SIZE_EXPAND_FILL
	_shield.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT if art == null else HORIZONTAL_ALIGNMENT_LEFT
	_meter = ProgressBar.new()
	_meter.min_value = 0
	_meter.max_value = 1
	_meter.step = 0
	_meter.show_percentage = false
	_meter.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_meter.custom_minimum_size.y = 4.0 if art == null else 7.0
	_meter_fill = StyleBoxFlat.new()
	var track := StyleBoxFlat.new()
	track.bg_color = Color("100e0c")
	_meter.add_theme_stylebox_override("background", track)
	_meter.add_theme_stylebox_override("fill", _meter_fill)
	content.add_child(_meter)
	_set_sizes(false)


func update_actor(actor: Dictionary, summary: String, large_text: bool) -> void:
	tooltip_text = summary
	accessibility_name = summary
	if _large_text != large_text:
		_set_sizes(large_text)
	var hp := int(actor.hp)
	var enemy: bool = actor.side == "enemy"
	var ink := HOSTILE if enemy else FRIEND
	_badge.text = str(actor.badge)
	if _portrait != null:
		_badge.text += "  ·  第 %d 阶段" % int(actor.get("boss_phase", 1))
	if _badge.get_theme_color("font_color") != ink:
		_badge.add_theme_color_override("font_color", ink)
	_unit_name.text = actor.display_name
	_unit_name.modulate.a = 0.56 if hp <= 0 else 1.0
	_health.text = "倒地" if hp <= 0 else "%d / %d" % [hp, int(actor.max_hp)]
	_health.modulate.a = 0.61 if hp <= 0 else 1.0
	var shield := int(actor.get("private_shield", 0))
	_shield.text = "盾 %d" % shield if shield > 0 else ("共享盾" if actor.has("shared_protection") else "")
	_meter.value = clampf(float(hp) / maxf(1.0, float(actor.max_hp)), 0.0, 1.0)
	if _meter_fill.bg_color != ink:
		_meter_fill.bg_color = ink


func _label(parent: Container, color: Color) -> Label:
	var label := Label.new()
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label


func _set_sizes(large: bool) -> void:
	_large_text = large
	var leader := _portrait != null
	custom_minimum_size.y = (122.0 if large else 109.0) if leader else (70.0 if large else 62.0)
	_badge.add_theme_font_size_override("font_size", 17 if large else 13)
	_unit_name.add_theme_font_size_override("font_size", (27 if large else 23) if leader else (21 if large else 17))
	_health.add_theme_font_size_override("font_size", 19 if large else 15)
	_shield.add_theme_font_size_override("font_size", 16 if large else 13)

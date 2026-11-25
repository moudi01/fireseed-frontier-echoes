extends VBoxContainer

const INK := Color("e9dbc0")
const MUTED := Color("c2ae91")
const GOLD := Color("e7bd75")
const WOUNDED := Color("f7ac8e")

var choices: VBoxContainer


func present(memory: Dictionary, actors: Array, portrait: Texture2D) -> void:
	add_theme_constant_override("separation", 10)
	_label(self, "%s的记忆" % memory.general, GOLD, 24)
	_label(self, "战斗暂停 · 第 %d / 2 段" % int(memory.number), MUTED, 16)
	var boss: Dictionary = {}
	var allies: Array[Dictionary] = []
	for actor: Dictionary in actors:
		if actor.side == "player":
			allies.append(actor)
		elif actor.kind == "MG01":
			boss = actor
	if not boss.is_empty():
		_boss_status(boss, portrait)
	_squad_status(allies)

	var story := _section("Story", "30271e", "6b533b")
	if memory.enabled:
		_label(story, memory.lead.speaker, GOLD, 16)
		_label(story, memory.lead.text, INK, 19)
	else:
		_label(story, "保留记忆尚未解锁", GOLD, 17)
		_label(story, "第 1 段尚未提交。战斗胜利后可在暮汀补做。", INK, 16)

	choices = VBoxContainer.new()
	choices.name = &"Choices"
	choices.add_theme_constant_override("separation", 6)
	add_child(choices)


func _boss_status(boss: Dictionary, portrait: Texture2D) -> void:
	var status := _section("BossStatus", "38271f", "895941")
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	status.add_child(row)
	var image := TextureRect.new()
	# The HUD banner leaves the left side empty for text and places Ado at the right.
	var crop := AtlasTexture.new()
	crop.atlas = portrait
	var edge := mini(portrait.get_width(), portrait.get_height())
	crop.region = Rect2(portrait.get_width() - edge, 0, edge, edge)
	crop.filter_clip = true
	image.texture = crop
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.custom_minimum_size = Vector2(72, 72)
	image.size_flags_vertical = SIZE_SHRINK_CENTER
	image.mouse_filter = MOUSE_FILTER_IGNORE
	row.add_child(image)

	var details := VBoxContainer.new()
	details.size_flags_horizontal = SIZE_EXPAND_FILL
	details.size_flags_vertical = SIZE_SHRINK_CENTER
	details.add_theme_constant_override("separation", 3)
	row.add_child(details)
	var hp := int(boss.hp)
	var max_hp := int(boss.max_hp)
	_label(details, "生命  %d / %d" % [hp, max_hp], INK, 17)
	var health := ProgressBar.new()
	health.max_value = max_hp
	health.value = hp
	health.show_percentage = false
	health.mouse_filter = MOUSE_FILTER_IGNORE
	health.custom_minimum_size.y = 5
	health.add_theme_stylebox_override("background", _style("211b16", "211b16", 0))
	health.add_theme_stylebox_override("fill", _style("b57c58", "b57c58", 0))
	details.add_child(health)
	_label(details, "护盾  %d" % int(boss.get("private_shield", 0)), MUTED, 16)


func _squad_status(allies: Array[Dictionary]) -> void:
	var status := _section("SquadStatus", "27251f", "55493b")
	var standing := 0
	var wounded: Array[Dictionary] = []
	for actor: Dictionary in allies:
		if int(actor.hp) > 0:
			standing += 1
			if int(actor.hp) < int(actor.max_hp):
				wounded.append(actor)
	_label(status, "队伍存活  %d / %d" % [standing, allies.size()], INK, 17)
	wounded.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a.hp) * int(b.max_hp) < int(b.hp) * int(a.max_hp))
	for index in mini(2, wounded.size()):
		var actor := wounded[index]
		var tint := WOUNDED if int(actor.hp) * 2 <= int(actor.max_hp) else MUTED
		_label(status, "%s  %s  %d / %d" % [actor.badge, actor.display_name, int(actor.hp), int(actor.max_hp)], tint, 15)
	if wounded.is_empty() and standing > 0:
		_label(status, "存活队员生命全满", MUTED, 15)


func _section(section_name: String, fill: String, edge: String) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.name = section_name
	panel.add_theme_stylebox_override("panel", _style(fill, edge, 10))
	add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 4)
	panel.add_child(column)
	return column


func _label(parent: Container, words: String, tint: Color, pixels: int) -> void:
	var label := Label.new()
	label.text = words
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.theme_type_variation = "PanelText%d" % pixels
	label.add_theme_color_override("font_color", tint)
	parent.add_child(label)


func _style(fill: String, edge: String, padding: float) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(fill)
	style.border_color = Color(edge)
	style.set_border_width_all(1 if padding > 0 else 0)
	style.set_corner_radius_all(4)
	for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		style.set_content_margin(side, padding)
	return style

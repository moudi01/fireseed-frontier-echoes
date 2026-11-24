extends TextureRect

const PAPER := "res://assets/town/archive_folio.webp"
const INK := Color("322719")

var current_key := ""
var scroll := ScrollContainer.new()
var date_line := Label.new()
var heading := Label.new()
var body := Label.new()
var reader_section := VBoxContainer.new()
var reader_heading := Label.new()
var reader_names := RichTextLabel.new()


func _ready() -> void:
	hide()
	expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(scroll)
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 13)
	scroll.add_child(column)
	column.add_child(date_line)
	column.add_child(heading)
	var rule := ColorRect.new()
	rule.color = Color("826242")
	rule.custom_minimum_size.y = 1.0
	column.add_child(rule)
	column.add_child(body)
	column.add_child(reader_section)
	reader_section.hide()
	reader_section.add_theme_constant_override("separation", 5)
	reader_section.add_child(reader_heading)
	reader_heading.text = "当前可学习"
	reader_heading.add_theme_color_override("font_color", INK)
	reader_section.add_child(reader_names)
	reader_names.fit_content = true
	reader_names.scroll_active = false
	reader_names.mouse_filter = Control.MOUSE_FILTER_IGNORE
	reader_names.add_theme_color_override("default_color", INK)
	reader_names.add_theme_constant_override("line_separation", 4)
	for label: Label in [date_line, heading, body]:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.add_theme_color_override("font_color", INK)
	body.add_theme_constant_override("line_spacing", 6)
	resized.connect(_inset)
	_inset()


func _inset() -> void:
	var inset := clampf(size.x * 0.072, 24, 68)
	scroll.offset_left = inset
	scroll.offset_right = -inset
	scroll.offset_top = clampf(size.y * 0.065, 22, 46)
	scroll.offset_bottom = -scroll.offset_top


func show_record(record: Dictionary, large: bool) -> void:
	show_document(record.id, "第 %d 日" % int(record.day), record.title, record.text, large)


func show_document(key: String, context: String, title: String, content: String, large: bool) -> void:
	if texture == null:
		texture = load(PAPER) as Texture2D
	show()
	reader_section.hide()
	date_line.text = context
	heading.text = title
	body.text = content
	date_line.add_theme_font_size_override("font_size", 23 if large else 18)
	heading.add_theme_font_size_override("font_size", 36 if large else 30)
	body.add_theme_font_size_override("font_size", 27 if large else 22)
	if current_key != key:
		scroll.scroll_vertical = 0
	current_key = key


func show_readers(learners: Array, known: Array, large: bool) -> void:
	reader_heading.add_theme_font_size_override("font_size", 29 if large else 24)
	reader_names.add_theme_font_size_override("normal_font_size", 26 if large else 21)
	reader_names.clear()
	if learners.is_empty():
		reader_names.add_text("当前无人可学习，可先存入书库。")
	for reader: Dictionary in learners:
		_append_reader(reader, reader.location)
	for reader: Dictionary in known:
		_append_reader(reader, "已学会 · " + str(reader.location))
	reader_section.show()


func _append_reader(reader: Dictionary, role: String) -> void:
	if reader_names.get_total_character_count() > 0:
		reader_names.add_text("\n")
	reader_names.push_color(Color("654c31"))
	reader_names.add_text(role + "　")
	reader_names.pop()
	reader_names.add_text(reader.name)


func dismiss() -> void:
	if visible:
		hide()
		texture = null
		current_key = ""

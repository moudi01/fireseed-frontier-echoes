extends VBoxContainer

const INK := Color("e9dbc0")
const GOLD := Color("e7bd75")

var divider := Color("534437")
var _empty: Label
var _rows: Array[Dictionary] = []
var _entries: Array[Dictionary] = []
var _font_px := 0


func _ready() -> void:
	add_theme_constant_override("separation", 3)
	_empty = _make_label(self, INK)
	_empty.text = "暂时没有交战记录"


func update_entries(entries: Array[Dictionary], font_px: int) -> void:
	if entries == _entries and font_px == _font_px:
		return
	_entries = entries
	_font_px = font_px
	_empty.visible = entries.is_empty()
	_empty.add_theme_font_size_override("font_size", font_px)
	var tick_width := 0.0
	for index in entries.size():
		if index == _rows.size():
			_add_row()
		var row := _rows[index]
		var tick: Label = row.beat
		var detail: Label = row.detail
		tick.add_theme_font_size_override("font_size", font_px)
		detail.add_theme_font_size_override("font_size", font_px)
		tick.text = "第 %d 拍" % entries[index].tick
		detail.text = entries[index].detail
		tick_width = maxf(tick_width, tick.get_minimum_size().x)
	for index in _rows.size():
		var row := _rows[index]
		row.container.visible = index < entries.size()
		row.beat.custom_minimum_size.x = tick_width


func _add_row() -> void:
	var row := VBoxContainer.new()
	row.add_theme_constant_override("separation", 3)
	add_child(row)
	var line := ColorRect.new()
	line.color = divider
	line.custom_minimum_size.y = 1.0
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(line)
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 10)
	row.add_child(columns)
	var tick := _make_label(columns, GOLD)
	tick.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var detail := _make_label(columns, INK)
	detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows.append({"container": row, "beat": tick, "detail": detail})


func _make_label(parent: Control, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label

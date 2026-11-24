extends Control

signal clue_selected(clue: String)

const ART := "res://assets/town/search_chart_ink.png"
const KEYS := ["tracks", "marker"]
const NAMES := ["最后出现地点", "转运支路"]
const ANCHORS := [Vector2(0.24, 0.43), Vector2(0.72, 0.57)]
const PAPER := Color("e9dbc0")
const GOLD := Color("e7bd75")
const DIM := Color("99aba4")
const INK := Color("1b2521")

var progress := 0
var font_px := 19
var _paper: Texture2D
var _inspect := Button.new()


func _ready() -> void:
	mouse_filter = MOUSE_FILTER_IGNORE
	_inspect.flat = true
	_inspect.self_modulate.a = 0
	_inspect.focus_mode = FOCUS_NONE
	_inspect.mouse_default_cursor_shape = CURSOR_POINTING_HAND
	_inspect.pressed.connect(func(): clue_selected.emit(KEYS[progress]))
	_inspect.mouse_entered.connect(queue_redraw)
	_inspect.mouse_exited.connect(queue_redraw)
	add_child(_inspect)
	resized.connect(_layout_target)
	hide()


func present(rescue: Dictionary, large: bool, enabled: bool) -> void:
	var active: Dictionary = rescue.get("active", {})
	visible = not active.is_empty()
	if not visible:
		_paper = null
		_inspect.hide()
		return
	if _paper == null:
		_paper = load(ART)
	progress = 0
	for batch: Dictionary in rescue.get("batches", []):
		if batch.id == active.id:
			progress = 2 if "marker" in batch.steps else 1 if "tracks" in batch.steps else 0
			break
	font_px = 23 if large else 19
	_inspect.visible = enabled and progress < KEYS.size()
	if _inspect.visible:
		_inspect.tooltip_text = "核对行进痕迹" if progress == 0 else "沿交接标记查找转运点"
		_inspect.accessibility_name = _inspect.tooltip_text
	_layout_target()
	queue_redraw()


func _label_box(index: int) -> Rect2:
	var font := get_theme_default_font()
	var measure := font.get_string_size(NAMES[index], HORIZONTAL_ALIGNMENT_LEFT, -1, font_px)
	var box_size := Vector2(ceilf(measure.x) + 14.0, ceilf(measure.y) + 4.0)
	var center := size * Vector2(ANCHORS[index])
	var top := center.y - 20.0 - box_size.y if index == 0 else center.y + 20.0
	return Rect2(Vector2(center.x - box_size.x * 0.5, top), box_size)


func _layout_target() -> void:
	if not is_node_ready() or not _inspect.visible or progress >= KEYS.size():
		return
	var pin := size * Vector2(ANCHORS[progress])
	var box := _label_box(progress).merge(Rect2(pin - Vector2(20, 20), Vector2(40, 40)))
	_inspect.position = box.position
	_inspect.size = box.size


func _draw() -> void:
	if _paper == null:
		return
	draw_texture_rect(_paper, Rect2(Vector2(4, 4), size - Vector2(8, 8)), false)
	var start := size * Vector2(ANCHORS[0])
	var end := size * Vector2(ANCHORS[1])
	var edge := (end - start).normalized() * 17.0
	draw_dashed_line(start + edge, end - edge, GOLD if progress > 0 else DIM, 2, 8, true)
	var font := get_theme_default_font()
	for index in KEYS.size():
		var at := size * Vector2(ANCHORS[index])
		var current := index == progress
		var color := Color("ffe4a6") if current and _inspect.is_hovered() else GOLD
		if index < progress:
			draw_circle(at, 16, GOLD, true, -1, true)
			draw_polyline(PackedVector2Array([at + Vector2(-8, 0), at + Vector2(-2, 6), at + Vector2(8, -6)]), INK, 3.5, true)
		else:
			draw_circle(at, 16, INK, true, -1, true)
			draw_circle(at, 16, color if current else DIM, false, 2.5, true)
			if current:
				draw_circle(at, 4.5, color, true, -1, true)
		var box := _label_box(index)
		if current:
			draw_rect(box, INK)
		var baseline := (box.size.y + font.get_ascent(font_px) - font.get_descent(font_px)) * 0.5
		draw_string(font, box.position + Vector2(0, baseline), NAMES[index], HORIZONTAL_ALIGNMENT_CENTER,
			box.size.x, font_px, PAPER if index <= progress else DIM)

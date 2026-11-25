extends Control

signal clue_selected(clue: String)

const ART := "res://assets/town/search_chart_ink.png"
const KEYS := ["tracks", "marker"]
const NAMES := ["最后出现地点", "转运支路"]
const ANCHORS := [Vector2(0.24, 0.43), Vector2(0.72, 0.57)]

# P04B warm frontier storybook palette
const PAPER := Color("f5ebd6")
const PARCHMENT_CARD := Color(0.95, 0.89, 0.77, 0.92)
const PARCHMENT_MUTED := Color(0.90, 0.83, 0.69, 0.82)
const INK := Color("241a12")
const INK_DARK := Color(0.16, 0.12, 0.08, 0.94)
const SEPIA := Color("5e452d")
const SEPIA_SOFT := Color(0.45, 0.34, 0.23, 0.62)
const GOLD := Color("e2b15b")
const GOLD_BRIGHT := Color("ffe4a6")
const FOCUS_RING := Color("fff4d6")
const LANDMARK_RED := Color("b65338")
const DONE_SAGE := Color("466146")
const WETLAND_WASH := Color(0.42, 0.55, 0.52, 0.16)

var progress := 0
var font_px := 19
var _large := false
var _paper: Texture2D
var _inspect := Button.new()

var _case_id := ""
var _origin_region := ""
var _origin_site_name := ""
var _missing_label := ""
var _returns_on := 0
var _deadline := 0
var _pulse_time := 0.0


func _ready() -> void:
	mouse_filter = MOUSE_FILTER_IGNORE
	_inspect.flat = true
	_inspect.self_modulate.a = 0.0
	_inspect.focus_mode = Control.FOCUS_NONE
	_inspect.mouse_default_cursor_shape = CURSOR_POINTING_HAND
	_inspect.pressed.connect(_on_inspect_pressed)
	_inspect.mouse_entered.connect(queue_redraw)
	_inspect.mouse_exited.connect(queue_redraw)
	_inspect.focus_entered.connect(queue_redraw)
	_inspect.focus_exited.connect(queue_redraw)
	_inspect.button_down.connect(queue_redraw)
	_inspect.button_up.connect(queue_redraw)
	add_child(_inspect)
	resized.connect(_layout_target)
	set_process(false)
	hide()


func _on_inspect_pressed() -> void:
	if progress < KEYS.size():
		clue_selected.emit(KEYS[progress])


func _is_low_motion() -> bool:
	var parent := get_parent()
	if parent != null and "_motion_reduced" in parent:
		return bool(parent._motion_reduced)
	return false


func _process(delta: float) -> void:
	if not visible or not _inspect.visible or _is_low_motion():
		set_process(false)
		return
	_pulse_time = fmod(_pulse_time + delta, TAU * 4.0)
	queue_redraw()


func present(rescue: Dictionary, large: bool, enabled: bool) -> void:
	var active: Dictionary = rescue.get("active", {})
	visible = not active.is_empty()
	if not visible:
		_paper = null
		_inspect.hide()
		_inspect.focus_mode = Control.FOCUS_NONE
		set_process(false)
		return
	if _paper == null:
		_paper = load(ART)
	_case_id = str(active.get("id", ""))
	_origin_region = str(active.get("origin_region", ""))
	_origin_site_name = ""
	_missing_label = ""
	_returns_on = int(active.get("returns_on", 0))
	_deadline = 0
	progress = 0
	for batch: Dictionary in rescue.get("batches", []):
		if str(batch.get("id", "")) == _case_id:
			var steps: Array = batch.get("steps", [])
			progress = 2 if "marker" in steps else 1 if "tracks" in steps else 0
			var region := str(batch.get("origin_region", ""))
			if not region.is_empty():
				_origin_region = region
			_origin_site_name = str(batch.get("origin_site_name", ""))
			_deadline = int(batch.get("deadline", 0))
			var member_names: PackedStringArray = PackedStringArray()
			for member: Variant in batch.get("members", []):
				if member is Dictionary:
					var label := str(member.get("display_name", member.get("name", "")))
					if not label.is_empty():
						member_names.append(label)
			_missing_label = "、".join(member_names)
			break
	_large = large
	font_px = 23 if large else 19
	_inspect.visible = enabled and progress < KEYS.size()
	_inspect.focus_mode = Control.FOCUS_ALL if _inspect.visible else Control.FOCUS_NONE
	if _inspect.visible:
		var action_hint := "核对行进痕迹" if progress == 0 else "沿交接标记查找转运点"
		var place := _node_title(progress)
		_inspect.tooltip_text = "%s · %s" % [place, action_hint]
		_inspect.accessibility_name = action_hint
	set_process(_inspect.visible and not _is_low_motion())
	_layout_target()
	queue_redraw()


func _node_title(index: int) -> String:
	if index == 0:
		return _origin_site_name if not _origin_site_name.is_empty() else NAMES[0]
	if progress == 0:
		return "待追踪方向"
	return NAMES[1]


func _node_subline(index: int) -> String:
	if index == 0:
		if progress == 0:
			return "最后出现 · 核对痕迹"
		return "最后出现 · 已核对"
	if progress == 0:
		return "先核对起始痕迹"
	if progress == 1:
		return "沿交接标记查找"
	return "交接标记已记录"


func _sub_font_px() -> int:
	return 16 if _large else 13


func _label_box(index: int) -> Rect2:
	var font := get_theme_default_font()
	var title := _node_title(index)
	var sub := _node_subline(index)
	var sub_px := _sub_font_px()
	var m_title := font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, font_px)
	var m_sub := font.get_string_size(sub, HORIZONTAL_ALIGNMENT_LEFT, -1, sub_px)
	var pad_x := 16.0 if _large else 14.0
	var pad_y := 8.0 if _large else 6.0
	var gap := 3.0
	var box_w := ceilf(maxf(m_title.x, m_sub.x)) + pad_x * 2.0
	var box_h := ceilf(m_title.y + m_sub.y + gap) + pad_y * 2.0
	var center := size * Vector2(ANCHORS[index])
	var top := center.y - 30.0 - box_h if index == 0 else center.y + 30.0
	var left := clampf(center.x - box_w * 0.5, 22.0, maxf(22.0, size.x - 22.0 - box_w))
	top = clampf(top, 22.0, maxf(22.0, size.y - 22.0 - box_h))
	return Rect2(Vector2(left, top), Vector2(box_w, box_h))


func _layout_target() -> void:
	if not is_node_ready() or not _inspect.visible or progress >= KEYS.size():
		return
	var pin := size * Vector2(ANCHORS[progress])
	var box := _label_box(progress).merge(Rect2(pin - Vector2(26, 26), Vector2(52, 52)))
	_inspect.position = box.position
	_inspect.size = box.size


func _sample_trail(start: Vector2, end: Vector2, steps: int) -> PackedVector2Array:
	var ctrl := (start + end) * 0.5 + Vector2(0.0, -minf(size.y * 0.085, 56.0))
	var pts := PackedVector2Array()
	for i in range(steps + 1):
		var t := float(i) / float(steps)
		var inv := 1.0 - t
		pts.append(inv * inv * start + 2.0 * inv * t * ctrl + t * t * end)
	return pts


func _draw_dashed_curve(pts: PackedVector2Array, color: Color, width: float, dash: float, gap: float) -> void:
	if pts.size() < 2:
		return
	var carry := 0.0
	var drawing := true
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var seg := a.distance_to(b)
		if seg <= 0.001:
			continue
		var dir := (b - a) / seg
		var pos := 0.0
		while pos < seg:
			var limit := dash if drawing else gap
			var step := minf(limit - carry, seg - pos)
			if drawing and step > 0.5:
				draw_line(a + dir * pos, a + dir * (pos + step), color, width, true)
			pos += step
			carry += step
			if carry >= limit - 0.001:
				carry = 0.0
				drawing = not drawing


func _draw_chevron(at: Vector2, dir: Vector2, sz: float, color: Color, width: float) -> void:
	var fwd := dir.normalized()
	var right := Vector2(-fwd.y, fwd.x)
	var tip := at + fwd * sz * 0.55
	var wing_l := at - fwd * sz * 0.45 + right * sz * 0.55
	var wing_r := at - fwd * sz * 0.45 - right * sz * 0.55
	draw_polyline(PackedVector2Array([wing_l, tip, wing_r]), color, width, true)


func _draw_region_accent() -> void:
	if _origin_region != "苇灯湿地":
		return
	# Subtle marshland watercolor pools along the lower basin for wetland cases
	var pools := [
		Vector3(0.32, 0.72, 0.065),
		Vector3(0.55, 0.67, 0.080),
		Vector3(0.80, 0.74, 0.060),
	]
	for p: Vector3 in pools:
		var c := Vector2(size.x * p.x, size.y * p.y)
		var rx := size.x * p.z
		var ry := rx * 0.34
		var poly := PackedVector2Array()
		for k in 18:
			var ang := TAU * float(k) / 18.0
			poly.append(c + Vector2(cos(ang) * rx, sin(ang) * ry))
		draw_colored_polygon(poly, WETLAND_WASH)
		draw_line(c + Vector2(-rx * 0.45, -2.0), c + Vector2(rx * 0.35, -2.0), Color(0.35, 0.46, 0.44, 0.28), 1.3, true)
		draw_line(c + Vector2(-rx * 0.20, 4.0), c + Vector2(rx * 0.48, 4.0), Color(0.35, 0.46, 0.44, 0.24), 1.2, true)


func _draw_route(start: Vector2, end: Vector2) -> void:
	var full := _sample_trail(start, end, 28)
	if progress == 0:
		# Do not reveal the transfer route before tracks are verified: show only an uncertain bearing
		var partial := PackedVector2Array()
		for i in range(1, 9):
			partial.append(full[i])
		_draw_dashed_curve(partial, Color(0.45, 0.34, 0.23, 0.50), 2.2, 6.0, 8.0)
		var tip := partial[partial.size() - 1]
		var dir := tip - partial[partial.size() - 2]
		_draw_chevron(tip, dir, 9.0, Color(0.45, 0.34, 0.23, 0.55), 2.0)
		return

	# Trim endpoints cleanly outside node circles
	var trimmed := PackedVector2Array()
	for i in range(full.size()):
		if full[i].distance_to(start) >= 24.0 and full[i].distance_to(end) >= 24.0:
			trimmed.append(full[i])
	if trimmed.size() < 2:
		return

	if progress == 1:
		# Discovered trail heading to transfer branch
		_draw_dashed_curve(trimmed, Color(0.37, 0.26, 0.16, 0.42), 5.0, 12.0, 8.0)
		_draw_dashed_curve(trimmed, GOLD, 2.6, 12.0, 8.0)
	else:
		# Confirmed full trail (both clues recorded)
		draw_polyline(trimmed, Color(0.36, 0.25, 0.15, 0.52), 5.5, true)
		_draw_dashed_curve(trimmed, GOLD_BRIGHT, 2.6, 14.0, 6.0)

	# Directional trail chevrons along the discovered route
	for idx in [trimmed.size() / 3, (trimmed.size() * 2) / 3]:
		if idx > 0 and idx < trimmed.size():
			var d := trimmed[idx] - trimmed[idx - 1]
			_draw_chevron(trimmed[idx], d, 11.0, SEPIA, 3.2)
			_draw_chevron(trimmed[idx], d, 10.0, GOLD_BRIGHT if progress >= 2 else GOLD, 2.0)


func _draw_landmark_pennant(at: Vector2, active: bool) -> void:
	# Compact frontier survey pennant marking the real last-seen landmark
	var base := at + Vector2(18.0, -8.0)
	var top := base + Vector2(0.0, -22.0)
	draw_line(base, top, INK, 2.6, true)
	var flag := PackedVector2Array([
		top + Vector2(1.0, 1.0),
		top + Vector2(15.0, 5.5),
		top + Vector2(1.0, 11.0),
	])
	draw_colored_polygon(flag, LANDMARK_RED if active else Color("9b5c43"))
	draw_polyline(PackedVector2Array([flag[0], flag[1], flag[2], flag[0]]), INK, 1.4, true)


func _draw_focus_brackets(rect: Rect2, color: Color) -> void:
	var r := rect.grow(4.0)
	var arm := 10.0
	var corners := [
		[r.position + Vector2(0, arm), r.position, r.position + Vector2(arm, 0)],
		[Vector2(r.end.x - arm, r.position.y), Vector2(r.end.x, r.position.y), Vector2(r.end.x, r.position.y + arm)],
		[Vector2(r.position.x, r.end.y - arm), Vector2(r.position.x, r.end.y), Vector2(r.position.x + arm, r.end.y)],
		[Vector2(r.end.x - arm, r.end.y), r.end, Vector2(r.end.x, r.end.y - arm)],
	]
	for tri: Array in corners:
		draw_polyline(PackedVector2Array(tri), INK, 4.0, true)
		draw_polyline(PackedVector2Array(tri), color, 2.2, true)


func _draw_node(index: int, font: Font) -> void:
	var at := size * Vector2(ANCHORS[index])
	var current := index == progress and _inspect.visible
	var completed := index < progress
	var locked := index > progress
	var hovered := current and _inspect.is_hovered()
	var focused := current and _inspect.has_focus()
	var pressed := current and _inspect.is_pressed()
	var low_motion := _is_low_motion()

	# Last-seen geographic survey ring around Node 0
	if index == 0:
		draw_arc(at, 30.0, 0.0, TAU, 36, Color(0.56, 0.34, 0.22, 0.42 if current else 0.26), 1.6, true)
		_draw_landmark_pennant(at, current or completed)

	# Node pin marker
	var radius := 18.0 if current else 16.0
	if pressed:
		radius -= 1.5

	if completed:
		draw_circle(at + Vector2(0, 2), radius + 1.0, Color(0.18, 0.12, 0.07, 0.25), true, -1, true)
		draw_circle(at, radius, GOLD, true, -1, true)
		draw_arc(at, radius, 0.0, TAU, 32, SEPIA, 2.4, true)
		draw_polyline(PackedVector2Array([
			at + Vector2(-7.5, 0.5),
			at + Vector2(-2.0, 6.0),
			at + Vector2(8.0, -5.5),
		]), INK, 3.4, true)
	elif current:
		var pulse := 0.0 if low_motion else (0.5 + 0.5 * sin(_pulse_time * 3.0))
		var accent := GOLD_BRIGHT if (hovered or focused) else GOLD
		# Soft warm halo
		var halo_r := radius + (10.0 if (hovered or focused) else (6.0 + 4.0 * pulse))
		var halo_a := 0.30 if (hovered or focused) else (0.20 if low_motion else 0.14 + 0.14 * pulse)
		draw_circle(at, halo_r, Color(accent.r, accent.g, accent.b, halo_a), true, -1, true)
		# Static double-ring in low-motion or focused state
		if focused:
			draw_arc(at, radius + 7.0, 0.0, TAU, 36, INK, 4.2, true)
			draw_arc(at, radius + 7.0, 0.0, TAU, 36, FOCUS_RING, 2.4, true)
		elif low_motion or hovered:
			draw_arc(at, radius + 5.5, 0.0, TAU, 36, Color(accent.r, accent.g, accent.b, 0.78), 1.8, true)

		draw_circle(at + Vector2(0, 2), radius + 1.0, Color(0.14, 0.09, 0.05, 0.34), true, -1, true)
		draw_circle(at, radius, INK_DARK, true, -1, true)
		draw_arc(at, radius, 0.0, TAU, 36, accent, 3.0 if (hovered or focused) else 2.5, true)
		draw_circle(at, 5.5 if (hovered or focused) else 4.5, accent, true, -1, true)
	else:
		# Locked / undiscovered node: muted survey mark, non-interactive
		draw_circle(at, 14.0, PARCHMENT_MUTED, true, -1, true)
		draw_arc(at, 14.0, 0.0, TAU, 28, SEPIA_SOFT, 1.8, true)
		var q_px := 16 if _large else 14
		var q_base := (font.get_ascent(q_px) - font.get_descent(q_px)) * 0.5
		draw_string(font, at + Vector2(-8.0, q_base), "?", HORIZONTAL_ALIGNMENT_CENTER, 16.0, q_px, SEPIA_SOFT)

	# Node label plaque
	var box := _label_box(index)
	var title := _node_title(index)
	var sub := _node_subline(index)
	var sub_px := _sub_font_px()

	if current:
		var border := FOCUS_RING if focused else (GOLD_BRIGHT if hovered else GOLD)
		var bg := Color(0.21, 0.15, 0.10, 0.96) if (hovered or focused) else INK_DARK
		draw_rect(box.grow(2.0), Color(0.12, 0.08, 0.04, 0.28), true)
		draw_rect(box, bg, true)
		draw_rect(box, border, false, 2.4 if (hovered or focused) else 1.8)
		if focused:
			_draw_focus_brackets(box, FOCUS_RING)
	elif completed:
		draw_rect(box.grow(1.0), Color(0.24, 0.17, 0.10, 0.16), true)
		draw_rect(box, PARCHMENT_CARD, true)
		draw_rect(box, SEPIA, false, 1.6)
	else:
		draw_rect(box, PARCHMENT_MUTED, true)
		draw_rect(box, SEPIA_SOFT, false, 1.2)

	var pad_y := 8.0 if _large else 6.0
	var title_h := font.get_height(font_px)
	var title_base := box.position.y + pad_y + font.get_ascent(font_px)
	var sub_base := box.position.y + pad_y + title_h + 3.0 + font.get_ascent(sub_px)

	var title_col := PAPER if current else (INK if completed else SEPIA_SOFT)
	var sub_col := (GOLD_BRIGHT if (hovered or focused) else GOLD) if current else (DONE_SAGE if completed else SEPIA_SOFT)

	draw_string(font, Vector2(box.position.x, title_base), title, HORIZONTAL_ALIGNMENT_CENTER, box.size.x, font_px, title_col)
	draw_string(font, Vector2(box.position.x, sub_base), sub, HORIZONTAL_ALIGNMENT_CENTER, box.size.x, sub_px, sub_col)


func _draw_cartouche(font: Font) -> void:
	var header_px := 20 if _large else 17
	var detail_px := 16 if _large else 13
	var region_text := _origin_region if not _origin_region.is_empty() else "失联调查"
	var header := "%s · %s" % [region_text, _case_id] if not _case_id.is_empty() else region_text
	var parts := PackedStringArray()
	if not _origin_site_name.is_empty():
		parts.append("最后出现：" + _origin_site_name)
	if not _missing_label.is_empty():
		parts.append("待寻：" + _missing_label)
	var detail := "   |   ".join(parts)

	var m_head := font.get_string_size(header, HORIZONTAL_ALIGNMENT_LEFT, -1, header_px)
	var m_det := font.get_string_size(detail, HORIZONTAL_ALIGNMENT_LEFT, -1, detail_px) if not detail.is_empty() else Vector2.ZERO
	var max_w := maxf(200.0, size.x * 0.64)
	var pad_x := 16.0
	var pad_y := 10.0
	var card_w := minf(max_w, ceilf(maxf(m_head.x, m_det.x)) + pad_x * 2.0)
	var card_h := ceilf(m_head.y + (m_det.y + 4.0 if not detail.is_empty() else 0.0)) + pad_y * 2.0
	var rect := Rect2(Vector2(28.0, 24.0), Vector2(card_w, card_h))

	draw_rect(rect.grow(2.0), Color(0.18, 0.12, 0.07, 0.18), true)
	draw_rect(rect, PARCHMENT_CARD, true)
	draw_rect(rect, SEPIA, false, 1.8)
	draw_rect(rect.grow(-3.5), Color(0.45, 0.34, 0.23, 0.42), false, 1.0)

	var y1 := rect.position.y + pad_y + font.get_ascent(header_px)
	draw_string(font, Vector2(rect.position.x + pad_x, y1), header, HORIZONTAL_ALIGNMENT_LEFT, card_w - pad_x * 2.0, header_px, INK)
	if not detail.is_empty():
		var y2 := rect.position.y + pad_y + font.get_height(header_px) + 4.0 + font.get_ascent(detail_px)
		draw_string(font, Vector2(rect.position.x + pad_x, y2), detail, HORIZONTAL_ALIGNMENT_LEFT, card_w - pad_x * 2.0, detail_px, SEPIA)


func _draw_status_strip(font: Font) -> void:
	var px := 16 if _large else 13
	var status_text := ""
	if progress == 0:
		status_text = "线索 0/2 · 核对最后出现地点的行进痕迹（点击节点或 Tab + 回车）"
	elif progress == 1:
		status_text = "线索 1/2 · 痕迹已得，沿交接标记查找转运支路（点击节点或 Tab + 回车）"
	else:
		status_text = "线索 2/2 · 两项线索已齐，待返暮汀交存确认转运点"

	if _large and progress < 2:
		status_text = "线索 %d/2 · %s" % [progress, "核对行进痕迹" if progress == 0 else "沿交接标记查找转运点"]

	var measured := font.get_string_size(status_text, HORIZONTAL_ALIGNMENT_LEFT, -1, px)
	var pad_x := 14.0
	var pad_y := 8.0
	var max_w := maxf(240.0, size.x - 56.0)
	var box_w := minf(max_w, ceilf(measured.x) + pad_x * 2.0)
	var box_h := ceilf(measured.y) + pad_y * 2.0
	var rect := Rect2(Vector2(28.0, maxf(28.0, size.y - 26.0 - box_h)), Vector2(box_w, box_h))

	draw_rect(rect, INK_DARK, true)
	draw_rect(rect, GOLD if progress < 2 else DONE_SAGE, false, 1.6)
	var baseline := rect.position.y + pad_y + font.get_ascent(px)
	draw_string(font, Vector2(rect.position.x + pad_x, baseline), status_text, HORIZONTAL_ALIGNMENT_LEFT, box_w - pad_x * 2.0, px, PAPER)


func _draw() -> void:
	if _paper == null:
		return
	var frame_rect := Rect2(Vector2(4, 4), size - Vector2(8, 8))
	draw_texture_rect(_paper, frame_rect, false)
	_draw_region_accent()

	var start := size * Vector2(ANCHORS[0])
	var end := size * Vector2(ANCHORS[1])
	_draw_route(start, end)

	var font := get_theme_default_font()
	_draw_cartouche(font)
	for index in KEYS.size():
		_draw_node(index, font)
	_draw_status_strip(font)

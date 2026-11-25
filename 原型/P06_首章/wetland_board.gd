extends RefCounted

const ShieldStage = preload("res://shield_stage.gd")

const INK := Color("3b332a")
const BANK_OUTER := Color("8b7960")
const BANK_INNER := Color("695f4c")
const SHALLOW_BASE := Color("768b80")
const SHALLOW_SHOAL := Color("94a596")
const SHALLOW_RIPPLE := Color("ded4b8")
const SHALLOW_SHADOW := Color("556a63")
const DEEP_SHELF := Color("49656e")
const DEEP_BASE := Color("304b56")
const DEEP_CORE := Color("243c47")
const DEEP_RIPPLE := Color("89a9ad")
const DEEP_INK := Color("1f323b")
const BRIDGE_CHANNEL := Color("5a6d68")
const BRIDGE_DECK := Color("b48c5f")
const BRIDGE_DECK_ALT := Color("a57f54")
const BRIDGE_HIGHLIGHT := Color("d1b184")
const BRIDGE_SIDE := Color("674b36")
const BRIDGE_POST := Color("4a382c")
const STONE_DARK := Color("5b5245")
const STONE_MID := Color("847866")
const STONE_LIGHT := Color("a49781")
const REED_COLOR := Color("7e774d")
const REED_DARK := Color("535136")
const LEGEND_BG := Color(0.11, 0.135, 0.12, 0.92)
const LEGEND_EDGE := Color("776850")


static func draw_water_and_bridges(
	canvas: CanvasItem,
	coordinate_map: Dictionary,
	terrain_cells: Dictionary,
	boundary_fn: Callable,
	grid_fn: Callable,
	scale: float,
	sideways: bool,
	font: Font,
	font_size: int,
	view_size: Vector2,
	show_deployment: bool,
	text_color: Color
) -> void:
	var shallow: Dictionary = terrain_cells.get("SHALLOW_WATER", {})
	var deep: Dictionary = terrain_cells.get("DEEP_WATER", {})
	var bridges: Dictionary = terrain_cells.get("FIXED_BRIDGE", {})
	var all_wet := {}
	for cell: Vector2i in shallow:
		all_wet[cell] = true
	for cell: Vector2i in deep:
		all_wet[cell] = true
	for cell: Vector2i in bridges:
		all_wet[cell] = true

	# 1. Unified damp-earth shoreline apron around all water & bridge-channel cells.
	if not all_wet.is_empty():
		var wet_paths: Array = boundary_fn.call(all_wet)
		for cell: Vector2i in all_wet:
			var pt: Vector2 = coordinate_map[cell]
			var outer_hex := _organic_hex(pt, scale * 1.15, sideways, cell)
			canvas.draw_colored_polygon(outer_hex, Color(BANK_OUTER, 0.34))
		for cell: Vector2i in all_wet:
			var pt: Vector2 = coordinate_map[cell]
			var inner_hex := _organic_hex(pt, scale * 1.05, sideways, cell)
			canvas.draw_colored_polygon(inner_hex, Color(BANK_INNER, 0.48))
		for path: PackedVector2Array in wet_paths:
			var soft := _bevel_loop(path, minf(6.5, scale * 0.22))
			canvas.draw_polyline(soft, Color(BANK_INNER, 0.58), 3.6, true)

	# 2. Recessed creek bed under fixed bridges so decks visibly span wet marsh.
	for cell: Vector2i in bridges:
		_draw_bridge_channel(canvas, coordinate_map[cell], scale, sideways, cell)

	# 3. Shallow water pools (watercolor wash + shoal glow + curved ripples + subtle hex ticks).
	if not shallow.is_empty():
		for cell: Vector2i in shallow:
			var pt: Vector2 = coordinate_map[cell]
			canvas.draw_colored_polygon(_organic_hex(pt, scale * 0.99, sideways, cell), Color(SHALLOW_BASE, 0.84))
			canvas.draw_colored_polygon(_organic_hex(pt + Vector2(-0.04, -0.03) * scale, scale * 0.72, sideways, cell),
				Color(SHALLOW_SHOAL, 0.34))
			_draw_shallow_ripples(canvas, pt, scale, cell)
			_draw_tactical_hex_ticks(canvas, pt, scale, sideways, Color(SHALLOW_RIPPLE, 0.42))
		for path: PackedVector2Array in boundary_fn.call(shallow):
			var soft := _bevel_loop(path, minf(5.5, scale * 0.18))
			canvas.draw_polyline(soft, Color(INK, 0.46), 1.6, true)
			var foam := _inset_loop(soft, 1.8)
			canvas.draw_polyline(foam, Color(SHALLOW_RIPPLE, 0.44), 1.1, true)

	# 4. Deep water basin (distinct dark luminance + shelf step + diagonal depth hatch for colorblind clarity).
	if not deep.is_empty():
		for cell: Vector2i in deep:
			var pt: Vector2 = coordinate_map[cell]
			canvas.draw_colored_polygon(_organic_hex(pt, scale * 0.99, sideways, cell), Color(DEEP_SHELF, 0.94))
			canvas.draw_colored_polygon(_organic_hex(pt + Vector2(0.0, 0.03) * scale, scale * 0.82, sideways, cell),
				Color(DEEP_BASE, 0.96))
			canvas.draw_colored_polygon(_organic_hex(pt + Vector2(0.0, 0.05) * scale, scale * 0.56, sideways, cell),
				Color(DEEP_CORE, 0.78))
			_draw_deep_pattern(canvas, pt, scale, sideways, cell)
			_draw_tactical_hex_ticks(canvas, pt, scale, sideways, Color(DEEP_RIPPLE, 0.34))
		for path: PackedVector2Array in boundary_fn.call(deep):
			var soft := _bevel_loop(path, minf(5.5, scale * 0.18))
			canvas.draw_polyline(soft, Color(DEEP_INK, 0.78), 2.4, true)
			var inner := _inset_loop(soft, 2.4)
			canvas.draw_polyline(inner, Color(DEEP_RIPPLE, 0.46), 1.2, true)

	# 5. Sparse shoreline reed tufts & wet pebbles along outer bank edges (kept close to bank).
	for cell: Vector2i in shallow:
		_draw_bank_accents(canvas, coordinate_map[cell], scale, sideways, cell, all_wet)

	# 6. Weathered wooden plank bridges with stone abutments & grounded pilings.
	for cell: Vector2i in bridges:
		_draw_fixed_bridge(canvas, cell, bridges, coordinate_map, grid_fn, scale, sideways)

	# 7. Pattern-coded terrain key.
	if not terrain_cells.is_empty() and font != null:
		_draw_key(canvas, terrain_cells, font, font_size, view_size, show_deployment, text_color)


static func draw_wetland_obstacle(canvas: CanvasItem, at: Vector2, scale: float, high: bool, seed_idx: int) -> void:
	var rx := scale * (0.64 if high else 0.50)
	var ry := scale * (0.32 if high else 0.22)
	# Grounding wet-earth shadow
	_draw_ellipse(canvas, at + Vector2(0.0, ry * 0.32), rx * 1.18, ry * 0.92, Color(0.14, 0.12, 0.10, 0.48))
	if high:
		# Weathered stone embankment pier / wetland boulder cluster with storybook ink contour
		var base_poly := PackedVector2Array([
			at + Vector2(-rx * 0.86, ry * 0.35),
			at + Vector2(-rx * 0.96, -ry * 0.18),
			at + Vector2(-rx * 0.44, -ry * 0.82),
			at + Vector2(rx * 0.38, -ry * 0.88),
			at + Vector2(rx * 0.92, -ry * 0.22),
			at + Vector2(rx * 0.82, ry * 0.38),
			at + Vector2(rx * 0.12, ry * 0.58),
			at + Vector2(-rx * 0.52, ry * 0.54),
		])
		canvas.draw_colored_polygon(base_poly, STONE_DARK)
		var main_body := PackedVector2Array([
			at + Vector2(-rx * 0.78, ry * 0.18),
			at + Vector2(-rx * 0.86, -ry * 0.32),
			at + Vector2(-rx * 0.36, -ry * 0.94),
			at + Vector2(rx * 0.34, -ry * 0.98),
			at + Vector2(rx * 0.80, -ry * 0.34),
			at + Vector2(rx * 0.72, ry * 0.16),
			at + Vector2(0.0, ry * 0.34),
		])
		canvas.draw_colored_polygon(main_body, STONE_MID)
		var top_facet := PackedVector2Array([
			at + Vector2(-rx * 0.62, -ry * 0.38),
			at + Vector2(-rx * 0.30, -ry * 0.92),
			at + Vector2(rx * 0.28, -ry * 0.95),
			at + Vector2(rx * 0.60, -ry * 0.42),
			at + Vector2(rx * 0.10, -ry * 0.24),
		])
		canvas.draw_colored_polygon(top_facet, STONE_LIGHT)
		# Secondary shoulder stone
		var side_sign := -1.0 if seed_idx % 2 == 0 else 1.0
		var sub_center := at + Vector2(side_sign * rx * 0.52, ry * 0.18)
		var sub_poly := PackedVector2Array([
			sub_center + Vector2(-rx * 0.34, ry * 0.24),
			sub_center + Vector2(-rx * 0.30, -ry * 0.28),
			sub_center + Vector2(rx * 0.24, -ry * 0.34),
			sub_center + Vector2(rx * 0.38, ry * 0.16),
		])
		canvas.draw_colored_polygon(sub_poly, STONE_MID.darkened(0.08))
		# Ink outlines & crack line
		var closed := base_poly.duplicate()
		closed.append(base_poly[0])
		canvas.draw_polyline(closed, Color(INK, 0.86), 1.65, true)
		var sub_closed := sub_poly.duplicate()
		sub_closed.append(sub_poly[0])
		canvas.draw_polyline(sub_closed, Color(INK, 0.78), 1.35, true)
		canvas.draw_polyline(PackedVector2Array([
			at + Vector2(-rx * 0.16, -ry * 0.64),
			at + Vector2(rx * 0.04, -ry * 0.22),
			at + Vector2(-rx * 0.08, ry * 0.16),
		]), Color(INK, 0.55), 1.15, true)
		# Small reed blades tucked at stone foot
		_draw_reed_tuft(canvas, at + Vector2(-side_sign * rx * 0.76, ry * 0.28), scale * 0.22)
	else:
		var low_poly := PackedVector2Array([
			at + Vector2(-rx * 0.85, ry * 0.20),
			at + Vector2(-rx * 0.58, -ry * 0.55),
			at + Vector2(rx * 0.45, -ry * 0.60),
			at + Vector2(rx * 0.86, ry * 0.15),
			at + Vector2(rx * 0.28, ry * 0.52),
			at + Vector2(-rx * 0.44, ry * 0.48),
		])
		canvas.draw_colored_polygon(low_poly, STONE_MID.darkened(0.10))
		var low_top := PackedVector2Array([
			at + Vector2(-rx * 0.48, -ry * 0.42),
			at + Vector2(rx * 0.32, -ry * 0.46),
			at + Vector2(rx * 0.54, -ry * 0.02),
			at + Vector2(-rx * 0.26, ry * 0.04),
		])
		canvas.draw_colored_polygon(low_top, STONE_LIGHT.darkened(0.08))
		var closed := low_poly.duplicate()
		closed.append(low_poly[0])
		canvas.draw_polyline(closed, Color(INK, 0.76), 1.4, true)


static func _draw_bridge_channel(canvas: CanvasItem, pt: Vector2, scale: float, sideways: bool, cell: Vector2i) -> void:
	canvas.draw_colored_polygon(_organic_hex(pt, scale * 0.96, sideways, cell), Color(BRIDGE_CHANNEL, 0.72))
	canvas.draw_colored_polygon(_organic_hex(pt + Vector2(0.0, scale * 0.04), scale * 0.72, sideways, cell),
		Color(DEEP_SHELF, 0.42))
	for dy in [-0.26, 0.27]:
		var c := pt + Vector2(0.0, dy * scale)
		_draw_wave_arc(canvas, c - Vector2(scale * 0.22, 0.0), scale * 0.44, scale * 0.035,
			Color(SHALLOW_RIPPLE, 0.36), 1.1)


static func _draw_fixed_bridge(
	canvas: CanvasItem,
	cell: Vector2i,
	bridges: Dictionary,
	coordinate_map: Dictionary,
	grid_fn: Callable,
	scale: float,
	sideways: bool
) -> void:
	var point: Vector2 = coordinate_map[cell]
	var reach: Vector2 = grid_fn.call(0.5, 0.0) * scale
	var across: Vector2 = ShieldStage.project_ground(Vector2(0.0, 0.42), sideways) * scale
	var has_left := bridges.has(cell - Vector2i.RIGHT)
	var has_right := bridges.has(cell + Vector2i.RIGHT)
	var start := point - reach * (1.02 if has_left else 0.88)
	var end := point + reach * (1.02 if has_right else 0.88)
	var drop := Vector2(0.0, scale * 0.16)

	# Stone abutment ramps at free bridge ends so the bridge anchors into the dirt bank
	if not has_left:
		_draw_abutment(canvas, start, -reach.normalized(), across, drop)
	if not has_right:
		_draw_abutment(canvas, end, reach.normalized(), across, drop)

	# Soft water shadow cast by the deck
	canvas.draw_colored_polygon(PackedVector2Array([
		start - across + drop * 0.9, end - across + drop * 0.9,
		end + across + drop * 1.85, start + across + drop * 1.85
	]), Color(0.14, 0.16, 0.15, 0.38))

	# Front timber beam thickness
	canvas.draw_colored_polygon(PackedVector2Array([
		start + across, end + across, end + across + drop, start + across + drop
	]), BRIDGE_SIDE)
	canvas.draw_line(start + across + drop, end + across + drop, Color(INK, 0.78), 1.4, true)

	# Deck planks with subtle warm alternating wood tones
	var plank_count := 6
	for i in range(plank_count):
		var t0 := float(i) / float(plank_count)
		var t1 := float(i + 1) / float(plank_count)
		var p0 := start.lerp(end, t0)
		var p1 := start.lerp(end, t1)
		var tone := BRIDGE_DECK if (i + cell.x) % 2 == 0 else BRIDGE_DECK_ALT
		canvas.draw_colored_polygon(PackedVector2Array([
			p0 - across, p1 - across, p1 + across, p0 + across
		]), tone)
		# Sunlit top bevel along plank edge
		canvas.draw_line(p0 - across * 0.86 + (p1 - p0) * 0.18, p0 + across * 0.86 + (p1 - p0) * 0.18,
			Color(BRIDGE_HIGHLIGHT, 0.50), 1.1, true)
		# Crisp ink seam between planks
		if i > 0:
			canvas.draw_line(p0 - across, p0 + across, Color(INK, 0.76), 1.35, true)
		# Tiny iron nail heads near curb rails
		var mid := (p0 + p1) * 0.5
		canvas.draw_circle(mid - across * 0.76, 1.05, Color(INK, 0.65))
		canvas.draw_circle(mid + across * 0.76, 1.05, Color(INK, 0.65))

	# Side timber curb rails with ink border
	for side_sign: float in [-1.0, 1.0]:
		var edge: Vector2 = across * side_sign
		canvas.draw_line(start + edge, end + edge, Color(INK, 0.88), 2.8, true)
		canvas.draw_line(start + edge - Vector2(0.0, 0.7), end + edge - Vector2(0.0, 0.7),
			BRIDGE_HIGHLIGHT if side_sign < 0.0 else BRIDGE_SIDE.lightened(0.18), 1.3, true)

	# Grounded timber pilings dipping into the water with tiny pale water rings
	var post_fractions: Array[float] = [0.12, 0.88]
	for frac: float in post_fractions:
		var brace := start.lerp(end, frac)
		# Rear short post
		canvas.draw_line(brace - across, brace - across - drop * 0.55, BRIDGE_POST, 3.2, true)
		canvas.draw_circle(brace - across - drop * 0.55, 1.6, BRIDGE_HIGHLIGHT, true, -1, true)
		# Front piling extending into water
		var foot := brace + across + drop * 1.45
		_draw_ellipse(canvas, foot, scale * 0.11, scale * 0.045, Color(SHALLOW_RIPPLE, 0.42))
		canvas.draw_line(foot, brace + across - drop * 0.45, Color(INK, 0.88), 4.6, true)
		canvas.draw_line(foot, brace + across - drop * 0.45, BRIDGE_POST.lightened(0.12), 2.8, true)
		canvas.draw_circle(brace + across - drop * 0.46, 1.85, BRIDGE_HIGHLIGHT, true, -1, true)


static func _draw_abutment(canvas: CanvasItem, edge_center: Vector2, outward: Vector2, across: Vector2, drop: Vector2) -> void:
	var ext := outward * drop.y * 1.35
	var poly := PackedVector2Array([
		edge_center - across * 1.06,
		edge_center + ext - across * 0.92,
		edge_center + ext + across * 0.92,
		edge_center + across * 1.06,
	])
	canvas.draw_colored_polygon(poly, STONE_MID)
	var top := PackedVector2Array([
		edge_center - across * 0.84,
		edge_center + ext * 0.72 - across * 0.74,
		edge_center + ext * 0.72 + across * 0.74,
		edge_center + across * 0.84,
	])
	canvas.draw_colored_polygon(top, STONE_LIGHT)
	var closed := poly.duplicate()
	closed.append(poly[0])
	canvas.draw_polyline(closed, Color(INK, 0.75), 1.35, true)


static func _draw_shallow_ripples(canvas: CanvasItem, pt: Vector2, scale: float, cell: Vector2i) -> void:
	var shift := float(posmod(cell.x * 3 - cell.y * 2, 3) - 1) * 0.10 * scale
	for i in range(2):
		var dy := (-0.13 + float(i) * 0.25) * scale
		var w := scale * (0.44 if i == 0 else 0.36)
		var origin := pt + Vector2(shift - w * 0.5 + (scale * 0.05 if i == 1 else 0.0), dy)
		_draw_wave_arc(canvas, origin + Vector2(0.0, 1.4), w, scale * 0.042, Color(SHALLOW_SHADOW, 0.46), 1.3)
		_draw_wave_arc(canvas, origin, w, scale * 0.042, Color(SHALLOW_RIPPLE, 0.68), 1.35)


static func _draw_deep_pattern(canvas: CanvasItem, pt: Vector2, scale: float, sideways: bool, cell: Vector2i) -> void:
	# Subtle diagonal depth strokes (high luminance-pattern cue for colorblind/grayscale separation)
	var rx := scale * 0.46
	var ry := scale * (0.28 if sideways else 0.42)
	for i in range(-1, 2):
		var ox := float(i) * scale * 0.22
		var a := pt + Vector2(ox - rx * 0.22, -ry * 0.48)
		var b := pt + Vector2(ox + rx * 0.22, ry * 0.48)
		canvas.draw_line(a, b, Color(DEEP_INK, 0.52), 1.25, true)
	# Double crisp ripple arcs in pale slate-teal
	var shift := float(posmod(cell.x + cell.y, 3) - 1) * 0.08 * scale
	for dy_f in [-0.11, 0.12]:
		var w := scale * 0.36
		var origin := pt + Vector2(shift - w * 0.5, dy_f * scale)
		_draw_wave_arc(canvas, origin, w, scale * 0.036, Color(DEEP_RIPPLE, 0.56), 1.25)


static func _draw_bank_accents(canvas: CanvasItem, pt: Vector2, scale: float, sideways: bool, cell: Vector2i, all_wet: Dictionary) -> void:
	# Place tiny reed tuft or pebble on up to 2 dry-facing corners of shallow water
	var neighbors := [Vector2i(-1, 1), Vector2i(-1, 0), Vector2i(0, -1),
		Vector2i(1, -1), Vector2i(1, 0), Vector2i(0, 1)]
	var placed := 0
	for i in range(6):
		if all_wet.has(cell + neighbors[i]):
			continue
		if posmod(cell.x * 7 + cell.y * 13 + i * 5, 3) != 0:
			continue
		var angle := TAU * (float(i) / 6.0 + 0.33)
		var dir := ShieldStage.project_ground(Vector2(cos(angle), sin(angle)), sideways)
		var pos := pt + dir * scale * 0.94
		if placed % 2 == 0:
			_draw_reed_tuft(canvas, pos, scale * 0.17)
		else:
			_draw_ellipse(canvas, pos, scale * 0.085, scale * 0.045, STONE_MID)
			_draw_ellipse(canvas, pos - Vector2(0.0, 0.8), scale * 0.055, scale * 0.028, STONE_LIGHT)
		placed += 1
		if placed >= 2:
			break


static func _draw_reed_tuft(canvas: CanvasItem, base: Vector2, h: float) -> void:
	canvas.draw_line(base, base + Vector2(-h * 0.38, -h * 0.86), REED_DARK, 1.5, true)
	canvas.draw_line(base, base + Vector2(h * 0.05, -h * 1.05), REED_COLOR, 1.4, true)
	canvas.draw_line(base, base + Vector2(h * 0.42, -h * 0.78), REED_COLOR.darkened(0.12), 1.3, true)


static func _draw_tactical_hex_ticks(canvas: CanvasItem, pt: Vector2, scale: float, sideways: bool, color: Color) -> void:
	# Subtle short ticks at each hex corner so tactical grid boundaries stay clear without harsh cages.
	var r := scale * 0.90
	for i in range(6):
		var a0 := TAU * (float(i) / 6.0 + 0.25)
		var a_prev := TAU * (float(posmod(i - 1, 6)) / 6.0 + 0.25)
		var a_next := TAU * (float((i + 1) % 6) / 6.0 + 0.25)
		var v := pt + ShieldStage.project_ground(Vector2(cos(a0), sin(a0)), sideways) * r
		var vp := pt + ShieldStage.project_ground(Vector2(cos(a_prev), sin(a_prev)), sideways) * r
		var vn := pt + ShieldStage.project_ground(Vector2(cos(a_next), sin(a_next)), sideways) * r
		canvas.draw_polyline(PackedVector2Array([
			v.lerp(vp, 0.16), v, v.lerp(vn, 0.16)
		]), color, 1.0, true)


static func _draw_wave_arc(canvas: CanvasItem, start: Vector2, width: float, amp: float, color: Color, line_w: float) -> void:
	var pts := PackedVector2Array()
	for i in range(9):
		var t := float(i) / 8.0
		var y := sin(t * TAU) * amp
		pts.append(start + Vector2(t * width, y))
	canvas.draw_polyline(pts, color, line_w, true)


static func _draw_ellipse(canvas: CanvasItem, center: Vector2, rx: float, ry: float, color: Color) -> void:
	var pts := PackedVector2Array()
	for i in range(14):
		var a := TAU * float(i) / 14.0
		pts.append(center + Vector2(cos(a) * rx, sin(a) * ry))
	canvas.draw_colored_polygon(pts, color)


static func _organic_hex(pos: Vector2, radius: float, sideways: bool, cell: Vector2i) -> PackedVector2Array:
	var shape := PackedVector2Array()
	var steps := 12
	for i in range(steps):
		var angle := TAU * (float(i) / float(steps) + 0.25)
		# Blend hex vertex shape with subtle deterministic organic wobble so pools feel hand-painted
		var hex_mod := 1.0 - 0.045 * (1.0 - absf(cos(3.0 * (angle - PI * 0.5))))
		var wobble := 1.0 + 0.032 * sin(float(i) * 2.1 + float(cell.x) * 1.7 + float(cell.y) * 2.9)
		shape.append(pos + ShieldStage.project_ground(Vector2(cos(angle), sin(angle)), sideways) * (radius * hex_mod * wobble))
	return shape


static func _bevel_loop(path: PackedVector2Array, bevel: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var count := path.size()
	if count < 3:
		return path
	for i in range(count):
		var cur := path[i]
		var prev := path[posmod(i - 1, count)]
		var next := path[(i + 1) % count]
		out.append(cur.move_toward(prev, bevel))
		out.append(cur.move_toward(next, bevel))
	out.append(out[0])
	return out


static func _inset_loop(loop: PackedVector2Array, amount: float) -> PackedVector2Array:
	if loop.size() < 4:
		return loop
	var centroid := Vector2.ZERO
	var count := loop.size() - 1
	for i in range(count):
		centroid += loop[i]
	centroid /= float(count)
	var out := PackedVector2Array()
	for i in range(count):
		out.append(loop[i].move_toward(centroid, amount))
	out.append(out[0])
	return out


static func _draw_key(
	canvas: CanvasItem,
	terrain_cells: Dictionary,
	font: Font,
	font_size: int,
	view_size: Vector2,
	show_deployment: bool,
	text_color: Color
) -> void:
	var order := [
		{"id": "SHALLOW_WATER", "label": "浅水"},
		{"id": "DEEP_WATER", "label": "深水"},
		{"id": "FIXED_BRIDGE", "label": "木桥"},
	]
	var active: Array[Dictionary] = []
	for item in order:
		if terrain_cells.has(item.id):
			active.append(item)
	if active.is_empty():
		return
	var origin := Vector2(24.0, view_size.y - (88.0 if show_deployment else 48.0))
	var height := float(font_size + 18)
	var span := float(font_size * 2 + 44)
	var box := Rect2(origin, Vector2(span * active.size() + 12.0, height))
	canvas.draw_rect(box, LEGEND_BG)
	canvas.draw_rect(box, LEGEND_EDGE, false, 1.2)
	var left := origin.x + 10.0
	for item in active:
		var sw := Rect2(Vector2(left, origin.y + 7.0), Vector2(22.0, height - 14.0))
		if item.id == "SHALLOW_WATER":
			canvas.draw_rect(sw, SHALLOW_BASE)
			_draw_wave_arc(canvas, sw.position + Vector2(3.0, sw.size.y * 0.52), sw.size.x - 6.0, 2.0, SHALLOW_RIPPLE, 1.3)
		elif item.id == "DEEP_WATER":
			canvas.draw_rect(sw, DEEP_BASE)
			canvas.draw_line(sw.position + Vector2(4.0, 2.0), sw.position + Vector2(10.0, sw.size.y - 2.0), DEEP_INK, 1.3, true)
			canvas.draw_line(sw.position + Vector2(12.0, 2.0), sw.position + Vector2(18.0, sw.size.y - 2.0), DEEP_INK, 1.3, true)
			_draw_wave_arc(canvas, sw.position + Vector2(3.0, sw.size.y * 0.52), sw.size.x - 6.0, 1.6, DEEP_RIPPLE, 1.2)
		else:
			canvas.draw_rect(sw, BRIDGE_DECK)
			canvas.draw_line(sw.position + Vector2(7.0, 1.0), sw.position + Vector2(7.0, sw.size.y - 1.0), INK, 1.2, true)
			canvas.draw_line(sw.position + Vector2(15.0, 1.0), sw.position + Vector2(15.0, sw.size.y - 1.0), INK, 1.2, true)
		canvas.draw_rect(sw, Color(INK, 0.82), false, 1.0)
		canvas.draw_string(font, Vector2(left + 28.0, origin.y + height - 9.0), item.label,
			HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, text_color)
		left += span

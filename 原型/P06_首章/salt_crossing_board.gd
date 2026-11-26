extends RefCounted

# 2D hex-overlay and specification module for RG04 · 沉息湖区 · SALT_CROSSING (盐渡).
# Exact 63-cell (7x9) terrain coordinates from authoritative 地图地形.json.
# Designed to plug cleanly into hex_board.gd without modifying any hot files here.

const REGION_ID := "RG04"
const SITE_ID := "G"
const BOARD_ID := "SALT_CROSSING"
const FIELD_ART := "res://assets/salt_crossing/salt_crossing_ink.png"

const CELLS := {
	"HIGH_GROUND": [Vector2i(1, 2), Vector2i(5, 2)],
	"SHALLOW_WATER": [
		Vector2i(3, 2),
		Vector2i(0, 3), Vector2i(1, 3), Vector2i(2, 3), Vector2i(3, 3),
		Vector2i(4, 3), Vector2i(5, 3), Vector2i(6, 3),
		Vector2i(3, 4),
	],
	"LOW_OBSTACLE": [Vector2i(1, 4), Vector2i(5, 4)],
}

const INK := Color("342e2a")
const SHALLOW_FILL := Color("8ca4a0")
const SHALLOW_RIM := Color("ded6c2")
const SHALLOW_RIPPLE := Color("e6e0ce")
const HIGH_GROUND_FILL := Color("e6decb")
const HIGH_GROUND_RIM := Color("948870")
const LOW_COVER_FILL := Color("8e8372")
const LOW_COVER_TOP := Color("cfc6b2")


static func field_art_path(region: String, site: String) -> String:
	return FIELD_ART if region == REGION_ID and site == SITE_ID else ""


static func hex_points(center: Vector2, radius: float, sideways := false) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var offset := 0.0 if sideways else PI / 6.0
	for i in 6:
		var a := offset + PI / 3.0 * float(i)
		pts.append(center + Vector2(cos(a) * radius, sin(a) * radius * 0.78))
	return pts


static func draw_terrain(
	canvas: CanvasItem,
	coordinate_map: Dictionary,
	terrain_cells: Dictionary,
	scale: float,
	sideways := false
) -> void:
	# 1. SHALLOW_WATER: pale salt-lake ford with salt-crust outer rim & subtle wave ticks (keeps warnings crisp)
	for cell in _cells_for(terrain_cells, "SHALLOW_WATER"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var outer := hex_points(pt, scale * 0.98, sideways)
		var inner := hex_points(pt, scale * 0.88, sideways)
		canvas.draw_colored_polygon(outer, Color(SHALLOW_RIM, 0.56))
		canvas.draw_colored_polygon(inner, Color(SHALLOW_FILL, 0.76))
		canvas.draw_polyline(_closed(inner), Color(SHALLOW_RIPPLE, 0.72), 1.4, true)
		# Two gentle horizontal ripple ticks near bottom edge (center left clear for base rings & warnings)
		canvas.draw_line(pt + Vector2(-scale * 0.30, scale * 0.18), pt + Vector2(-scale * 0.04, scale * 0.18),
			Color(SHALLOW_RIPPLE, 0.65), 1.4, true)
		canvas.draw_line(pt + Vector2(scale * 0.06, scale * 0.28), pt + Vector2(scale * 0.28, scale * 0.28),
			Color(SHALLOW_RIPPLE, 0.58), 1.3, true)

	# 2. HIGH_GROUND: pale salt-limestone stepped platform
	for cell in _cells_for(terrain_cells, "HIGH_GROUND"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var base := hex_points(pt + Vector2(0, scale * 0.07), scale * 0.94, sideways)
		var top := hex_points(pt + Vector2(0, -scale * 0.06), scale * 0.84, sideways)
		canvas.draw_colored_polygon(base, Color(HIGH_GROUND_RIM, 0.75))
		canvas.draw_colored_polygon(top, Color(HIGH_GROUND_FILL, 0.92))
		canvas.draw_polyline(_closed(top), Color(HIGH_GROUND_RIM, 0.95), 2.0, true)
		var c0 := pt + Vector2(-scale * 0.22, scale * 0.34)
		var c1 := pt + Vector2(0.0, scale * 0.24)
		var c2 := pt + Vector2(scale * 0.22, scale * 0.34)
		canvas.draw_polyline(PackedVector2Array([c0, c1, c2]), Color(INK, 0.65), 1.8, true)

	# 3. LOW_OBSTACLE: weathered salt-encrusted ferry bollard & low timber bumper
	for cell in _cells_for(terrain_cells, "LOW_OBSTACLE"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var foot := hex_points(pt, scale * 0.86, sideways)
		canvas.draw_colored_polygon(foot, Color(LOW_COVER_FILL, 0.52))
		var wall := Rect2(pt + Vector2(-scale * 0.54, -scale * 0.20), Vector2(scale * 1.08, scale * 0.40))
		var cap := Rect2(pt + Vector2(-scale * 0.58, -scale * 0.28), Vector2(scale * 1.16, scale * 0.14))
		canvas.draw_rect(wall, LOW_COVER_FILL, true)
		canvas.draw_rect(cap, LOW_COVER_TOP, true)
		canvas.draw_rect(wall, INK, false, 2.0)
		canvas.draw_rect(cap, INK, false, 1.8)


static func _cells_for(terrain_cells: Dictionary, key: String) -> Array:
	if terrain_cells.has(key):
		var raw = terrain_cells[key]
		if raw is Dictionary:
			return raw.keys()
		if raw is Array:
			return raw
	return CELLS.get(key, [])


static func _closed(pts: PackedVector2Array) -> PackedVector2Array:
	var out := pts.duplicate()
	if not out.is_empty():
		out.append(out[0])
	return out

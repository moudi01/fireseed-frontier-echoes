extends RefCounted

# 2D hex-overlay and specification module for RG03 · G · MIRROR_COURT (镜关战场).
# Designed to plug cleanly into hex_board.gd without modifying any hot files here.

const REGION_ID := "RG03"
const SITE_ID := "G"
const BOARD_ID := "MIRROR_COURT"
const FIELD_ART := "res://assets/mirror_court/mirror_court_ink.png"

const CELLS := {
	"LOW_OBSTACLE": [Vector2i(1, 4), Vector2i(4, 4)],
	"HIGH_OBSTACLE": [Vector2i(2, 4), Vector2i(3, 4)],
	"HIGH_GROUND": [Vector2i(1, 3), Vector2i(6, 3), Vector2i(0, 5), Vector2i(5, 5)],
}

const INK := Color("362d26")
const HIGH_GROUND_FILL := Color("ded2ba")
const HIGH_GROUND_RIM := Color("8d7a5c")
const LOW_COVER_FILL := Color("9d907b")
const LOW_COVER_TOP := Color("bcb099")
const HIGH_COVER_FILL := Color("5e564c")
const HIGH_COVER_MIRROR := Color("9aa5a1")
const HIGH_COVER_BRONZE := Color("9a7c52")


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
	# 1. HIGH_GROUND: pale raised limestone platform with double stepped bevel
	for cell in _cells_for(terrain_cells, "HIGH_GROUND"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var base := hex_points(pt + Vector2(0, scale * 0.07), scale * 0.94, sideways)
		var top := hex_points(pt + Vector2(0, -scale * 0.06), scale * 0.84, sideways)
		canvas.draw_colored_polygon(base, Color(HIGH_GROUND_RIM, 0.72))
		canvas.draw_colored_polygon(top, Color(HIGH_GROUND_FILL, 0.90))
		canvas.draw_polyline(_closed(top), Color(HIGH_GROUND_RIM, 0.95), 2.0, true)
		# Small elevation chevron at bottom rim (leaves cell center open for unit rings & warnings)
		var c0 := pt + Vector2(-scale * 0.22, scale * 0.34)
		var c1 := pt + Vector2(0.0, scale * 0.24)
		var c2 := pt + Vector2(scale * 0.22, scale * 0.34)
		canvas.draw_polyline(PackedVector2Array([c0, c1, c2]), Color(INK, 0.65), 1.8, true)

	# 2. LOW_OBSTACLE: low carved stone parapet (distinct warm mid-stone + horizontal cap)
	for cell in _cells_for(terrain_cells, "LOW_OBSTACLE"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var foot := hex_points(pt, scale * 0.86, sideways)
		canvas.draw_colored_polygon(foot, Color(LOW_COVER_FILL, 0.55))
		var wall := Rect2(pt + Vector2(-scale * 0.56, -scale * 0.22), Vector2(scale * 1.12, scale * 0.44))
		var cap := Rect2(pt + Vector2(-scale * 0.60, -scale * 0.30), Vector2(scale * 1.20, scale * 0.16))
		canvas.draw_rect(wall, LOW_COVER_FILL, true)
		canvas.draw_rect(cap, LOW_COVER_TOP, true)
		canvas.draw_rect(wall, INK, false, 2.0)
		canvas.draw_rect(cap, INK, false, 1.8)

	# 3. HIGH_OBSTACLE: tall fractured mirror stele (dark stone mass + bronze/mirror inlay + tall silhouette)
	for cell in _cells_for(terrain_cells, "HIGH_OBSTACLE"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var foot := hex_points(pt, scale * 0.90, sideways)
		canvas.draw_colored_polygon(foot, Color(INK, 0.42))
		var body := PackedVector2Array([
			pt + Vector2(-scale * 0.46, scale * 0.26),
			pt + Vector2(-scale * 0.40, -scale * 0.72),
			pt + Vector2(scale * 0.06, -scale * 0.86),
			pt + Vector2(scale * 0.44, -scale * 0.66),
			pt + Vector2(scale * 0.48, scale * 0.26),
		])
		canvas.draw_colored_polygon(body, HIGH_COVER_FILL)
		canvas.draw_polyline(_closed(body), INK, 2.4, true)
		var inset := Rect2(pt + Vector2(-scale * 0.24, -scale * 0.56), Vector2(scale * 0.48, scale * 0.62))
		canvas.draw_rect(inset, HIGH_COVER_MIRROR, true)
		canvas.draw_rect(inset, HIGH_COVER_BRONZE, false, 2.4)
		# Crack line for instant silhouette distinction from low cover
		canvas.draw_line(pt + Vector2(-scale * 0.08, -scale * 0.48), pt + Vector2(scale * 0.12, -scale * 0.10), Color(INK, 0.72), 1.6, true)


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

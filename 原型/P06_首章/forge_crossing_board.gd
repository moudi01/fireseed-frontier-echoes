extends RefCounted

# 2D hex-overlay and specification module for RG05 · G · FORGE_CROSSING (铸律工场, 90 cells).
# Live integration MUST pass authoritative terrain_cells & anchors from slice/board state
# (explicit empty groups prevent preview defaults from leaking into live battles).

const REGION_ID := "RG05"
const SITE_ID := "G"
const BOARD_ID := "FORGE_CROSSING"
const FIELD_ART := "res://assets/forge_crossing/forge_crossing_ink.png"

# Preview-only reference coordinates from local-handoff.json
const PREVIEW_CELLS := {
	"HIGH_OBSTACLE": [Vector2i(2, 3), Vector2i(6, 3)],
	"HIGH_GROUND": [Vector2i(-1, 4), Vector2i(7, 4)],
	"LOW_OBSTACLE": [Vector2i(2, 4), Vector2i(4, 4)],
}
const PREVIEW_ANCHORS := [Vector2i(1, 4), Vector2i(3, 4)]

const INK := Color("302a26")
const HIGH_GROUND_FILL := Color("d6cec0")
const HIGH_GROUND_RIM := Color("7d7466")
const LOW_COVER_FILL := Color("7d766d")
const LOW_COVER_TOP := Color("aca599")
const HIGH_COVER_FILL := Color("4b4743")
const HIGH_COVER_BRONZE := Color("9e8254")
const ANCHOR_RING := Color("3c7d8c")
const ANCHOR_CORE := Color("d6ba78")


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
	sideways := false,
	anchors: Array = []
) -> void:
	# 1. HIGH_GROUND: pale stone-and-iron gantry terrace
	for cell in _cells_for(terrain_cells, "HIGH_GROUND"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var base := hex_points(pt + Vector2(0, scale * 0.07), scale * 0.94, sideways)
		var top := hex_points(pt + Vector2(0, -scale * 0.06), scale * 0.84, sideways)
		canvas.draw_colored_polygon(base, Color(HIGH_GROUND_RIM, 0.76))
		canvas.draw_colored_polygon(top, Color(HIGH_GROUND_FILL, 0.92))
		canvas.draw_polyline(_closed(top), Color(HIGH_GROUND_RIM, 0.95), 2.0, true)
		var c0 := pt + Vector2(-scale * 0.22, scale * 0.34)
		var c1 := pt + Vector2(0.0, scale * 0.24)
		var c2 := pt + Vector2(scale * 0.22, scale * 0.34)
		canvas.draw_polyline(PackedVector2Array([c0, c1, c2]), Color(INK, 0.65), 1.8, true)

	# 2. Public Floor Anchors (cool bronze-teal geometric emblem so orange warnings stay high-contrast!)
	for cell in anchors:
		var g: Vector2i = cell if cell is Vector2i else Vector2i(int(cell[0]), int(cell[1]))
		if not coordinate_map.has(g):
			continue
		var pt: Vector2 = coordinate_map[g]
		var outer := hex_points(pt, scale * 0.74, sideways)
		canvas.draw_polyline(_closed(outer), Color(ANCHOR_RING, 0.92), 2.4, true)
		var d := scale * 0.34
		var diamond := PackedVector2Array([
			pt + Vector2(0, -d * 0.78), pt + Vector2(d, 0), pt + Vector2(0, d * 0.78), pt + Vector2(-d, 0),
		])
		canvas.draw_colored_polygon(diamond, Color(ANCHOR_CORE, 0.42))
		canvas.draw_polyline(_closed(diamond), Color(INK, 0.85), 1.8, true)

	# 3. LOW_OBSTACLE: low iron-bound forge anvil/trough
	for cell in _cells_for(terrain_cells, "LOW_OBSTACLE"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var foot := hex_points(pt, scale * 0.86, sideways)
		canvas.draw_colored_polygon(foot, Color(LOW_COVER_FILL, 0.54))
		var wall := Rect2(pt + Vector2(-scale * 0.56, -scale * 0.22), Vector2(scale * 1.12, scale * 0.44))
		var cap := Rect2(pt + Vector2(-scale * 0.60, -scale * 0.30), Vector2(scale * 1.20, scale * 0.16))
		canvas.draw_rect(wall, LOW_COVER_FILL, true)
		canvas.draw_rect(cap, LOW_COVER_TOP, true)
		canvas.draw_rect(wall, INK, false, 2.0)
		canvas.draw_rect(cap, INK, false, 1.8)

	# 4. HIGH_OBSTACLE: tall basalt/iron forge pillar
	for cell in _cells_for(terrain_cells, "HIGH_OBSTACLE"):
		if not coordinate_map.has(cell):
			continue
		var pt: Vector2 = coordinate_map[cell]
		var foot := hex_points(pt, scale * 0.90, sideways)
		canvas.draw_colored_polygon(foot, Color(INK, 0.44))
		var body := Rect2(pt + Vector2(-scale * 0.44, -scale * 0.80), Vector2(scale * 0.88, scale * 1.06))
		canvas.draw_rect(body, HIGH_COVER_FILL, true)
		canvas.draw_rect(body, INK, false, 2.4)
		var band := Rect2(pt + Vector2(-scale * 0.46, -scale * 0.48), Vector2(scale * 0.92, scale * 0.14))
		canvas.draw_rect(band, HIGH_COVER_BRONZE, true)
		canvas.draw_rect(band, INK, false, 1.6)


static func _cells_for(terrain_cells: Dictionary, key: String) -> Array:
	if terrain_cells.has(key):
		var raw = terrain_cells[key]
		if raw is Dictionary:
			return raw.keys()
		if raw is Array:
			return raw
	return []


static func _closed(pts: PackedVector2Array) -> PackedVector2Array:
	var out := pts.duplicate()
	if not out.is_empty():
		out.append(out[0])
	return out
